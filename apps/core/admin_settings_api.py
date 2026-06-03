import json

from ninja import Body, Router

from apps.core.jwt_auth import AccessTokenAuth


router = Router()


def _legacy():
    from apps.core import admin_api as legacy

    return legacy


def _require_staff(request):
    legacy = _legacy()
    if not request.auth or not request.auth.is_staff:
        return legacy.admin_error("需要管理员权限", status=403)
    return None


@router.get("/stats", auth=AccessTokenAuth(), tags=["Admin"])
def get_stats(request):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    advanced_settings = legacy.get_runtime_advanced_settings()
    queue_driver = advanced_settings.get("queue_driver", "sync")
    queue_enabled = bool(advanced_settings.get("queue_enabled", False))
    queue_worker_status = legacy.QueueService.get_worker_status()
    queue_metrics = legacy.QueueService.get_metrics()
    database_label = legacy.detect_database_label()
    cache_driver = legacy.detect_cache_driver()
    realtime_driver = legacy.detect_realtime_driver()
    redis_enabled = legacy.is_redis_enabled(queue_enabled=queue_enabled, queue_driver=queue_driver)
    cache_connection = legacy._probe_cache_connection()
    realtime_connection = legacy._probe_realtime_connection()
    queue_broker_connection = legacy._probe_queue_broker_connection(queue_enabled, queue_driver)
    runtime_risks = legacy.build_runtime_risks(
        debug_mode=legacy.settings.DEBUG,
        database_label=database_label,
        cache_driver=cache_driver,
        realtime_driver=realtime_driver,
        queue_enabled=queue_enabled,
        queue_driver=queue_driver,
        queue_worker_status=queue_worker_status,
        redis_enabled=redis_enabled,
        cache_connection=cache_connection,
        realtime_connection=realtime_connection,
        queue_broker_connection=queue_broker_connection,
    )
    auth_secret_status = legacy.build_auth_secret_status()
    runtime_dependency_checks = legacy.build_runtime_dependency_checks(
        cache_connection=cache_connection,
        realtime_connection=realtime_connection,
        queue_broker_connection=queue_broker_connection,
        queue_worker_status=queue_worker_status,
    )

    return {
        "runtimeName": "Python",
        "pythonVersion": legacy.sys.version.split()[0],
        "djangoVersion": legacy.django.get_version(),
        "databaseLabel": database_label,
        "cacheDriver": cache_driver,
        "queueDriver": queue_driver,
        "queueEnabled": queue_enabled,
        "queueLabel": legacy.detect_queue_driver_label(queue_enabled, queue_driver),
        "queueWorkerStatus": queue_worker_status["status"],
        "queueWorkerLabel": queue_worker_status["label"],
        "queueWorkerAvailable": queue_worker_status["available"],
        "queueWorkerCount": queue_worker_status["worker_count"],
        "queueWorkerMessage": queue_worker_status["message"],
        "queueMetrics": queue_metrics,
        "realtimeDriver": realtime_driver,
        "redisEnabled": redis_enabled,
        "cacheConnectionStatus": cache_connection["status"],
        "cacheConnectionLabel": cache_connection["label"],
        "cacheConnectionAvailable": cache_connection["available"],
        "cacheConnectionMessage": cache_connection["message"],
        "realtimeConnectionStatus": realtime_connection["status"],
        "realtimeConnectionLabel": realtime_connection["label"],
        "realtimeConnectionAvailable": realtime_connection["available"],
        "realtimeConnectionMessage": realtime_connection["message"],
        "queueBrokerStatus": queue_broker_connection["status"],
        "queueBrokerLabel": queue_broker_connection["label"],
        "queueBrokerAvailable": queue_broker_connection["available"],
        "queueBrokerMessage": queue_broker_connection["message"],
        "runtimeDependencyChecks": runtime_dependency_checks,
        "runtimeRisks": runtime_risks,
        "authSecretStatus": auth_secret_status["status"],
        "authSecretLabel": auth_secret_status["label"],
        "authSecretMessage": auth_secret_status["message"],
        "debugMode": legacy.settings.DEBUG,
        "maintenanceMode": bool(advanced_settings.get("maintenance_mode", False)),
        "totalUsers": legacy.User.objects.count(),
        "totalDiscussions": legacy.Discussion.objects.count(),
        "totalPosts": legacy.Post.objects.count(),
        "openFlags": legacy.PostFlag.objects.filter(status=legacy.PostFlag.STATUS_OPEN).count(),
        "pendingApprovals": (
            legacy.Discussion.objects.filter(approval_status=legacy.Discussion.APPROVAL_PENDING).count()
            + legacy.Post.objects.filter(approval_status=legacy.Post.APPROVAL_PENDING).exclude(
                id__in=legacy.Discussion.objects.filter(
                    approval_status=legacy.Discussion.APPROVAL_PENDING
                ).values_list("first_post_id", flat=True)
            ).count()
        ),
    }


