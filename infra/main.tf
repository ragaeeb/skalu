provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "firebase.googleapis.com",
    "firebasehosting.googleapis.com",
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

  template {
    scaling {
      min_instance_count = 1
      max_instance_count = 2
    }

    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/skalu/api:latest"

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
        name  = "PORT"
        value = "8080"
      }
      env {
        name  = "MAX_CONTENT_LENGTH"
        value = "10485760"
      }

      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 5
        period_seconds        = 5
        failure_threshold     = 10
      }

      liveness_probe {
        http_get {
          path = "/health"
        }
        period_seconds    = 30
        failure_threshold = 3
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

resource "google_iam_workload_identity_pool" "github" {
  depends_on                = [google_project_service.apis]
  workload_identity_pool_id = "github-pool"
  display_name              = "GitHub Actions Pool"
  description               = "Identity pool for GitHub Actions CI/CD"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub OIDC Provider"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.actor"      = "assertion.actor"
    "attribute.ref"        = "assertion.ref"
  }

  attribute_condition = "attribute.repository == '${var.github_owner}/${var.github_repo}'"
}

resource "google_service_account" "github_actions" {
  account_id   = "github-actions-sa"
  display_name = "GitHub Actions Service Account"
  description  = "Used by GitHub Actions to deploy Skalu"
}

locals {
  github_sa_roles = [
    "roles/run.admin",
    "roles/artifactregistry.writer",
    "roles/iam.serviceAccountUser",
    "roles/firebase.admin",
  ]
}

resource "google_project_iam_member" "github_actions_roles" {
  for_each = toset(local.github_sa_roles)
  project  = var.project_id
  role     = each.key
  member   = "serviceAccount:${google_service_account.github_actions.email}"
}

resource "google_service_account_iam_member" "wif_binding" {
  service_account_id = google_service_account.github_actions.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_owner}/${var.github_repo}"
}
