cmd_redeploy() {
  if [[ ! -f "$CONFIG" ]]; then
    echo "Error: no active deployment found. Run 'dynodocs up' first."
    exit 1
  fi

  source <(tr -d '\r' < "$CONFIG")
  SSH_KEY_PATH="${SSH_KEY_PATH/#\~/$HOME}"

  echo "→ Deploying to $DROPLET_IP..."
  ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=accept-new root@"$DROPLET_IP" \
    "cd /opt/hackathon && git pull origin main && systemctl restart api"

  echo "✓ Deployment complete. Backend restarted at http://$DROPLET_IP:8000"
}
