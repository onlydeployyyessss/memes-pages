"""End-to-end pipeline test with a real (generated) sample video."""
import pytest

from memes_shared.models import (
    Caption,
    ContentSource,
    DestinationAccount,
    DiscoveredContent,
    PublishingJob,
    Video,
    AccountSettings,
)


def _make_world(db):
    src = ContentSource(name="Partner", source_type="authorized_feed",
                        url="https://p.example.com", authorization="authorized")
    caption = Caption(name="Default", text="😂 {hashtags}", is_default=True,
                      hashtags=["memes", "viral"])
    db.add_all([src, caption])
    db.flush()
    acc = DestinationAccount(name="P1", platform="custom", username="p1",
                             status="active", automation_enabled=True,
                             default_caption_id=caption.id)
    db.add(acc)
    db.flush()
    db.add(AccountSettings(account_id=acc.id,
                           caption_settings={"mode": "default"},
                           distribution={"enabled": True}))
    content = DiscoveredContent(
        source_id=src.id, title="Test viral video", url="https://p.example.com/v/1",
        external_id="v1", media_url="https://p.example.com/media/1.mp4",
        media_type="video", category="memes",
        published_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        discovered_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        raw_metrics={"views": 100_000, "likes": 10_000, "comments": 1_000, "shares": 2_000},
    )
    db.add(content)
    db.flush()
    return src, acc, content


def _fake_download(sample_video):
    """Return a download() that copies (never touches the shared fixture)."""
    import shutil
    import uuid
    from pathlib import Path

    def _download(url, dest_dir, **kw):
        Path(dest_dir).mkdir(parents=True, exist_ok=True)
        dest = Path(dest_dir) / f"dl_{uuid.uuid4().hex[:8]}.mp4"
        shutil.copy(sample_video, dest)
        return dest

    return _download


def test_full_pipeline_creates_jobs(db, sample_video, monkeypatch):
    if not sample_video:
        pytest.skip("ffmpeg unavailable")

    monkeypatch.setattr(
        "memes_shared.services.pipeline.media_svc.download",
        _fake_download(sample_video),
    )

    from memes_shared.services.pipeline import process_content

    src, acc, content = _make_world(db)
    status = process_content(db, content)
    assert status == "queued", content.error

    video = db.query(Video).filter_by(content_id=content.id).one()
    assert video.status == "ready"
    assert video.file_size > 0
    assert video.duration > 0

    jobs = db.query(PublishingJob).filter_by(content_id=content.id).all()
    assert len(jobs) == 1
    assert "#memes" in jobs[0].caption_text


def test_duplicate_skipped(db, sample_video, monkeypatch):
    if not sample_video:
        pytest.skip("ffmpeg unavailable")

    from memes_shared.services.pipeline import process_content

    monkeypatch.setattr(
        "memes_shared.services.pipeline.media_svc.download",
        _fake_download(sample_video),
    )

    src, acc, content = _make_world(db)
    assert process_content(db, content) == "queued"

    # second identical download → must be skipped as duplicate
    content2 = DiscoveredContent(
        source_id=src.id, title="Same video again", url="https://p.example.com/v/2",
        external_id="v2", media_url="https://p.example.com/media/1.mp4",
        media_type="video", category="memes",
        discovered_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    db.add(content2)
    db.flush()
    assert process_content(db, content2) == "skipped"
    assert "duplicate" in content2.error.lower()


def test_unauthorized_source_never_processed(db):
    from memes_shared.services.pipeline import process_content

    src = ContentSource(name="Rogue", source_type="rss", authorization="not_authorized")
    db.add(src)
    db.flush()
    content = DiscoveredContent(
        source_id=src.id, url="https://x/v", media_url="https://x/v.mp4",
        discovered_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    db.add(content)
    db.flush()
    assert process_content(db, content) == "skipped"
    assert "not authorized" in content.error
