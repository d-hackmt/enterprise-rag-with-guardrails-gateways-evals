"""
Ingestion service — dual-mode:
  CLI mode  : python -m app.ingestion.processor DATA/ [--wipe]
              Reads local files, uploads to RAW bucket, then processes.
  Cloud mode: uvicorn app.ingestion.processor:app --port 8080
              Receives Eventarc webhook (GCS object.finalized), downloads file
              from GCS, and processes WITHOUT re-uploading to RAW bucket.

Loop-proofing (critical for Eventarc):
  The Eventarc trigger watches the RAW bucket. The service MUST NOT write back
  to the RAW bucket in cloud mode — that would re-trigger the event infinitely.
  Bucket isolation: RAW bucket → triggers ingestion → writes only to PROCESSED bucket.
"""

import os
import sys
import uuid
import json
import tempfile
import logfire
import vertexai

from typing import List
from fastapi import FastAPI, Request, BackgroundTasks
from google.cloud import storage
from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.config import settings
from app.services.retrieval.embedding import embed_texts
from app.ingestion.loaders.pdf import parse_pdf
from app.ingestion.loaders.html import parse_html
from app.ingestion.loaders.text import parse_text
from app.ingestion.chunking.splitter import chunk_text

logfire.configure(service_name="enterprise-ingestion-service")

vertexai.init(project=settings.PROJECT_ID, location=settings.LOCATION)

storage_client = storage.Client(project=settings.PROJECT_ID)

qdrant_client = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY,
)

# ── FastAPI app (used in Cloud Run / Eventarc webhook mode) ──────────────────

app = FastAPI(title="RAG Ingestion Service")


@app.get("/")
def health():
    return {"status": "ok", "service": "RAG Ingestion", "mode": "cloud"}


