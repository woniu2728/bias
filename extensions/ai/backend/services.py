from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import httpx

from apps.core.extension_settings_service import get_extension_settings
from apps.core.extensions.runtime_access import (
    can_runtime_view_post,
    get_extension_host_service,
    get_runtime_discussion_model,
    get_runtime_post_model,
)
from apps.core.visibility import can_view_model_instance


EXTENSION_ID = "ai"


@dataclass(frozen=True)
class AiSettings:
    enabled: bool
    base_url: str
    api_key: str
    model: str
    timeout_seconds: int
    temperature: float
    fallback_enabled: bool


class AiService:
    @staticmethod
    def get_settings() -> AiSettings:
        values = get_extension_settings(EXTENSION_ID)
        return AiSettings(
            enabled=bool(values.get("enabled", True)),
            base_url=str(values.get("base_url") or "").strip().rstrip("/"),
            api_key=str(values.get("api_key") or "").strip(),
            model=str(values.get("model") or "gpt-4.1-mini").strip(),
            timeout_seconds=max(3, int(values.get("timeout_seconds") or 30)),
            temperature=max(0.0, min(float(values.get("temperature_tenths", 4) or 4) / 10, 1.5)),
            fallback_enabled=bool(values.get("fallback_enabled", True)),
        )

    @staticmethod
    def coach_question(*, title: str, content: str, user: Any = None) -> dict:
        title = _clean_text(title, limit=160)
        content = _clean_text(content, limit=4000)
        prompt = (
            "你是论坛提问教练。请检查这个帖子是否适合发布，并给出结构化建议。"
            "重点关注：问题是否清楚、环境/日志/已尝试方案是否完整、标题是否可搜索。"
        )
        fallback = _question_coach_fallback(title=title, content=content)
        return AiService._complete_json(
            action="question_coach",
            system_prompt=prompt,
            user_prompt=f"标题：{title}\n\n内容：{content}",
            fallback=fallback,
            user=user,
        )

    @staticmethod
    def summon_role(*, role: str, title: str = "", content: str = "", user: Any = None) -> dict:
        normalized_role = _normalize_role(role)
        title = _clean_text(title, limit=160)
        content = _clean_text(content, limit=5000)
        prompt = {
            "scribe": "你是论坛书记员。请总结讨论、列出主要观点、未解决问题和下一步。",
            "detective": "你是论坛侦探。请根据内容提炼可搜索线索，并建议应该查找哪些历史讨论。",
            "challenger": "你是论坛挑战官。请提出反方观点、风险和追问，帮助讨论变深入。",
        }[normalized_role]
        fallback = _role_fallback(normalized_role, title=title, content=content)
        return AiService._complete_json(
            action=f"role_{normalized_role}",
            system_prompt=prompt,
            user_prompt=f"标题：{title}\n\n内容：{content}",
            fallback=fallback,
            user=user,
        )

    @staticmethod
    def judge_bounty(*, question: str, answer: str, user: Any = None) -> dict:
        question = _clean_text(question, limit=4000)
        answer = _clean_text(answer, limit=4000)
        fallback = _bounty_judge_fallback(question=question, answer=answer)
        return AiService._complete_json(
            action="bounty_judge",
            system_prompt=(
                "你是论坛悬赏裁判。请根据问题和候选答案生成验收评分。"
                "只辅助判断，最终由楼主决定。"
            ),
            user_prompt=f"问题：\n{question}\n\n候选答案：\n{answer}",
            fallback=fallback,
            user=user,
        )

    @staticmethod
    def summarize_discussion(*, discussion_id: int, user: Any = None) -> dict:
        Discussion = get_runtime_discussion_model()
        Post = get_runtime_post_model()
        discussion = Discussion.objects.filter(id=discussion_id).first()
        if discussion is None:
            raise ValueError("讨论不存在")
        if not can_view_model_instance(Discussion, discussion, user=user, ability="view"):
            raise ValueError("讨论不存在")
        posts = list(
            Post.objects.filter(discussion_id=discussion_id, is_hidden=False)
            .select_related("user")
            .order_by("number")[:80]
        )
        posts = [post for post in posts if can_runtime_view_post(post, user)]
        content = "\n".join(
            f"#{post.number} {getattr(post.user, 'display_name', '') or getattr(post.user, 'username', '用户')}: {_clean_text(post.content, limit=800)}"
            for post in posts
        )
        fallback = _discussion_summary_fallback(discussion.title, posts)
        return AiService._complete_json(
            action="discussion_summary",
            system_prompt="你是论坛书记员。请为长讨论生成新用户也能看懂的摘要、观点和待办。",
            user_prompt=f"讨论标题：{discussion.title}\n\n楼层内容：\n{content}",
            fallback=fallback,
            user=user,
        )

    @staticmethod
    def _complete_json(*, action: str, system_prompt: str, user_prompt: str, fallback: dict, user: Any = None) -> dict:
        settings = AiService.get_settings()
        payload_id = _payload_id(action, user_prompt)
        cost = _resolve_points_cost(action, user)
        if not settings.enabled:
            return _with_points_meta(
                {**fallback, "mode": "disabled", "request_id": payload_id},
                cost=0,
                spend_key="",
            )
        spend_key = _spend_points_for_ai(action=action, payload_id=payload_id, cost=cost, user=user)
        if not settings.base_url or not settings.api_key:
            if settings.fallback_enabled:
                return _with_points_meta(
                    {**fallback, "mode": "fallback", "request_id": payload_id},
                    cost=cost,
                    spend_key=spend_key,
                )
            _refund_points_for_ai(user=user, spend_key=spend_key, action=action, payload_id=payload_id)
            raise ValueError("AI 服务尚未配置 base_url 和 api_key")

        try:
            response = _call_openai_compatible_chat(
                settings=settings,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        except Exception:
            _refund_points_for_ai(user=user, spend_key=spend_key, action=action, payload_id=payload_id)
            raise
        return _with_points_meta(
            {
                "mode": "remote",
                "request_id": payload_id,
                "action": action,
                "text": response,
                "cards": [],
            },
            cost=cost,
            spend_key=spend_key,
        )


def _call_openai_compatible_chat(*, settings: AiSettings, system_prompt: str, user_prompt: str) -> str:
    url = f"{settings.base_url}/chat/completions"
    response = httpx.post(
        url,
        headers={
            "Authorization": f"Bearer {settings.api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": settings.temperature,
        },
        timeout=settings.timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    choices = payload.get("choices") or []
    if not choices:
        raise ValueError("AI 服务没有返回内容")
    message = choices[0].get("message") or {}
    return str(message.get("content") or "").strip()


def _question_coach_fallback(*, title: str, content: str) -> dict:
    missing = []
    if len(title) < 8:
        missing.append("标题偏短，建议写清楚对象、问题和关键错误。")
    if "报错" not in content and "error" not in content.lower() and len(content) < 120:
        missing.append("正文信息偏少，建议补充报错、环境、复现步骤或截图说明。")
    if "尝试" not in content and "试过" not in content:
        missing.append("建议说明已经尝试过哪些方案，避免重复排查。")
    score = max(35, 95 - len(missing) * 18)
    return {
        "action": "question_coach",
        "score": score,
        "text": "这个问题可以发布，但补齐关键信息后更容易获得有效回复。" if missing else "这个问题结构较完整，适合发布。",
        "cards": [{"title": "建议补充", "items": missing or ["可以考虑补充运行环境和期望结果。"]}],
    }


def _role_fallback(role: str, *, title: str, content: str) -> dict:
    if role == "challenger":
        return {
            "action": "role_challenger",
            "text": "我先提出几个反方问题：这个方案在边界条件下是否仍成立？有没有更简单的替代方案？失败后如何回滚？",
            "cards": [{"title": "追问", "items": ["证据是否充分？", "成本是否可接受？", "有没有遗漏的用户场景？"]}],
        }
    if role == "detective":
        keywords = [item for item in [title, *_clean_text(content, limit=200).split()] if len(item) >= 2][:6]
        return {
            "action": "role_detective",
            "text": "可以先从历史讨论里查相同报错、相同模块和相同操作路径。",
            "cards": [{"title": "搜索线索", "items": keywords or ["错误信息", "模块名", "操作步骤"]}],
        }
    return {
        "action": "role_scribe",
        "text": "目前讨论可以整理为：背景是什么、已经确认了什么、还缺什么信息、下一步谁来验证。",
        "cards": [{"title": "纪要结构", "items": ["主要观点", "未解决问题", "下一步"]}],
    }


def _bounty_judge_fallback(*, question: str, answer: str) -> dict:
    checks = [
        "是否解释了原因",
        "是否给出可执行步骤",
        "是否说明风险或回滚方式",
    ]
    score = 70 + min(20, len(answer) // 80)
    return {
        "action": "bounty_judge",
        "score": min(score, 95),
        "text": "这个答案可以作为候选，但建议楼主按验收条件逐项确认。",
        "cards": [{"title": "验收条件", "items": checks}],
    }


def _discussion_summary_fallback(title: str, posts: list[Any]) -> dict:
    return {
        "action": "discussion_summary",
        "text": f"《{title}》目前共有 {len(posts)} 条可见回复。建议先看首帖、最新回复和被互动最多的回复。",
        "cards": [{"title": "阅读入口", "items": ["背景", "主要观点", "待确认问题"]}],
    }


def _normalize_role(role: str) -> str:
    value = str(role or "").strip().lower()
    if value in {"detective", "侦探"}:
        return "detective"
    if value in {"challenger", "挑战官", "challenge"}:
        return "challenger"
    return "scribe"


def _clean_text(value: str | None, *, limit: int) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


def _payload_id(action: str, content: str) -> str:
    digest = hashlib.sha256(f"{action}:{content}".encode("utf-8")).hexdigest()
    return digest[:16]


def _resolve_points_cost(action: str, user: Any = None) -> int:
    if not user or not getattr(user, "is_authenticated", False):
        return 0
    try:
        service = _get_points_service()
        if service is None:
            return 0
        return max(0, int(_points_service_method(service, "get_ai_action_cost")(action) or 0))
    except Exception:
        return 0


def _spend_points_for_ai(*, action: str, payload_id: str, cost: int, user: Any = None) -> str:
    if cost <= 0 or not user or not getattr(user, "is_authenticated", False):
        return ""
    spend_key = f"ai:{action}:{user.id}:{payload_id}"
    service = _get_points_service()
    if service is None:
        return ""
    _points_service_method(service, "spend")(
        user,
        cost,
        reason=f"ai_{action}",
        idempotency_key=spend_key,
        source_type="ai",
        source_id=payload_id,
        meta={"action": action, "request_id": payload_id},
    )
    return spend_key


def _refund_points_for_ai(*, user: Any = None, spend_key: str = "", action: str = "", payload_id: str = "") -> None:
    if not spend_key or not user or not getattr(user, "is_authenticated", False):
        return
    try:
        service = _get_points_service()
        if service is None:
            return
        _points_service_method(service, "refund_spend")(
            user,
            spend_key,
            reason=f"ai_{action}_refund",
            meta={"action": action, "request_id": payload_id},
        )
    except Exception:
        return


def _with_points_meta(payload: dict, *, cost: int, spend_key: str) -> dict:
    if cost <= 0:
        return payload
    return {
        **payload,
        "points": {
            "cost": int(cost),
            "charged": bool(spend_key),
        },
    }


def _get_points_service():
    return get_extension_host_service("points.service")


def _points_service_method(service: Any, name: str):
    if isinstance(service, dict):
        method = service.get(name)
    else:
        method = getattr(service, name, None)
    if not callable(method):
        raise RuntimeError(f"points.service 缺少方法: {name}")
    return method
