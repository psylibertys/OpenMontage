#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${MODEL_ROOT:-/root/autodl-tmp/comfyui-models}"
STATE_ROOT="${STATE_ROOT:-/root/autodl-tmp/comfyui-runtime/model-download}"
MIN_FREE_BYTES="${MIN_FREE_BYTES:-53687091200}"
MODEL_HASH_MODE="${MODEL_HASH_MODE:-size}"
TOKEN_FILE="${HF_TOKEN_FILE:-/root/.cache/huggingface/token}"
MANIFEST="$STATE_ROOT/full-suite-models.tsv"
STATUS="$STATE_ROOT/status.env"
LOG="$STATE_ROOT/download.log"
PID_FILE="$STATE_ROOT/download.pid"

mkdir -p "$STATE_ROOT"
exec > >(tee -a "$LOG") 2>&1
printf '%s\n' "$$" > "$PID_FILE"

current="initializing"
completed=0
skipped=0
failed=0
checksum_pid=""
checksum_target=""

entries() {
  cat <<'EOF'
black-forest-labs/FLUX.2-klein-9b-kv-fp8|flux-2-klein-9b-kv-fp8.safetensors|diffusion_models/flux2/flux-2-klein-9b-kv-fp8.safetensors|9818935984
Comfy-Org/flux2-klein-9B|split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors|text_encoders/qwen_3_8b_fp8mixed.safetensors|8664848742
Comfy-Org/flux2-klein-9B|split_files/vae/flux2-vae.safetensors|vae/flux2-vae.safetensors|336211292
Kijai/WanVideo_comfy_fp8_scaled|I2V/Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors|diffusion_models/wan2.1/Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors|16643349018
Kijai/WanVideo_comfy|Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors|loras/wan2.2/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors|738005744
Comfy-Org/Wan_2.1_ComfyUI_repackaged|split_files/model_patches/wan2.1_infiniteTalk_single_fp16.safetensors|model_patches/wan2.1_infiniteTalk_single_fp16.safetensors|5125258232
Kijai/wav2vec2_safetensors|wav2vec2-chinese-base_fp16.safetensors|audio_encoders/wav2vec2-chinese-base_fp16.safetensors|190115368
Kijai/WanVideo_comfy|Wan2_1_VAE_bf16.safetensors|vae/Wan2_1_VAE_bf16.safetensors|253806278
Kijai/WanVideo_comfy_fp8_scaled|Wan22Animate/Wan2_2-Animate-14B_fp8_scaled_e4m3fn_KJ_v2.safetensors|diffusion_models/wan2.2/Wan2_2-Animate-14B_fp8_scaled_e4m3fn_KJ_v2.safetensors|17317143060
Kijai/WanVideo_comfy_fp8_scaled|SCAIL/Wan21-14B-SCAIL-preview_fp8_e4m3fn_scaled_KJ.safetensors|diffusion_models/scail/Wan21-14B-SCAIL-preview_fp8_e4m3fn_scaled_KJ.safetensors|16401525232
Kijai/WanVideo_comfy|Wan21_Uni3C_controlnet_fp16.safetensors|controlnet/Wan21_Uni3C_controlnet_fp16.safetensors|1997314376
Kijai/WanVideo_comfy|umt5-xxl-enc-fp8_e4m3fn.safetensors|text_encoders/umt5-xxl-enc-fp8_e4m3fn.safetensors|6731333792
Comfy-Org/Wan_2.1_ComfyUI_repackaged|split_files/clip_vision/clip_vision_h.safetensors|clip_vision/clip_vision_h.safetensors|1264219396
Kijai/WanVideo_comfy|LoRAs/Wan22_relight/WanAnimate_relight_lora_fp16.safetensors|loras/wan2.2/WanAnimate_relight_lora_fp16.safetensors|1436672440
Kijai/WanVideo_comfy|LoRAs/Wan22-Lightning/old/Wan2.2-Lightning_I2V-A14B-4steps-lora_LOW_fp16.safetensors|loras/wan2.2/Wan2.2-Lightning_I2V-A14B-4steps-lora_LOW_fp16.safetensors|613561776
Kijai/WanVideo_comfy|Pusa/Wan21_PusaV1_LoRA_14B_rank512_bf16.safetensors|loras/wan2.2/Wan21_PusaV1_LoRA_14B_rank512_bf16.safetensors|4907437824
Kijai/WanVideo_comfy|LoRAs/Wan22_FunReward/Wan2.2-Fun-A14B-InP-LOW-HPS2.1_resized_dynamic_avg_rank_15_bf16.safetensors|loras/wan2.2/Wan2.2-Fun-A14B-InP-LOW-HPS2.1_resized_dynamic_avg_rank_15_bf16.safetensors|101752852
Kijai/WanVideo_comfy|FastWan/FastWan_T2V_14B_480p_lora_rank_64_bf16.safetensors|loras/wan2.2/FastWan_T2V_14B_480p_lora_rank_64_bf16.safetensors|630697104
pankjkkkkkk/sam3_pt|sam3.pt|sam3/sam3.pt|3450062241
Kijai/vitpose_comfy|onnx/vitpose_h_wholebody_model.onnx|detection/vitpose_h_wholebody_model.onnx|420252
Kijai/vitpose_comfy|onnx/vitpose_h_wholebody_data.bin|detection/vitpose_h_wholebody_data.bin|2548958740
Wan-AI/Wan2.2-Animate-14B|process_checkpoint/det/yolov10m.onnx|detection/yolov10m.onnx|61659339
EOF
}

