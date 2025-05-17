terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0" # Specify a recent, stable version
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
    random = {
      source = "hashicorp/random"
      version = "~> 3.0"
    }
  }
  required_version = ">= 1.0" # Specify Terraform version
}

provider "google" {
  project     = var.gcp_project_id
  region      = var.gcp_region
}

provider "google-beta" {
  project     = var.gcp_project_id
  region      = var.gcp_region
} 