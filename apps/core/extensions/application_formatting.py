from __future__ import annotations

from typing import TYPE_CHECKING

from apps.core.extensions.types import (
    ExtensionFormatterCallback,
    ExtensionFormatterDefinition,
)

if TYPE_CHECKING:
    from apps.core.extensions.application import ExtensionHost


class ApplicationLocaleService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host

    def register_path(self, extension_id: str, path: str) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_path = str(path or "").strip()
        if not normalized_extension_id or not normalized_path:
            return

        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        if normalized_path not in view.locale_paths:
            view.locale_paths = tuple([*view.locale_paths, normalized_path])

    def get_paths(self, *, extension_id: str | None = None) -> list[str]:
        if extension_id is not None:
            view = self._host.get_runtime_view(extension_id)
            if view is None:
                return []
            return list(view.locale_paths)

        paths: list[str] = []
        for view in self._host.get_runtime_views():
            paths.extend(view.locale_paths)
        return paths


class ApplicationFormatterService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host

    def register_transform(self, extension_id: str, callback) -> None:
        self.register_render(extension_id, callback)

    def register_configure(self, extension_id: str, callback, *, description: str = "") -> None:
        self.register_phase(extension_id, "configure", callback, description=description)

    def register_parse(self, extension_id: str, callback, *, description: str = "") -> None:
        self.register_phase(extension_id, "parse", callback, description=description)

    def register_render(self, extension_id: str, callback, *, description: str = "") -> None:
        self.register_phase(extension_id, "render", callback, description=description)

    def register_unparse(self, extension_id: str, callback, *, description: str = "") -> None:
        self.register_phase(extension_id, "unparse", callback, description=description)

    def register_phase(self, extension_id: str, phase: str, callback, *, description: str = "") -> None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_phase = str(phase or "").strip().lower()
        if normalized_phase == "transform":
            normalized_phase = "render"
        if normalized_phase not in {"configure", "parse", "render", "unparse"}:
            return
        if not normalized_extension_id or not callable(callback):
            return

        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        definition = ExtensionFormatterDefinition(
            phase=normalized_phase,
            callback=callback,
            module_id=normalized_extension_id,
            description=str(description or "").strip(),
        )
        view.formatter_callbacks = tuple([*view.formatter_callbacks, definition])
        if normalized_phase == "render":
            view.formatter_pipeline = tuple([*view.formatter_pipeline, callback])

    def get_pipeline(self, *, extension_id: str | None = None, phase: str = "render") -> list[ExtensionFormatterCallback]:
        normalized_phase = str(phase or "render").strip().lower() or "render"
        if normalized_phase == "transform":
            normalized_phase = "render"
        if extension_id is not None:
            view = self._host.get_runtime_view(extension_id)
            if view is None:
                return []
            if normalized_phase == "render" and not view.formatter_callbacks:
                return list(view.formatter_pipeline)
            return [
                definition.callback
                for definition in view.formatter_callbacks
                if definition.phase == normalized_phase
            ]

        pipeline: list[ExtensionFormatterCallback] = []
        for view in self._host.get_runtime_views():
            if normalized_phase == "render" and not view.formatter_callbacks:
                pipeline.extend(view.formatter_pipeline)
                continue
            pipeline.extend(
                definition.callback
                for definition in view.formatter_callbacks
                if definition.phase == normalized_phase
            )
        return pipeline
