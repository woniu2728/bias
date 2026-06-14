from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.core.extensions.application import ExtensionHost


class ApplicationSettingsService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host

    def register_fields(
        self,
        extension_id: str,
        fields,
        *,
        expose_to_forum=(),
        generated_page: bool = True,
        defaults=(),
        reset_when=(),
        reset_frontend_cache_for=(),
        theme_variables=(),
        forum_serializations=(),
    ) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id:
            return

        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        fields_collection = list(view.settings_schema)
        for field in fields or ():
            fields_collection.append(field)
        view.settings_schema = tuple(fields_collection)

        default_collection = list(view.settings_defaults)
        for definition in defaults or ():
            if getattr(definition, "key", ""):
                default_collection.append(definition)
        view.settings_defaults = tuple(default_collection)

        reset_collection = list(view.settings_reset_rules)
        for definition in reset_when or ():
            if getattr(definition, "key", "") and callable(getattr(definition, "callback", None)):
                reset_collection.append(definition)
        view.settings_reset_rules = tuple(reset_collection)

        cache_keys = list(view.settings_frontend_cache_keys)
        for key in reset_frontend_cache_for or ():
            normalized_key = str(key or "").strip()
            if normalized_key and normalized_key not in cache_keys:
                cache_keys.append(normalized_key)
        view.settings_frontend_cache_keys = tuple(cache_keys)

        theme_collection = list(view.settings_theme_variables)
        for definition in theme_variables or ():
            if getattr(definition, "name", "") and getattr(definition, "key", ""):
                theme_collection.append(definition)
        view.settings_theme_variables = tuple(theme_collection)

        forum_serialization_collection = list(view.settings_forum_serializations)
        for definition in forum_serializations or ():
            if getattr(definition, "attribute", "") and getattr(definition, "key", ""):
                forum_serialization_collection.append(definition)
        view.settings_forum_serializations = tuple(forum_serialization_collection)

        forum_keys = list(view.forum_settings_keys)
        for key in expose_to_forum or ():
            normalized_key = str(key or "").strip()
            if normalized_key and normalized_key not in forum_keys:
                forum_keys.append(normalized_key)
        view.forum_settings_keys = tuple(forum_keys)

        if generated_page:
            view.use_generated_settings_page = True
            self._host.frontend.register_pages(
                normalized_extension_id,
                settings_pages=(f"/admin/extensions/{normalized_extension_id}/settings",),
            )


class ApplicationAdminActionService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host

    def register_runtime_actions(
        self,
        extension_id: str,
        actions,
        *,
        generated_page: bool = False,
    ) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id:
            return

        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        collection = list(view.runtime_actions)
        for action in actions or ():
            collection.append(action)
        view.runtime_actions = tuple(collection)

        if generated_page:
            view.use_generated_operations_page = True
            self._host.frontend.register_pages(
                normalized_extension_id,
                operations_pages=(f"/admin/extensions/{normalized_extension_id}/operations",),
            )

    def register_admin_actions(
        self,
        extension_id: str,
        actions,
        *,
        generated_permissions_page: bool = False,
        generated_operations_page: bool = False,
    ) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id:
            return

        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        collection = list(view.admin_actions)
        for action in actions or ():
            collection.append(action)
        view.admin_actions = tuple(collection)

        if generated_permissions_page:
            view.use_generated_permissions_page = True
            self._host.frontend.register_pages(
                normalized_extension_id,
                permissions_pages=(f"/admin/extensions/{normalized_extension_id}/permissions",),
            )
        if generated_operations_page:
            view.use_generated_operations_page = True
            self._host.frontend.register_pages(
                normalized_extension_id,
                operations_pages=(f"/admin/extensions/{normalized_extension_id}/operations",),
            )

    def mark_generated_permissions_page(self, extension_id: str) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id:
            return

        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        view.use_generated_permissions_page = True
        self._host.frontend.register_pages(
            normalized_extension_id,
            permissions_pages=(f"/admin/extensions/{normalized_extension_id}/permissions",),
        )
