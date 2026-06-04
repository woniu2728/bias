import re


MENTION_USERNAME_PATTERN = r"[A-Za-z0-9_-]+"
MENTION_RE = re.compile(rf"@({MENTION_USERNAME_PATTERN})")


def extract_mentioned_usernames(content: str) -> list[str]:
    if not content:
        return []

    seen: set[str] = set()
    usernames: list[str] = []
    for username in MENTION_RE.findall(content):
        normalized = username.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            usernames.append(normalized)
    return usernames


def replace_mentions(content: str, replacer) -> str:
    if not content:
        return ""
    return MENTION_RE.sub(replacer, content)
