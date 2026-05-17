"""
GCS persistence for eval runs.
Saves results to GCP_PROCESSED_BUCKET under the eval-results/ prefix.
Silently skips if GCP_PROCESSED_BUCKET is not set (local dev without GCS).
"""

import os
import json
import logfire
from datetime import datetime, timezone

BUCKET  = os.getenv("GCP_PROCESSED_BUCKET")
PREFIX  = "eval-results/"


def _client():
    from google.cloud import storage
    return storage.Client()


def save_eval_run(metric_results: dict, label: str = "") -> str | None:
    """
    Serialises metric DataFrames to JSON and uploads to GCS.
    Returns the GCS URI on success, None if BUCKET is not configured.
    """
    if not BUCKET:
        logfire.warning("GCP_PROCESSED_BUCKET not set — skipping GCS save.")
        return None

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    blob_path = f"{PREFIX}{timestamp}.json"

    payload = {
        "timestamp": timestamp,
        "label":     label or timestamp,
        "averages":  {
            key: round(float(df[key].mean()), 3)
            for key, df in metric_results.items()
        },
        "per_question": {
            key: df.to_dict(orient="records")
            for key, df in metric_results.items()
        },
    }

    try:
        client  = _client()
        bucket  = client.bucket(BUCKET)
        blob    = bucket.blob(blob_path)
        blob.upload_from_string(
            json.dumps(payload, indent=2),
            content_type="application/json",
        )
        uri = f"gs://{BUCKET}/{blob_path}"
        logfire.info(f"✅ Eval run saved to {uri}")
        return uri
    except Exception as e:
        logfire.error(f"❌ Failed to save eval run: {e}")
        return None


def list_eval_runs() -> list[dict]:
    """
    Returns all past eval runs from GCS sorted newest-first.
    Each entry: {path, timestamp, label, averages}
    """
    if not BUCKET:
        return []
    try:
        client  = _client()
        bucket  = client.bucket(BUCKET)
        blobs   = list(bucket.list_blobs(prefix=PREFIX))
        runs    = []
        for blob in blobs:
            if not blob.name.endswith(".json"):
                continue
            try:
                data = json.loads(blob.download_as_string())
                runs.append({
                    "path":      blob.name,
                    "timestamp": data.get("timestamp", blob.name),
                    "label":     data.get("label", blob.name),
                    "averages":  data.get("averages", {}),
                })
            except Exception:
                continue
        return sorted(runs, key=lambda x: x["timestamp"], reverse=True)
    except Exception as e:
        logfire.error(f"❌ Failed to list eval runs: {e}")
        return []


def load_eval_run(path: str) -> dict | None:
    """Downloads and returns a specific eval run JSON from GCS."""
    if not BUCKET:
        return None
    try:
        client = _client()
        bucket = client.bucket(BUCKET)
        blob   = bucket.blob(path)
        return json.loads(blob.download_as_string())
    except Exception as e:
        logfire.error(f"❌ Failed to load eval run {path}: {e}")
        return None
