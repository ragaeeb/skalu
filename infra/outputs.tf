output "api_url" {
  description = "Cloud Run API service URL"
  value       = google_cloud_run_v2_service.api.uri
}

output "artifact_registry_repo" {
  description = "Docker image repository path"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/skalu/api"
}

output "workload_identity_provider" {
  description = "WIF provider - add as GCP_WORKLOAD_IDENTITY_PROVIDER GitHub secret"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "github_actions_service_account" {
  description = "SA email - add as GCP_SERVICE_ACCOUNT GitHub secret"
  value       = google_service_account.github_actions.email
}
