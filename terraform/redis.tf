resource "google_redis_instance" "main_cache" {
  project          = var.gcp_project_id
  name             = var.redis_instance_name
  tier             = var.redis_tier
  memory_size_gb   = var.redis_memory_size_gb
  location_id      = "${var.gcp_region}-a" # Explicitly setting to zone 'a' in the region
  # For STANDARD_HA, location_id could be a specific zone like var.gcp_region + "-a"
  # However, the 'region' field below is also required and should match var.gcp_region
  region           = var.gcp_region 

  connect_mode     = "PRIVATE_SERVICE_ACCESS"
  authorized_network = "projects/${var.gcp_project_id}/global/networks/${var.vpc_network_name}"

  # transit_encryption_mode = "SERVER_AUTHENTICATION" # Recommended for production
  # maintenance_policy { ... } # Optional, can be configured as needed

  # Ensure PSA is configured and the Redis API is enabled
  depends_on = [
    google_service_networking_connection.private_vpc_connection,
    google_project_service.project_services["redis.googleapis.com"]
  ]
} 