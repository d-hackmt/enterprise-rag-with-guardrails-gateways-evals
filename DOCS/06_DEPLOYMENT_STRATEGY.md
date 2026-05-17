# 🚀 Deployment Strategy

The project uses a **Cloud-Native CI/CD pipeline** that eliminates the need for local Docker installations. All builds and deployments happen directly on Google Cloud infrastructure.

---

## 🏗️ 1. Build Phase: Cloud Build
We use **Google Cloud Build** to convert our source code into a secure, production-ready container image.

### Process:
1.  **Submission**: Run `gcloud builds submit`.
2.  **Packaging**: Cloud Build reads the `Dockerfile`, installs `requirements.txt`, and packages the app.
3.  **Storage**: The resulting image is pushed to **Artifact Registry**.

---

## 🚢 2. Release Phase: Cloud Run
The container is deployed to **Google Cloud Run**, a serverless compute platform.

### Configuration:
*   **Memory**: `2Gi` (Required for the heavy AI libraries during startup).
*   **CPU**: `1.0` (Sufficient for high-speed API response).
*   **Concurrency**: `80` (Allows 80 users to share a single container instance).
*   **VPC Connection**: Routed through `rag-vps` to access internal DBs.

---

## 🔄 3. Continuous Updates
To update the system, simply rebuild the image and redeploy. Cloud Run handles a **"Blue-Green Deployment"** automatically:
1.  It starts the *new* version of your app.
2.  It waits for the new version to pass health checks.
3.  It slowly shifts 100% of the traffic to the new version.
4.  It shuts down the old version.

**Result**: Zero downtime for your users.

---

## 🛠️ Summary Command
```powershell
# The "One-Command" to build and deploy
gcloud builds submit --tag us-central1-docker.pkg.dev/[PROJECT]/rag-repo/rag-api:v1 .

gcloud run deploy rag-api --image ... [flags]
```
