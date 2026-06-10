from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


FORCE_DENY = "force_deny"
FORCE_ALLOW = "force_allow"
DENY = "deny"
ALLOW = "allow"

_DECISION_PRIORITY = (
    (FORCE_DENY, False),
    (FORCE_ALLOW, True),
    (DENY, False),
    (ALLOW, True),
)


@dataclass(frozen=True)
class AuthorizationDecision:
    value: str

    @classmethod
    def allow(cls) -> "AuthorizationDecision":
        return cls(ALLOW)

    @classmethod
    def deny(cls) -> "AuthorizationDecision":
        return cls(DENY)

    @classmethod
    def force_allow(cls) -> "AuthorizationDecision":
        return cls(FORCE_ALLOW)

    @classmethod
    def force_deny(cls) -> "AuthorizationDecision":
        return cls(FORCE_DENY)


class AuthorizationPolicy:
    GLOBAL = "GLOBAL"
    ALLOW = "ALLOW"
    DENY = "DENY"
    FORCE_ALLOW = "FORCE_ALLOW"
    FORCE_DENY = "FORCE_DENY"

    def allow(self) -> AuthorizationDecision:
        return allow()

    def deny(self) -> AuthorizationDecision:
        return deny()

    def force_allow(self) -> AuthorizationDecision:
        return force_allow()

    def force_deny(self) -> AuthorizationDecision:
        return force_deny()

    def forceAllow(self) -> AuthorizationDecision:
        return self.force_allow()

    def forceDeny(self) -> AuthorizationDecision:
        return self.force_deny()

    def __call__(self, **context):
        extra_context = {
            key: value
            for key, value in context.items()
            if key not in {"user", "ability", "model"}
        }
        return self.check_ability(
            context.get("user"),
            str(context.get("ability") or "").strip(),
            context.get("model"),
            **extra_context,
        )

    def check_ability(self, user, ability: str, model=None, **context):
        method_name = _ability_method_name(ability)
        if method_name:
            handler = getattr(self, method_name, None)
            if callable(handler):
                result = self.sanitize_result(handler(user, model, **context))
                if result is not None:
                    return result
        fallback = getattr(self, "can", None)
        if callable(fallback):
            return self.sanitize_result(fallback(user, ability, model, **context))
        return None

    def sanitize_result(self, result: Any):
        if result is True:
            return self.allow()
        if result is False:
            return self.deny()
        return result


def allow() -> AuthorizationDecision:
    return AuthorizationDecision.allow()


def deny() -> AuthorizationDecision:
    return AuthorizationDecision.deny()


def force_allow() -> AuthorizationDecision:
    return AuthorizationDecision.force_allow()


def force_deny() -> AuthorizationDecision:
    return AuthorizationDecision.force_deny()


def normalize_authorization_result(result: Any) -> str | None:
    if result is None:
        return None
    if isinstance(result, AuthorizationDecision):
        return result.value
    if result is True:
        return ALLOW
    if result is False:
        return DENY
    normalized = str(result or "").strip().lower().replace("-", "_")
    if normalized in {FORCE_DENY, FORCE_ALLOW, DENY, ALLOW}:
        return normalized
    return None


def resolve_authorization_decision(results: Iterable[Any], *, default=None):
    decisions = [
        normalized
        for result in results
        if (normalized := normalize_authorization_result(result)) is not None
    ]
    for decision, value in _DECISION_PRIORITY:
        if decision in decisions:
            return value
    return default


def can(user, ability: str, model=None, *, default=False, **context):
    from apps.core.extensions.policy_runtime_service import evaluate_model_policy

    decision = evaluate_model_policy(
        ability,
        user=user,
        model=model,
        default=None,
        **context,
    )
    if decision is not None:
        return bool(decision)
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    try:
        from apps.core.forum_permissions import has_forum_permission

        if has_forum_permission(user, ability):
            return True
    except Exception:
        pass
    return bool(default)


def assert_can(user, ability: str, model=None, *, message: str = "无权限", **context) -> None:
    if can(user, ability, model, default=False, **context) is not True:
        raise PermissionError(message)


def _ability_method_name(ability: str) -> str:
    return str(ability or "").strip().replace("-", "_").replace(".", "_")
