# 06. Shadow Testing and Release Decisions

> **Series:** AI Production Monitoring Lab · [Index](../README.md#articles) · Previous: [05](05-guardrails-in-production.md) · Next: [07. From Alert to Regression Test](07-from-alert-to-regression-test.md)

Monitoring tells you something got worse. Safe release practices stop it from getting worse in the first place.

## 1. Release patterns

| Pattern | How it works | Risk to users |
|---|---|---|
| **Offline eval** | run the golden dataset (labs 1–3) | none, but limited to the inputs you thought of |
| **Shadow** | the candidate answers real traffic, but its answers are recorded, not shown | none |
| **Canary** | a small share of users gets the candidate, with automatic rollback | small and bounded |
| **A/B test** | split traffic and compare outcomes such as thumbs-down rate | moderate; needs enough traffic for significance |

This lab implements **shadow testing** ([`prodlab/release.py`](../prodlab/release.py)): replay the baseline period's real (redacted) queries through the production model and the candidate, with identical random seeds, so that differences come from the model and not from the traffic.

## 2. A deterministic decision rule

The candidate is promoted only if **none** of these regress:

- groundedness failures (beyond a tolerance, and statistically significant);
- **over-refusals** (refusing questions the help articles *can* answer);
- p95 latency (more than 20% worse);
- cost per request (more than 20% worse);
- and only with at least 300 shadow requests.

Results at the time of writing:

| Candidate | Decision | Why |
|---|---|---|
| `model-b-good` | **promote** | fewer groundedness failures, faster, cheaper |
| `model-b-bad` | reject | groundedness failures several times higher |
| `model-a-2026-11` (the silent update) | reject | more groundedness failures, higher cost |

Shadow testing would have **caught the silent update before it reached users**, if the provider had announced it. That is a strong argument for pinning model versions and shadow-testing every upgrade.

## 3. A real finding: the naive rule rejected the better model

The first version of the rule checked the **total refusal rate**. It rejected `model-b-good`, because that model refused slightly more often.

Looking closer, every extra refusal was on a question the help articles could not answer. Where the production model **invented** an answer about team workspaces, the candidate **said "I don't know"**. The candidate was more honest, and the metric punished it.

The fix: count only **over-refusals**, refusals when the context *did* contain the answer. A refusal of an unanswerable question is the correct behaviour.

**Lesson:** release metrics encode values. Before gating on a metric, ask whether moving it in the "bad" direction could ever be the right behaviour. Refusal rate, answer length and response time all have this trap.

## 4. Making shadow tests trustworthy

- **Same inputs, same seeds:** compare models, not luck.
- **Enough samples:** small differences in rates need hundreds or thousands of requests.
- **Representative traffic:** shadow on recent traffic, including the new topics and languages that drift monitoring found.
- **Privacy:** shadow traffic is real user data; use the redacted queries.
- **Cost:** shadowing doubles inference cost for the period; sample if needed.

---
Next: [07. From Alert to Regression Test](07-from-alert-to-regression-test.md)
