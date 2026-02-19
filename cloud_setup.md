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
brew install terraform bun uv
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

## 2) Fast path bootstrap

Run:

```bash
scripts/bootstrap_cloud.sh \
  --project-id YOUR_PROJECT_ID \
  --github-owner YOUR_GITHUB_OWNER \
  --github-repo skalu \
  --region us-central1 \
  --allowed-origins "*" \
  --run-terraform-apply
```

What this does:
- sets gcloud project
- enables required APIs
- creates Terraform state bucket
- runs Terraform init/plan/apply
- creates Artifact Registry, Cloud Run service, Cloud Build trigger, and IAM bindings

## 3) One-time GitHub connection in Cloud Build

Cloud Build requires one interactive authorization to install/authorize the Cloud Build GitHub App for your repo.

In GCP Console:
1. Go to Cloud Build -> Triggers.
2. Click **Connect repository**.
3. Select GitHub and authorize the app for your org/repo.
4. Confirm your repo is visible to Cloud Build.

After this, Terraform-managed trigger (`skalu-api-deploy`) will fire on pushes to `main`.

## 4) Verify Terraform outputs

```bash
terraform -chdir=infra output
```

Important outputs:
- `api_url`
- `api_deploy_trigger_id`
- `cloudbuild_deployer_service_account`

## 5) Local verification (recommended before first push)

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

## 6) Deploy flow

Push to `main`:
- changes matching trigger paths run `cloudbuild/api.cloudbuild.yaml`
- pipeline runs frontend tests, builds bundled image, deploys Cloud Run, and smoke-checks `/health` + `/version`

## 7) Post-deploy checks

```bash
API_URL="$(terraform -chdir=infra output -raw api_url)"
curl -fsS "${API_URL}/health"
curl -fsS "${API_URL}/version"
```

## 8) Troubleshooting

- Trigger not firing:
  - verify Cloud Build GitHub connection is installed for the repo.
  - verify trigger branch regex is `^main$`.
- Cloud Run deploy permission failure:
  - ensure Cloud Build deployer service account has `roles/run.admin`, `roles/artifactregistry.writer`, and `roles/iam.serviceAccountUser`.
- Frontend not rendering on Cloud Run:
  - confirm container includes `frontend/dist` build output.
  - verify `/` on Cloud Run returns `index.html`.
