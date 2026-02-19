#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PID=""
FRONTEND_PID=""

kill_tree() {
  local pid="${1:-}"
  if [[ -z "${pid}" ]]; then
    return
  fi

  # Terminate descendants first (Flask debug reloader / Vite subprocesses), then parent.
  local child=""
  while read -r child; do
    if [[ -n "${child}" ]]; then
      kill_tree "${child}"
    fi
  done < <(pgrep -P "${pid}" 2>/dev/null || true)

  kill "${pid}" 2>/dev/null || true
}

is_port_in_use() {
  local port="${1}"
  lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
}

cleanup() {
  trap - INT TERM HUP EXIT

  echo "[dev_up] Shutdown started..."

  if [[ -n "${BACKEND_PID}" ]]; then
    echo "[dev_up] Terminating backend process tree (pid=${BACKEND_PID})"
    kill_tree "${BACKEND_PID}"
  fi

  if [[ -n "${FRONTEND_PID}" ]]; then
    echo "[dev_up] Terminating frontend process tree (pid=${FRONTEND_PID})"
    kill_tree "${FRONTEND_PID}"
  fi

  # Fallback: ensure listeners started by this script are torn down.
  echo "[dev_up] Enforcing port cleanup for 8080 and 5173"
  lsof -ti tcp:8080 | xargs kill -TERM 2>/dev/null || true
  lsof -ti tcp:5173 | xargs kill -TERM 2>/dev/null || true
  sleep 1
  lsof -ti tcp:8080 | xargs kill -KILL 2>/dev/null || true
  lsof -ti tcp:5173 | xargs kill -KILL 2>/dev/null || true

  local backend_ok="yes"
  local frontend_ok="yes"
  if lsof -nP -iTCP:8080 -sTCP:LISTEN >/dev/null 2>&1; then
    backend_ok="no"
  fi
  if lsof -nP -iTCP:5173 -sTCP:LISTEN >/dev/null 2>&1; then
    frontend_ok="no"
  fi

  if [[ "${backend_ok}" == "yes" && "${frontend_ok}" == "yes" ]]; then
    echo "[dev_up] Shutdown complete: backend/frontend listeners are stopped."
  else
    echo "[dev_up] Shutdown incomplete: backend_stopped=${backend_ok}, frontend_stopped=${frontend_ok}"
    if [[ "${backend_ok}" == "no" ]]; then
      lsof -nP -iTCP:8080 -sTCP:LISTEN || true
    fi
    if [[ "${frontend_ok}" == "no" ]]; then
      lsof -nP -iTCP:5173 -sTCP:LISTEN || true
    fi
  fi

  wait 2>/dev/null || true
}

on_signal() {
  echo "[dev_up] Received interrupt signal; shutting down..."
  cleanup
  exit 130
}

trap on_signal INT TERM HUP
trap cleanup EXIT

if [[ ! -d "${ROOT_DIR}/.venv" ]]; then
  echo "Missing virtualenv at ${ROOT_DIR}/.venv"
  echo "Create it with: uv venv --python 3.14 .venv && source .venv/bin/activate && uv pip install -r requirements_dev.txt"
  exit 1
fi

if ! command -v bun >/dev/null 2>&1; then
  echo "bun is not installed or not on PATH"
  exit 1
fi

if is_port_in_use 8080; then
  echo "Port 8080 is already in use. Stop the existing backend first."
  echo "Hint: lsof -nP -iTCP:8080 -sTCP:LISTEN"
  exit 1
fi

if is_port_in_use 5173; then
  echo "Port 5173 is already in use. Stop the existing frontend first."
  echo "Hint: lsof -nP -iTCP:5173 -sTCP:LISTEN"
  exit 1
fi

(
  cd "${ROOT_DIR}"
  source .venv/bin/activate
  export FLASK_DEBUG=1
  python app.py
) &
BACKEND_PID=$!

echo "Backend started (pid=${BACKEND_PID}) on http://localhost:8080 (hot reload enabled)"

(
  cd "${ROOT_DIR}/frontend"
  bun run dev -- --port 5173 --strictPort
) &
FRONTEND_PID=$!

echo "Frontend started (pid=${FRONTEND_PID}) on http://localhost:5173"

echo "Press Ctrl+C to stop both services."

# macOS default bash (3.2) does not support `wait -n`.
# Poll both children and exit when either one exits.
while true; do
  if ! kill -0 "${BACKEND_PID}" 2>/dev/null; then
    wait "${BACKEND_PID}" 2>/dev/null || true
    break
  fi

  if ! kill -0 "${FRONTEND_PID}" 2>/dev/null; then
    wait "${FRONTEND_PID}" 2>/dev/null || true
    break
  fi

  sleep 1
done
