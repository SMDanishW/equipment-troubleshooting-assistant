from typing import Any

from pydantic import BaseModel, Field


class QueryUnderstandingOutput(BaseModel):
    query_type: str
    normalized_query: str
    is_followup: bool
    previous_user_context: str
    needs_clarification: bool
    clarification_questions: list[str]


class DiagnosisCause(BaseModel):
    cause: str
    evidence_ids: list[str]


class DiagnosisOutput(BaseModel):
    likely_causes: list[DiagnosisCause]
    insufficient_context: bool


class TroubleshootingStep(BaseModel):
    step: str
    evidence_ids: list[str]
    risk_level: str


class TroubleshootingOutput(BaseModel):
    steps: list[TroubleshootingStep]


class GuardrailsOutput(BaseModel):
    approved: bool
    safety_notes: list[str]
    blocked_steps: list[TroubleshootingStep]
    approved_steps: list[TroubleshootingStep]


class CrossCheckIssue(BaseModel):
    step: str
    issue: str


class CrossCheckOutput(BaseModel):
    is_grounded: bool
    unsupported_claims: list[str]
    citation_issues: list[CrossCheckIssue]


class FinalSynthesisOutput(BaseModel):
    answer: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    images: list[dict[str, Any]] = Field(default_factory=list)
