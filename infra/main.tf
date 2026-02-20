provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "cloudresourcemanager.googleapis.com",
  ])
  service            = each.key
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "skalu" {
  depends_on    = [google_project_service.apis]
  location      = var.region
  repository_id = "skalu"
  format        = "DOCKER"
  description   = "Skalu API container images"
}

resource "google_cloud_run_v2_service" "api" {
  depends_on = [google_project_service.apis]
  name       = "skalu-api"
  location   = var.region
  deletion_protection = false

  template {
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    max_instance_request_concurrency = 1
    timeout                          = "3600s"

    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/skalu/api:latest"
      command = ["/usr/local/bin/python"]
      args    = ["/app/app.py"]

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
        cpu_idle          = false
        startup_cpu_boost = true
      }

      env {
        name  = "ALLOWED_ORIGINS"
        value = var.allowed_origins
      }
      env {
        name  = "MAX_CONTENT_LENGTH"
        value = "10485760"
      }
      env {
        name  = "ANALYZE_TIMEOUT_SECONDS"
        value = tostring(var.analyze_timeout_seconds)
      }
      env {
        name  = "STREAM_HEARTBEAT_SECONDS"
        value = tostring(var.stream_heartbeat_seconds)
      }
    }

    annotations = {
      "run.googleapis.com/cpu-throttling" = "false"
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = google_cloud_run_v2_service.api.project
  location = google_cloud_run_v2_service.api.location
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

data "google_project" "current" {
  project_id = var.project_id
}

resource "google_service_account" "cloudbuild_deployer" {
  account_id   = "cloudbuild-deployer-sa"
  display_name = "Cloud Build Deployer"
  description  = "Used by Cloud Build triggers to deploy API and frontend"
}

locals {
  cloudbuild_deployer_roles = [
    "roles/cloudbuild.builds.builder",
    "roles/logging.logWriter",
    "roles/run.admin",
    "roles/artifactregistry.writer",
    "roles/iam.serviceAccountUser",
  ]
}

resource "google_project_iam_member" "cloudbuild_deployer_roles" {
  for_each = toset(local.cloudbuild_deployer_roles)
  project  = var.project_id
  role     = each.key
  member   = "serviceAccount:${google_service_account.cloudbuild_deployer.email}"
}

resource "google_service_account_iam_member" "cloudbuild_service_agent_can_act_as_deployer" {
  service_account_id = google_service_account.cloudbuild_deployer.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-cloudbuild.iam.gserviceaccount.com"
}

resource "google_service_account_iam_member" "cloudbuild_legacy_sa_can_act_as_deployer" {
  service_account_id = google_service_account.cloudbuild_deployer.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${data.google_project.current.number}@cloudbuild.gserviceaccount.com"
}

resource "google_cloudbuild_trigger" "api_deploy" {
  depends_on = [
    google_project_service.apis,
    google_artifact_registry_repository.skalu,
    google_project_iam_member.cloudbuild_deployer_roles,
    google_service_account_iam_member.cloudbuild_service_agent_can_act_as_deployer,
    google_service_account_iam_member.cloudbuild_legacy_sa_can_act_as_deployer,
  ]

  name        = "skalu-api-deploy"
  description = "Deploy Skalu backend to Cloud Run on pushes to main"
  filename    = "cloudbuild/api.cloudbuild.yaml"

  service_account = google_service_account.cloudbuild_deployer.id

  github {
    owner = var.github_owner
    name  = var.github_repo

    push {
      branch = "^main$"
    }
  }

  included_files = [
    "app.py",
    "backend/**",
    "frontend/**",
    "demo_utils.py",
    "skalu.py",
    "requirements.txt",
    "Dockerfile",
    "pyproject.toml",
    "cloudbuild/api.cloudbuild.yaml",
  ]

  substitutions = {
    _REGION                    = var.region
    _SERVICE                   = google_cloud_run_v2_service.api.name
    _IMAGE_REPO                = "${var.region}-docker.pkg.dev/${var.project_id}/skalu/api"
    _ALLOWED_ORIGINS           = var.allowed_origins
    _ANALYZE_TIMEOUT_SECONDS   = tostring(var.analyze_timeout_seconds)
    _STREAM_HEARTBEAT_SECONDS  = tostring(var.stream_heartbeat_seconds)
  }
}
