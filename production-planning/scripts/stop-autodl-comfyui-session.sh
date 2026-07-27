#!/usr/bin/env bash
set -Eeuo pipefail

STATE_DIR="${TMPDIR:-/tmp}/openmontage-autodl-comfyui"
PID_FILE="$STATE_DIR/session.pid"

if [[ ! -s "$PID_FILE" ]]; then
  printf '%s\n' 'No local ComfyUI SSH session is recorded.'
  exit 0
fi

pid="$(cat "$PID_FILE")"
if kill -0 "$pid" 2>/dev/null; then
  kill "$pid"
  for _ in {1..20}; do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.25
  done
fi
rm -f "$PID_FILE"
printf '%s\n' 'Local ComfyUI SSH session stopped.'
