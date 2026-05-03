#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
INFRA_DIR="$REPO_ROOT/infra"
CONFIG="$SCRIPT_DIR/config.env"

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
    exit 1
    ;;
esac
