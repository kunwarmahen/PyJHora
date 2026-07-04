#!/usr/bin/env bash
#
# dev.sh — start/stop/restart the Jyotir AI web app (backend + frontend)
#
# Usage:
#   ./dev.sh start            # start both backend and frontend
#   ./dev.sh stop             # stop both
#   ./dev.sh restart          # restart both
#   ./dev.sh status           # show status of both
#
#   ./dev.sh start backend    # only the backend  (FastAPI/uvicorn :8000)
#   ./dev.sh stop frontend    # only the frontend (React dev server :3000)
#   ./dev.sh restart backend  # ...and so on for any action + target
#
#   ./dev.sh logs             # tail both logs
#   ./dev.sh logs backend     # tail one log
#
# Production frontend (optimized static build via `npm run build`):
#   ./dev.sh build-web        # build the optimized bundle -> frontend/build
#   ./dev.sh serve            # serve the production build (:3000, SPA routing)
#                             #   builds first if frontend/build is missing
#
# Containers (docker / podman compose, auto-detected):
#   ./dev.sh build            # build image(s)
#   ./dev.sh up               # build + deploy containers (detached)
#   ./dev.sh down             # stop & remove containers
#   ./dev.sh ps               # container status
#   ./dev.sh clogs [backend]  # follow container logs (optionally one service)
#   DEV_COMPOSE="podman compose" ./dev.sh up   # force a specific engine
#
# Targets: backend | frontend | both (default: both)

set -euo pipefail

# --- paths --------------------------------------------------------------
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
RUN_DIR="$ROOT_DIR/.run"          # holds pid + log files
mkdir -p "$RUN_DIR"

BACKEND_PID="$RUN_DIR/backend.pid"
FRONTEND_PID="$RUN_DIR/frontend.pid"
BACKEND_LOG="$RUN_DIR/backend.log"
FRONTEND_LOG="$RUN_DIR/frontend.log"

BACKEND_PORT=8000
FRONTEND_PORT=3000

COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"
COMPOSE_BIN=""                    # resolved lazily by detect_compose

# --- colours ------------------------------------------------------------
if [ -t 1 ]; then
  C_OK="\033[0;32m"; C_ERR="\033[0;31m"; C_INFO="\033[0;36m"; C_RST="\033[0m"
else
  C_OK=""; C_ERR=""; C_INFO=""; C_RST=""
fi
info() { echo -e "${C_INFO}==>${C_RST} $*"; }
ok()   { echo -e "${C_OK}✓${C_RST} $*"; }
err()  { echo -e "${C_ERR}✗${C_RST} $*" >&2; }

# --- helpers ------------------------------------------------------------
is_running() {  # is_running <pidfile>
  local f="$1"
  [ -f "$f" ] && kill -0 "$(cat "$f")" 2>/dev/null
}

kill_tree() {  # kill_tree <pid> — kill a pid and ALL descendants, leaves first
  local pid="$1" child
  for child in $(pgrep -P "$pid" 2>/dev/null); do
    kill_tree "$child"
  done
  kill "$pid" 2>/dev/null || true
}

kill_port() {  # kill_port <port> — kill whatever is LISTENing on a tcp port
  local port="$1" pids
  pids="$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  [ -z "$pids" ] && return
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true
  # wait for a clean exit, then force-kill anything still bound
  for _ in 1 2 3 4 5 6; do
    pids="$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true)"
    [ -z "$pids" ] && return
    sleep 0.5
  done
  # shellcheck disable=SC2086
  kill -9 $pids 2>/dev/null || true
}

