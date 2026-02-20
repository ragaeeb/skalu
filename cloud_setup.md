# Skalu Cloud Setup (Cloud Run Only, Cloud Build GitHub Deploys)

This setup deploys both backend API and frontend UI from a single Cloud Run service and a single Cloud Build trigger.

- Runtime: Cloud Run (`skalu-api`)
- CD: Cloud Build GitHub trigger on pushes to `main`
- IaC: Terraform (`infra/`)
- No Firebase required

Reference docs:
- Cloud Build GitHub repository triggers: https://docs.cloud.google.com/build/docs/automating-builds/github/build-repos-from-github
- Cloud Run continuous deploy quickstart: https://docs.cloud.google.com/run/docs/quickstarts/deploy-continuously
- Cloud Build pricing: https://cloud.google.com/build/pricing
- Cloud Run pricing: https://cloud.google.com/run/pricing

## 1) Install tools (first-time setup on macOS with Homebrew)

### 1.1 Install Homebrew (if not installed)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Then add Brew to your shell (Apple Silicon):

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

### 1.2 Install required CLIs

```bash
brew update
brew install --cask google-cloud-sdk
brew install hashicorp/tap/terraform bun uv
```

### 1.3 Verify tool versions

```bash
gcloud version
terraform version
bun --version
uv --version
```

Expected minimums:
- `terraform >= 1.9`
- `bun >= 1.3.9`

### 1.4 Authenticate gcloud

```bash
gcloud auth login
gcloud auth application-default login
```

## 2) Create/select your GCP project (first-time required)

If you do not already have a project for Skalu, create one:

```bash
gcloud projects create skalu-<unique-suffix> --name="Skalu"
```

Find/list projects (optional):

```bash
gcloud projects list
```

Set the project you want to use:

```bash
gcloud config set project YOUR_PROJECT_ID
```

Link billing to the project (required for Cloud Run/Cloud Build):
- In console: Billing -> My Projects -> Link billing account
- Or CLI (if you know your billing account ID):

```bash
gcloud billing projects link YOUR_PROJECT_ID --billing-account=XXXXXX-XXXXXX-XXXXXX
```

### 2.1 Set ADC quota project (important)

After login, set your project explicitly:

```bash
gcloud config set project YOUR_PROJECT_ID
```

Then set the Application Default Credentials quota project (this avoids the warning you saw):

```bash
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
```

Optional verification:

```bash
gcloud config get-value project
cat ~/.config/gcloud/application_default_credentials.json | rg quota_project_id
```

Expected behavior notes:
- If `gcloud config set project` warns about ADC quota mismatch, run `gcloud auth application-default set-quota-project YOUR_PROJECT_ID`.
- If it warns about missing `environment` tag, this is usually an org-policy recommendation. Setup can continue unless your organization enforces it as a hard requirement.

If your org requires the `environment` tag, ask your org admin for the tag key/value and then add it. Typical values are `Development`, `Staging`, `Test`, or `Production`.

List existing tag keys/values:

```bash
gcloud resource-manager tags keys list
gcloud resource-manager tags values list --parent=tagKeys/TAG_KEY_NUMERIC_ID
```

Bind tag value to your project:

```bash
gcloud resource-manager tags bindings create \
  --parent="//cloudresourcemanager.googleapis.com/projects/YOUR_PROJECT_ID" \
  --tag-value="tagValues/TAG_VALUE_NUMERIC_ID"
```

## 3) Fast path bootstrap

Run:

```bash
scripts/bootstrap_cloud.sh \
  --region us-central1 \
  --allowed-origins "*" \
  --run-terraform-apply
```

By default the script auto-detects:
- `project_id` from `gcloud config get-value project`
- GitHub owner/repo from `frontend/package.json` repository URL

You can override if needed:

```bash
scripts/bootstrap_cloud.sh \
  --project-id YOUR_PROJECT_ID \
  --github-owner YOUR_GITHUB_OWNER \
  --github-repo YOUR_GITHUB_REPO
```

What this does:
- sets gcloud project
- enables required APIs
- creates Terraform state bucket
- runs Terraform init/plan
- on `--run-terraform-apply`, does first-run bootstrap in this order:
  - applies Artifact Registry resource target
  - builds and pushes initial `api:latest` image with Cloud Build
  - waits until `api:latest` is visible in Artifact Registry
  - runs full Terraform apply
- creates Artifact Registry, Cloud Run service, Cloud Build trigger, and IAM bindings

## 4) One-time GitHub connection in Cloud Build

Cloud Build requires one interactive authorization to install/authorize the Cloud Build GitHub App for your repo.

In GCP Console:
1. Go to Cloud Build -> Triggers.
2. Click **Connect repository**.
3. Select GitHub and authorize the app for your org/repo.
4. Confirm your repo is visible to Cloud Build.

