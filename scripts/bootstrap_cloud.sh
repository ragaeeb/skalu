#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Bootstrap Skalu cloud setup for a project.

Usage:
  scripts/bootstrap_cloud.sh \
    --project-id YOUR_PROJECT_ID \
    --github-owner YOUR_GITHUB_OWNER \
    --github-repo skalu \
    [--region us-central1] \
    [--allowed-origins "*"] \
    [--run-terraform-apply]

Notes:
- If terraform.tfvars does not exist, it is created from terraform.tfvars.example.
- Cloud Build's GitHub App connection requires a one-time interactive authorization in
  the Google Cloud console.
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

PROJECT_ID=""
REGION="us-central1"
GITHUB_OWNER=""
GITHUB_REPO=""
ALLOWED_ORIGINS=""
RUN_TF_APPLY="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-id)
      PROJECT_ID="${2:-}"
      shift 2
      ;;
    --region)
      REGION="${2:-}"
      shift 2
      ;;
    --github-owner)
      GITHUB_OWNER="${2:-}"
      shift 2
      ;;
    --github-repo)
      GITHUB_REPO="${2:-}"
      shift 2
      ;;
    --allowed-origins)
      ALLOWED_ORIGINS="${2:-}"
      shift 2
      ;;
    --run-terraform-apply)
      RUN_TF_APPLY="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${PROJECT_ID}" || -z "${GITHUB_OWNER}" || -z "${GITHUB_REPO}" ]]; then
  echo "Missing required args: --project-id, --github-owner, --github-repo" >&2
  usage
  exit 1
fi

require_cmd gcloud
require_cmd terraform
require_cmd gsutil

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA_DIR="${ROOT_DIR}/infra"
TFVARS_PATH="${INFRA_DIR}/terraform.tfvars"
TFSTATE_BUCKET="skalu-tfstate-${PROJECT_ID}"

echo "[bootstrap] Setting gcloud project to ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}" >/dev/null

echo "[bootstrap] Enabling required APIs"
gcloud services enable \
  cloudresourcemanager.googleapis.com \
  cloudbuild.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  storage.googleapis.com

if ! gsutil ls -b "gs://${TFSTATE_BUCKET}" >/dev/null 2>&1; then
  echo "[bootstrap] Creating Terraform state bucket gs://${TFSTATE_BUCKET}"
  gsutil mb -l "${REGION}" "gs://${TFSTATE_BUCKET}"
  gsutil versioning set on "gs://${TFSTATE_BUCKET}"
else
  echo "[bootstrap] Terraform state bucket already exists: gs://${TFSTATE_BUCKET}"
fi

echo "[bootstrap] Running terraform init"
terraform -chdir="${INFRA_DIR}" init -backend-config="bucket=${TFSTATE_BUCKET}" >/dev/null

if [[ ! -f "${TFVARS_PATH}" ]]; then
  echo "[bootstrap] Creating infra/terraform.tfvars from example"
  cp "${INFRA_DIR}/terraform.tfvars.example" "${TFVARS_PATH}"
fi

if [[ -n "${ALLOWED_ORIGINS}" ]]; then
  echo "[bootstrap] Writing terraform.tfvars with supplied values"
  cat > "${TFVARS_PATH}" <<EOF
project_id      = "${PROJECT_ID}"
region          = "${REGION}"
github_owner    = "${GITHUB_OWNER}"
github_repo     = "${GITHUB_REPO}"
allowed_origins = "${ALLOWED_ORIGINS}"
analyze_timeout_seconds = 3300
stream_heartbeat_seconds = 15
EOF
else
  echo "[bootstrap] Please edit ${TFVARS_PATH} before terraform apply."
fi

echo "[bootstrap] Running terraform plan"
terraform -chdir="${INFRA_DIR}" plan

if [[ "${RUN_TF_APPLY}" == "true" ]]; then
  echo "[bootstrap] Running terraform apply"
  terraform -chdir="${INFRA_DIR}" apply -auto-approve
else
  echo "[bootstrap] Skipping terraform apply (use --run-terraform-apply to apply)."
fi

echo
echo "[bootstrap] Done."
echo "Next:"
echo "1) If not applied yet: terraform -chdir=infra apply"
echo "2) In Cloud Console: connect GitHub repository to Cloud Build GitHub App"
echo "3) Push to main to trigger Cloud Build deploys"
