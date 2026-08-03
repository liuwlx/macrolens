output "api_url" {
  value = google_cloud_run_v2_service.api.uri
}

output "worker_name" {
  value = google_cloud_run_v2_service.worker.name
}

output "scheduler_name" {
  value = google_cloud_run_v2_service.scheduler.name
}

output "database_connection_name" {
  value = google_sql_database_instance.postgres.connection_name
}

output "database_generated_password" {
  description = "Bootstrap-only password. Move it into Secret Manager and rotate after first apply."
  value       = random_password.database.result
  sensitive   = true
}

output "assets_bucket" {
  value = google_storage_bucket.assets.name
}

output "artifact_repository" {
  value = google_artifact_registry_repository.backend.name
}
