# --- UI MICROSERVICE (Streamlit chat frontend) ---
FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

# Layer-cache: install deps before copying app code
COPY requirements-ui.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements-ui.txt

# Copy only UI code
COPY ui/ ./ui/

ENV PYTHONUNBUFFERED=1
ENV PORT=8501

EXPOSE 8501

# Cloud Run routes to port 8501 (set via container_port in cloud_run.tf)
CMD ["streamlit", "run", "ui/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
