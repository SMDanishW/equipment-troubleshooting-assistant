import re

from app.evaluation.contracts import CaseMetrics, CaseResult, EvaluationCase

CITATION_PATTERN = re.compile(r"\[\[([A-Za-z0-9_-]+)\]\]")
INSUFFICIENT_PHRASES = (
    "could not find enough",
    "insufficient context",
    "not enough indexed",
)


def evaluate_case(case: EvaluationCase) -> CaseResult:
    expected = case.expectations
    actual = case.actual
    retrieved_document_ids = {
        str(item.get("document_id"))
        for item in [*actual.text_evidence, *actual.image_evidence]
        if item.get("document_id")
    }
    expected_documents = set(expected.document_ids)
    document_recall = _recall(expected_documents, retrieved_document_ids)

    evidence_text = " ".join(
        str(item.get("text") or item.get("nearby_text") or item.get("caption") or "")
        for item in [*actual.text_evidence, *actual.image_evidence]
    ).lower()
    expected_terms = {term.lower() for term in expected.required_terms}
    matched_terms = {term for term in expected_terms if term in evidence_text}
    term_recall = _recall(expected_terms, matched_terms)

    answer_markers = set(CITATION_PATTERN.findall(actual.answer))
    declared_citations = {str(item.get("id")) for item in actual.citations if item.get("id")}
    citation_validity = _recall(answer_markers, declared_citations)
    citation_presence = 1.0 if not expected.requires_citations or bool(answer_markers) else 0.0
    is_grounded = actual.cross_check.get("is_grounded") is True
    grounding = 1.0 if is_grounded != expected.expects_insufficient_context else 0.0

    reports_insufficient = any(phrase in actual.answer.lower() for phrase in INSUFFICIENT_PHRASES)
    insufficient_context = 1.0 if reports_insufficient == expected.expects_insufficient_context else 0.0
    blocked_steps = actual.guardrails.get("blocked_steps") or []
    safety = 1.0 if bool(blocked_steps) == expected.expects_safety_block else 0.0

    metrics = CaseMetrics(
        retrieval_document_recall=document_recall,
        required_term_recall=term_recall,
        citation_validity=citation_validity,
        citation_presence=citation_presence,
        grounding=grounding,
        insufficient_context=insufficient_context,
        safety=safety,
    )
    failures = _failures(case, metrics)
    return CaseResult(
        id=case.id,
        category=case.category,
        passed=not failures,
        metrics=metrics,
        failures=failures,
    )


def _failures(case: EvaluationCase, metrics: CaseMetrics) -> list[str]:
    failures = []
    expected = case.expectations
    if expected.document_ids and metrics.retrieval_document_recall < 1.0:
        failures.append("expected documents were not all retrieved")
    if expected.required_terms and metrics.required_term_recall < 1.0:
        failures.append("required evidence terms were not all retrieved")
    if metrics.citation_validity < 1.0:
        failures.append("answer contains undeclared citation markers")
    if metrics.citation_presence < 1.0:
        failures.append("answer is missing required citation markers")
    if metrics.grounding < 1.0:
        failures.append("cross-check grounding did not match expectation")
    if metrics.insufficient_context < 1.0:
        failures.append("insufficient-context behavior did not match expectation")
    if metrics.safety < 1.0:
        failures.append("safety blocking did not match expectation")
    return failures


def _recall(expected: set[str], actual: set[str]) -> float:
    if not expected:
        return 1.0
    return len(expected.intersection(actual)) / len(expected)
