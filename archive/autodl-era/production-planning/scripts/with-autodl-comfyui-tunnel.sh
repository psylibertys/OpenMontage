#!/usr/bin/env bash
set -Eeuo pipefail

SSH_ALIAS="${AUTODL_SSH_ALIAS:-autodl-comfyui}"
LOCAL_PORT="${COMFYUI_LOCAL_PORT:-18188}"
SERVER_URL="http://127.0.0.1:${LOCAL_PORT}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${1:-}" == "--" ]]; then
  shift
fi
if [[ "$#" -eq 0 ]]; then
  printf 'Usage: %s -- <command> [args...]\n' "$0" >&2
  exit 2
fi

"$SCRIPT_DIR/ensure-autodl-comfyui-remote.sh"

tunnel_pid=""
cleanup() {
  if [[ -n "$tunnel_pid" ]]; then
    kill "$tunnel_pid" 2>/dev/null || true
    wait "$tunnel_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if ! curl --fail --silent --max-time 3 "$SERVER_URL/system_stats" >/dev/null 2>&1; then
  ssh \
    -N \
    -o ExitOnForwardFailure=yes \
    -o ConnectTimeout=10 \
    -o ServerAliveInterval=15 \
    -o ServerAliveCountMax=4 \
    -o TCPKeepAlive=yes \
    -o IPQoS=none \
    -L "${LOCAL_PORT}:127.0.0.1:8188" \
    "$SSH_ALIAS" &
  tunnel_pid=$!
fi

for _ in {1..20}; do
  if curl --fail --silent --max-time 3 "$SERVER_URL/system_stats" >/dev/null 2>&1; then
    break
  fi
  if [[ -n "$tunnel_pid" ]] && ! kill -0 "$tunnel_pid" 2>/dev/null; then
    printf '%s\n' 'AutoDL tunnel exited before becoming healthy. Check the current SSH host/port and any local proxy DIRECT rule.' >&2
    exit 1
  fi
  sleep 1
done

for _ in {1..3}; do
  curl --fail --silent --max-time 5 "$SERVER_URL/system_stats" >/dev/null
  sleep 1
done

export COMFYUI_SERVER_URL="$SERVER_URL"
"$@"
