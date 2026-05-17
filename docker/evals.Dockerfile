# --- EVALS MICROSERVICE (RAGAS eval suite + Guardrails testing) ---
# PyTorch-heavy image — kept separate so build time doesn't bleed into
# backend/ui/ingestion images.
FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

# Layer-cache: install deps before copying app code
COPY requirements-evals.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements-evals.txt

# Copy eval code + golden dataset
COPY evals/ ./evals/

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

EXPOSE 8080

# Cloud Run port 8080; for local: docker run -p 8501:8080 evals-image
CMD ["streamlit", "run", "evals/app.py", "--server.port=8080", "--server.address=0.0.0.0"]
