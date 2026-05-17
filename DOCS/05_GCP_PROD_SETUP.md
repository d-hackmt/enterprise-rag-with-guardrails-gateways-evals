# 🛠️ GCP Production Setup

This guide details the manual and automated steps required to provision the Google Cloud environment for the Enterprise RAG Platform.

---

## 🚦 Phase 1: API Enablement
Before any service can be used, the following APIs must be enabled in your GCP Project:
```powershell
gcloud services enable \
    artifactregistry.googleapis.com \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    sqladmin.googleapis.com \
    documentai.googleapis.com \
    compute.googleapis.com \
    discoveryengine.googleapis.com
```

---

## 🏗️ Phase 2: Resource Provisioning

### 1. Cloud Storage (The Data Lake)
We use two buckets to separate "raw" input from "processed" knowledge.
*   **Raw Bucket**: `gs://[PROJECT]-rag-raw`
*   **Processed Bucket**: `gs://[PROJECT]-rag-processed`

### 2. Document AI (The Smart Parser)
You must create a **"Document OCR"** processor in the GCP Console.
*   **Location**: `us` or `eu`.
*   **ID**: Copy the Processor ID into your `.env` as `GCP_DOC_AI_PROCESSOR_ID`.

### 3. Serverless VPC Access (Networking)
To connect Cloud Run to private databases (Cloud SQL/Redis), a VPC connector is required.
*   **Name**: `rag-vps`
*   **Subnet**: `10.8.0.0/28`

---

## 🔑 Phase 3: IAM Least Privilege
We follow the principle of least privilege. Each service account should only have the roles it needs.

| Entity | Role Required | Purpose |
| :--- | :--- | :--- |
| **Developer Account** | `roles/owner` | Full setup and testing. |
| **Cloud Run SA** | `roles/documentai.apiUser` | To call the parsing API. |
| **Cloud Run SA** | `roles/documentai.apiUser` | To call the Document AI parser. |
| **Service Agent** | `roles/vpcaccess.user` | To manage the VPC bridge. |

---

## ⏩ Moving to Terraform (The Future)
Currently, these steps are documented in `commands.md`. In the next phase, we will adopt **Terraform** to automate this entire setup with a single `terraform apply` command.
