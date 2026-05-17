# --- INGESTION MICROSERVICE (Eventarc webhook + document parsing) ---
FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    gcc g++ libgomp1 libmagic-dev \
    libxcb1 libx11-6 libxrender1 libxext6 libgl1 \
    poppler-utils libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Layer-cache: install deps before copying app code
COPY requirements-ingestion.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements-ingestion.txt

# Copy only ingestion code
COPY app/ ./app/

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

EXPOSE 8080

CMD ["uvicorn", "app.ingestion.processor:app", "--host", "0.0.0.0", "--port", "8080"]
