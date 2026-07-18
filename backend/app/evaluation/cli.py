import argparse
from pathlib import Path

from app.evaluation.runner import run_evaluation, write_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic equipment-agent AI evaluations.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--min-pass-rate", type=float, default=1.0)
    args = parser.parse_args()
    if not 0.0 <= args.min_pass_rate <= 1.0:
        parser.error("--min-pass-rate must be between 0 and 1")

    report = run_evaluation(args.dataset)
    if args.output:
        write_report(report, args.output)
    print(report.model_dump_json(indent=2))
    return 0 if report.pass_rate >= args.min_pass_rate else 1


if __name__ == "__main__":
    raise SystemExit(main())
