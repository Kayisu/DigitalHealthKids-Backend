"""Shared category constants and helpers for app categorization.

These keep Python services aligned with the curated category set used by
`app/assets/myapps.csv` and the client UI.
"""
from __future__ import annotations
from typing import Optional

# Canonical category keys used across the project
CATEGORY_KEYS = [
    "artificial_intelligence",
    "shopping",
    "tools",
    "games",
    "music",
    "video",
    "food_&_drink",
    "travel_&_transportation",
    "social",
    "design",
    "education",
    "finance",
    "productivity",
    "health_&_fitness",
    "hobby_entertainment",
]

# Default bucket when we cannot confidently classify
DEFAULT_CATEGORY_KEY = "tools"

# Turkish display labels for the canonical keys
CATEGORY_LABELS_TR = {
    "artificial_intelligence": "Yapay Zeka",
    "shopping": "Alışveriş",
    "tools": "Araçlar",
    "games": "Oyun",
    "music": "Müzik",
    "video": "Video",
    "food_&_drink": "Yiyecek & İçecek",
    "travel_&_transportation": "Seyahat & Ulaşım",
    "social": "Sosyal",
    "design": "Tasarım",
    "education": "Eğitim",
    "finance": "Finans",
    "productivity": "Üretkenlik",
    "health_&_fitness": "Sağlık & Fitness",
    "hobby_entertainment": "Hobi & Eğlence",
}

# Normalization/alias table to collapse legacy or upstream categories
CATEGORY_ALIASES = {
    "game": "games",
    "games": "games",
    "gaming": "games",
    "video_players": "video",
    "video_players_and_editors": "video",
    "music_and_audio": "music",
    "music_app": "music",
    "music": "music",
    "audio": "music",
    "podcast": "music",
    "podcasts": "music",
    "music": "video",
    "audio": "video",
    "entertainment": "hobby_entertainment",
    "lifestyle": "hobby_entertainment",
    "travel_and_local": "travel_&_transportation",
    "maps_and_navigation": "travel_&_transportation",
    "navigation": "travel_&_transportation",
    "transportation": "travel_&_transportation",
    "map": "travel_&_transportation",
    "gps": "travel_&_transportation",
    "communication": "social",
    "messaging": "social",
    "social_media": "social",
    "messaging": "social",
    "news_and_magazines": "social",
    "food_and_drink": "food_&_drink",
    "food": "food_&_drink",
    "drink": "food_&_drink",
    "health_and_fitness": "health_&_fitness",
    "health": "health_&_fitness",
    "fitness": "health_&_fitness",
    "finance_and_banking": "finance",
    "business": "productivity",
    "productivity_tools": "productivity",
    "personalization": "design",
    "art_and_design": "design",
    "photography": "design",
    "education_kids": "education",
    "kids": "education",
    "other": DEFAULT_CATEGORY_KEY,
    "others": DEFAULT_CATEGORY_KEY,
}


def canonicalize_category_key(raw: Optional[str]) -> str:
    """Normalize a raw category value to one of the canonical keys.

    - Lowercases, trims, and replaces spaces/hyphens with underscores.
    - Applies alias table to collapse variants.
    - Falls back to DEFAULT_CATEGORY_KEY to avoid `other` buckets.
    """
    if not raw:
        return DEFAULT_CATEGORY_KEY

    key = raw.strip().lower()
    key = key.replace(" ", "_").replace("-", "_")
    key = key.replace("__", "_")
    key = key.replace("&amp;", "&")

    # First pass: direct match
    if key in CATEGORY_KEYS:
        return key

    # Alias lookup (alias itself might need a second pass)
    alias = CATEGORY_ALIASES.get(key)
    if alias:
        return canonicalize_category_key(alias)

    return DEFAULT_CATEGORY_KEY


def display_label_for(key: Optional[str]) -> str:
    """Return the Turkish display label for a canonical key (fallback to Title Case)."""
    if not key:
        return CATEGORY_LABELS_TR[DEFAULT_CATEGORY_KEY]
    canonical = canonicalize_category_key(key)
    return CATEGORY_LABELS_TR.get(canonical, canonical.replace("_", " ").title())


__all__ = [
    "CATEGORY_KEYS",
    "CATEGORY_LABELS_TR",
    "CATEGORY_ALIASES",
    "DEFAULT_CATEGORY_KEY",
    "canonicalize_category_key",
    "display_label_for",
]
