#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

QUALITY_PRESETS = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "4k": (3840, 2160),
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def run(cmd: list[str]) -> None:
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        eprint("Error: ffmpeg is not installed or not available in PATH.")
        sys.exit(2)
    except subprocess.CalledProcessError as exc:
        eprint(f"Error: ffmpeg failed with exit code {exc.returncode}.")
        sys.exit(exc.returncode)


def discover_images(photos_dir: Path) -> list[Path]:
    if not photos_dir.exists() or not photos_dir.is_dir():
        eprint(f"Error: photos directory does not exist: {photos_dir}")
        sys.exit(2)

    images = [
        p
        for p in sorted(photos_dir.iterdir(), key=lambda p: p.name.lower())
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    ]
    if not images:
        eprint(f"Error: no supported images found in {photos_dir}")
        sys.exit(2)
    return images


def build_concat_file(images: list[Path], seconds_per_slide: float, path: Path) -> None:
    lines: list[str] = []
    for image in images:
        lines.append(f"file {shlex.quote(str(image.resolve()))}")
        lines.append(f"duration {seconds_per_slide}")
    lines.append(f"file {shlex.quote(str(images[-1].resolve()))}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def quality_to_dimensions(quality: str | None, width: int | None, height: int | None) -> tuple[int, int]:
    if quality:
        return QUALITY_PRESETS[quality]
    if width and height:
        return width, height
    return QUALITY_PRESETS["1080p"]


def prompt(text: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or (default or "")


def choose_quality_interactive() -> str:
    options = ["720p", "1080p", "4k"]
    print("\nChoose output quality:")
    for idx, label in enumerate(options, start=1):
        w, h = QUALITY_PRESETS[label]
        print(f"  {idx}) {label} ({w}x{h})")

    while True:
        choice = input("Enter choice [2]: ").strip() or "2"
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice) - 1]
        print("Invalid choice, please enter 1, 2, or 3.")


def collect_interactive_settings(args: argparse.Namespace) -> None:
    print("Starting new slideshow project setup...")
    args.photos = prompt("Photo input directory", "./photos")
    args.output = prompt("Output MP4 path", "./out/slideshow.mp4")

    include_audio = prompt("Add background audio? (y/N)", "n").lower() in {"y", "yes"}
    if include_audio:
        args.audio = prompt("Audio file path", "./audio/track.mp3")

    args.quality = choose_quality_interactive()
    args.seconds = float(prompt("Seconds per slide", str(args.seconds)))
    args.fps = int(prompt("Frames per second", str(args.fps)))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a memorial slideshow MP4 from photos.")
    parser.add_argument("--start-project", action="store_true", help="Launch interactive project setup menu.")
    parser.add_argument("--photos", help="Input photos directory.")
    parser.add_argument("--output", help="Output MP4 path.")
    parser.add_argument("--audio", help="Optional background audio path.")

    parser.add_argument("--quality", choices=["720p", "1080p", "4k"], help="Resolution preset.")
    parser.add_argument("--width", type=int, help="Output width (ignored when --quality is set).")
    parser.add_argument("--height", type=int, help="Output height (ignored when --quality is set).")

    parser.add_argument("--seconds", type=float, default=6.0, help="Seconds per slide.")
    parser.add_argument("--fps", type=int, default=30, help="Output FPS.")

    parser.add_argument("--fade", type=float, default=1.0, help="Reserved for future transition effects.")
    parser.add_argument("--zoom-end", type=float, default=1.06, help="Reserved for future Ken Burns controls.")
    parser.add_argument("--dedup-mode", default="both", help="Reserved for future dedup controls.")
    parser.add_argument("--dhash-threshold", type=int, default=6, help="Reserved for future dedup controls.")
    parser.add_argument("--audio-fade-in", type=float, default=0.0)
    parser.add_argument("--audio-fade-out", type=float, default=0.0)
    parser.add_argument("--title", default="")
    parser.add_argument("--subtitle", default="")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.start_project:
        collect_interactive_settings(args)

    if not args.photos or not args.output:
        parser.error("--photos and --output are required unless --start-project is used.")

    photos_dir = Path(args.photos)
    output_file = Path(args.output)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    width, height = quality_to_dimensions(args.quality, args.width, args.height)
    images = discover_images(photos_dir)

    with tempfile.TemporaryDirectory(prefix="slideshow_") as tmp_dir:
        concat_path = Path(tmp_dir) / "inputs.ffconcat"
        build_concat_file(images, args.seconds, concat_path)

        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
            f"fps={args.fps},format=yuv420p"
        )

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
        ]

        if args.audio:
            audio = Path(args.audio)
            if not audio.exists() or not audio.is_file():
                eprint(f"Error: audio file does not exist: {audio}")
                sys.exit(2)
            cmd += ["-i", str(audio)]

        cmd += ["-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p"]

        if args.audio:
            audio_filters: list[str] = []
            if args.audio_fade_in > 0:
                audio_filters.append(f"afade=t=in:st=0:d={args.audio_fade_in}")
            if args.audio_fade_out > 0:
                total_duration = len(images) * args.seconds
                fade_start = max(total_duration - args.audio_fade_out, 0)
                audio_filters.append(f"afade=t=out:st={fade_start}:d={args.audio_fade_out}")
            if audio_filters:
                cmd += ["-af", ",".join(audio_filters)]
            cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]

        cmd += ["-movflags", "+faststart", str(output_file)]

        run(cmd)

    print(f"Built slideshow: {output_file}")
    print(f"Slides: {len(images)} | Resolution: {width}x{height} | FPS: {args.fps}")


if __name__ == "__main__":
    main()
