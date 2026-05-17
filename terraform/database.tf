# --- CLOUD SQL (POSTGRES) ---

resource "google_sql_database_instance" "postgres" {
  name             = "${var.app_name}-db"
  database_version = "POSTGRES_15"
  region           = var.region

  settings {
    tier = "db-f1-micro" # Smallest tier to keep costs low during dev
    
    ip_configuration {
      ipv4_enabled = true
      # No authorized_networks — Cloud Run connects via Unix socket (Cloud SQL Auth Proxy).
      # Public IP is required for the proxy to function but no direct TCP access is open.
    }
  }
  deletion_protection = false # Set to true for production!
}

resource "google_sql_database" "database" {
  name     = "rag_memory"
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_user" "users" {
  name     = "rag_admin"
  instance = google_sql_database_instance.postgres.name
  password = var.db_password
}
