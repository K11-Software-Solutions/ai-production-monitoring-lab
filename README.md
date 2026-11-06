# AI Production Monitoring Lab

[![CI quality gates](https://github.com/K11-Software-Solutions/ai-production-monitoring-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/K11-Software-Solutions/ai-production-monitoring-lab/actions/workflows/ci.yml)
[![Code: MIT](https://img.shields.io/badge/Code-MIT-blue.svg)](LICENSE) [![Articles: CC BY 4.0](https://img.shields.io/badge/Articles-CC%20BY%204.0-lightgrey.svg)](articles/LICENSE.md)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![No dependencies](https://img.shields.io/badge/runtime%20deps-none-success)

**Monitor an AI assistant in production, and test the monitoring itself.** Tracing, online evals without reference answers, drift detection, runtime guardrails, shadow releases, incident triage and the feedback loop into regression tests, all gated in CI.

The fourth lab in a series for quality engineers moving into AI:

| Lab | Question it answers |
|---|---|
| [Becoming an AI Quality Engineer](https://github.com/K11-Software-Solutions/becoming-ai-quality-engineer) | Is the RAG **application** good enough to ship? |
| [LLM Model Testing Lab](https://github.com/K11-Software-Solutions/llm-model-testing-lab) | Is the **model** good enough? |
| [Agent Testing Lab](https://github.com/K11-Software-Solutions/agent-testing-lab) | Is the **agent** safe to let act? |
| **AI Production Monitoring Lab** (this repo) | Is it **still** good, for the users we actually have, right now? |

## How it works

A deterministic **simulator** produces 14 days of traffic for a support assistant and injects six realistic incidents on known days. Because the simulator knows the ground truth, the lab can test whether the monitors catch each one, how fast, and how many false alarms they raise.

| Day | Incident | Caught by |
|---|---|---|
| 5 | Silent model update (chattier, more hallucinations) | output tokens, groundedness failures |
| 8 | Feature launch the help articles don't cover | unknown-topic rate, topic drift (PSI), refusals, thumbs-down |
| 9 | Language shift (Spanish-speaking users) | language drift, language mismatch |
| 11–12 | Provider latency spike on a few requests | **p95** latency (the mean barely moves) |
| 12 | Prompt-injection campaign | injection-flag rate |
| 13 | Prompt bloat | input tokens, cost per request |

A second **quiet** scenario has no incidents: any alert on it is a false alarm.

## Articles

| # | Article |
|---|---|
| 01 | [Why Production Is Where AI Quality Is Decided](articles/01-why-production-decides-ai-quality.md) |
| 02 | [Tracing: What to Record (and What Never to Store)](articles/02-tracing-what-to-record.md) |
| 03 | [Online Evals Without Reference Answers](articles/03-online-evals-without-reference-answers.md) |
| 04 | [Monitors and Drift: Rates, Ratios, PSI, and Why Averages Lie](articles/04-monitors-and-drift.md) |
| 05 | [Guardrails in Production and Their Error Rates](articles/05-guardrails-in-production.md) |
| 06 | [Shadow Testing and Release Decisions](articles/06-shadow-testing-and-release-decisions.md) |
| 07 | [From Alert to Root Cause to Regression Test](articles/07-from-alert-to-regression-test.md) |
| 08 | [Testing the Monitoring System](articles/08-testing-the-monitoring-system.md) |

## Quick start

Requirements: Python 3.11+. There are no runtime dependencies, and no API key is needed.

```bash
git clone https://github.com/K11-Software-Solutions/ai-production-monitoring-lab.git
cd ai-production-monitoring-lab
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

```bash
pytest                                                        # unit tests (~7 s)
python -m prodlab.simulate --scenario incidents --out data/incidents.jsonl
python -m prodlab.monitors data/incidents.jsonl              # daily metrics + alerts
python -m evals.run_monitoring_evals                         # test the monitoring, with gates
python -m evals.run_monitoring_evals --monitor mean-latency  # negative control: must FAIL
```

## Repository layout

```text
prodlab/
  system.py        the assistant under monitoring: retrieval + model versions (incl. a silent update)
  simulate.py      deterministic traffic with scheduled incidents; "incidents" and "quiet" scenarios
  traces.py        trace records (JSON Lines); PII redacted at write time
  guardrails.py    PII detection and redaction (email, phone, Luhn-checked cards), injection flags
  online_evals.py  reference-free checks (groundedness, refusal, language) + risk-based sampling
  monitors.py      daily metrics; ratio rules, z-tested rate rules, PSI drift; alerts
  triage.py        global changes, segment breakdown, export of PII-free regression cases
  release.py       shadow testing and a deterministic promote/reject rule
evals/
  run_monitoring_evals.py   detection recall/delay, false alarms, guardrails, evaluator validity,
                            triage, feedback loop, release decisions
  thresholds.json           gates on the monitoring system
  datasets/guardrail_labels.jsonl
tests/             63 deterministic tests
articles/          the eight articles
.github/workflows/ci.yml   tests → monitoring evals + 2 negative controls; traces uploaded
```

## What the lab finds

- **Averages hide tail latency.** A mean-based monitor misses a latency incident that p95 catches on day one.
- **Statistics prevent alert fatigue.** Without a z-test and a minimum effect size, a quiet week produces dozens of false alarms; with them, zero.
- **The cheapest signal fires first.** The silent model update showed up in output tokens before quality metrics.
- **Guardrails have locale bugs.** The labelled set caught a missed UK phone number and an order number misread as a phone number.
- **Release metrics encode values.** A naive refusal-rate rule rejected the *more honest* candidate model.
- **Global changes confound triage.** The new model version "explained" every alert until it was separated out.
- **Overlap-based evaluators miss changed numbers.** A refund window of 60 days instead of 30 passes the groundedness check.

## Experiments (multi-seed)

The CI gate checks one published scenario. The paper's experiments ([`experiments/`](experiments)) rerun everything across **50 seeds** and sweep incident sizes and alert thresholds:

```bash
python -m experiments.run_experiments            # ~15 min; writes experiments/results/summary.md and CSVs
pip install -r requirements-experiments.txt
python -m experiments.plot_figures               # figures in experiments/results/figures/
```

The multi-seed results qualify some single-seed claims, and they are reported as such (see [`experiments/results/summary.md`](experiments/results/summary.md)):

- The default latency incident (6% of requests slowed) sits near the detection boundary: the p95 rule catches it on onset day in about 74% of seeds, the mean rule in about 2%.
- The standard monitors raise at least one false alarm in a few of the 50 quiet runs, not zero in every run.
- On *subtle* incidents the default minimum-effect floor costs recall; a stricter z-threshold without the floor does better at no extra false alarms.
- At an equal evaluation budget, random sampling detects the silent model update at least as well as risk-based sampling, which spends budget on already-flagged traffic.

## Related K11 tools

This lab watches **real traffic after release**. Two K11 tools test with **synthetic inputs before and alongside release**, and together they cover most of an AI system's lifecycle:

```text
 PR / config change ──► pre-release security ──► release ──► production ──► incident ──► regression case
 llm-eval-agent-app     llm-assurance-toolkit    this lab:   this lab:     this lab:     feeds back into
 (bias & robustness     (OWASP LLM Top 10        shadow test traces,       triage        the test sets
  gate on every PR)      red-teaming, CI gate)               drift, alerts
```

| Tool | What it does | How it relates to this lab |
|---|---|---|
| [llm-eval-agent-app](https://github.com/K11-Software-Solutions/llm-eval-agent-app) | GitHub App that runs bias and robustness evaluations on every pull request, posts scorecards as Check Runs and blocks merges below threshold; also runs scheduled evals and tracks trends | The PR-time counterpart of this lab's release gate (article 06). Its scheduled evals are *synthetic monitoring*: a fixed probe set that catches regressions even when live traffic is low |
| [k11techlab-llm-assurance-toolkit](https://github.com/K11-Software-Solutions/k11techlab-llm-assurance-toolkit) | Red-teaming with 41 probes mapped to the OWASP Top 10 for LLM Applications, deterministic leak/PII/refusal detectors, an optional LLM judge, a CI gate and an MCP server | The attack side of this lab's guardrails and injection-campaign incident (article 05). Run it before release; this lab measures how guardrails perform on real traffic afterwards |

Failures found in production here make good new cases for both tools, and their findings make good regression cases here.

## Limitations

Simulated traffic (no seasonality, bots or correlated outages), a fixed baseline, daily windows, simple evaluators and no alert grouping. See [article 08](articles/08-testing-the-monitoring-system.md#6-limitations).

## About

Created by **Kavita Jadhav**, founder of [K11 Software Solutions](https://github.com/K11-Software-Solutions), Senior SDET and AI Quality Engineer working on LLM evaluation, red teaming and agentic QA systems.

**Licences:** code under the [MIT License](LICENSE); the written material in [`articles/`](articles/LICENSE.md) under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) (share and adapt with credit).

The product, users and incidents are fictional.

## Citing

Use GitHub's **Cite this repository** button (from [`CITATION.cff`](CITATION.cff)). Each tagged release is archived on Zenodo with its own DOI; cite the version you used, or the concept DOI for the project as a whole. The DOI badge will appear here after the first release.
