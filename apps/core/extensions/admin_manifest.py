from __future__ import annotations

from pathlib import Path

from apps.core.markdown_service import MarkdownService


def build_extension_links(extension) -> dict:
    links: dict[str, object] = {}
    documentation_url = manifest_attr(extension, "documentation_url")
    homepage = manifest_attr(extension, "homepage")
    support_email = manifest_nested_attr(extension, "security", "support_email")
    if documentation_url:
        links["documentation"] = documentation_url
    if homepage:
        links["website"] = homepage
    if support_email:
        links["support"] = f"mailto:{support_email}"

    extra_links = dict((manifest_value(extension, "extra", {}) or {}).get("links") or {})
    for key, value in extra_links.items():
        normalized_key = str(key or "").strip()
        if normalized_key and value:
            links[normalized_key] = value

    links["authors"] = build_extension_author_links(extension)
    return links


def build_extension_author_names(extension) -> list[str]:
    return [
        str(getattr(author, "name", "") or "").strip()
        for author in manifest_sequence(extension, "authors")
        if str(getattr(author, "name", "") or "").strip()
    ]


def build_extension_author_links(extension) -> list[dict[str, str]]:
    author_links = []
    for author in manifest_sequence(extension, "authors"):
        name = str(getattr(author, "name", "") or "").strip()
        if not name:
            continue
        homepage = str(getattr(author, "homepage", "") or "").strip()
        email = str(getattr(author, "email", "") or "").strip()
        link = homepage or (f"mailto:{email}" if email else "")
        author_links.append({"name": name, "link": link})
    return author_links


def build_extension_readme(extension) -> dict:
    if extension.source != "filesystem":
        return _missing_readme()

    manifest_path = manifest_attr(extension, "path")
    root_path = Path(manifest_path) if manifest_path else None
    if root_path is None:
        return _missing_readme()

    for candidate in (
        root_path / "README.md",
        root_path / "README",
        root_path / "docs" / "README.md",
    ):
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            source = candidate.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            source = candidate.read_text(encoding="utf-8", errors="replace")
        return {
            "available": bool(source.strip()),
            "path": str(candidate),
            "html": MarkdownService.render(source, sanitize=True),
            "source": source,
        }

    return _missing_readme()


def manifest_attr(extension, name: str, default: str = "") -> str:
    return str(manifest_value(extension, name, default) or default).strip()


def manifest_value(extension, name: str, default=None):
    manifest = getattr(extension, "manifest", None)
    if isinstance(manifest, dict):
        return manifest.get(name, default)
    return getattr(manifest, name, default)


def manifest_nested_value(extension, group: str, name: str, default=None):
    parent = manifest_value(extension, group, None)
    if isinstance(parent, dict):
        return parent.get(name, default)
    return getattr(parent, name, default)


def manifest_nested_attr(extension, group: str, name: str, default: str = "") -> str:
    return str(manifest_nested_value(extension, group, name, default) or default).strip()


def manifest_sequence(extension, name: str) -> list:
    value = manifest_value(extension, name, ()) or ()
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _missing_readme() -> dict:
    return {
        "available": False,
        "path": "",
        "html": "",
        "source": "",
    }
