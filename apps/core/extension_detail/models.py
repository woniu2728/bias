from __future__ import annotations

from apps.core.extension_django_apps import normalize_extension_django_app_label
from apps.core.extensions.runtime_probe import inspect_extension_runtime

def _build_extension_model_definitions(runtime_view):
    if runtime_view is None:
        return []
    definitions = [
        {
            "model": _model_name(item.model),
            "key": item.key,
            "kind": item.kind,
            "description": item.description,
        }
        for item in getattr(runtime_view, "model_definitions", ()) or ()
    ]
    definitions.extend([
        {
            "model": _model_name(item.model),
            "key": item.name,
            "kind": f"relation:{item.relation_type}",
            "description": item.description,
        }
        for item in getattr(runtime_view, "model_relations", ()) or ()
    ])
    definitions.extend([
        {
            "model": _model_name(item.model),
            "key": item.attribute,
            "kind": "cast",
            "description": item.description,
        }
        for item in getattr(runtime_view, "model_casts", ()) or ()
    ])
    definitions.extend([
        {
            "model": _model_name(item.model),
            "key": item.attribute,
            "kind": "default",
            "description": item.description,
        }
        for item in getattr(runtime_view, "model_defaults", ()) or ()
    ])
    definitions.extend([
        {
            "model": _model_name(item.model),
            "key": item.identifier,
            "kind": "model-url:slug",
            "description": item.description,
        }
        for item in getattr(runtime_view, "model_slug_drivers", ()) or ()
    ])
    return definitions

def _build_extension_owned_models(runtime_view, *, extension=None):
    if runtime_view is None:
        return []
    items = []
    target_app_label = _extension_app_label(runtime_view.extension_id, extension=extension)
    target_app_label_source = _extension_app_label_source(extension)
    for item in getattr(runtime_view, "model_definitions", ()) or ():
        if item.kind != "owner":
            continue
        model = item.model
        current_app_label = _model_app_label(model)
        package_migration_required = _model_package_migration_required(model, runtime_view.extension_id)
        app_label_migration_required = _model_app_label_migration_required(
            model,
            runtime_view.extension_id,
            extension=extension,
        )
        items.append({
            "module_id": runtime_view.extension_id,
            "model": _model_name(model),
            "model_label": _model_label(model),
            "model_module": _model_module(model),
            "app_label": current_app_label,
            "current_app_label": current_app_label,
            "target_app_label": target_app_label,
            "target_app_label_source": target_app_label_source,
            "db_table": _model_db_table(model),
            "storage_origin": _model_storage_origin(model, runtime_view.extension_id),
            "package_migration_required": package_migration_required,
            "app_label_migration_required": app_label_migration_required,
            "migration_risk": _model_migration_risk(
                package_migration_required=package_migration_required,
                app_label_migration_required=app_label_migration_required,
            ),
            "recommended_steps": _model_migration_recommended_steps(
                package_migration_required=package_migration_required,
                app_label_migration_required=app_label_migration_required,
            ),
            "key": item.key,
            "description": item.description,
        })
    return items

def _build_extension_model_ownership_audit(runtime_view, *, extension=None):
    if runtime_view is None:
        return {
            "owned_model_count": 0,
            "extension_native_count": 0,
            "django_app_count": 0,
            "package_migration_required_count": 0,
            "app_label_migration_required_count": 0,
            "target_app_label": "",
            "target_app_label_source": "",
            "items": [],
        }

    items = _build_extension_owned_models(runtime_view, extension=extension)
    return {
        "owned_model_count": len(items),
        "extension_native_count": sum(1 for item in items if item["storage_origin"] == "extension"),
        "django_app_count": sum(1 for item in items if item["storage_origin"] == "django_app"),
        "package_migration_required_count": sum(1 for item in items if item["package_migration_required"]),
        "app_label_migration_required_count": sum(1 for item in items if item["app_label_migration_required"]),
        "target_app_label": _extension_app_label(runtime_view.extension_id, extension=extension),
        "target_app_label_source": _extension_app_label_source(extension),
        "app_label_migration_plan_required_count": sum(
            1
            for item in items
            if item["app_label_migration_required"] and item["target_app_label"]
        ),
        "app_label_migration_items": [
            _build_model_app_label_migration_item(item)
            for item in items
            if item["app_label_migration_required"]
        ],
        "items": items,
    }

def _build_extension_model_relations(runtime_view):
    if runtime_view is None:
        return []
    return [
        {
            "module_id": runtime_view.extension_id,
            "model": _model_name(item.model),
            "name": item.name,
            "relation_type": item.relation_type,
            "related_model": _model_name(item.related_model),
            "foreign_key": item.foreign_key,
            "owner_key": item.owner_key,
            "inject_attribute": bool(getattr(item, "inject_attribute", True)),
            "description": item.description,
        }
        for item in getattr(runtime_view, "model_relations", ()) or ()
    ]

