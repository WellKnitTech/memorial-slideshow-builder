#!/usr/bin/env bash
set -euo pipefail

python3 build_slideshow_kb.py \
  --photos ./photos \
  --output ./out/slideshow_1080p.mp4 \
  --seconds 6 \
  --fade 1 \
  --fps 30 \
  --width 1920 --height 1080 \
  --zoom-end 1.06 \
  --dedup-mode both \
  --dhash-threshold 6 \
  --audio ./audio/track.mp3 \
  --audio-fade-in 2.5 \
  --audio-fade-out 3.5 \
  --title "In Loving Memory" \
  --subtitle "Celebrating a life well lived"
