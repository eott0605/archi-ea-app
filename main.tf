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

# The new Storage Account you want to automatically create
resource "azurerm_storage_account" "blob_storage" {
  name                     = "modelinfoaccount"       # Must be unique globally, lowercase letters/numbers only
  resource_group_name      = "archi-ea-app-rg" # Your existing target RG
  location                 = "eastus"
  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"

  # Enforce high security settings
  min_tls_version               = "TLS1_2"
  https_traffic_only_enabled    = true
  # CHANGED: Allow public access ONLY from your whitelisted networks/IPs
  public_network_access_enabled = true 

  # ADD THIS BLOCK TO ENABLE THE FIREWALL
  network_rules {
    default_action             = "Deny"
    bypass                     = ["AzureServices"]
  }
}

resource "azurerm_storage_container" "blob_container" {
  name                  = "modelinfocontainer" # Name of your blob folder
  storage_account_id    = azurerm_storage_account.blob_storage.id
  container_access_type = "private" # Keeps your data safe and private
}

output "storage_account_name" {
  value       = azurerm_storage_account.blob_storage.name
  description = "The name of the newly created storage account."
}