# --- backend ------------------------------------------------------------
start_backend() {
  if is_running "$BACKEND_PID"; then
    ok "backend already running (pid $(cat "$BACKEND_PID"), :$BACKEND_PORT)"
    return
  fi
  info "starting backend on :$BACKEND_PORT ..."
  (
    cd "$BACKEND_DIR"
    # Invoke the venv interpreter directly rather than sourcing activate:
    # a venv resolves from the executable's location, so this is robust even
    # if the venv was created under an old (since-renamed) directory path.
    if [ -x venv/bin/python ]; then
      exec venv/bin/python main.py
    fi
    exec python main.py
  ) >"$BACKEND_LOG" 2>&1 &
  echo $! >"$BACKEND_PID"
  sleep 1
  if is_running "$BACKEND_PID"; then
    ok "backend started (pid $(cat "$BACKEND_PID")) — logs: $BACKEND_LOG"
  else
    err "backend failed to start — see $BACKEND_LOG"
    tail -n 20 "$BACKEND_LOG" || true
  fi
}

stop_backend() {
  if is_running "$BACKEND_PID"; then
    local pid; pid="$(cat "$BACKEND_PID")"
    info "stopping backend (pid $pid) ..."
    # kill the whole tree so uvicorn child workers go too
    kill_tree "$pid"
  fi
  # safety net: anything still matching the entrypoint or holding the port
  pkill -f "python main.py" 2>/dev/null || true
  kill_port "$BACKEND_PORT"
  rm -f "$BACKEND_PID"
  ok "backend stopped"
}

# --- frontend -----------------------------------------------------------
start_frontend() {
  if is_running "$FRONTEND_PID"; then
    ok "frontend already running (pid $(cat "$FRONTEND_PID"), :$FRONTEND_PORT)"
    return
  fi
  info "starting frontend on :$FRONTEND_PORT ..."
  (
    cd "$FRONTEND_DIR"
    exec env BROWSER=none npm start
  ) >"$FRONTEND_LOG" 2>&1 &
  echo $! >"$FRONTEND_PID"
  sleep 1
  if is_running "$FRONTEND_PID"; then
    ok "frontend starting (pid $(cat "$FRONTEND_PID")) — logs: $FRONTEND_LOG"
  else
    err "frontend failed to start — see $FRONTEND_LOG"
    tail -n 20 "$FRONTEND_LOG" || true
  fi
}

stop_frontend() {
  if is_running "$FRONTEND_PID"; then
    local pid; pid="$(cat "$FRONTEND_PID")"
    info "stopping frontend (pid $pid) ..."
    # npm start -> react-scripts -> webpack dev server: kill the whole tree,
    # not just direct children, or the grandchild keeps holding the port
    kill_tree "$pid"
  fi
  # safety net: the dev server that actually binds the port
  kill_port "$FRONTEND_PORT"
  rm -f "$FRONTEND_PID"
  ok "frontend stopped"
}

# --- production frontend build ------------------------------------------
build_web() {  # produce an optimized static bundle in frontend/build
  info "building production frontend bundle ..."
  ( cd "$FRONTEND_DIR" && npm run build )
  ok "production build ready — $FRONTEND_DIR/build"
}

serve_frontend() {  # serve the optimized build with SPA (client-side routing) fallback
  if is_running "$FRONTEND_PID"; then
    ok "frontend already running (pid $(cat "$FRONTEND_PID"), :$FRONTEND_PORT)"
    return
  fi
  if [ ! -d "$FRONTEND_DIR/build" ]; then
    info "no production build found — building first ..."
    build_web
  fi
  info "serving production build on :$FRONTEND_PORT ..."
  (
    cd "$FRONTEND_DIR"
    # `serve -s` rewrites unknown paths to index.html so React Router deep links work
    exec npx --yes serve -s build -l "$FRONTEND_PORT"
  ) >"$FRONTEND_LOG" 2>&1 &
  echo $! >"$FRONTEND_PID"
  sleep 1
  if is_running "$FRONTEND_PID"; then
    ok "frontend (prod) serving (pid $(cat "$FRONTEND_PID")) — logs: $FRONTEND_LOG"
  else
    err "frontend failed to serve — see $FRONTEND_LOG"
    tail -n 20 "$FRONTEND_LOG" || true
  fi
}

