# --- AUTO-INGESTION (EVENTARC TRIGGER) ---

# 1. The Ingestion Service (Receives the trigger)
resource "google_cloud_run_v2_service" "ingestion" {
  name     = "${var.app_name}-ingestion"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY" # Only Eventarc can talk to this

  template {
    service_account = google_service_account.ingestion_sa.email
    
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.postgres.connection_name]
      }
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.app_name}-repo/ingestion:latest"
      
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

      env {
        name  = "QDRANT_CLUSTER_ENDPOINT"
        value = var.qdrant_url
      }
      env {
        name  = "QDRANT_API_KEY"
        value = var.qdrant_api_key
      }
      env {
        name  = "DB_CONNECTION_NAME"
        value = google_sql_database_instance.postgres.connection_name
      }
      env {
        name  = "PROJECT_ID"
        value = var.project_id
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
      env {
        name  = "GCP_DOC_AI_PROCESSOR_ID"
        value = var.doc_ai_processor_id
      }
      env {
        name  = "GCP_DOC_AI_LOCATION"
        value = "us" # Document AI is usually 'us' or 'eu'
      }
    }
  }
}



# 2. Eventarc Trigger (Watches GCS)
resource "google_eventarc_trigger" "gcs_trigger" {
  name     = "rag-gcs-trigger"
  location = var.region
  
  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }

  matching_criteria {
    attribute = "bucket"
    value     = google_storage_bucket.raw_data.name
  }

  destination {
    cloud_run_service {
      service = google_cloud_run_v2_service.ingestion.name
      region  = var.region
      path    = "/ingest"
    }
  }

  service_account = google_service_account.ingestion_sa.email

  depends_on = [
    google_project_iam_member.ingestion_roles,
    google_project_iam_member.gcs_pubsub_publishing,
    google_project_iam_member.eventarc_service_agent,
  ]
}


