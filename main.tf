terraform {
  required_version = ">= 1.5.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
  # Securely store state in an existing storage account
  backend "azurerm" {
    resource_group_name  = "my-existing-tfstate-rg"
    storage_account_name = "myexistingtfstatestorage"
    container_name       = "tfstate"
    key                  = "storage-account.tfstate"
    use_oidc             = true # Tells Terraform to use GitHub's OIDC login
  }
}

provider "azurerm" {
  features {}
  use_oidc = true # Tells the provider to use GitHub's OIDC login
  skip_provider_registration = true
}

resource "azurerm_storage_account" "blob_storage" {
  name                     = "modelinfoaccount"       
  resource_group_name      = "archi-ea-app-rg" 
  location                 = "eastus"
  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"

  min_tls_version               = "TLS1_2"
  https_traffic_only_enabled    = true
  public_network_access_enabled = true 

  # Keep your laptop whitelisted permanently so you can always view the data
  network_rules {
    default_action             = "Deny"
    bypass                     = ["AzureServices"]
    ip_rules                   = ["47.201.174.117"] 
  }
}

resource "azurerm_storage_container" "blob_container" {
  name                  = "modelinfocontainer"
  storage_account_id    = azurerm_storage_account.blob_storage.id
  container_access_type = "private" 
}

# Also add an output for the storage connection string
output "storage_connection_string" {
  value     = azurerm_storage_account.blob_storage.primary_connection_string
  sensitive = true
}

output "storage_account_name" {
  value       = azurerm_storage_account.blob_storage.name
  description = "The name of the newly created storage account."
}

# Automatically fetches the official live list of GitHub IP addresses
data "http" "github_meta" {
  url = "https://github.com"
}

# Decodes the JSON response to extract only the Actions runner IPv4 addresses
locals {
  github_actions_ips = jsondecode(data.http.github_meta.response_body).actions
  # Filters out IPv6 addresses because Azure Storage Firewalls only support IPv4 CIDR blocks
  github_actions_ipv4 = [for ip in local.github_actions_ips : ip if !contains(split("", ip), ":")]
}
