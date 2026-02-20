# Memorial Slideshow Builder

Create MP4 memorial slideshows from a folder of photos, with optional background audio.

## Features

- Interactive **project start menu** (`--start-project`) for:
  - input photos folder
  - output MP4 location
  - optional audio path
  - quality preset
- Quality presets:
  - `720p` (1280x720)
  - `1080p` (1920x1080)
  - `4k` (3840x2160)
- CLI mode for scripted runs
- Optional audio fade-in / fade-out

## Installation

```bash
python -m pip install --user --upgrade -r requirements.txt
```

Also install `ffmpeg` using your OS package manager.

## Quick start (interactive)

```bash
python3 build_slideshow_kb.py --start-project
```

You will be prompted to choose:

1. Input photos directory
2. Output MP4 file path
3. Whether to add audio
4. Output quality (`720p`, `1080p`, `4k`)
5. Title card personalization (name, subtitle, colors, alignment)
6. Timing settings

## Quick start (scripted)

```bash
python3 build_slideshow_kb.py \
  --photos ./photos \
  --output ./out/slideshow_4k.mp4 \
  --quality 4k \
  --seconds 6 \
  --fps 30 \
  --title "In Loving Memory" \
  --name-line "Jane Doe" \
  --subtitle "1950-2024" \
  --footer "Forever in our hearts" \
  --title-align center \
  --accent-color d8c080
```


## Title card customization

Use these options to fully script title-card personalization:

- `--title` main heading
- `--name-line` prominent honoree name line
- `--subtitle` secondary line (dates/message)
- `--footer` optional bottom line (quote/service text)
- `--title-align` (`left`, `center`, `right`)
- `--title-bg` background hex color
- `--title-color` main title hex color
- `--subtitle-color` subtitle/footer hex color
- `--accent-color` name line hex color

Example:

```bash
python3 build_slideshow_kb.py \
  --photos ./photos \
  --output ./out/slideshow.mp4 \
  --name-line "Jane Doe" \
  --subtitle "1950-2024" \
  --footer "Forever remembered" \
  --title-align left \
  --title-bg 101018 \
  --title-color f6f2e8 \
  --subtitle-color c9c4b8 \
  --accent-color d8c080
```

## Wrapper scripts

- `./make.sh` - basic 1080p run
- `./sample_run.sh` - 1080p run with audio

## Notes

- Supported image extensions: `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`
- If `--quality` is provided, it takes precedence over `--width/--height`
