from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch

from apps.core.api_errors import api_error
from apps.core.extensions.runtime_access import get_runtime_resource_registry
from apps.core.resource_api import ResourceQueryOptions, parse_resource_query_options
from extensions.tags.backend.models import Tag
from extensions.tags.backend.schemas import TagCreateSchema, TagUpdateSchema
from extensions.tags.backend.services import TagService


def _get_resource_registry():
    return get_runtime_resource_registry()


def _build_tag_serialize_context(user=None, action="view"):
    return {
        "forbidden_tag_ids": set(TagService.get_forbidden_tag_ids(user, action=action)),
    }


def _get_prefetched_children(tag):
    if hasattr(tag, "visible_children"):
        return tag.visible_children
    return tag.children.all().order_by("position", "name")


def _serialize_tag(
    tag,
    user=None,
    include_children=False,
    action="view",
    context=None,
    resource_options=None,
):
    context = context or _build_tag_serialize_context(user, action=action)
    forbidden_tag_ids = context["forbidden_tag_ids"]
    resource_options = resource_options or ResourceQueryOptions()
    payload = _get_resource_registry().serialize(
        "tag",
        tag,
        {"user": user, "action": action},
        only=resource_options.fields,
        include=resource_options.includes,
    )
    children = []
    if include_children:
        children = [
            _serialize_tag(
                child,
                user=user,
                include_children=True,
                action=action,
                context=context,
                resource_options=resource_options,
            )
            for child in _get_prefetched_children(tag)
            if not child.is_hidden and child.id not in forbidden_tag_ids
        ]

    payload["children"] = children
    return payload


def _apply_tag_resource_preloads(queryset, user=None, action="view", resource_options=None):
    resource_options = resource_options or ResourceQueryOptions()
    return _get_resource_registry().apply_preload_plan(
        queryset,
        "tag",
        {"user": user, "action": action},
        only=resource_options.fields,
        include=resource_options.includes,
    )


def _tag_query_value(context, key: str, default=None):
    return dict(context.get("query") or {}).get(key, default)


def _tag_payload(context) -> dict:
    payload = context.get("payload")
    return payload if isinstance(payload, dict) else {}


def _tag_object_id(context) -> int:
    try:
        return int(context.get("object_id") or 0)
    except (TypeError, ValueError):
        return 0


