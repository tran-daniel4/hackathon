variable "do_token" {
  description = "DigitalOcean API token"
  type        = string
  sensitive   = true
}

variable "ssh_fingerprint" {
  description = "SSH key fingerprint registered in DigitalOcean (Settings > Security)"
  type        = string
}

variable "do_project_name" {
  description = "Name of the existing DigitalOcean project to assign the droplet to"
  type        = string
}
