"""Санитизация HTML комментариев: только разрешённые теги, без атрибутов."""

import re
import bleach

_ALLOWED_TAGS = ("b", "i", "u", "em", "strong")


def sanitize_comment(text: str) -> str:
    """Оставляет только b/i/u/em/strong; script, img, iframe и прочее удаляются."""
    text = re.sub(r"<(script|style)\b[^>]*>.*?</\1\s*>", "", text, flags=re.I | re.S)
    return bleach.clean(
        text,
        tags=_ALLOWED_TAGS,
        attributes={},
        protocols=[],
        strip=True,
        strip_comments=True,
    )
