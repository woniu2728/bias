import os

from ninja import Router

from apps.core.api_errors import api_error
from apps.core.auth import AuthBearer
from apps.core.audit import log_admin_action
from apps.core.jwt_auth import AccessTokenAuth
from apps.core.schemas import UploadFileOutSchema
from extensions.uploads.backend.services import UploadService


router = Router()


def _require_staff(request):
    if not request.auth or not request.auth.is_staff:
        return api_error("需要管理员权限", status=403)
    return None


@router.get("/uploads/policy", auth=AuthBearer(), tags=["Uploads"])
def get_upload_policy(request):
    return UploadService.get_upload_policy()


@router.post("/uploads", response=UploadFileOutSchema, auth=AuthBearer(), tags=["Uploads"])
def upload_attachment(request):
    file = request.FILES.get("file")
    if not file:
        return api_error("请选择要上传的文件", status=400)

    try:
        file_url, file_info = UploadService.upload_attachment(file, request.auth.id)
    except ValueError as exc:
        return api_error(str(exc), status=400)

    ext = os.path.splitext(file.name)[1].lower()
    return {
        "url": file_url,
        "original_name": file_info.get("original_name") or file.name,
        "size": file_info.get("size") or file.size,
        "mime_type": file_info.get("mime_type") or file.content_type,
        "hash": file_info.get("hash"),
        "is_image": UploadService.is_image_extension(ext),
    }


@router.post("/admin/appearance/upload", auth=AccessTokenAuth(), tags=["Admin"])
def upload_appearance_asset(request, target: str):
    denied = _require_staff(request)
    if denied:
        return denied

    if target not in {"logo", "favicon"}:
        return api_error("仅支持上传 logo 或 favicon", status=400)

    file = request.FILES.get("file")
    if not file:
        return api_error("请选择要上传的文件", status=400)

    try:
        file_url, file_info = UploadService.upload_site_asset(file, target)
    except ValueError as exc:
        return api_error(str(exc), status=400)

    log_admin_action(
        request,
        "admin.appearance_asset.upload",
        target_type="appearance_asset",
        data={
            "target": target,
            "original_name": file_info.get("original_name") or file.name,
            "size": file_info.get("size") or file.size,
            "mime_type": file_info.get("mime_type") or file.content_type,
        },
    )
    return {
        "target": target,
        "url": file_url,
        "original_name": file_info.get("original_name") or file.name,
        "size": file_info.get("size") or file.size,
        "mime_type": file_info.get("mime_type") or file.content_type,
    }
