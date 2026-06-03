from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.http import JsonResponse


@dataclass(frozen=True)
class JsonApiErrorItem:
    detail: str
    status: int = 400
    code: str = ""
    source: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": str(self.status),
            "detail": self.detail,
        }
        if self.code:
            payload["code"] = self.code
        if self.source:
            payload["source"] = dict(self.source)
        return payload


class JsonApiError(ValueError):
    status = 400

    def __init__(
        self,
        detail: str,
        *,
        status: int | None = None,
        code: str = "",
        pointer: str = "",
        parameter: str = "",
        errors: list[JsonApiErrorItem | dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status = int(status or self.status)
        self.code = code
        self.pointer = pointer
        self.parameter = parameter
        self.errors = list(errors or [])

    def as_errors(self) -> list[dict[str, Any]]:
        if self.errors:
            output = []
            for item in self.errors:
                if isinstance(item, JsonApiErrorItem):
                    output.append(item.as_dict())
                else:
                    payload = dict(item)
                    payload.setdefault("status", str(self.status))
                    output.append(payload)
            return output

        source = {}
        if self.pointer:
            source["pointer"] = self.pointer
        if self.parameter:
            source["parameter"] = self.parameter
        return [
            JsonApiErrorItem(
                detail=self.detail,
                status=self.status,
                code=self.code,
                source=source or None,
            ).as_dict()
        ]


class BadJsonApiRequest(JsonApiError):
    status = 400


class JsonApiConflict(JsonApiError):
    status = 409


class JsonApiForbidden(JsonApiError):
    status = 403


class JsonApiValidationError(JsonApiError):
    status = 422


def jsonapi_error_response(error: JsonApiError | str, *, status: int | None = None) -> JsonResponse:
    if isinstance(error, JsonApiError):
        response_status = int(status or error.status)
        return JsonResponse({"errors": error.as_errors()}, status=response_status)
    response_status = int(status or 400)
    return JsonResponse(
        {
            "errors": [
                JsonApiErrorItem(detail=str(error), status=response_status).as_dict()
            ]
        },
        status=response_status,
    )
