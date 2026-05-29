from __future__ import annotations


def classify_extension_diagnostics(item: dict) -> dict:
    blocking_reasons = []
    warning_reasons = []

    if not item.get("healthy", True):
        blocking_reasons.append("运行时健康检查未通过")

    if item.get("runtime_issues"):
        blocking_reasons.append("存在运行时问题")

    if item.get("dependency_state") not in {"", "healthy"}:
        blocking_reasons.append("依赖状态异常")

    migration_execution = item.get("migration_execution") or {}
    migration_status = str(migration_execution.get("status") or "").strip()
    if migration_status and migration_status not in {"ok", "skipped"}:
        blocking_reasons.append("最近迁移执行异常")

    migration_plan = item.get("migration_plan") or {}
    pending_migration_files = migration_plan.get("pending_files") or []

    delivery_checks = item.get("delivery_checks") or []
    for check in delivery_checks:
        if check.get("status") != "attention":
            continue
        if check.get("optional"):
            warning_reasons.append(f"{check.get('label') or check.get('key')}: {check.get('status_label') or '需关注'}")
        else:
            blocking_reasons.append(f"{check.get('label') or check.get('key')}: {check.get('status_label') or '需关注'}")

    if item.get("migration_state") == "attention":
        blocking_reasons.append("迁移状态异常")
    elif item.get("migration_state") in {"pending"} or pending_migration_files:
        warning_reasons.append("迁移状态待完善")

    return {
        "blocking": bool(blocking_reasons),
        "warning": bool(warning_reasons),
        "has_attention": bool(blocking_reasons or warning_reasons),
        "blocking_reasons": _dedupe(blocking_reasons),
        "warning_reasons": _dedupe(warning_reasons),
    }


def summarize_extension_diagnostics(items: list[dict]) -> dict:
    results = [classify_extension_diagnostics(item) for item in items]
    return {
        "blocking_count": sum(1 for item in results if item["blocking"]),
        "warning_count": sum(1 for item in results if item["warning"]),
        "attention_count": sum(1 for item in results if item["has_attention"]),
    }


def summarize_extension_delivery(items: list[dict]) -> dict:
    return {
        "asset_count": sum(int((item.get("delivery_assets") or {}).get("asset_count") or 0) for item in items),
        "frontend_bundle_count": sum(
            1 for item in items
            if _has_delivery_asset(item, "frontend_admin_entry") or _has_delivery_asset(item, "frontend_forum_entry")
        ),
        "migration_bundle_count": sum(1 for item in items if _has_delivery_asset(item, "migrations")),
        "locale_bundle_count": sum(1 for item in items if _has_delivery_asset(item, "locale")),
        "signed_extension_count": sum(1 for item in items if _has_delivery_asset(item, "signature")),
    }


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    results = []
    for item in items:
        key = str(item or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        results.append(key)
    return results


def _has_delivery_asset(item: dict, key: str) -> bool:
    delivery_assets = item.get("delivery_assets") or {}
    assets = delivery_assets.get("assets") or []
    return any(
        asset.get("key") == key and asset.get("exists")
        for asset in assets
        if isinstance(asset, dict)
    )
