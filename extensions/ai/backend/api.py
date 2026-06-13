from __future__ import annotations

from ninja import Body, Router

from apps.core.api_errors import api_error
from apps.core.auth import AuthBearer
from extensions.ai.backend.schemas import (
    AiBountyJudgeSchema,
    AiCoachQuestionSchema,
    AiDiscussionSummarySchema,
    AiSummonRoleSchema,
)
from extensions.ai.backend.services import AiService


router = Router()


@router.post("/ai/question-coach", auth=AuthBearer(), tags=["AI"])
def coach_question(request, payload: AiCoachQuestionSchema = Body(...)):
    try:
        return AiService.coach_question(
            title=payload.title,
            content=payload.content,
            user=request.auth,
        )
    except ValueError as exc:
        return api_error(str(exc), status=400)


@router.post("/ai/summon", auth=AuthBearer(), tags=["AI"])
def summon_role(request, payload: AiSummonRoleSchema = Body(...)):
    try:
        return AiService.summon_role(
            role=payload.role,
            title=payload.title,
            content=payload.content,
            user=request.auth,
        )
    except ValueError as exc:
        return api_error(str(exc), status=400)


@router.post("/ai/bounty-judge", auth=AuthBearer(), tags=["AI"])
def judge_bounty(request, payload: AiBountyJudgeSchema = Body(...)):
    try:
        return AiService.judge_bounty(
            question=payload.question,
            answer=payload.answer,
            user=request.auth,
        )
    except ValueError as exc:
        return api_error(str(exc), status=400)


@router.post("/ai/discussion-summary", auth=AuthBearer(), tags=["AI"])
def summarize_discussion(request, payload: AiDiscussionSummarySchema = Body(...)):
    try:
        return AiService.summarize_discussion(
            discussion_id=payload.discussion_id,
            user=request.auth,
        )
    except ValueError as exc:
        return api_error(str(exc), status=400)
