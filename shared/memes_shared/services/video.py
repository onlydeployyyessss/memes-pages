"""Video validation & processing via ffprobe/ffmpeg."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from memes_shared.logging_setup import get_logger

log = get_logger("memes.video")

MAX_DURATION_SECONDS = 600.0
MIN_DURATION_SECONDS = 0.5
MAX_HEIGHT = 1920


class VideoProcessingError(Exception):
    pass


def _require_bin(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise VideoProcessingError(f"{name} is not installed — required for video processing")
    return path


def ffprobe(path: str | Path) -> dict:
    """Return ffprobe JSON (format + streams) or raise VideoProcessingError."""
    bin_ = _require_bin("ffprobe")
    cmd = [
        bin_, "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=60, check=True)
        return json.loads(proc.stdout.decode() or "{}")
    except subprocess.CalledProcessError as e:
        raise VideoProcessingError(f"ffprobe failed: {e.stderr.decode()[:300]}") from e
    except json.JSONDecodeError as e:
        raise VideoProcessingError("ffprobe produced invalid output") from e


def validate_video(
    path: str | Path,
    *,
    min_duration: float = MIN_DURATION_SECONDS,
    max_duration: float = MAX_DURATION_SECONDS,
) -> tuple[dict, str]:
    """Validate that the file is a playable video. Returns (info, error).

    info keys: duration,width,height,fps,has_audio,codec,audio_codec
    error is '' when valid.
    """
    try:
        data = ffprobe(path)
    except VideoProcessingError as e:
        return {}, str(e)

    streams = data.get("streams", [])
    vstreams = [s for s in streams if s.get("codec_type") == "video"]
    astreams = [s for s in streams if s.get("codec_type") == "audio"]
    if not vstreams:
        return {}, "no video stream found"
    v = vstreams[0]
    try:
        duration = float((data.get("format") or {}).get("duration") or v.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if duration < min_duration:
        return {}, f"duration {duration:.2f}s below minimum {min_duration}s"
    if duration > max_duration:
        return {}, f"duration {duration:.0f}s above maximum {max_duration:.0f}s"
    fps_parts = (v.get("avg_frame_rate") or "0/1").split("/")
    try:
        fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 and float(fps_parts[1]) else 0.0
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    info = {
        "duration": round(duration, 3),
        "width": int(v.get("width") or 0),
        "height": int(v.get("height") or 0),
        "fps": round(fps, 2),
        "has_audio": bool(astreams),
        "codec": v.get("codec_name", ""),
        "audio_codec": astreams[0].get("codec_name", "") if astreams else "",
    }
    return info, ""


def normalize_video(
    path: str | Path, out_dir: str | Path, *, max_height: int = MAX_HEIGHT
) -> Path:
    """Re-encode to platform-friendly MP4 (h264/aac, faststart), capped height."""
    ffmpeg = _require_bin("ffmpeg")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{Path(path).stem}_normalized.mp4"
    vf = f"scale='min({max_height},ih)':-2"
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(path),
        "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=1800, check=False)
    if proc.returncode != 0 or not out.exists():
        raise VideoProcessingError(f"ffmpeg normalize failed: {proc.stderr.decode()[:400]}")
    return out


def extract_cover(path: str | Path, out_dir: str | Path, at_seconds: float = 0.5) -> Path:
    """Extract a frame as JPG reel-cover candidate."""
    ffmpeg = _require_bin("ffmpeg")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{Path(path).stem}_cover.jpg"
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-ss", str(at_seconds), "-i", str(path), "-frames:v", "1", "-q:v", "2", str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=120, check=False)
    if proc.returncode != 0 or not out.exists():
        raise VideoProcessingError(f"cover extraction failed: {proc.stderr.decode()[:300]}")
    return out
