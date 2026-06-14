from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from apps.core.extensions.container import wrap_callback
from apps.core.extensions.types import (
    ExtensionAdminActionDefinition,
    ExtensionDiscussionLifecycleDefinition,
    ExtensionManifestRuntimeActionDefinition,
    ExtensionManifestSettingFieldDefinition,
    ExtensionPostLifecycleDefinition,
    ExtensionSettingDefaultDefinition,
    ExtensionSettingForumSerializationDefinition,
    ExtensionSettingResetDefinition,
    ExtensionSettingThemeVariableDefinition,
    ExtensionSystemHookDefinition,
)
from apps.core.forum_registry_types import (
    AdminPageDefinition,
    DiscussionListFilterDefinition,
    DiscussionListQueryDefinition,
    DiscussionSortDefinition,
    NotificationTypeDefinition,
    PermissionDefinition,
    PostTypeDefinition,
    SearchFilterDefinition,
    UserPreferenceDefinition,
)

if TYPE_CHECKING:
    from apps.core.extensions.application import ExtensionHost, ExtensionRuntimeView


@dataclass(frozen=True)
class ForumPermissionExtender:
    checkers: tuple[ExtensionSystemHookDefinition, ...] = ()

    def checker(
        self,
        key: str,
        handler: Any,
        *,
        description: str = "",
        order: int = 100,
    ) -> "ForumPermissionExtender":
        return ForumPermissionExtender(
            checkers=tuple([
                *self.checkers,
                ExtensionSystemHookDefinition(
                    key=str(key or "").strip(),
                    callback=handler,
                    description=str(description or "").strip(),
                    order=int(order),
                ),
            ]),
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.checkers:
            return

        extension_id = extension.extension_id

        def apply(forum_permissions, host: "ExtensionHost"):
            for definition in sorted(self.checkers, key=lambda item: int(item.order or 100)):
                handler = definition.callback
                if isinstance(handler, str) or isinstance(handler, type):
                    handler = wrap_callback(handler, host)
                forum_permissions.register_checker(
                    extension_id,
                    definition.key,
                    handler,
                    description=definition.description,
                )
            return forum_permissions

        app.resolving("forum.permissions", apply)


@dataclass(frozen=True)
class DiscussionLifecycleExtender:
    definitions: tuple[ExtensionDiscussionLifecycleDefinition, ...] = ()

    def handler(
        self,
        key: str,
        *,
        prepare_create: Any = None,
        apply_create: Any = None,
        prepare_update: Any = None,
        apply_update: Any = None,
        prepare_delete: Any = None,
        apply_delete: Any = None,
        apply_hidden: Any = None,
        apply_approved: Any = None,
        apply_rejected: Any = None,
        description: str = "",
    ) -> "DiscussionLifecycleExtender":
        return DiscussionLifecycleExtender(
            definitions=tuple([
                *self.definitions,
                ExtensionDiscussionLifecycleDefinition(
                    key=str(key or "").strip(),
                    prepare_create=prepare_create,
                    apply_create=apply_create,
                    prepare_update=prepare_update,
                    apply_update=apply_update,
                    prepare_delete=prepare_delete,
                    apply_delete=apply_delete,
                    apply_hidden=apply_hidden,
                    apply_approved=apply_approved,
                    apply_rejected=apply_rejected,
                    description=str(description or "").strip(),
                ),
            ]),
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.definitions:
            return

        extension_id = extension.extension_id

        def apply(discussion_lifecycle, host: "ExtensionHost"):
            for definition in self.definitions:
                replacements = {}
                for attr in (
                    "prepare_create",
                    "apply_create",
                    "prepare_update",
                    "apply_update",
                    "prepare_delete",
                    "apply_delete",
                    "apply_hidden",
                    "apply_approved",
                    "apply_rejected",
                ):
                    value = getattr(definition, attr)
                    if isinstance(value, str) or isinstance(value, type):
                        replacements[attr] = wrap_callback(value, host)
                if replacements:
                    definition = replace(definition, **replacements)
                discussion_lifecycle.register(extension_id, definition)
            return discussion_lifecycle

        app.resolving("discussion.lifecycle", apply)


@dataclass(frozen=True)
class PostLifecycleExtender:
    definitions: tuple[ExtensionPostLifecycleDefinition, ...] = ()

    def handler(
        self,
        key: str,
        *,
        apply_created: Any = None,
        apply_updated: Any = None,
        apply_approved: Any = None,
        apply_hidden: Any = None,
        prepare_delete: Any = None,
        apply_deleted: Any = None,
        description: str = "",
    ) -> "PostLifecycleExtender":
        return PostLifecycleExtender(
            definitions=tuple([
                *self.definitions,
                ExtensionPostLifecycleDefinition(
                    key=str(key or "").strip(),
                    apply_created=apply_created,
                    apply_updated=apply_updated,
                    apply_approved=apply_approved,
                    apply_hidden=apply_hidden,
                    prepare_delete=prepare_delete,
                    apply_deleted=apply_deleted,
                    description=str(description or "").strip(),
                ),
            ]),
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.definitions:
            return

        extension_id = extension.extension_id

        def apply(post_lifecycle, host: "ExtensionHost"):
            for definition in self.definitions:
                replacements = {}
                for attr in (
                    "apply_created",
                    "apply_updated",
                    "apply_approved",
                    "apply_hidden",
                    "prepare_delete",
                    "apply_deleted",
                ):
                    value = getattr(definition, attr)
                    if isinstance(value, str) or isinstance(value, type):
                        replacements[attr] = wrap_callback(value, host)
                if replacements:
                    definition = replace(definition, **replacements)
                post_lifecycle.register(extension_id, definition)
            return post_lifecycle

        app.resolving("post.lifecycle", apply)


@dataclass(frozen=True)
class SettingsExtender:
    fields: tuple[ExtensionManifestSettingFieldDefinition, ...] = ()
    expose_to_forum: tuple[str, ...] = ()
    generated_page: bool = True
    defaults: tuple[ExtensionSettingDefaultDefinition, ...] = ()
    reset_rules: tuple[ExtensionSettingResetDefinition, ...] = ()
    frontend_cache_keys: tuple[str, ...] = ()
    theme_variables: tuple[ExtensionSettingThemeVariableDefinition, ...] = ()
    forum_serializations: tuple[ExtensionSettingForumSerializationDefinition, ...] = ()

    def default(self, key: str, value: Any) -> "SettingsExtender":
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return self
        return SettingsExtender(
            fields=self.fields,
            expose_to_forum=self.expose_to_forum,
            generated_page=self.generated_page,
            defaults=tuple([*self.defaults, ExtensionSettingDefaultDefinition(normalized_key, value)]),
            reset_rules=self.reset_rules,
            frontend_cache_keys=self.frontend_cache_keys,
            theme_variables=self.theme_variables,
            forum_serializations=self.forum_serializations,
        )

    def reset_when(self, key: str, callback: Any) -> "SettingsExtender":
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return self
        return SettingsExtender(
            fields=self.fields,
            expose_to_forum=self.expose_to_forum,
            generated_page=self.generated_page,
            defaults=self.defaults,
            reset_rules=tuple([*self.reset_rules, ExtensionSettingResetDefinition(normalized_key, callback)]),
            frontend_cache_keys=self.frontend_cache_keys,
            theme_variables=self.theme_variables,
            forum_serializations=self.forum_serializations,
        )

    def reset_frontend_cache_for(self, *keys: str) -> "SettingsExtender":
        normalized_keys = tuple(
            key
            for key in (str(item or "").strip() for item in keys)
            if key
        )
        return SettingsExtender(
            fields=self.fields,
            expose_to_forum=self.expose_to_forum,
            generated_page=self.generated_page,
            defaults=self.defaults,
            reset_rules=self.reset_rules,
            frontend_cache_keys=tuple(dict.fromkeys([*self.frontend_cache_keys, *normalized_keys])),
            theme_variables=self.theme_variables,
            forum_serializations=self.forum_serializations,
        )

    def theme_variable(self, name: str, key: str, callback: Any = None) -> "SettingsExtender":
        normalized_name = str(name or "").strip()
        normalized_key = str(key or "").strip()
        if not normalized_name or not normalized_key:
            return self
        return SettingsExtender(
            fields=self.fields,
            expose_to_forum=self.expose_to_forum,
            generated_page=self.generated_page,
            defaults=self.defaults,
            reset_rules=self.reset_rules,
            frontend_cache_keys=self.frontend_cache_keys,
            theme_variables=tuple([
                *self.theme_variables,
                ExtensionSettingThemeVariableDefinition(normalized_name, normalized_key, callback),
            ]),
            forum_serializations=self.forum_serializations,
        )

    def serialize_to_forum(self, attribute: str, key: str, callback: Any = None) -> "SettingsExtender":
        normalized_attribute = str(attribute or "").strip()
        normalized_key = str(key or "").strip()
        if not normalized_attribute or not normalized_key:
            return self
        return SettingsExtender(
            fields=self.fields,
            expose_to_forum=self.expose_to_forum,
            generated_page=self.generated_page,
            defaults=self.defaults,
            reset_rules=self.reset_rules,
            frontend_cache_keys=self.frontend_cache_keys,
            theme_variables=self.theme_variables,
            forum_serializations=tuple([
                *self.forum_serializations,
                ExtensionSettingForumSerializationDefinition(normalized_attribute, normalized_key, callback),
            ]),
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        extension_id = extension.extension_id

        def normalize_settings_callback(callback):
            if isinstance(callback, str):
                return wrap_callback(callback, app)
            if isinstance(callback, type) and getattr(callback, "__module__", "") != "builtins":
                return wrap_callback(callback, app)
            return callback

        def apply(settings, host: "ExtensionHost"):
            reset_rules = tuple(
                replace(definition, callback=normalize_settings_callback(definition.callback))
                if isinstance(definition.callback, (str, type))
                else definition
                for definition in self.reset_rules
            )
            theme_variables = tuple(
                replace(definition, callback=normalize_settings_callback(definition.callback))
                if isinstance(definition.callback, (str, type))
                else definition
                for definition in self.theme_variables
            )
            forum_serializations = tuple(
                replace(definition, callback=normalize_settings_callback(definition.callback))
                if isinstance(definition.callback, (str, type))
                else definition
                for definition in self.forum_serializations
            )
            settings.register_fields(
                extension_id,
                self.fields,
                expose_to_forum=self.expose_to_forum,
                generated_page=self.generated_page,
                defaults=tuple(
                    replace(definition, module_id=definition.module_id or extension_id)
                    for definition in self.defaults
                ),
                reset_when=tuple(
                    replace(definition, module_id=definition.module_id or extension_id)
                    for definition in reset_rules
                ),
                reset_frontend_cache_for=self.frontend_cache_keys,
                theme_variables=tuple(
                    replace(definition, module_id=definition.module_id or extension_id)
                    for definition in theme_variables
                ),
                forum_serializations=tuple(
                    replace(definition, module_id=definition.module_id or extension_id)
                    for definition in forum_serializations
                ),
            )
            return settings

        app.resolving("settings", apply)


@dataclass(frozen=True)
class AdminSurfaceExtender:
    permissions: tuple[PermissionDefinition, ...] = ()
    admin_pages: tuple[AdminPageDefinition, ...] = ()
    permissions_pages: tuple[str, ...] = ()
    operations_pages: tuple[str, ...] = ()
    generated_permissions_page: bool = False

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        extension_id = extension.extension_id

        def apply(forum, host: "ExtensionHost"):
            for definition in self.permissions:
                forum.register_permission(definition, extension_id=extension_id)
            for definition in self.admin_pages:
                forum.register_admin_page(definition, extension_id=extension_id)
            return forum

        if self.permissions or self.admin_pages:
            app.resolving("forum", apply)
        if self.permissions_pages or self.operations_pages:
            def apply_pages(frontend, host: "ExtensionHost"):
                host.register_admin_surface_pages(
                    extension,
                    permissions_pages=self.permissions_pages,
                    operations_pages=self.operations_pages,
                )
                return frontend

            app.resolving("frontend", apply_pages)
        if self.generated_permissions_page:
            def apply_actions(actions, host: "ExtensionHost"):
                actions.mark_generated_permissions_page(extension_id)
                return actions

            app.resolving("actions", apply_actions)


@dataclass(frozen=True)
class NotificationsExtender:
    notification_types: tuple[NotificationTypeDefinition, ...] = ()
    user_preferences: tuple[UserPreferenceDefinition, ...] = ()

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not (self.notification_types or self.user_preferences):
            return

        extension_id = extension.extension_id

        def apply(forum, host: "ExtensionHost"):
            for definition in self.notification_types:
                forum.register_notification_type(definition, extension_id=extension_id)
            for definition in self.user_preferences:
                forum.register_user_preference(definition, extension_id=extension_id)
            return forum

        app.resolving("forum", apply)


@dataclass(frozen=True)
class PostExtender:
    post_types: tuple[PostTypeDefinition, ...] = ()

    def type(
        self,
        post_type: Any,
        *,
        code: str = "",
        label: str = "",
        description: str = "",
        icon: str = "far fa-comment",
        is_default: bool = False,
        is_stream_visible: bool = True,
        counts_toward_discussion: bool = True,
        counts_toward_user: bool = True,
        searchable: bool = True,
    ) -> "PostExtender":
        definition = post_type if isinstance(post_type, PostTypeDefinition) else PostTypeDefinition(
            code=code or self._post_type_code(post_type),
            label=label or self._post_type_label(post_type),
            module_id="",
            description=description or str(getattr(post_type, "description", "") or ""),
            icon=icon or str(getattr(post_type, "icon", "") or "far fa-comment"),
            is_default=bool(is_default or getattr(post_type, "is_default", False)),
            is_stream_visible=bool(is_stream_visible),
            counts_toward_discussion=bool(counts_toward_discussion),
            counts_toward_user=bool(counts_toward_user),
            searchable=bool(searchable),
        )
        if not definition.code:
            return self
        return PostExtender(post_types=tuple([*self.post_types, definition]))

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.post_types:
            return
        extension_id = extension.extension_id

        def apply(forum, host: "ExtensionHost"):
            forum.register_external_module_id(extension_id)
            for definition in self.post_types:
                forum.register_post_type(replace(definition, module_id=definition.module_id or extension_id), extension_id=extension_id)
            return forum

        app.resolving("forum", apply)

    @staticmethod
    def _post_type_code(post_type: Any) -> str:
        return str(
            getattr(post_type, "code", "")
            or getattr(post_type, "type", "")
            or getattr(post_type, "post_type", "")
            or getattr(post_type, "__name__", "")
        ).strip()

    @staticmethod
    def _post_type_label(post_type: Any) -> str:
        return str(
            getattr(post_type, "label", "")
            or getattr(post_type, "name", "")
            or PostExtender._post_type_code(post_type)
        ).strip()


@dataclass(frozen=True)
class UserExtender:
    definitions: tuple[ExtensionSystemHookDefinition, ...] = ()
    user_preferences: tuple[UserPreferenceDefinition, ...] = ()

    def display_name_driver(self, identifier: str, driver: Any, *, description: str = "", order: int = 100) -> "UserExtender":
        return self._with_definition("display_name_driver", {
            "identifier": str(identifier or "").strip(),
            "driver": driver,
            "description": str(description or "").strip(),
        }, order=order)

    def avatar_driver(self, identifier: str, driver: Any, *, description: str = "", order: int = 100) -> "UserExtender":
        return self._with_definition("avatar_driver", {
            "identifier": str(identifier or "").strip(),
            "driver": driver,
            "description": str(description or "").strip(),
        }, order=order)

    def permission_groups(self, callback: Any, *, description: str = "", order: int = 100) -> "UserExtender":
        return self._with_definition("permission_groups", {
            "callback": callback,
            "description": str(description or "").strip(),
        }, order=order)

    def model_provider(self, provider: Any, *, description: str = "", order: int = 100) -> "UserExtender":
        return self._with_definition("model_provider", {
            "provider": provider,
            "description": str(description or "").strip(),
        }, order=order)

    def register_preference(
        self,
        key: str,
        transformer: Any = None,
        default: Any = None,
        *,
        label: str = "",
        description: str = "",
        category: str = "notification",
    ) -> "UserExtender":
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return self
        preference = UserPreferenceDefinition(
            key=normalized_key,
            label=str(label or normalized_key).strip(),
            module_id="",
            description=str(description or "").strip(),
            category=str(category or "notification").strip() or "notification",
            default_value=bool(default),
        )
        extender = UserExtender(
            definitions=self.definitions,
            user_preferences=tuple([*self.user_preferences, preference]),
        )
        if transformer is None:
            return extender
        return extender._with_definition("preference_transformer", {
            "key": normalized_key,
            "transformer": transformer,
            "default": default,
        })

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not (self.definitions or self.user_preferences):
            return
        extension_id = extension.extension_id

        def apply_forum(forum, host: "ExtensionHost"):
            forum.register_external_module_id(extension_id)
            for definition in self.user_preferences:
                forum.register_user_preference(replace(definition, module_id=definition.module_id or extension_id), extension_id=extension_id)
            return forum

        def apply_user(user, host: "ExtensionHost"):
            for definition in self.definitions:
                user.register(extension_id, replace(definition, module_id=definition.module_id or extension_id))
            return user

        if self.user_preferences:
            app.resolving("forum", apply_forum)
        if self.definitions:
            app.resolving("user", apply_user)

    def _with_definition(self, key: str, payload: Any, *, order: int = 100) -> "UserExtender":
        return UserExtender(
            definitions=tuple([*self.definitions, ExtensionSystemHookDefinition(
                key=key,
                callback=payload,
                order=int(order),
            )]),
            user_preferences=self.user_preferences,
        )


@dataclass(frozen=True)
class ForumCapabilitiesExtender:
    post_types: tuple[PostTypeDefinition, ...] = ()
    search_filters: tuple[SearchFilterDefinition, ...] = ()
    discussion_list_queries: tuple[DiscussionListQueryDefinition, ...] = ()
    discussion_sorts: tuple[DiscussionSortDefinition, ...] = ()
    discussion_list_filters: tuple[DiscussionListFilterDefinition, ...] = ()

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not (
            self.post_types
            or self.search_filters
            or self.discussion_list_queries
            or self.discussion_sorts
            or self.discussion_list_filters
        ):
            return

        extension_id = extension.extension_id

        def apply(forum, host: "ExtensionHost"):
            for definition in self.post_types:
                forum.register_post_type(definition, extension_id=extension_id)
            for definition in self.search_filters:
                forum.register_search_filter(definition, extension_id=extension_id)
            for definition in self.discussion_list_queries:
                forum.register_discussion_list_query(definition, extension_id=extension_id)
            for definition in self.discussion_sorts:
                forum.register_discussion_sort(definition, extension_id=extension_id)
            for definition in self.discussion_list_filters:
                forum.register_discussion_list_filter(definition, extension_id=extension_id)
            return forum

        app.resolving("forum", apply)


@dataclass(frozen=True)
class RuntimeActionsExtender:
    actions: tuple[ExtensionManifestRuntimeActionDefinition, ...] = ()
    generated_page: bool = False

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        extension_id = extension.extension_id

        def apply(actions, host: "ExtensionHost"):
            actions.register_runtime_actions(
                extension_id,
                self.actions,
                generated_page=self.generated_page,
            )
            return actions

        app.resolving("actions", apply)


@dataclass(frozen=True)
class AdminNavigationExtender:
    actions: tuple[ExtensionAdminActionDefinition, ...] = ()
    generated_permissions_page: bool = False
    generated_operations_page: bool = False

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        extension_id = extension.extension_id

        def apply(actions, host: "ExtensionHost"):
            actions.register_admin_actions(
                extension_id,
                self.actions,
                generated_permissions_page=self.generated_permissions_page,
                generated_operations_page=self.generated_operations_page,
            )
            return actions

        app.resolving("actions", apply)
