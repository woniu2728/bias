def apply():
    return "flags owns post_flags through extensions.flags.backend.models.PostFlag"


def rollback():
    return "flags model ownership marker rolled back"
