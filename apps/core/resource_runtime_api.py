from __future__ import annotations

from ninja import Router

from apps.core.resource_dispatcher import dispatch_resource_endpoint


router = Router()


@router.get("/resources/{resource}/{endpoint}", tags=["Resources"])
def dispatch_resource_get(request, resource: str, endpoint: str):
    return dispatch_resource_endpoint(request, resource=resource, endpoint=endpoint)


@router.post("/resources/{resource}/{endpoint}", tags=["Resources"])
def dispatch_resource_post(request, resource: str, endpoint: str):
    return dispatch_resource_endpoint(request, resource=resource, endpoint=endpoint)


@router.patch("/resources/{resource}/{endpoint}", tags=["Resources"])
def dispatch_resource_patch(request, resource: str, endpoint: str):
    return dispatch_resource_endpoint(request, resource=resource, endpoint=endpoint)


@router.delete("/resources/{resource}/{endpoint}", tags=["Resources"])
def dispatch_resource_delete(request, resource: str, endpoint: str):
    return dispatch_resource_endpoint(request, resource=resource, endpoint=endpoint)


@router.get("/resources/{resource}/{object_id}/{endpoint}", tags=["Resources"])
def dispatch_resource_object_get(request, resource: str, object_id: str, endpoint: str):
    return dispatch_resource_endpoint(request, resource=resource, object_id=object_id, endpoint=endpoint)


@router.post("/resources/{resource}/{object_id}/{endpoint}", tags=["Resources"])
def dispatch_resource_object_post(request, resource: str, object_id: str, endpoint: str):
    return dispatch_resource_endpoint(request, resource=resource, object_id=object_id, endpoint=endpoint)


@router.patch("/resources/{resource}/{object_id}/{endpoint}", tags=["Resources"])
def dispatch_resource_object_patch(request, resource: str, object_id: str, endpoint: str):
    return dispatch_resource_endpoint(request, resource=resource, object_id=object_id, endpoint=endpoint)


@router.delete("/resources/{resource}/{object_id}/{endpoint}", tags=["Resources"])
def dispatch_resource_object_delete(request, resource: str, object_id: str, endpoint: str):
    return dispatch_resource_endpoint(request, resource=resource, object_id=object_id, endpoint=endpoint)
