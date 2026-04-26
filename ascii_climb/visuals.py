from __future__ import annotations

from ascii_climb.models import Item


RARITY_COLORS = {
    "common": "#f2f2f2",
    "uncommon": "#2fbf71",
    "rare": "#3d7bff",
    "mythical": "#a05cff",
    "legendary": "#f59f2a",
    "corrupted": "#d94444",
}

QUALITY_COLORS = {
    "trash": "#f2f2f2",
    "worn": "#2fbf71",
    "used": "#3d7bff",
    "polished": "#a05cff",
    "new": "#f59f2a",
    "special craft": "#d94444",
}


def item_colors(item: Item) -> tuple[str, str]:
    return (
        RARITY_COLORS.get(item.rarity, "#f2f2f2"),
        QUALITY_COLORS.get(item.quality, "#f2f2f2"),
    )


def enhancement_color(rarity: str) -> str:
    return RARITY_COLORS.get(rarity, "#f2f2f2")


def readable_text_color(background: str) -> str:
    color = background.lstrip("#")
    if len(color) != 6:
        return "#111111"
    red = int(color[0:2], 16)
    green = int(color[2:4], 16)
    blue = int(color[4:6], 16)
    brightness = (red * 299 + green * 587 + blue * 114) / 1000
    return "#111111" if brightness > 150 else "#ffffff"


def readable_text_for_backgrounds(*backgrounds: str) -> str:
    normalized = [background.lower() for background in backgrounds if background]
    if any(color in {"#f2f2f2", "#ffffff", "#fff"} for color in normalized):
        return "#111111"
    if not normalized:
        return "#111111"
    darkest = min(normalized, key=lambda color: 999 if len(color.lstrip("#")) != 6 else (
        int(color.lstrip("#")[0:2], 16) * 299
        + int(color.lstrip("#")[2:4], 16) * 587
        + int(color.lstrip("#")[4:6], 16) * 114
    ))
    return readable_text_color(darkest)