def _tag_int_query_value(context, key: str):
    value = _tag_query_value(context, key)
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _tag_bool_query_value(context, key: str, default=False):
    value = _tag_query_value(context, key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _tag_purpose_query_value(context):
    purpose = str(_tag_query_value(context, "purpose", "view") or "view")
    if purpose not in {"view", "start_discussion", "reply"}:
        return "view"
    return purpose


def dispatch_tag_create(context):
    payload = TagCreateSchema(**_tag_payload(context))
    try:
        tag = TagService.create_tag(
            name=payload.name,
            slug=payload.slug,
            description=payload.description or "",
            color=payload.color or "",
            icon=payload.icon or "",
            background_url=payload.background_url or "",
            position=payload.position or 0,
            parent_id=payload.parent_id,
            is_hidden=payload.is_hidden or False,
            is_restricted=payload.is_restricted or False,
            view_scope=payload.view_scope or Tag.ACCESS_PUBLIC,
            start_discussion_scope=payload.start_discussion_scope or Tag.ACCESS_MEMBERS,
            reply_scope=payload.reply_scope or Tag.ACCESS_MEMBERS,
            user=context["user"],
        )
        return _serialize_tag(tag, user=context["user"], include_children=True)
    except PermissionDenied as e:
        return api_error(str(e), status=403)
    except ValueError as e:
        return api_error(str(e), status=400)


def dispatch_tag_index(context):
    request = context["request"]
    user = context.get("user")
    resource_options = parse_resource_query_options(request, "tag")
    include_hidden = _tag_bool_query_value(context, "include_hidden", False)
    include_children = _tag_bool_query_value(context, "include_children", True)
    purpose = _tag_purpose_query_value(context)
    if include_hidden and (not user or not user.is_staff):
        include_hidden = False

    visible_child_queryset = Tag.objects.select_related("last_posted_discussion").order_by("position", "name")
    if not include_hidden:
        visible_child_queryset = visible_child_queryset.filter(is_hidden=False)
    visible_child_queryset = TagService.filter_tags_for_user(visible_child_queryset, user, action=purpose)

    queryset = Tag.objects.select_related("last_posted_discussion").prefetch_related(
        Prefetch("children", queryset=visible_child_queryset, to_attr="visible_children")
    ).all()
    queryset = _apply_tag_resource_preloads(
        queryset,
        user=user,
        action=purpose,
        resource_options=resource_options,
    )

    parent_id = _tag_int_query_value(context, "parent_id")
    if parent_id is None:
        queryset = queryset.filter(parent__isnull=True)
    else:
        queryset = queryset.filter(parent_id=parent_id)

    if not include_hidden:
        queryset = queryset.filter(is_hidden=False)

    queryset = TagService.filter_tags_for_user(queryset, user, action=purpose)
    tags = queryset.order_by("position", "name")

    serialize_context = _build_tag_serialize_context(user, action=purpose)
    return {
        "data": [
            _serialize_tag(
                tag,
                user=user,
                include_children=include_children,
                action=purpose,
                context=serialize_context,
                resource_options=resource_options,
            )
            for tag in tags
        ]
    }


def dispatch_tag_popular(context):
    request = context["request"]
    user = context.get("user")
    resource_options = parse_resource_query_options(request, "tag")
    limit = _tag_int_query_value(context, "limit") or 10
    tags = TagService.filter_tags_for_user(
        Tag.objects.filter(is_hidden=False),
        user,
        action="view",
    )
    tags = _apply_tag_resource_preloads(
        tags,
        user=user,
        action="view",
        resource_options=resource_options,
    ).order_by("-discussion_count", "-last_posted_at")[:limit]

    serialize_context = _build_tag_serialize_context(user, action="view")
    return {
        "data": [
            _serialize_tag(tag, user=user, context=serialize_context, resource_options=resource_options)
            for tag in tags
        ]
    }


def _load_visible_tag(tag, user, resource_options):
    if not tag:
        return None
    tag = _apply_tag_resource_preloads(
        Tag.objects.select_related("last_posted_discussion").prefetch_related("children").filter(id=tag.id),
        user=user,
        action="view",
        resource_options=resource_options,
    ).get()
    if not TagService.can_view_tag(tag, user):
        return api_error("没有权限查看此标签", status=403)
    return tag


def dispatch_tag_show(context):
    request = context["request"]
    user = context.get("user")
    resource_options = parse_resource_query_options(request, "tag")
    tag = _load_visible_tag(TagService.get_tag_by_id(_tag_object_id(context)), user, resource_options)
    if tag is None:
        return api_error("标签不存在", status=404)
    if hasattr(tag, "status_code"):
        return tag
    return _serialize_tag(tag, user=user, include_children=True, resource_options=resource_options)


def dispatch_tag_show_by_slug(context):
    request = context["request"]
    user = context.get("user")
    resource_options = parse_resource_query_options(request, "tag")
    slug = str(context.get("object_id") or "").strip()
    tag = _load_visible_tag(TagService.get_tag_by_slug(slug), user, resource_options)
    if tag is None:
        return api_error("标签不存在", status=404)
    if hasattr(tag, "status_code"):
        return tag
    return _serialize_tag(tag, user=user, include_children=True, resource_options=resource_options)


def dispatch_tag_update(context):
    payload = TagUpdateSchema(**_tag_payload(context))
    try:
        tag = TagService.update_tag(
            tag_id=_tag_object_id(context),
            user=context["user"],
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            color=payload.color,
            icon=payload.icon,
            background_url=payload.background_url,
            position=payload.position,
            parent_id=payload.parent_id,
            is_hidden=payload.is_hidden,
            is_restricted=payload.is_restricted,
            view_scope=payload.view_scope,
            start_discussion_scope=payload.start_discussion_scope,
            reply_scope=payload.reply_scope,
        )

        tag = Tag.objects.select_related("last_posted_discussion").prefetch_related("children").get(id=tag.id)
        return _serialize_tag(tag, user=context["user"], include_children=True)
    except Tag.DoesNotExist:
        return api_error("标签不存在", status=404)
    except PermissionDenied as e:
        return api_error(str(e), status=403)
    except ValueError as e:
        return api_error(str(e), status=400)


def dispatch_tag_delete(context):
    try:
        TagService.delete_tag(_tag_object_id(context), context["user"])
        return {"message": "标签已删除"}
    except Tag.DoesNotExist:
        return api_error("标签不存在", status=404)
    except PermissionDenied as e:
        return api_error(str(e), status=403)
    except ValueError as e:
        return api_error(str(e), status=400)

