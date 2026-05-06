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

  # Write .env
  - |
    cat > /opt/dynodocs/app/api/.env << 'EOF'
    DATABASE_URL=postgresql+asyncpg://${db_user}:${db_password}@localhost:5432/dynodocs
    ALEMBIC_DATABASE_URL=postgresql+asyncpg://${db_user}:${db_password}@127.0.0.1:5432/dynodocs
    REDIS_URL=redis://localhost:6379/0
    JWT_SECRET_KEY=${jwt_secret_key}
    ACCESS_TOKEN_EXPIRE_MINUTES=15
    REFRESH_TOKEN_EXPIRE_MINUTES=60
    POSTGRES_USER=${db_user}
    POSTGRES_PASSWORD=${db_password}
    POSTGRES_DB=dynodocs
    GITHUB_CLIENT_ID=${github_client_id}
    GITHUB_CLIENT_SECRET=${github_client_secret}
    NEXTAUTH_SECRET=${nextauth_secret}
    ALLOWED_ORIGINS=${allowed_origins}
    EOF

  # Start DBs
  - |
    docker run -d --name postgres --restart always \
      -e POSTGRES_USER=${db_user} \
      -e POSTGRES_PASSWORD=${db_password} \
      -e POSTGRES_DB=dynodocs \
      -p 5432:5432 \
      postgres:15

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

  # Wait for Postgres to be ready, then run migrations
  - until docker exec postgres pg_isready -U ${db_user} > /dev/null 2>&1; do sleep 2; done
  - cd /opt/dynodocs/app/api && /opt/dynodocs/app/api/.venv/bin/alembic upgrade head

  # Start API
  - |
    nohup /opt/dynodocs/app/api/.venv/bin/uvicorn main:app \
      --app-dir /opt/dynodocs/app/api \
      --host 0.0.0.0 --port 8000 > /var/log/api.log 2>&1 &
