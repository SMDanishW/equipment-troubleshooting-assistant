# AI Evaluation Harness

Datasets are versioned JSONL snapshots containing expectations and captured pipeline outputs. Run the smoke gate from the backend directory:

```powershell
python -m app.evaluation.cli --dataset evaluation/datasets/smoke_v1.jsonl --output evaluation/reports/smoke_v1.json --min-pass-rate 1.0
```

The command exits non-zero when the required pass rate is not met. Snapshot cases are deterministic and suitable for CI; they do not call an external model.
