"""AI (OpenRouter) endpoints: status, settings, test connection, AI tools.

SECURITY: the API key is only ever read from the OPENROUTER_API_KEY
environment variable. It is never returned by any endpoint here, never
logged, and never sent to the frontend.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.deps import current_admin, get_db
from backend.app.serializers import rows_to_dicts
from memes_shared.config import get_settings
from memes_shared.models import AIUsageLog, DiscoveredContent, ContentSource
from memes_shared.services.ai import get_ai
from memes_shared.services.settings import get_setting, set_setting

router = APIRouter(dependencies=[Depends(current_admin)])

EDITABLE_AI_FIELDS = {
    "enabled", "provider", "model",
    "trend_assist", "influence_scoring", "blend_weight", "max_score_adjustment",
    "caption_generation", "report_summaries", "assistant_enabled",
    "max_requests_per_hour", "max_requests_per_day", "retries",
}


@router.get("/status")
def ai_status(db: Session = Depends(get_db)):
    ai = get_ai(db)
    cfg = get_setting(db, "ai")
    usage = ai.usage_counts()
    last_fail = (
        db.query(AIUsageLog)
        .filter(AIUsageLog.success.is_(False))
        .order_by(AIUsageLog.id.desc())
        .first()
    )
    return {
        "provider": cfg.get("provider", "openrouter"),
        "model": cfg.get("model") or get_settings().openrouter_model,
        "available_models": cfg.get("available_models", []),
        # SECURITY: only whether the key is configured — never the key itself
        "key_configured": bool(get_settings().openrouter_api_key),
        "enabled": bool(cfg.get("enabled", True)),
        "configured": ai.configured,
        "requests_today": usage["today"],
        "requests_this_hour": usage["hour"],
        "tokens_today": usage["tokens_today"],
        "limits": {
            "max_requests_per_hour": cfg.get("max_requests_per_hour"),
            "max_requests_per_day": cfg.get("max_requests_per_day"),
        },
        "features": {
            "trend_assist": bool(cfg.get("trend_assist")),
            "influence_scoring": bool(cfg.get("influence_scoring")),
            "caption_generation": bool(cfg.get("caption_generation")),
            "report_summaries": bool(cfg.get("report_summaries")),
            "assistant_enabled": bool(cfg.get("assistant_enabled")),
        },
        "blend_weight": float(cfg.get("blend_weight", 0.3)),
        "max_score_adjustment": float(cfg.get("max_score_adjustment", 10.0)),
        "last_error": (
            {"error_type": last_fail.error_type, "error": last_fail.error[:200],
             "at": last_fail.created_at.isoformat()}
            if last_fail else None
        ),
    }


@router.put("/settings")
def put_ai_settings(body: dict, db: Session = Depends(get_db)):
    clean = {k: v for k, v in (body or {}).items() if k in EDITABLE_AI_FIELDS}
    if "blend_weight" in clean:
        try:
            clean["blend_weight"] = max(0.0, min(1.0, float(clean["blend_weight"])))
        except (TypeError, ValueError):
            raise HTTPException(422, "blend_weight must be 0..1")
    merged = set_setting(db, "ai", clean)
    db.commit()
    return merged


@router.post("/test")
def test_connection(db: Session = Depends(get_db)):
    """Send a minimal authenticated request; return status — key never exposed."""
    result = get_ai(db).test_connection()
    db.commit()
    return result


@router.get("/usage")
def usage(limit: int = 100, db: Session = Depends(get_db)):
    rows = (
        db.query(AIUsageLog)
        .order_by(AIUsageLog.id.desc())
        .limit(min(limit, 500))
        .all()
    )
    return {"items": rows_to_dicts(rows)}


@router.post("/captions/generate")
def generate_captions(body: dict, db: Session = Depends(get_db)):
    ai = get_ai(db)
    if not ai.configured:
        raise HTTPException(409, "AI is not configured — set OPENROUTER_API_KEY")
    captions = ai.generate_captions(
        title=str(body.get("title", ""))[:300],
        description=str(body.get("description", ""))[:800],
        category=str(body.get("category", "memes")),
        tone=str(body.get("tone", "fun, casual")),
        count=max(1, min(int(body.get("count", 3)), 10)),
        platform=str(body.get("platform", "instagram")),
    )
    db.commit()
    return {"captions": captions}


@router.post("/hashtags")
def generate_hashtags(body: dict, db: Session = Depends(get_db)):
    ai = get_ai(db)
    if not ai.configured:
        raise HTTPException(409, "AI is not configured — set OPENROUTER_API_KEY")
    tags = ai.generate_hashtags(
        title=str(body.get("title", ""))[:300],
        category=str(body.get("category", "memes")),
        count=max(3, min(int(body.get("count", 12)), 30)),
    )
    db.commit()
    return {"hashtags": tags}


@router.post("/categorize")
def categorize(body: dict, db: Session = Depends(get_db)):
    ai = get_ai(db)
    if not ai.configured:
        raise HTTPException(409, "AI is not configured — set OPENROUTER_API_KEY")
    category = ai.categorize(
        title=str(body.get("title", ""))[:300],
        description=str(body.get("description", ""))[:800],
    )
    db.commit()
    return {"category": category}


@router.post("/language")
def detect_language(body: dict, db: Session = Depends(get_db)):
    ai = get_ai(db)
    if not ai.configured:
        raise HTTPException(409, "AI is not configured — set OPENROUTER_API_KEY")
    language = ai.detect_language(str(body.get("text", ""))[:1500])
    db.commit()
    return {"language": language}


@router.post("/trend-analysis/{content_id}")
def trend_analysis(content_id: int, db: Session = Depends(get_db)):
    """Preview AI trend analysis for one content item (advisory only —
    does not change the stored score; the rule engine stays deterministic)."""
    content = db.get(DiscoveredContent, content_id)
    if content is None:
        raise HTTPException(404, "Content not found")
    ai = get_ai(db)
    if not ai.configured:
        raise HTTPException(409, "AI is not configured — set OPENROUTER_API_KEY")
    source = db.get(ContentSource, content.source_id) if content.source_id else None
    meta = {
        "title": (content.title or "")[:200],
        "description": (content.description or "")[:400],
        "category": content.category,
        "source": source.name if source else "manual",
        "views": (content.raw_metrics or {}).get("views", 0),
        "likes": (content.raw_metrics or {}).get("likes", 0),
        "comments": (content.raw_metrics or {}).get("comments", 0),
        "shares": (content.raw_metrics or {}).get("shares", 0),
        "content_age_hours": (
            (content.published_at and __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc) - content.published_at
             ).total_seconds() / 3600 if content.published_at else None),
    }
    analysis = ai.analyze_trend(meta)
    db.commit()
    if analysis is None:
        return {"ok": False, "detail": "AI analysis unavailable — deterministic score stands"}
    return {"ok": True, "ai": analysis.model_dump()}
