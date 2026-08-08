#!/usr/bin/env bash

set -euo pipefail

output_dir="./MP3"
url_file=""
urls=()

while [ "$#" -gt 0 ]; do
  case "$1" in
    -o|--output-dir)
      output_dir="${2:-}"
      if [ -z "$output_dir" ]; then
        echo "Missing value for --output-dir"
        exit 1
      fi
      shift 2
      ;;
    -f|--file)
      url_file="${2:-}"
      if [ -z "$url_file" ]; then
        echo "Missing value for --file"
        exit 1
      fi
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 [-o output-dir] [--file urls.txt | <youtube-url> ...]"
      exit 0
      ;;
    *)
      urls+=("$1")
      shift
      ;;
  esac
done

if ! command -v yt-dlp >/dev/null 2>&1; then
  echo "yt-dlp not found. Install it first, then try again."
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg not found. Install it first, then try again."
  exit 1
fi

if [ -n "$url_file" ]; then
  if [ ! -f "$url_file" ]; then
    echo "URL file not found: $url_file"
    exit 1
  fi
  while IFS= read -r line || [ -n "$line" ]; do
    # Skip empty lines and comment lines in the URL file.
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    urls+=("$line")
  done < "$url_file"
fi

if [ "${#urls[@]}" -eq 0 ]; then
  echo "No URLs provided."
  echo "Usage: $0 [-o output-dir] [--file urls.txt | <youtube-url> ...]"
  exit 1
fi

mkdir -p "$output_dir"

format_duration() {
  local total_seconds="$1"
  local hours=$((total_seconds / 3600))
  local minutes=$(((total_seconds % 3600) / 60))
  local seconds=$((total_seconds % 60))

  if [ "$hours" -gt 0 ]; then
    printf '%02d:%02d:%02d' "$hours" "$minutes" "$seconds"
  else
    printf '%02d:%02d' "$minutes" "$seconds"
  fi
}

batch_start_seconds=$SECONDS
total_urls=${#urls[@]}

for index in "${!urls[@]}"; do
  url="${urls[$index]}"
  current_number=$((index + 1))
  elapsed_seconds=$((SECONDS - batch_start_seconds))

  if [ "$index" -gt 0 ]; then
    average_seconds=$((elapsed_seconds / index))
    remaining_seconds=$((average_seconds * (total_urls - index)))
    echo
    echo "Completed $index/$total_urls. Elapsed $(format_duration "$elapsed_seconds"). Estimated remaining $(format_duration "$remaining_seconds")."
  fi

  echo "Starting $current_number/$total_urls: $url"
  yt-dlp \
    --newline \
    --extract-audio \
    --audio-format mp3 \
    --audio-quality 0 \
    --output "${output_dir}/%(title)s.%(ext)s" \
    "$url"

  elapsed_seconds=$((SECONDS - batch_start_seconds))
  echo "Finished $current_number/$total_urls in $(format_duration "$elapsed_seconds")."
done
