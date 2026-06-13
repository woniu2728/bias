from __future__ import annotations

from dataclasses import dataclass

from apps.core.extension_settings_service import get_extension_settings


EXTENSION_ID = "points"


@dataclass(frozen=True)
class PointsSettings:
    enabled: bool
    discussion_create_reward: int
    reply_create_reward: int
    like_received_reward: int
    ai_question_coach_cost: int
    ai_role_summon_cost: int
    ai_bounty_judge_cost: int
    ai_discussion_summary_cost: int


def get_points_settings() -> PointsSettings:
    values = get_extension_settings(EXTENSION_ID)
    return PointsSettings(
        enabled=bool(values.get("enabled", True)),
        discussion_create_reward=max(0, int(values.get("discussion_create_reward") or 0)),
        reply_create_reward=max(0, int(values.get("reply_create_reward") or 0)),
        like_received_reward=max(0, int(values.get("like_received_reward") or 0)),
        ai_question_coach_cost=max(0, int(values.get("ai_question_coach_cost") or 0)),
        ai_role_summon_cost=max(0, int(values.get("ai_role_summon_cost") or 0)),
        ai_bounty_judge_cost=max(0, int(values.get("ai_bounty_judge_cost") or 0)),
        ai_discussion_summary_cost=max(0, int(values.get("ai_discussion_summary_cost") or 0)),
    )


def get_ai_action_cost(action: str) -> int:
    settings = get_points_settings()
    if not settings.enabled:
        return 0
    normalized = str(action or "").strip()
    if normalized == "question_coach":
        return settings.ai_question_coach_cost
    if normalized.startswith("role_"):
        return settings.ai_role_summon_cost
    if normalized == "bounty_judge":
        return settings.ai_bounty_judge_cost
    if normalized == "discussion_summary":
        return settings.ai_discussion_summary_cost
    return 0

