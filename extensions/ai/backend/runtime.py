from __future__ import annotations

from extensions.ai.backend.services import AiService


def ai_service_provider(_host=None):
    return {
        "settings": AiService.get_settings,
        "coach_question": AiService.coach_question,
        "summon_role": AiService.summon_role,
        "judge_bounty": AiService.judge_bounty,
        "summarize_discussion": AiService.summarize_discussion,
    }
