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
} 