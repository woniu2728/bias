import re


TAG_MENTION_RE = re.compile(r"(?<![\w/])#([A-Za-z0-9_-]{1,100})")


def render_tag_mentions_html(html: str) -> str:
    if not html:
        return ""

    slugs = set(TAG_MENTION_RE.findall(html))
    if not slugs:
        return html

    from apps.tags.models import Tag

    tag_map = {
        item["slug"]: item
        for item in Tag.objects.filter(slug__in=slugs).values("id", "name", "slug")
    }
    if not tag_map:
        return html

    def replace_tag(match):
        slug = match.group(1)
        tag = tag_map.get(slug)
        if not tag:
            return match.group(0)
        label = tag["name"] or tag["slug"]
        return f'<a href="/t/{tag["slug"]}" class="mention mention--tag">#{label}</a>'

    parts = html.split("<a")
    processed_parts = [TAG_MENTION_RE.sub(replace_tag, parts[0])]
    for part in parts[1:]:
        end_tag = part.find("</a>")
        if end_tag != -1:
            processed_parts.append("<a" + part[:end_tag + 4])
            processed_parts.append(TAG_MENTION_RE.sub(replace_tag, part[end_tag + 4:]))
        else:
            processed_parts.append("<a" + part)

    return "".join(processed_parts)
