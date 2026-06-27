#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ENV_FILE:-.env}"
MODE="${OPENCIVIC_COMPOSE_MODE:-dev}"
PILOT="${OPENCIVIC_PILOT:-false}"
RUN_DIR="$ROOT_DIR/.opencivic"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"
FRONTEND_LOG_FILE="$RUN_DIR/frontend.log"

log() {
  printf '\n[%s] %s\n' "$(date -u +'%H:%M:%S')" "$*"
}

compose() {
  local -a files=()
  if [[ "$MODE" == "prod" ]]; then
    files=(-f docker-compose.prod.yml)
  else
    files=(-f docker-compose.dev.yml)
    if [[ "$PILOT" == "true" ]]; then
      files+=(-f docker-compose.pilot.yml)
    fi
  fi
  docker compose "${files[@]}" --env-file "$ENV_FILE" "$@"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command not found: $1" >&2
    exit 1
  fi
}

is_windows() {
  case "$(uname -s 2>/dev/null)" in
    MINGW* | MSYS* | CYGWIN*) return 0 ;;
  esac
  [[ "${OS:-}" == "Windows_NT" ]]
}

load_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "Missing $ENV_FILE. Copy .env.example to .env and set values." >&2
    exit 1
  fi
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  OPENCIVIC_API_PORT="${OPENCIVIC_API_PORT:-8100}"
  OPENCIVIC_FRONTEND_PORT="${OPENCIVIC_FRONTEND_PORT:-3100}"
  OPENCIVIC_GATEWAY_PORT="${OPENCIVIC_GATEWAY_PORT:-8088}"
  if port_in_use "$OPENCIVIC_GATEWAY_PORT"; then
    for candidate in 8088 8090 8888 8099 8188 8800; do
      if ! port_in_use "$candidate"; then
        log "Gateway port $OPENCIVIC_GATEWAY_PORT in use — switching to $candidate"
        OPENCIVIC_GATEWAY_PORT="$candidate"
        break
      fi
    done
    if port_in_use "$OPENCIVIC_GATEWAY_PORT"; then
      echo "No free gateway port (tried 8088, 8090, 8888, 8099, 8188, 8800). Set OPENCIVIC_GATEWAY_PORT in .env." >&2
      exit 1
    fi
  fi
  export OPENCIVIC_API_PORT OPENCIVIC_FRONTEND_PORT OPENCIVIC_GATEWAY_PORT
}

port_in_use() {
  local port="$1"
  if command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -Command \
      "if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
    return $?
  fi
  if command -v ss >/dev/null 2>&1; then
    ss -tln | grep -q ":${port} "
    return $?
  fi
  netstat -tln 2>/dev/null | grep -q ":${port} "
}

frontend_pid_running() {
  [[ -f "$FRONTEND_PID_FILE" ]] || return 1
  local pid
  pid="$(cat "$FRONTEND_PID_FILE")"
  kill -0 "$pid" 2>/dev/null
}

stop_host_frontend() {
  if frontend_pid_running; then
    local pid
    pid="$(cat "$FRONTEND_PID_FILE")"
    log "Stopping host frontend (pid $pid)..."
    kill "$pid" 2>/dev/null || true
    sleep 1
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$FRONTEND_PID_FILE"
}

ensure_frontend_deps() {
  require_command npm
  if [[ ! -d "$ROOT_DIR/frontend/node_modules/next" ]]; then
    log "Installing frontend dependencies (one-time)..."
    (cd "$ROOT_DIR/frontend" && npm install)
  fi
}

start_host_frontend() {
  ensure_frontend_deps
  stop_host_frontend
  mkdir -p "$RUN_DIR"
  log "Starting frontend on http://localhost:${OPENCIVIC_FRONTEND_PORT}"
  (
    cd "$ROOT_DIR/frontend"
    export NEXT_PUBLIC_API_URL="http://localhost:${OPENCIVIC_API_PORT}/api/v1"
    export NEXT_TELEMETRY_DISABLED=1
    nohup npm run dev -- -p "${OPENCIVIC_FRONTEND_PORT}" >"$FRONTEND_LOG_FILE" 2>&1 &
    echo $! >"$FRONTEND_PID_FILE"
  )
}

