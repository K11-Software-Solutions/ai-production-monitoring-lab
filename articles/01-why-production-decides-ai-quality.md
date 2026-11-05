# 01. Why Production Is Where AI Quality Is Decided

> **Series:** AI Production Monitoring Lab · [Index](../README.md#articles) · Next: [02. Tracing](02-tracing-what-to-record.md)

The first three labs in this series test AI systems **before release**: a RAG application, a model, and an agent. Every one of them ends with a green CI pipeline. This lab is about what happens next, because a passing eval suite is a statement about the past.

## What changes after launch

| Before release | After release |
|---|---|
| You choose the inputs | Users choose the inputs, including ones nobody imagined |
| The model is pinned | Providers update models, sometimes silently |
| Documents are fixed | Products launch before the help articles are updated |
| You have expected answers | You have **no reference answers**, only traces and feedback |
| Failures are test results | Failures are customer experiences, costs and incidents |

Offline evals answer *"is this version good enough to ship?"*. Production monitoring answers *"is it still good, for the users we actually have, right now?"*. You need both, and they feed each other: production failures become tomorrow's eval cases.

## The system and the incidents

The lab monitors a small support assistant for a fictional note-taking product (the same domain as the first lab). A deterministic **simulator** generates 14 days of traffic, 400 requests a day, and injects six realistic incidents on known days:

| Day | Incident | What it looks like |
|---|---|---|
| 5 | **Silent model update** | answers get longer, more invented details |
| 8 | **Feature launch, docs not updated** | questions about "team workspaces" the help articles don't cover |
| 9 | **Language shift** | a campaign in Spain brings Spanish-speaking users |
| 11–12 | **Provider latency spike** | a small share of requests become very slow |
| 12 | **Prompt-injection campaign** | a forum post encourages users to jailbreak the bot |
| 13 | **Prompt bloat** | a prompt change adds a large block of context to every request |

A second scenario, **quiet**, has no incidents at all.

## Testing the monitoring itself

Because the simulator knows the ground truth, this lab can do something rarely possible in real life: **test the monitors**. The questions are the same ones you would ask of any test suite:

- **Recall:** did every incident raise the right alert, and how quickly?
- **Precision:** how many alerts were false alarms? (On the quiet scenario, the correct number is zero.)
- **Evaluator validity:** do the online evaluators agree with the hidden ground truth?
- **Negative controls:** do deliberately broken monitors fail the gate?

At the time of writing the standard monitors detect all six incidents **on the day they start**, raise **no** unexplained alerts, and raise **zero** alerts on the quiet scenario.

## What you will practise

| Article | Skill |
|---|---|
| 02 | Designing traces: what to record, and what never to store |
| 03 | Online evals without reference answers, and validating them |
| 04 | Monitors and drift: rates, ratios, PSI, and why averages lie |
| 05 | Guardrails in production and their error rates |
| 06 | Shadow testing and release decisions |
| 07 | From alert to root cause to regression test |
| 08 | Testing the monitoring system in CI |

Everything is plain Python with no runtime dependencies and no API key.

---
Next: [02. Tracing: What to Record](02-tracing-what-to-record.md)
