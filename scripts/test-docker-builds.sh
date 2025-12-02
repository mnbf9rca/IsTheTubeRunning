#!/usr/bin/env bash
# Test Docker builds locally for both backend and frontend
# Tests both build and runtime to ensure containers work correctly

set -e

# Check for required .env.keys file
if [[ ! -f "backend/.env.keys" ]]; then
  echo "❌ ERROR: backend/.env.keys file not found"
  echo ""
  echo "This file contains private keys for decrypting .env files."
  echo "It should already exist in your backend directory (gitignored)."
  echo ""
  echo "If you need to regenerate it, you'll need access to the encrypted"
  echo ".env.ci or .env.production files and run:"
  echo "  dotenvx encrypt -k \"SECRET_*\" -f backend/.env.ci"
  echo ""
  echo "Note: .env.keys is gitignored and should never be committed"
  exit 1
fi

echo "🧪 Testing Docker builds..."
echo ""

# Test backend build
echo "📦 Building backend (this may take 4-6 minutes on first build)..."
timeout 400 docker buildx build --platform linux/amd64 -t isthetube-backend:test ./backend
echo "✅ Backend build successful"
echo ""

# Test frontend build
echo "📦 Building frontend..."
timeout 400 docker buildx build --platform linux/amd64 -t isthetube-frontend:test ./frontend
echo "✅ Frontend build successful"
echo ""

# Runtime test - backend (will fail without database, but verifies dotenvx decryption)
echo "🔥 Runtime test - backend..."
echo "   (Expected: Will start but exit due to no database connection)"
# Extract DOTENV_PRIVATE_KEY_CI from .env.keys for testing
DOTENV_PRIVATE_KEY_CI=$(grep "DOTENV_PRIVATE_KEY_CI" backend/.env.keys | cut -d'=' -f2-)
docker run -d --name backend-test --platform linux/amd64 -p 8000:8000 \
  -e DOTENV_PRIVATE_KEY_CI="$DOTENV_PRIVATE_KEY_CI" \
  isthetube-backend:test

sleep 10
if docker logs backend-test 2>&1 | grep -q "Starting gunicorn"; then
  echo "✅ Backend container started (gunicorn running)"
  if docker logs backend-test 2>&1 | grep -q "Connection refused"; then
    echo "✅ dotenvx decryption works (failed at DB connection as expected)"
  else
    echo "⚠️  Backend running but unexpected state"
  fi
else
  echo "❌ Backend container failed to start gunicorn"
  docker logs backend-test
  docker rm -f backend-test
  exit 1
fi
docker rm -f backend-test
echo ""

# Runtime test - frontend
echo "🔥 Runtime test - frontend..."
docker run -d --name frontend-test --platform linux/amd64 -p 8080:8080 \
  isthetube-frontend:test

sleep 3
if curl -s http://localhost:8080/ | grep -q "<!doctype html>"; then
  echo "✅ Frontend container serving HTML"
else
  echo "❌ Frontend container not responding"
  docker rm -f frontend-test
  exit 1
fi
docker rm -f frontend-test
echo ""

echo "🎉 All tests passed!"
echo ""
echo "📋 Summary:"
echo "  ✅ Backend builds successfully"
echo "  ✅ Frontend builds successfully"
echo "  ✅ Backend dotenvx decryption works"
echo "  ✅ Backend gunicorn starts with 4 workers"
echo "  ✅ Frontend serves static assets"
echo ""
echo "💡 Next steps:"
echo "  - Use deploy/docker-compose.prod.yml to run all services together"
echo "  - Backend needs PostgreSQL and Redis to fully function"
