cmd_ssh() {
  if [[ ! -f "$CONFIG" ]]; then
    echo "Error: no active deployment found. Run 'dynodocs up' first."
    exit 1
  fi

  source <(tr -d '\r' < "$CONFIG")
  SSH_KEY_PATH="${SSH_KEY_PATH/#\~/$HOME}"

  echo "→ Connecting to $DROPLET_IP ($INFRA_PROVIDER)..."
  exec ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=accept-new "$SSH_USER@$DROPLET_IP"
}
