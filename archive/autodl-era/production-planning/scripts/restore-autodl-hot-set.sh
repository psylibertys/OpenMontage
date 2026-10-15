#!/usr/bin/env bash
# Server-side hot-set restore: copy model groups from the warm root to the hot
# root with SHA-256 verification, enforcing the minimum-free-space rule.
#
# Group paths mirror production-planning/AUTODL_HOT_MODEL_PROFILES_73GB.json
# (source of truth — update both if the JSON changes).
#
# Run from the workstation (script is piped over SSH):
#   ssh autodl-comfyui 'bash -s' < restore-autodl-hot-set.sh qwen_tts krea2
set -Eeuo pipefail

WARM_ROOT="/root/autodl-fs/comfyui-models"
HOT_ROOT="/root/autodl-tmp/comfyui-models"
MIN_FREE_GB=20

group_paths() {
  case "$1" in
    qwen_tts)
      printf '%s\n' "qwen-tts/" ;;
    krea2)
      printf '%s\n' \
        "diffusion_models/krea2/" \
        "text_encoders/qwen3vl_4b_fp8_scaled.safetensors" \
        "vae/qwen_image_vae.safetensors" ;;
    wan22_i2v)
      printf '%s\n' \
        "diffusion_models/wan2.2/wan2.2_i2v_A14b_high_noise_lightx2v_4step-Q6_K.gguf" \
        "diffusion_models/wan2.2/wan2.2_i2v_A14b_low_noise_lightx2v_4step-Q6_K.gguf" \
        "text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors" \
        "vae/wan_2.1_vae.safetensors" ;;
    *)
      echo "unknown group: $1 (known: qwen_tts krea2 wan22_i2v)" >&2
      return 2 ;;
  esac
}

tree_sha256() {
  local path="$1"
  if [[ -d "$path" ]]; then
    ( cd "$path" && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum )
  else
    sha256sum "$path"
  fi
}

[[ $# -ge 1 ]] || { echo "usage: restore-autodl-hot-set.sh <group> [group ...]" >&2; exit 2; }

echo "== hot root before =="
mkdir -p "$HOT_ROOT"
du -sh "$HOT_ROOT"/* 2>/dev/null || echo "(hot root empty)"
df -h /root/autodl-tmp | tail -1

failed=0
for group in "$@"; do
  echo "== restoring group: $group =="
  while IFS= read -r rel; do
    src="$WARM_ROOT/$rel"
    dst="$HOT_ROOT/$rel"
    if [[ ! -e "$src" ]]; then
      echo "MISSING in warm root: $src" >&2
      failed=1
      continue
    fi
    echo "-- copy $rel"
    mkdir -p "$(dirname "$dst")"
    tmp="${dst}.restore-part"
    rm -rf "$tmp"
    cp -a "$src" "$tmp"
    echo "-- verify $rel"
    if [[ "$(tree_sha256 "$src")" == "$(tree_sha256 "$tmp")" ]]; then
      rm -rf "$dst"
      mv "$tmp" "$dst"
      echo "   verified OK"
    else
      echo "   SHA-256 MISMATCH for $rel — left ${tmp} for inspection" >&2
      failed=1
    fi
  done < <(group_paths "$group")
done

echo "== hot root after =="
du -sh "$HOT_ROOT"/* 2>/dev/null || true
free_kb="$(df --output=avail -k /root/autodl-tmp | tail -1)"
free_gb=$((free_kb / 1024 / 1024))
echo "free after restore: ${free_gb}GB (minimum ${MIN_FREE_GB}GB)"

if (( failed )); then echo "RESTORE FAILED" >&2; exit 1; fi
if (( free_gb < MIN_FREE_GB )); then echo "FREE SPACE BELOW MINIMUM" >&2; exit 3; fi
echo "RESTORE OK"
