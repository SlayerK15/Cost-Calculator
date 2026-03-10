terraform {
  required_version = ">= 1.5"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

# ── Resource Group ──
resource "azurerm_resource_group" "platform" {
  name     = "llm-platform-rg"
  location = var.location
}

# ── AKS Cluster ──
resource "azurerm_kubernetes_cluster" "platform" {
  name                = "llm-platform"
  location            = azurerm_resource_group.platform.location
  resource_group_name = azurerm_resource_group.platform.name
  dns_prefix          = "llm-platform"

  default_node_pool {
    name       = "system"
    node_count = 2
    vm_size    = "Standard_DS2_v2"
  }

  identity {
    type = "SystemAssigned"
  }
}

# GPU Node Pool
resource "azurerm_kubernetes_cluster_node_pool" "gpu" {
  name                  = "gpupool"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.platform.id
  vm_size               = var.gpu_vm_size
  min_count             = 0
  max_count             = var.max_gpu_nodes
  enable_auto_scaling   = true

  node_taints = ["nvidia.com/gpu=present:NoSchedule"]

  node_labels = {
    "workload" = "llm-inference"
  }
}

# ── PostgreSQL ──
resource "azurerm_postgresql_flexible_server" "platform" {
  name                   = "llm-platform-db"
  resource_group_name    = azurerm_resource_group.platform.name
  location               = azurerm_resource_group.platform.location
  version                = "16"
  administrator_login    = "postgres"
  administrator_password = var.db_password
  sku_name               = "GP_Standard_D2s_v3"
  storage_mb             = 32768
  zone                   = "1"
}

resource "azurerm_postgresql_flexible_server_database" "platform" {
  name      = "llmplatform"
  server_id = azurerm_postgresql_flexible_server.platform.id
}

# ── Redis ──
resource "azurerm_redis_cache" "platform" {
  name                = "llm-platform-redis"
  location            = azurerm_resource_group.platform.location
  resource_group_name = azurerm_resource_group.platform.name
  capacity            = 1
  family              = "C"
  sku_name            = "Standard"
  minimum_tls_version = "1.2"
}

# ── Container Registry ──
resource "azurerm_container_registry" "platform" {
  name                = "llmplatformacr"
  resource_group_name = azurerm_resource_group.platform.name
  location            = azurerm_resource_group.platform.location
  sku                 = "Standard"
  admin_enabled       = true
}

# ── Storage Account ──
resource "azurerm_storage_account" "models" {
  name                     = "llmplatformmodels"
  resource_group_name      = azurerm_resource_group.platform.name
  location                 = azurerm_resource_group.platform.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_container" "models" {
  name                  = "model-weights"
  storage_account_name  = azurerm_storage_account.models.name
  container_access_type = "private"
}

# ── Outputs ──
output "aks_cluster_name" {
  value = azurerm_kubernetes_cluster.platform.name
}

output "acr_login_server" {
  value = azurerm_container_registry.platform.login_server
}

output "db_fqdn" {
  value = azurerm_postgresql_flexible_server.platform.fqdn
}

output "redis_hostname" {
  value = azurerm_redis_cache.platform.hostname
}
