import logging

from ninja import Body, Router

from apps.core.api_errors import api_error
from apps.core.admin_auth import require_staff
from apps.core.extensions.exceptions import ExtensionNotFoundError, ExtensionStateError
from apps.core.extensions.registry import get_extension_registry
from apps.core.extension_service import ExtensionService
from apps.core.extension_settings_service import get_extension_settings, serialize_extension_settings_schema, save_extension_settings
from apps.core.extensions.frontend_compiler import inspect_extension_frontend_output_manifest
from apps.core.audit import log_admin_action
from apps.core.jwt_auth import AccessTokenAuth
from apps.core.admin_extension_detail import (
    _serialize_admin_extension,
    _serialize_admin_extension_action_payload,
    _serialize_admin_extensions_payload,
    serialize_admin_extension,
    serialize_admin_extensions_payload,
)


router = Router()
logger = logging.getLogger(__name__)


_require_staff = require_staff


@router.get("/extensions", auth=AccessTokenAuth(), tags=["Admin"])
def list_admin_extensions(request):
    denied = _require_staff(request)
    if denied:
        return denied

    summary = str(request.GET.get("summary") or "").strip().lower() in {"1", "true", "yes", "on"}
    return _serialize_admin_extensions_payload(get_extension_registry().get_extensions(), summary=summary)


@router.post("/extensions/sync", auth=AccessTokenAuth(), tags=["Admin"])
def sync_admin_extensions(request, payload: dict = Body(default={})):
    denied = _require_staff(request)
    if denied:
        return denied

    prune_missing = bool(dict(payload or {}).get("prune_missing", True))
    ExtensionService.sync_extension_packages(
        prune_missing=prune_missing,
        actor=request.auth,
        request=request,
    )
    return _serialize_admin_extensions_payload(get_extension_registry().get_extensions())


@router.post("/extensions/sync-order", auth=AccessTokenAuth(), tags=["Admin"])
def sync_admin_extension_order(request):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        ExtensionService.sync_enabled_extension_order(
            actor=request.auth,
            request=request,
        )
    except ExtensionStateError as exc:
        return api_error(str(exc), status=409, code=exc.code, field_errors=exc.details)
    return _serialize_admin_extensions_payload(get_extension_registry().get_extensions())


@router.post("/extensions/rebuild-frontend", auth=AccessTokenAuth(), tags=["Admin"])
def rebuild_admin_extension_frontend(request, payload: dict = Body(default={})):
    denied = _require_staff(request)
    if denied:
        return denied

    options = dict(payload or {})
    result = ExtensionService.rebuild_extension_frontend_assets(
        run_build=bool(options.get("run_build", True)),
        include_disabled=bool(options.get("include_disabled", False)),
        publish=bool(options.get("publish", False)),
        actor=request.auth,
        request=request,
    )
    status = str(result.get("status") or "")
    if status and status != "ok":
        return api_error(
            str(result.get("message") or "扩展前端资产重建失败"),
            status=409,
            code="extension_frontend_rebuild_failed",
            field_errors=result,
        )
    return {
        **_serialize_admin_extensions_payload(get_extension_registry().get_extensions()),
        "frontend_rebuild": result,
    }


@router.get("/extensions/{extension_id}", auth=AccessTokenAuth(), tags=["Admin"])
def get_admin_extension(request, extension_id: str):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        extension = get_extension_registry().get_extension(extension_id)
    except ExtensionNotFoundError:
        return api_error("扩展不存在", status=404, code="extension_not_found")
    frontend_output_manifest = inspect_extension_frontend_output_manifest()
    return {
        "extension": _serialize_admin_extension(
            extension,
            include_permission_details=True,
            frontend_output_manifest=frontend_output_manifest,
        ),
    }