write_status() {
  local state="$1"
  local free
  free="$(df -B1 --output=avail "$ROOT" | tail -1 | tr -d ' ')"
  {
    printf 'state=%q\n' "$state"
    printf 'pid=%q\n' "$$"
    printf 'updated_at=%q\n' "$(date -Iseconds)"
    printf 'current=%q\n' "$current"
    printf 'completed=%q\n' "$completed"
    printf 'skipped=%q\n' "$skipped"
    printf 'failed=%q\n' "$failed"
    printf 'free_bytes=%q\n' "$free"
  } > "$STATUS.tmp"
  mv -f "$STATUS.tmp" "$STATUS"
}

check_free() {
  local required="${1:-0}" free
  free="$(df -B1 --output=avail "$ROOT" | tail -1 | tr -d ' ')"
  if (( free - required < MIN_FREE_BYTES )); then
    printf '[STOP] download needs %s bytes; free space %s would cross safety floor %s\n' \
      "$required" "$free" "$MIN_FREE_BYTES"
    write_status stopped_low_space
    exit 75
  fi
}

finish_checksum() {
  if [[ -z "$checksum_pid" ]]; then
    return 0
  fi
  if wait "$checksum_pid"; then
    printf '[SHA256] %s\n' "$checksum_target"
  else
    printf '[FAIL] sha256 calculation failed: %s\n' "$checksum_target"
    failed=$((failed + 1))
  fi
  checksum_pid=""
  checksum_target=""
}

start_checksum() {
  local target="$1"
  if [[ "$MODEL_HASH_MODE" != "sha256" ]]; then
    printf 'size=%s verified_at=%s\n' "$(stat -c '%s' "$target")" "$(date -Iseconds)" \
      > "$target.verified"
    return 0
  fi
  finish_checksum
  checksum_target="$target"
  (
    sha256sum "$target" > "$target.sha256.tmp" &&
      mv -f "$target.sha256.tmp" "$target.sha256"
  ) &
  checksum_pid="$!"
}

verification_missing() {
  local target="$1"
  if [[ "$MODEL_HASH_MODE" == "sha256" ]]; then
    [[ ! -s "$target.sha256" ]]
  else
    [[ ! -s "$target.verified" ]]
  fi
}