def _build_extension_model_visibility(runtime_view):
    if runtime_view is None:
        return []
    return [
        {
            "model": _model_name(item.model),
            "ability": item.ability,
            "description": item.description,
        }
        for item in getattr(runtime_view, "model_visibility", ()) or ()
    ]

def _resolve_display_model(model):
    from apps.core.extensions.model_references import resolve_model_reference

    return resolve_model_reference(model) or model

def _model_name(model) -> str:
    resolved_model = _resolve_display_model(model)
    return str(getattr(resolved_model, "__name__", "") or str(resolved_model))

def _model_label(model) -> str:
    model = _resolve_display_model(model)
    meta = getattr(model, "_meta", None)
    label = str(getattr(meta, "label", "") or getattr(meta, "label_lower", "") or "").strip()
    if label:
        return label
    module = str(getattr(model, "__module__", "") or "").strip()
    name = str(getattr(model, "__name__", "") or getattr(model, "__qualname__", "") or "").strip()
    return ".".join(item for item in (module, name) if item) or str(model)

def _model_module(model) -> str:
    model = _resolve_display_model(model)
    return str(getattr(model, "__module__", "") or "").strip()

def _model_app_label(model) -> str:
    model = _resolve_display_model(model)
    meta = getattr(model, "_meta", None)
    return str(getattr(meta, "app_label", "") or "").strip()

def _extension_app_label(extension_id: str, *, extension=None) -> str:
    manifest_label = str(getattr(getattr(extension, "manifest", None), "django_app_label", "") or "").strip()
    return normalize_extension_django_app_label(extension_id, manifest_label)

def _extension_app_label_source(extension=None) -> str:
    manifest_label = str(getattr(getattr(extension, "manifest", None), "django_app_label", "") or "").strip()
    return "manifest" if manifest_label else "extension_id"

def _model_db_table(model) -> str:
    model = _resolve_display_model(model)
    meta = getattr(model, "_meta", None)
    return str(getattr(meta, "db_table", "") or "").strip()

def _model_storage_origin(model, extension_id: str) -> str:
    module = _model_module(model)
    extension_module = f"extensions.{str(extension_id or '').replace('-', '_')}."
    if module.startswith(extension_module):
        return "extension"
    if module.startswith("extensions."):
        return "extension-other"
    if module.startswith("apps."):
        return "django_app"
    return "external"

def _model_package_migration_required(model, extension_id: str) -> bool:
    return _model_storage_origin(model, extension_id) == "django_app"

def _model_app_label_migration_required(model, extension_id: str, *, extension=None) -> bool:
    app_label = _model_app_label(model)
    expected = _extension_app_label(extension_id, extension=extension)
    return bool(app_label and expected and app_label != expected)

def _model_migration_risk(*, package_migration_required: bool, app_label_migration_required: bool) -> str:
    if app_label_migration_required:
        return "high"
    if package_migration_required:
        return "medium"
    return "none"

def _model_migration_recommended_steps(
    *,
    package_migration_required: bool,
    app_label_migration_required: bool,
) -> list[str]:
    steps = []
    if package_migration_required:
        steps.append("将模型定义迁入扩展 backend/models.py，并从核心 Django app model 文件移除实体定义。")
    if app_label_migration_required:
        steps.extend([
            "新增目标扩展 app label 的状态迁移，使用 SeparateDatabaseAndState 保留现有数据表。",
            "将模型 Meta.app_label 切换为目标扩展 app label，并明确 ContentType/Permission 迁移策略。",
            "运行 makemigrations --check、扩展安装迁移和卸载回滚测试，确认不会生成删表建表操作。",
        ])
    return steps

def _build_model_app_label_migration_item(item: dict) -> dict:
    return {
        "module_id": item.get("module_id") or "",
        "model": item.get("model") or "",
        "model_label": item.get("model_label") or "",
        "current_app_label": item.get("current_app_label") or item.get("app_label") or "",
        "target_app_label": item.get("target_app_label") or "",
        "db_table": item.get("db_table") or "",
        "migration_risk": item.get("migration_risk") or "high",
        "recommended_steps": list(item.get("recommended_steps") or ()),
    }

def _serialize_extension_migration_execution(extension):
    payload = dict(extension.runtime.migration_execution or {})
    if not payload:
        return None
    return {
        "state": str(payload.get("state") or ""),
        "label": str(payload.get("label") or ""),
        "status": str(payload.get("status") or ""),
        "status_label": str(payload.get("status_label") or ""),
        "message": str(payload.get("message") or ""),
        "executed_at": str(payload.get("executed_at") or ""),
        "details": dict(payload.get("details") or {}),
    }

def _serialize_extension_migration_plan(extension):
    payload = dict(inspect_extension_runtime(extension).get("migration_plan") or {})
    return {
        "declared_files": list(payload.get("declared_files") or []),
        "applied_files": list(payload.get("applied_files") or []),
        "pending_files": list(payload.get("pending_files") or []),
    }
