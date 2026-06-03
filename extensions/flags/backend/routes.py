from __future__ import annotations

from ninja import Router

from apps.core.auth import AuthBearer
from apps.core.resource_dispatcher import dispatch_resource_endpoint


router = Router()


@router.post("/posts/{post_id}/report", auth=AuthBearer(), tags=["Posts"])
def report_post(request, post_id: int):
    return dispatch_resource_endpoint(
        request,
        resource="post",
        object_id=str(post_id),
        endpoint="report",
    )


@router.post("/posts/{post_id}/flags/resolve", auth=AuthBearer(), tags=["Posts"])
def resolve_post_flags(request, post_id: int):
    return dispatch_resource_endpoint(
        request,
        resource="post",
        object_id=str(post_id),
        endpoint="flags/resolve",
    )


@router.delete("/posts/{post_id}/flags", auth=AuthBearer(), tags=["Posts"])
def delete_post_flags(request, post_id: int):
    return dispatch_resource_endpoint(
        request,
        resource="post",
        object_id=str(post_id),
        endpoint="flags/delete",
    )