After this, Terraform-managed trigger (`skalu-api-deploy`) will fire on pushes to `main`.

## 5) Verify Terraform outputs

```bash
terraform -chdir=infra output
```

Important outputs:
- `api_url`
- `api_deploy_trigger_id`
- `cloudbuild_deployer_service_account`

## 6) Local verification (recommended before first push)

Backend + frontend together:

```bash
./dev_up.sh
```

Or separate:

Backend:

```bash
uv venv --python 3.14 .venv
source .venv/bin/activate
uv pip install -r requirements_dev.txt
pytest -q
python app.py
```

Frontend:

```bash
cd frontend
bun install
bun run test
bun run build
```

## 7) Deploy flow

Push to `main`:
- changes matching trigger paths run `cloudbuild/api.cloudbuild.yaml`
- pipeline runs frontend tests, builds bundled image, deploys Cloud Run, and smoke-checks `/health` + `/version`

## 8) Post-deploy checks

```bash
API_URL="$(terraform -chdir=infra output -raw api_url)"
curl -fsS "${API_URL}/health"
curl -fsS "${API_URL}/version"
```

## 9) Troubleshooting

- Trigger not firing:
  - verify Cloud Build GitHub connection is installed for the repo.
  - verify trigger branch regex is `^main$`.
- Warning when setting project:
  - message: `project ... lacks an 'environment' tag`
  - meaning: organization policy warning/recommendation about project tagging.
  - action: safe to continue for personal projects. If your org enforces tags, create/bind the required `environment` tag value:

```bash
gcloud resource-manager tags keys list
gcloud resource-manager tags values list --parent=tagKeys/TAG_KEY_NUMERIC_ID
gcloud resource-manager tags bindings create \
  --parent="//cloudresourcemanager.googleapis.com/projects/YOUR_PROJECT_ID" \
  --tag-value="tagValues/TAG_VALUE_NUMERIC_ID"
```
- Cloud Run deploy permission failure:
  - ensure Cloud Build deployer service account has `roles/run.admin`, `roles/artifactregistry.writer`, and `roles/iam.serviceAccountUser`.
- Terraform apply fails with reserved env var error:
  - message: `The following reserved env names were provided: PORT`
  - meaning: Cloud Run sets `PORT` automatically; it must not be set manually in service env vars.
  - action: remove `PORT` from `infra/main.tf`/deploy flags and re-run:

```bash
terraform -chdir=infra apply
```
- Terraform apply fails with image not found:
  - message: `Image '.../api:latest' not found`
  - meaning: Cloud Run service creation happened before any initial image was pushed.
  - action: use the updated bootstrap script (it seeds `api:latest` before full apply), then rerun:

```bash
scripts/bootstrap_cloud.sh \
  --region us-central1 \
  --allowed-origins "*" \
  --run-terraform-apply
```
- Terraform apply fails with startup probe error:
  - message: `Revision ... is not ready ... failed the configured startup probe checks`
  - meaning: a strict custom startup probe failed during first revision boot.
  - action: pull latest infra changes (custom startup/liveness probes removed), then rerun:

```bash
terraform -chdir=infra apply
```

If needed, inspect revision logs:

```bash
gcloud run services logs read skalu-api --region us-central1 --project YOUR_PROJECT_ID --limit=200
```
- Cloud Run logs show `Application exec likely failed` or `Application failed to start`:
  - meaning: container entrypoint/CMD failed before serving traffic.
  - action: pull latest `Dockerfile` (Cloud Run-safe startup command `python app.py`), rebuild/push bootstrap image, then re-apply:

```bash
scripts/bootstrap_cloud.sh \
  --region us-central1 \
  --allowed-origins "*" \
  --run-terraform-apply
```
- Terraform keeps failing while updating an existing broken `skalu-api` service:
  - symptom: Cloud Run service stays on a failed revision (for example `latestCreatedRevisionName` stuck on an older failed revision), often with old startup probe config.
  - action: delete the broken service and let Terraform recreate it:

```bash
gcloud run services delete skalu-api --project YOUR_PROJECT_ID --region us-central1 --quiet
terraform -chdir=infra apply
```

The bootstrap script now performs this reset automatically when it detects an unhealthy service.
- Terraform apply fails with deletion protection during replace:
  - message: `cannot destroy service without setting deletion_protection=false`
  - meaning: prior failed Cloud Run create left a tainted resource in state.
  - action: pull latest infra/script changes, then rerun bootstrap. If needed, recover manually:

```bash
terraform -chdir=infra untaint google_cloud_run_v2_service.api || true
terraform -chdir=infra apply
```
- Frontend not rendering on Cloud Run:
  - confirm container includes `frontend/dist` build output.
  - verify `/` on Cloud Run returns `index.html`.
