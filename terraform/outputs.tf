# --- Cloud SQL Outputs --- 
output "db_instance_connection_name" {
  description = "The connection name for the Cloud SQL instance, used by proxies and clients."
  value       = google_sql_database_instance.main_db_instance.connection_name
}

output "db_instance_private_ip" {
  description = "The private IP address assigned to the Cloud SQL instance."
  value       = google_sql_database_instance.main_db_instance.private_ip_address
}

output "db_password_secret_id" {
  description = "The ID of the Secret Manager secret containing the database password."
  value       = google_secret_manager_secret.db_password_secret.id
  sensitive   = true # Mark this output as sensitive
}

# --- GCS Outputs --- 
output "media_bucket_url" {
  description = "The gs:// URL for the media uploads bucket."
  value       = google_storage_bucket.media_uploads.url
}

# --- Redis Outputs --- 
output "redis_host" {
  description = "The host IP address of the Redis instance."
  value       = google_redis_instance.main_cache.host
}

output "redis_port" {
  description = "The port number of the Redis instance."
  value       = google_redis_instance.main_cache.port
} 