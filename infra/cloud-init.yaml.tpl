#cloud-config

runcmd:
  # Fix DNS before anything else
  - rm -f /etc/resolv.conf
  - printf "nameserver 8.8.8.8\nnameserver 1.1.1.1\n" > /etc/resolv.conf

  # Wait for DNS to resolve
  - until getent hosts github.com > /dev/null 2>&1; do sleep 3; done

  # Install packages
  - apt-get update -y
  - apt-get install -y git curl docker.io python3-pip python3-venv build-essential
  - curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  - apt-get install -y nodejs

  # Enable and start Docker
  - systemctl enable docker
  - systemctl start docker
  - sleep 10

  # Clone repo
  - rm -rf /opt/dynodocs
  - git clone --branch ${repo_branch} ${repo_url} /opt/dynodocs

  # Derive the droplet's public URLs for frontend/API wiring
  - |
    PUBLIC_IP="$(curl -fsSL http://169.254.169.254/metadata/v1/interfaces/public/0/ipv4/address)"
    FRONTEND_ORIGIN="http://$${PUBLIC_IP}:3000"
    API_PUBLIC_URL="http://$${PUBLIC_IP}:8000"
    if [ -n "${allowed_origins}" ]; then
      COMBINED_ALLOWED_ORIGINS="${allowed_origins},$${FRONTEND_ORIGIN}"
    else
      COMBINED_ALLOWED_ORIGINS="$${FRONTEND_ORIGIN}"
    fi
    printf 'PUBLIC_IP=%s\nFRONTEND_ORIGIN=%s\nAPI_PUBLIC_URL=%s\nCOMBINED_ALLOWED_ORIGINS=%s\n' \
      "$${PUBLIC_IP}" "$${FRONTEND_ORIGIN}" "$${API_PUBLIC_URL}" "$${COMBINED_ALLOWED_ORIGINS}" \
      > /opt/dynodocs/.runtime-env

  # Write shared root .env for frontend-friendly defaults
  - |
    . /opt/dynodocs/.runtime-env
    cat > /opt/dynodocs/.env <<EOF
    NEXT_PUBLIC_API_URL=$${API_PUBLIC_URL}
    NEXT_PUBLIC_SUPABASE_URL=${supabase_url}
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=${supabase_publishable_key}
    SUPABASE_URL=${supabase_url}
    DATABASE_URL=${supabase_database_url}
    ALEMBIC_DATABASE_URL=${supabase_alembic_database_url}
    REDIS_URL=redis://localhost:6379/0
    ALLOWED_ORIGINS=$${COMBINED_ALLOWED_ORIGINS}
    EOF

  # Write API .env
  - cp /opt/dynodocs/.env /opt/dynodocs/app/api/.env

  # Write frontend production env
  - |
    . /opt/dynodocs/.runtime-env
    cat > /opt/dynodocs/app/web/.env.production <<EOF
    NEXT_PUBLIC_API_URL=$${API_PUBLIC_URL}
    NEXT_PUBLIC_SUPABASE_URL=${supabase_url}
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=${supabase_publishable_key}
    EOF

  # Start Redis
  - |
    docker run -d --name redis --restart always \
      -p 6379:6379 \
      redis:7

  # Install Ollama and configure it before pulling models
  - curl -fsSL https://ollama.com/install.sh | sh
  - |
    mkdir -p /etc/systemd/system/ollama.service.d
    cat > /etc/systemd/system/ollama.service.d/override.conf << 'EOF'
    [Service]
    Environment="OLLAMA_MAX_LOADED_MODELS=1"
    Environment="OLLAMA_NUM_PARALLEL=1"
    EOF
  - systemctl daemon-reload
  - systemctl restart ollama
  - until curl -sf http://localhost:11434/api/tags > /dev/null; do sleep 3; done
  - ollama pull ${ollama_model}

  # Set up Python venv and install deps
  - python3 -m venv /opt/dynodocs/app/api/.venv
  - /opt/dynodocs/app/api/.venv/bin/pip install -r /opt/dynodocs/app/api/requirements.txt

  # Install frontend dependencies and build the app
  - cd /opt/dynodocs/app/web && npm ci
  - cd /opt/dynodocs/app/web && npm run build

  # Run migrations against Supabase Postgres
  - cd /opt/dynodocs/app/api && /opt/dynodocs/app/api/.venv/bin/alembic upgrade head

  # Create systemd service for API
  - |
    cat > /etc/systemd/system/dynodocs-api.service <<'EOF'
    [Unit]
    Description=DynoDocs API
    After=network.target

    [Service]
    WorkingDirectory=/opt/dynodocs/app/api
    EnvironmentFile=/opt/dynodocs/app/api/.env
    ExecStart=/opt/dynodocs/app/api/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
    Restart=always
    RestartSec=5
    StandardOutput=journal
    StandardError=journal

    [Install]
    WantedBy=multi-user.target
    EOF

  # Create systemd service for frontend
  - |
    cat > /etc/systemd/system/dynodocs-web.service <<'EOF'
    [Unit]
    Description=DynoDocs Web
    After=network.target

    [Service]
    WorkingDirectory=/opt/dynodocs/app/web
    ExecStart=/usr/bin/npm run start -- --hostname 0.0.0.0 --port 3000
    Restart=always
    RestartSec=5
    StandardOutput=journal
    StandardError=journal

    [Install]
    WantedBy=multi-user.target
    EOF

  # Enable and start services
  - systemctl daemon-reload
  - systemctl enable dynodocs-api dynodocs-web
  - systemctl start dynodocs-api dynodocs-web
