<p align="center">
  <img src="docs/media/research-orbits.gif" alt="Animated orbital illustration" width="100%">
</p>

# Universe Search Harness

Agentic follow-up of Gaia astrometric black-hole candidates, where every agent verdict is checked against the data its tools actually returned.

<p>
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="Gaia DR3" src="https://img.shields.io/badge/Data-Gaia%20DR3-3cb8b0?style=flat-square">
  <img alt="Tests" src="https://img.shields.io/badge/tests-63%20offline-4c9a2a?style=flat-square">
  <img alt="License" src="https://img.shields.io/badge/code-Apache--2.0-6376d9?style=flat-square">
</p>

> [!IMPORTANT]
> No new black hole is claimed. The agent cannot output a discovery verdict; its best possible outcome is "needs follow-up".

## The problem

Gaia DR3 published about 170,000 astrometric binary orbits. A few of them have photocentre orbits large enough to imply a dark companion of several solar masses. Most of those turn out to be bad fits, blended light, luminous companions or triples, or have already been studied. Separating them takes many small lookups across Gaia, SIMBAD, VizieR and the literature. That is good work for an agent, but only if you can tell when the agent is making things up.

## What this repo does

1. Triage pipeline (`harness2-universe run`). Reads Gaia DR3 two-body orbits, computes the photocentre mass function f_phot = (a0/parallax)^3 / P^2, excludes known objects, and holds anomalies for review. The bundled 500-row snapshot reproduces exactly: 17 anomalies, 14 held, 2 known black holes and 1 refuted candidate excluded, 0 released.

2. Follow-up agent (`harness2-agent investigate`). A tool-using LLM investigates one candidate at a time with six read-only tools: `nss_orbit`, `gaia_quality`, `simbad_lookup`, `vizier_crossmatch`, `known_catalogs`, `ads_search`. It finishes by submitting a structured verdict in which every claim cites `(call_id, field, value)`.

3. Verifier. The verifier rejects any citation that does not match the tool output, and applies rules per verdict. For example, `PUBLISHED_PRIOR` must cite a real `matched=true` result. Rejected verdicts become `UNVERIFIED`, so a model cannot score by inventing evidence.

4. Blind controls and an outer loop (`harness2-agent eval`, `optimize`). There are 42 sources in the snapshot that are already published: Gaia BH1 and BH2, Shahaf 2023 and Li 2026 candidates. Each control's labeling catalog is withheld, so the agent has to rediscover it through other routes. The harness2 Propose/Probe/Compose loop then tunes the agent's playbook (strategy text, tool order, call budget) on the tune split. A playbook is adopted only on strict improvement, and the test split can be spent once.

## Why it works for agentic loops

| Need | How it is handled |
| --- | --- |
| A reward that can't be gamed | Evidence-bound verdicts, checked mechanically. Always answering "published" scores zero. |
| Labels the agent hasn't seen | Blind positive controls with the labeling source withheld; a one-shot test-split ledger |
| Bounded cost | Per-candidate limits on steps, tool calls and tokens; compact tool output; shared cache |
| Free reruns | `--tools record` saves every archive response as a fixture; `--tools replay` reruns offline at zero network cost |
| Any model | OpenAI-compatible (OpenRouter, vLLM, llama.cpp, Ollama, LM Studio), Anthropic, plus a deterministic heuristic baseline |
| Safe by default | The model never writes queries or URLs. Arguments are validated against allowlists, nothing is executed, remote endpoints need explicit opt-in, and guarded code is hash-sealed. |

## Quick start

Python 3.11 or newer.

```sh
cd harness
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.lock
pip install --no-build-isolation --no-deps -e .

harness2-universe verify
python -m unittest discover -s tests          # 63 tests, offline
harness2-universe run --output runs/base --memory runs/base-memory.json
```

### Run the agent

The archives are public and need no keys. Record live responses once, then replay them as often as you like.

