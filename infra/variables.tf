variable "do_token" {
  description = "DigitalOcean API token"
  type        = string
  sensitive   = true
}

variable "ssh_fingerprints" {
  description = "SSH key fingerprints for all team members registered in DigitalOcean (Settings > Security)"
  type        = list(string)
}

variable "do_project_name" {
  description = "Name of the existing DigitalOcean project to assign the droplet to"
  type        = string
}
