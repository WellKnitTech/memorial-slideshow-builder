# Memorial Slideshow Builder (1080p)

A production-grade memorial slideshow generator for 1080p reception TVs.

## Features

- EXIF date ordering (DateTimeOriginal)
- Exact duplicate removal (SHA-256)
- Near duplicate removal (Perceptual dHash)
- Tasteful Ken Burns zoom (subtle)
- Smooth crossfades
- Optional background music
- 1080p H.264 output
- VLC-ready looping playback

---

## Installation (Arch Linux)

```bash
sudo pacman -Syu --needed ffmpeg python python-pip
python -m pip install --user --upgrade -r requirements.txt