@router.get("/extensions/{extension_id}/settings", auth=AccessTokenAuth(), tags=["Admin"])
def get_admin_extension_settings(request, extension_id: str):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        extension = get_extension_registry().get_extension(extension_id)
        return {
            "extension_id": extension.id,
            "schema": serialize_extension_settings_schema(extension.id),
            "settings": get_extension_settings(extension.id),
        }
    except ExtensionNotFoundError:
        return api_error("扩展不存在", status=404, code="extension_not_found")


@router.post("/extensions/{extension_id}/settings", auth=AccessTokenAuth(), tags=["Admin"])
def save_admin_extension_settings(request, extension_id: str, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        extension = get_extension_registry().get_extension(extension_id)
        settings_data = save_extension_settings(extension.id, payload)
        log_admin_action(
            request,
            "admin.extension.settings.update",
            target_type="extension",
            data={
                "extension_id": extension.id,
                "keys": sorted(payload.keys()),
            },
        )
        return {
            "message": "扩展设置保存成功",
            "extension_id": extension.id,
            "settings": settings_data,
        }
    except ExtensionNotFoundError:
        return api_error("扩展不存在", status=404, code="extension_not_found")
    except ExtensionStateError as exc:
        return api_error(str(exc), status=409, code=exc.code, field_errors=exc.details)


@router.post("/extensions/{extension_id}/enable", auth=AccessTokenAuth(), tags=["Admin"])
def enable_admin_extension(request, extension_id: str):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        extension = ExtensionService.set_extension_enabled(
            extension_id,
            True,
            actor=request.auth,
            request=request,
        )
    except ExtensionStateError as exc:
        return api_error(str(exc), status=409, code=exc.code, field_errors=exc.details)
    return _serialize_admin_extension_action_payload(extension)


@router.post("/extensions/{extension_id}/install", auth=AccessTokenAuth(), tags=["Admin"])
def install_admin_extension(request, extension_id: str):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        extension = ExtensionService.install_extension(
            extension_id,
            actor=request.auth,
            request=request,
        )
    except ExtensionStateError as exc:
        return api_error(str(exc), status=409, code=exc.code, field_errors=exc.details)
    return _serialize_admin_extension_action_payload(extension)


@router.post("/extensions/{extension_id}/runtime-hooks/{hook_name}", auth=AccessTokenAuth(), tags=["Admin"])
def run_admin_extension_runtime_hook(request, extension_id: str, hook_name: str):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        extension = ExtensionService.run_extension_runtime_hook(
            extension_id,
            hook_name,
            actor=request.auth,
            request=request,
        )
    except ExtensionStateError as exc:
        return api_error(str(exc), status=409, code=exc.code, field_errors=exc.details)
    return _serialize_admin_extension_action_payload(extension)


@router.post("/extensions/{extension_id}/migrations", auth=AccessTokenAuth(), tags=["Admin"])
def run_admin_extension_migrations(request, extension_id: str):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        extension = ExtensionService.run_extension_migrations(
            extension_id,
            actor=request.auth,
            request=request,
        )
    except ExtensionStateError as exc:
        return api_error(str(exc), status=409, code=exc.code, field_errors=exc.details)
    return _serialize_admin_extension_action_payload(extension)


@router.post("/extensions/{extension_id}/disable", auth=AccessTokenAuth(), tags=["Admin"])
def disable_admin_extension(request, extension_id: str):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        extension = ExtensionService.set_extension_enabled(
            extension_id,
            False,
            actor=request.auth,
            request=request,
        )
    except ExtensionStateError as exc:
        return api_error(str(exc), status=409, code=exc.code, field_errors=exc.details)
    return _serialize_admin_extension_action_payload(extension)


@router.post("/extensions/{extension_id}/uninstall", auth=AccessTokenAuth(), tags=["Admin"])
def uninstall_admin_extension(request, extension_id: str):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        extension = ExtensionService.uninstall_extension(
            extension_id,
            actor=request.auth,
            request=request,
        )
    except ExtensionStateError as exc:
        return api_error(str(exc), status=409, code=exc.code, field_errors=exc.details)
    return _serialize_admin_extension_action_payload(extension)

