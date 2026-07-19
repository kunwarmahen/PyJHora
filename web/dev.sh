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
#   ./dev.sh test             # backend golden-value + endpoint tests (§3.2)
#   ./dev.sh test engine      # also smoke-run PyJHora's own ~1,500 tests
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
# NAS deploy (remote Docker over SSH, Cloudflare Tunnel for domain + SSL):
#   ./dev.sh nas deploy       # build images locally, ship + load on NAS, start stack
#   ./dev.sh nas up           # (re)start on NAS without rebuilding
#   ./dev.sh nas down         # stop the stack on NAS
#   ./dev.sh nas logs [svc]   # tail NAS logs (optionally one service)
#   ./dev.sh nas ps           # container status on NAS
#   ./dev.sh nas shell [svc]  # shell into a NAS container (default: backend)
#   #   config via web/.env (see .env.nas.example): NAS_HOST/USER/PATH, TUNNEL_TOKEN, ...
#   #   e.g.  NAS_HOST=192.168.1.50 ./dev.sh nas deploy
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

# Overridable so the stack can run beside another service already holding a
# default port:  BACKEND_PORT=8001 ./dev.sh start
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"
COMPOSE_BIN=""                    # resolved lazily by detect_compose

# --- NAS deploy config --------------------------------------------------
ENV_FILE="$ROOT_DIR/.env"
COMPOSE_NAS="$ROOT_DIR/docker-compose.nas.yml"

# Image names (built locally, loaded on the NAS — never built there).
IMG_BACKEND="jyotirai-backend:latest"
IMG_WEB="jyotirai-web:latest"

# Read a single KEY=value from web/.env (first match, value verbatim; empty if absent).
env_val() { [ -f "$ENV_FILE" ] && grep -E "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2- || true; }

# NAS connection: env var  >  .env  >  built-in default
NAS_HOST="${NAS_HOST:-$(env_val NAS_HOST)}"
NAS_USER="${NAS_USER:-$(env_val NAS_USER)}"; NAS_USER="${NAS_USER:-$(whoami)}"
NAS_PATH="${NAS_PATH:-$(env_val NAS_PATH)}"; NAS_PATH="${NAS_PATH:-pyjhora}"  # relative = NAS home dir
NAS_SSH_KEY="${NAS_SSH_KEY:-$(env_val NAS_SSH_KEY)}"
NAS_SSH_PORT="${NAS_SSH_PORT:-$(env_val NAS_SSH_PORT)}"; NAS_SSH_PORT="${NAS_SSH_PORT:-22}"
NAS_SSH_CTL="/tmp/.jyotirai-ssh-$$"   # ControlMaster socket — one password prompt per deploy

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

kill_port_if_ours() {  # kill_port_if_ours <port> <cmdline-pattern>
  # Kill port holders only when their command line matches OUR entrypoint, so a
  # co-resident app (another project's uvicorn, say) is reported and left alone.
  local port="$1" pattern="$2" pid cmd
  for pid in $(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true); do
    cmd="$(ps -p "$pid" -o args= 2>/dev/null || true)"
    case "$cmd" in
      *"$pattern"*) kill "$pid" 2>/dev/null || true ;;
      *) err "port $port is held by another app (pid $pid) — leaving it alone:"
         printf '      %s\n' "$(printf '%s' "$cmd" | cut -c1-100)" ;;
    esac
  done
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
    # Sign in with Google: surface the client ID from web/.env into the process
    # env so pydantic-settings picks it up in local (non-docker) dev too.
    export GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID:-$(env_val GOOGLE_CLIENT_ID)}"
    export BACKEND_PORT
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
  # Safety net for a backend we lost the pidfile for. Deliberately NOT a blanket
  # kill_port: another project may legitimately hold this port, and killing a
  # stranger's server because it answers on :8000 is never what "stop the
  # backend" should mean.
  pkill -f "python main.py" 2>/dev/null || true
  kill_port_if_ours "$BACKEND_PORT" "main.py"
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
    # Pass the Google client ID from web/.env to CRA's dev server (create-react-app
    # only inlines REACT_APP_* vars present in its environment at build/start).
    exec env BROWSER=none \
      PORT="$FRONTEND_PORT" \
      REACT_APP_API_URL="${REACT_APP_API_URL:-http://localhost:$BACKEND_PORT}" \
      REACT_APP_GOOGLE_CLIENT_ID="${REACT_APP_GOOGLE_CLIENT_ID:-$(env_val REACT_APP_GOOGLE_CLIENT_ID)}" \
      npm start
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

