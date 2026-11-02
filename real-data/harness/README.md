# Universe Search Harness — real-data repair v1

**Start here: this searches measured Gaia non-single-star orbits for review-worthy anomalies. It does not certify new black holes.** The original synthetic detection runner has been replaced, not run behind this interface.

## Run on Windows / WSL / Linux
Use Python **3.11 or 3.12**, extract this entire folder, open a terminal in it.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
python -m pip install --no-build-isolation -e .
python -m harness2.cli.universe verify
python -m unittest discover -s tests -v
python -m harness2.cli.universe run --output runs/my-first-real-run --memory runs/my-memory.json --k 3 --mode sequential
```
WSL/Linux: replace the first two lines with `python3 -m venv .venv` and `source .venv/bin/activate`. This is an **editable source-tree distribution**: keep policy/data alongside code. A standalone wheel is not supported.

The default uses the included **real 2026-10-19 Gaia snapshot**, not today's sky and not simulated fixtures. It reproduces 500 measured records, 17 photocentre-function anomalies: 14 held, 2 known black holes and 1 previously refuted case excluded. **Zero publishable new candidates.** Other previously studied objects are excluded even below the anomaly threshold.

## Connect to live archives
```sh
python -m harness2.cli.universe probe --output runs/connectivity.json
python -m harness2.cli.universe run --live --output runs/live-search-01 --memory runs/live-memory.json --page-size 500 --max-pages 20 --k 3 --context
```
Public read-only ESA Gaia TAP, CDS VizieR and SIMBAD require no account/API key. Live runs verify the schema, page actual NSS records by source/solution key, refresh two published candidate catalogs, optionally retrieve photometry and identifications, and retain exact responses/query/hash/time. A missing service aborts; **there is no stale or simulated fallback**. Current development probes timed out at ESA and returned HTTP503 at CDS; see `runs/live_*probe.json`. Consequently **fresh live end-to-end and real covariance-array format are not yet verified here**. Retry from the user's local connection before relying on live operation.

`--max-pages` bounds a run, not the whole survey. Increase it and use the same output plus `--resume` after an interrupted acquisition; completed run folders cannot be overwritten. Resume verifies cursor/query/cache hashes. If an acquisition already reached its page cap, increasing the cap changes its configuration; start a new acquisition rather than changing state. Acquisition provenance records whether coverage ended or is bounded/partial. The fixed quality preselection (positive/high-SNR parallax and period, published significance>10, finite Thiele-Innes fields) **biases completeness**; significance is a catalog selection field, not our calibrated detection significance. This is a Gaia DR3 orbit channel, not an exhaustive search of every black hole in the universe.

## What the recursion actually does
`--mode parallel` evaluates proposal/domain/composition variants from a fixed parent; `sequential` uses the adopted parent for subsequent steps. Only three finite ranking weights can change. Training aggregates go to the proposer, validation rows select improvements, and a source-level hash partition keeps all solutions for a star in one split. Adopted configuration is stored and used on later runs. There is no synthetic reward, truth label, invented FAP, or arbitrary model-generated Python/shell execution.

The fixed metric is a **heuristic data-quality triage utility**, not discovery yield or scientifically calibrated precision/recall. Small samples may not support adoption. Deterministic mode is reproducible; it is not an LLM disguised as one.

For an already-running local OpenAI-compatible model server:
```sh
# PowerShell: $env:LOCAL_AI_BASE_URL='http://127.0.0.1:8080/v1'
export LOCAL_AI_BASE_URL=http://127.0.0.1:8080/v1
python -m harness2.cli.universe run --output runs/local-model-run --provider local --model YOUR_ACTUAL_SERVED_MODEL_ID --k 3
```
Only loopback endpoints are accepted; no remote provider or keys are included. Failures do not silently switch models. Model weights/server are intentionally not bundled or automatically downloaded.

## RTX 4090
CPU is adequate for the 500-row snapshot, which lacks covariance. Optional `--backend cuda` uses double-precision torch tensors for correlated-observable Monte Carlo **when supported covariance exists**. Install an appropriate CUDA PyTorch build from https://pytorch.org/get-started/locally/ in a separate environment and record `pip freeze`, driver and device. Test CPU/CUDA agreement before large runs. CUDA is not required for network I/O; using a local proposal model is another genuine GPU workload. **No RTX4090 benchmark or GPU run was performed here.** Errors on an explicitly requested unavailable CUDA device are not hidden.

## Results and frozen holdout
`review_queue.json/csv`: held anomalies only, never known/refuted/published cases; `records.json`: full dispositions; `summary.json`: counts; `provenance.json` and acquisition cache: raw evidence; `recursion.json`: actual proposals/adoptions; `human_review_template.json`: required independent checks; `run_manifest.json`: bound inputs/code/output hashes.

Only after freezing the ranking/protocol:
```sh
python -m harness2.cli.universe evaluate-holdout --run runs/my-first-real-run --ledger runs/heldout-ledger.json
```
Keep **one ledger across runs**. Overlapping test-source IDs or the same dataset cannot be evaluated again. Reusing/deleting ledgers or reading test results to tune future versions destroys the heldout claim. This is an auditable workflow, not a tamper-proof security sandbox against the local owner.

Read `docs/SCIENCE.md`, `docs/REPAIR_AUDIT.md`, and `AGENTS.md` before modifying anything.
