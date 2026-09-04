"""Duplicate detection: SHA-256 exact match + perceptual frame hashes."""
from __future__ import annotations

import hashlib
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image
from sqlalchemy.orm import Session

from memes_shared.logging_setup import get_logger

log = get_logger("memes.dedup")

PHASH_SIZE = 16          # 16x16 = 256-bit average hash per frame
FRAME_SIMILARITY_THRESHOLD = 24  # max hamming distance (~9%) per frame pair


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _average_hash(img: Image.Image) -> str:
    g = img.convert("L").resize((PHASH_SIZE, PHASH_SIZE), Image.LANCZOS)
    px = list(g.getdata())
    avg = sum(px) / len(px)
    bits = "".join("1" if p > avg else "0" for p in px)
    return "".join(f"{int(bits[i:i+4], 2):x}" for i in range(0, len(bits), 4))


def extract_frame_hashes(video_path: str | Path, max_frames: int = 5) -> list[str]:
    """Extract evenly-spread frames via ffmpeg and return their average hashes."""
    ffmpeg = _ffmpeg_bin()
    hashes: list[str] = []
    with tempfile.TemporaryDirectory(prefix="mphash_") as td:
        out_pattern = str(Path(td) / "frame_%02d.jpg")
        # One pass: fps filter producing ~max_frames evenly spread frames
        cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(video_path),
            "-vf", f"thumbnail=100,scale={PHASH_SIZE * 2}:-2",
            "-frames:v", str(max_frames), "-q:v", "3", out_pattern,
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=180, check=False)
        except FileNotFoundError as e:
            raise RuntimeError("ffmpeg not found — required for duplicate detection") from e
        for f in sorted(Path(td).glob("frame_*.jpg"))[:max_frames]:
            try:
                hashes.append(_average_hash(Image.open(f)))
            except Exception:
                continue
    return hashes


def _ffmpeg_bin() -> str:
    import shutil

    return shutil.which("ffmpeg") or "ffmpeg"


def hamming_hex(a: str, b: str) -> int:
    if len(a) != len(b):
        return 10**9
    return sum(bin(int(x, 16) ^ int(y, 16)).count("1") for x, y in zip(a, b))


def frames_similar(h1: list[str], h2: list[str]) -> bool:
    if not h1 or not h2:
        return False
    pairs = list(zip(h1, h2))
    dists = [hamming_hex(a, b) for a, b in pairs]
    close = sum(1 for d in dists if d <= FRAME_SIMILARITY_THRESHOLD)
    return close >= max(1, int(len(pairs) * 0.6))


@dataclass
class DuplicateCheckResult:
    is_duplicate: bool = False
    reasons: list[str] = field(default_factory=list)
    matched_content_id: int | None = None

    @property
    def reason_text(self) -> str:
        return "; ".join(self.reasons) if self.reasons else "duplicate"

    def add(self, reason: str, content_id: int | None = None) -> None:
        self.is_duplicate = True
        self.reasons.append(reason)
        self.matched_content_id = self.matched_content_id or content_id


def check_pre_download(
    session: Session,
    *,
    source_url: str = "",
    external_id: str = "",
) -> DuplicateCheckResult:
    """Cheap checks before downloading: source URL / external id seen before."""
    from memes_shared.models import DiscoveredContent, PublishingHistory

    res = DuplicateCheckResult()
    if source_url:
        q = session.query(DiscoveredContent).filter(DiscoveredContent.url == source_url)
        existing = q.first()
        if existing is not None and existing.status not in ("detected",):
            res.add(f"source URL already processed (status: {existing.status})", existing.id)
    if external_id:
        dup = (
            session.query(PublishingHistory)
            .join(DiscoveredContent, DiscoveredContent.id == PublishingHistory.content_id)
            .filter(DiscoveredContent.external_id == external_id)
            .first()
        )
        if dup is not None:
            res.add("external id previously published", dup.content_id)
    return res


def check_media(
    session: Session,
    *,
    sha256: str = "",
    phash_frames: list[str] | None = None,
    compare_limit: int = 5000,
) -> DuplicateCheckResult:
    """Hash-based checks after download."""
    from memes_shared.models import Video, VideoHash

    res = DuplicateCheckResult()
    if sha256:
        exact = session.query(VideoHash).filter(VideoHash.sha256 == sha256).first()
        if exact is not None:
            video = session.get(Video, exact.video_id)
            res.add("identical file already stored (sha256)", video.content_id if video else None)
            return res

    phash_frames = phash_frames or []
    if phash_frames:
        rows = (
            session.query(VideoHash)
            .filter(VideoHash.phash != "")
            .order_by(VideoHash.id.desc())
            .limit(compare_limit)
            .all()
        )
        for row in rows:
            try:
                existing_frames = [f for f in row.phash.split(":") if f]
            except Exception:
                continue
            if frames_similar(phash_frames, existing_frames):
                video = session.get(Video, row.video_id)
                res.add(
                    "perceptually similar video already in library",
                    video.content_id if video else None,
                )
                return res
    return res
