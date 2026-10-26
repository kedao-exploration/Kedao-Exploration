from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class EvidenceItem(BaseModel):
    statement: str
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"


class GoalSet(BaseModel):
    long_term: list[EvidenceItem] = Field(default_factory=list)
    this_term: list[EvidenceItem] = Field(default_factory=list)
    next_30_days: list[EvidenceItem] = Field(default_factory=list)


class AttentionItem(BaseModel):
    category: Literal["support", "follow_up", "data_gap"]
    priority: Literal["low", "medium", "high"]
    note: str
    evidence_refs: list[str] = Field(default_factory=list)


class StudentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_state: list[EvidenceItem]
    goals: GoalSet
    interests: list[EvidenceItem]
    engagement_and_clubs: list[EvidenceItem]
    skills_and_self_regulation: list[EvidenceItem]
    wellbeing_and_support_preferences: list[EvidenceItem]
    constraints: list[EvidenceItem]
    recommendation_profile: list[EvidenceItem]
    advisor_attention: list[AttentionItem]
    uncertainties: list[str]
    summary: str


class Theme(BaseModel):
    name: str
    count: int = Field(ge=0)
    percentage: float = Field(ge=0, le=100)
    evidence: list[str] = Field(default_factory=list)


class ActivityRecommendation(BaseModel):
    title: str
    rationale: str
    suggested_format: str
    estimated_count: int = Field(ge=0)
    target_student_ids: list[str] = Field(default_factory=list)
    priority: Literal["low", "medium", "high"]


class AggregateReport(BaseModel):
    overview: str
    majority_themes: list[Theme]
    minority_needs: list[Theme] = Field(max_length=8)
    activity_recommendations: list[ActivityRecommendation]
    coverage_and_data_gaps: list[str]


class ActivityMatch(BaseModel):
    include: bool
    fit_score: int = Field(ge=0, le=100)
    interest_score: int = Field(ge=0, le=100)
    need_score: int = Field(ge=0, le=100)
    availability_score: int = Field(ge=0, le=100)
    reasons: list[str] = Field(max_length=4)
    evidence_refs: list[str]
    caution: str | None = None


class SurveyQuestion(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,39}$")
    type: Literal["single", "multiple", "short_text", "long_text", "scale"]
    label: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=800)
    required: bool = False
    sensitive: bool = False
    options: list[dict[str, str]] | None = None
    min: int | None = None
    max: int | None = None
    minLabel: str | None = None
    maxLabel: str | None = None
    maxLength: int | None = Field(default=None, le=10000)


class SurveySchema(BaseModel):
    questions: list[SurveyQuestion] = Field(min_length=1, max_length=50)


class ActivityCreate(BaseModel):
    title: str
    description: str
    start_at: datetime
    end_at: datetime
    location: str | None = None
    tags: list[str] = Field(default_factory=list)
    capacity: int | None = None
