#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG="$SCRIPT_DIR/config.env"

# Capture INFRA_PROVIDER from the environment before sourcing config.env,
# so the env var takes precedence over any saved value in config.env.
_INFRA_PROVIDER_ENV="${INFRA_PROVIDER:-}"

if [[ -f "$CONFIG" ]]; then
  source <(tr -d '\r' < "$CONFIG")
fi

[[ -n "$_INFRA_PROVIDER_ENV" ]] && INFRA_PROVIDER="$_INFRA_PROVIDER_ENV"
INFRA_PROVIDER="${INFRA_PROVIDER:-oracle}"

case "$INFRA_PROVIDER" in
  oracle)
    INFRA_DIR="$REPO_ROOT/infra-oracle"
    SSH_USER="ubuntu"
    TF_OUTPUT_IP="instance_public_ip"
    RESTART_CMD="sudo systemctl restart dynodocs-api"
    ;;
  digitalocean)
    INFRA_DIR="$REPO_ROOT/infra"
    SSH_USER="root"
    TF_OUTPUT_IP="droplet_ip"
    RESTART_CMD="systemctl restart api"
    ;;
  *)
    echo "Error: unknown INFRA_PROVIDER '$INFRA_PROVIDER'. Must be 'oracle' or 'digitalocean'."
    exit 1
    ;;
esac

source "$SCRIPT_DIR/lib/terraform.sh"
source "$SCRIPT_DIR/lib/deploy.sh"
source "$SCRIPT_DIR/lib/ssh.sh"

case "${1:-}" in
  up)       cmd_up ;;
  down)     cmd_down ;;
  redeploy) cmd_redeploy ;;
  ssh)      cmd_ssh ;;
  *)
    echo "Usage: dynodocs <up|down|redeploy|ssh>"
    echo ""
    echo "  up        Provision infrastructure and bootstrap the server"
    echo "  down      Destroy all infrastructure"
    echo "  redeploy  Pull latest code and restart the backend"
    echo "  ssh       Open an SSH session to the remote server"
    echo ""
    echo "Set INFRA_PROVIDER=oracle (default) or INFRA_PROVIDER=digitalocean before running."
    exit 1
    ;;
esac
