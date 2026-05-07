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

variable "repo_url" {
  description = "Git repository URL to deploy onto the droplet"
  type        = string
}

variable "repo_branch" {
  description = "Git branch to deploy onto the droplet"
  type        = string
  default     = "main"
}

variable "supabase_url" {
  description = "Supabase project URL"
  type        = string
  sensitive   = true
}

variable "supabase_publishable_key" {
  description = "Supabase publishable key for the frontend"
  type        = string
  sensitive   = true
}

variable "supabase_database_url" {
  description = "Supabase Postgres connection string for the API"
  type        = string
  sensitive   = true
}

variable "supabase_alembic_database_url" {
  description = "Supabase Postgres connection string used by Alembic"
  type        = string
  sensitive   = true
}

variable "allowed_origins" {
  description = "Comma-separated list of frontend origins allowed by the API (CORS)"
  type        = string
  default     = "http://localhost:3000"
}
