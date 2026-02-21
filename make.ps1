$ErrorActionPreference = "Stop"

python .\build_slideshow_kb.py `
  --photos .\photos `
  --output .\out\slideshow_1080p.mp4 `
  --quality 1080p `
  --seconds 6 `
  --fade 1 `
  --fps 30 `
  --zoom-end 1.06 `
  --dedup-mode both `
  --dhash-threshold 6 `
  --title "In Loving Memory"