download_one() {
  local repo="$1" repo_path="$2" relative="$3" expected="$4"
  local target="$ROOT/$relative" part="$ROOT/$relative.part"
  local official="https://huggingface.co/$repo/resolve/main/$repo_path?download=true"
  local mirror="https://hf-mirror.com/$repo/resolve/main/$repo_path?download=true"
  local size primary secondary auth=()

  current="$repo/$repo_path"
  write_status running
  mkdir -p "$(dirname "$target")"

  if [[ -f "$target" ]]; then
    size="$(stat -c '%s' "$target")"
    if [[ "$expected" == 0 || "$size" == "$expected" ]]; then
      printf '[SKIP] %s (%s bytes)\n' "$relative" "$size"
      if verification_missing "$target"; then
        start_checksum "$target"
      fi
      skipped=$((skipped + 1))
      return 0
    fi
    mv -f "$target" "$part"
  fi

  size=0
  [[ -f "$part" ]] && size="$(stat -c '%s' "$part")"
  if (( expected > size )); then
    check_free "$((expected - size))"
  else
    check_free 0
  fi

  if [[ -s "$TOKEN_FILE" ]]; then
    auth=(--header="Authorization: Bearer $(tr -d '\r\n' < "$TOKEN_FILE")")
  fi

  primary="$official"
  secondary="$mirror"
  if [[ "${PREFER_HF_MIRROR:-auto}" == "1" || ( "${PREFER_HF_MIRROR:-auto}" == "auto" && ! -s "$TOKEN_FILE" ) ]]; then
    primary="$mirror"
    secondary="$official"
  fi

  printf '[START] %s -> %s\n' "$current" "$relative"
  if ! aria2c --continue=true --file-allocation=none --auto-file-renaming=false \
      --allow-overwrite=true --max-tries=5 --retry-wait=5 --connect-timeout=20 \
      --timeout=120 --lowest-speed-limit=1K --max-connection-per-server=16 \
      --split=16 --min-split-size=1M --summary-interval=30 --console-log-level=warn \
      "${auth[@]}" --dir="$(dirname "$part")" --out="$(basename "$part")" "$primary"; then
    printf '[FALLBACK] primary source failed; trying secondary\n'
    if ! aria2c --continue=true --file-allocation=none --auto-file-renaming=false \
        --allow-overwrite=true --max-tries=8 --retry-wait=5 --connect-timeout=20 \
        --timeout=120 --lowest-speed-limit=1K --max-connection-per-server=16 \
        --split=16 --min-split-size=1M --summary-interval=30 --console-log-level=warn \
        --dir="$(dirname "$part")" --out="$(basename "$part")" "$secondary"; then
      printf '[FAIL] %s\n' "$current"
      failed=$((failed + 1))
      return 1
    fi
  fi

  size="$(stat -c '%s' "$part")"
  if [[ "$expected" != 0 && "$size" != "$expected" ]]; then
    printf '[FAIL] size mismatch %s: got %s expected %s\n' "$relative" "$size" "$expected"
    failed=$((failed + 1))
    return 1
  fi
  mv -f "$part" "$target"
  start_checksum "$target"
  completed=$((completed + 1))
  printf '[DONE] %s (%s bytes)\n' "$relative" "$size"
}

download_url() {
  local url="$1" fallback_url="$2" relative="$3" expected="$4"
  local target="$ROOT/$relative" part="$ROOT/$relative.part" size
  current="$url"
  write_status running
  mkdir -p "$(dirname "$target")"
  if [[ -f "$target" ]] && [[ "$(stat -c '%s' "$target")" == "$expected" ]]; then
    if verification_missing "$target"; then
      start_checksum "$target"
    fi
    skipped=$((skipped + 1))
    return 0
  fi
  size=0
  [[ -f "$part" ]] && size="$(stat -c '%s' "$part")"
  check_free "$((expected > size ? expected - size : 0))"
  if ! aria2c --continue=true --file-allocation=none --auto-file-renaming=false \
      --allow-overwrite=true --max-tries=5 --retry-wait=5 --connect-timeout=20 \
      --timeout=120 --lowest-speed-limit=1K --max-connection-per-server=8 \
      --split=8 --min-split-size=1M --console-log-level=warn \
      --dir="$(dirname "$part")" --out="$(basename "$part")" "$url"; then
    aria2c --continue=true --file-allocation=none --auto-file-renaming=false \
      --allow-overwrite=true --max-tries=8 --retry-wait=5 --connect-timeout=20 \
      --timeout=120 --lowest-speed-limit=1K --max-connection-per-server=8 \
      --split=8 --min-split-size=1M --console-log-level=warn \
      --dir="$(dirname "$part")" --out="$(basename "$part")" "$fallback_url" || {
        failed=$((failed + 1)); return 1;
      }
  fi
  size="$(stat -c '%s' "$part")"
  if [[ "$size" != "$expected" ]]; then
    printf '[FAIL] size mismatch %s: got %s expected %s\n' "$relative" "$size" "$expected"
    failed=$((failed + 1)); return 1
  fi
  mv -f "$part" "$target"
  start_checksum "$target"
  completed=$((completed + 1))
}

mkdir -p "$ROOT"
entries > "$MANIFEST"
trap 'write_status interrupted' INT TERM HUP
write_status running
while IFS='|' read -r repo repo_path relative expected; do
  [[ -n "$repo" ]] || continue
  download_one "$repo" "$repo_path" "$relative" "$expected" || true
done < "$MANIFEST"

download_url \
  "https://github.com/isarandi/nlf/releases/download/v0.3.2/nlf_l_multi_0.3.2.torchscript" \
  "https://gh-proxy.com/https://github.com/isarandi/nlf/releases/download/v0.3.2/nlf_l_multi_0.3.2.torchscript" \
  "nlf/nlf_l_multi_0.3.2.torchscript" \
  "493117974" || true

finish_checksum

current="finished"
if (( failed )); then
  write_status complete_with_errors
  exit 1
fi
write_status complete
printf '[COMPLETE] completed=%s skipped=%s\n' "$completed" "$skipped"
