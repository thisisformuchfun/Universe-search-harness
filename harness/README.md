# harness2-universe

Python package for the Gaia DR3 triage pipeline and the evidence-verified follow-up agent. See the [top-level README](../README.md) for the overview.

## Install

```sh
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.lock
pip install --no-build-isolation --no-deps -e .
harness2-universe verify
python -m unittest discover -s tests
```

This is an editable source-tree install: `policy/`, `data/` and the code must stay together, because the guard hashes cover all three.

## Pipeline: harness2-universe

```sh
harness2-universe run --output runs/base --memory runs/base-memory.json            # bundled snapshot
harness2-universe probe --output runs/connectivity.json                           # check archive access
harness2-universe run --live --output runs/live-01 --page-size 500 --max-pages 20 --context
```

- The default input is the bundled 2026-10-19 snapshot of 500 quality-cut Gaia DR3 orbits. It is real data, not a fresh query.
- Live mode pages `gaiadr3.nss_two_body_orbit` by key, refreshes the published catalogs and stores raw responses with hashes. If a service fails, the run aborts. There is no stale or simulated fallback.
- Output files: `records.json` (all dispositions), `review_queue.json/csv` (held only), `summary.json`, `provenance.json`, `run_manifest.json` (input, code and output hashes).
- The old three-weight ranking loop (`--provider deterministic|local`) is still there for reproducibility. The agent below is where the model does real work.

## Survey: harness2-survey

```sh
harness2-survey acquire --store data/cache/bulk                       # whole NSS table + context, verified
harness2-survey run --store data/cache/bulk --out runs/survey-01      # find, then vet as candidates accumulate
harness2-survey bench --store data/cache/bulk --backends numpy torch:cpu
```

Searches all 443,205 Gaia DR3 orbit solutions through an astrometric and a spectroscopic channel, then runs an automated vetting battery on the shortlist. The vetting stage triggers by itself whenever enough candidates are waiting. Every tier is a hold or an exclusion; see [`docs/SURVEY.md`](docs/SURVEY.md). The first full run is committed under `runs/survey-dr3-20261112/`.

## Agent: harness2-agent

| Command | Purpose |
| --- | --- |
| `investigate --run R --held` or `--ids ...` | Run the agent on chosen sources and write a transcript and verdict per source |
| `eval --run R [--split tune]` | Blind evaluation on labeled controls; prints recall, verified rate and cost |
| `eval --run R --split test --final` | One-shot holdout; refuses a second run for the same control set |
| `optimize --run R --rounds N --proposer rule\|llm` | Propose/Probe/Compose over the playbook on the tune split |
| `build-controls --run R` | Regenerate `data/controls/controls_v1.json` from a snapshot run |

Shared options:

- `--provider heuristic|openai|openrouter|anthropic`, `--model`, `--base-url`, `--api-key-env`
- `--allow-remote-model` is required for any non-loopback endpoint, which must be HTTPS
- `--tools replay|record|live` and `--fixtures DIR`. Replay is the default and never touches the network.
- `--ads` enables `ads_search`; live use needs `ADS_API_TOKEN`
- Budgets: `--max-steps`, `--max-tool-calls`, `--max-tokens` per candidate. The playbook's own `max_tool_calls` also applies.
- `--playbook FILE` uses a tuned playbook from `optimize --memory`

### Module map

| File | Role |
| --- | --- |
| `harness2/agent/tools.py` | Tool specs, argument validation, per-investigation call log, live/replay/record backends |
| `harness2/agent/models.py` | OpenAI-compatible and Anthropic adapters, endpoint policy, heuristic baseline, scripted model |
| `harness2/agent/loop.py` | Bounded model-tool loop and system prompt |
| `harness2/agent/verify.py` | Evidence verifier and per-verdict rules |
| `harness2/agent/evaluate.py` | Controls, scoring, proposers, Propose/Probe/Compose, one-shot test ledger |
| `policy/agent_tools.json` | Gaia release, column list, allowlisted VizieR catalogs, compact-companion bibcodes |

### Scoring

`objective = recall + 0.25 * verified_rate - 0.02 * mean_tool_calls - 0.002 * mean_ktokens`

Recall counts only verified `PUBLISHED_PRIOR` verdicts on blind positive controls. The weights live in `evaluate.score` and are guarded code, so a proposal can't change them.

### Adding a tool or catalog

Add a VizieR catalog in `policy/agent_tools.json` only after confirming the table name and Gaia ID column from the official ReadMe. A new tool needs a `LiveBackend._<name>` method, an entry in `TOOL_NAMES` and `TOOL_DESCRIPTIONS`, validation in `Session._validate`, and a test. Then reseal (see below).

## Guard and reseal

`policy/guard_manifest.json` hashes every file under `harness2/`, the policies, the snapshot manifest and the controls. Runs and optimization abort if any of them change mid-run. After a reviewed code change with passing tests, a maintainer reseals:

```sh
python scripts/seal_release.py
```

Never reseal to make a failing guard pass in an automated loop.

## Gaia DR4

Gaia DR4 is scheduled for 2 December 2026. The harness still reads DR3; [`docs/DR4.md`](docs/DR4.md) lists every DR3 assumption in the code and the release-day runbook.

```sh
python scripts/dr4_readiness.py requirements                         # tables and columns the harness reads, offline
python scripts/dr4_readiness.py check --release gaiadr3 --sample 0   # positive control against DR3
python scripts/dr4_readiness.py check --release gaiadr4 --out runs/dr4-readiness.json
python scripts/dr4_readiness.py watchlist --out data/dr4/watchlist.csv
```

`check` reports `NOT_PUBLISHED`, `SCHEMA_COMPATIBLE`, `NEEDS_PARSER_REVIEW`, `INCOMPATIBLE` or `ARCHIVE_ERROR`. A compatible schema is not permission to switch: changing `gaia_release` and the connector is a guarded change that needs review and a reseal.

## GPU

`harness2-survey run --backend torch:cuda` (or `torch:mps`, `torch:cpu`) moves the survey's Monte Carlo kernels to PyTorch; the default NumPy backend runs chunks on a thread pool. The PyTorch path is tested against NumPy on CPU only, and no GPU timing is claimed here.

For the sealed pipeline, CPU is enough for the snapshot. `--backend cuda` uses float64 torch for covariance Monte Carlo when live rows carry `corr_vec`. Install a CUDA PyTorch build separately and check that CPU and CUDA agree.

## Further reading

`docs/SCIENCE.md` covers the physics and caveats. `docs/SURVEY.md` covers the whole-catalogue survey and its vetting battery. `docs/DR4.md` covers the move to Gaia DR4. `docs/REPAIR_AUDIT.md` and the independent reviews record how the first version was found to cheat on synthetic data and how that was fixed.
