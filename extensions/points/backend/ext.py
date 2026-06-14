from apps.core.extensions import (
    ApiResourceExtender,
    ApiRoutesExtender,
    EventListenersExtender,
    FrontendExtender,
    LifecycleExtender,
    ModelExtender,
    ServiceProviderExtender,
    SettingsExtender,
    ExtensionEventListenerDefinition,
    setting_field,
)
from extensions.points.backend.api import router as points_router
from extensions.points.backend.listeners import (
    handle_discussion_created,
    handle_post_created,
    handle_post_liked,
)
from extensions.points.backend.models import PointAccount, PointLedgerEntry
from extensions.points.backend.resources import (
    user_detail_resource_field_definitions,
    user_summary_resource_field_definitions,
)
from extensions.points.backend.runtime import points_service_provider


EXTENSION_ID = "points"


def extend():
    return [
        ApiRoutesExtender(
            mounts=(("", points_router),),
            tags=("Points",),
        ),
        FrontendExtender(
            forum_entry="extensions/points/frontend/forum/index.js",
        ),
        EventListenersExtender(
            listeners=event_listener_definitions(),
        ),
        ServiceProviderExtender(
            key="points.service",
            provider=points_service_provider,
        ),
        SettingsExtender(fields=setting_definitions(), expose_to_forum=(
            "enabled",
            "ai_question_coach_cost",
            "ai_role_summon_cost",
            "ai_bounty_judge_cost",
            "ai_discussion_summary_cost",
        ))
        .default("enabled", True)
        .default("discussion_create_reward", 10)
        .default("reply_create_reward", 3)
        .default("like_received_reward", 1)
        .default("ai_question_coach_cost", 2)
        .default("ai_role_summon_cost", 3)
        .default("ai_bounty_judge_cost", 5)
        .default("ai_discussion_summary_cost", 8),
        ModelExtender()
        .owns(PointAccount, description="用户积分账户由 points 扩展拥有。")
        .owns(PointLedgerEntry, description="用户积分账本由 points 扩展拥有。"),
        ApiResourceExtender("user_detail").fields(user_detail_resource_field_definitions),
        ApiResourceExtender("user_summary").fields(user_summary_resource_field_definitions),
        LifecycleExtender(),
    ]


def event_listener_definitions():
    return (
        ExtensionEventListenerDefinition(
            event_type="extensions.discussions.backend.events.DiscussionCreatedEvent",
            handler=handle_discussion_created,
            description="讨论发布成功后奖励作者积分。",
        ),
        ExtensionEventListenerDefinition(
            event_type="extensions.posts.backend.events.PostCreatedEvent",
            handler=handle_post_created,
            description="回复发布成功后奖励作者积分。",
        ),
        ExtensionEventListenerDefinition(
            event_type="extensions.likes.backend.events.PostLikedEvent",
            handler=handle_post_liked,
            description="回复被点赞后奖励作者积分。",
        ),
    )


def setting_definitions():
    return (
        setting_field({
            "key": "enabled",
            "label": "启用积分系统",
            "type": "boolean",
            "default": True,
            "help_text": "关闭后不再自动发放或消费积分，但历史账本保留。",
            "order": 5,
        }),
        setting_field({
            "key": "discussion_create_reward",
            "label": "发主题奖励",
            "type": "number",
            "default": 10,
            "help_text": "审核通过的主题创建后奖励作者的积分。",
            "order": 10,
        }),
        setting_field({
            "key": "reply_create_reward",
            "label": "回复奖励",
            "type": "number",
            "default": 3,
            "help_text": "审核通过的回复创建后奖励作者的积分。",
            "order": 20,
        }),
        setting_field({
            "key": "like_received_reward",
            "label": "收到点赞奖励",
            "type": "number",
            "default": 1,
            "help_text": "回复被其他用户点赞后奖励作者的积分。",
            "order": 30,
        }),
        setting_field({
            "key": "ai_question_coach_cost",
            "label": "AI 提问教练消耗",
            "type": "number",
            "default": 2,
            "help_text": "每次使用 AI 提问教练消耗的积分。",
            "order": 100,
        }),
        setting_field({
            "key": "ai_role_summon_cost",
            "label": "AI 角色召唤消耗",
            "type": "number",
            "default": 3,
            "help_text": "每次召唤 AI 书记员、侦探或挑战官消耗的积分。",
            "order": 110,
        }),
        setting_field({
            "key": "ai_bounty_judge_cost",
            "label": "AI 悬赏裁判消耗",
            "type": "number",
            "default": 5,
            "help_text": "每次使用 AI 悬赏裁判消耗的积分。",
            "order": 120,
        }),
        setting_field({
            "key": "ai_discussion_summary_cost",
            "label": "AI 讨论纪要消耗",
            "type": "number",
            "default": 8,
            "help_text": "每次生成讨论纪要消耗的积分。",
            "order": 130,
        }),
    )
