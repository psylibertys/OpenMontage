#!/usr/bin/env bash
set -uo pipefail

ROOT="${MODEL_LIBRARY_ROOT:-/media/data/ai-models/comfyui}"
MODELS="${MODEL_DIRECTORY:-$ROOT/models}"
MANIFESTS="${MODEL_MANIFEST_DIRECTORY:-$ROOT/manifests}"
CHECKSUMS="${MODEL_CHECKSUM_DIRECTORY:-$ROOT/checksums}"
FILE_MANIFEST="$MANIFESTS/first-batch-model-files.tsv"
STATUS_FILE="$MANIFESTS/first-batch-download.status"
PID_FILE="$MANIFESTS/first-batch-download.pid"

mkdir -p "$MANIFESTS" "$CHECKSUMS" \
  "$MODELS/qwen-tts" \
  "$MODELS/diffusion_models/z-image" \
  "$MODELS/diffusion_models/krea2" \
  "$MODELS/diffusion_models/wan2.2" \
  "$MODELS/text_encoders" "$MODELS/vae" "$MODELS/SEEDVR2"

printf '%s\n' "$$" > "$PID_FILE"

completed=0
skipped=0
failed=0
current="initializing"
prefer_mirror=0
current_part=""
current_expected=0
current_source="none"

write_status() {
  local state="$1"
  local tmp="$STATUS_FILE.tmp.$$"
  local current_bytes=0
  if [[ -n "$current_part" && -f "$current_part" ]]; then
    current_bytes="$(stat -c '%s' "$current_part" 2>/dev/null || printf 0)"
  fi
  {
    printf 'state=%s\n' "$state"
    printf 'pid=%s\n' "$$"
    printf 'updated_at=%s\n' "$(date -Iseconds)"
    printf 'current=%s\n' "$current"
    printf 'current_source=%s\n' "$current_source"
    printf 'current_downloaded_bytes=%s\n' "$current_bytes"
    printf 'current_expected_bytes=%s\n' "$current_expected"
    printf 'completed=%s\n' "$completed"
    printf 'skipped=%s\n' "$skipped"
    printf 'failed=%s\n' "$failed"
    printf 'expected_total_bytes=%s\n' "77295972275"
  } > "$tmp"
  mv -f "$tmp" "$STATUS_FILE"
}

handle_interrupt() {
  write_status interrupted
  printf '[INTERRUPTED] signal received at %s; partial file retained for resume\n' "$(date -Iseconds)"
  exit 130
}

trap handle_interrupt INT TERM HUP

safe_name() {
  printf '%s' "$1" | tr '/ ' '__' | tr -cd 'A-Za-z0-9._-'
}

record_checksum() {
  local target="$1"
  local relative="${target#"$ROOT"/}"
  local digest checksum_file
  digest="$(sha256sum "$target" | awk '{print $1}')"
  checksum_file="$CHECKSUMS/$(safe_name "$relative").sha256"
  printf '%s  %s\n' "$digest" "$relative" > "$checksum_file"
}

