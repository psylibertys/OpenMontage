#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 6 || $# -gt 7 ]]; then
  echo "Usage: $0 URL OUTPUT EXPECTED_BYTES EXPECTED_SHA256 AUTH_HEADER_FILE PROXY_URL [JOBS]" >&2
  exit 64
fi

url="$1"
output="$2"
expected_bytes="$3"
expected_sha="$4"
auth_header_file="$5"
proxy_url="$6"
jobs="${7:-8}"
block_bytes=16777216
chunk_dir="${output}.chunks"
assembled="${output}.assembled.part"

[[ "$expected_bytes" =~ ^[0-9]+$ ]] || { echo "EXPECTED_BYTES must be an integer" >&2; exit 64; }
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || { echo "JOBS must be positive" >&2; exit 64; }
[[ -s "$auth_header_file" ]] || { echo "Auth header file is missing or empty" >&2; exit 66; }

mkdir -p "$chunk_dir" "$(dirname "$output")"
chmod 700 "$chunk_dir"

if [[ -f "$output" ]] && [[ "$(stat -f %z "$output")" == "$expected_bytes" ]]; then
  current_sha="$(shasum -a 256 "$output" | awk '{print $1}')"
  if [[ "$current_sha" == "$expected_sha" ]]; then
    echo "[SKIP] verified output already exists: $output"
    exit 0
  fi
fi

raw_span=$(( (expected_bytes + jobs - 1) / jobs ))
chunk_span=$(( (raw_span + block_bytes - 1) / block_bytes * block_bytes ))

download_chunk() {
  local index="$1" start="$2" end="$3" expected_chunk="$4"
  local final tmp status size attempt
  final="$(printf '%s/chunk-%03d.bin' "$chunk_dir" "$index")"
  tmp="${final}.downloading"

  if [[ -f "$final" ]] && [[ "$(stat -f %z "$final")" == "$expected_chunk" ]]; then
    echo "[SKIP] chunk $index"
    return 0
  fi

  for attempt in $(seq 1 20); do
    echo "[START] chunk=$index attempt=$attempt range=$start-$end"
    status="$(curl --silent --show-error --fail --location \
      --proxy "$proxy_url" \
      -H @"$auth_header_file" \
      --connect-timeout 20 --speed-time 120 --speed-limit 1024 \
      --range "$start-$end" \
      --output "$tmp" \
      --write-out '%{http_code}' \
      "$url" || true)"
    size=0
    [[ -f "$tmp" ]] && size="$(stat -f %z "$tmp")"
    if [[ "$status" == "206" && "$size" == "$expected_chunk" ]]; then
      mv "$tmp" "$final"
      echo "[DONE] chunk=$index bytes=$size"
      return 0
    fi
    echo "[RETRY] chunk=$index http=$status bytes=$size expected=$expected_chunk" >&2
    sleep 5
  done

  echo "[FAIL] chunk=$index" >&2
  return 1
}

pids=()
for index in $(seq 0 $((jobs - 1))); do
  start=$((index * chunk_span))
  (( start < expected_bytes )) || break
  end=$((start + chunk_span - 1))
  (( end < expected_bytes )) || end=$((expected_bytes - 1))
  expected_chunk=$((end - start + 1))
  download_chunk "$index" "$start" "$end" "$expected_chunk" &
  pids+=("$!")
done

failed=0
for pid in "${pids[@]}"; do
  wait "$pid" || failed=1
done
(( failed == 0 )) || exit 1

first_chunk="$(printf '%s/chunk-%03d.bin' "$chunk_dir" 0)"
cp "$first_chunk" "$assembled"
truncate -s "$expected_bytes" "$assembled"

for index in $(seq 1 $((jobs - 1))); do
  start=$((index * chunk_span))
  (( start < expected_bytes )) || break
  chunk="$(printf '%s/chunk-%03d.bin' "$chunk_dir" "$index")"
  seek_blocks=$((start / block_bytes))
  dd if="$chunk" of="$assembled" bs="$block_bytes" seek="$seek_blocks" conv=notrunc 2>/dev/null
done

actual_bytes="$(stat -f %z "$assembled")"
[[ "$actual_bytes" == "$expected_bytes" ]] || { echo "Assembled size mismatch" >&2; exit 1; }
actual_sha="$(shasum -a 256 "$assembled" | awk '{print $1}')"
[[ "$actual_sha" == "$expected_sha" ]] || { echo "Assembled SHA-256 mismatch" >&2; exit 1; }

mv "$assembled" "$output"
printf '%s  %s\n' "$actual_sha" "$output" > "${output}.sha256"
echo "[COMPLETE] $output"
