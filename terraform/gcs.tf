resource "google_storage_bucket" "media_uploads" {
  project                     = var.gcp_project_id
  name                        = var.media_bucket_name
  location                    = var.gcp_region // Or a multi-region if appropriate
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  force_destroy               = false // Set to true for non-prod

  versioning {
    enabled = true
  }

  # Delete incomplete multipart uploads after 7 days
  lifecycle_rule {
    action {
      type = "AbortIncompleteMultipartUpload"
    }
    condition {
      age = 7
    }
  }

  # Move objects to Nearline storage after 90 days
  lifecycle_rule {
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
    condition {
      age = 90
    }
  }

  # Delete old versions after 365 days
  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      num_newer_versions = 1
      age                = 365
    }
  }

  cors {
    origin          = ["http://localhost:3000", "https://${var.app_domain}"]
    method          = ["GET", "PUT", "POST", "DELETE"]
    response_header = ["Content-Type", "Authorization"]
    max_age_seconds = 3600
  }
}

# Specific IAM permissions for the media bucket
resource "google_storage_bucket_iam_member" "backend_sa_object_creator" {
  bucket = google_storage_bucket.media_uploads.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.backend_sa.email}"
}

resource "google_storage_bucket_iam_member" "backend_sa_object_viewer" {
  bucket = google_storage_bucket.media_uploads.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.backend_sa.email}"
}

resource "google_storage_bucket_iam_member" "crewai_sa_object_creator" {
  bucket = google_storage_bucket.media_uploads.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.crewai_sa.email}"
}

resource "google_storage_bucket_iam_member" "crewai_sa_object_viewer" {
  bucket = google_storage_bucket.media_uploads.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.crewai_sa.email}"
}

# IAM for public read access to the media bucket
resource "google_storage_bucket_iam_member" "media_bucket_public_viewer" {
  bucket = google_storage_bucket.media_uploads.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
} 