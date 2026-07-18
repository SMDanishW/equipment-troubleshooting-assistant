from typing import Any

from pydantic import BaseModel, Field


class EvaluationExpectations(BaseModel):
    document_ids: list[str] = Field(default_factory=list)
    required_terms: list[str] = Field(default_factory=list)
    requires_citations: bool = True
    expects_insufficient_context: bool = False
    expects_safety_block: bool = False


class EvaluationActual(BaseModel):
    text_evidence: list[dict[str, Any]] = Field(default_factory=list)
    image_evidence: list[dict[str, Any]] = Field(default_factory=list)
    answer: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    guardrails: dict[str, Any] = Field(default_factory=dict)
    cross_check: dict[str, Any] = Field(default_factory=dict)


class EvaluationCase(BaseModel):
    id: str
    category: str
    question: str
    expectations: EvaluationExpectations
    actual: EvaluationActual


class CaseMetrics(BaseModel):
    retrieval_document_recall: float
    required_term_recall: float
    citation_validity: float
    citation_presence: float
    grounding: float
    insufficient_context: float
    safety: float


class CaseResult(BaseModel):
    id: str
    category: str
    passed: bool
    metrics: CaseMetrics
    failures: list[str]


class EvaluationReport(BaseModel):
    dataset: str
    cases: int
    passed: int
    pass_rate: float
    metric_averages: CaseMetrics
    results: list[CaseResult]
