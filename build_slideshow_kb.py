#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import logging
import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps

LOG = logging.getLogger("memorial_slideshow")

QUALITY_PRESETS = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "4k": (3840, 2160),
}

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

# EXIF tag IDs
EXIF_DATETIME_ORIGINAL = 36867
EXIF_DATETIME_DIGITIZED = 36868
EXIF_DATETIME = 306


@dataclass(frozen=True)
class PhotoItem:
    path: Path
    ts: float
    sha256: str
    dhash64: int


def eprint(msg: str) -> None:
    print(msg)


def check_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found on PATH. Install it (pacman -S ffmpeg).")


def run_cmd(cmd: list[str]) -> None:
    LOG.debug("CMD: %s", " ".join(cmd))
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed.\nCMD: {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )


def sha256_file(p: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def parse_exif_datetime(s: str) -> Optional[datetime]:
    try:
        return datetime.strptime(s, "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None


def best_timestamp_epoch(p: Path) -> float:
    try:
        with Image.open(p) as im:
            exif = im.getexif()
            for tag in (EXIF_DATETIME_ORIGINAL, EXIF_DATETIME_DIGITIZED, EXIF_DATETIME):
                val = exif.get(tag)
                if isinstance(val, str):
                    dt = parse_exif_datetime(val)
                    if dt:
                        return dt.timestamp()
    except Exception:
        pass
    return p.stat().st_mtime


def dhash_64(p: Path) -> int:
    try:
        with Image.open(p) as im:
            im = ImageOps.exif_transpose(im)
            im = im.convert("L")
            im = im.resize((9, 8), Image.Resampling.LANCZOS)
            pixels = list(im.getdata())
            bits = 0
            bitpos = 0
            for y in range(8):
                row = pixels[y * 9 : (y + 1) * 9]
                for x in range(8):
                    if row[x] > row[x + 1]:
                        bits |= 1 << bitpos
                    bitpos += 1
            return bits
    except Exception:
        return int(hashlib.sha1(str(p).encode("utf-8", errors="ignore")).hexdigest()[:16], 16)


def hamming64(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def list_candidate_files(folder: Path) -> list[Path]:
    files: list[Path] = []
    for f in folder.rglob("*"):
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS:
            files.append(f)
    return sorted(files, key=lambda x: x.name.lower())


def build_photo_items(folder: Path) -> list[PhotoItem]:
    items: list[PhotoItem] = []
    for p in list_candidate_files(folder):
        try:
            items.append(PhotoItem(path=p, ts=best_timestamp_epoch(p), sha256=sha256_file(p), dhash64=dhash_64(p)))
        except Exception as e:
            LOG.warning("Skipping unreadable file %s: %s", p, e)
    items.sort(key=lambda x: (x.ts, x.path.name.lower()))
    return items


def dedup_items(items: list[PhotoItem], dedup_mode: str, dhash_threshold: int) -> tuple[list[PhotoItem], dict[str, int]]:
    stats = {"exact_skipped": 0, "perceptual_skipped": 0}

    if dedup_mode == "off":
        return items, stats

    survivors: list[PhotoItem] = items

    if dedup_mode in ("exact", "both"):
        seen_sha: set[str] = set()
        tmp: list[PhotoItem] = []
        for it in survivors:
            if it.sha256 in seen_sha:
                stats["exact_skipped"] += 1
                LOG.info("Exact duplicate skipped: %s", it.path)
                continue
            seen_sha.add(it.sha256)
            tmp.append(it)
        survivors = tmp

    if dedup_mode in ("perceptual", "both"):
        kept: list[PhotoItem] = []
        for it in survivors:
            is_dup = False
            for k in kept:
                if hamming64(it.dhash64, k.dhash64) <= dhash_threshold:
                    stats["perceptual_skipped"] += 1
                    LOG.info("Near-duplicate skipped: %s (matches %s)", it.path.name, k.path.name)
                    is_dup = True
                    break
            if not is_dup:
                kept.append(it)
        survivors = kept

    return survivors, stats


def fit_to_canvas(img: Image.Image, canvas_size: tuple[int, int], bg_rgb=(12, 12, 12), margin_px: int = 60) -> Image.Image:
    cw, ch = canvas_size
    target_w = max(1, cw - margin_px * 2)
    target_h = max(1, ch - margin_px * 2)

    img = ImageOps.exif_transpose(img)

    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, bg_rgb)
        bg.paste(img, mask=img.split()[-1])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    img.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)

    canvas = Image.new("RGB", (cw, ch), bg_rgb)
    x = (cw - img.size[0]) // 2
    y = (ch - img.size[1]) // 2
    canvas.paste(img, (x, y))
    return canvas


def try_load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/TTF/DejaVuSerif.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/LiberationSerif-Regular.ttf",
        "/usr/share/fonts/TTF/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        fp = Path(p)
        if fp.exists():
            try:
                return ImageFont.truetype(str(fp), size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def render_title_card(out_path: Path, canvas_size: tuple[int, int], title: str, subtitle: str, bg_rgb=(12, 12, 12)) -> None:
    cw, ch = canvas_size
    img = Image.new("RGB", (cw, ch), bg_rgb)
    draw = ImageDraw.Draw(img)

    title_font = try_load_font(size=int(ch * 0.075))
    subtitle_font = try_load_font(size=int(ch * 0.035))

    def text_size(txt: str, font) -> tuple[int, int]:
        bbox = draw.textbbox((0, 0), txt, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    title = title.strip()
    subtitle = subtitle.strip()

    title_w, title_h = text_size(title, title_font)
    subtitle_w, subtitle_h = (0, 0)
    if subtitle:
        subtitle_w, subtitle_h = text_size(subtitle, subtitle_font)

    gap = int(ch * 0.02) if subtitle else 0
    total_h = title_h + (subtitle_h + gap if subtitle else 0)
    y0 = (ch - total_h) // 2

    draw.text(((cw - title_w) // 2, y0), title, font=title_font, fill=(235, 235, 235))
    if subtitle:
        draw.text(((cw - subtitle_w) // 2, y0 + title_h + gap), subtitle, font=subtitle_font, fill=(200, 200, 200))

    img.save(out_path, "JPEG", quality=92, optimize=True)


def make_kb_segment(
    still_path: Path,
    out_path: Path,
    width: int,
    height: int,
    seconds: float,
    fps: int,
    zoom_end: float,
    crf: int,
    preset: str,
) -> None:
    total_frames = max(1, int(round(seconds * fps)))

    if zoom_end <= 1.00001:
        run_cmd(
            [
                "ffmpeg",
                "-y",
                "-loop",
                "1",
                "-t",
                f"{seconds:.3f}",
                "-i",
                str(still_path),
                "-vf",
                f"scale={width}:{height},format=yuv420p,fps={fps}",
                "-c:v",
                "libx264",
                "-preset",
                preset,
                "-crf",
                str(crf),
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(out_path),
            ]
        )
        return

    z_step = (zoom_end - 1.0) / max(1, (total_frames - 1))
    z_expr = f"min(1.0+{z_step:.10f}*on,{zoom_end:.5f})"
    x_expr = "iw/2-(iw/zoom/2)"
    y_expr = "ih/2-(ih/zoom/2)"

    vf = (
        f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d={total_frames}:"
        f"s={width}x{height}:fps={fps},format=yuv420p"
    )

    run_cmd(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(still_path),
            "-vf",
            vf,
            "-t",
            f"{seconds:.3f}",
            "-r",
            str(fps),
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            str(crf),
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
    )


def build_xfade_master(
    segments: list[Path],
    output: Path,
    seconds_per: float,
    fade_seconds: float,
    fps: int,
    crf: int,
    preset: str,
    audio_path: Optional[Path],
    audio_fade_in: float,
    audio_fade_out: float,
) -> None:
    if not segments:
        raise RuntimeError("No segments to combine.")

    fade = min(fade_seconds, max(0.2, seconds_per * 0.5))
    total_video = (len(segments) * seconds_per) - ((len(segments) - 1) * fade)

    inputs: list[str] = []
    for s in segments:
        inputs += ["-i", str(s)]

    parts: list[str] = []
    for i in range(len(segments)):
        parts.append(f"[{i}:v]format=yuv420p,setsar=1,fps={fps}[v{i}]")

    current = "v0"
    t = seconds_per - fade
    for i in range(1, len(segments)):
        outv = f"x{i}"
        parts.append(f"[{current}][v{i}]xfade=transition=fade:duration={fade:.3f}:offset={t:.3f}[{outv}]")
        current = outv
        t += seconds_per - fade

    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(parts), "-map", f"[{current}]"]

    if audio_path:
        cmd += ["-stream_loop", "-1", "-i", str(audio_path)]
        fade_out_start = max(0.0, total_video - audio_fade_out)
        af = (
            f"afade=t=in:st=0:d={audio_fade_in:.3f},"
            f"afade=t=out:st={fade_out_start:.3f}:d={audio_fade_out:.3f},"
            f"atrim=0:{total_video:.3f}"
        )
        cmd += ["-map", f"[{current}]", "-map", f"{len(segments)}:a", "-af", af, "-shortest"]

    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output),
    ]
    run_cmd(cmd)


def normalize_title_segments(
    title_still: Path,
    seg_dir: Path,
    seconds_per: float,
    title_seconds: float,
    width: int,
    height: int,
    fps: int,
    crf: int,
    preset: str,
) -> list[Path]:
    title_len = max(title_seconds, seconds_per)
    n = int(math.ceil(title_len / seconds_per))
    segments: list[Path] = []
    for k in range(n):
        seg = seg_dir / f"seg_title_{k:03d}.mp4"
        make_kb_segment(
            still_path=title_still,
            out_path=seg,
            width=width,
            height=height,
            seconds=seconds_per,
            fps=fps,
            zoom_end=1.0,
            crf=crf,
            preset=preset,
        )
        segments.append(seg)
    return segments


def prompt(text: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or (default or "")


def choose_quality_interactive() -> str:
    options = ["720p", "1080p", "4k"]
    eprint("\nChoose output quality:")
    for idx, label in enumerate(options, start=1):
        w, h = QUALITY_PRESETS[label]
        eprint(f"  {idx}) {label} ({w}x{h})")

    while True:
        choice = input("Enter choice [2]: ").strip() or "2"
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice) - 1]
        eprint("Invalid choice, please enter 1, 2, or 3.")


def collect_interactive_settings(args: argparse.Namespace) -> None:
    eprint("Starting new slideshow project setup...")
    args.photos = prompt("Photo input directory", "./photos")
    args.output = prompt("Output MP4 path", "./out/slideshow.mp4")

    include_audio = prompt("Add background audio? (y/N)", "n").lower() in {"y", "yes"}
    if include_audio:
        args.audio = prompt("Audio file path", "./audio/track.mp3")

    args.quality = choose_quality_interactive()
    args.seconds = float(prompt("Seconds per slide", str(args.seconds)))
    args.fps = int(prompt("Frames per second", str(args.fps)))


def resolve_dimensions(quality: str | None, width: int, height: int) -> tuple[int, int]:
    if quality:
        return QUALITY_PRESETS[quality]
    return width, height


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Build a tasteful memorial slideshow MP4 with EXIF date ordering, de-dup, Ken Burns, and fades."
    )
    ap.add_argument("--start-project", action="store_true", help="Launch interactive project setup menu.")

    ap.add_argument("--photos", help="Folder containing photos")
    ap.add_argument("--output", default="out/slideshow.mp4", help="Output MP4 path")
    ap.add_argument("--audio", default="", help="Optional audio file path (mp3/wav/m4a)")

    ap.add_argument("--quality", choices=["720p", "1080p", "4k"], help="Resolution preset.")
    ap.add_argument("--seconds", type=float, default=6.0, help="Seconds per photo (uniform segments)")
    ap.add_argument("--fade", type=float, default=1.0, help="Crossfade duration in seconds")
    ap.add_argument("--fps", type=int, default=30, help="Frames per second")

    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--margin", type=int, default=60)

    ap.add_argument("--zoom-end", type=float, default=1.06, help="Final zoom factor (subtle: 1.05-1.10)")

    ap.add_argument("--title", default="In Loving Memory", help="Optional title card text")
    ap.add_argument("--subtitle", default="", help="Optional subtitle")
    ap.add_argument("--title-seconds", type=float, default=7.0, help="Desired title hold time (will be normalized)")
    ap.add_argument("--no-title", action="store_true", help="Disable title card")

    ap.add_argument("--audio-fade-in", type=float, default=2.5)
    ap.add_argument("--audio-fade-out", type=float, default=3.5)

    ap.add_argument("--dedup-mode", default="both", choices=["both", "exact", "perceptual", "off"])
    ap.add_argument(
        "--dhash-threshold",
        type=int,
        default=6,
        help="Near-duplicate threshold (lower is stricter). Typical: 4-8. Start with 6.",
    )

    ap.add_argument("--crf", type=int, default=18, help="x264 CRF quality (lower is higher quality). 18 is excellent.")
    ap.add_argument("--preset", default="medium", choices=["slow", "medium", "fast"], help="Encoding speed vs efficiency.")
    ap.add_argument("--loglevel", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return ap


def main() -> int:
    args = build_parser().parse_args()

    if args.start_project:
        collect_interactive_settings(args)

    if not args.photos:
        raise SystemExit("--photos is required unless --start-project is used.")

    logging.basicConfig(level=getattr(logging, args.loglevel), format="%(asctime)s %(levelname)s %(message)s")

    check_ffmpeg()

    photos_dir = Path(args.photos).expanduser().resolve()
    out = Path(args.output).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    if not photos_dir.is_dir():
        LOG.error("Photos folder not found: %s", photos_dir)
        return 2

    audio_path: Optional[Path] = None
    if args.audio.strip():
        audio_path = Path(args.audio).expanduser().resolve()
        if not audio_path.exists():
            LOG.error("Audio file not found: %s", audio_path)
            return 2

    items = build_photo_items(photos_dir)
    if not items:
        LOG.error("No supported photos found under: %s", photos_dir)
        return 2

    survivors, stats = dedup_items(items, args.dedup_mode, args.dhash_threshold)
    LOG.info(
        "Photos: %d total, %d used. Skipped exact=%d, near=%d",
        len(items),
        len(survivors),
        stats["exact_skipped"],
        stats["perceptual_skipped"],
    )

    if not survivors:
        LOG.error("All photos were removed by de-dup. Try --dedup-mode exact or --dhash-threshold higher.")
        return 2

    width, height = resolve_dimensions(args.quality, args.width, args.height)
    canvas = (width, height)
    bg_rgb = (12, 12, 12)

    with tempfile.TemporaryDirectory(prefix="memorial_slideshow_") as tmp:
        tmp_dir = Path(tmp)
        frames_dir = tmp_dir / "frames"
        seg_dir = tmp_dir / "segs"
        frames_dir.mkdir()
        seg_dir.mkdir()

        stills: list[Path] = []

        if not args.no_title and args.title.strip():
            title_still = frames_dir / "still_00000.jpg"
            render_title_card(
                out_path=title_still,
                canvas_size=canvas,
                title=args.title.strip(),
                subtitle=args.subtitle.strip(),
                bg_rgb=bg_rgb,
            )
            stills.append(title_still)

        for idx, it in enumerate(survivors, start=1):
            try:
                with Image.open(it.path) as im:
                    frame = fit_to_canvas(im, canvas, bg_rgb=bg_rgb, margin_px=args.margin)
                    fp = frames_dir / f"still_{idx:05d}.jpg"
                    frame.save(fp, "JPEG", quality=92, optimize=True)
                    stills.append(fp)
            except Exception as e:
                LOG.warning("Skipping %s: %s", it.path, e)

        if not stills:
            LOG.error("No frames rendered.")
            return 2

        segments: list[Path] = []

        if not args.no_title and args.title.strip():
            title_segments = normalize_title_segments(
                title_still=stills[0],
                seg_dir=seg_dir,
                seconds_per=args.seconds,
                title_seconds=args.title_seconds,
                width=width,
                height=height,
                fps=args.fps,
                crf=args.crf,
                preset=args.preset,
            )
            segments.extend(title_segments)
            start_idx = 1
        else:
            start_idx = 0

        zoom_end = max(1.0, args.zoom_end)
        for i, still in enumerate(stills[start_idx:], start=0):
            seg = seg_dir / f"seg_{i:05d}.mp4"
            make_kb_segment(
                still_path=still,
                out_path=seg,
                width=width,
                height=height,
                seconds=args.seconds,
                fps=args.fps,
                zoom_end=zoom_end,
                crf=args.crf,
                preset=args.preset,
            )
            segments.append(seg)
            if (i + 1) % 15 == 0:
                LOG.info("Built %d photo segments...", i + 1)

        build_xfade_master(
            segments=segments,
            output=out,
            seconds_per=args.seconds,
            fade_seconds=args.fade,
            fps=args.fps,
            crf=args.crf,
            preset=args.preset,
            audio_path=audio_path,
            audio_fade_in=args.audio_fade_in,
            audio_fade_out=args.audio_fade_out,
        )

    LOG.info("Done: %s", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