# --- status -------------------------------------------------------------
status_one() {  # status_one <name> <pidfile> <port>
  local name="$1" f="$2" port="$3"
  if is_running "$f"; then
    ok "$name: running (pid $(cat "$f"), :$port)"
  else
    err "$name: stopped"
  fi
}

# --- containers (docker / podman) ---------------------------------------
# Resolve a compose command. Override with DEV_COMPOSE, e.g.
#   DEV_COMPOSE="podman compose" ./dev.sh up
detect_compose() {
  [ -n "$COMPOSE_BIN" ] && return 0
  if [ -n "${DEV_COMPOSE:-}" ]; then
    COMPOSE_BIN="$DEV_COMPOSE"
  elif docker compose version >/dev/null 2>&1; then
    COMPOSE_BIN="docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_BIN="docker-compose"
  elif podman compose version >/dev/null 2>&1; then
    COMPOSE_BIN="podman compose"
  elif command -v podman-compose >/dev/null 2>&1; then
    COMPOSE_BIN="podman-compose"
  else
    err "no compose tool found — install docker compose or podman compose"
    exit 1
  fi
  info "compose: $COMPOSE_BIN"
}

compose() {  # run from the web dir so the backend's 'context: ..' resolves to repo root
  detect_compose
  # shellcheck disable=SC2086
  ( cd "$ROOT_DIR" && $COMPOSE_BIN -f "$COMPOSE_FILE" "$@" )
}

compose_services() {  # map dev target -> compose service name(s); empty = all
  case "$TARGET" in
    backend)  echo backend ;;
    frontend) echo frontend ;;
    both|"")  echo "" ;;
    *) err "unknown target '$TARGET' (use: backend | frontend | both)"; exit 1 ;;
  esac
}

# shellcheck disable=SC2046  # word-splitting of compose_services is intentional
container_build() { info "building image(s) ...";   compose build $(compose_services); ok "build complete"; }
container_up()    { info "deploying container(s) ..."; compose up -d --build $(compose_services); ok "containers up"; compose ps; }
container_down()  { info "stopping container(s) ..."; compose down;                  ok "containers down"; }
container_ps()    { compose ps; }
container_clogs() { compose logs -f --tail=100 $(compose_services); }

# --- dispatch -----------------------------------------------------------
ACTION="${1:-}"
TARGET="${2:-both}"

do_target() {  # do_target <backend_fn> <frontend_fn>
  case "$TARGET" in
    backend)  "$1" ;;
    frontend) "$2" ;;
    both|"")  "$1"; "$2" ;;
    *) err "unknown target '$TARGET' (use: backend | frontend | both)"; exit 1 ;;
  esac
}

case "$ACTION" in
  start)   do_target start_backend start_frontend ;;
  stop)    do_target stop_backend  stop_frontend ;;
  restart)
    do_target stop_backend stop_frontend
    sleep 1
    do_target start_backend start_frontend
    ;;
  status)
    status_one backend  "$BACKEND_PID"  "$BACKEND_PORT"
    status_one frontend "$FRONTEND_PID" "$FRONTEND_PORT"
    ;;
  logs)
    case "$TARGET" in
      backend)  tail -f "$BACKEND_LOG" ;;
      frontend) tail -f "$FRONTEND_LOG" ;;
      both|"")  tail -f "$BACKEND_LOG" "$FRONTEND_LOG" ;;
      *) err "unknown target '$TARGET'"; exit 1 ;;
    esac
    ;;
  build-web|webbuild) build_web ;;
  serve)   serve_frontend ;;
  build)   container_build ;;
  up)      container_up ;;
  down)    container_down ;;
  ps)      container_ps ;;
  clogs)   container_clogs ;;
  ""|-h|--help|help)
    sed -n '2,22p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    ;;
  *)
    err "unknown action '$ACTION'"
    echo "Run './dev.sh help' for usage." >&2
    exit 1
    ;;
esac
