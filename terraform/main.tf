// Example: Enable necessary APIs (adjust as needed)
resource "google_project_service" "project_services" {
  project = var.gcp_project_id
  for_each = toset([
    "compute.googleapis.com",
    "sqladmin.googleapis.com",
    "storage.googleapis.com",
    "redis.googleapis.com",
    "iam.googleapis.com",
    "secretmanager.googleapis.com",
    "run.googleapis.com",          // For Cloud Run
    "container.googleapis.com",    // For GKE (if chosen)
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",   // If using Cloud Build
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "servicenetworking.googleapis.com" // Needed for private service access
  ])
  service                    = each.key
  disable_dependent_services = true // Set to false if you want to auto-enable dependencies
  disable_on_destroy         = false // Set to true if you want to disable services on destroy
}

// Example: Basic VPC Network (if not using default)
/*
resource "google_compute_network" "main_vpc" {
  project                 = var.gcp_project_id
  name                    = "kc-main-vpc"
  auto_create_subnetworks = true // Or false for custom subnets
}
*/ 