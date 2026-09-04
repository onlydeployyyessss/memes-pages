"""Content library: list/detail/upload/reprocess/delete."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.app.deps import current_admin, get_db
from backend.app.serializers import rows_to_dicts, to_dict
from memes_shared.config import get_settings
from memes_shared.models import DiscoveredContent, TrendScore, Video
from memes_shared.services.pipeline import process_content

router = APIRouter(dependencies=[Depends(current_admin)])


@router.get("")
def list_content(
    status: str | None = None,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(DiscoveredContent).order_by(DiscoveredContent.discovered_at.desc())
    if status:
        q = q.filter(DiscoveredContent.status == status)
    if category:
        q = q.filter(DiscoveredContent.category == category)
    total = q.count()
    rows = q.offset(offset).limit(min(limit, 200)).all()
    items = []
    for row in rows:
        d = to_dict(row, exclude={"raw_metrics", "description"})
        ts = db.query(TrendScore).filter_by(content_id=row.id).first()
        d["trend_score"] = ts.score if ts else None
        items.append(d)
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/{content_id}")
def get_content(content_id: int, db: Session = Depends(get_db)):
    content = db.get(DiscoveredContent, content_id)
    if content is None:
        raise HTTPException(404, "Content not found")
    d = to_dict(content)
    videos = db.query(Video).filter_by(content_id=content_id).all()
    d["videos"] = rows_to_dicts(videos)
    ts = db.query(TrendScore).filter_by(content_id=content_id).first()
    d["trend"] = to_dict(ts) if ts else None
    return d


@router.post("/upload", status_code=201)
def upload_video(
    file: UploadFile = File(...),
    title: str = "",
    category: str = "memes",
    caption: str = "",
    db: Session = Depends(get_db),
):
    """Manual/Telegram upload: straight into the pipeline (manual = authorized
    by definition — the operator owns the content they upload)."""
    allowed_ext = {".mp4", ".mov", ".webm", ".m4v", ".mkv", ".avi"}
    suffix = "." + (file.filename or "video.mp4").rsplit(".", 1)[-1].lower()
    if suffix not in allowed_ext:
        raise HTTPException(422, f"unsupported file type {suffix}")

    cfg = get_settings()
    uploads_dir = cfg.media_path / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    filename = f"upload_{uuid.uuid4().hex[:12]}{suffix}"
    dest = uploads_dir / filename
    size = 0
    with open(dest, "wb") as f:
        while chunk := file.file.read(1 << 20):
            size += len(chunk)
            if size > 500 * 1024 * 1024:
                f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, "file exceeds 500 MB limit")
            f.write(chunk)

    content = DiscoveredContent(
        source_id=None,
        external_id=f"upload_{uuid.uuid4().hex[:12]}",
        title=title or (file.filename or "Manual upload"),
        url=f"upload://{filename}",
        media_url="",
        media_type="video",
        category=category or "memes",
        description=caption or "",
        discovered_at=datetime.now(timezone.utc),
        raw_metrics={"manual_upload": True, "filename": filename},
        status="detected",
    )
    db.add(content)
    db.flush()

    # manual uploads bypass discovery: pre-seed a perfect trend score context
    from memes_shared.services.trend_engine import compute_trend_score

    score, breakdown = compute_trend_score(
        {"views": 0, "likes": 0, "comments": 0, "shares": 0}, None,
        trend_cfg=None, history=None,
    )
    db.add(TrendScore(content_id=content.id, score=score, signals=breakdown))

    # inject local file directly into pipeline: wrap download step
    content.status = "processing"
    db.flush()
    try:
        from memes_shared.services import video as video_svc
        from memes_shared.services.publishing import create_jobs_for_content
        from memes_shared.services import dedup

        info, err = video_svc.validate_video(dest)
        if err:
            raise ValueError(err)
        sha = dedup.sha256_file(dest)
        dup = dedup.check_media(db, sha256=sha)
        if dup.is_duplicate:
            content.status = "skipped"
            content.error = f"duplicate: {dup.reason_text}"
            db.commit()
            return to_dict(content)
        normalized = video_svc.normalize_video(dest, cfg.media_path / "videos")
        cover = ""
        try:
            cover = str(video_svc.extract_cover(normalized, cfg.media_path / "covers"))
        except Exception:  # noqa: BLE001
            pass
        video = Video(
            content_id=content.id, file_path=str(normalized), original_path=str(dest),
            cover_path=cover, file_size=normalized.stat().st_size,
            duration=info.get("duration", 0), width=info.get("width", 0),
            height=info.get("height", 0), fps=info.get("fps", 0),
            has_audio=info.get("has_audio", True), status="ready",
        )
        db.add(video)
        db.flush()
        import hashlib

        from memes_shared.models import VideoHash

        db.add(VideoHash(
            video_id=video.id, sha256=sha, source_url_hash=hashlib.sha256(content.url.encode()).hexdigest(),
        ))
        jobs = create_jobs_for_content(db, content, video)
        content.status = "queued" if jobs else "skipped"
        if not jobs:
            content.error = "no eligible destination accounts"
    except Exception as e:  # noqa: BLE001
        content.status = "failed"
        content.error = str(e)[:1000]
    db.commit()
    return to_dict(content)


@router.post("/{content_id}/reprocess")
def reprocess(content_id: int, db: Session = Depends(get_db)):
    content = db.get(DiscoveredContent, content_id)
    if content is None:
        raise HTTPException(404, "Content not found")
    content.status = "processing"
    content.error = ""
    db.flush()
    result = process_content(db, content)
    db.commit()
    return {"content_id": content.id, "status": result}


@router.delete("/{content_id}")
def delete_content(content_id: int, db: Session = Depends(get_db)):
    content = db.get(DiscoveredContent, content_id)
    if content is None:
        raise HTTPException(404, "Content not found")
    db.delete(content)
    db.commit()
    return {"ok": True}
