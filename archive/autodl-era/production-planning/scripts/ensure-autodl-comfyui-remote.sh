#!/usr/bin/env bash
set -Eeuo pipefail

SSH_ALIAS="${AUTODL_SSH_ALIAS:-autodl-comfyui}"

# The OpenMontageCleanup middleware rejects uploads with 401 unless
# OPENMONTAGE_CLEANUP_TOKEN matches the local COMFYUI_CLEANUP_TOKEN. The env
# file is not persisted across instance resets, so (re)write it on every start.
CLEANUP_TOKEN="${COMFYUI_CLEANUP_TOKEN:-}"
if [[ -z "$CLEANUP_TOKEN" && -f "$(dirname "$0")/../../.env" ]]; then
  CLEANUP_TOKEN="$(grep -o '^COMFYUI_CLEANUP_TOKEN=..*' "$(dirname "$0")/../../.env" | head -1 | cut -d= -f2-)"
fi

ssh \
  -o ConnectTimeout=10 \
  -o ServerAliveInterval=15 \
  -o ServerAliveCountMax=4 \
  -o TCPKeepAlive=yes \
  -o IPQoS=none \
  "$SSH_ALIAS" "CLEANUP_TOKEN='$CLEANUP_TOKEN' bash -s" <<'REMOTE_SCRIPT'
set -Eeuo pipefail
install=/root/ComfyUI-Easy-Install
comfy="$install/ComfyUI"
python="$install/python_embeded/bin/python3"
runtime=/root/autodl-tmp/comfyui-runtime
env_file="$runtime/openmontage.env"
pidfile="$runtime/logs/openmontage-comfyui-detached.pid"
logfile="$runtime/logs/openmontage-comfyui-detached.log"
mkdir -p "$runtime/input" "$runtime/output" "$runtime/temp" "$runtime/logs"

if [[ -n "$CLEANUP_TOKEN" ]]; then
  touch "$env_file"
  chmod 600 "$env_file"
  grep -v "^OPENMONTAGE_CLEANUP_TOKEN=" "$env_file" >"$env_file.tmp" || true
  printf "OPENMONTAGE_CLEANUP_TOKEN=%s\n" "$CLEANUP_TOKEN" >>"$env_file.tmp"
  mv "$env_file.tmp" "$env_file"
fi

if ! command -v nvidia-smi >/dev/null 2>&1 || ! nvidia-smi -L >/dev/null 2>&1; then
  printf "%s\n" "GPU is unavailable; start this AutoDL instance in GPU mode." >&2
  exit 1
fi

if curl --fail --silent --max-time 3 http://127.0.0.1:8188/system_stats >/dev/null 2>&1; then
  printf "%s\n" "Remote ComfyUI is already healthy and detached."
  exit 0
fi

if [[ -s "$pidfile" ]]; then
  old_pid=$(cat "$pidfile")
  if kill -0 "$old_pid" 2>/dev/null; then
    kill "$old_pid"
    for _ in {1..20}; do
      kill -0 "$old_pid" 2>/dev/null || break
      sleep 0.25
    done
  fi
fi

if [[ -s "$env_file" ]]; then
  set -a
  source "$env_file"
  set +a
fi
cd "$comfy"
nohup "$python" main.py \
  --listen 127.0.0.1 \
  --port 8188 \
  --input-directory "$runtime/input" \
  --output-directory "$runtime/output" \
  --temp-directory "$runtime/temp" \
  >"$logfile" 2>&1 </dev/null &
printf "%s\n" "$!" >"$pidfile"

for _ in {1..60}; do
  pid=$(cat "$pidfile")
  if ! kill -0 "$pid" 2>/dev/null; then
    printf "%s\n" "Detached ComfyUI exited during startup. Recent log:" >&2
    tail -80 "$logfile" >&2 || true
    exit 1
  fi
  if curl --fail --silent --max-time 3 http://127.0.0.1:8188/system_stats >/dev/null 2>&1; then
    printf "%s\n" "Remote detached ComfyUI is healthy."
    exit 0
  fi
  sleep 2
done

printf "%s\n" "Detached ComfyUI did not become healthy within 120 seconds. Recent log:" >&2
tail -80 "$logfile" >&2 || true
exit 1
REMOTE_SCRIPT
