#!/usr/bin/env bash
#
# dev.sh — start/stop/restart the PyJHora web app (backend + frontend)
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

# --- status -------------------------------------------------------------
status_one() {  # status_one <name> <pidfile> <port>
  local name="$1" f="$2" port="$3"
  if is_running "$f"; then
    ok "$name: running (pid $(cat "$f"), :$port)"
  else
    err "$name: stopped"
  fi
}

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
  ""|-h|--help|help)
    sed -n '2,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    ;;
  *)
    err "unknown action '$ACTION'"
    echo "Run './dev.sh help' for usage." >&2
    exit 1
    ;;
esac
