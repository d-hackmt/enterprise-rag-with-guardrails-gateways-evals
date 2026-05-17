output "backend_url" {
  value       = google_cloud_run_v2_service.backend.uri
  description = "Public URL of the FastAPI backend"
}

output "ui_url" {
  value       = google_cloud_run_v2_service.ui.uri
  description = "Public URL of the Streamlit UI"
}

output "db_public_ip" {
  value       = google_sql_database_instance.postgres.public_ip_address
  description = "Public IP of the Cloud SQL Postgres instance"
}

output "db_connection_name" {
  value       = google_sql_database_instance.postgres.connection_name
  description = "Cloud SQL connection name (project:region:instance)"
}

output "redis_host" {
  value       = google_redis_instance.cache.host
  description = "Private IP of the Redis Memorystore instance (only reachable inside VPC)"
}

output "evals_url" {
  value       = google_cloud_run_v2_service.evals.uri
  description = "Public URL of the Evals Streamlit UI"
}

output "ingestion_url" {
  value       = google_cloud_run_v2_service.ingestion.uri
  description = "Internal URL of the Ingestion service (Eventarc only — not publicly reachable)"
}

output "artifact_repo" {
  value       = google_artifact_registry_repository.repo.name
  description = "Artifact Registry repository name"
}
