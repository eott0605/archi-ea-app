variable "azure_client_id" {
  type        = string
  description = "Passed from GitHub Secret via TF_VAR_azure_client_id"
}

variable "azure_tenant_id" {
  type        = string
  description = "Passed from GitHub Secret via TF_VAR_azure_tenant_id"
}

terraform {
  required_version = ">= 1.5.0"  
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.0"
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
  use_oidc                   = true 
}

provider "azuread" {}

data "azuread_service_principal" "github_sp" {
  client_id = var.azure_client_id
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

output "storage_connection_string" {
  value     = azurerm_storage_account.blob_storage.primary_connection_string
  sensitive = true
  description = "storage connection string"
}

output "storage_account_name" {
  value       = azurerm_storage_account.blob_storage.name
  description = "The name of the storage account."
}

resource "azurerm_mssql_server" "sql_server" {
  name                         = "modelinfosqlserver3" 
  resource_group_name          = "archi-ea-app-rg"
  location                     = "centralus"
  version                      = "12.0"
  administrator_login          = "sqladmin"
  administrator_login_password = "SecurePassword123!"
  minimum_tls_version = "1.2"

  azuread_administrator {
    login_username = "github-actions-principal"
    object_id      = data.azuread_service_principal.github_sp.object_id
    tenant_id      = var.azure_tenant_id
  }
}

resource "azurerm_mssql_database" "sql_db" {
  name           = "modelinfodb"
  server_id      = azurerm_mssql_server.sql_server.id
  collation      = "SQL_Latin1_General_CP1_CI_AS"
  license_type   = "LicenseIncluded"
  max_size_gb    = 2
  sku_name       = "Basic" # Very cheap, perfect for <10,000 rows
}

resource "azurerm_mssql_firewall_rule" "allow_azure" {
  name             = "AllowAzureServices"
  server_id        = azurerm_mssql_server.sql_server.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

output "sql_server_fqdn" {
  value = azurerm_mssql_server.sql_server.fully_qualified_domain_name
  description = "The name of the SQL Server"
}