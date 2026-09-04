"""AI provider abstraction — Memes Pages AI layer.

All AI features go through the central service (`service.py`), which is
provider-agnostic. OpenRouter is the first provider; future providers only
need to implement `AIProvider`.
"""
from memes_shared.services.ai.base import AIProvider, AIResponse
from memes_shared.services.ai.openrouter import OpenRouterProvider
from memes_shared.services.ai.schemas import TrendAnalysis, parse_trend_analysis
from memes_shared.services.ai.service import AIService, extract_json, get_ai

__all__ = [
    "AIProvider",
    "AIResponse",
    "OpenRouterProvider",
    "AIService",
    "get_ai",
    "TrendAnalysis",
    "parse_trend_analysis",
    "extract_json",
]
