import json
from pathlib import Path

from app.evaluation.contracts import CaseMetrics, EvaluationCase, EvaluationReport
from app.evaluation.evaluator import evaluate_case


def load_cases(path: Path) -> list[EvaluationCase]:
    cases = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            cases.append(EvaluationCase.model_validate_json(line))
        except Exception as exc:
            raise ValueError(f"Invalid evaluation case at {path}:{line_number}") from exc
    if not cases:
        raise ValueError(f"Evaluation dataset {path} contains no cases.")
    return cases


def run_evaluation(path: Path) -> EvaluationReport:
    results = [evaluate_case(case) for case in load_cases(path)]
    metric_names = tuple(CaseMetrics.model_fields)
    averages = {
        name: sum(getattr(result.metrics, name) for result in results) / len(results)
        for name in metric_names
    }
    passed = sum(result.passed for result in results)
    return EvaluationReport(
        dataset=path.name,
        cases=len(results),
        passed=passed,
        pass_rate=passed / len(results),
        metric_averages=CaseMetrics(**averages),
        results=results,
    )


def write_report(report: EvaluationReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.model_dump(), indent=2) + "\n", encoding="utf-8")
