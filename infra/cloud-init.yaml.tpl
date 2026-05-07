#cloud-config

runcmd:
  # Fix DNS before anything else
  - rm -f /etc/resolv.conf
  - printf "nameserver 8.8.8.8\nnameserver 1.1.1.1\n" > /etc/resolv.conf

  # Wait for DNS to resolve
  - until getent hosts github.com > /dev/null 2>&1; do sleep 3; done

  # Install packages
  - apt-get update -y
  - apt-get install -y git curl docker.io python3-pip python3-venv

  # Enable and start Docker
  - systemctl enable docker
  - systemctl start docker
  - sleep 10

  # Clone repo
  - rm -rf /opt/dynodocs
  - git clone --branch feature/agents https://github.com/tran-daniel4/DynoDocs.git /opt/dynodocs

  # Write shared root .env for frontend-friendly defaults
  - |
    cat > /opt/dynodocs/.env << 'EOF'
    NEXT_PUBLIC_API_URL=http://localhost:8000
    NEXT_PUBLIC_SUPABASE_URL=${supabase_url}
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=${supabase_publishable_key}
    SUPABASE_URL=${supabase_url}
    DATABASE_URL=${supabase_database_url}
    ALEMBIC_DATABASE_URL=${supabase_alembic_database_url}
    REDIS_URL=redis://localhost:6379/0
    ALLOWED_ORIGINS=${allowed_origins}
    EOF

  # Write API .env
  - cp /opt/dynodocs/.env /opt/dynodocs/app/api/.env

  # Start Redis
  - |
    docker run -d --name redis --restart always \
      -p 6379:6379 \
      redis:7

  # Install Ollama and configure it before pulling models
  - curl -fsSL https://ollama.com/install.sh | sh || true
  - |
    mkdir -p /etc/systemd/system/ollama.service.d
    cat > /etc/systemd/system/ollama.service.d/override.conf << 'EOF'
    [Service]
    Environment="OLLAMA_MAX_LOADED_MODELS=1"
    Environment="OLLAMA_NUM_PARALLEL=1"
    EOF
  - systemctl daemon-reload
  - systemctl restart ollama
  - sleep 5
  - ollama pull deepseek-coder:6.7b-instruct-q4_K_M || true

  # Set up Python venv and install deps
  - python3 -m venv /opt/dynodocs/app/api/.venv
  - /opt/dynodocs/app/api/.venv/bin/pip install -r /opt/dynodocs/app/api/requirements.txt

  # Run migrations against Supabase Postgres
  - cd /opt/dynodocs/app/api && /opt/dynodocs/app/api/.venv/bin/alembic upgrade head

  # Start API
  - |
    nohup /opt/dynodocs/app/api/.venv/bin/uvicorn main:app \
      --app-dir /opt/dynodocs/app/api \
      --host 0.0.0.0 --port 8000 > /var/log/api.log 2>&1 &