@app.post("/ingest")
async def ingest_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Eventarc endpoint — receives GCS object.finalized events.
    Downloads the file from GCS (already in RAW bucket) and processes it
    WITHOUT uploading back to RAW (that would cause an infinite event loop).
    """
    body = await request.json()

    # Eventarc delivers the GCS object metadata directly in the request body.
    # Handle both direct payload and wrapped {"data": {...}} format.
    data = body.get("data", body)
    bucket_name = data.get("bucket")
    object_name = data.get("name")   # e.g. "true/my_document.pdf"

    if not bucket_name or not object_name:
        logfire.warning("⚠️ Webhook received invalid payload", body=str(body)[:200])
        return {"status": "error", "message": "Missing bucket or name in payload"}

    # Infer source_type from the GCS path prefix (e.g. "true/doc.pdf" → "true")
    parts = object_name.split("/")
    source_type = parts[0] if len(parts) > 1 else "general"
    filename    = parts[-1]

    logfire.info(f"📥 Webhook received: gs://{bucket_name}/{object_name}")

    # Process in background — return 200 immediately so Eventarc doesn't retry
    background_tasks.add_task(_process_from_gcs, bucket_name, object_name, filename, source_type)

    return {"status": "accepted", "file": object_name}


# ── Core processing functions ────────────────────────────────────────────────

def upload_to_gcs(data, bucket_name: str, destination_blob_name: str, is_json: bool = False):
    with logfire.span("☁️ GCS Upload", bucket=bucket_name, blob=destination_blob_name):
        try:
            bucket = storage_client.bucket(bucket_name)
            blob   = bucket.blob(destination_blob_name)
            if is_json:
                blob.upload_from_string(json.dumps(data), content_type="application/json")
            else:
                blob.upload_from_filename(data)
            logfire.info(f"✅ Uploaded to {bucket_name}/{destination_blob_name}")
        except Exception as e:
            logfire.error(f"❌ GCS Upload Failed: {e}")
            raise


def _ensure_collection():
    if not qdrant_client.collection_exists(settings.QDRANT_COLLECTION):
        qdrant_client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
        )
        logfire.info(f"🆕 Created Qdrant collection '{settings.QDRANT_COLLECTION}'")


def process_file(file_path: str, filename: str, source_type: str, skip_raw_upload: bool = False):
    """
    Orchestrates parse → chunk → embed → index for a single file.

    skip_raw_upload=True  : Cloud/webhook mode — file is already in RAW bucket.
                            Skipping re-upload prevents the Eventarc feedback loop.
    skip_raw_upload=False : CLI mode — upload the local file to RAW bucket first.
    """
    with logfire.span("🚀 Processing File", file=filename, source=source_type,
                      cloud_mode=skip_raw_upload):
        try:
            _ensure_collection()

            # Step 1: Upload RAW file to GCS (CLI mode only)
            raw_gcs_path = f"{source_type}/{filename}"
            if not skip_raw_upload:
                upload_to_gcs(file_path, settings.RAW_BUCKET, raw_gcs_path)
            else:
                logfire.info(f"⏩ Skipping RAW upload (cloud mode) — file already at gs://{settings.RAW_BUCKET}/{raw_gcs_path}")

            # Step 2: Extract text
            ext = filename.lower().split(".")[-1]
            if ext == "pdf":
                full_text = parse_pdf(file_path)
            elif ext in ("html", "htm"):
                full_text = parse_html(file_path)
            elif ext == "txt":
                full_text = parse_text(file_path)
            elif ext in ("docx", "pptx"):
                from app.ingestion.loaders.office import parse_office
                full_text = parse_office(file_path)
            else:
                logfire.warning(f"⏩ Skipping unsupported file type: {filename}")
                return

            if not full_text or not full_text.strip():
                logfire.warning(f"⚠️ No text extracted from {filename}")
                return

            # Step 3: Chunk
            chunks = chunk_text(full_text)
            if not chunks:
                return

            # Step 4: Upload PROCESSED metadata to GCS (PROCESSED bucket — safe, no loop risk)
            processed_data     = {"filename": filename, "chunks": chunks, "source_type": source_type}
            processed_gcs_path = f"{source_type}/{filename}.json"
            upload_to_gcs(processed_data, settings.PROCESSED_BUCKET, processed_gcs_path, is_json=True)

            # Step 5: Embed and index in Qdrant
            with logfire.span("🧠 Vectorizing & Indexing"):
                embeddings = embed_texts(chunks)
                points = [
                    models.PointStruct(
                        id=str(uuid.uuid4()),
                        vector=vector,
                        payload={
                            "text": chunk,
                            "source": filename,
                            "source_type": source_type,
                            "raw_gcs_path": f"gs://{settings.RAW_BUCKET}/{raw_gcs_path}",
                        },
                    )
                    for chunk, vector in zip(chunks, embeddings)
                ]
                qdrant_client.upsert(
                    collection_name=settings.QDRANT_COLLECTION,
                    points=points,
                )
                logfire.info(f"✨ Indexed {len(points)} points to Qdrant from '{filename}'")

        except Exception as e:
            logfire.error(f"💥 Failed to process {filename}: {e}")


def _process_from_gcs(bucket_name: str, object_name: str, filename: str, source_type: str):
    """
    Cloud/webhook helper: downloads file from GCS to a temp path, then processes it.
    skip_raw_upload=True ensures we never write back to the RAW bucket.
    """
    with logfire.span("☁️ Cloud Mode: Download & Process", file=object_name):
        try:
            ext = filename.lower().split(".")[-1]
            with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
                tmp_path = tmp.name

            bucket = storage_client.bucket(bucket_name)
            blob   = bucket.blob(object_name)
            blob.download_to_filename(tmp_path)
            logfire.info(f"⬇️ Downloaded gs://{bucket_name}/{object_name} → {tmp_path}")

            process_file(tmp_path, filename, source_type, skip_raw_upload=True)

        except Exception as e:
            logfire.error(f"❌ Cloud processing failed for {object_name}: {e}")
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


# ── CLI mode ─────────────────────────────────────────────────────────────────

def run_universal_ingestion(base_dir: str, explicit_source_type: str = None, wipe: bool = False):
    """
    CLI entry point — scans a local directory, uploads files to RAW bucket, then processes.
    """
    with logfire.span("🌍 Universal Ingestion Started", base_directory=base_dir):
        if wipe:
            with logfire.span("🧹 Wiping Collection"):
                if qdrant_client.collection_exists(settings.QDRANT_COLLECTION):
                    qdrant_client.delete_collection(settings.QDRANT_COLLECTION)
                    logfire.info(f"🗑️ Collection '{settings.QDRANT_COLLECTION}' deleted")

        _ensure_collection()

        subdirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]

        if not subdirs:
            if explicit_source_type:
                source_type = explicit_source_type
            else:
                base_name   = os.path.basename(os.path.normpath(base_dir)).lower()
                source_type = "true" if "true" in base_name else "noisy" if "noisy" in base_name else "general"
            logfire.info(f"📂 No subdirectories — processing {base_dir} as '{source_type}'")
            _process_directory(base_dir, source_type)
        else:
            for subdir in subdirs:
                source_type = "true" if "true" in subdir.lower() else "noisy" if "noisy" in subdir.lower() else subdir
                _process_directory(os.path.join(base_dir, subdir), source_type)


def _process_directory(dir_path: str, source_type: str):
    with logfire.span("📁 Scanning Directory", path=dir_path, source=source_type):
        files = [f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))]
        logfire.info(f"🔍 Found {len(files)} files")
        for filename in files:
            process_file(os.path.join(dir_path, filename), filename, source_type, skip_raw_upload=False)


if __name__ == "__main__":
    wipe_requested = "--wipe" in sys.argv
    clean_args     = [a for a in sys.argv if a != "--wipe"]
    target_dir     = clean_args[1] if len(clean_args) > 1 else "DATA"
    explicit_type  = clean_args[2] if len(clean_args) > 2 else None

    if not os.path.exists(target_dir):
        print(f"Error: Path {target_dir} does not exist.")
        sys.exit(1)

    run_universal_ingestion(target_dir, explicit_source_type=explicit_type, wipe=wipe_requested)
    logfire.info("🏁 Universal Ingestion Job Completed")
