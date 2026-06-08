from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse

from apps.core.auth import get_optional_user
from apps.core.extensions.runtime_access import get_runtime_resource_registry
from apps.core.resource_api import parse_resource_query_options
from apps.core.resource_errors import JsonApiError, jsonapi_error_response


@dataclass(frozen=True)
class ResourceEndpointContext:
    request: Any
    resource: str
    endpoint: str
    method: str
    user: Any = None
    object_id: str | None = None
    payload: Any = None
    query: dict[str, Any] | None = None
    resource_options: Any = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "request": self.request,
            "resource": self.resource,
            "endpoint": self.endpoint,
            "method": self.method,
            "user": self.user,
            "object_id": self.object_id,
            "payload": self.payload,
            "query": dict(self.query or {}),
            "resource_options": self.resource_options,
        }


def dispatch_resource_endpoint(
    request,
    *,
    resource: str,
    endpoint: str,
    object_id: str | None = None,
):
    registry = get_runtime_resource_registry()
    user = get_optional_user(request)
    if user is not None and getattr(user, "is_authenticated", False):
        request.auth = user
    method = str(getattr(request, "method", "GET") or "GET").upper()
    context = ResourceEndpointContext(
        request=request,
        resource=resource,
        endpoint=endpoint,
        method=method,
        user=user,
        object_id=object_id,
        payload=_parse_request_payload(request),
        query=_extract_query_params(request),
        resource_options=parse_resource_query_options(request, resource),
    )
    definition = registry.get_dispatch_endpoint(
        resource,
        endpoint,
        method,
        context.as_dict(),
    )
    if definition is None:
        return jsonapi_error_response("资源端点不存在", status=404)
    if definition.auth_required and (user is None or not getattr(user, "is_authenticated", False)):
        return jsonapi_error_response("请先登录", status=401)
    forum_permission = str(definition.forum_permission or "").strip()
    if not forum_permission and definition.ability is None and definition.permission:
        forum_permission = str(definition.permission or "").strip()
    if forum_permission:
        if user is None or not getattr(user, "is_authenticated", False):
            return jsonapi_error_response("请先登录", status=401)
        from extensions.users.backend.services import UserService

        if not UserService.has_forum_permission(user, forum_permission):
            return jsonapi_error_response("无权限", status=403)

    try:
        context_payload = context.as_dict()
        context_payload["default_include"] = tuple(definition.default_include or ())
        context_payload["default_sort"] = definition.default_sort
        context_payload["paginate"] = bool(definition.paginate)
        result = registry.dispatch_resource_endpoint(definition, context_payload)
    except LookupError as exc:
        return jsonapi_error_response(str(exc) or "资源不存在", status=404)
    except JsonApiError as exc:
        return jsonapi_error_response(exc)
    except PermissionDenied as exc:
        return jsonapi_error_response(str(exc) or "无权限", status=403)
    except PermissionError as exc:
        return jsonapi_error_response(str(exc) or "无权限", status=403)
    except ValueError as exc:
        return jsonapi_error_response(str(exc), status=400)

    return _to_response(result)


def _parse_request_payload(request):
    if str(getattr(request, "method", "GET") or "GET").upper() in {"GET", "HEAD", "OPTIONS"}:
        return None
    body = getattr(request, "body", b"") or b""
    if not body:
        return {}
    try:
        return json.loads(body.decode(getattr(request, "encoding", None) or "utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _params_to_dict(getattr(request, "POST", None))


def _extract_query_params(request) -> dict[str, Any]:
    return _params_to_dict(getattr(request, "GET", None))


def _params_to_dict(params) -> dict[str, Any]:
    if params is None:
        return {}
    lists = getattr(params, "lists", None)
    if lists is None:
        return dict(params)
    output: dict[str, Any] = {}
    for key, values in lists():
        output[key] = values[-1] if len(values) == 1 else list(values)
    return output


def _to_response(result):
    if isinstance(result, HttpResponse):
        return result
    if result is None:
        return HttpResponse(status=204)
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], int):
        status, payload = result
        if payload is None:
            return HttpResponse(status=status)
        return JsonResponse(payload, status=status, safe=isinstance(payload, dict))
    if isinstance(result, list):
        return JsonResponse(result, safe=False)
    return JsonResponse(result, safe=isinstance(result, dict))