# --- NAS deploy (remote Docker over SSH) --------------------------------
# Build the two images locally, ship them to the NAS, load + start with the
# Cloudflare-Tunnel compose stack. The NAS never builds anything.

ENGINE=""                          # local image build engine (docker|podman)
detect_engine() {
  [ -n "$ENGINE" ] && return 0
  if command -v docker >/dev/null 2>&1; then ENGINE="docker"
  elif command -v podman >/dev/null 2>&1; then ENGINE="podman"
  else err "no docker/podman found to build images"; exit 1; fi
  info "build engine: $ENGINE"
}

require_nas_host() {
  [ -n "$NAS_HOST" ] || { err "NAS_HOST not set — add it to web/.env or run: NAS_HOST=<ip> ./dev.sh nas ..."; exit 1; }
}
require_env() {
  [ -f "$ENV_FILE" ] || { err "web/.env not found — run: cp .env.nas.example .env  then fill it in"; exit 1; }
}

# shellcheck disable=SC2046  # intentional word-splitting of ssh_opts below
ssh_opts() {
  local o="-p ${NAS_SSH_PORT} -o StrictHostKeyChecking=no -o ConnectTimeout=10"
  o="$o -o ControlMaster=auto -o ControlPath=${NAS_SSH_CTL} -o ControlPersist=120"
  [ -n "$NAS_SSH_KEY" ] && o="$o -i $NAS_SSH_KEY"
  echo "$o"
}
nas_ssh_open()  { info "connecting to ${NAS_USER}@${NAS_HOST} ..."; ssh $(ssh_opts) -o ControlMaster=yes -fN "${NAS_USER}@${NAS_HOST}"; }
nas_ssh_close() { ssh -O exit -o "ControlPath=${NAS_SSH_CTL}" "${NAS_USER}@${NAS_HOST}" 2>/dev/null || true; rm -f "$NAS_SSH_CTL"; }
nas_ssh() {  # nas_ssh [-t] <cmd...>   (-t forces a PTY so sudo can prompt)
  local tty=""; [ "${1:-}" = "-t" ] && { tty="-tt"; shift; }
  ssh $(ssh_opts) $tty "${NAS_USER}@${NAS_HOST}" "$@"
}
nas_scp() {  # nas_scp <local> <remote>
  local key=""; [ -n "$NAS_SSH_KEY" ] && key="-i $NAS_SSH_KEY"
  scp -P "$NAS_SSH_PORT" -o StrictHostKeyChecking=no -o ControlMaster=auto \
      -o "ControlPath=${NAS_SSH_CTL}" -o ControlPersist=120 $key "$1" "${NAS_USER}@${NAS_HOST}:$2"
}

nas_build_images() {
  detect_engine
  info "building backend image $IMG_BACKEND (context = repo root) ..."
  # Context is the repo root so the image can vendor the jhora `src/` library.
  ( cd "$ROOT_DIR/.." && $ENGINE build -t "$IMG_BACKEND" -f web/backend/Dockerfile . )

  info "building web image $IMG_WEB (static build + nginx) ..."
  # Same-origin build (REACT_APP_API_URL=""); pull branding from .env when present.
  local wargs=(--build-arg "REACT_APP_API_URL=")
  local v
  v="$(env_val REACT_APP_SITE_TITLE)";       [ -n "$v" ] && wargs+=(--build-arg "REACT_APP_SITE_TITLE=$v")
  v="$(env_val REACT_APP_SITE_TAGLINE)";      [ -n "$v" ] && wargs+=(--build-arg "REACT_APP_SITE_TAGLINE=$v")
  v="$(env_val REACT_APP_ENABLE_MAP_PICKER)"; [ -n "$v" ] && wargs+=(--build-arg "REACT_APP_ENABLE_MAP_PICKER=$v")
  v="$(env_val REACT_APP_GOOGLE_CLIENT_ID)";  [ -n "$v" ] && wargs+=(--build-arg "REACT_APP_GOOGLE_CLIENT_ID=$v")
  ( cd "$FRONTEND_DIR" && $ENGINE build "${wargs[@]}" -t "$IMG_WEB" -f Dockerfile.nas . )
  ok "images built"
}

