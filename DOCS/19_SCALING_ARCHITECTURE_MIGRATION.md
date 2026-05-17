# 🚀 Migration to Scalable Enterprise Architecture

This document outlines our roadmap for upgrading the existing application into a fully scalable, enterprise-grade distributed system. As usage grows, relying on a single monolith and manual ingestion scripts is no longer viable. We are adopting a robust microservices and event-driven architecture.

---

## 🏗️ Phase 1: Microservices & Infrastructure as Code (Terraform)
We are splitting the monolithic application into dedicated, containerized microservices and managing our entire cloud infrastructure using Terraform.

*   **What's added**:
    *   `terraform/`: This new directory contains the blueprints (`.tf` files) for our entire Google Cloud environment (Cloud Run, Cloud SQL, Redis, Eventarc, Service Accounts, etc.). This ensures our infrastructure is reproducible and version-controlled.
    *   `docker/`: Dedicated Dockerfiles for each microservice (`backend.Dockerfile`, `ui.Dockerfile`, `ingestion.Dockerfile`, `evals.Dockerfile`) to ensure clean separation of concerns and independent scaling on Cloud Run. Each service has its own `requirements-*.txt` — no shared dependency bloat.

## 💾 Phase 2: Persistent Agentic Memory (Postgres)
Currently, our LangGraph agent relies on in-memory checkpointing (`MemorySaver`). This means if the Cloud Run container restarts, user chat history is lost.

*   **What's added**:
    *   We are provisioning a **Cloud SQL (PostgreSQL)** database.
    *   We will upgrade our agent's state manager to use `PostgresSaver`. This guarantees that user conversation threads persist permanently across sessions and container restarts.

## ⚡ Phase 3: Event-Driven Ingestion (Eventarc)
Currently, data ingestion requires running a manual CLI script (`python -m app.ingestion.processor`). For enterprise scale, this must be automated.

*   **What's added**:
    *   A dedicated **Ingestion Cloud Run Service** running a lightweight FastAPI listener.
    *   **Google Eventarc**: We are configuring Eventarc triggers on our raw GCS buckets. Now, the moment a new document (PDF, HTML, etc.) is uploaded to the bucket, an event is fired that instantly triggers the ingestion service to parse, chunk, embed, and push the data to Qdrant without human intervention.

## 🧠 Phase 4: Semantic Caching (Redis)
Large Language Models (LLMs) are expensive and can add latency. If a user asks a question that was recently answered, we shouldn't waste tokens recalculating the response.

*   **What's added**:
    *   We are provisioning a **Memorystore (Redis)** instance.
    *   We are implementing a **Semantic Cache** using Vertex AI embeddings. Before the agent begins its complex RAG workflow, it checks Redis. If the new query is semantically similar (cosine distance < 0.15) to a previously answered question, the cached response is served instantly in ~50ms. The cache uses plain `redis-py` + `numpy` cosine similarity — no extra libraries required.

---

## 📊 Phase 5: Persistent Eval History (GCS + Cloud Run Evals Service)
The evaluation pipeline needed to be accessible without running code locally, and eval results needed to persist across sessions.

*   **What's added**:
    *   A dedicated **Evals Cloud Run Service** (`evals.Dockerfile`) running a Streamlit dashboard. Evaluators open the URL and run RAGAS evaluations against the production backend directly — no local setup required.
    *   **GCS persistence for eval results** — after each eval run, results are saved to `gs://{processed_bucket}/eval-results/` as a timestamped JSON file. The History tab in the Streamlit app loads these on startup, enabling score trend tracking across pipeline changes.
    *   **4-tab Streamlit UI**: Ground Truth → Live Pipeline → Eval Metrics → History.
