from bias_core.extensions import ThemeExtender


def extend():
    return [
        ThemeExtender()
        .variables({
            "--forum-primary-color": "#256f68",
            "--forum-accent-color": "#b44d24",
            "--forum-bg-canvas": "#f6f8f5",
        })
        .document_classes("bias-theme-fixture")
        .head_tag("link", {
            "id": "bias-fixture-theme-css",
            "rel": "stylesheet",
            "href": "/static/extensions/fixture-theme/theme.css",
        })
    ]
