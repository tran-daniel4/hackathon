cmd_up() {
  if [[ ! -f "$INFRA_DIR/terraform.tfvars" ]]; then
    echo "Error: $INFRA_DIR/terraform.tfvars not found."
    echo "Copy terraform.tfvars.example and fill in your credentials."
    exit 1
  fi

  echo "→ Initializing Terraform ($INFRA_PROVIDER)..."
  if [[ ! -d "$INFRA_DIR/.terraform" ]]; then
    terraform -chdir="$INFRA_DIR" init -input=false
  fi

  echo "→ Provisioning infrastructure..."
  terraform -chdir="$INFRA_DIR" apply -auto-approve

  echo "→ Fetching instance IP..."
  DROPLET_IP="$(terraform -chdir="$INFRA_DIR" output -raw "$TF_OUTPUT_IP")"

  read -rp "SSH private key path [~/.ssh/id_ed25519]: " SSH_KEY_PATH
  SSH_KEY_PATH="${SSH_KEY_PATH:-~/.ssh/id_ed25519}"

  for entry in "DROPLET_IP=$DROPLET_IP" "SSH_KEY_PATH=$SSH_KEY_PATH" "INFRA_PROVIDER=$INFRA_PROVIDER"; do
    key="${entry%%=*}"
    if [[ -f "$CONFIG" ]] && grep -q "^${key}=" "$CONFIG"; then
      sed -i "s|^${key}=.*|${entry}|" "$CONFIG"
    else
      printf "%s\n" "$entry" >> "$CONFIG"
    fi
  done

  echo ""
  echo "✓ Provisioning complete"
  echo "  Backend API:  http://$DROPLET_IP:8000/health"
  echo "  SSH:          ssh -i $SSH_KEY_PATH $SSH_USER@$DROPLET_IP"
  echo ""
  echo "Note: cloud-init takes ~3 minutes to finish bootstrapping on first boot."
}

cmd_down() {
  echo "→ Destroying infrastructure ($INFRA_PROVIDER)..."
  terraform -chdir="$INFRA_DIR" destroy -auto-approve

  if [[ -f "$CONFIG" ]]; then
    sed -i 's/^DROPLET_IP=.*/DROPLET_IP=/' "$CONFIG"
  fi
  echo "✓ Infrastructure destroyed and local state cleared."
}