```sh
# Deterministic baseline, no model, records fixtures as it goes
harness2-agent eval --run runs/base --provider heuristic --tools record --fixtures fixtures/live --out runs/eval-heuristic

# Local model (any OpenAI-compatible server on loopback)
harness2-agent eval --run runs/base --provider openai --base-url http://127.0.0.1:8080/v1 --model qwen3 \
    --tools replay --fixtures fixtures/live --out runs/eval-local

# OpenRouter or Anthropic (opt in to remote; only prompts and public archive data are sent)
export OPENROUTER_API_KEY=...
harness2-agent eval --run runs/base --provider openrouter --model YOUR_OPENROUTER_MODEL_ID \
    --allow-remote-model --tools replay --fixtures fixtures/live --out runs/eval-or

# Tune the playbook on the tune split, then spend the test split once
harness2-agent optimize --run runs/base --rounds 4 --proposer llm --provider anthropic \
    --model claude-sonnet-5-5 --allow-remote-model --memory runs/playbook.json --out runs/opt
harness2-agent eval --run runs/base --split test --final --playbook runs/playbook.json --provider anthropic \
    --model claude-sonnet-5-5 --allow-remote-model

# Investigate the 14 held candidates with the tuned playbook
harness2-agent investigate --run runs/base --held --playbook runs/playbook.json --provider anthropic \
    --model claude-sonnet-5-5 --allow-remote-model --tools record --fixtures fixtures/live --out runs/held14
```

Add `--ads` with `ADS_API_TOKEN` set to enable full-text literature search. Without ADS, the two Li 2026 controls can't be rediscovered. That is intentional: it measures what the toolset can and can't find.

Each investigation writes a JSON file with the full transcript, every tool call with provenance, token usage and the verifier's result. `summary.json` reports recall on controls, verified rate, citation failure rate, and mean tool calls and tokens per candidate.

## Results so far

The DR3 review from October and November 2026 is preserved in [`archive/dr3-review-2026-11`](archive/dr3-review-2026-11/README.md). Of the 14 held sources, two turned out to be already-published compact-binary candidates in [Li et al. 2026](https://arxiv.org/abs/2610.34715). A general web-search index failed to find known positive controls during that review. That failure is why this repo now measures agents on blind controls instead of trusting their literature searches.

The [interactive explorer](dashboard/README.md) shows the 14 held sources in 3D with their measurements, risks and references.

<p align="center"><img src="docs/media/explorer-overview.jpg" alt="Gaia source explorer" width="90%"></p>

## Limitations

- Controls are positives only. Recall measures whether the agent finds prior work. Nothing here measures discovery precision, because no labeled true negatives exist.
- The bundled snapshot lacks correlation vectors, so Monte Carlo uncertainty is unavailable for all 500 rows. Live runs fetch `corr_vec`.
- Live tool queries (Gaia `gaia_source` columns, SIMBAD `has_ref`/`ref` joins, VizieR tables) were written against the published schemas but have not yet run from this repository's CI. Run one `--tools record` pass and check the fixtures before relying on them.
- The heuristic thresholds (RUWE, IPD, significance) are triage defaults, not validated physical cuts.

## Next: Gaia DR4

Gaia DR4 is scheduled for 2 December 2026 and includes epoch astrometry and radial velocities. That allows actual orbit refits instead of triage of catalog solutions. Planned work: a DR4 connector after schema verification on release day, an `epoch_astrometry` tool, and controls rebuilt from DR3 results that DR4 confirms or refutes.

## Layout

| Path | Contents |
| --- | --- |
| [`harness/`](harness/README.md) | Python package: pipeline, agent, verifier, controls, tests |
| [`harness/harness2/agent/`](harness/harness2/agent) | `tools.py`, `models.py`, `loop.py`, `verify.py`, `evaluate.py` |
| [`harness/data/controls/`](harness/data/controls/controls_v1.json) | 42 labeled controls with a fixed tune/test split |
| [`dashboard/`](dashboard/README.md) | Static 3D explorer for the held sources |
| [`archive/dr3-review-2026-11/`](archive/dr3-review-2026-11/README.md) | Frozen evidence packet from the first review |
| [`AGENTS.md`](AGENTS.md) | Rules for coding agents working in this repo |

## Attribution

The code is Apache-2.0. Gaia data are from ESA/Gaia/DPAC. Third-party papers, catalogs and survey products keep their own terms; see [third-party notices](archive/dr3-review-2026-11/public-review/THIRD_PARTY_NOTICES.md). Some included source archives are CC BY-NC-SA 4.0.
