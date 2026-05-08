terraform {
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
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
    repo_url                      = var.repo_url
    repo_branch                   = var.repo_branch
    supabase_url                  = var.supabase_url
    supabase_publishable_key      = var.supabase_publishable_key
    supabase_database_url         = var.supabase_database_url
    supabase_alembic_database_url = var.supabase_alembic_database_url
    allowed_origins               = var.allowed_origins
    ollama_model                  = var.ollama_model
  })

  ssh_keys = var.ssh_fingerprints
}

data "digitalocean_project" "dynodocs" {
  name = var.do_project_name
}

resource "digitalocean_firewall" "dynodocs" {
  name        = "dynodocs-dev"
  droplet_ids = [digitalocean_droplet.dynodocs.id]

  inbound_rule {
    protocol         = "tcp"
    port_range       = "22"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "3000"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "8000"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}

resource "null_resource" "ollama_model_pull" {
  depends_on = [digitalocean_droplet.dynodocs, digitalocean_firewall.dynodocs]

  triggers = {
    droplet_id  = digitalocean_droplet.dynodocs.id
    ollama_model = var.ollama_model
  }

  connection {
    type        = "ssh"
    host        = digitalocean_droplet.dynodocs.ipv4_address
    user        = "root"
    agent       = true
    timeout     = "30m"
  }

  provisioner "remote-exec" {
    inline = [
      # Wait for cloud-init to finish
      "cloud-init status --wait",
      # Wait for Ollama to be ready
      "until curl -sf http://localhost:11434/api/tags > /dev/null; do sleep 5; done",
      # Pull the model if not already present
      "ollama list | grep -q '${var.ollama_model}' || ollama pull '${var.ollama_model}'",
    ]
  }
}

resource "digitalocean_project_resources" "dynodocs" {
  project   = data.digitalocean_project.dynodocs.id
  resources = [digitalocean_droplet.dynodocs.urn]
}

output "droplet_ip" {
  description = "Public IP of the droplet"
  value       = digitalocean_droplet.dynodocs.ipv4_address
}
