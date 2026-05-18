#cloud-config

runcmd:
  # Fix DNS before anything else
  - rm -f /etc/resolv.conf
  - printf "nameserver 8.8.8.8\nnameserver 1.1.1.1\n" > /etc/resolv.conf

  # Wait for DNS to resolve
  - until getent hosts github.com > /dev/null 2>&1; do sleep 3; done

  # Install packages
  - apt-get update -y
  - apt-get install -y git curl docker.io python3-pip python3-venv build-essential iptables-persistent

  # OCI Ubuntu images block inbound ports at the OS level via iptables.
  # The OCI Security List (Terraform) opens port 8000 at the network level,
  # but traffic is still dropped here unless we also open it in iptables.
  - iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT
  - netfilter-persistent save

  # Enable and start Docker
  - systemctl enable docker
  - systemctl start docker
  - sleep 10

  # Clone repo
  - rm -rf /opt/dynodocs
  - git clone --branch ${repo_branch} ${repo_url} /opt/dynodocs

  # Write API .env
  - |
    cat > /opt/dynodocs/app/api/.env <<EOF
    SUPABASE_URL=${supabase_url}
    DATABASE_URL=${supabase_database_url}
    ALEMBIC_DATABASE_URL=${supabase_alembic_database_url}
    REDIS_URL=redis://localhost:6379/0
    ALLOWED_ORIGINS=${allowed_origins}
    ANTHROPIC_API_KEY=${anthropic_api_key}
    EOF

  # Add swap to prevent OOM during pip install
  - fallocate -l 2G /swapfile
  - chmod 600 /swapfile
  - mkswap /swapfile
  - swapon /swapfile
  - echo '/swapfile none swap sw 0 0' >> /etc/fstab

  # Start Redis
  - |
    docker run -d --name redis --restart always \
      -p 6379:6379 \
      redis:7

  # Set up Python venv and install deps
  - python3 -m venv /opt/dynodocs/app/api/.venv
  - /opt/dynodocs/app/api/.venv/bin/pip install -r /opt/dynodocs/app/api/requirements.txt

  # Run migrations against Supabase Postgres
  - cd /opt/dynodocs/app/api && /opt/dynodocs/app/api/.venv/bin/alembic upgrade head

  # Create systemd service for API
  - |
    cat > /etc/systemd/system/dynodocs-api.service << 'EOF'
    [Unit]
    Description=DynoDocs API
    After=network-online.target
    Wants=network-online.target

    [Service]
    WorkingDirectory=/opt/dynodocs/app/api
    EnvironmentFile=/opt/dynodocs/app/api/.env
    ExecStart=/opt/dynodocs/app/api/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
    Restart=always
    RestartSec=5
    TimeoutStopSec=10
    StandardOutput=journal
    StandardError=journal

    [Install]
    WantedBy=multi-user.target
    EOF

  # Enable and start API service
  - systemctl daemon-reload
  - systemctl enable dynodocs-api
  - systemctl start dynodocs-api
