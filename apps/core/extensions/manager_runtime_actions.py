from __future__ import annotations

from apps.core.extensions.extension_runtime import Extension
from apps.core.extensions.migrations import has_django_extension_migrations
from apps.core.extensions.product import is_extension_protected
from apps.core.extensions.types import ExtensionRuntimeActionDefinition


def build_runtime_actions(extension: Extension) -> tuple[ExtensionRuntimeActionDefinition, ...]:
    manifest_actions = build_manifest_runtime_actions(extension)
    migration_action = build_migration_runtime_action(extension)
    protected = is_extension_protected(extension)
    action_prefix = []
    if migration_action is not None:
        action_prefix.append(migration_action)
    action_prefix.extend(list(manifest_actions))

    if not extension.runtime.installed:
        return tuple([
            ExtensionRuntimeActionDefinition(
                key="install",
                label="安装扩展",
                action="install",
                tone="primary",
                confirm_title="安装扩展",
                confirm_message=f"确定安装 {extension.name} 吗？当前版本会登记为已安装并默认启用。",
                confirm_text="安装",
                success_message="扩展已安装并启用。",
                order=10,
            ),
            *action_prefix,
        ])

    actions = list(action_prefix)
    if extension.runtime.enabled:
        if not protected:
            actions.append(ExtensionRuntimeActionDefinition(
                key="disable",
                label="停用扩展",
                action="disable",
                tone="danger",
                confirm_title="停用扩展",
                confirm_message=f"确定停用 {extension.name} 吗？相关后台入口和运行能力会立即隐藏。",
                confirm_text="停用",
                success_message="扩展已停用。",
                requires_installed=True,
                order=20,
            ))
    else:
        actions.append(ExtensionRuntimeActionDefinition(
            key="enable",
            label="启用扩展",
            action="enable",
            tone="primary",
            confirm_title="启用扩展",
            confirm_message=f"确定启用 {extension.name} 吗？依赖校验通过后会立即恢复能力。",
            confirm_text="启用",
            success_message="扩展已启用。",
            requires_installed=True,
            order=10,
        ))
        if not protected:
            actions.append(ExtensionRuntimeActionDefinition(
                key="uninstall",
                label="卸载扩展",
                action="uninstall",
                tone="danger",
                confirm_title="卸载扩展",
                confirm_message=build_uninstall_confirm_message(extension),
                confirm_text="卸载",
                success_message="扩展已卸载。",
                requires_installed=True,
                order=30,
            ))

    return tuple(actions)


def build_manifest_runtime_actions(extension: Extension) -> tuple[ExtensionRuntimeActionDefinition, ...]:
    actions = []
    for action in sorted(extension.manifest_runtime_actions, key=lambda item: (item.order, item.key)):
        actions.append(ExtensionRuntimeActionDefinition(
            key=action.key,
            label=action.label,
            action=f"hook:{action.hook}",
            tone=action.tone,
            confirm_title=action.confirm_title,
            confirm_message=action.confirm_message,
            confirm_text=action.confirm_text,
            success_message=action.success_message,
            requires_enabled=action.requires_enabled,
            requires_installed=action.requires_installed,
            order=action.order,
        ))
    return tuple(actions)


def build_migration_runtime_action(extension: Extension) -> ExtensionRuntimeActionDefinition | None:
    if not extension.runtime.installed:
        return None
    if not has_django_extension_migrations(extension):
        return None
    return ExtensionRuntimeActionDefinition(
        key="migrations",
        label="执行迁移",
        action="migrations",
        tone="default",
        confirm_title="执行扩展迁移",
        confirm_message=f"确定执行 {extension.name} 的扩展迁移吗？该操作通常用于安装后补跑或同步迁移摘要。",
        confirm_text="执行",
        success_message="扩展迁移已执行。",
        requires_installed=True,
        order=15,
    )


def build_uninstall_confirm_message(extension: Extension) -> str:
    warnings = list(extension.runtime.uninstall_warnings or ())
    if not warnings:
        return f"确定卸载 {extension.name} 吗？"

    body = "；".join(warnings[:2])
    return f"确定卸载 {extension.name} 吗？{body}"
