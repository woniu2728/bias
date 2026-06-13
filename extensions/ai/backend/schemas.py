from __future__ import annotations

from pydantic import BaseModel, Field


class AiCoachQuestionSchema(BaseModel):
    title: str = Field("", max_length=200)
    content: str = Field("", max_length=12000)


class AiSummonRoleSchema(BaseModel):
    role: str = Field("scribe", max_length=40)
    title: str = Field("", max_length=200)
    content: str = Field("", max_length=12000)


class AiBountyJudgeSchema(BaseModel):
    question: str = Field("", max_length=12000)
    answer: str = Field("", max_length=12000)


class AiDiscussionSummarySchema(BaseModel):
    discussion_id: int = Field(..., ge=1)
