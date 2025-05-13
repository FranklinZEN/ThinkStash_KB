# --- Random Password Generation for DB --- 
resource "random_password" "db_password" {
  length           = 16
  special          = true
  override_special = "_%@" 
}

# --- Store DB Password in Secret Manager --- 
resource "google_secret_manager_secret" "db_password_secret" {
  project   = var.gcp_project_id
  secret_id = "kc-db-password"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_password_version" {
  secret      = google_secret_manager_secret.db_password_secret.id
  secret_data = random_password.db_password.result

  lifecycle {
    ignore_changes = [secret_data] # Prevent Terraform from trying to update the password on every run 
  }
}

# --- Configure Private Service Access --- 
resource "google_compute_global_address" "private_ip_address" {
  project       = var.gcp_project_id
  name          = "private-ip-for-google-services"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  ip_version    = "IPV4"
  network       = "projects/${var.gcp_project_id}/global/networks/${var.vpc_network_name}"
  prefix_length = 16 # Adjust range if needed 
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = "projects/${var.gcp_project_id}/global/networks/${var.vpc_network_name}"
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_address.name]
}

# --- Provision Cloud SQL Instance --- 
resource "google_sql_database_instance" "main_db_instance" {
  project             = var.gcp_project_id
  name                = var.db_instance_name 
  database_version    = "POSTGRES_15"
  region              = var.gcp_region

  settings {
    tier = var.db_tier
    ip_configuration {
      ipv4_enabled    = true
      private_network = "projects/${var.gcp_project_id}/global/networks/${var.vpc_network_name}"
      require_ssl     = true
    }
    backup_configuration {
      enabled            = true
      point_in_time_recovery_enabled = true
      backup_retention_settings {
        retained_backups = 7 
      }
    }
    database_flags {
      name  = "log_min_duration_statement" 
      value = "250" # Log slow queries 
    }
    # Add insights_config and other settings as needed 
  }

  # Ensure PSA is configured before creating the instance 
  depends_on = [google_service_networking_connection.private_vpc_connection]

  deletion_protection = false # Set to true for production 
}

# --- Create Application Database --- 
resource "google_sql_database" "app_db" {
  project  = var.gcp_project_id
  instance = google_sql_database_instance.main_db_instance.name
  name     = var.db_name
}

# --- Create Application DB User --- 
resource "google_sql_user" "app_user" {
  project  = var.gcp_project_id
  instance = google_sql_database_instance.main_db_instance.name
  name     = var.db_user_name
  password = random_password.db_password.result

  # Terraform manages the password; reference the random password directly.
  # Application should retrieve password from Secret Manager. 
} 