nas_deploy() {
  require_nas_host; require_env
  nas_build_images

  local tb="/tmp/jyotirai-backend.tar.gz" tw="/tmp/jyotirai-web.tar.gz"
  info "exporting images to tarballs ..."
  $ENGINE save "$IMG_BACKEND" | gzip > "$tb"
  $ENGINE save "$IMG_WEB"     | gzip > "$tw"
  ok "exported (backend $(du -sh "$tb" | cut -f1), web $(du -sh "$tw" | cut -f1))"

  nas_ssh_open
  trap 'nas_ssh_close' EXIT

  info "preparing ${NAS_PATH} on ${NAS_HOST} ..."
  nas_ssh "mkdir -p '${NAS_PATH}/nginx' '${NAS_PATH}/mongo-data'"

  info "transferring images + config ..."
  nas_scp "$tb"                          "${NAS_PATH}/jyotirai-backend.tar.gz"
  nas_scp "$tw"                          "${NAS_PATH}/jyotirai-web.tar.gz"
  nas_scp "$COMPOSE_NAS"                 "${NAS_PATH}/docker-compose.yml"
  nas_scp "$ENV_FILE"                    "${NAS_PATH}/.env"
  nas_scp "$ROOT_DIR/nginx/nginx.conf"   "${NAS_PATH}/nginx/nginx.conf"

  info "loading images + (re)starting the stack on NAS ..."
  nas_ssh -t "
    set -e
    cd '${NAS_PATH}'
    echo '[nas] loading images ...'
    sudo docker load < jyotirai-backend.tar.gz
    sudo docker load < jyotirai-web.tar.gz
    # podman-built images may land as localhost/<name>; retag to the plain name compose expects
    sudo docker tag localhost/${IMG_BACKEND} ${IMG_BACKEND} 2>/dev/null || true
    sudo docker tag localhost/${IMG_WEB} ${IMG_WEB} 2>/dev/null || true
    echo '[nas] restarting stack ...'
    sudo docker compose down 2>/dev/null || true
    sudo docker compose up -d --remove-orphans
    sudo docker compose ps
    rm -f jyotirai-backend.tar.gz jyotirai-web.tar.gz
  "

  rm -f "$tb" "$tw"
  nas_ssh_close
  trap - EXIT

  echo ""
  ok "deployed to NAS (${NAS_HOST})"
  info "cloudflared dials the tunnel outbound — the app is live at your Cloudflare hostname"
  info "logs: ./dev.sh nas logs   |   stop: ./dev.sh nas down"
}

nas_up()    { require_nas_host; nas_ssh_open; trap 'nas_ssh_close' EXIT; info "(re)starting stack on ${NAS_HOST} ...";
              nas_ssh -t "cd '${NAS_PATH}' && sudo docker compose up -d --remove-orphans && sudo docker compose ps";
              nas_ssh_close; trap - EXIT; ok "done"; }
nas_down()  { require_nas_host; nas_ssh_open; trap 'nas_ssh_close' EXIT; info "stopping stack on ${NAS_HOST} ...";
              nas_ssh -t "cd '${NAS_PATH}' && sudo docker compose down"; nas_ssh_close; trap - EXIT; ok "done"; }
nas_logs()  { require_nas_host; local svc="${1:-}"; nas_ssh_open; trap 'nas_ssh_close' EXIT; info "tailing NAS logs (Ctrl-C to stop) ...";
              nas_ssh -t "cd '${NAS_PATH}' && sudo docker compose logs -f --tail=100 $svc"; nas_ssh_close; trap - EXIT; }
nas_ps()    { require_nas_host; nas_ssh_open; trap 'nas_ssh_close' EXIT;
              nas_ssh -t "cd '${NAS_PATH}' && sudo docker compose ps"; nas_ssh_close; trap - EXIT; }
nas_shell() { require_nas_host; local svc="${1:-backend}"; nas_ssh_open; trap 'nas_ssh_close' EXIT; info "shell into '$svc' on ${NAS_HOST} ...";
              nas_ssh -t "cd '${NAS_PATH}' && sudo docker compose exec $svc /bin/sh"; nas_ssh_close; trap - EXIT; }

