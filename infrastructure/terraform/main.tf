locals {
  name = "macrolens-${var.environment}"
  common_env = {
    ENVIRONMENT                       = var.environment
    LOG_LEVEL                         = "INFO"
    WEB_ORIGIN                        = var.web_origin
    COOKIE_SECURE                     = "true"
    COOKIE_SAMESITE                   = "none"
    ALLOW_PUBLIC_REGISTRATION         = "false"
    BOOTSTRAP_ADMIN_EMAIL             = "admin@macrolens.local"
    S3_BUCKET                         = google_storage_bucket.assets.name
    S3_REGION                         = var.region
    S3_ENDPOINT_URL                   = "https://storage.googleapis.com"
    OPENAI_MODEL                      = "gpt-5.6-terra"
    OPENAI_BASE_URL                   = ""
    OPENAI_DEEP_RESEARCH_MODEL        = "gpt-5.6"
    OPENAI_EMBEDDING_MODEL            = "text-embedding-3-small"
    OPENAI_STORE                      = "false"
    OTEL_EXPORTER_OTLP_ENDPOINT       = ""
  }
  secret_env = {
    DATABASE_URL                      = var.secret_names.database_url_async
    DATABASE_URL_SYNC                 = var.secret_names.database_url_sync
    JWT_SECRET                        = var.secret_names.jwt_secret
    BOOTSTRAP_ADMIN_PASSWORD          = var.secret_names.bootstrap_admin_password
    S3_ACCESS_KEY_ID                  = var.secret_names.s3_access_key_id
    S3_SECRET_ACCESS_KEY              = var.secret_names.s3_secret_access_key
    FRED_API_KEY                      = var.secret_names.fred_api_key
    BEA_API_KEY                       = var.secret_names.bea_api_key
    BLS_API_KEY                       = var.secret_names.bls_api_key
    EIA_API_KEY                       = var.secret_names.eia_api_key
    CENSUS_API_KEY                    = var.secret_names.census_api_key
    OPENAI_API_KEY                    = var.secret_names.openai_api_key
  }
}

resource "google_project_service" "services" {
  for_each = toset([
    "artifactregistry.googleapis.com",
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
    "cloudscheduler.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "backend" {
  depends_on    = [google_project_service.services]
  location      = var.region
  repository_id = var.artifact_repository
  description   = "MacroLens production container images"
  format        = "DOCKER"
}

resource "google_service_account" "runtime" {
  account_id   = "${local.name}-runtime"
  display_name = "MacroLens ${var.environment} runtime"
}

resource "google_project_iam_member" "runtime_roles" {
  for_each = toset([
    "roles/cloudsql.client",
    "roles/secretmanager.secretAccessor",
    "roles/storage.objectAdmin",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_sql_database_instance" "postgres" {
  depends_on          = [google_project_service.services]
  name                = "${local.name}-postgres"
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = var.environment == "production"

  settings {
    tier              = var.database_tier
    availability_type = var.environment == "production" ? "REGIONAL" : "ZONAL"
    disk_type         = "PD_SSD"
    disk_size         = var.database_disk_size_gb
    disk_autoresize   = true

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "03:00"
      backup_retention_settings {
        retained_backups = var.environment == "production" ? 30 : 7
        retention_unit   = "COUNT"
      }
    }

    maintenance_window {
      day          = 7
      hour         = 4
      update_track = "stable"
    }

    insights_config {
      query_insights_enabled  = true
      record_application_tags = true
      record_client_address   = false
    }

    ip_configuration {
      ipv4_enabled = true
      ssl_mode     = "ENCRYPTED_ONLY"
    }
  }
}

resource "google_sql_database" "database" {
  name     = "macrolens"
  instance = google_sql_database_instance.postgres.name
}

resource "random_password" "database" {
  length           = 32
  special          = true
  override_special = "-_!"
}

resource "google_sql_user" "application" {
  name     = "macrolens"
  instance = google_sql_database_instance.postgres.name
  password = random_password.database.result
}

resource "google_storage_bucket" "assets" {
  name                        = "${var.project_id}-${local.name}-assets"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false

  versioning { enabled = true }
  lifecycle_rule {
    condition { age = 365 }
    action { type = "SetStorageClass" storage_class = "NEARLINE" }
  }
  lifecycle_rule {
    condition { age = 2555 }
    action { type = "Delete" }
  }
}

resource "google_cloud_run_v2_service" "api" {
  depends_on          = [google_project_service.services, google_project_iam_member.runtime_roles]
  name                = "${local.name}-api"
  location            = var.region
  deletion_protection = var.environment == "production"
  ingress             = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.runtime.email
    timeout         = "300s"
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.postgres.connection_name]
      }
    }
    scaling {
      min_instance_count = var.api_min_instances
      max_instance_count = var.api_max_instances
    }
    containers {
      image = var.backend_image
      ports { container_port = 8080 }
      command = ["uvicorn"]
      args    = ["macrolens_api.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
      resources {
        limits = { cpu = "2", memory = "2Gi" }
      }
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
      startup_probe {
        http_get { path = "/api/v1/ready" }
        initial_delay_seconds = 5
        timeout_seconds       = 5
        period_seconds        = 5
        failure_threshold     = 24
      }
      liveness_probe {
        http_get { path = "/api/v1/live" }
        timeout_seconds   = 5
        period_seconds    = 30
        failure_threshold = 3
      }
      dynamic "env" {
        for_each = local.common_env
        content { name = env.key value = env.value }
      }
      dynamic "env" {
        for_each = local.secret_env
        content {
          name = env.key
          value_source {
            secret_key_ref { secret = env.value version = "latest" }
          }
        }
      }
    }
  }
}

