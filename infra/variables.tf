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

variable "jwt_secret_key" {
  description = "JWT signing secret — generate with: openssl rand -hex 32"
  type        = string
  sensitive   = true
}

variable "github_client_id" {
  description = "GitHub OAuth App client ID"
  type        = string
  sensitive   = true
}

variable "github_client_secret" {
  description = "GitHub OAuth App client secret"
  type        = string
  sensitive   = true
}

variable "nextauth_secret" {
  description = "NextAuth secret — generate with: openssl rand -base64 32"
  type        = string
  sensitive   = true
}

variable "db_user" {
  description = "Postgres username"
  type        = string
  default     = "user"
}

variable "db_password" {
  description = "Postgres password"
  type        = string
  sensitive   = true
  default     = "password"
}

variable "allowed_origins" {
  description = "Comma-separated list of frontend origins allowed by the API (CORS)"
  type        = string
  default     = "http://localhost:3000"
}
