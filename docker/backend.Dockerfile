# --- BACKEND MICROSERVICE (FastAPI + LangGraph Agent) ---
FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    gcc g++ libgomp1 libmagic-dev \
    && rm -rf /var/lib/apt/lists/*

# Layer-cache: install deps before copying app code
COPY requirements-backend.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements-backend.txt

# Copy only the backend application code
COPY app/ ./app/

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
