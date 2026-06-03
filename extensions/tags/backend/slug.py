from __future__ import annotations

from django.utils.text import slugify


class TagSlugDriver:
    def generate(self, source, *, explicit_slug: str = "", context: dict | None = None) -> str:
        value = str(explicit_slug or source or "").strip()
        return slugify(value, allow_unicode=True).strip()
