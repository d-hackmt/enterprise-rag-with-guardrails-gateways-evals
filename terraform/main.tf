# --- CORE INFRASTRUCTURE ---

# 1. Enable Required APIs
resource "google_project_service" "services" {
  for_each = toset([
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "aiplatform.googleapis.com",
    "discoveryengine.googleapis.com",
    "pubsub.googleapis.com",
    "eventarc.googleapis.com",
    "redis.googleapis.com",
    "vpcaccess.googleapis.com",
    "compute.googleapis.com",
    "documentai.googleapis.com"
  ])
  service = each.key
  disable_on_destroy = false
}

# 2. Get Project Data
data "google_project" "project" {
  project_id = var.project_id
}

# 3. Networking (Required for Redis)
resource "google_compute_network" "rag_vpc" {
  name                    = "rag-vpc"
  auto_create_subnetworks = true
  depends_on              = [google_project_service.services]
}

# 4. Redis Instance (Memorystore)
resource "google_redis_instance" "cache" {
  name           = "rag-cache"
  tier           = "BASIC"
  memory_size_gb = 1
  location_id    = "${var.region}-a"
  authorized_network = google_compute_network.rag_vpc.id

  redis_version     = "REDIS_6_X"
  display_name      = "RAG Semantic Cache"

  depends_on = [google_project_service.services]
}

# 5. Service Account for Ingestion
resource "google_service_account" "ingestion_sa" {
  account_id   = "rag-ingestion-sa"
  display_name = "RAG Ingestion Service Account"
}

# Grant SA permission to read from bucket and write to logs
resource "google_project_iam_member" "ingestion_roles" {
  for_each = toset([
    "roles/storage.objectAdmin",
    "roles/logging.logWriter",
    "roles/aiplatform.user",
    "roles/eventarc.eventReceiver",
    "roles/run.invoker",
    "roles/documentai.apiUser"
  ])
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.ingestion_sa.email}"
}

# 6. GCS Permissions for Eventarc
# GCS needs to be able to publish to PubSub to trigger Eventarc
data "google_storage_project_service_account" "gcs_account" {
  project = var.project_id
}

resource "google_project_iam_member" "gcs_pubsub_publishing" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${data.google_storage_project_service_account.gcs_account.email_address}"
}

# 7. Eventarc Service Agent Permissions
# GCP creates the service agent SA when eventarc.googleapis.com is enabled, but it
# takes a few seconds. time_sleep ensures the SA exists before we grant it the role.
resource "time_sleep" "wait_for_eventarc_sa" {
  create_duration = "30s"
  depends_on      = [google_project_service.services]
}

resource "google_project_iam_member" "eventarc_service_agent" {
  project = var.project_id
  role    = "roles/eventarc.serviceAgent"
  member  = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-eventarc.iam.gserviceaccount.com"
  depends_on = [time_sleep.wait_for_eventarc_sa]
}

# 8. Storage Buckets
resource "google_storage_bucket" "raw_data" {
  name     = "${var.project_id}-rag-raw"
  location = var.region
  uniform_bucket_level_access = true
  force_destroy = true
}

resource "google_storage_bucket" "processed_data" {
  name     = "${var.project_id}-rag-processed"
  location = var.region
  uniform_bucket_level_access = true
  force_destroy = true
}

# 8. Artifact Registry for Docker Images
resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = "${var.app_name}-repo"
  description   = "Docker repository for RAG Microservices"
  format        = "DOCKER"

  depends_on = [google_project_service.services]
}

# 9. Pre-destroy: delete all Docker images from Artifact Registry before the repo
#    can be destroyed. Without this, terraform destroy fails because AR repos cannot
#    be deleted while they still contain images.
resource "null_resource" "cleanup_images" {
  triggers = {
    project_id = var.project_id
    region     = var.region
    app_name   = var.app_name
  }

  provisioner "local-exec" {
    when        = destroy
    interpreter = ["powershell", "-Command"]
    command     = <<-EOT
      $repo = "${self.triggers.region}-docker.pkg.dev/${self.triggers.project_id}/${self.triggers.app_name}-repo"
      foreach ($svc in @("backend", "ui", "ingestion", "evals")) {
        Write-Host "Deleting $repo/$svc:latest ..."
        gcloud artifacts docker images delete "$repo/$svc`:latest" --quiet --delete-tags 2>$null
      }
      Write-Host "Artifact Registry images cleared."
    EOT
  }

  depends_on = [google_artifact_registry_repository.repo]
}
