"""Publishing dispatch tests (dry-run) + safety behaviour."""
from datetime import datetime, timedelta, timezone

from memes_shared.models import (
    AccountSettings,
    Caption,
    DestinationAccount,
    DiscoveredContent,
    PublishingBatch,
    PublishingHistory,
    PublishingJob,
    Video,
)
from memes_shared.services.publishing import create_jobs_for_content, dispatch_due_jobs
from memes_shared.services.scheduler import schedule_queue
from memes_shared.services.settings import get_setting


def _world(db, n_accounts=2):
    caption = Caption(name="C", text="hi {hashtags}", is_default=True, hashtags=["m"])
    db.add(caption)
    db.flush()
    accounts = []
    for i in range(n_accounts):
        a = DestinationAccount(name=f"A{i}", platform="custom", username=f"a{i}",
                               status="active", automation_enabled=True,
                               default_caption_id=caption.id)
        db.add(a)
        db.flush()
        db.add(AccountSettings(account_id=a.id, caption_settings={"mode": "default"},
                               distribution={"enabled": True}))
        accounts.append(a)
    content = DiscoveredContent(
        title="T", url="u", external_id=f"e{n_accounts}",
        media_type="video", category="memes",
        discovered_at=datetime.now(timezone.utc),
    )
    db.add(content)
    db.flush()
    video = Video(content_id=content.id, file_path="/nonexistent.mp4", status="ready")
    db.add(video)
    db.flush()
    return accounts, content, video


def test_multi_account_distribution(db):
    accounts, content, video = _world(db, n_accounts=3)
    jobs = create_jobs_for_content(db, content, video)
    assert len(jobs) == 3
    assert {j.account_id for j in jobs} == {a.id for a in accounts}
    assert all("#m" in j.caption_text for j in jobs)


def test_disabled_distribution_excluded(db):
    accounts, content, video = _world(db, n_accounts=1)
    from memes_shared.models import AccountSettings as AS

    db.query(AS).filter_by(account_id=accounts[0].id).update(
        {"distribution": {"enabled": False}}
    )
    jobs = create_jobs_for_content(db, content, video)
    assert len(jobs) == 0


def test_dispatch_dry_run_publishes(db, monkeypatch, tmp_path):
    accounts, content, video = _world(db, n_accounts=2)
    real_file = tmp_path / "v.mp4"
    real_file.write_bytes(b"0000")
    video.file_path = str(real_file)
    jobs = create_jobs_for_content(db, content, video)

    from memes_shared.services import automation as auto

    auto.start(db)
    stats = dispatch_due_jobs(db)
    db.commit()
    assert stats["published"] == 2
    assert content.status == "published"
    assert db.query(PublishingHistory).count() == 2


def test_dispatch_blocked_when_automation_off(db, tmp_path):
    accounts, content, video = _world(db, n_accounts=1)
    video.file_path = str(tmp_path / "v.mp4")
    create_jobs_for_content(db, content, video)
    from memes_shared.services import automation as auto

    auto.stop(db)
    stats = dispatch_due_jobs(db)
    assert stats["dispatched"] == 0 or stats.get("published", 0) == 0


def test_transient_failure_backoff(db, monkeypatch, tmp_path):
    from memes_shared.services.publishers.base import PublishResult

    accounts, content, video = _world(db, n_accounts=1)
    real_file = tmp_path / "v.mp4"
    real_file.write_bytes(b"x")
    video.file_path = str(real_file)
    job = create_jobs_for_content(db, content, video)[0]

    from memes_shared.services import publishers

    class Flaky:
        name = "flaky"

        def publish(self, **kw):
            return PublishResult(success=False, error="network glitch",
                                 error_type="transient")

    monkeypatch.setitem(publishers.REGISTRY, "dry_run", Flaky())
    from memes_shared.services import automation as auto

    auto.start(db)
    stats = dispatch_due_jobs(db)
    db.refresh(job)
    assert job.status == "scheduled"      # retry scheduled…
    assert job.next_retry_at is not None  # …with backoff timestamp
    assert job.attempts == 1

    # second + third attempt exhaust retries (forced so backoff time is ignored)
    dispatch_due_jobs(db, force_job_ids=[job.id])
    dispatch_due_jobs(db, force_job_ids=[job.id])
    db.refresh(job)
    assert job.status == "failed"
    assert job.attempts == 3


def test_scheduler_assigns_batches(db):
    accounts, content, video = _world(db, n_accounts=2)
    jobs = create_jobs_for_content(db, content, video)
    result = schedule_queue(db)
    assert result["scheduled"] == 2
    assert result["batches"] >= 1
    for job in jobs:
        db.refresh(job)
        assert job.publish_at is not None
        assert job.status == "scheduled"
        assert job.batch_id is not None


def test_rate_limit_stops_and_pauses(db, monkeypatch, tmp_path):
    from memes_shared.services.publishers.base import PublishResult

    accounts, content, video = _world(db, n_accounts=1)
    real_file = tmp_path / "v.mp4"
    real_file.write_bytes(b"x")
    video.file_path = str(real_file)
    job = create_jobs_for_content(db, content, video)[0]

    class Limited:
        name = "limited"

        def publish(self, **kw):
            return PublishResult(success=False, error="rate limit exceeded",
                                 error_type="rate_limit")

    from memes_shared.services import publishers

    monkeypatch.setitem(publishers.REGISTRY, "dry_run", Limited())
    from memes_shared.services import automation as auto

    auto.start(db)
    stats = dispatch_due_jobs(db)
    db.refresh(job)
    db.refresh(accounts[0])
    assert stats["rate_limited"] is True
    assert job.status == "scheduled"          # rescheduled after cooldown
    assert accounts[0].status == "paused"     # account paused by safety stop
