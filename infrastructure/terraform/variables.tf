variable "project_id" {
  description = "Google Cloud project ID."
  type        = string
}

variable "region" {
  description = "Primary Google Cloud region."
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "production"
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production."
  }
}

variable "backend_image" {
  description = "Fully-qualified backend image URI."
  type        = string
}

variable "web_origin" {
  description = "Vercel production origin allowed by CORS and CSRF checks."
  type        = string
}

variable "artifact_repository" {
  type    = string
  default = "macrolens"
}

variable "database_tier" {
  type    = string
  default = "db-custom-2-7680"
}

variable "database_disk_size_gb" {
  type    = number
  default = 100
}

variable "api_min_instances" {
  type    = number
  default = 1
}

variable "api_max_instances" {
  type    = number
  default = 10
}

variable "worker_instances" {
  type    = number
  default = 1
}

variable "secret_names" {
  description = "Existing Secret Manager secret names. Each must have an enabled latest version before apply."
  type = object({
    database_url_sync       = string
    database_url_async      = string
    jwt_secret              = string
    bootstrap_admin_password = string
    s3_access_key_id        = string
    s3_secret_access_key    = string
    fred_api_key            = string
    bea_api_key             = string
    bls_api_key             = string
    eia_api_key             = string
    census_api_key          = string
    openai_api_key          = string
  })
  default = {
    database_url_sync        = "macrolens-database-url-sync"
    database_url_async       = "macrolens-database-url-async"
    jwt_secret               = "macrolens-jwt-secret"
    bootstrap_admin_password = "macrolens-bootstrap-admin-password"
    s3_access_key_id         = "macrolens-s3-access-key-id"
    s3_secret_access_key     = "macrolens-s3-secret-access-key"
    fred_api_key             = "macrolens-fred-api-key"
    bea_api_key              = "macrolens-bea-api-key"
    bls_api_key              = "macrolens-bls-api-key"
    eia_api_key              = "macrolens-eia-api-key"
    census_api_key           = "macrolens-census-api-key"
    openai_api_key           = "macrolens-openai-api-key"
  }
}
