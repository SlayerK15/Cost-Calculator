terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ── GKE Cluster ──
resource "google_container_cluster" "platform" {
  name     = "llm-platform"
  location = var.region

  initial_node_count       = 1
  remove_default_node_pool = true

  networking_mode = "VPC_NATIVE"
  ip_allocation_policy {}

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }
}

# System node pool
resource "google_container_node_pool" "system" {
  name       = "system-pool"
  cluster    = google_container_cluster.platform.name
  location   = var.region
  node_count = 2

  node_config {
    machine_type = "e2-standard-4"
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }
}

# GPU node pool
resource "google_container_node_pool" "gpu" {
  name     = "gpu-pool"
  cluster  = google_container_cluster.platform.name
  location = var.region

  autoscaling {
    min_node_count = 0
    max_node_count = var.max_gpu_nodes
  }

  node_config {
    machine_type = var.gpu_machine_type
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]

    guest_accelerator {
      type  = var.gpu_accelerator_type
      count = var.gpus_per_node
    }

    taint {
      key    = "nvidia.com/gpu"
      value  = "present"
      effect = "NO_SCHEDULE"
    }
  }
}

# ── Cloud SQL (PostgreSQL) ──
resource "google_sql_database_instance" "platform" {
  name             = "llm-platform-db"
  database_version = "POSTGRES_16"
  region           = var.region

  settings {
    tier = "db-custom-2-7680"

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.platform.id
    }
  }

  deletion_protection = false
}

resource "google_sql_database" "platform" {
  name     = "llmplatform"
  instance = google_sql_database_instance.platform.name
}

# ── VPC ──
resource "google_compute_network" "platform" {
  name                    = "llm-platform-network"
  auto_create_subnetworks = true
}

# ── Memorystore (Redis) ──
resource "google_redis_instance" "platform" {
  name           = "llm-platform-redis"
  tier           = "BASIC"
  memory_size_gb = 1
  region         = var.region

  authorized_network = google_compute_network.platform.id
}

# ── Artifact Registry ──
resource "google_artifact_registry_repository" "platform" {
  location      = var.region
  repository_id = "llm-platform"
  format        = "DOCKER"
}

# ── GCS for model storage ──
resource "google_storage_bucket" "models" {
  name          = "llm-platform-models-${var.project_id}"
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true
}

# ── Outputs ──
output "gke_endpoint" {
  value = google_container_cluster.platform.endpoint
}

output "registry_url" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.platform.repository_id}"
}

output "db_connection" {
  value = google_sql_database_instance.platform.connection_name
}

output "redis_host" {
  value = google_redis_instance.platform.host
}
