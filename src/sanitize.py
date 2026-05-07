"""Санитизация HTML комментариев: только разрешённые теги, без атрибутов."""

import bleach

_ALLOWED_TAGS = ("b", "i", "u", "em", "strong")


def sanitize_comment(text: str) -> str:
    """Оставляет только b/i/u/em/strong; script, img, iframe и прочее удаляются."""
    return bleach.clean(
        text,
        tags=_ALLOWED_TAGS,
        attributes={},  # без onerror, style и т.п.
        protocols=[],
        strip=True,
        strip_comments=True,
    )
