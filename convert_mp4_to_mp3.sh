#!/usr/bin/env bash

set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "Usage: $0 input.mp4 [output.mp3]"
  exit 1
fi

input_file="$1"
output_file="${2:-${input_file%.*}.mp3}"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg not found. Install it first, then try again."
  exit 1
fi

ffmpeg -i "$input_file" -vn -acodec libmp3lame -q:a 2 "$output_file"
echo "Saved: $output_file"
