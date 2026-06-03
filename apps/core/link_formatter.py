from __future__ import annotations

from html import escape
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.parse import urlparse


LinkAttributeCallback = Callable[[Any, str, dict[str, str]], Any]


def apply_link_attribute_callbacks(
    html: str,
    *,
    site_url: str = "",
    set_rel: LinkAttributeCallback | None = None,
    set_target: LinkAttributeCallback | None = None,
) -> str:
    if not html or not (set_rel or set_target):
        return html or ""

    parser = _LinkAttributeParser(
        site_url=str(site_url or "").rstrip("/"),
        set_rel=set_rel,
        set_target=set_target,
    )
    parser.feed(html)
    parser.close()
    return parser.output


def apply_default_external_link_attributes(html: str) -> str:
    def set_rel(uri, site_url: str, attributes: dict[str, str]) -> str:
        if not _is_external_http_uri(uri, site_url):
            return attributes.get("rel", "")
        return attributes.get("rel") or "noopener noreferrer"

    def set_target(uri, site_url: str, attributes: dict[str, str]) -> str:
        if not _is_external_http_uri(uri, site_url):
            return attributes.get("target", "")
        return attributes.get("target") or "_blank"

    return apply_link_attribute_callbacks(html, set_rel=set_rel, set_target=set_target)


class _LinkAttributeParser(HTMLParser):
    def __init__(
        self,
        *,
        site_url: str,
        set_rel: LinkAttributeCallback | None,
        set_target: LinkAttributeCallback | None,
    ) -> None:
        super().__init__(convert_charrefs=False)
        self.site_url = site_url
        self.set_rel = set_rel
        self.set_target = set_target
        self.parts: list[str] = []

    @property
    def output(self) -> str:
        return "".join(self.parts)

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "a":
            self.parts.append(self.get_starttag_text() or self._serialize_tag(tag, attrs))
            return
        self.parts.append(self._serialize_tag(tag, self._resolve_anchor_attrs(attrs)))

    def handle_startendtag(self, tag: str, attrs) -> None:
        if tag.lower() != "a":
            self.parts.append(self.get_starttag_text() or self._serialize_tag(tag, attrs, self_closing=True))
            return
        self.parts.append(self._serialize_tag(tag, self._resolve_anchor_attrs(attrs), self_closing=True))

    def handle_endtag(self, tag: str) -> None:
        self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        self.parts.append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self.parts.append(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        self.parts.append(f"<?{data}>")

    def unknown_decl(self, data: str) -> None:
        self.parts.append(f"<![{data}]>")

    def _resolve_anchor_attrs(self, attrs) -> list[tuple[str, str | None]]:
        attributes = _attrs_to_dict(attrs)
        uri = urlparse(attributes.get("href", ""))

        if self.set_rel:
            rel = self.set_rel(uri, self.site_url, dict(attributes))
            if rel:
                attributes["rel"] = str(rel)

        if self.set_target:
            target = self.set_target(uri, self.site_url, dict(attributes))
            if target:
                attributes["target"] = str(target)

        return _merge_attrs(attrs, attributes)

    @staticmethod
    def _serialize_tag(tag: str, attrs, *, self_closing: bool = False) -> str:
        pieces = [f"<{tag}"]
        for name, value in attrs:
            if value is None:
                pieces.append(f" {name}")
            else:
                pieces.append(f' {name}="{escape(str(value), quote=True)}"')
        pieces.append(" />" if self_closing else ">")
        return "".join(pieces)


def _attrs_to_dict(attrs) -> dict[str, str]:
    output: dict[str, str] = {}
    for name, value in attrs:
        output[str(name).lower()] = "" if value is None else str(value)
    return output


def _merge_attrs(original_attrs, attributes: dict[str, str]) -> list[tuple[str, str | None]]:
    merged: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for name, value in original_attrs:
        key = str(name).lower()
        seen.add(key)
        merged.append((name, attributes.get(key, value)))
    for key, value in attributes.items():
        if key not in seen:
            merged.append((key, value))
    return merged


def _is_external_http_uri(uri, site_url: str) -> bool:
    if uri.scheme not in ("http", "https") or not uri.netloc:
        return False
    site = urlparse(site_url or "")
    return bool(site.netloc and uri.netloc != site.netloc) or not site.netloc
