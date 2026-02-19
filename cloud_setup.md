# Skalu Google Cloud Setup

This is the one-time setup for automated deploys to Cloud Run (API) and Firebase Hosting (frontend).

## 1) Install tools

- `gcloud`
- `terraform >= 1.9`
- `firebase-tools`
- `bun >= 1.3.9`
- `uv`

## 2) Create/select GCP project

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

Enable required services:

```bash
gcloud services enable \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  firebase.googleapis.com \
  firebasehosting.googleapis.com \
  storage.googleapis.com
```

## 3) Create Terraform state bucket

```bash
gsutil mb -l us-central1 gs://skalu-tfstate-YOUR_PROJECT_ID
gsutil versioning set on gs://skalu-tfstate-YOUR_PROJECT_ID
```

Initialize Terraform with backend bucket parameter:

```bash
cd infra
terraform init -backend-config="bucket=skalu-tfstate-YOUR_PROJECT_ID"
```

## 4) Configure tfvars and apply

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` values, then:

```bash
terraform plan
terraform apply
```

Capture outputs:

```bash
terraform output
```

## 5) Configure Firebase

```bash
firebase login
firebase projects:addfirebase YOUR_PROJECT_ID
firebase login:ci
```

Save the token from `firebase login:ci` as `FIREBASE_TOKEN` in GitHub secrets.

## 6) Required GitHub secrets

Add in repository settings:

- `GCP_PROJECT_ID`
- `GCP_WORKLOAD_IDENTITY_PROVIDER` (Terraform output)
- `GCP_SERVICE_ACCOUNT` (Terraform output)
- `VITE_API_URL` (Terraform `api_url` output)
- `FIREBASE_TOKEN` (from `firebase login:ci`)

## 7) Local verification

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
bunx playwright install chromium
bunx playwright test
bun run build
```

## 8) Deploy triggers

- Push backend changes to `main` to trigger `deploy-api.yml`.
- Push frontend changes to `main` to trigger `deploy-frontend.yml`.
