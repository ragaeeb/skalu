#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Bootstrap Skalu cloud setup for a project.

Usage:
  scripts/bootstrap_cloud.sh \
    [--region us-central1] \
    [--allowed-origins "*"] \
    [--project-id YOUR_PROJECT_ID] \
    [--github-owner YOUR_GITHUB_OWNER] \
    [--github-repo YOUR_GITHUB_REPO] \
    [--run-terraform-apply]

Notes:
- If terraform.tfvars does not exist, it is created from terraform.tfvars.example.
- Cloud Build's GitHub App connection requires a one-time interactive authorization in
  the Google Cloud console.
- If not provided, project/repo metadata is auto-detected from:
  - `gcloud config get-value project`
  - `frontend/package.json` repository metadata
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

seed_initial_image() {
  local image_ref="$1"
  echo "[bootstrap] Seeding initial image for first Cloud Run revision: ${image_ref}"
  gcloud builds submit "${ROOT_DIR}" \
    --project "${PROJECT_ID}" \
    --tag "${image_ref}" \
    --quiet
}

wait_for_image_tag() {
  local image_path="$1"
  local expected_tag="$2"
  local max_attempts="${3:-24}"
  local sleep_seconds="${4:-5}"
  local attempt=1

  echo "[bootstrap] Waiting for ${image_path}:${expected_tag} to be visible in Artifact Registry"
  while (( attempt <= max_attempts )); do
    if gcloud artifacts docker tags list "${image_path}" \
      --project "${PROJECT_ID}" \
      --format='value(tag)' 2>/dev/null | rg -qx "${expected_tag}"; then
      echo "[bootstrap] Found ${image_path}:${expected_tag}"
      return 0
    fi
    echo "[bootstrap] Tag not visible yet (attempt ${attempt}/${max_attempts}), retrying in ${sleep_seconds}s..."
    sleep "${sleep_seconds}"
    attempt=$((attempt + 1))
  done

  echo "[bootstrap] Timed out waiting for ${image_path}:${expected_tag}" >&2
  return 1
}

reset_unhealthy_service_if_needed() {
  local service_name="$1"
  local ready_status
  local latest_ready_revision

  if ! gcloud run services describe "${service_name}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" >/dev/null 2>&1; then
    return 0
  fi

  ready_status="$(gcloud run services describe "${service_name}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --format='value(status.conditions[?type=Ready].status)' 2>/dev/null || true)"
  latest_ready_revision="$(gcloud run services describe "${service_name}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --format='value(status.latestReadyRevisionName)' 2>/dev/null || true)"

  if [[ "${ready_status}" != "True" || -z "${latest_ready_revision}" ]]; then
    echo "[bootstrap] Detected unhealthy Cloud Run service ${service_name} (ready=${ready_status:-unknown}). Recreating it."
    gcloud run services delete "${service_name}" \
      --project "${PROJECT_ID}" \
      --region "${REGION}" \
      --quiet || true
  fi
}

resolve_project_id() {
  local current_value="$1"
  if [[ -z "${current_value}" || "${current_value}" == "(unset)" ]]; then
    echo ""
    return
  fi

  # Handle project number or project ID; normalize to canonical project ID.
  local normalized
  normalized="$(gcloud projects describe "${current_value}" --format='value(projectId)' 2>/dev/null || true)"
  echo "${normalized}"
}

read_repo_from_package_json() {
  local package_json_path="$1"
  python3 - "$package_json_path" <<'PY'
import json
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    print("|")
    raise SystemExit(0)

data = json.loads(path.read_text(encoding="utf-8"))
repository = data.get("repository")
url = ""
if isinstance(repository, str):
    url = repository
elif isinstance(repository, dict):
    url = str(repository.get("url") or "")

url = url.strip()
if not url:
    print("|")
    raise SystemExit(0)

# Supports forms like:
# - git+https://github.com/owner/repo.git
# - https://github.com/owner/repo
# - git@github.com:owner/repo.git
match = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)", url)
if not match:
    print("|")
    raise SystemExit(0)

print(f"{match.group('owner')}|{match.group('repo')}")
PY
}

PROJECT_ID_OVERRIDE=""
REGION="us-central1"
GITHUB_OWNER_OVERRIDE=""
GITHUB_REPO_OVERRIDE=""
ALLOWED_ORIGINS="*"
RUN_TF_APPLY="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-id)
      PROJECT_ID_OVERRIDE="${2:-}"
      shift 2
      ;;
    --region)
      REGION="${2:-}"
      shift 2
      ;;
    --github-owner)
      GITHUB_OWNER_OVERRIDE="${2:-}"
      shift 2
      ;;
    --github-repo)
      GITHUB_REPO_OVERRIDE="${2:-}"
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

