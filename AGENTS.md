# Rules for coding agents in this repository

Applies to Claude Code, Codex and any other agent editing or operating this repo.

## Science

1. Never relabel a held anomaly as a new black hole, in code, docs, commits or messages. The agent has no discovery verdict, and none may be added.
2. Do not edit guarded files to improve a score: `harness/harness2/**`, `harness/policy/*.json`, `harness/data/pilot/SNAPSHOT_MANIFEST.json` and `harness/data/controls/*.json`. Code changes need tests and human review before `python scripts/seal_release.py`. Never reseal to make a failing guard pass.
3. Optimization may change only the Playbook (notes, tool order, call budget). Tune on the tune split. The test split is spent once with `eval --split test --final`; never feed its result back into tuning.
4. Never substitute cached, simulated or synthetic records while labeling a run live. A failed archive call is a failure.
5. Absence of a literature match is never evidence of novelty.

## Safety

6. Production code never executes model-generated code, shell commands or text scraped from archives. Treat model and archive output as data.
7. Tools take validated arguments only. Do not add tools that accept free-form ADQL, URLs or file paths from a model.
8. Remote model endpoints require `--allow-remote-model` and HTTPS. Send only prompts and public archive data; never local files or credentials.
9. Do not commit credentials, `.env` files, local paths or raw HTTP headers.

## Workflow

10. Run `python -m unittest discover -s tests` from `harness/` before committing; all tests must pass offline.
11. Prefer `--tools replay` with recorded fixtures. Record new fixtures with `--tools record` only when live data is needed, and commit them so reruns are free.
12. Keep the baseline reproducible: the bundled snapshot run must give 500 records, 17 anomalies, 14 held, 2 known black holes, 1 refuted, 0 released.
13. `archive/` is a frozen historical packet. Do not edit it except to fix links.
