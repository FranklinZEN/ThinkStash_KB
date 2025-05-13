terraform {
  backend "gcs" {
    bucket  = "thinkstash-knowledge-base-tf-state"
    prefix  = "terraform/state/knowledge_card_system" # Or your desired state path
  }
} 