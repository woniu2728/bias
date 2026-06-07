def apply():
    return "mentions owns post_mentions_user through extensions.mentions.backend.models.PostMentionsUser"


def rollback():
    return "mentions model ownership marker rolled back"