# --- tests --------------------------------------------------------------
# Backend golden-value + endpoint smoke tests (§3.2). `./dev.sh test engine`
# additionally smoke-runs PyJHora's own ~8,000-test suite so an engine version
# bump can be validated.
#
# Known-bad upstream baselines tolerated by run_engine_tests. Each entry is an
# extended regex matched against a whole "Test Failed" line; a run is green only
# if EVERY failure matches one of these. Both the expected AND actual values are
# pinned, so a genuine engine regression shifts "Actual:" and goes red.
#
#   1) Mars/Venus previous conjunction: upstream's own hardcoded matrix records
#      this single event twice with two different values ('13:11:58 PM' at row 3
#      col 6 vs '13:11:57 PM' at row 6 col 3, pvr_tests.py conjunction_tests_2).
#      A pair's conjunction is one physical event, so the table contradicts
#      itself; the engine says '13:11:56 PM'. Recheck on each PyJHora bump.
ENGINE_KNOWN_FAILURES=(
  '^Test#:[0-9]+ Planetary Conjunctions \(Previous\) Expected: 13:11:58 PM Actual: 13:11:56 PM Test Failed .*Mars.*Venus.*conjunction'
)
backend_py() {  # echo the backend interpreter
  if [ -x "$BACKEND_DIR/venv/bin/python" ]; then echo "$BACKEND_DIR/venv/bin/python";
  else echo python; fi
}
run_tests() {
  local py; py="$(backend_py)"
  info "running backend golden + endpoint tests ..."
  ( cd "$BACKEND_DIR" && "$py" -m pytest tests/ -q "$@" )
}
run_engine_tests() {
  local py; py="$(backend_py)"
  local log="${TMPDIR:-/tmp}/pyjhora-engine-tests.$$.log"
  # pvr_tests.py is NOT a pytest suite -- it is a standalone __main__ script with
  # its own runner, so it must be executed as a module (pytest only collects the
  # imported `test_example` helper and errors on its missing "fixtures").
  # It also always exits 0 (it computes exit_code, then ends with a bare exit()),
  # so trust its printed "#Failed Tests N" summary rather than the exit status.
  # NOTE: the suite stops at the FIRST failure (set_stop_on_fail(True) in its
  # __main__), so an unexpected failure leaves every later test unrun.
  info "smoke-running PyJHora's own test suite (src/jhora/tests/pvr_tests.py, ~2 min) ..."
  set +e
  ( cd "$ROOT_DIR/.." && PYTHONPATH=src PYJHORA_TEST_AUTO_CONFIRM=1 \
      "$py" -m jhora.tests.pvr_tests ) 2>&1 | tee "$log" | grep -E "Test Failed|Total Tests|Elapsed time|Traceback"
  local rc="${PIPESTATUS[0]}"
  local summary; summary="$(grep -E "^Total Tests " "$log" | tail -1)"
  local fails; fails="$(grep -E "Test Failed" "$log")"
  set -e
  local failed; failed="$(printf '%s' "$summary" | sed -nE 's/.*#Failed Tests ([0-9]+).*/\1/p')"
  info "${summary:-no test summary emitted}  (full log: $log)"

  # Drop known-bad upstream baselines; anything left is a real failure.
  local unknown="$fails" known
  for known in "${ENGINE_KNOWN_FAILURES[@]}"; do
    unknown="$(printf '%s' "$unknown" | { grep -vE "$known" || true; })"
  done
  if [ -n "$fails" ] && [ -z "$unknown" ]; then
    info "tolerating ${failed} known-bad upstream baseline(s) -- see ENGINE_KNOWN_FAILURES"
  fi

  if [ "$rc" -ne 0 ] || [ -z "$failed" ] || [ -n "$unknown" ]; then
    err "engine tests reported failures (review before trusting a version bump)"
    [ -n "$unknown" ] && printf '%s\n' "$unknown" >&2
    return 1
  fi
  info "engine tests passed"
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
  test|tests)
    case "${2:-}" in
      engine) run_engine_tests ;;
      "")     run_tests ;;
      *)      run_tests "${@:2}" ;;
    esac
    ;;
  build-web|webbuild) build_web ;;
  serve)   serve_frontend ;;
  build)   container_build ;;
  up)      container_up ;;
  down)    container_down ;;
  ps)      container_ps ;;
  clogs)   container_clogs ;;
  nas)
    case "${2:-}" in
      deploy) nas_deploy ;;
      up)     nas_up ;;
      down)   nas_down ;;
      logs)   nas_logs "${3:-}" ;;
      ps)     nas_ps ;;
      shell)  nas_shell "${3:-}" ;;
      *) err "unknown nas command '${2:-}' (use: deploy | up | down | logs | ps | shell)"; exit 1 ;;
    esac
    ;;
  ""|-h|--help|help)
    sed -n '2,44p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    ;;
  *)
    err "unknown action '$ACTION'"
    echo "Run './dev.sh help' for usage." >&2
    exit 1
    ;;
esac
