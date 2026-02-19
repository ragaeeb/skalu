variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "github_owner" {
  description = "GitHub organisation or username"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name (without owner)"
  type        = string
}

variable "allowed_origins" {
  description = "Comma-separated list of allowed CORS origins for the API"
  type        = string
}