require_cmd gcloud
require_cmd terraform
require_cmd gsutil
require_cmd python3

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA_DIR="${ROOT_DIR}/infra"
TFVARS_PATH="${INFRA_DIR}/terraform.tfvars"
PACKAGE_JSON_PATH="${ROOT_DIR}/frontend/package.json"

PROJECT_ID="${PROJECT_ID_OVERRIDE}"
if [[ -z "${PROJECT_ID}" ]]; then
  PROJECT_ID="$(resolve_project_id "$(gcloud config get-value project 2>/dev/null || true)")"
fi
if [[ -z "${PROJECT_ID}" ]]; then
  echo "Unable to determine project id. Set an active project or pass --project-id." >&2
  echo "Hint: gcloud config set project YOUR_PROJECT_ID" >&2
  exit 1
fi

REPO_META="$(read_repo_from_package_json "${PACKAGE_JSON_PATH}")"
DETECTED_OWNER="${REPO_META%%|*}"
DETECTED_REPO="${REPO_META##*|}"

GITHUB_OWNER="${GITHUB_OWNER_OVERRIDE:-${DETECTED_OWNER}}"
GITHUB_REPO="${GITHUB_REPO_OVERRIDE:-${DETECTED_REPO}}"
if [[ -z "${GITHUB_OWNER}" || -z "${GITHUB_REPO}" ]]; then
  echo "Unable to determine GitHub owner/repo from ${PACKAGE_JSON_PATH}." >&2
  echo "Pass --github-owner and --github-repo explicitly." >&2
  exit 1
fi

TFSTATE_BUCKET="skalu-tfstate-${PROJECT_ID}"

echo "[bootstrap] Resolved project=${PROJECT_ID} repo=${GITHUB_OWNER}/${GITHUB_REPO} region=${REGION}"
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

echo "[bootstrap] Writing terraform.tfvars"
cat > "${TFVARS_PATH}" <<EOF
project_id      = "${PROJECT_ID}"
region          = "${REGION}"
github_owner    = "${GITHUB_OWNER}"
github_repo     = "${GITHUB_REPO}"
allowed_origins = "${ALLOWED_ORIGINS}"
analyze_timeout_seconds = 3300
stream_heartbeat_seconds = 15
EOF

echo "[bootstrap] Running terraform plan"
terraform -chdir="${INFRA_DIR}" plan

if [[ "${RUN_TF_APPLY}" == "true" ]]; then
  SERVICE_NAME="skalu-api"
  IMAGE_REPO="${REGION}-docker.pkg.dev/${PROJECT_ID}/skalu/api"

  echo "[bootstrap] Applying Artifact Registry target first (bootstrap image seed prerequisite)"
  terraform -chdir="${INFRA_DIR}" apply -auto-approve -target=google_artifact_registry_repository.skalu

  seed_initial_image "${IMAGE_REPO}:latest"
  wait_for_image_tag "${IMAGE_REPO}" "latest"
  reset_unhealthy_service_if_needed "${SERVICE_NAME}"

  # Recover from a previously failed/tainted first Cloud Run create.
  terraform -chdir="${INFRA_DIR}" untaint google_cloud_run_v2_service.api >/dev/null 2>&1 || true

  echo "[bootstrap] Running full terraform apply"
  if ! terraform -chdir="${INFRA_DIR}" apply -auto-approve; then
    echo >&2
    echo "[bootstrap] Terraform apply failed." >&2
    echo "[bootstrap] If error includes 'Repository mapping does not exist'," >&2
    echo "[bootstrap] complete the one-time Cloud Build GitHub App repo connection in Console:" >&2
    echo "[bootstrap] https://console.cloud.google.com/cloud-build/triggers;region=global/connect?project=${PROJECT_ID}" >&2
    echo "[bootstrap] Then run: terraform -chdir=infra apply" >&2
    exit 1
  fi
else
  echo "[bootstrap] Skipping terraform apply (use --run-terraform-apply to apply)."
fi

echo
echo "[bootstrap] Done."
echo "Next:"
echo "1) If not applied yet: terraform -chdir=infra apply"
echo "2) In Cloud Console: connect GitHub repository to Cloud Build GitHub App"
echo "3) Push to main to trigger Cloud Build deploys"