resource "google_cloud_run_v2_service" "worker" {
  depends_on          = [google_project_service.services, google_project_iam_member.runtime_roles]
  name                = "${local.name}-worker"
  location            = var.region
  deletion_protection = var.environment == "production"
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = google_service_account.runtime.email
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.postgres.connection_name]
      }
    }
    scaling {
      min_instance_count = var.worker_instances
      max_instance_count = var.worker_instances
    }
    containers {
      image   = var.backend_image
      command = ["python"]
      args    = ["-m", "macrolens_worker.main", "run"]
      resources {
        limits   = { cpu = "2", memory = "4Gi" }
        cpu_idle = false
      }
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
      env { name = "WORKER_ID" value = "cloud-run-worker" }
      dynamic "env" {
        for_each = local.common_env
        content { name = env.key value = env.value }
      }
      dynamic "env" {
        for_each = local.secret_env
        content {
          name = env.key
          value_source {
            secret_key_ref { secret = env.value version = "latest" }
          }
        }
      }
    }
  }
}

resource "google_cloud_run_v2_service" "scheduler" {
  depends_on          = [google_project_service.services, google_project_iam_member.runtime_roles]
  name                = "${local.name}-scheduler"
  location            = var.region
  deletion_protection = var.environment == "production"
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = google_service_account.runtime.email
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.postgres.connection_name]
      }
    }
    scaling { min_instance_count = 1 max_instance_count = 1 }
    containers {
      image   = var.backend_image
      command = ["python"]
      args    = ["-m", "macrolens_worker.main", "schedule"]
      resources {
        limits   = { cpu = "1", memory = "1Gi" }
        cpu_idle = false
      }
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
      dynamic "env" {
        for_each = local.common_env
        content { name = env.key value = env.value }
      }
      dynamic "env" {
        for_each = local.secret_env
        content {
          name = env.key
          value_source {
            secret_key_ref { secret = env.value version = "latest" }
          }
        }
      }
    }
  }
}

resource "google_cloud_run_v2_job" "migrate" {
  depends_on          = [google_project_service.services, google_project_iam_member.runtime_roles]
  name                = "${local.name}-migrate"
  location            = var.region
  deletion_protection = var.environment == "production"
  template {
    template {
      service_account = google_service_account.runtime.email
      timeout         = "900s"
      max_retries     = 1
      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.postgres.connection_name]
        }
      }
      containers {
        image   = var.backend_image
        command = ["alembic"]
        args    = ["upgrade", "head"]
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
        dynamic "env" {
          for_each = local.common_env
          content { name = env.key value = env.value }
        }
        dynamic "env" {
          for_each = local.secret_env
          content {
            name = env.key
            value_source {
              secret_key_ref { secret = env.value version = "latest" }
            }
          }
        }
      }
    }
  }
}

resource "google_cloud_run_v2_job" "seed" {
  depends_on          = [google_project_service.services, google_project_iam_member.runtime_roles, google_cloud_run_v2_job.migrate]
  name                = "${local.name}-seed"
  location            = var.region
  deletion_protection = var.environment == "production"
  template {
    template {
      service_account = google_service_account.runtime.email
      timeout         = "900s"
      max_retries     = 1
      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.postgres.connection_name]
        }
      }
      containers {
        image   = var.backend_image
        command = ["python"]
        args    = ["-m", "macrolens_api.cli", "seed"]
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
        dynamic "env" {
          for_each = local.common_env
          content { name = env.key value = env.value }
        }
        dynamic "env" {
          for_each = local.secret_env
          content {
            name = env.key
            value_source {
              secret_key_ref { secret = env.value version = "latest" }
            }
          }
        }
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "api_public" {
  project  = var.project_id
  location = google_cloud_run_v2_service.api.location
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