@router.post("/queue/metrics/reset", auth=AccessTokenAuth(), tags=["Admin"])
def reset_queue_metrics(request):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    metrics = legacy.QueueService.reset_metrics()
    legacy.log_admin_action(request, "admin.queue_metrics.reset", data={"metrics": metrics})
    return {
        "message": "队列运行指标已重置",
        "metrics": metrics,
    }


@router.get("/settings", auth=AccessTokenAuth(), tags=["Admin"])
def get_settings(request):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    return legacy.get_setting_group("basic", legacy.BASIC_SETTINGS_DEFAULTS)


@router.post("/settings", auth=AccessTokenAuth(), tags=["Admin"])
def save_settings(request, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    settings_data = legacy.save_setting_group("basic", legacy.BASIC_SETTINGS_DEFAULTS, payload)
    legacy.log_admin_action(
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

    legacy = _legacy()
    return legacy.get_setting_group("appearance", legacy.APPEARANCE_SETTINGS_DEFAULTS)


@router.post("/appearance", auth=AccessTokenAuth(), tags=["Admin"])
def save_appearance_settings(request, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    settings_data = legacy.save_setting_group("appearance", legacy.APPEARANCE_SETTINGS_DEFAULTS, payload)
    legacy.log_admin_action(
        request,
        "admin.settings.update",
        target_type="settings",
        data={"group": "appearance", "keys": sorted(payload.keys())},
    )
    return {"message": "外观设置保存成功", "settings": settings_data}


@router.post("/appearance/upload", auth=AccessTokenAuth(), tags=["Admin"])
def upload_appearance_asset(request, target: str):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    if target not in {"logo", "favicon"}:
        return legacy.admin_error("仅支持上传 logo 或 favicon", status=400)

    file = request.FILES.get("file")
    if not file:
        return legacy.admin_error("请选择要上传的文件", status=400)

    try:
        file_url, file_info = legacy.FileUploadService.upload_site_asset(file, target)
    except ValueError as exc:
        return legacy.admin_error(str(exc), status=400)

    legacy.log_admin_action(
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


@router.get("/mail", auth=AccessTokenAuth(), tags=["Admin"])
def get_mail_settings(request):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    return legacy.build_mail_settings_response(request.auth.email if request.auth else "")


@router.post("/mail", auth=AccessTokenAuth(), tags=["Admin"])
def save_mail_settings(request, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    normalized_payload = dict(payload)
    if "mail_from" in normalized_payload:
        mail_from_address, mail_from_name = legacy.parse_mail_from(normalized_payload.pop("mail_from"))
        normalized_payload["mail_from_address"] = mail_from_address
        normalized_payload["mail_from_name"] = mail_from_name

    defaults = legacy.get_mail_settings_defaults()
    settings_data = legacy.save_setting_group("mail", defaults, normalized_payload)
    expected_settings = legacy.serialize_mail_settings(settings_data)
    try:
        config_path = legacy.sync_mail_settings_to_site_config(settings_data)
    except Exception as exc:
        return legacy.admin_error(f"邮件设置写入站点配置失败: {exc}", status=500)

    response = legacy.build_mail_settings_response(request.auth.email if request.auth else "")
    if response.get("mail_from") != expected_settings.get("mail_from"):
        location = config_path or "数据库设置"
        return legacy.admin_error(
            "邮件设置保存后校验失败，运行时读取到的发件地址与刚保存的不一致。"
            f" 期望值: {expected_settings.get('mail_from') or '(空)'};"
            f" 实际值: {response.get('mail_from') or '(空)'};"
            f" 配置来源: {location}",
            status=500,
        )
    legacy.log_admin_action(
        request,
        "admin.settings.update",
        target_type="settings",
        data={"group": "mail", "keys": sorted(normalized_payload.keys())},
    )
    response["message"] = "邮件设置保存成功"
    response["settings"] = legacy.serialize_mail_settings(settings_data)
    return response


@router.post("/mail/test", auth=AccessTokenAuth(), tags=["Admin"])
def send_test_email(request):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    payload = {}
    if request.body:
        raw_body = request.body.decode("utf-8", errors="ignore").strip()
        content_type = str(request.headers.get("content-type") or "")
        should_parse_json = "application/json" in content_type or raw_body[:1] in {"{", "["}
        if should_parse_json:
            try:
                payload = json.loads(raw_body) if raw_body else {}
            except json.JSONDecodeError:
                return legacy.admin_error("测试邮件请求格式无效", status=400)
            if not isinstance(payload, dict):
                payload = {}

    mail_settings = legacy.get_setting_group("mail", legacy.get_mail_settings_defaults())
    to_email = (
        str(payload.get("to_email") or "").strip()
        or str(mail_settings.get("mail_test_recipient") or "").strip()
        or str(request.auth.email or "").strip()
    )
    if not to_email:
        return legacy.admin_error("请先填写测试收件箱", status=400)

    try:
        legacy.validate_email(to_email)
    except legacy.ValidationError:
        return legacy.admin_error("测试收件箱格式无效", status=400)

    try:
        sent_count = legacy.EmailService.send_test_email(to_email)
    except Exception as exc:
        return legacy.admin_error(str(exc), status=400)

    legacy.log_admin_action(
        request,
        "admin.mail.test",
        target_type="mail",
        data={"to_email": to_email, "sent_count": sent_count},
    )
    return {"message": "测试邮件已发送", "sent_count": sent_count, "to_email": to_email}


@router.get("/advanced", auth=AccessTokenAuth(), tags=["Admin"])
def get_advanced_settings(request):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    return legacy.get_runtime_advanced_settings()


@router.post("/advanced", auth=AccessTokenAuth(), tags=["Admin"])
def save_advanced_settings(request, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    runtime_payload = dict(payload)
    runtime_payload.pop("debug_mode", None)
    validation_errors = legacy.validate_advanced_runtime_settings(runtime_payload)
    if validation_errors:
        return legacy.admin_error(
            "；".join(validation_errors),
            status=400,
            code="invalid_runtime_configuration",
            field_errors={"advanced": validation_errors},
        )

    settings_data = legacy.save_setting_group("advanced", legacy.ADVANCED_SETTINGS_DEFAULTS, runtime_payload)
    settings_data["debug_mode"] = legacy.get_runtime_advanced_settings()["debug_mode"]
    legacy.log_admin_action(
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

    legacy = _legacy()
    try:
        legacy.cache.clear()
        legacy.clear_runtime_setting_caches()
        from apps.core.extensions.event_bus import get_extension_event_bus
        from apps.core.extensions.events import RuntimeCacheClearedEvent
        from apps.core.extensions.runtime_event_listeners import bootstrap_extension_runtime_event_listeners

        bootstrap_extension_runtime_event_listeners()
        get_extension_event_bus().dispatch(RuntimeCacheClearedEvent())
    except Exception as exc:
        return legacy.admin_error(f"缓存清理失败: {exc}", status=503)

    legacy.log_admin_action(request, "admin.cache.clear", target_type="cache")
    return {"message": "缓存已清除"}


@router.get("/search-indexes/status", auth=AccessTokenAuth(), tags=["Admin"])
def get_search_index_status(request):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    queue_worker_status = legacy.QueueService.get_worker_status()
    latest_rebuild = legacy.AuditLog.objects.filter(action="admin.search_indexes.rebuild").first()
    search_index_status = legacy.SearchIndexService.get_status()

    last_rebuild = None
    if latest_rebuild:
        last_rebuild = {
            "created_at": latest_rebuild.created_at,
            "duration_ms": latest_rebuild.data.get("duration_ms", 0),
            "indexes": latest_rebuild.data.get("indexes", []),
        }

    return {
        **search_index_status,
        "databaseLabel": legacy.detect_database_label(),
        "lastRebuild": last_rebuild,
        "queueWorkerStatus": queue_worker_status["status"],
        "queueWorkerLabel": queue_worker_status["label"],
        "queueWorkerAvailable": queue_worker_status["available"],
        "queueWorkerCount": queue_worker_status["worker_count"],
        "queueWorkerMessage": queue_worker_status["message"],
    }


@router.post("/search-indexes/rebuild", auth=AccessTokenAuth(), tags=["Admin"])
def rebuild_search_indexes(request):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    try:
        result = legacy.SearchIndexService.rebuild_postgres_indexes()
    except RuntimeError as exc:
        return legacy.admin_error(str(exc), status=400)
    except Exception as exc:
        return legacy.admin_error(f"搜索索引重建失败: {exc}", status=503)

    legacy.log_admin_action(
        request,
        "admin.search_indexes.rebuild",
        target_type="search_index",
        data={
            "indexes": result.get("indexes", []),
            "duration_ms": result.get("duration_ms", 0),
        },
    )
    return result
