# --- Service Accounts --- 
resource "google_service_account" "backend_sa" {
  project      = var.gcp_project_id
  account_id   = var.backend_sa_name
  display_name = "Knowledge Card Backend Service Account"
}

resource "google_service_account" "crewai_sa" {
  project      = var.gcp_project_id
  account_id   = var.crewai_sa_name
  display_name = "Knowledge Card CrewAI Services Service Account"
}

resource "google_service_account" "cicd_sa" {
  project      = var.gcp_project_id
  account_id   = var.cicd_sa_name
  display_name = "Knowledge Card CI/CD Pipeline Service Account"
}

# --- OpenAI API Key Secret --- 
resource "google_secret_manager_secret" "openai_api_key_secret" {
  project   = var.gcp_project_id
  secret_id = var.openai_api_key_secret_name

  replication {
    auto {}
  }
  # Depends on the Secret Manager API being enabled (already in main.tf)
  depends_on = [google_project_service.project_services["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret_version" "openai_api_key_version" {
  secret      = google_secret_manager_secret.openai_api_key_secret.id
  secret_data = var.openai_api_key # This comes from terraform.tfvars (sensitive)

  # Prevent Terraform from showing diffs if the key is updated outside Terraform,
  # or if var.openai_api_key is null and the secret is populated manually later.
  lifecycle {
    ignore_changes = [secret_data]
  }
}

# --- Gemini API Key Secret --- 
resource "google_secret_manager_secret" "gemini_api_key_secret" {
  project   = var.gcp_project_id
  secret_id = var.gemini_api_key_secret_name

  replication {
    auto {}
  }
  depends_on = [google_project_service.project_services["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret_version" "gemini_api_key_version" {
  secret      = google_secret_manager_secret.gemini_api_key_secret.id
  secret_data = var.gemini_api_key # This comes from terraform.tfvars (sensitive)

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# --- IAM Permissions for Service Accounts --- 

# Backend SA Permissions
resource "google_project_iam_member" "backend_sa_sql_client" {
  project = var.gcp_project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}

resource "google_project_iam_member" "backend_sa_storage_object_admin" {
  project = var.gcp_project_id
  role    = "roles/storage.objectAdmin" # Consider scoping to specific buckets in production
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}

resource "google_project_iam_member" "backend_sa_redis_editor" {
  project = var.gcp_project_id
  role    = "roles/redis.editor"
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}

resource "google_project_iam_member" "backend_sa_secret_accessor" {
  project = var.gcp_project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}

# CrewAI SA Permissions (starting with Secret Accessor)
resource "google_project_iam_member" "crewai_sa_secret_accessor" {
  project = var.gcp_project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.crewai_sa.email}"
}

# CI/CD SA Permissions (basic roles for now, more might be needed for CICD-1)
# Example: Allow CI/CD to act as (impersonate) other service accounts if needed for deployment
resource "google_project_iam_member" "cicd_sa_service_account_user" {
  project = var.gcp_project_id
  role    = "roles/iam.serviceAccountUser" # Allows impersonation
  member  = "serviceAccount:${google_service_account.cicd_sa.email}"
}

# Example: Allow CI/CD to manage Cloud Run services
resource "google_project_iam_member" "cicd_sa_run_admin" {
  project = var.gcp_project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.cicd_sa.email}"
}

# Example: Allow CI/CD to write to Artifact Registry
resource "google_project_iam_member" "cicd_sa_artifact_registry_writer" {
  project = var.gcp_project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.cicd_sa.email}"
}

# --- Secret Accessor Permissions --- 

# Grant Backend SA access to the DB Password Secret
resource "google_secret_manager_secret_iam_member" "backend_sa_access_db_password" {
  project   = var.gcp_project_id # Or google_secret_manager_secret.db_password_secret.project
  secret_id = google_secret_manager_secret.db_password_secret.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.backend_sa.email}"

  # Ensure this depends on both the secret and the SA existing
  depends_on = [
    google_secret_manager_secret.db_password_secret,
    google_service_account.backend_sa
  ]
}

# Grant CrewAI SA access to the OpenAI API Key Secret
resource "google_secret_manager_secret_iam_member" "crewai_sa_access_openai_api_key" {
  project   = var.gcp_project_id 
  secret_id = google_secret_manager_secret.openai_api_key_secret.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.crewai_sa.email}"

  depends_on = [
    google_secret_manager_secret.openai_api_key_secret,
    google_service_account.crewai_sa
  ]
}

# Grant CrewAI SA access to the Gemini API Key Secret
resource "google_secret_manager_secret_iam_member" "crewai_sa_access_gemini_api_key" {
  project   = var.gcp_project_id 
  secret_id = google_secret_manager_secret.gemini_api_key_secret.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.crewai_sa.email}"

  depends_on = [
    google_secret_manager_secret.gemini_api_key_secret,
    google_service_account.crewai_sa
  ]
} 