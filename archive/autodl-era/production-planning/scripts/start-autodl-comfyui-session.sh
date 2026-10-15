#!/usr/bin/env bash
set -Eeuo pipefail

SSH_ALIAS="${AUTODL_SSH_ALIAS:-autodl-comfyui}"
LOCAL_PORT="${COMFYUI_LOCAL_PORT:-18188}"
STATE_DIR="${TMPDIR:-/tmp}/openmontage-autodl-comfyui"
PID_FILE="$STATE_DIR/tunnel.pid"
LOG_FILE="$STATE_DIR/tunnel.log"
SERVER_URL="http://127.0.0.1:${LOCAL_PORT}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$STATE_DIR"
"$SCRIPT_DIR/ensure-autodl-comfyui-remote.sh"

if [[ -s "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  if curl --fail --silent --max-time 5 "$SERVER_URL/system_stats" >/dev/null; then
    printf 'ComfyUI tunnel is already healthy: %s\n' "$SERVER_URL"
    exit 0
  fi
  printf '%s\n' 'A recorded tunnel exists but is unhealthy; run stop-autodl-comfyui-session.sh before retrying.' >&2
  exit 1
fi
rm -f "$PID_FILE"

nohup ssh \
  -N \
  -o ExitOnForwardFailure=yes \
  -o ConnectTimeout=10 \
  -o ServerAliveInterval=15 \
  -o ServerAliveCountMax=4 \
  -o TCPKeepAlive=yes \
  -o IPQoS=none \
  -L "${LOCAL_PORT}:127.0.0.1:8188" \
  "$SSH_ALIAS" >"$LOG_FILE" 2>&1 </dev/null &
tunnel_pid=$!
printf '%s\n' "$tunnel_pid" >"$PID_FILE"

for _ in {1..20}; do
  if ! kill -0 "$tunnel_pid" 2>/dev/null; then
    printf '%s\n' 'AutoDL tunnel exited early. Recent log:' >&2
    tail -80 "$LOG_FILE" >&2 || true
    rm -f "$PID_FILE"
    exit 1
  fi
  if curl --fail --silent --max-time 3 "$SERVER_URL/system_stats" >/dev/null 2>&1; then
    for _ in {1..3}; do
      sleep 1
      curl --fail --silent --max-time 5 "$SERVER_URL/system_stats" >/dev/null
    done
    printf 'Remote ComfyUI is detached; local tunnel is healthy: %s\n' "$SERVER_URL"
    printf '%s\n' 'For automated generation, prefer with-autodl-comfyui-tunnel.sh so the tunnel and command share one lifecycle.'
    exit 0
  fi
  sleep 1
done

printf '%s\n' 'Local tunnel did not become healthy within 20 seconds. Recent log:' >&2
tail -80 "$LOG_FILE" >&2 || true
kill "$tunnel_pid" 2>/dev/null || true
rm -f "$PID_FILE"
exit 1