download_one() {
  local repo="$1"
  local repo_path="$2"
  local target="$3"
  local expected="$4"
  local label="${repo}/${repo_path}"
  local part="${target}.part"
  local actual=0
  local official="https://huggingface.co/${repo}/resolve/main/${repo_path}?download=true"
  local mirror="https://hf-mirror.com/${repo}/resolve/main/${repo_path}?download=true"

  fetch_url() {
    local url="$1"
    if command -v aria2c >/dev/null 2>&1 && (( expected >= 50000000 )); then
      aria2c --continue=true --file-allocation=none --auto-file-renaming=false \
        --allow-overwrite=true --max-tries=8 --retry-wait=5 \
        --connect-timeout=20 --timeout=120 --lowest-speed-limit=1K \
        --max-connection-per-server=16 --split=16 --min-split-size=1M \
        --summary-interval=30 --console-log-level=warn \
        --dir="$(dirname "$part")" --out="$(basename "$part")" "$url"
    else
      curl -fL --retry 8 --retry-all-errors --retry-delay 5 \
        --connect-timeout 20 --speed-limit 1024 --speed-time 120 \
        -C - -o "$part" "$url"
    fi
  }

  current="$label"
  current_part="$part"
  current_expected="$expected"
  current_source="checking"
  write_status running
  mkdir -p "$(dirname "$target")"

  if [[ -f "$target" ]]; then
    actual="$(stat -c '%s' "$target")"
    if [[ "$actual" == "$expected" ]]; then
      printf '[SKIP] %s already complete (%s bytes)\n' "$label" "$actual"
      record_checksum "$target"
      skipped=$((skipped + 1))
      write_status running
      return 0
    fi
    if [[ ! -e "$part" ]]; then
      printf '[RESUME] moving incomplete target to %s (%s/%s bytes)\n' "$part" "$actual" "$expected"
      mv "$target" "$part"
    else
      printf '[WARN] incomplete target and part both exist; preserving target, continuing part\n'
    fi
  fi

  if [[ -f "$part" ]]; then
    actual="$(stat -c '%s' "$part")"
    if (( actual > expected )); then
      local oversized="${part}.oversized.$(date +%Y%m%dT%H%M%S)"
      printf '[WARN] oversized partial preserved as %s\n' "$oversized"
      mv "$part" "$oversized"
    fi
  fi

  printf '[START] %s -> %s (%s bytes)\n' "$label" "$target" "$expected"
  if (( prefer_mirror == 0 )); then
    current_source="huggingface.co"
    write_status running
    if fetch_url "$official"; then
      :
    else
      prefer_mirror=1
      printf '[FALLBACK] official endpoint failed; using hf-mirror for this and remaining files\n'
    fi
  fi

  if (( prefer_mirror == 1 )); then
    current_source="hf-mirror.com"
    write_status running
    if ! fetch_url "$mirror"; then
      printf '[FAIL] mirror transport failed for %s\n' "$label"
      failed=$((failed + 1))
      write_status running_with_errors
      return 1
    fi
  fi

  actual="$(stat -c '%s' "$part" 2>/dev/null || printf 0)"
  if [[ "$actual" != "$expected" ]]; then
    printf '[FAIL] size mismatch for %s: got %s, expected %s; partial retained\n' "$label" "$actual" "$expected"
    failed=$((failed + 1))
    write_status running_with_errors
    return 1
  fi

  mv -f "$part" "$target"
  record_checksum "$target"
  completed=$((completed + 1))
  printf '[DONE] %s (%s bytes)\n' "$label" "$expected"
  write_status running
  return 0
}

write_file_manifest() {
  local tmp="$FILE_MANIFEST.tmp.$$"
  printf 'official_repo\trepo_path\ttarget_relative_to_comfyui_root\texpected_bytes\n' > "$tmp"
  while IFS='|' read -r repo repo_path target expected; do
    [[ -n "$repo" ]] || continue
    printf '%s\t%s\t%s\t%s\n' "$repo" "$repo_path" "${target#"$ROOT"/}" "$expected" >> "$tmp"
  done < <(entries)
  mv -f "$tmp" "$FILE_MANIFEST"
}

