# Production Deployment

## Target topology

- Web: Vercel;
- API: Google Cloud Run service;
- Worker: Cloud Run service with always-allocated CPU and one instance;
- Scheduler: Cloud Run service with one instance and idempotent enqueueing;
- Migration: Cloud Run Job;
- Database: Cloud SQL PostgreSQL 16 with pgvector;
- Object storage: GCS, S3 or Cloudflare R2;
- AI: OpenAI API;
- secrets: Google Secret Manager.

## Prerequisites

1. A GCP project with billing enabled;
2. a production domain for the Web application;
3. Terraform 1.8+ and gcloud;
4. official provider API keys;
5. licensed market-data contracts for any restricted series;
6. an OpenAI project and key.

## Provision infrastructure

```bash
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

Before `apply`, create the Secret Manager secrets listed in `variables.tf` and add enabled `latest` versions. The two database URL secrets should use the Cloud SQL connection method selected by your organization.

## Database setup

```bash
gcloud run jobs execute macrolens-production-migrate --region us-central1 --wait
# one-time seed
gcloud run jobs update macrolens-production-migrate \
  --command python --args=-m,macrolens_api.cli,seed
gcloud run jobs execute macrolens-production-migrate --region us-central1 --wait
```

Restore the migration command after seeding. Change the administrator password through a controlled procedure.

## Vercel

Set the project root to the repository root and build command to:

```bash
npm --workspace apps/web run build
```

Required variable:

```text
NEXT_PUBLIC_API_URL=https://API_HOST/api/v1
```

The API `WEB_ORIGIN` must exactly match the production Vercel custom domain.

## Release procedure

1. merge only after CI passes;
2. build and push an immutable image tagged with the commit SHA;
3. execute migrations as a Cloud Run Job;
4. deploy API, Worker and Scheduler with the same backend image;
5. deploy Web;
6. run health, login and critical-path checks;
7. monitor ingestion lag, errors and database load;
8. retain the previous image and database restore point for rollback.

## Rollback

- Application: redeploy the previous immutable image and Web deployment.
- Database: forward-fix is preferred. Destructive down migrations are prohibited in production.
- Data publication: activate the previous publication batch; never delete vintages.
