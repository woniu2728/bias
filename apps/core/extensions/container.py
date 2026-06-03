from __future__ import annotations

import importlib
import inspect
from typing import Any


def import_string(path: str) -> Any:
    normalized = str(path or "").strip()
    if not normalized:
        raise ImportError("Import path is empty")
    module_path, separator, attr = normalized.replace(":", ".").rpartition(".")
    if not separator or not module_path or not attr:
        raise ImportError(f"Import path must include module and attribute: {normalized}")
    module = importlib.import_module(module_path)
    return getattr(module, attr)


def resolve_container_value(
    value: Any,
    container: Any = None,
    _stack: tuple[type, ...] = (),
    _skip_container_lookup: bool = False,
) -> Any:
    if isinstance(value, str):
        if container is not None and not _skip_container_lookup:
            service = _container_get(container, value, _missing=None)
            if service is not None:
                return service
        try:
            value = import_string(value)
        except (ImportError, AttributeError):
            return value
    if isinstance(value, type):
        if container is not None and not _skip_container_lookup:
            service = _container_get(container, _annotation_key(value), _missing=None)
            if service is not None:
                return service
            service = _container_get(container, value.__name__, _missing=None)
            if service is not None:
                return service
        injected = _instantiate_with_dependencies(value, container, _stack=_stack)
        if injected is not None:
            return injected
        try:
            return value(container)
        except TypeError:
            return value()
    return value


def _instantiate_with_dependencies(cls: type, container: Any = None, _stack: tuple[type, ...] = ()) -> Any:
    if container is None:
        return None
    if cls in _stack:
        return None
    try:
        signature = inspect.signature(cls)
    except (TypeError, ValueError):
        return None
    kwargs = {}
    for name, parameter in signature.parameters.items():
        if name == "self":
            continue
        if parameter.kind not in (parameter.POSITIONAL_OR_KEYWORD, parameter.KEYWORD_ONLY):
            return None
        service = _container_get(container, name, _missing=None)
        if service is None and parameter.annotation is not inspect.Signature.empty:
            annotation = parameter.annotation
            service = _container_get(container, _annotation_key(annotation), _missing=None)
            if service is None and isinstance(annotation, type):
                service = _instantiate_with_dependencies(annotation, container, _stack=(*_stack, cls))
        if service is None:
            if parameter.default is inspect.Signature.empty:
                return None
            continue
        kwargs[name] = service
    try:
        return cls(**kwargs)
    except TypeError:
        return None


def _container_get(container: Any, key: Any, _missing: Any = None):
    normalized = str(key or "").strip()
    if not normalized:
        return _missing
    getter = getattr(container, "make", None) or getattr(container, "get", None)
    if callable(getter):
        try:
            return getter(normalized, _missing)
        except TypeError:
            try:
                return getter(normalized)
            except (KeyError, TypeError):
                return _missing
        except KeyError:
            return _missing
    return getattr(container, normalized, _missing)


def _annotation_key(annotation: Any) -> str:
    if isinstance(annotation, str):
        return annotation
    name = getattr(annotation, "__name__", "")
    module = getattr(annotation, "__module__", "")
    return f"{module}.{name}" if module and name else str(annotation)


def wrap_callback(callback: Any, container: Any = None):
    lazy = isinstance(callback, (str, type))

    def invoke(*args, **kwargs):
        resolved = resolve_container_value(callback, container) if lazy else callback
        if not callable(resolved):
            return resolved
        return resolved(*args, **kwargs)

    return invoke if lazy or callable(callback) else callback
