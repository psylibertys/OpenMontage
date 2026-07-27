#!/usr/bin/env bash
set -Eeuo pipefail

SSH_ALIAS="${AUTODL_SSH_ALIAS:-autodl-comfyui}"
LOCAL_PORT="${COMFYUI_LOCAL_PORT:-18188}"

printf 'Opening http://127.0.0.1:%s -> %s:127.0.0.1:8188\n' "$LOCAL_PORT" "$SSH_ALIAS"
exec ssh \
  -N \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -L "${LOCAL_PORT}:127.0.0.1:8188" \
  "$SSH_ALIAS"
