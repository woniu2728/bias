from django.middleware.csrf import get_token
from ninja import Router
from apps.core.schemas import (
    MarkdownPreviewInSchema,
    MarkdownPreviewOutSchema,
)
from apps.core.auth import get_optional_user
from apps.core.markdown_service import MarkdownService
from apps.core.runtime_state import get_runtime_status
from apps.core.settings_service import get_public_forum_settings

router = Router()


@router.get("/forum", tags=["Forum"])
def get_forum_settings(request):
    """获取前台公开论坛设置"""
    return get_public_forum_settings(user=get_optional_user(request))


@router.get("/system/status", tags=["System"])
def get_system_status(request):
    """获取论坛安装/升级状态"""
    status = get_runtime_status()
    return {
        "state": status.state,
        "message": status.message,
        "current_version": status.current_version,
        "installed_version": status.installed_version,
    }


@router.get("/csrf", tags=["Auth"])
def get_csrf_token(request):
    """初始化 SPA 所需的 CSRF cookie。"""
    return {"csrfToken": get_token(request)}


@router.post("/preview", response=MarkdownPreviewOutSchema, tags=["Forum"])
def preview_markdown(request, payload: MarkdownPreviewInSchema):
    """实时预览 Markdown 内容"""
    return {
        "html": MarkdownService.render(payload.content or "", sanitize=True)
    }
