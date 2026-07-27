#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/root/autodl-tmp"
INSTALL="$ROOT/ComfyUI-Easy-Install"
COMFY="$INSTALL/ComfyUI"
PYTHON="$INSTALL/python_embeded/python"
UV="$INSTALL/python_embeded/bin/uv"
WHEEL="$ROOT/downloads/llama_cpp_python-0.3.40+cu128-cp312-cp312-linux_x86_64.whl"
HELPER="$ROOT/Helper-CEI-NEXT-unix.zip"
LOG="$ROOT/logs/comfyui-resume.log"
FAILED="$ROOT/logs/comfyui-node-failures.txt"

exec > >(tee -a "$LOG") 2>&1
trap 'printf "resume failed at line %s\n" "$LINENO"' ERR

for path in "$COMFY" "$PYTHON" "$UV" "$WHEEL" "$HELPER"; do
  if [[ ! -e "$path" ]]; then
    printf 'required path missing: %s\n' "$path" >&2
    exit 1
  fi
done

UV_ARGS=(--system --no-cache --link-mode=copy --index-url https://pypi.org/simple --python "$PYTHON")
PIP_ARGS=(--no-cache-dir --timeout=120 --retries=3 --root-user-action=ignore)
export GIT_LFS_SKIP_SMUDGE=1
export GIT_TERMINAL_PROMPT=0
export UV_CONCURRENT_DOWNLOADS=4
export UV_CONCURRENT_INSTALLS=4
export UV_HTTP_TIMEOUT=120

accelerated_requirements() {
  local requirements="$1"
  local label="$2"
  local report="$ROOT/logs/${label}.pip-report.json"
  local urls="$ROOT/logs/${label}.aria2.txt"
  local wheelhouse="$ROOT/wheelhouse"
  mkdir -p "$wheelhouse"

  if ! "$PYTHON" -m pip install --dry-run --report "$report" \
      --index-url https://pypi.org/simple --timeout 120 --retries 3 \
      -r "$requirements"; then
    return 1
  fi

  "$PYTHON" - "$report" "$urls" "$wheelhouse" <<'PY'
import json
import os
import sys
from urllib.parse import unquote, urlparse

report_path, urls_path, wheelhouse = sys.argv[1:]
with open(report_path, encoding="utf-8") as handle:
    report = json.load(handle)

urls = []
for item in report.get("install", []):
    url = item.get("download_info", {}).get("url", "")
    if not url.startswith(("http://", "https://")):
        continue
    filename = unquote(os.path.basename(urlparse(url).path))
    if filename and os.path.exists(os.path.join(wheelhouse, filename)):
        continue
    urls.append(url)

with open(urls_path, "w", encoding="utf-8") as handle:
    handle.write("\n".join(urls))
    if urls:
        handle.write("\n")
PY

  if [[ -s "$urls" ]]; then
    aria2c -i "$urls" -d "$wheelhouse" -j8 -x16 -s16 -k1M \
      --file-allocation=none --continue=true --auto-file-renaming=false
  fi

  "$PYTHON" -m pip install --no-index --find-links "$wheelhouse" \
    --timeout 120 --retries 3 --root-user-action ignore -r "$requirements"
}

printf '%s\n' '== resume base dependencies =='
"$UV" pip install "$WHEEL" "${UV_ARGS[@]}"
"$UV" pip install stringzilla==3.12.6 transformers==4.57.6 descript-audio-codec scipy==1.17.1 pygit2 av==16.0.1 "${UV_ARGS[@]}"
"$UV" pip install -r "$COMFY/requirements.txt" "${UV_ARGS[@]}"

install_node() {
  local url="$1"
  local folder="$2"
  local target="$COMFY/custom_nodes/$folder"
  printf '\n== custom node: %s ==\n' "$folder"

  if [[ ! -d "$target/.git" ]]; then
    if ! git clone "$url" "$target"; then
      printf '%s clone\n' "$folder" >> "$FAILED"
      return 0
    fi
  fi

  if [[ -s "$target/requirements.txt" ]]; then
    if ! accelerated_requirements "$target/requirements.txt" "$folder"; then
      printf '%s requirements\n' "$folder" >> "$FAILED"
    fi
  fi

  if [[ -s "$target/install.py" ]]; then
    if ! "$PYTHON" "$target/install.py"; then
      printf '%s install.py\n' "$folder" >> "$FAILED"
    fi
  fi
}

: > "$FAILED"
install_node https://github.com/Comfy-Org/ComfyUI-Manager comfyui-manager
install_node https://github.com/yolain/ComfyUI-Easy-Use ComfyUI-Easy-Use
install_node https://github.com/Fannovel16/comfyui_controlnet_aux comfyui_controlnet_aux
install_node https://github.com/rgthree/rgthree-comfy rgthree-comfy
install_node https://github.com/MohammadAboulEla/ComfyUI-iTools comfyui-itools
install_node https://github.com/city96/ComfyUI-GGUF ComfyUI-GGUF
install_node https://github.com/gseth/ControlAltAI-Nodes controlaltai-nodes
install_node https://github.com/lquesada/ComfyUI-Inpaint-CropAndStitch comfyui-inpaint-cropandstitch
install_node https://github.com/1038lab/ComfyUI-RMBG comfyui-rmbg
install_node https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite comfyui-videohelpersuite
install_node https://github.com/shiimizu/ComfyUI-TiledDiffusion ComfyUI-TiledDiffusion
install_node https://github.com/kijai/ComfyUI-KJNodes comfyui-kjnodes
install_node https://github.com/kijai/ComfyUI-WanVideoWrapper ComfyUI-WanVideoWrapper
install_node https://github.com/1038lab/ComfyUI-QwenVL ComfyUI-QwenVL
install_node https://github.com/flybirdxx/ComfyUI-Qwen-TTS qwen3-tts-comfyui
install_node https://github.com/Saganaki22/ComfyUI-FishAudioS2 ComfyUI-fish-audio-s2
install_node https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler seedvr2_videoupscaler
install_node https://github.com/chflame163/ComfyUI_LayerStyle comfyui_layerstyle
install_node https://github.com/kijai/ComfyUI-WanAnimatePreprocess ComfyUI-WanAnimatePreprocess
install_node https://gitlab.com/pixaroma/ComfyUI-Pixaroma.git ComfyUI-Pixaroma
install_node https://github.com/yolain/ComfyUI-Easy-Sam3 comfyui-easy-sam3
install_node https://github.com/kijai/ComfyUI-SCAIL-Pose ComfyUI-SCAIL-Pose
install_node https://github.com/kijai/ComfyUI-MelBandRoFormer ComfyUI-MelBandRoFormer
install_node https://github.com/capitan01R/ComfyUI-Krea2T-Enhancer ComfyUI-Krea2T-Enhancer

apt-get update -qq
apt-get install -y sox ffmpeg unzip
"$UV" pip install pylatexenc python-ffmpeg "${UV_ARGS[@]}"

cd "$ROOT"
unzip -o "$HELPER" -d "$ROOT"
find "$INSTALL" -type f -name '*.bat' -delete
find "$INSTALL" -type f -name '*.sh' -exec chmod +x {} +

installed_triton="$($PYTHON -c 'import importlib.metadata as m; print(m.version("triton"))')"
required_triton="$($PYTHON -c 'import importlib.metadata as m; r=[x for x in (m.metadata("torch").get_all("Requires-Dist") or []) if x.startswith("triton")]; print(r[0].split("==")[1].split(";")[0].strip() if r and "==" in r[0] else "")')"
if [[ -n "$required_triton" && "$installed_triton" != "$required_triton" ]]; then
  "$PYTHON" -m pip install --upgrade --force-reinstall "triton==$required_triton" "${PIP_ARGS[@]}"
fi

"$UV" pip uninstall pydantic pydantic-core "${UV_ARGS[@]}" || true
"$UV" pip install pydantic "${UV_ARGS[@]}"

mkdir -p "$COMFY/user/default/workflows"
cp -f "$ROOT"/workflows/ui/*.json "$COMFY/user/default/workflows/"

printf '\n%s\n' '== resume complete =='
if [[ -s "$FAILED" ]]; then
  printf '%s\n' 'custom-node warnings:'
  cat "$FAILED"
else
  printf '%s\n' 'all custom-node install steps completed'
fi
