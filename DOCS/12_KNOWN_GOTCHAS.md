# ⚠️ Known Gotchas & Architectural Decisions

When building an Enterprise-grade system on Google Cloud, you will encounter specific platform quirks. This document tracks those "gotchas" and explains why our architecture is designed the way it is.

---

## 1. Document AI Multi-Region Limitation

**The Issue:** 
When processing documents, you might see this error:
`400 Request contains an invalid argument: 'us-central1' must match the server deployment 'us'`

**The Reason:**
Unlike Cloud Run or Cloud Storage, which can be deployed to highly specific single regions (like `us-central1` in Iowa), **Google Cloud Document AI** relies on massive, shared machine learning clusters. Because of this, Google forces you to create OCR processors in broad **multi-regions** like `us` (United States) or `eu` (Europe). 

**The Solution (Our Architecture):**
We deliberately separate our location variables:
*   `LOCATION="us-central1"`: Used for compute (Cloud Run) and Storage (GCS Buckets) to ensure low latency and specific data residency.
*   `GCP_DOC_AI_LOCATION="us"`: Used exclusively by the `loaders/pdf.py` parsing engine.

When we migrate to Terraform, this separation is standard practice and perfectly aligns with Google's Infrastructure-as-Code best practices.

---

## 2. Windows Permission Denied with `gsutil`

**The Issue:**
When running commands like `gsutil mb` on a Windows machine, you might encounter:
`[Errno 13] Permission denied: 'C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\platform/gsutil\VERSION'`

**The Reason:**
`gsutil` is a legacy Python-based tool bundled with the Google Cloud SDK. When executed, it attempts to read/write a `VERSION` file in its global installation directory. If your command prompt is not running as Administrator, Windows User Account Control (UAC) blocks this access.

**The Solution:**
We have officially deprecated `gsutil` in our project documentation. We now use the modern, compiled CLI tool `gcloud storage` (e.g., `gcloud storage buckets create`). The modern `gcloud storage` engine handles permissions correctly on Windows and is significantly faster for transferring large amounts of vector data.

---

## 3. Logfire Initialization Order (The "Poisoning" Bug)

**The Issue:**
When adding Logfire observability, you might see traces fail to appear in the dashboard, accompanied by the warning:
`No logs or spans will be created until logfire.configure() has been called.`

**The Reason:**
If any module in the application calls `logfire.info()` or `logfire.span()` *before* `logfire.configure()` has been executed, Logfire's internal state becomes "poisoned" for that process. It enters a silent, no-op mode and discards all subsequent traces, even if you call `.configure()` later. 

If we were to import `settings` from `app.config` at the top of `app/main.py` to get the `LOGFIRE_TOKEN`, Python's import engine could inadvertently load nested modules (like our reranker or LLM clients) which might contain module-level Logfire calls, triggering this poisoning effect.

**The Solution:**
We bypass the `config.py` file entirely at the very top of `app/main.py`. We load the environment variables directly using `os.getenv()` and configure Logfire **before any other application imports occur**. 

```python
# app/main.py
import logfire
import os
from dotenv import load_dotenv

load_dotenv()
logfire.configure(token=os.getenv("LOGFIRE_TOKEN"))

# Safe to import the rest of the application now!
from app.config import settings 
from app.agents.graph import rag_agent
```
This guarantees that Logfire is fully awake and tracing before the rest of the application is loaded into memory.

---

## 5. Eventarc Service Agent — Creation Race Condition

**The Issue:**
When running `terraform apply` for the first time, the Eventarc trigger creation fails with a 403 or 400 error referencing the Eventarc service agent SA even though `eventarc.googleapis.com` was just enabled.

**The Reason:**
GCP creates the Eventarc service agent SA (`service-{NUMBER}@gcp-sa-eventarc.iam.gserviceaccount.com`) **asynchronously** after the API is enabled. If Terraform immediately tries to bind `roles/eventarc.serviceAgent` to it, the SA may not exist yet and the IAM grant fails. There is no reliable synchronous CLI command to trigger creation (both `gcloud beta services identity create` and `gcloud services identity create` either require a beta component or don't exist in older SDK versions).

**The Solution:**
Use the `hashicorp/time` provider to insert a 30-second pause after the APIs are enabled, before the IAM binding runs:

```hcl
# terraform/main.tf
resource "time_sleep" "wait_for_eventarc_sa" {
  create_duration = "30s"
  depends_on      = [google_project_service.services]
}

resource "google_project_iam_member" "eventarc_service_agent" {
  project    = var.project_id
  role       = "roles/eventarc.serviceAgent"
  member     = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-eventarc.iam.gserviceaccount.com"
  depends_on = [time_sleep.wait_for_eventarc_sa]
}
```

After adding the `hashicorp/time` provider to `provider.tf`, run `terraform init` to download it before `terraform apply`.

---

## 6. HCL Semicolons in `env` Blocks

**The Issue:**
Terraform `plan` or `apply` fails with a parse error when `env` blocks in Cloud Run service definitions use semicolons:

```hcl
# ❌ INVALID HCL
env { name = "PROJECT_ID"; value = var.project_id }
```

**The Reason:**
HCL does not allow multiple arguments on one line separated by semicolons inside block bodies. Each argument must be on its own line.

**The Solution:**
Expand every `env` block to multi-line format:

```hcl
# ✅ CORRECT
env {
  name  = "PROJECT_ID"
  value = var.project_id
}
```

---

## 7. `terraform.tfvars` — Never Commit Secrets

**The Issue:**
`terraform.tfvars` contains plaintext API keys (`groq_api_key`, `qdrant_api_key`, `db_password`, etc.). If accidentally committed, these leak to anyone who can read the repository.

**The Reason:**
Terraform reads `terraform.tfvars` automatically — it's designed to hold the actual values for variables defined in `variables.tf`. There is no built-in secrets management; values are plaintext.

**The Solution:**
- `terraform.tfvars` is in `.gitignore` — verify it stays excluded before every commit
- A `terraform.tfvars.example` file with placeholder values is tracked in git so students know what fields to fill
- On CI/CD, use environment variables (`TF_VAR_groq_api_key=...`) rather than committing tfvars

---

## 4. The "Lazy Loading" Pattern (Vertex AI & FlashRank)

**The Issue:**
Loading heavy machine learning models (like FlashRank) or initializing large SDKs (like Vertex AI) at the very top of your files can cause two major problems:
1.  **FastAPI Startup Delays**: The server won't start responding to health checks until the models are loaded, which can cause Cloud Run to think the container failed to start.
2.  **Logfire Poisoning**: If these SDKs make any internal calls before Logfire is configured, they can "poison" the process, causing your traces to disappear.

**The Solution:**
We implemented a **Lazy Loading** pattern across the entire application. We do not initialize Vertex AI or the Ranker at the module level. Instead, we wrap them in "getter" functions that only trigger the first time they are actually needed.

```python
# app/services/retrieval/embedding.py
def get_embedding_model():
    global model
    if model is None:
        # Initialized ONLY on first use!
        vertexai.init(project=settings.PROJECT_ID, location=settings.LOCATION)
        model = TextEmbeddingModel.from_pretrained("text-embedding-004")
    return model
```

This ensures your FastAPI server starts in **milliseconds**, and Logfire is guaranteed to be active before any AI service is touched.
