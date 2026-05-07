terraform {
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
}

provider "digitalocean" {
  token = var.do_token
}

resource "digitalocean_droplet" "dynodocs" {
  image  = "ubuntu-24-04-x64"
  name   = "dynodocs-dev"
  region = "nyc1"
  size   = "s-4vcpu-8gb"

  user_data = templatefile("cloud-init.yaml.tpl", {
    supabase_url                  = var.supabase_url
    supabase_publishable_key      = var.supabase_publishable_key
    supabase_database_url         = var.supabase_database_url
    supabase_alembic_database_url = var.supabase_alembic_database_url
    allowed_origins               = var.allowed_origins
  })

  ssh_keys = var.ssh_fingerprints
}

data "digitalocean_project" "dynodocs" {
  name = var.do_project_name
}

resource "digitalocean_project_resources" "dynodocs" {
  project   = data.digitalocean_project.dynodocs.id
  resources = [digitalocean_droplet.dynodocs.urn]
}

output "droplet_ip" {
  description = "Public IP of the droplet"
  value       = digitalocean_droplet.dynodocs.ipv4_address
}
