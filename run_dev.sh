#!/usr/bin/env bash
#
# Starts the dashboard: the server (FastAPI) and the website (Vite) together.
#
#   ./run_dev.sh              start both and show their logs; Ctrl-C stops both
#   ./run_dev.sh --reset-db   delete the database and load it again first
#                             (this also deletes every user account, then
#                             creates the demo platform admin again)
#   ./run_dev.sh --help       show this message
#
# Then open http://localhost:5173 (use localhost, not 127.0.0.1).
#
# Lines 2-11 above are printed by --help, so keep that text within them.
#
# This always runs from the main project folder, wherever you start it from.
# The server is loaded as `backend.app.main`, which only works from there -
# anywhere else it fails with ModuleNotFoundError.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# Load your private settings from .env, if you have one (git ignores it).
# Without it, the server uses a fixed development key and says so below.
# It's loaded here so the database loader and the server both get it. A
# broken .env stops the script straight away (because of `set -e`) - a clear
# stop is better than half your settings loaded.
if [[ -f "$ROOT/.env" ]]; then
  set -a; source "$ROOT/.env"; set +a
fi

BACKEND_PORT=8000
FRONTEND_PORT=5173
PY="$ROOT/.venv/bin/python"
UVICORN="$ROOT/.venv/bin/uvicorn"
LOG_DIR="$ROOT/.run-logs"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

RESET_DB=0
for arg in "$@"; do
  case "$arg" in
    --reset-db) RESET_DB=1 ;;
    -h|--help) sed -n '2,11p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

say()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m warn\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31merror\033[0m %s\n' "$*" >&2; exit 1; }

port_busy() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

# macOS doesn't come with `timeout`, so just keep checking instead.
wait_for_url() {
  local url=$1 tries=$2
  for _ in $(seq 1 "$tries"); do
    curl -sf "$url" >/dev/null 2>&1 && return 0
    sleep 0.5
  done
  return 1
}

# ---------------------------------------------------------------- checks

[[ -x "$UVICORN" ]] || die "$UVICORN not found. Create the venv and install backend/requirements.txt."

if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
  say "frontend dependencies missing - running npm install"
  (cd "$ROOT/frontend" && npm install)
fi

if [[ ! -f "$ROOT/serving/output/orders_seed.json" ]]; then
  die "serving/output/orders_seed.json is missing. Generate it first:
       $PY serving/export_seed.py
     (this retrains GraphSAGE and rescores the test edges - it takes a while)"
fi

if [[ $RESET_DB -eq 1 ]]; then
  say "resetting the database (wipes rules, overrides, logged actions and user accounts)"
  "$PY" -m backend.scripts.seed_db --force
elif [[ ! -f "$ROOT/backend/orders.db" ]]; then
  say "no database yet - seeding it"
  "$PY" -m backend.scripts.seed_db
fi

# An old copy of the server can keep the port while the new one quietly fails
# to start. The page then loads old code, with no error shown anywhere. That's
# the most confusing problem you can hit here, so always clear old copies first.
if pgrep -f "uvicorn backend.app.main" >/dev/null 2>&1 \
   || pgrep -f "$ROOT/frontend/node_modules/.bin/vite" >/dev/null 2>&1; then
  say "stopping servers left over from a previous run"
  pkill -f "uvicorn backend.app.main" 2>/dev/null || true
  pkill -f "$ROOT/frontend/node_modules/.bin/vite" 2>/dev/null || true
  sleep 2
fi

port_busy "$BACKEND_PORT" && die "port $BACKEND_PORT is held by something else - free it and retry"

mkdir -p "$LOG_DIR"
: > "$BACKEND_LOG"
: > "$FRONTEND_LOG"

# ---------------------------------------------------------------- shutdown

cleanup() {
  trap - INT TERM EXIT
  echo
  say "shutting down"
  [[ -n "${TAIL_PID:-}" ]] && kill "$TAIL_PID" 2>/dev/null || true
  [[ -n "${BACKEND_PID:-}" ]]  && kill "$BACKEND_PID"  2>/dev/null || true
  [[ -n "${FRONTEND_PID:-}" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
  sleep 1
  # Make extra sure. uvicorn --reload starts a second process that does the
  # real work, and either server may still be using its port. Only stop
  # processes matching the exact commands this script started, so nothing
  # else is touched.
  pkill -f "uvicorn backend.app.main" 2>/dev/null || true
  pkill -f "$ROOT/frontend/node_modules/.bin/vite" 2>/dev/null || true
  wait 2>/dev/null || true
  say "stopped. logs kept in .run-logs/"
}
trap cleanup INT TERM EXIT

# ---------------------------------------------------------------- start

if [[ -z "${RETURNS_DASHBOARD_JWT_SECRET:-}" ]]; then
  warn "RETURNS_DASHBOARD_JWT_SECRET is not set - using the built-in development signing key."
  warn "Fine locally; anyone with this repo could forge a session against a real deployment."
fi

say "starting backend on http://127.0.0.1:$BACKEND_PORT"
"$UVICORN" backend.app.main:app --reload --port "$BACKEND_PORT" >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

if ! wait_for_url "http://127.0.0.1:$BACKEND_PORT/api/health" 60; then
  echo; warn "backend did not come up - last lines of $BACKEND_LOG:"; tail -20 "$BACKEND_LOG"
  exit 1
fi
say "backend ready"

if port_busy "$FRONTEND_PORT"; then
  warn "port $FRONTEND_PORT is already in use - Vite will pick another one (check the log)"
fi

say "starting frontend"
# `npm run dev` just runs `vite`, but going through npm adds two extra
# processes (sh, then npm) between this script and the server. The process ID
# saved here would then not be the server's, and Ctrl-C would leave Vite
# running. Starting vite directly makes FRONTEND_PID the real server.
(cd "$ROOT/frontend" && exec node_modules/.bin/vite) >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

# Vite only listens on IPv6 here, so localhost works but 127.0.0.1 doesn't.
if ! wait_for_url "http://localhost:$FRONTEND_PORT" 60; then
  echo; warn "frontend did not come up - last lines of $FRONTEND_LOG:"; tail -20 "$FRONTEND_LOG"
  exit 1
fi

# Read from the Python settings rather than written out again here, so this
# message, the account that gets created and the login page always agree.
DEMO_CREDS="$("$PY" -c 'from backend.app.constants import DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD; print(f"{DEMO_ADMIN_EMAIL} / {DEMO_ADMIN_PASSWORD}")' 2>/dev/null || echo "see the sign-in page")"

cat <<EOF

  Dashboard   http://localhost:$FRONTEND_PORT      <- open this
  API         http://127.0.0.1:$BACKEND_PORT/api/health
  API docs    http://127.0.0.1:$BACKEND_PORT/docs

  Sign in as  $DEMO_CREDS
              (platform admin, also printed on the sign-in page; or create a
              tenant-scoped account with "Sign up")

  Use localhost for the dashboard, not 127.0.0.1 - Vite binds IPv6 only.
  Ctrl-C stops both.

EOF

# Show both logs, each labelled with its file name, until Ctrl-C.
tail -f "$BACKEND_LOG" "$FRONTEND_LOG" &
TAIL_PID=$!
# Take it off bash's job list. Otherwise bash prints "Terminated: 15" when you
# stop the script, which looks like a crash rather than a normal stop.
disown "$TAIL_PID" 2>/dev/null || true
wait "$BACKEND_PID" "$FRONTEND_PID"
