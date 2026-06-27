#!/usr/bin/env bash
# Bootstrap dev/pilot stack for release verification and Playwright E2E.
# Usage:
#   ./scripts/ci_release_smoke.sh bootstrap [dev|pilot]
#   ./scripts/ci_release_smoke.sh verify-release
#   ./scripts/ci_release_smoke.sh playwright [dev|pilot]
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OPENCIVIC_MODE="${OPENCIVIC_MODE:-dev}"
API_PORT="${OPENCIVIC_API_PORT:-8100}"
GATEWAY_PORT="${OPENCIVIC_GATEWAY_PORT:-8088}"
FRONTEND_PORT="${OPENCIVIC_FRONTEND_PORT:-3100}"
KEYCLOAK_PORT="${OPENCIVIC_KEYCLOAK_PORT:-8180}"

compose_files() {
  local -a files=(-f docker-compose.dev.yml -f docker-compose.ci-release.yml)
  if [[ "$OPENCIVIC_MODE" == "pilot" ]]; then
    files+=(-f docker-compose.pilot.yml)
  fi
  printf '%s\n' "${files[@]}"
}

compose() {
  local -a files
  mapfile -t files < <(compose_files)
  docker compose "${files[@]}" "$@"
}

log() {
  printf '[ci-release] %s\n' "$*"
}

prepare_env() {
  cp .env.example .env
  sed -i 's/CHANGE_ME/testpassword123/g' .env
  sed -i 's/CHANGE_ME_MINIMUM_32_CHARACTERS/testsecretkey32charsminimumhere1/g' .env
  {
    echo "POSTGRES_PASSWORD=testpassword123"
    echo "VALKEY_PASSWORD=testpassword123"
    echo "SECRET_KEY=testsecretkey32charsminimumhere1"
    echo "CLAMAV_ENABLED=false"
    echo "DEV_AUTH_TOKEN=dev-local-token-change-me"
    echo "DEV_STEWARD_AUTH_TOKEN=dev-steward-token-change-me"
    echo "DEV_ADMIN_AUTH_TOKEN=dev-admin-token-change-me"
    echo "DEV_DEVELOPER_AUTH_TOKEN=dev-developer-token-change-me"
    echo "OPENCIVIC_API_PORT=${API_PORT}"
    echo "OPENCIVIC_GATEWAY_PORT=${GATEWAY_PORT}"
    echo "OPENCIVIC_FRONTEND_PORT=${FRONTEND_PORT}"
    echo "OPENCIVIC_KEYCLOAK_PORT=${KEYCLOAK_PORT}"
    echo "KEYCLOAK_ADMIN_PASSWORD=admin-change-me"
    echo "KEYCLOAK_CLIENT_SECRET=pilot-client-secret-change-me"
  } >> .env
}

wait_for_url() {
  local url="$1"
  local label="$2"
  local timeout="${3:-180}"
  log "Waiting for ${label} at ${url} (${timeout}s)..."
  timeout "${timeout}" bash -c "until curl -sf '${url}' >/dev/null; do sleep 3; done"
}

bootstrap() {
  local mode="${1:-dev}"
  OPENCIVIC_MODE="$mode"
  export OPENCIVIC_MODE

  local -a files
  mapfile -t files < <(compose_files)

  prepare_env

  log "Starting data services..."
  compose up -d postgres valkey minio qdrant

  timeout 90 bash -c "until docker compose $(printf ' %q' "${files[@]}") exec -T postgres pg_isready -U opencivic -d opencivic; do sleep 2; done"

  log "Running migrations and dev seed..."
  compose run --rm --no-deps api alembic upgrade head
  compose run --rm --no-deps api python scripts/seed_dev.py

  if [[ "$OPENCIVIC_MODE" == "pilot" ]]; then
    log "Starting Keycloak (pilot)..."
    compose up -d keycloak
    wait_for_url "http://127.0.0.1:${KEYCLOAK_PORT}/health/ready" "keycloak" 240
  fi

  log "Starting application stack..."
  compose up -d api worker beat apisix nginx frontend

  wait_for_url "http://127.0.0.1:${API_PORT}/api/v1/health/live" "api" 240
  wait_for_url "http://127.0.0.1:${API_PORT}/api/v1/health/ready" "api-ready" 240
  wait_for_url "http://127.0.0.1:${GATEWAY_PORT}/api/v1/health/live" "gateway" 240
  wait_for_url "http://127.0.0.1:${FRONTEND_PORT}/portal" "frontend" 240

  log "Bootstrap complete (mode=${OPENCIVIC_MODE})"
}

verify_release_smoke() {
  if [[ "${OPENCIVIC_MODE}" == "pilot" ]]; then
    log "Skipping verify_release in pilot mode (dev tokens disabled)"
    return 0
  fi

  log "Running verify_release..."
  (
    cd "$ROOT_DIR/backend"
    OPENCIVIC_API_URL="http://127.0.0.1:${API_PORT}/api/v1" \
    OPENCIVIC_GATEWAY_URL="http://127.0.0.1:${GATEWAY_PORT}" \
    DEV_AUTH_TOKEN="${DEV_AUTH_TOKEN:-dev-local-token-change-me}" \
    DEV_STEWARD_AUTH_TOKEN="${DEV_STEWARD_AUTH_TOKEN:-dev-steward-token-change-me}" \
    DEV_ADMIN_AUTH_TOKEN="${DEV_ADMIN_AUTH_TOKEN:-dev-admin-token-change-me}" \
      python scripts/verify_release.py --gateway-url "http://127.0.0.1:${GATEWAY_PORT}"
  )
}

playwright_smoke() {
  local mode="${1:-dev}"
  OPENCIVIC_MODE="$mode"
  export OPENCIVIC_MODE

  log "Running Playwright (mode=${mode})..."
  (
    cd "$ROOT_DIR/frontend"
    export OPENCIVIC_FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}"
    export OPENCIVIC_API_URL="http://127.0.0.1:${GATEWAY_PORT}/api/v1"

    if [[ "$mode" == "pilot" ]]; then
      export OPENCIVIC_PILOT_AUTH=true
      npm run test:e2e:pilot
    else
      npm run test:e2e:ci
    fi
  )
}

main() {
  local command="${1:-}"
  case "$command" in
    bootstrap)
      bootstrap "${2:-dev}"
      ;;
    verify-release)
      verify_release_smoke
      ;;
    playwright)
      playwright_smoke "${2:-dev}"
      ;;
    *)
      echo "Usage: $0 {bootstrap [dev|pilot]|verify-release|playwright [dev|pilot]}" >&2
      exit 1
      ;;
  esac
}

main "$@"
