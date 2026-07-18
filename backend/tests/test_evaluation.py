import json
from pathlib import Path

from app.evaluation.contracts import EvaluationCase
from app.evaluation.evaluator import evaluate_case
from app.evaluation.runner import run_evaluation, write_report


def make_case(**overrides):
    payload = {
        "id": "case-1",
        "category": "grounding",
        "question": "What does E102 mean?",
        "expectations": {
            "document_ids": ["document-1"],
            "required_terms": ["pressure sensor"],
            "requires_citations": True,
        },
        "actual": {
            "text_evidence": [
                {"id": "txt_1", "document_id": "document-1", "text": "Pressure sensor failure."}
            ],
            "answer": "Check the pressure sensor. [[txt_1]]",
            "citations": [{"id": "txt_1"}],
            "guardrails": {"approved": True, "blocked_steps": []},
            "cross_check": {"is_grounded": True},
        },
    }
    payload.update(overrides)
    return EvaluationCase.model_validate(payload)


def test_grounded_case_passes_all_required_metrics():
    result = evaluate_case(make_case())

    assert result.passed
    assert result.metrics.retrieval_document_recall == 1.0
    assert result.metrics.citation_validity == 1.0


def test_undeclared_citation_and_wrong_document_fail():
    case = make_case()
    case.actual.answer = "Unsupported answer. [[txt_missing]]"
    case.actual.text_evidence[0]["document_id"] = "other-document"

    result = evaluate_case(case)

    assert not result.passed
    assert "expected documents were not all retrieved" in result.failures
    assert "answer contains undeclared citation markers" in result.failures


def test_versioned_smoke_dataset_and_report(tmp_path):
    dataset = Path(__file__).parents[1] / "evaluation" / "datasets" / "smoke_v1.jsonl"
    report = run_evaluation(dataset)
    output = tmp_path / "report.json"
    write_report(report, output)

    assert report.cases == 3
    assert report.pass_rate == 1.0
    assert json.loads(output.read_text(encoding="utf-8"))["passed"] == 3
