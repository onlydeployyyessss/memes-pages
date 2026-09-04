"""Caption rendering: placeholders, templates, hashtag sets, random selection."""
from __future__ import annotations

import random
import re
from datetime import datetime

PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def render_template(template: str, context: dict) -> str:
    """Replace {placeholder} tokens; unknown placeholders become ''."""
    def sub(m: re.Match) -> str:
        val = context.get(m.group(1), "")
        return "" if val is None else str(val)
    return PLACEHOLDER_RE.sub(sub, template).strip()


def pick_template(templates: list) -> object | None:
    """Weighted random selection among enabled templates."""
    enabled = [t for t in templates if getattr(t, "enabled", True)]
    if not enabled:
        return None
    weights = [max(1, getattr(t, "weight", 1)) for t in enabled]
    return random.choices(enabled, weights=weights, k=1)[0]


def format_hashtags(tags: list[str]) -> str:
    cleaned = []
    for t in tags or []:
        t = (t or "").strip().lstrip("#")
        if t:
            cleaned.append(f"#{t}")
    return " ".join(cleaned)


def build_caption(
    *,
    mode: str = "default",
    custom_text: str = "",
    caption_row=None,             # Caption | None
    template_row=None,            # CaptionTemplate | None
    hashtags: list[str] | None = None,
    context: dict | None = None,
    first_comment: str = "",
) -> str:
    """Build the final caption text for a publishing job.

    Modes: default → default caption row; template → rendered template
    (random selection happens upstream); custom → free text.
    """
    ctx = {"date": datetime.utcnow().strftime("%Y-%m-%d"), **(context or {})}
    if mode == "custom" and custom_text:
        base = render_template(custom_text, ctx)
    elif mode == "template" and template_row is not None:
        base = render_template(template_row.template_text, ctx)
    elif caption_row is not None:
        base = render_template(caption_row.text or "", {**ctx, "hashtags": format_hashtags(caption_row.hashtags)})
        tags = hashtags if hashtags is not None else caption_row.hashtags
        rendered_tags = format_hashtags(tags)
        if rendered_tags and "{hashtags}" not in (caption_row.text or ""):
            base = f"{base}\n\n{rendered_tags}".strip()
        return base
    else:
        base = ""

    if hashtags:
        tag_line = format_hashtags(hashtags)
        if "{hashtags}" in base:
            base = base.replace("{hashtags}", tag_line)
        elif tag_line:
            base = f"{base}\n\n{tag_line}".strip()
    if first_comment:
        base = f"{base}\n\n{first_comment}".strip()
    return base.strip()
