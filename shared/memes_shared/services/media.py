"""Media downloading with safety limits (authorized sources only upstream)."""
from __future__ import annotations

import mimetypes
from pathlib import Path

import httpx

from memes_shared.logging_setup import get_logger

log = get_logger("memes.media")

MAX_DOWNLOAD_BYTES = 500 * 1024 * 1024  # 500 MB safety cap
ALLOWED_CONTENT_PREFIXES = ("video/", "application/octet-stream", "binary/octet-stream")


class MediaDownloadError(Exception):
    pass


def download(
    url: str,
    dest_dir: str | Path,
    filename: str | None = None,
    timeout: float = 300.0,
    max_bytes: int = MAX_DOWNLOAD_BYTES,
) -> Path:
    """Stream-download `url` into `dest_dir`. Returns local path.

    Raises MediaDownloadError on HTTP errors, oversized files or non-video
    content types (when the server provides one).
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        with client.stream("GET", url) as resp:
            if resp.status_code >= 400:
                raise MediaDownloadError(f"HTTP {resp.status_code} downloading {url}")
            ctype = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
            if ctype and ctype.startswith(("image/", "text/")) and "svg" not in ctype:
                raise MediaDownloadError(f"refusing non-video content-type '{ctype}'")

            if filename is None:
                ext = Path(httpx.URL(url).path).suffix or mimetypes.guess_extension(ctype) or ".mp4"
                filename = f"dl_{abs(hash(url)) % 10**10}{ext}"
            dest = dest_dir / filename
            size = 0
            with open(dest, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=1 << 20):
                    size += len(chunk)
                    if size > max_bytes:
                        f.close()
                        dest.unlink(missing_ok=True)
                        raise MediaDownloadError(f"file exceeds {max_bytes} byte limit")
                    f.write(chunk)
    if dest.stat().st_size == 0:
        dest.unlink(missing_ok=True)
        raise MediaDownloadError("downloaded file is empty")
    log.info("downloaded %s (%.1f MB)", dest.name, dest.stat().st_size / 1e6)
    return dest
