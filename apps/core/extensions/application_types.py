from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ApplicationRouteMount:
    prefix: str
    router: Any
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ApplicationNamedRoute:
    app_name: str
    method: str
    path: str
    name: str
    handler: Any
    module_id: str = ""
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ApplicationWebSocketRoute:
    path: str
    name: str
    consumer: Any
    module_id: str = ""


@dataclass
class ApplicationMiddlewareMount:
    target: str
    middleware: Any
    order: int = 100


@dataclass
class ApplicationPolicyMount:
    key: str
    handler: Any
    model: Any = None
    global_policy: bool = False
    query_policy: bool = False


@dataclass(frozen=True)
class ApplicationForumPermissionChecker:
    key: str
    handler: Any
    description: str = ""
    module_id: str = ""
