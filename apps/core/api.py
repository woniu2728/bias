import os
from django.middleware.csrf import get_token
from ninja import Router
from apps.core.api_errors import api_error
from apps.core.schemas import (
    MarkdownPreviewInSchema,
    MarkdownPreviewOutSchema,
    UploadFileOutSchema,
)
from apps.core.auth import AuthBearer
from apps.core.auth import get_optional_user
from apps.core.file_service import FileUploadService
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


@router.get("/uploads/policy", auth=AuthBearer(), tags=["Uploads"])
def get_upload_policy(request):
    """获取当前上传策略，供前端展示限制和提示。"""
    return FileUploadService.get_upload_policy()


@router.post("/preview", response=MarkdownPreviewOutSchema, tags=["Forum"])
def preview_markdown(request, payload: MarkdownPreviewInSchema):
    """实时预览 Markdown 内容"""
    return {
        "html": MarkdownService.render(payload.content or "", sanitize=True)
    }


@router.post("/uploads", response=UploadFileOutSchema, auth=AuthBearer(), tags=["Uploads"])
def upload_attachment(request):
    """上传 composer 附件或图片"""
    file = request.FILES.get("file")
    if not file:
        return api_error("请选择要上传的文件", status=400)

    try:
        file_url, file_info = FileUploadService.upload_attachment(file, request.auth.id)
    except ValueError as e:
        return api_error(str(e), status=400)

    ext = os.path.splitext(file.name)[1].lower()
    return {
        "url": file_url,
        "original_name": file_info.get("original_name") or file.name,
        "size": file_info.get("size") or file.size,
        "mime_type": file_info.get("mime_type") or file.content_type,
        "hash": file_info.get("hash"),
        "is_image": ext in FileUploadService.ALLOWED_IMAGE_EXTENSIONS,
    }
