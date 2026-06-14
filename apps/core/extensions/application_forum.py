from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apps.core.extensions.application_types import ApplicationForumPermissionChecker

if TYPE_CHECKING:
    from apps.core.extensions.application import ExtensionHost
    from apps.core.forum_registry import ForumRegistry
    from apps.core.resource_registry import ResourceRegistry


class ApplicationForumPermissionService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host

    def register_checker(
        self,
        extension_id: str,
        key: str,
        handler,
        *,
        description: str = "",
    ) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_key = str(key or "").strip()
        if not normalized_extension_id or not normalized_key or not callable(handler):
            return

        definition = ApplicationForumPermissionChecker(
            key=normalized_key,
            handler=handler,
            description=str(description or "").strip(),
            module_id=normalized_extension_id,
        )
        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        view.forum_permission_checkers = tuple([
            *(
                item
                for item in view.forum_permission_checkers
                if str(getattr(item, "key", "") or "").strip() != normalized_key
            ),
            definition,
        ])

        from apps.core.forum_permissions import register_forum_permission_checker

        register_forum_permission_checker(f"{normalized_extension_id}:{normalized_key}", handler)

    def get_checkers(self, *, extension_id: str | None = None) -> list[ApplicationForumPermissionChecker]:
        if extension_id is not None:
            view = self._host.get_runtime_view(extension_id)
            if view is None:
                return []
            return list(view.forum_permission_checkers)

        definitions: list[ApplicationForumPermissionChecker] = []
        for view in self._host.get_runtime_views():
            definitions.extend(view.forum_permission_checkers)
        return definitions


class ApplicationDiscussionLifecycleService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host

    def register(self, extension_id: str, definition) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_key = str(getattr(definition, "key", "") or "").strip()
        if not normalized_extension_id or not normalized_key:
            return

        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        view.discussion_lifecycle = tuple([
            *(
                item
                for item in view.discussion_lifecycle
                if str(getattr(item, "key", "") or "").strip() != normalized_key
            ),
            definition,
        ])

    def prepare_create(self, *, user, payload: dict, context: dict | None = None) -> dict:
        return self._run_phase("prepare_create", user=user, payload=payload, context=context)

    def apply_create(self, *, discussion, states: dict, context: dict | None = None) -> dict:
        return self._apply_phase("apply_create", discussion=discussion, states=states, context=context)

    def prepare_update(self, *, discussion, user, payload: dict, context: dict | None = None) -> dict:
        return self._run_phase("prepare_update", discussion=discussion, user=user, payload=payload, context=context)

    def apply_update(self, *, discussion, states: dict, context: dict | None = None) -> dict:
        return self._apply_phase("apply_update", discussion=discussion, states=states, context=context)

    def prepare_delete(self, *, discussion, user, context: dict | None = None) -> dict:
        return self._run_phase("prepare_delete", discussion=discussion, user=user, context=context)

    def apply_delete(self, *, states: dict, context: dict | None = None) -> dict:
        return self._apply_phase("apply_delete", states=states, context=context)

    def apply_hidden(self, *, discussion, context: dict | None = None) -> dict:
        return self._apply_phase("apply_hidden", discussion=discussion, states={}, context=context)

    def apply_approved(self, *, discussion, context: dict | None = None) -> dict:
        return self._apply_phase("apply_approved", discussion=discussion, states={}, context=context)

    def apply_rejected(self, *, discussion, context: dict | None = None) -> dict:
        return self._apply_phase("apply_rejected", discussion=discussion, states={}, context=context)

    def get_definitions(self, *, extension_id: str | None = None) -> list:
        if extension_id is not None:
            view = self._host.get_runtime_view(extension_id)
            if view is None:
                return []
            return list(view.discussion_lifecycle)

        definitions: list = []
        for view in self._host.get_runtime_views():
            definitions.extend(view.discussion_lifecycle)
        return definitions

    def _run_phase(self, phase: str, **kwargs) -> dict:
        states = {}
        for definition in self.get_definitions():
            handler = getattr(definition, phase, None)
            if not callable(handler):
                continue
            result = handler(**kwargs)
            if result is not None:
                states[definition.key] = result
        return states

    def _apply_phase(self, phase: str, *, states: dict, **kwargs) -> dict:
        results = {}
        for definition in self.get_definitions():
            handler = getattr(definition, phase, None)
            if not callable(handler):
                continue
            state = states.get(definition.key)
            result = handler(state=state, **kwargs)
            if isinstance(result, dict):
                results[definition.key] = result
        return results


