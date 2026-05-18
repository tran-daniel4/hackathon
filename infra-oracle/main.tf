terraform {
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 6.0"
    }
  }
}

# --- PROVIDER ---
# Authenticates to OCI using your API key pair.
# Unlike DigitalOcean's single token, OCI needs 4 pieces of identity info.
provider "oci" {
  tenancy_ocid     = var.tenancy_ocid
  user_ocid        = var.user_ocid
  fingerprint      = var.fingerprint
  private_key_path = var.private_key_path
  region           = var.region
}

# --- IMAGE LOOKUP ---
# OCI images are identified by a region-specific OCID, not a friendly slug.
# This data source automatically finds the latest Ubuntu 22.04 Arm image
# in your region so you don't have to hardcode the OCID.
data "oci_core_images" "ubuntu_arm" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "22.04"
  shape                    = "VM.Standard.A1.Flex"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
  state                    = "AVAILABLE"
}

# --- VIRTUAL CLOUD NETWORK (VCN) ---
# DigitalOcean handles networking automatically behind the scenes.
# In OCI, you explicitly define the network your instance lives in.
# The VCN is like a private network with a 10.0.0.0/16 address space.
resource "oci_core_vcn" "dynodocs" {
  compartment_id = var.compartment_ocid
  cidr_block     = "10.0.0.0/16"
  display_name   = "dynodocs-vcn"
  dns_label      = "dynodocs"
}

# --- INTERNET GATEWAY ---
# Allows traffic between the VCN and the public internet.
# Without this, the instance has no internet access at all.
resource "oci_core_internet_gateway" "dynodocs" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.dynodocs.id
  display_name   = "dynodocs-igw"
  enabled        = true
}

# --- ROUTE TABLE ---
# Tells the VCN: send all outbound traffic (0.0.0.0/0) through the internet gateway.
# This is what gives the instance outbound internet access (to reach GitHub, Anthropic, etc.)
resource "oci_core_route_table" "dynodocs" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.dynodocs.id
  display_name   = "dynodocs-rt"

  route_rules {
    network_entity_id = oci_core_internet_gateway.dynodocs.id
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
  }
}

# --- SECURITY LIST ---
# OCI's equivalent of a firewall. This replaces the digitalocean_firewall resource.
# Important: OCI has TWO layers of firewall:
#   1. This Security List (network level, configured here)
#   2. Host-level iptables (configured in cloud-init)
# Both layers must allow a port for traffic to reach the app.
resource "oci_core_security_list" "dynodocs" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.dynodocs.id
  display_name   = "dynodocs-sl"

  # Allow SSH inbound
  ingress_security_rules {
    protocol  = "6"  # TCP
    source    = join(",", var.ssh_allowed_ips)
    stateless = false
    tcp_options {
      min = 22
      max = 22
    }
  }

  # Allow API inbound (port 8000)
  ingress_security_rules {
    protocol  = "6"  # TCP
    source    = "0.0.0.0/0"
    stateless = false
    tcp_options {
      min = 8000
      max = 8000
    }
  }

  # Allow all outbound (so the instance can reach Anthropic, GitHub, Supabase, etc.)
  egress_security_rules {
    protocol    = "all"
    destination = "0.0.0.0/0"
    stateless   = false
  }
}

# --- SUBNET ---
# A subdivision of the VCN where the instance lives.
# It's public (assign_public_ip = true on the instance) so traffic can reach it.
resource "oci_core_subnet" "dynodocs" {
  compartment_id    = var.compartment_ocid
  vcn_id            = oci_core_vcn.dynodocs.id
  cidr_block        = "10.0.1.0/24"
  display_name      = "dynodocs-subnet"
  dns_label         = "dynodocs"
  route_table_id    = oci_core_route_table.dynodocs.id
  security_list_ids = [oci_core_security_list.dynodocs.id]
}

# --- COMPUTE INSTANCE ---
# VM.Standard.A1.Flex is the Arm Ampere A1 shape.
# The free tier allows up to 4 OCPUs and 24 GB RAM total across all A1 instances.
# We use 2 OCPUs + 4 GB — well within the free limit and plenty for this app.
resource "oci_core_instance" "dynodocs" {
  availability_domain = var.availability_domain
  compartment_id      = var.compartment_ocid
  display_name        = "dynodocs-api"
  shape               = "VM.Standard.A1.Flex"

  shape_config {
    ocpus         = 2
    memory_in_gbs = 4
  }

  # Use the latest Ubuntu 22.04 Arm image found by the data source above
  source_details {
    source_type = "image"
    source_id   = data.oci_core_images.ubuntu_arm.images[0].id
  }

  # Place the instance in the public subnet and assign a public IP
  create_vnic_details {
    subnet_id        = oci_core_subnet.dynodocs.id
    assign_public_ip = true
    hostname_label   = "dynodocs"
  }

  # In OCI, metadata.ssh_authorized_keys takes the FULL public key string.
  # user_data must be base64-encoded (unlike DigitalOcean which took a plain string).
  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data = base64encode(templatefile("${path.module}/cloud-init.yaml.tpl", {
      repo_url                      = var.repo_url
      repo_branch                   = var.repo_branch
      supabase_url                  = var.supabase_url
      supabase_publishable_key      = var.supabase_publishable_key
      supabase_database_url         = var.supabase_database_url
      supabase_alembic_database_url = var.supabase_alembic_database_url
      allowed_origins               = var.allowed_origins
      anthropic_api_key             = var.anthropic_api_key
    }))
  }
}

# --- OUTPUT ---
output "instance_public_ip" {
  description = "Public IP of the Oracle Cloud instance — use this as your new API host"
  value       = oci_core_instance.dynodocs.public_ip
}