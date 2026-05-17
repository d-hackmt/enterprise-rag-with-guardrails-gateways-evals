# 🏢 GCP Roles & Services Deep-Dive

This document explains **why** we use specific Google Cloud services and **when** specific permissions are required.

---

## 🛠️ The Service Catalog

### 1. Cloud Run (Compute)
*   **Purpose**: To host the API and the UI as scalable, serverless containers.
*   **Roles Required**: `roles/run.admin` (to deploy) and `roles/run.invoker` (to visit the URL).

### 2. Vertex AI (AI Engine)
*   **Purpose**: Used for generating high-quality embeddings (`text-embedding-004`).
*   **Roles Required**: `roles/aiplatform.user` and `roles/discoveryengine.viewer`.

### 3. Document AI (The Parser)
*   **Purpose**: Used to parse complex PDFs and perform OCR.
*   **Roles Required**: `roles/documentai.apiUser`.



---

## 🤖 User vs. Service Account (The "Robot")

When running IAM `add-iam-policy-binding` commands (or clicking "+ Grant access" in the GCP Console), you are simply adding a new "Rule" (Role) to an existing identity. We grant access to two different entities for two distinct reasons:

### 1. The Human User (`user:your-email@gmail.com`)
You are the developer. We grant your personal email roles like `Cloud Run Admin` and `Artifact Registry Admin`.
* **Why?** So that when you run `gcloud run deploy` from your local terminal, Google Cloud recognizes you as an Admin and allows the deployment to proceed. It also allows you to test the API locally using Application Default Credentials.

### 2. The Cloud Run Robot (`serviceAccount:123456789-compute@developer.gserviceaccount.com`)
This is the **Default Compute Service Account**. 
* **Why?** When your code is running live in the cloud on Google Cloud Run, you are no longer there typing on a keyboard. The code acts on behalf of this "robot" Service Account. 
* We grant this robot access to roles like `Vertex AI User` and `Document AI API User` so that when your live Python app tries to embed a query or parse a PDF, the robot has permission to do so and doesn't crash with a `403 Permission Denied` error.

---

## 🔑 IAM Reference Table

| Principal | Role | Necessary For |
| :--- | :--- | :--- |
| **User Email** | `roles/owner` or `run.admin` | Initial project setup, local testing, & deployments. |
| **Compute SA** | `roles/storage.objectViewer` | Reading docs from GCS during ingestion. |
| **Compute SA** | `roles/documentai.apiUser` | Parsing documents in production. |
| **Compute SA** | `roles/aiplatform.user` | Generating embeddings in production. |

---

## 🔐 Permission Best Practices
*   **Least Privilege**: Never give a service account `roles/owner`. Only give the specific API roles listed above.
*   **Service Agents**: Some Google-internal accounts (like the Cloud Run Service Agent) need `roles/vpcaccess.user` to manage network bridges. This is often a missing step during manual configuration.
