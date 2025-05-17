variable "gcp_project_id" {
  description = "The GCP project ID."
  type        = string
}

variable "gcp_region" {
  description = "The GCP region for resources."
  type        = string
  default     = "us-central1" # Or your preferred default region
}

variable "db_name" {
  description = "Name for the primary database within the Cloud SQL instance."
  type        = string
  default     = "knowledge_base_TS"
}

variable "db_user_name" {
  description = "Username for the application database user."
  type        = string
  default     = "kc_app_user"
}

variable "db_tier" {
  description = "Machine tier for the Cloud SQL instance (e.g., db-g1-small)."
  type        = string
  default     = "db-g1-small"
}

variable "db_password_secret_name" {
  description = "Name for the Secret Manager secret storing the DB password."
  type        = string
  default     = "kc-db-password"
}

variable "db_instance_name" {
  description = "Name for the Cloud SQL database instance."
  type        = string
  default     = "knowledge-base-ts-db-instance"
}

variable "vpc_network_name" {
  description = "Name of the VPC network to connect Cloud SQL and Redis."
  type        = string
  default     = "default" // Assuming default VPC unless specified otherwise
}

variable "media_bucket_name" {
  description = "Globally unique name for the GCS bucket for media uploads."
  type        = string
  # No default, should be provided in tfvars for uniqueness
}

variable "redis_instance_name" {
  description = "Name for the Memorystore Redis instance."
  type        = string
  default     = "kc-redis-main"
}

variable "redis_tier" {
  description = "Tier for Redis (BASIC or STANDARD_HA)."
  type        = string
  default     = "BASIC" # Suitable for dev/testing, consider STANDARD_HA for prod
}

variable "redis_memory_size_gb" {
  description = "Memory size in GB for Redis."
  type        = number
  default     = 1
}

variable "backend_sa_name" {
  description = "Name for the Backend Service Account (e.g., kc-backend-sa)."
  type        = string
  default     = "kc-backend-sa"
}

variable "crewai_sa_name" {
  description = "Name for the CrewAI Services Service Account (e.g., kc-crewai-sa)."
  type        = string
  default     = "kc-crewai-sa"
}

variable "cicd_sa_name" {
  description = "Name for the CI/CD Pipeline Service Account (e.g., kc-cicd-sa)."
  type        = string
  default     = "kc-cicd-sa"
}

variable "openai_api_key_secret_name" {
  description = "Name for the Secret Manager secret storing the OpenAI API Key."
  type        = string
  default     = "kc-openai-api-key"
}

variable "openai_api_key" {
  description = "The OpenAI API Key. This should be provided via a secure .tfvars file."
  type        = string
  sensitive   = true
  # No default, must be provided if an OpenAI API key secret is to be created with a value
}

variable "gemini_api_key_secret_name" {
  description = "Name for the Secret Manager secret storing the Gemini API Key."
  type        = string
  default     = "kc-gemini-api-key"
}

variable "gemini_api_key" {
  description = "The Gemini API Key. This should be provided via a secure .tfvars file."
  type        = string
  sensitive   = true
  # No default, must be provided if a Gemini API key secret is to be created with a value
}

variable "app_domain" {
  description = "The domain name for the application (e.g., app.thinkstash.com)."
  type        = string
  default     = "localhost" # Default to localhost for development
}
// Add other common variables as needed 