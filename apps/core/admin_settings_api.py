from django.conf import settings
from django.core.cache import cache

from ninja import Body, Router

from apps.core import runtime_diagnostics
from apps.core.admin_auth import require_staff
from apps.core.api_errors import api_error
from apps.core.audit import log_admin_action
from apps.core.jwt_auth import AccessTokenAuth
from apps.core.mail_drivers import (
    can_mail_driver_send,
    get_driver_definitions,
    parse_mail_from,
    serialize_mail_settings,
    validate_mail_settings,
)
from apps.core.runtime_diagnostics import (
    detect_database_label,
    detect_realtime_driver,
)
from apps.core.settings_service import (
    APPEARANCE_SETTINGS_DEFAULTS,
    BASIC_SETTINGS_DEFAULTS,
    clear_runtime_setting_caches,
    get_advanced_settings as get_runtime_advanced_settings,
    get_advanced_settings_defaults,
    get_mail_settings as get_runtime_mail_settings,
    get_mail_settings_defaults,
    get_setting_group,
    save_setting_group,
    sync_mail_settings_to_site_config,
)


router = Router()


_require_staff = require_staff


def _build_mail_settings_response(admin_email: str = "") -> dict:
    settings_data = get_runtime_mail_settings()
    errors = validate_mail_settings(settings_data)
    driver_definitions = get_driver_definitions()
    effective_test_to_email = (
        str(settings_data.get("mail_test_recipient") or "").strip()
        or str(admin_email or "").strip()
    )
    settings_data.update({
        "drivers": driver_definitions,
        "driver_options": [
            {"value": key, "label": value.get("label") or key}
            for key, value in driver_definitions.items()
        ],
        "sending": can_mail_driver_send(settings_data, errors),
        "errors": errors,
        "mail_test_recipient": str(settings_data.get("mail_test_recipient") or "").strip(),
        "test_to_email": effective_test_to_email,
    })
    return settings_data


def _validate_advanced_runtime_settings(payload: dict) -> list[str]:
    return runtime_diagnostics.validate_advanced_runtime_settings(
        payload,
        database_label=detect_database_label(),
        realtime_driver=detect_realtime_driver(),
    )


@router.get("/settings", auth=AccessTokenAuth(), tags=["Admin"])
def get_settings(request):
    denied = _require_staff(request)
    if denied:
        return denied

    return get_setting_group("basic", BASIC_SETTINGS_DEFAULTS)


@router.post("/settings", auth=AccessTokenAuth(), tags=["Admin"])
def save_settings(request, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied

    settings_data = save_setting_group("basic", BASIC_SETTINGS_DEFAULTS, payload)
    log_admin_action(
        request,
        "admin.settings.update",
        target_type="settings",
        data={"group": "basic", "keys": sorted(payload.keys())},
    )
    return {"message": "设置保存成功", "settings": settings_data}


@router.get("/appearance", auth=AccessTokenAuth(), tags=["Admin"])
def get_appearance_settings(request):
    denied = _require_staff(request)
    if denied:
        return denied

    return get_setting_group("appearance", APPEARANCE_SETTINGS_DEFAULTS)


@router.post("/appearance", auth=AccessTokenAuth(), tags=["Admin"])
def save_appearance_settings(request, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied

    settings_data = save_setting_group("appearance", APPEARANCE_SETTINGS_DEFAULTS, payload)
    log_admin_action(
        request,
        "admin.settings.update",
        target_type="settings",
        data={"group": "appearance", "keys": sorted(payload.keys())},
    )
    return {"message": "外观设置保存成功", "settings": settings_data}


@router.get("/mail", auth=AccessTokenAuth(), tags=["Admin"])
def get_mail_settings(request):
    denied = _require_staff(request)
    if denied:
        return denied

    return _build_mail_settings_response(request.auth.email if request.auth else "")


@router.post("/mail", auth=AccessTokenAuth(), tags=["Admin"])
def save_mail_settings(request, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied

    normalized_payload = dict(payload)
    if "mail_from" in normalized_payload:
        mail_from_address, mail_from_name = parse_mail_from(normalized_payload.pop("mail_from"))
        normalized_payload["mail_from_address"] = mail_from_address
        normalized_payload["mail_from_name"] = mail_from_name

    defaults = get_mail_settings_defaults()
    settings_data = save_setting_group("mail", defaults, normalized_payload)
    expected_settings = serialize_mail_settings(settings_data)
    try:
        config_path = sync_mail_settings_to_site_config(settings_data)
    except Exception as exc:
        return api_error(f"邮件设置写入站点配置失败: {exc}", status=500)

    response = _build_mail_settings_response(request.auth.email if request.auth else "")
    if response.get("mail_from") != expected_settings.get("mail_from"):
        location = config_path or "数据库设置"
        return api_error(
            "邮件设置保存后校验失败，运行时读取到的发件地址与刚保存的不一致。"
            f" 期望值: {expected_settings.get('mail_from') or '(空)'};"
            f" 实际值: {response.get('mail_from') or '(空)'};"
            f" 配置来源: {location}",
            status=500,
        )
    log_admin_action(
        request,
        "admin.settings.update",
        target_type="settings",
        data={"group": "mail", "keys": sorted(normalized_payload.keys())},
    )
    response["message"] = "邮件设置保存成功"
    response["settings"] = serialize_mail_settings(settings_data)
    return response


@router.get("/advanced", auth=AccessTokenAuth(), tags=["Admin"])
def get_advanced_settings(request):
    denied = _require_staff(request)
    if denied:
        return denied

    return get_runtime_advanced_settings()


@router.post("/advanced", auth=AccessTokenAuth(), tags=["Admin"])
def save_advanced_settings(request, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied

    runtime_payload = dict(payload)
    runtime_payload.pop("debug_mode", None)
    if "maintenance_mode_key" in runtime_payload:
        runtime_payload["maintenance_mode"] = str(
            runtime_payload.get("maintenance_mode_key") or "none"
        ).strip().lower() != "none"
    validation_errors = _validate_advanced_runtime_settings(runtime_payload)
    if validation_errors:
        return api_error(
            "；".join(validation_errors),
            status=400,
            code="invalid_runtime_configuration",
            field_errors={"advanced": validation_errors},
        )

    settings_data = save_setting_group("advanced", get_advanced_settings_defaults(), runtime_payload)
    settings_data["debug_mode"] = get_runtime_advanced_settings()["debug_mode"]
    log_admin_action(
        request,
        "admin.settings.update",
        target_type="settings",
        data={"group": "advanced", "keys": sorted(runtime_payload.keys())},
    )
    return {"message": "高级设置保存成功", "settings": settings_data}


@router.post("/cache/clear", auth=AccessTokenAuth(), tags=["Admin"])
def clear_cache(request):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        cache.clear()
        clear_runtime_setting_caches()
        from apps.core.extensions.event_bus import get_extension_event_bus
        from apps.core.extensions.events import RuntimeCacheClearedEvent
        from apps.core.extensions.runtime_event_listeners import bootstrap_extension_runtime_event_listeners

        bootstrap_extension_runtime_event_listeners()
        get_extension_event_bus().dispatch(RuntimeCacheClearedEvent())
    except Exception as exc:
        return api_error(f"缓存清理失败: {exc}", status=503)

    log_admin_action(request, "admin.cache.clear", target_type="cache")
    return {"message": "缓存已清除"}
