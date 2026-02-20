output "api_url" {
  description = "Cloud Run API service URL"
  value       = google_cloud_run_v2_service.api.uri
}

output "artifact_registry_repo" {
  description = "Docker image repository path"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/skalu/api"
}

output "cloudbuild_deployer_service_account" {
  description = "Cloud Build deployer service account email"
  value       = google_service_account.cloudbuild_deployer.email
}

output "api_deploy_trigger_id" {
  description = "Cloud Build trigger ID for API deploys"
  value       = google_cloudbuild_trigger.api_deploy.trigger_id
}
