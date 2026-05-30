EXTENSION_ID = "emoji"


def run_install(context):
    return {
        "status": "ok",
        "status_label": "已安装",
        "message": "Emoji 扩展已安装。",
        "details": {
            "extension_id": context.extension_id,
        },
    }


def run_enable(context):
    return {
        "status": "ok",
        "status_label": "已启用",
        "message": "Emoji 扩展已启用。",
    }


def run_disable(context):
    return {
        "status": "ok",
        "status_label": "已停用",
        "message": "Emoji 扩展已停用。",
    }


def run_uninstall(context):
    return {
        "status": "ok",
        "status_label": "已卸载",
        "message": "Emoji 扩展已卸载。",
    }
