from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db.models import Max

from apps.core.resource_errors import JsonApiForbidden, JsonApiValidationError
from apps.core.resource_objects import DatabaseResource, ResourceEndpoint, ResourceField, ResourceRelationship, ResourceSort
from apps.posts.models import Post, PostFlag
from apps.posts.services import PostService


class FlagResource(DatabaseResource):
    model = PostFlag
    module_id = "flags"
    description = "帖子举报 JSON:API 资源。"

    def type(self):
        return "flag"

    def query(self, context):
        queryset = PostFlag.objects.select_related(
            "post",
            "post__discussion",
            "post__user",
            "user",
            "resolved_by",
        )
        if str(context.get("endpoint") or "").strip() == "index":
            latest_ids = (
                queryset.filter(status=PostFlag.STATUS_OPEN)
                .values("post_id")
                .annotate(latest_id=Max("id"))
                .values_list("latest_id", flat=True)
            )
            queryset = queryset.filter(id__in=latest_ids)
        return queryset

    def scope(self, queryset, context):
        from apps.core.forum_resources_flags import scope_flag_visibility

        return scope_flag_visibility(queryset, context)

    def base(self, instance, context):
        return {
            "id": instance.id,
            "type": "user",
            "reason": instance.reason or None,
            "reason_detail": instance.message or None,
            "created_at": instance.created_at,
        }

    def fields(self):
        return [
            ResourceField(
                "reason",
                resolver=lambda instance, context: instance.reason or None,
                writable=True,
                nullable=True,
                value_type="string",
                setter=lambda instance, value, context: setattr(instance, "reason", value or ""),
            ),
            ResourceField(
                "reason_detail",
                resolver=lambda instance, context: instance.message or None,
                writable=True,
                nullable=True,
                value_type="string",
                setter=lambda instance, value, context: setattr(instance, "message", value or ""),
            ),
            ResourceRelationship(
                "post",
                resolver=lambda instance, context: getattr(instance, "post", None),
                resource_type="post",
                writable=True,
                required_on_create=True,
            )
            .object()
            .set_relationship_with(_set_flag_post),
            ResourceRelationship(
                "user",
                resolver=lambda instance, context: getattr(instance, "user", None),
                resource_type="user_summary",
            ),
        ]

    def sorts(self):
        return [
            ResourceSort("created_at", handler=("-created_at",)),
        ]

    def endpoints(self):
        return [
            ResourceEndpoint.create()
            .for_module(self.module_id)
            .authenticated()
            .add_default_include(["post", "user"]),
            ResourceEndpoint.index()
            .for_module(self.module_id)
            .authenticated()
            .add_default_include(["user", "post"])
            .with_default_sort("created_at")
            .with_pagination(default_limit=20, max_limit=50),
        ]

    def new_model(self, context):
        user = context.get("user")
        if not user or not user.is_authenticated:
            raise JsonApiForbidden("请先登录")
        return PostFlag(user=user)

    def creating(self, instance, context):
        if not instance.reason and not instance.message:
            raise JsonApiValidationError(
                "举报原因或补充说明至少填写一项",
                pointer="/data/attributes/reason",
            )
        return instance

    def create_action(self, instance, context):
        post = getattr(instance, "post", None)
        user = context.get("user")
        if post is None:
            raise JsonApiValidationError("缺少举报帖子", pointer="/data/relationships/post")
        try:
            return PostService.report_post(
                post.id,
                user,
                reason=instance.reason,
                message=instance.message,
            )
        except PermissionDenied as exc:
            raise JsonApiForbidden(str(exc) or "无权限") from exc
        except ValueError as exc:
            raise JsonApiValidationError(str(exc), pointer="/data") from exc


def _set_flag_post(instance, value, context):
    post_id = _relationship_identifier(value, expected_type="post")
    if not post_id:
        raise JsonApiValidationError("缺少举报帖子", pointer="/data/relationships/post")
    post = Post.objects.select_related("discussion", "user").filter(id=post_id).first()
    if post is None:
        raise JsonApiValidationError("帖子不存在", pointer="/data/relationships/post")
    user = context.get("user")
    if not PostService._can_view_post(post, user):
        raise JsonApiForbidden("没有权限查看此帖子", pointer="/data/relationships/post")
    instance.post = post


def _relationship_identifier(value, *, expected_type: str) -> int | None:
    if not isinstance(value, dict):
        return None
    if str(value.get("type") or "").strip() != expected_type:
        return None
    try:
        return int(value.get("id") or 0)
    except (TypeError, ValueError):
        return None
