"""Duplicate detection tests (requires ffmpeg for phash paths)."""
import pytest

from memes_shared.services import dedup


def test_sha256_exact_match(db, sample_video):
    if not sample_video:
        pytest.skip("ffmpeg unavailable")
    from memes_shared.models import DiscoveredContent, Video, VideoHash

    sha = dedup.sha256_file(sample_video)
    content = DiscoveredContent(title="t", url="u1", discovered_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
    db.add(content)
    db.flush()
    video = Video(content_id=content.id, file_path=sample_video, status="ready")
    db.add(video)
    db.flush()
    db.add(VideoHash(video_id=video.id, sha256=sha))
    db.flush()

    result = dedup.check_media(db, sha256=sha)
    assert result.is_duplicate
    assert "identical file" in result.reasons[0]


def test_unique_file_not_flagged(db, sample_video):
    if not sample_video:
        pytest.skip("ffmpeg unavailable")
    result = dedup.check_media(db, sha256="deadbeef" * 8, phash_frames=["a" * 64])
    assert not result.is_duplicate


def test_frame_similarity_logic():
    h1 = ["0" * 64, "f" * 64]
    h2 = ["0" * 64, "f" * 64]
    assert dedup.frames_similar(h1, h2)
    h3 = ["0" * 64, "0" * 63 + "1"]
    assert dedup.frames_similar(h1, h3)  # tiny difference, 1 close frame + threshold
    h4 = ["f" * 64, "0" * 64]
    h5 = ["0" * 64, "f" * 64]
    assert not dedup.frames_similar(h4, h5)  # inverted frames not similar
