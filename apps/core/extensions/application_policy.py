from __future__ import annotations

from typing import TYPE_CHECKING

from apps.core.extensions.application_types import (
    ApplicationMiddlewareMount,
    ApplicationPolicyMount,
)

if TYPE_CHECKING:
    from apps.core.extensions.application import ExtensionHost


class ApplicationMiddlewareService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host

    def mount(
        self,
        extension_id: str,
        target: str,
        middleware,
        *,
        order: int = 100,
    ) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id or middleware is None:
            return

        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        view.middleware_mounts = tuple([*view.middleware_mounts, ApplicationMiddlewareMount(
            target=str(target or "").strip() or "api",
            middleware=middleware,
            order=int(order),
        )])

    def get_mounts(self, *, target: str | None = None) -> list[ApplicationMiddlewareMount]:
        mounts: list[ApplicationMiddlewareMount] = []
        for view in self._host.get_runtime_views():
            mounts.extend(view.middleware_mounts)
        if target is not None:
            mounts = [item for item in mounts if item.target == target]
        return sorted(mounts, key=lambda item: (item.target, item.order))


class ApplicationPolicyService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host

    def mount(self, extension_id: str, key: str, handler) -> None:
        self.mount_key(extension_id, key, handler)

    def mount_key(self, extension_id: str, key: str, handler) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_key = str(key or "").strip()
        if not normalized_extension_id or not normalized_key or not callable(handler):
            return

        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        view.policy_mounts = tuple([*view.policy_mounts, ApplicationPolicyMount(
            key=normalized_key,
            handler=handler,
        )])

    def global_policy(self, extension_id: str, handler) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id or not callable(handler):
            return
        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        view.policy_mounts = tuple([*view.policy_mounts, ApplicationPolicyMount(
            key="",
            handler=handler,
            global_policy=True,
        )])

    def model_policy(self, extension_id: str, model, handler) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id or model is None or not callable(handler):
            return
        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        view.policy_mounts = tuple([*view.policy_mounts, ApplicationPolicyMount(
            key="",
            handler=handler,
            model=model,
        )])

    def query_model_policy(self, extension_id: str, model, handler) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id or model is None or not callable(handler):
            return
        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        view.policy_mounts = tuple([*view.policy_mounts, ApplicationPolicyMount(
            key="",
            handler=handler,
            model=model,
            query_policy=True,
        )])

    def get_mounts(self) -> list[ApplicationPolicyMount]:
        mounts: list[ApplicationPolicyMount] = []
        for view in self._host.get_runtime_views():
            mounts.extend(view.policy_mounts)
        return mounts
