"""Prompt templates for every AI feature.

Ground rule baked into every prompt: the AI works ONLY with the structured
data we hand it — it must never invent metrics.
"""
from __future__ import annotations

import json

TREND_SYSTEM = (
    "You are Trend Hunter, the trend-analysis engine of a social media "
    "automation platform. You analyze viral-content metadata and respond with "
    "STRICT JSON only — no prose, no code fences. Schema:\n"
    '{"trend_score": 0-100, "trend_level": "low|rising|hot|viral", '
    '"confidence": 0.0-1.0, "category": "best fitting category", '
    '"reason": "one short sentence", "recommendation": "queue|watch|skip"}'
)


def trend_user_prompt(meta: dict) -> str:
    return (
        "Analyze this discovered content for viral potential. Use ONLY the "
        "data provided.\n\nDATA:\n" + json.dumps(meta, default=str, indent=2)
    )


CAPTION_SYSTEM = (
    "You are a social-media caption writer for meme/reels pages. Respond with "
    "STRICT JSON only: {\"captions\": [\"...\", ...]}. Captions are punchy, "
    "emoji-friendly, platform-safe, each under 900 characters. Include 3-8 "
    "relevant hashtags inside each caption."
)


def caption_user_prompt(*, title: str, description: str, category: str,
                        tone: str, count: int, platform: str = "instagram") -> str:
    return (
        f"Write {count} caption variations.\n"
        f"Platform: {platform}\nTone: {tone or 'fun, casual'}\n"
        f"Category: {category or 'memes'}\n"
        f"Video title: {title or '(untitled)'}\n"
        f"Description: {(description or '')[:600] or '(none)'}"
    )


HASHTAG_SYSTEM = (
    "You are a hashtag researcher. Respond with STRICT JSON only: "
    "{\"hashtags\": [\"tag1\", \"tag2\", ...]} — lowercase, no '#' prefix, "
    "mix broad and niche tags."
)


def hashtag_user_prompt(*, title: str, category: str, count: int = 12) -> str:
    return (f"Suggest {count} hashtags for this video.\n"
            f"Title: {title or '(untitled)'}\nCategory: {category or 'memes'}")


CATEGORY_SYSTEM = (
    "You are a content classifier. Respond with STRICT JSON only: "
    "{\"category\": \"one_lowercase_word\"} — choose the single best category "
    "(e.g. memes, funny, gaming, sports, news, animals, food, tech)."
)


def category_user_prompt(title: str, description: str) -> str:
    return (f"Classify this video into one category.\nTitle: {title or '(untitled)'}\n"
            f"Description: {(description or '')[:500]}")


LANGUAGE_SYSTEM = (
    "Detect the language. Respond with STRICT JSON only: {\"language\": \"en\"} "
    "(ISO 639-1 code)."
)


def language_user_prompt(text: str) -> str:
    return f"Detect the language of this text:\n\n{(text or '')[:800]}"


REPORT_SYSTEM = (
    "You write concise executive summaries of social-media performance. "
    "Use ONLY the numbers in the provided report data — never invent metrics. "
    "Respond with 3-6 short lines starting with 📊 AI PERFORMANCE SUMMARY, "
    "each line a concrete insight from the data."
)


def report_user_prompt(report_text: str, payload: dict) -> str:
    return ("REPORT DATA (authoritative):\n"
            + json.dumps(payload, default=str, indent=2)
            + "\n\nFORMATTED REPORT:\n" + report_text[:2000])


ASSISTANT_SYSTEM = (
    "You are the Memes Pages AI assistant embedded in a social-media "
    "automation platform. Answer the operator's question using ONLY the "
    "JSON context provided (real database analytics). If the data does not "
    "contain the answer, say you don't have that data. Be concise; use "
    "emoji-light formatting; never invent numbers."
)


def assistant_user_prompt(question: str, context_json: str) -> str:
    return f"LIVE DATABASE CONTEXT:\n{context_json}\n\nOPERATOR QUESTION: {question}"
