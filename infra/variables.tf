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
  description = "GitHub organization or username for Cloud Build trigger source"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name (without owner) for Cloud Build trigger source"
  type        = string
}

variable "allowed_origins" {
  description = "Comma-separated list of allowed CORS origins for the API"
  type        = string
}

variable "analyze_timeout_seconds" {
  description = "Maximum analysis duration for a single request."
  type        = number
  default     = 3300
}

variable "stream_heartbeat_seconds" {
  description = "Heartbeat interval for NDJSON streaming responses."
  type        = number
  default     = 15
}