entries() {
  cat <<ENTRIES
Qwen/Qwen3-TTS-Tokenizer-12Hz|.gitattributes|${MODELS}/qwen-tts/Qwen3-TTS-Tokenizer-12Hz/.gitattributes|1519
Qwen/Qwen3-TTS-Tokenizer-12Hz|README.md|${MODELS}/qwen-tts/Qwen3-TTS-Tokenizer-12Hz/README.md|3482
Qwen/Qwen3-TTS-Tokenizer-12Hz|config.json|${MODELS}/qwen-tts/Qwen3-TTS-Tokenizer-12Hz/config.json|2336
Qwen/Qwen3-TTS-Tokenizer-12Hz|configuration.json|${MODELS}/qwen-tts/Qwen3-TTS-Tokenizer-12Hz/configuration.json|76
Qwen/Qwen3-TTS-Tokenizer-12Hz|model.safetensors|${MODELS}/qwen-tts/Qwen3-TTS-Tokenizer-12Hz/model.safetensors|682293092
Qwen/Qwen3-TTS-Tokenizer-12Hz|preprocessor_config.json|${MODELS}/qwen-tts/Qwen3-TTS-Tokenizer-12Hz/preprocessor_config.json|234
Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice|.gitattributes|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-CustomVoice/.gitattributes|1519
Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice|README.md|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-CustomVoice/README.md|57846
Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice|config.json|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-CustomVoice/config.json|4908
Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice|generation_config.json|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-CustomVoice/generation_config.json|245
Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice|merges.txt|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-CustomVoice/merges.txt|1671839
Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice|model.safetensors|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-CustomVoice/model.safetensors|3833402552
Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice|preprocessor_config.json|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-CustomVoice/preprocessor_config.json|127
Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice|speech_tokenizer/config.json|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-CustomVoice/speech_tokenizer/config.json|2336
Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice|speech_tokenizer/configuration.json|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-CustomVoice/speech_tokenizer/configuration.json|76
Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice|speech_tokenizer/model.safetensors|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-CustomVoice/speech_tokenizer/model.safetensors|682293092
Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice|speech_tokenizer/preprocessor_config.json|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-CustomVoice/speech_tokenizer/preprocessor_config.json|234
Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice|tokenizer_config.json|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-CustomVoice/tokenizer_config.json|7344
Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice|vocab.json|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-CustomVoice/vocab.json|2776833
Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign|.gitattributes|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-VoiceDesign/.gitattributes|1519
Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign|README.md|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-VoiceDesign/README.md|3214
Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign|config.json|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-VoiceDesign/config.json|4421
Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign|generation_config.json|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-VoiceDesign/generation_config.json|245
Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign|merges.txt|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-VoiceDesign/merges.txt|1671839
Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign|model.safetensors|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-VoiceDesign/model.safetensors|3833402552
Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign|preprocessor_config.json|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-VoiceDesign/preprocessor_config.json|127
Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign|speech_tokenizer/config.json|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-VoiceDesign/speech_tokenizer/config.json|2336
Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign|speech_tokenizer/configuration.json|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-VoiceDesign/speech_tokenizer/configuration.json|76
Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign|speech_tokenizer/model.safetensors|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-VoiceDesign/speech_tokenizer/model.safetensors|682293092
Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign|speech_tokenizer/preprocessor_config.json|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-VoiceDesign/speech_tokenizer/preprocessor_config.json|234
Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign|tokenizer_config.json|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-VoiceDesign/tokenizer_config.json|7344
Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign|vocab.json|${MODELS}/qwen-tts/Qwen3-TTS-12Hz-1.7B-VoiceDesign/vocab.json|2776833
gguf-org/z-image-gguf|z-image-turbo-q4_k_s.gguf|${MODELS}/diffusion_models/z-image/z-image-turbo-q4_k_s.gguf|4335245376
Lockout/qwen3-4b-heretic-zimage|qwen-4b-zimage-heretic-q8.gguf|${MODELS}/text_encoders/qwen-4b-zimage-heretic-q8.gguf|4280404896
Comfy-Org/z_image_turbo|split_files/vae/ae.safetensors|${MODELS}/vae/ae.safetensors|335304388
Comfy-Org/Krea-2|diffusion_models/krea2_turbo_fp8_scaled.safetensors|${MODELS}/diffusion_models/krea2/krea2_turbo_fp8_scaled.safetensors|13141730784
Comfy-Org/Krea-2|text_encoders/qwen3vl_4b_fp8_scaled.safetensors|${MODELS}/text_encoders/qwen3vl_4b_fp8_scaled.safetensors|5242467968
Comfy-Org/Krea-2|vae/qwen_image_vae.safetensors|${MODELS}/vae/qwen_image_vae.safetensors|253806246
jayn7/WAN2.2-I2V_A14B-DISTILL-LIGHTX2V-4STEP-GGUF|high_noise/wan2.2_i2v_A14b_high_noise_lightx2v_4step-Q6_K.gguf|${MODELS}/diffusion_models/wan2.2/wan2.2_i2v_A14b_high_noise_lightx2v_4step-Q6_K.gguf|12013492864
jayn7/WAN2.2-I2V_A14B-DISTILL-LIGHTX2V-4STEP-GGUF|low_noise/wan2.2_i2v_A14b_low_noise_lightx2v_4step-Q6_K.gguf|${MODELS}/diffusion_models/wan2.2/wan2.2_i2v_A14b_low_noise_lightx2v_4step-Q6_K.gguf|12013492864
Comfy-Org/Wan_2.1_ComfyUI_repackaged|split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors|${MODELS}/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors|6735906897
Comfy-Org/Wan_2.1_ComfyUI_repackaged|split_files/vae/wan_2.1_vae.safetensors|${MODELS}/vae/wan_2.1_vae.safetensors|253815318
AInVFX/SeedVR2_comfyUI|seedvr2_ema_7b_fp8_e4m3fn_mixed_block35_fp16.safetensors|${MODELS}/SEEDVR2/seedvr2_ema_7b_fp8_e4m3fn_mixed_block35_fp16.safetensors|8466296338
numz/SeedVR2_comfyUI|ema_vae_fp16.safetensors|${MODELS}/SEEDVR2/ema_vae_fp16.safetensors|501324814
ENTRIES
}

main() {
  current="writing manifest"
  write_status running
  write_file_manifest

  while IFS='|' read -r repo repo_path target expected; do
    [[ -n "$repo" ]] || continue
    download_one "$repo" "$repo_path" "$target" "$expected" || true
  done < <(entries)

  current="finished"
  current_part=""
  current_expected=0
  current_source="none"
  if (( failed == 0 )); then
    write_status complete
    printf '[COMPLETE] all files present and size-verified at %s\n' "$(date -Iseconds)"
  else
    write_status complete_with_errors
    printf '[COMPLETE_WITH_ERRORS] %s file(s) failed at %s\n' "$failed" "$(date -Iseconds)"
    return 1
  fi
}

main "$@"
