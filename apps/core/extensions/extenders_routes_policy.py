from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from apps.core.extensions.container import resolve_container_value, wrap_callback
from apps.core.extensions.extender_helpers import (
    evaluate_conditional_extender_condition,
    resolve_conditional_extenders,
)
from apps.core.extensions.extender_values import flatten_extenders

if TYPE_CHECKING:
    from apps.core.extensions.application import ExtensionHost, ExtensionRuntimeView


@dataclass(frozen=True)
class RoutesExtender:
    app_name: str = "api"
    routes: tuple[tuple[str, str, str, Any], ...] = ()
    removed_routes: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        normalized_app = str(self.app_name or "api").strip() or "api"
        if normalized_app != "api":
            raise ValueError("RoutesExtender 目前只注册后端 API 命名路由；前台/后台页面路由请使用 FrontendExtender.route()")
        object.__setattr__(self, "app_name", normalized_app)

    def get(self, path: str, name: str, handler: Any) -> "RoutesExtender":
        return self.route("GET", path, name, handler)

    def post(self, path: str, name: str, handler: Any) -> "RoutesExtender":
        return self.route("POST", path, name, handler)

    def put(self, path: str, name: str, handler: Any) -> "RoutesExtender":
        return self.route("PUT", path, name, handler)

    def patch(self, path: str, name: str, handler: Any) -> "RoutesExtender":
        return self.route("PATCH", path, name, handler)

    def delete(self, path: str, name: str, handler: Any) -> "RoutesExtender":
        return self.route("DELETE", path, name, handler)

    def route(self, method: str, path: str, name: str, handler: Any) -> "RoutesExtender":
        return RoutesExtender(
            app_name=self.app_name,
            routes=tuple([*self.routes, (str(method or "GET").strip().upper(), path, name, handler)]),
            removed_routes=self.removed_routes,
            tags=self.tags,
        )

    def remove(self, name: str) -> "RoutesExtender":
        normalized = str(name or "").strip()
        if not normalized:
            return self
        return RoutesExtender(
            app_name=self.app_name,
            routes=self.routes,
            removed_routes=tuple([*self.removed_routes, normalized]),
            tags=self.tags,
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.routes and not self.removed_routes:
            return

        extension_id = extension.extension_id

        def apply(routes, host: "ExtensionHost"):
            for name in self.removed_routes:
                routes.remove_route(extension_id, self.app_name, name)
            for method, path, name, handler in self.routes:
                resolved_handler = handler
                if isinstance(resolved_handler, str) or isinstance(resolved_handler, type):
                    resolved_handler = wrap_callback(resolved_handler, host)
                routes.add_route(
                    extension_id,
                    self.app_name,
                    method,
                    path,
                    name,
                    resolved_handler,
                    tags=self.tags,
                )
            return routes

        app.resolving("routes", apply)


@dataclass(frozen=True)
class ApiRoutesExtender:
    mounts: tuple[tuple[str, Any], ...] = ()
    tags: tuple[str, ...] = ()

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        mounts = tuple(
            (str(prefix or "").strip(), router)
            for prefix, router in self.mounts
            if router is not None
        )
        if not mounts:
            return

        extension_id = extension.extension_id

        def apply(routes, host: "ExtensionHost"):
            routes.remove_mounts(extension_id)
            for prefix, router in mounts:
                routes.mount(extension_id, prefix, router, tags=self.tags)
            return routes

        app.resolving("routes", apply)


@dataclass(frozen=True)
class WebSocketRoutesExtender:
    routes: tuple[tuple[str, str, Any], ...] = ()

    def route(self, path: str, name: str, consumer: Any) -> "WebSocketRoutesExtender":
        return WebSocketRoutesExtender(
            routes=tuple([*self.routes, (path, name, consumer)]),
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.routes:
            return

        extension_id = extension.extension_id

        def apply(routes, host: "ExtensionHost"):
            routes.remove_routes(extension_id)
            for path, name, consumer in self.routes:
                resolved_consumer = resolve_container_value(consumer, host) if isinstance(consumer, (str, type)) else consumer
                routes.add_route(extension_id, path, name, resolved_consumer)
            return routes

        app.resolving("websocket.routes", apply)


@dataclass(frozen=True)
class MiddlewareExtender:
    mounts: tuple[tuple[str, Any, int], ...] = ()

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.mounts:
            return

        extension_id = extension.extension_id

        def apply(middleware_service, host: "ExtensionHost"):
            for target, middleware, order in self.mounts:
                if middleware is None:
                    continue
                middleware_service.mount(extension_id, target, middleware, order=order)
            return middleware_service

        app.resolving("middleware", apply)


@dataclass(frozen=True)
class PolicyExtender:
    mounts: tuple[tuple[str, Any], ...] = ()
    global_policies: tuple[Any, ...] = ()
    model_policies: tuple[tuple[Any, Any], ...] = ()
    query_model_policies: tuple[tuple[Any, Any], ...] = ()

    def global_policy(self, handler: Callable[..., bool]) -> "PolicyExtender":
        return PolicyExtender(
            mounts=self.mounts,
            global_policies=tuple([*self.global_policies, handler]),
            model_policies=self.model_policies,
            query_model_policies=self.query_model_policies,
        )

    def policy(self, model: Any, handler: Any) -> "PolicyExtender":
        return self.model_policy(model, handler)

    def model_policy(self, model: Any, handler: Any) -> "PolicyExtender":
        return PolicyExtender(
            mounts=self.mounts,
            global_policies=self.global_policies,
            model_policies=tuple([*self.model_policies, (model, handler)]),
            query_model_policies=self.query_model_policies,
        )

    def query_model_policy(self, model: Any, handler: Any) -> "PolicyExtender":
        return PolicyExtender(
            mounts=self.mounts,
            global_policies=self.global_policies,
            model_policies=self.model_policies,
            query_model_policies=tuple([*self.query_model_policies, (model, handler)]),
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.mounts and not self.global_policies and not self.model_policies and not self.query_model_policies:
            return

        extension_id = extension.extension_id

        def apply(policies, host: "ExtensionHost"):
            for key, handler in self.mounts:
                policies.mount(extension_id, key, _wrap_policy_handler(handler, host))
            for handler in self.global_policies:
                policies.global_policy(extension_id, _wrap_policy_handler(handler, host))
            for model, handler in self.model_policies:
                policies.model_policy(extension_id, model, _wrap_policy_handler(handler, host))
            for model, handler in self.query_model_policies:
                policies.query_model_policy(extension_id, model, _wrap_policy_handler(handler, host))
            return policies

        app.resolving("policies", apply)


def _wrap_policy_handler(handler: Any, host: "ExtensionHost"):
    if not isinstance(handler, (str, type)) and not callable(getattr(handler, "check_ability", None)):
        return handler

    resolved_cache = {
        "ready": False,
        "value": None,
    }

    def resolve_handler():
        if resolved_cache["ready"]:
            return resolved_cache["value"]
        resolved = resolve_container_value(handler, host) if isinstance(handler, (str, type)) else handler
        resolved_cache["value"] = resolved
        resolved_cache["ready"] = True
        return resolved

    def invoke(**context):
        resolved = resolve_handler()
        check_ability = getattr(resolved, "check_ability", None)
        if callable(check_ability):
            extra_context = {
                key: value
                for key, value in context.items()
                if key not in {"user", "ability", "model"}
            }
            return check_ability(
                context.get("user"),
                str(context.get("ability") or "").strip(),
                context.get("model"),
                **extra_context,
            )
        if callable(resolved):
            try:
                return resolved(**context)
            except TypeError:
                return resolved(context.get("user"), context.get("ability"), context.get("model"))
        return None

    invoke._bias_policy_cache = resolved_cache
    return invoke


@dataclass(frozen=True)
class ConditionalExtender:
    callbacks: tuple[Callable[["ExtensionHost"], Any], ...] = ()

    def when(self, condition: Callable[["ExtensionHost"], bool] | bool, callback: Callable[[], Any] | str | type) -> "ConditionalExtender":
        def resolver(host: "ExtensionHost"):
            if not evaluate_conditional_extender_condition(condition, host):
                return []
            return resolve_conditional_extenders(callback, host)

        return ConditionalExtender(callbacks=tuple([*self.callbacks, resolver]))

    def when_extension_enabled(self, extension_id: str, callback: Callable[[], Any] | str | type) -> "ConditionalExtender":
        normalized = str(extension_id or "").strip()

        def condition(host: "ExtensionHost") -> bool:
            extension = host.get_runtime_extension(normalized)
            return bool(extension and extension.runtime.enabled)

        return self.when(condition, callback)

    def when_extension_disabled(self, extension_id: str, callback: Callable[[], Any] | str | type) -> "ConditionalExtender":
        normalized = str(extension_id or "").strip()

        def condition(host: "ExtensionHost") -> bool:
            extension = host.get_runtime_extension(normalized)
            return not bool(extension and extension.runtime.enabled)

        return self.when(condition, callback)

    def when_setting(
        self,
        key: str,
        expected: Any,
        callback: Callable[[], Any] | str | type,
        *,
        strict: bool = False,
    ) -> "ConditionalExtender":
        normalized_key = str(key or "").strip()

        def condition(host: "ExtensionHost") -> bool:
            try:
                from apps.core.models import Setting

                record = Setting.objects.filter(key=normalized_key).first()
                value = record.value if record is not None else None
            except Exception:
                value = None
            if strict:
                return value == expected and type(value) is type(expected)
            return value == expected

        return self.when(condition, callback)

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        for resolver in self.callbacks:
            extenders = resolver(app)
            for extender in flatten_extenders(extenders):
                extend_fn = getattr(extender, "extend", None)
                if callable(extend_fn):
                    app._mark_extension_extender(extension.extension_id, extender)
                    extend_fn(app, extension)