class ApplicationPostLifecycleService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host

    def register(self, extension_id: str, definition) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_key = str(getattr(definition, "key", "") or "").strip()
        if not normalized_extension_id or not normalized_key:
            return

        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        view.post_lifecycle = tuple([
            *(
                item
                for item in view.post_lifecycle
                if str(getattr(item, "key", "") or "").strip() != normalized_key
            ),
            definition,
        ])

    def apply_created(self, *, post, context: dict | None = None) -> dict:
        return self._apply_phase("apply_created", post=post, context=context)

    def apply_updated(self, *, post, context: dict | None = None) -> dict:
        return self._apply_phase("apply_updated", post=post, context=context)

    def apply_approved(self, *, post, context: dict | None = None) -> dict:
        return self._apply_phase("apply_approved", post=post, context=context)

    def apply_hidden(self, *, post, context: dict | None = None) -> dict:
        return self._apply_phase("apply_hidden", post=post, context=context)

    def prepare_delete(self, *, post, context: dict | None = None) -> dict:
        return self._apply_phase("prepare_delete", post=post, context=context)

    def apply_deleted(self, *, context: dict | None = None) -> dict:
        return self._apply_phase("apply_deleted", context=context)

    def get_definitions(self, *, extension_id: str | None = None) -> list:
        if extension_id is not None:
            view = self._host.get_runtime_view(extension_id)
            if view is None:
                return []
            return list(view.post_lifecycle)

        definitions: list = []
        for view in self._host.get_runtime_views():
            definitions.extend(view.post_lifecycle)
        return definitions

    def _apply_phase(self, phase: str, **kwargs) -> dict:
        results = {}
        for definition in self.get_definitions():
            handler = getattr(definition, phase, None)
            if not callable(handler):
                continue
            result = handler(**kwargs)
            if isinstance(result, dict):
                results[definition.key] = result
        return results


class ApplicationForumService:
    def __init__(self, host: "ExtensionHost", registry: "ForumRegistry") -> None:
        self._host = host
        self._registry = registry

    def register_permission(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_permission(definition)
        self._append_extension_tuple(extension_id, "permissions", definition)

    def register_admin_page(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_admin_page(definition)
        self._append_extension_tuple(extension_id, "admin_pages", definition)

    def register_notification_type(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_notification_type(definition)
        self._append_extension_tuple(extension_id, "notification_types", definition)

    def register_user_preference(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_user_preference(definition)
        self._append_extension_tuple(extension_id, "user_preferences", definition)

    def register_language_pack(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_language_pack(definition)
        self._append_extension_tuple(extension_id, "language_packs", definition)

    def register_post_type(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_post_type(definition)
        self._append_extension_tuple(extension_id, "post_types", definition)

    def register_search_filter(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_search_filter(definition)
        self._append_extension_tuple(extension_id, "search_filters", definition)

    def register_discussion_list_query(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_discussion_list_query(definition)
        self._append_extension_tuple(extension_id, "discussion_list_queries", definition)

    def register_discussion_sort(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_discussion_sort(definition)
        self._append_extension_tuple(extension_id, "discussion_sorts", definition)

    def register_discussion_list_filter(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_discussion_list_filter(definition)
        self._append_extension_tuple(extension_id, "discussion_list_filters", definition)

    def register_external_module_id(self, module_id: str) -> None:
        self._registry.register_external_module_id(module_id)

    def _append_extension_tuple(self, extension_id: str, field_name: str, definition: Any) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        view = self._host._get_or_create_runtime_view(normalized)
        setattr(view, field_name, tuple([*getattr(view, field_name), definition]))

    def __getattr__(self, item: str) -> Any:
        return getattr(self._registry, item)


class ApplicationResourceService:
    def __init__(self, host: "ExtensionHost", registry: "ResourceRegistry") -> None:
        self._host = host
        self._registry = registry

    def register_resource(self, definition, *, extension_id: str = "") -> None:
        registered = self._registry.register_resource(definition)
        self._append_extension_tuple(extension_id, "resource_definitions", registered)

    def register_field(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_field(definition)
        self._append_extension_tuple(extension_id, "resource_fields", definition)

    def register_field_mutator(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_field_mutator(definition)
        self._append_extension_tuple(extension_id, "resource_field_mutators", definition)

    def register_relationship(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_relationship(definition)
        self._append_extension_tuple(extension_id, "resource_relationships", definition)

    def register_endpoint(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_endpoint(definition)
        self._append_extension_tuple(extension_id, "resource_endpoints", definition)

    def register_sort(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_sort(definition)
        self._append_extension_tuple(extension_id, "resource_sorts", definition)

    def register_filter(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_filter(definition)
        self._append_extension_tuple(extension_id, "resource_filters", definition)

    def _append_extension_tuple(self, extension_id: str, field_name: str, definition: Any) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        view = self._host._get_or_create_runtime_view(normalized)
        setattr(view, field_name, tuple([*getattr(view, field_name), definition]))

    def __getattr__(self, item: str) -> Any:
        return getattr(self._registry, item)