wait_for_url() {
  local url="$1"
  local label="$2"
  local timeout_seconds="${3:-120}"
  local elapsed=0
  while (( elapsed < timeout_seconds )); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 3
    elapsed=$((elapsed + 3))
  done
  echo "Timed out waiting for $label at $url" >&2
  return 1
}

check_ports() {
  local -a ports=()
  if [[ "$MODE" == "prod" ]]; then
    ports=(80)
  else
    ports=("$OPENCIVIC_API_PORT")
    if ! frontend_pid_running && ! port_in_use "$OPENCIVIC_FRONTEND_PORT"; then
      : # frontend port free
    elif frontend_pid_running; then
      : # our frontend already on the port — ok
    elif port_in_use "$OPENCIVIC_FRONTEND_PORT"; then
      ports+=("$OPENCIVIC_FRONTEND_PORT")
    fi
  fi

  local blocked=()
  local port
  for port in "${ports[@]}"; do
    if port_in_use "$port"; then
      blocked+=("$port")
    fi
  done

  if ((${#blocked[@]} > 0)); then
    echo "Cannot start — port(s) already in use: ${blocked[*]}" >&2
    echo "Stop the conflicting service or change OPENCIVIC_API_PORT / OPENCIVIC_FRONTEND_PORT in .env" >&2
    if command -v docker >/dev/null 2>&1; then
      echo "Containers publishing these ports:" >&2
      docker ps --format "table {{.Names}}\t{{.Ports}}" 2>/dev/null | grep -E "$(IFS='|'; echo "${blocked[*]}")" >&2 || true
    fi
    exit 1
  fi

  if compose ps --status running -q 2>/dev/null | grep -q .; then
    log "OpenCivic ($MODE) backend is already running — refreshing..."
    return 0
  fi
}

wait_for_healthy() {
  local timeout_seconds="${1:-300}"
  local elapsed=0
  log "Waiting for Docker services (timeout ${timeout_seconds}s)..."
  while (( elapsed < timeout_seconds )); do
    if ! compose ps --format json 2>/dev/null | grep -q '"Health":"unhealthy"'; then
      if ! compose ps --format json 2>/dev/null | grep -q '"Health":"starting"'; then
        return 0
      fi
    fi
    sleep 5
    elapsed=$((elapsed + 5))
  done
  echo "Timed out waiting for Docker services." >&2
  compose ps
  return 1
}

print_status() {
  compose ps
  if frontend_pid_running; then
    printf 'Host frontend: running (pid %s)\n' "$(cat "$FRONTEND_PID_FILE")"
  fi
}

verify_dev() {
  local api_base frontend_base gateway_base
  api_base="$(dev_base_url "$OPENCIVIC_API_PORT")"
  frontend_base="$(dev_base_url "$OPENCIVIC_FRONTEND_PORT")"
  gateway_base="$(dev_base_url "$OPENCIVIC_GATEWAY_PORT")"

  curl -fsS "${api_base}/api/v1/health/live" | grep -q '"status"'
  curl -fsS "${api_base}/api/v1/health/ready" | grep -q '"database":"ok"'
  curl -fsS "${api_base}/api/v1/docs" | grep -q 'swagger'
  curl -fsS "${gateway_base}/api/v1/health/live" | grep -q '"status"'
  curl -fsS "${gateway_base}/api/v1/health/ready" | grep -q '"database":"ok"'
  log "Running API smoke checks..."
  local verify_args=(python scripts/verify_release.py --gateway-url "${gateway_base}")
  if [[ "$PILOT" == "true" ]]; then
    verify_args+=(--tus)
  fi
  OPENCIVIC_API_URL="http://host.docker.internal:${OPENCIVIC_API_PORT}/api/v1" \
    OPENCIVIC_GATEWAY_URL="${gateway_base}" \
    DEV_AUTH_TOKEN="${DEV_AUTH_TOKEN:-dev-local-token-change-me}" \
    DEV_STEWARD_AUTH_TOKEN="${DEV_STEWARD_AUTH_TOKEN:-dev-steward-token-change-me}" \
    DEV_ADMIN_AUTH_TOKEN="${DEV_ADMIN_AUTH_TOKEN:-dev-admin-token-change-me}" \
    TUS_ENABLED="${TUS_ENABLED:-false}" \
    compose run --rm --no-deps api "${verify_args[@]}"
  wait_for_url "${frontend_base}/portal" "frontend" 60
  log "Dev stack ready (verified):"
  log "  ${frontend_base}/portal          — catalog"
  log "  ${frontend_base}/login           — staff sign-in"
  log "  ${frontend_base}/admin           — IT admin (org_admin)"
  log "  ${frontend_base}/developer       — developer console"
  log "  ${gateway_base}/api/v1             — API via nginx → APISIX"
  log "  ${api_base}/api/v1/health/live   — API direct (debug)"
  if is_windows; then
    log "  (Windows: 127.0.0.1 avoids Docker Desktop IPv6 localhost hangs)"
  fi
}

run_e2e_smoke() {
  if [[ ! -f "$ROOT_DIR/frontend/e2e/smoke.spec.ts" ]]; then
    return 0
  fi
  if ! command -v npm >/dev/null 2>&1; then
    log "Skipping Playwright smoke — npm not found"
    return 0
  fi
  log "Running Playwright UI smoke tests..."
  local api_base frontend_base gateway_base
  api_base="$(dev_base_url "$OPENCIVIC_API_PORT")"
  frontend_base="$(dev_base_url "$OPENCIVIC_FRONTEND_PORT")"
  gateway_base="$(dev_base_url "$OPENCIVIC_GATEWAY_PORT")"
  (
    cd "$ROOT_DIR/frontend"
    if [[ ! -d node_modules/@playwright/test ]]; then
      npm install --no-audit --no-fund
      npx playwright install chromium --with-deps 2>/dev/null || npx playwright install chromium
    fi
    if [[ "$PILOT" == "true" ]]; then
      OPENCIVIC_FRONTEND_URL="$frontend_base" \
      OPENCIVIC_API_URL="${gateway_base}/api/v1" \
      OPENCIVIC_PILOT_AUTH=true \
        npm run test:e2e:pilot
    else
      OPENCIVIC_FRONTEND_URL="$frontend_base" \
      OPENCIVIC_API_URL="${gateway_base}/api/v1" \
        npm run test:e2e:ci
    fi
  )
}

verify_prod() {
  curl -fsS "http://localhost/health" >/dev/null
  curl -fsS "http://localhost/api/v1/health/live" | grep -q '"status"'
  curl -fsS "http://localhost/api/v1/docs" | grep -q 'swagger'
  log "Production stack ready at http://localhost"
}

stop_stale_windows_frontend() {
  if ! is_windows; then
    return 0
  fi
  stop_host_frontend
  if command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -Command "
      Get-NetTCPConnection -LocalPort ${OPENCIVIC_FRONTEND_PORT} -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object {
          \$p = Get-Process -Id \$_.OwningProcess -ErrorAction SilentlyContinue
          if (\$p -and \$p.ProcessName -eq 'node') {
            Stop-Process -Id \$p.Id -Force -ErrorAction SilentlyContinue
          }
        }" >/dev/null 2>&1 || true
  fi
}

dev_base_url() {
  if is_windows; then
    printf 'http://127.0.0.1:%s' "$1"
  else
    printf 'http://localhost:%s' "$1"
  fi
}

start_dev_frontend() {
  stop_stale_windows_frontend

  log "Starting frontend container..."
  if compose up -d --build frontend; then
    local frontend_url
    frontend_url="$(dev_base_url "$OPENCIVIC_FRONTEND_PORT")"
    if wait_for_url "${frontend_url}/portal" "frontend" 180; then
      return 0
    fi
    log "Docker frontend did not become ready — falling back to host frontend"
    compose stop frontend 2>/dev/null || true
  fi
  if is_windows; then
    echo "Docker frontend failed on Windows. Restart Docker Desktop and run ./deploy.sh up again." >&2
    exit 1
  fi
  start_host_frontend
  wait_for_url "http://localhost:${OPENCIVIC_FRONTEND_PORT}/portal" "frontend" 120
}

cmd_up() {
  require_command docker
  require_command curl
  load_env
  check_ports
  mkdir -p "$RUN_DIR"
  stop_stale_windows_frontend

  if [[ "$MODE" == "prod" ]]; then
    log "Starting production stack (20+ services) — first run may take 15+ minutes"
    mkdir -p infrastructure/docker/pgbouncer
    printf '"opencivic" "%s"\n' "$POSTGRES_PASSWORD" > infrastructure/docker/pgbouncer/userlist.txt
    compose up -d --build
    wait_for_healthy
    print_status
    verify_prod
    return 0
  fi

  log "Starting dev stack (postgres, valkey, minio, keycloak, clamav, api, worker, beat + gateway + frontend)..."
  compose up -d --build postgres valkey minio keycloak clamav
  wait_for_healthy
  log "Applying database migrations..."
  compose run --rm --no-deps api alembic upgrade head
  log "Seeding dev tenant and ensuring object storage..."
  compose run --rm --no-deps api python scripts/seed_dev.py
  compose up -d --build --force-recreate api worker beat
  wait_for_healthy
  compose up -d --build apisix frontend
  wait_for_healthy
  compose up -d nginx
  wait_for_healthy
  if [[ "$PILOT" == "true" ]]; then
    compose up -d tusd
    wait_for_healthy
    if [[ "${PGBACKREST_ENABLED:-false}" == "true" ]]; then
      log "Starting pgBackRest sidecar and seeding stanza..."
      compose --profile backup up -d pgbackrest
      sleep 5
      compose exec -T pgbackrest pgbackrest stanza-create --stanza="${PGBACKREST_STANZA:-opencivic}" \
        2>/dev/null || true
      compose exec -T pgbackrest pgbackrest backup --stanza="${PGBACKREST_STANZA:-opencivic}" --type=full \
        2>/dev/null || log "pgBackRest backup skipped (may already exist)"
    fi
  fi
  start_dev_frontend
  print_status
  verify_dev
  run_e2e_smoke
}

cmd_down() {
  require_command docker
  if [[ "$MODE" != "prod" ]]; then
    stop_host_frontend
  fi
  compose down "$@"
}

cmd_status() {
  require_command docker
  print_status
}

cmd_logs() {
  require_command docker
  compose logs -f "${@:-}"
}

cmd_frontend() {
  load_env
  start_host_frontend
  wait_for_url "http://localhost:${OPENCIVIC_FRONTEND_PORT}" "frontend" 120
  log "Frontend ready at http://localhost:${OPENCIVIC_FRONTEND_PORT}"
}

usage() {
  cat <<EOF
Usage: ./deploy.sh [dev|prod|pilot] <command>

Commands:
  up       Build and start the full dev stack (backend + frontend + gateway)
  down     Stop containers and host frontend (add -v to remove volumes)
  status   Show service status
  logs     Follow Docker logs
  frontend Restart only the host frontend (usually not needed)

Examples:
  ./deploy.sh up              # start everything (nginx → APISIX → API)
  ./deploy.sh pilot up        # Tier B pilot overlay (Keycloak, TUS, backup)
  ./deploy.sh down            # stop everything
  ./deploy.sh prod up         # full production stack
EOF
}

main() {
  local first="${1:-}"
  case "$first" in
    dev) MODE=dev; shift ;;
    prod) MODE=prod; shift ;;
    pilot) MODE=dev; PILOT=true; shift ;;
  esac

  local command="${1:-}"
  case "$command" in
    up) shift; cmd_up "$@" ;;
    down) shift; cmd_down "$@" ;;
    status) shift; cmd_status "$@" ;;
    logs) shift; cmd_logs "$@" ;;
    frontend) shift; cmd_frontend "$@" ;;
    *) usage; exit 1 ;;
  esac
}

main "$@"
