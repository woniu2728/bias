from __future__ import annotations

from pathlib import Path

from django.template import Origin
from django.template.loaders.base import Loader


class ExtensionNamespaceLoader(Loader):
    """Load extension templates registered as ``namespace::template``."""

    def get_template_sources(self, template_name, template_dirs=None):
        try:
            namespace, name = self._split_template_name(template_name)
            views = self._get_view_service()
        except (LookupError, RuntimeError, ValueError):
            return

        for hint in views.get_namespace_hints(namespace):
            candidate = (Path(hint) / name).resolve()
            if not candidate.is_file():
                continue
            yield Origin(
                name=str(candidate),
                template_name=template_name,
                loader=self,
            )

    def get_contents(self, origin):
        try:
            return Path(origin.name).read_text(encoding="utf-8")
        except OSError as exc:
            from django.template import TemplateDoesNotExist

            raise TemplateDoesNotExist(origin) from exc

    def _get_view_service(self):
        from apps.core.extensions.bootstrap import get_extension_host

        host = get_extension_host()
        views = getattr(host, "views", None)
        if views is None:
            raise LookupError("扩展视图服务未就绪")
        return views

    @staticmethod
    def _split_template_name(template_name: str) -> tuple[str, str]:
        raw = str(template_name or "").strip()
        if "::" not in raw:
            raise ValueError("不是扩展命名空间模板")
        namespace, name = raw.split("::", 1)
        namespace = namespace.strip()
        name = name.strip().lstrip("/\\")
        if not namespace or not name or ".." in Path(name).parts:
            raise ValueError("扩展模板名非法")
        return namespace, name


def clear_extension_template_caches() -> None:
    from django.template import engines

    for engine in engines.all():
        backend = getattr(engine, "engine", None)
        for loader in getattr(backend, "template_loaders", ()):
            reset = getattr(loader, "reset", None)
            if callable(reset):
                reset()
