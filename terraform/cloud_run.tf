
# --- CLOUD RUN SERVICES ---

# 1. Backend API Service
resource "google_cloud_run_v2_service" "backend" {
  name     = "${var.app_name}-backend"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    vpc_access {
      network_interfaces {
        network = google_compute_network.rag_vpc.name
      }
      egress = "PRIVATE_RANGES_ONLY"
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.postgres.connection_name]
      }
    }

    scaling {
      min_instance_count = 1
      max_instance_count = 10
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.app_name}-repo/backend:latest"

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "2Gi"
        }
      }

      # --- GCP Core ---
      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "LOCATION"
        value = var.region
      }
      env {
        name  = "GCP_RAW_BUCKET"
        value = google_storage_bucket.raw_data.name
      }
      env {
        name  = "GCP_PROCESSED_BUCKET"
        value = google_storage_bucket.processed_data.name
      }
      env {
        name  = "GCP_DOC_AI_LOCATION"
        value = "us"
      }
      env {
        name  = "GCP_DOC_AI_PROCESSOR_ID"
        value = var.doc_ai_processor_id
      }

      # --- LLM ---
      env {
        name  = "GROQ_API_KEY"
        value = var.groq_api_key
      }
      env {
        name  = "GROQ_FALLBACK_API_KEY"
        value = var.groq_fallback_api_key
      }

      # --- LLM Gateway (Portkey) ---
      env {
        name  = "PORTKEY_API_KEY"
        value = var.portkey_api_key
      }
      env {
        name  = "PORTKEY_CONFIG_ID"
        value = var.portkey_config_id
      }

      # --- Guardrails (NVIDIA) ---
      env {
        name  = "NVIDIA_API_KEY"
        value = var.nvidia_api_key
      }

      # --- Vector DB ---
      env {
        name  = "QDRANT_CLUSTER_ENDPOINT"
        value = var.qdrant_url
      }
      env {
        name  = "QDRANT_API_KEY"
        value = var.qdrant_api_key
      }

      # --- Postgres Memory ---
      env {
        name  = "DB_CONNECTION_NAME"
        value = google_sql_database_instance.postgres.connection_name
      }
      env {
        name  = "DB_USER"
        value = "rag_admin"
      }
      env {
        name  = "DB_PASS"
        value = var.db_password
      }
      env {
        name  = "DB_NAME"
        value = "rag_memory"
      }
      env {
        name  = "DB_HOST"
        value = "/cloudsql/${google_sql_database_instance.postgres.connection_name}"
      }
      env {
        name  = "LOCAL_MODE"
        value = "false"
      }

      # --- Redis Semantic Cache ---
      env {
        name  = "REDIS_HOST"
        value = google_redis_instance.cache.host
      }
      env {
        name  = "REDIS_PORT"
        value = "6379"
      }
      env {
        name  = "USE_SEMANTIC_CACHE"
        value = "true"
      }

      # --- Observability ---
      env {
        name  = "LOGFIRE_TOKEN"
        value = var.logfire_token
      }
      env {
        name  = "LANGSMITH_TRACING"
        value = "true"
      }
      env {
        name  = "LANGSMITH_API_KEY"
        value = var.langsmith_api_key
      }
      env {
        name  = "LANGSMITH_PROJECT"
        value = var.langsmith_project
      }
      env {
        name  = "LANGSMITH_ENDPOINT"
        value = "https://api.smith.langchain.com"
      }
    }
  }

  depends_on = [google_project_service.services]
}


# 2. UI Service
resource "google_cloud_run_v2_service" "ui" {
  name     = "${var.app_name}-ui"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.app_name}-repo/ui:latest"

      ports {
        container_port = 8501
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }

      env {
        name  = "BACKEND_URL"
        value = google_cloud_run_v2_service.backend.uri
      }
      env {
        name  = "LOGFIRE_TOKEN"
        value = var.logfire_token
      }
      env {
        name  = "LANGSMITH_TRACING"
        value = "true"
      }
      env {
        name  = "LANGSMITH_API_KEY"
        value = var.langsmith_api_key
      }
      env {
        name  = "LANGSMITH_PROJECT"
        value = var.langsmith_project
      }
      env {
        name  = "LANGSMITH_ENDPOINT"
        value = "https://api.smith.langchain.com"
      }
    }
  }

  depends_on = [google_cloud_run_v2_service.backend]
}


# 3. Evals Service
resource "google_cloud_run_v2_service" "evals" {
  name     = "${var.app_name}-evals"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    timeout = "3600s"

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.app_name}-repo/evals:latest"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "4Gi"
        }
      }

      env {
        name  = "BACKEND_URL"
        value = google_cloud_run_v2_service.backend.uri
      }
      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "LOCATION"
        value = var.region
      }
      env {
        name  = "GCP_PROCESSED_BUCKET"
        value = google_storage_bucket.processed_data.name
      }
      env {
        name  = "JUDGE_GROQ"
        value = var.judge_groq
      }
      env {
        name  = "LOGFIRE_TOKEN"
        value = var.logfire_token
      }
      env {
        name  = "LANGSMITH_TRACING"
        value = "true"
      }
      env {
        name  = "LANGSMITH_API_KEY"
        value = var.langsmith_api_key
      }
      env {
        name  = "LANGSMITH_PROJECT"
        value = var.langsmith_project
      }
      env {
        name  = "LANGSMITH_ENDPOINT"
        value = "https://api.smith.langchain.com"
      }
    }
  }

  depends_on = [google_cloud_run_v2_service.backend]
}


# --- PUBLIC ACCESS (Unauthenticated for Demo) ---
resource "google_cloud_run_v2_service_iam_member" "backend_public" {
  name     = google_cloud_run_v2_service.backend.name
  location = google_cloud_run_v2_service.backend.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "ui_public" {
  name     = google_cloud_run_v2_service.ui.name
  location = google_cloud_run_v2_service.ui.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "evals_public" {
  name     = google_cloud_run_v2_service.evals.name
  location = google_cloud_run_v2_service.evals.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
