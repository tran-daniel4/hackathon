# OCI provider authentication
variable "tenancy_ocid" {
  description = "Your Oracle Cloud tenancy OCID"
  type        = string
  sensitive   = true
}

variable "user_ocid" {
  description = "Your Oracle Cloud user OCID"
  type        = string
  sensitive   = true
}

variable "fingerprint" {
  description = "Fingerprint of your OCI API key"
  type        = string
  sensitive   = true
}

variable "private_key_path" {
  description = "Path to your OCI API private key (.pem file) on your local machine"
  type        = string
  default     = "~/.oci/oci_api_key.pem"
}

variable "region" {
  description = "OCI region (e.g. us-ashburn-1)"
  type        = string
}

# Instance placement
variable "compartment_ocid" {
  description = "OCID of the compartment to create resources in (use tenancy OCID for root)"
  type        = string
}

variable "availability_domain" {
  description = "Full availability domain name (e.g. abcD:US-ASHBURN-AD-1)"
  type        = string
}

# SSH access — pass the full public key string, not a fingerprint
variable "ssh_public_key" {
  description = "Full SSH public key string (contents of your ~/.ssh/id_rsa.pub or id_ed25519.pub)"
  type        = string
}

variable "ssh_allowed_ips" {
  description = "CIDR blocks allowed to SSH in. Restrict to your own IP for security."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

# App configuration (same as DigitalOcean config)
variable "repo_url" {
  description = "Git repository URL"
  type        = string
}

variable "repo_branch" {
  description = "Git branch to deploy"
  type        = string
  default     = "main"
}

variable "supabase_url" {
  type      = string
  sensitive = true
}

variable "supabase_publishable_key" {
  type      = string
  sensitive = true
}

variable "supabase_database_url" {
  type      = string
  sensitive = true
}

variable "supabase_alembic_database_url" {
  type      = string
  sensitive = true
}

variable "allowed_origins" {
  description = "Comma-separated CORS origins"
  type        = string
  default     = "http://localhost:3000"
}

variable "anthropic_api_key" {
  type      = string
  sensitive = true
}