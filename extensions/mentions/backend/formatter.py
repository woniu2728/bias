from apps.core.extensions.runtime_access import get_runtime_username_id_map
from extensions.mentions.backend.parser import MENTION_RE, extract_mentioned_usernames


def render_mentions_html(html: str) -> str:
    if not html:
        return ""

    mention_names = set(extract_mentioned_usernames(html))
    mention_map = get_runtime_username_id_map(mention_names)

    def replace_mention(match):
        username = match.group(1)
        user_id = mention_map.get(username)
        target = user_id if user_id else username
        return f'<a href="/u/{target}" class="mention">@{username}</a>'

    parts = html.split("<a")
    processed_parts = [MENTION_RE.sub(replace_mention, parts[0])]
    for part in parts[1:]:
        end_tag = part.find("</a>")
        if end_tag != -1:
            processed_parts.append("<a" + part[:end_tag + 4])
            processed_parts.append(MENTION_RE.sub(replace_mention, part[end_tag + 4:]))
        else:
            processed_parts.append("<a" + part)

    return "".join(processed_parts)

