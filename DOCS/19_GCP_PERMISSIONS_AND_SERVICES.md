# GCP Permissions & Services Reference

Complete reference of every GCP service and IAM role used in this project — what it does, why it's needed, and when it's active.

---

## GCP APIs (Services)

Enable all of these once per project:

```bash
gcloud services enable \
    artifactregistry.googleapis.com \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    documentai.googleapis.com \
    aiplatform.googleapis.com \
    discoveryengine.googleapis.com \
    compute.googleapis.com \
    vpcaccess.googleapis.com \
    sqladmin.googleapis.com \
    storage.googleapis.com
```

| API | Service Name | Why Needed | When Active |
|-----|-------------|-----------|-------------|
| `artifactregistry.googleapis.com` | Artifact Registry | Stores the Docker image built by Cloud Build | Build time + every Cloud Run deploy |
| `run.googleapis.com` | Cloud Run | Hosts the FastAPI backend as a serverless container | Always (production) |
| `cloudbuild.googleapis.com` | Cloud Build | Builds the Docker image in the cloud without local Docker | Every `gcloud builds submit` |
| `documentai.googleapis.com` | Document AI | High-fidelity PDF parsing and OCR during data ingestion | Ingestion pipeline only |
| `aiplatform.googleapis.com` | Vertex AI | Generates text embeddings for both ingestion and query-time vector search | Ingestion + every `/query` call |
| `discoveryengine.googleapis.com` | Vertex AI Search | Alternative search engine integration (wired up, optional) | Optional |
| `compute.googleapis.com` | Compute Engine | Required for VPC connector infrastructure | VPC networking |
| `vpcaccess.googleapis.com` | Serverless VPC Access | Allows Cloud Run to connect to private VPC resources | Only if using Cloud SQL or Redis |
| `sqladmin.googleapis.com` | Cloud SQL Admin | Manages Postgres instances for LangGraph checkpointer | Optional (not active in current deploy) |
| `storage.googleapis.com` | Cloud Storage | Stores raw and processed documents; Cloud Build source tarballs | Ingestion + every build |

---

## IAM Roles

### Principal 1 — User Account (`djadhwani20@gmail.com`)

Your personal account. Needs admin-level roles to manage infrastructure from the CLI.

| Role | Why Needed | When Used |
|------|-----------|-----------|
| `roles/run.admin` | Deploy, update, and delete Cloud Run services | Every `gcloud run deploy` |
| `roles/artifactregistry.admin` | Create repos and manage Docker images in Artifact Registry | Initial setup + image management |
| `roles/storage.admin` | Create GCS buckets, upload documents, manage lifecycle | Ingestion + bucket setup |
| `roles/cloudsql.client` | Connect to Cloud SQL Postgres from local machine | Local dev with Cloud SQL |
| `roles/aiplatform.user` | Call Vertex AI embedding and prediction APIs | Local ingestion + testing |
| `roles/documentai.apiUser` | Call Document AI to parse PDFs | Local ingestion pipeline |
| `roles/discoveryengine.editor` | Create and manage Vertex AI Search data stores | Optional search setup |
| `roles/vpcaccess.admin` | Create VPC connectors for private networking | VPC setup (one-time) |

---

### Principal 2 — Compute Service Account (`320432910529-compute@developer.gserviceaccount.com`)

The default GCP compute SA. In this project it acts as the **Cloud Build runner AND the Cloud Run runtime identity** — all build and runtime API calls go through this SA.

| Role | Why Needed | When Used |
|------|-----------|-----------|
| `roles/aiplatform.user` | Embed user queries via Vertex AI before searching Qdrant — **without this, every `/query` call fails with 403** | Every production query at runtime |
| `roles/documentai.apiUser` | Parse PDFs via Document AI during ingestion | Ingestion pipeline on Cloud Run |
| `roles/discoveryengine.editor` | Call Vertex AI Search APIs | Optional / search feature |
| `roles/storage.admin` | Read source tarballs from GCS during Cloud Build; Cloud Run pulls processed docs | Build time + ingestion |
| `roles/artifactregistry.writer` | Push the built Docker image to Artifact Registry after `gcloud builds submit` | Every build |
| `roles/logging.logWriter` | Write Cloud Build and Cloud Run logs to Cloud Logging | Build time + runtime |

---

### Principal 3 — Serverless Robot SA (`service-320432910529@serverless-robot-prod.iam.gserviceaccount.com`)

GCP-managed SA for Cloud Run's internal infrastructure agent.

| Role | Why Needed | When Used |
|------|-----------|-----------|
| `roles/vpcaccess.user` | Allows Cloud Run to attach to and route traffic through a VPC connector | Only when `--vpc-connector` is used in deploy |

---

## GCS Buckets

| Bucket | Purpose | Used By |
|--------|---------|---------|
| `dmtxpresss-rag-raw` | Raw uploaded documents (PDF, HTML, DOCX, PPTX, TXT) before processing | Ingestion pipeline — upload step |
| `dmtxpresss-rag-processed` | Chunked and processed document text ready for embedding | Ingestion pipeline — embed + index step |

---

## Permission → Error Mapping

Quick reference for diagnosing 403 errors:

| Error message | Missing permission | Fix |
|--------------|-------------------|-----|
| `Permission 'aiplatform.endpoints.predict' denied` | `roles/aiplatform.user` on compute SA | Grant to `320432910529-compute@...` |
| `Permission 'artifactregistry.repositories.uploadArtifacts' denied` | `roles/artifactregistry.writer` on compute SA | Grant to `320432910529-compute@...` |
| `storage.objects.get access denied` | `roles/storage.admin` on compute SA | Grant to `320432910529-compute@...` |
| `does not have permission to write logs to Cloud Logging` | `roles/logging.logWriter` on compute SA | Grant to `320432910529-compute@...` |
| `VPC connector does not exist or Cloud Run does not have permission` | `roles/vpcaccess.user` on serverless robot SA | Grant to `service-320432910529@...` |
| `documentai.processors.processDocument denied` | `roles/documentai.apiUser` on compute SA | Grant to `320432910529-compute@...` |

---

## What Runs Where

| Component | Runs On | Identity Used |
|-----------|---------|--------------|
| FastAPI `/query` backend | Cloud Run | `320432910529-compute@developer.gserviceaccount.com` |
| Docker image build | Cloud Build | `320432910529-compute@developer.gserviceaccount.com` |
| Data ingestion pipeline | Local machine | `djadhwani20@gmail.com` (ADC) |
| Streamlit Chat UI | Streamlit Cloud | No GCP identity — calls Cloud Run via HTTPS |
| Eval Streamlit App | Local machine | No GCP identity — calls Cloud Run via HTTPS |
