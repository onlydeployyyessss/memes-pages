"""Seed demo data (optional, for local evaluation & live preview).

Run: python -m scripts.seed_admin --demo
"""
from __future__ import annotations

import random
from datetime import timedelta

from memes_shared.db.session import get_session
from memes_shared.models import (
    AccountSettings,
    Caption,
    CaptionTemplate,
    ContentSource,
    DailyMetric,
    DestinationAccount,
    DiscoveredContent,
    RssFeed,
    TrendScore,
)
from memes_shared.services.settings import ensure_default_settings
from memes_shared.services.trend_engine import compute_trend_score
from memes_shared.utils.timeutil import utcnow

CATEGORIES = ["memes", "funny", "viral", "gaming"]


def seed_demo() -> None:
    with get_session() as s:
        ensure_default_settings(s)
        if s.query(DestinationAccount).count():
            print("• demo data already present — skipping")
            return

        # ── Captions & template ──────────────────────────────────────
        caption = Caption(
            name="Default meme caption", is_default=True,
            text="😂 Follow for more!\n\n{hashtags}",
            hashtags=["memes", "funny", "viral", "dankmemes", "explore"],
        )
        template = CaptionTemplate(
            name="Hype template (weighted)",
            template_text="🔥 {title}\n\nWhich one are you? 👇\n{hashtags}",
            placeholder_keys=["title", "hashtags"], weight=3,
        )
        s.add_all([caption, template])
        s.flush()

        # ── Destination accounts (dry-run platforms) ─────────────────
        for i, (name, followers) in enumerate(
            [("Meme Page 1", 25_000), ("Meme Page 2", 18_000), ("Gaming Clips", 9_500)], 1
        ):
            acc = DestinationAccount(
                name=name,
                platform="custom",
                username=f"memepage{i}",
                status="active",
                automation_enabled=True,
                followers_count=followers,
                default_caption_id=caption.id,
                notes="dry-run destination (demo)",
            )
            s.add(acc)
            s.flush()
            s.add(AccountSettings(
                account_id=acc.id,
                caption_settings={"mode": "default", "hashtags": caption.hashtags,
                                  "custom_text": "", "first_comment": ""},
                cover_settings={"mode": "default", "cover_id": None},
                posting_limits={"max_per_day": 8, "max_per_hour": 2},
                distribution={"enabled": True, "categories": [],
                              "keywords": [], "publish_delay_minutes": i * 5},
            ))
            # 30 days of chart-friendly metrics
            base = followers - 30 * random.randint(10, 60)
            for d in range(30, -1, -1):
                day = (utcnow() - timedelta(days=d)).date()
                grown = base + (followers - base) * (30 - d) // 30
                views = random.randint(8_000, 60_000)
                likes = int(views * random.uniform(0.05, 0.11))
                comments = int(views * random.uniform(0.004, 0.012))
                shares = int(views * random.uniform(0.006, 0.02))
                posts = random.randint(1, 4)
                s.add(DailyMetric(
                    account_id=acc.id, date=day, followers=grown,
                    new_followers=random.randint(5, 90), posts=posts, views=views,
                    likes=likes, comments=comments, shares=shares,
                    engagement_rate=round((likes + comments + shares) / views, 4),
                ))

        # ── Sources: RSS + authorized feed ───────────────────────────
        rss_src = ContentSource(
            name="🔥 Viral Memes Feed", source_type="rss",
            url="https://example.com/feed.xml", authorization="authorized",
            enabled=False, categories=["memes"], priority=1, check_interval_minutes=15,
            notes="demo feed (example URL — replace with a real authorized feed)",
        )
        s.add(rss_src)
        s.flush()
        s.add(RssFeed(source_id=rss_src.id, feed_name="🔥 Viral Memes",
                      url="https://example.com/feed.xml", category="memes",
                      priority=1, enabled=False, check_interval_minutes=15))
        s.add(ContentSource(
            name="Partner authorized feed", source_type="authorized_feed",
            url="https://partner.example.com/api/trending.json",
            authorization="not_authorized", enabled=False, categories=["viral"],
            priority=3, check_interval_minutes=30,
            notes="demo — flip authorization to 'authorized' to enable automation",
        ))

        # ── Sample trending content ──────────────────────────────────
        now = utcnow()
        for i in range(8):
            published = now - timedelta(hours=random.randint(1, 20))
            metrics = {
                "views": random.randint(20_000, 400_000),
                "likes": random.randint(2_000, 40_000),
                "comments": random.randint(100, 3_000),
                "shares": random.randint(200, 6_000),
                "growth_rate_percent_per_hour": random.uniform(10, 220),
            }
            score, breakdown = compute_trend_score(metrics, published, trend_cfg=None)
            status = ["detected", "detected", "queued", "published"][i % 4]
            content = DiscoveredContent(
                title=f"Trending Video #{342 - i} — viral meme clip",
                url=f"https://example.com/watch/{342 - i}",
                external_id=f"demo-{342 - i}",
                media_type="video",
                category=random.choice(CATEGORIES),
                published_at=published,
                discovered_at=now - timedelta(minutes=i * 7),
                raw_metrics=metrics,
                status=status,
            )
            s.add(content)
            s.flush()
            s.add(TrendScore(content_id=content.id, score=score, signals=breakdown,
                             computed_at=now))
        s.commit()
        print("✔ demo accounts, sources, captions and trending content created")
