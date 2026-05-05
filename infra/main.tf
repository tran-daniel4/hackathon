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
  size   = "s-8vcpu-32gb"

  user_data = templatefile("cloud-init.yaml.tpl", {
    jwt_secret_key       = var.jwt_secret_key
    github_client_id     = var.github_client_id
    github_client_secret = var.github_client_secret
    nextauth_secret      = var.nextauth_secret
    db_user              = var.db_user
    db_password          = var.db_password
    allowed_origins      = var.allowed_origins
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
