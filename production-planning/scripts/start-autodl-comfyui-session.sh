#!/usr/bin/env bash
set -Eeuo pipefail

SSH_ALIAS="${AUTODL_SSH_ALIAS:-autodl-comfyui}"
LOCAL_PORT="${COMFYUI_LOCAL_PORT:-18188}"
STATE_DIR="${TMPDIR:-/tmp}/openmontage-autodl-comfyui"
PID_FILE="$STATE_DIR/session.pid"
LOG_FILE="$STATE_DIR/session.log"
SERVER_URL="http://127.0.0.1:${LOCAL_PORT}"

mkdir -p "$STATE_DIR"

if [[ -s "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  if curl --fail --silent --max-time 5 "$SERVER_URL/system_stats" >/dev/null; then
    printf 'ComfyUI session is already healthy: %s\n' "$SERVER_URL"
    exit 0
  fi
  printf 'A prior session process exists but is not healthy; stop it before retrying.\n' >&2
  exit 1
fi
rm -f "$PID_FILE"

remote_command=$(cat <<'REMOTE'
set -Eeuo pipefail
install=/root/ComfyUI-Easy-Install
comfy="$install/ComfyUI"
python="$install/python_embeded/bin/python3"
runtime=/root/autodl-tmp/comfyui-runtime
env_file="$runtime/openmontage.env"
mkdir -p "$runtime/input" "$runtime/output" "$runtime/temp" "$runtime/logs"
if ! command -v nvidia-smi >/dev/null 2>&1 || ! nvidia-smi -L >/dev/null 2>&1; then
  printf '%s\n' 'GPU is unavailable; start this AutoDL instance in GPU mode.' >&2
  exit 1
fi
if [[ -s "$env_file" ]]; then
  set -a
  source "$env_file"
  set +a
fi
cd "$comfy"
exec "$python" main.py \
  --listen 127.0.0.1 \
  --port 8188 \
  --input-directory "$runtime/input" \
  --output-directory "$runtime/output" \
  --temp-directory "$runtime/temp"
REMOTE
)

nohup ssh \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -L "${LOCAL_PORT}:127.0.0.1:8188" \
  "$SSH_ALIAS" \
  "$remote_command" >"$LOG_FILE" 2>&1 &
session_pid=$!
printf '%s\n' "$session_pid" > "$PID_FILE"

for _ in {1..60}; do
  if ! kill -0 "$session_pid" 2>/dev/null; then
    printf 'ComfyUI SSH session exited early. Recent log:\n' >&2
    tail -80 "$LOG_FILE" >&2 || true
    rm -f "$PID_FILE"
    exit 1
  fi
  if curl --fail --silent --max-time 3 "$SERVER_URL/system_stats" >/dev/null; then
    printf 'ComfyUI is healthy: %s\n' "$SERVER_URL"
    printf 'Use: export COMFYUI_SERVER_URL=%s\n' "$SERVER_URL"
    exit 0
  fi
  sleep 2
done

printf 'ComfyUI did not become healthy within 120 seconds. Recent log:\n' >&2
tail -80 "$LOG_FILE" >&2 || true
kill "$session_pid" 2>/dev/null || true
rm -f "$PID_FILE"
exit 1
