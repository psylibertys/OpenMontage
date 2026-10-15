#!/usr/bin/env bash
set -Eeuo pipefail

DATA_ROOT="/root/autodl-tmp"
INSTALL="/root/ComfyUI-Easy-Install"
COMFY="$INSTALL/ComfyUI"
PYTHON="$INSTALL/python_embeded/bin/python3"
MODEL_ROOT="$DATA_ROOT/comfyui-models"
RUNTIME_ROOT="$DATA_ROOT/comfyui-runtime"
PID_FILE="$RUNTIME_ROOT/logs/comfyui.pid"
LOG_FILE="$RUNTIME_ROOT/logs/comfyui-runtime.log"
HOST="127.0.0.1"
PORT="8188"
ENV_FILE="$RUNTIME_ROOT/openmontage.env"

is_running() {
  [[ -s "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

prepare_data_dirs() {
  mkdir -p \
    "$MODEL_ROOT/diffusion_models/z-image" \
    "$MODEL_ROOT/diffusion_models/krea2" \
    "$MODEL_ROOT/diffusion_models/wan2.2" \
    "$MODEL_ROOT/text_encoders" \
    "$MODEL_ROOT/vae" \
    "$MODEL_ROOT/SEEDVR2" \
    "$MODEL_ROOT/qwen-tts" \
    "$RUNTIME_ROOT/input" \
    "$RUNTIME_ROOT/output" \
    "$RUNTIME_ROOT/temp" \
    "$RUNTIME_ROOT/logs"
}

start() {
  if is_running; then
    printf 'ComfyUI is already running (pid=%s)\n' "$(cat "$PID_FILE")"
    return 0
  fi
  prepare_data_dirs
  if [[ -s "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
  fi
  cd "$COMFY"
  local -a runtime_args=(
    --input-directory "$RUNTIME_ROOT/input"
    --output-directory "$RUNTIME_ROOT/output"
    --temp-directory "$RUNTIME_ROOT/temp"
  )
  if ! command -v nvidia-smi >/dev/null 2>&1 || ! nvidia-smi -L >/dev/null 2>&1; then
    runtime_args+=(--cpu)
  fi
  nohup "$PYTHON" main.py --listen "$HOST" --port "$PORT" "${runtime_args[@]}" >>"$LOG_FILE" 2>&1 &
  printf '%s\n' "$!" > "$PID_FILE"
  sleep 5
  if ! is_running; then
    printf '%s\n' 'ComfyUI failed to start; recent log follows:' >&2
    tail -80 "$LOG_FILE" >&2
    return 1
  fi
  printf 'ComfyUI started (pid=%s, %s:%s)\n' "$(cat "$PID_FILE")" "$HOST" "$PORT"
}

foreground() {
  prepare_data_dirs
  if [[ -s "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
  fi
  cd "$COMFY"
  printf '%s\n' "$$" > "$PID_FILE"
  exec "$PYTHON" main.py \
    --listen "$HOST" \
    --port "$PORT" \
    --input-directory "$RUNTIME_ROOT/input" \
    --output-directory "$RUNTIME_ROOT/output" \
    --temp-directory "$RUNTIME_ROOT/temp"
}

stop() {
  if ! is_running; then
    rm -f "$PID_FILE"
    printf '%s\n' 'ComfyUI is not running'
    return 0
  fi
  local pid
  pid="$(cat "$PID_FILE")"
  kill "$pid"
  for _ in {1..20}; do
    kill -0 "$pid" 2>/dev/null || break
    sleep 1
  done
  if kill -0 "$pid" 2>/dev/null; then
    kill -KILL "$pid"
  fi
  rm -f "$PID_FILE"
  printf '%s\n' 'ComfyUI stopped'
}

status() {
  if is_running; then
    printf 'running pid=%s url=http://%s:%s\n' "$(cat "$PID_FILE")" "$HOST" "$PORT"
  else
    printf '%s\n' 'stopped'
    return 1
  fi
}

health() {
  curl --fail --silent --show-error --max-time 10 "http://$HOST:$PORT/system_stats"
  printf '\n'
}

case "${1:-}" in
  prepare) prepare_data_dirs; printf '%s\n' 'ComfyUI data directories are ready' ;;
  start) start ;;
  foreground) foreground ;;
  stop) stop ;;
  restart) stop; start ;;
  status) status ;;
  health) health ;;
  logs) tail -n "${2:-120}" "$LOG_FILE" ;;
  *) printf 'usage: %s {prepare|start|foreground|stop|restart|status|health|logs [lines]}\n' "$0" >&2; exit 2 ;;
esac
