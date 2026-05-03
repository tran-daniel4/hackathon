#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$REPO_ROOT"

if [ -n "$(docker compose ps -q 2>/dev/null)" ]; then
  echo "Containers already running. Tearing down volumes for a clean start..."
  docker compose down -v
fi

echo "Starting Docker containers..."
docker compose up -d postgres redis

echo "Waiting for postgres to be ready..."
until docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-dynodocs}" > /dev/null 2>&1; do
  sleep 1
done
echo "Postgres is ready."

echo "Running database migrations..."
cd "$REPO_ROOT/app/api"
source .venv/Scripts/activate
alembic upgrade head
echo "Migrations complete."

echo "Starting backend..."
cd "$REPO_ROOT/app/api"
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
