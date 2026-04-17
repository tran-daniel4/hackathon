#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Checking for port 5432 conflicts..."
PIDS_ON_5432=$(netstat -ano 2>/dev/null | grep ":5432" | awk '{print $5}' | sort -u)
PID_COUNT=$(echo "$PIDS_ON_5432" | grep -c '[0-9]' || true)

if [ "$PID_COUNT" -gt 1 ]; then
  echo ""
  echo "WARNING: Multiple processes detected on port 5432 (PIDs: $(echo $PIDS_ON_5432 | tr '\n' ' '))"
  echo "A native PostgreSQL service may be competing with Docker."
  echo "Fix: run the following in PowerShell (as Administrator), then re-run this script:"
  echo ""
  echo "  Stop-Service -Name postgresql*"
  echo "  Get-Service -Name postgresql* | Set-Service -StartupType Disabled"
  echo ""
  exit 1
fi

echo "Starting Docker containers..."
cd "$REPO_ROOT"
docker compose up -d postgres redis

echo "Waiting for postgres to be ready..."
until docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-dynodocs}" > /dev/null 2>&1; do
  sleep 1
done
echo "Postgres is ready."

echo "Starting backend..."
cd "$REPO_ROOT/app/api"
source .venv/Scripts/activate
uvicorn main:app --reload &
BACKEND_PID=$!
echo "Backend started (PID $BACKEND_PID)"

echo "Starting frontend..."
cd "$REPO_ROOT/app/web"
npm run dev &
FRONTEND_PID=$!
echo "Frontend started (PID $FRONTEND_PID)"

echo ""
echo "All services running."
echo "  API:      http://localhost:8000"
echo "  Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop the API and frontend."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" EXIT
wait $BACKEND_PID $FRONTEND_PID
