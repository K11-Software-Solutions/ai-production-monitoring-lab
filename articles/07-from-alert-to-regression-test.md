# 07. From Alert to Root Cause to Regression Test

> **Series:** AI Production Monitoring Lab · [Index](../README.md#articles) · Previous: [06](06-shadow-testing-and-release-decisions.md) · Next: [08. Testing the Monitoring System](08-testing-the-monitoring-system.md)

An alert is the start of the work. The incident loop has three steps: **localise** the cause, **fix** it, and **feed it back** so that the next offline eval run covers it.

## 1. Step one: what changed globally?

Before slicing traffic, ask what changed for *everyone*. [`triage.global_changes()`](../prodlab/triage.py) lists dimensions that have a single value today, different from the baseline:

```text
day 8: model_version  model-a-2026-09 → model-a-2026-11
```

### A real finding: the naive breakdown blamed the model for everything

The first version of the segment analysis ranked `model_version = model-a-2026-11` as the top contributor to **every** alert after day 5: unknown topics, Spanish-language mismatches, injection flags. Of course it did: 100% of today's traffic was on the new model and 0% of the baseline's. A dimension that changed for everyone "explains" everything and nothing.

The fix separates the two questions. Global changes are reported on their own, and segment analysis is run only on dimensions that vary within the day.

## 2. Step two: which slice moved the metric?

`segment_breakdown()` compares each segment (topic, language, model version, prompt version) with the baseline and ranks them by **contribution** to the change in rate:

| Alert | Top segment | Interpretation |
|---|---|---|
| day 8, unknown-topic rate | `topic = none` | questions retrieval cannot match: the new feature |
| day 9, language mismatch | `language = es` | Spanish queries answered in English |
| day 12, injection flags | `topic = none` | injection prompts match no help article |

From there, read individual traces in that segment. The answers to team-workspace questions show the model **inventing prices**:

```text
query:  "How do I add members to my team?"
answer: "Team workspaces cost 5 dollars per user and include unlimited storage."
```

No help article mentions team pricing: the model made it up. Other answers in the same segment drift to unrelated invented "facts" about refunds or the API.

## 3. Step three: turn failures into regression cases

`export_regression_cases()` collects thumbs-down and ungrounded conversations from incident days, deduplicates them by normalised query, and writes candidate eval cases:

```json
{"query": "How do I add members to my team?", "observed_answer": "...", "reasons": ["ungrounded"],
 "day": 8, "topic": null, "language": "en", "needs_label": "expected answer to be written by a human reviewer"}
```

At the time of writing the incident run exports a few dozen candidate cases, **none containing PII**: queries are redacted at trace time and re-checked at export (article 05).

Each case still needs a human to write the expected behaviour ("refuse until the docs exist", "answer in Spanish"). Then it joins the golden dataset from lab 1, and the next release cannot repeat the failure.

## 4. Fixes for the six incidents

| Incident | Short-term mitigation | Long-term fix | Regression protection |
|---|---|---|---|
| Silent model update | pin the previous version | shadow-test every provider update | release gate (article 06) |
| Feature launch, no docs | refuse-with-handoff for the new topic | docs as part of the launch checklist | exported cases |
| Language shift | detect language, answer or route accordingly | multilingual evals and docs | Spanish cases in the eval set |
| Latency spike | timeouts, fallback provider | p95 SLO with the provider | p95 monitor |
| Injection campaign | flag and rate-limit | layered defences (agent lab) | new attack prompts in the eval set |
| Prompt bloat | revert the prompt | cost check in prompt review | cost-per-request monitor and release gate |

## 5. Writing up an incident

Use the same short format as the earlier labs:

```markdown
**Alert:** day 8, unknown_topic_rate +0.30 (z≈17), topic_psi ≈0.7
**Global changes:** model_version (since day 5, separate incident)
**Top segment:** topic = none (team-workspace questions)
**Impact:** about 30% of requests unanswerable; the model invents prices for some
**Cause:** feature launched before the help articles were updated
**Mitigation:** refuse and hand off to a human for team questions
**Fix:** publish team-workspace docs; add them to the launch checklist
**Regression:** exported cases labelled and added to the golden dataset
```

---
Next: [08. Testing the Monitoring System](08-testing-the-monitoring-system.md)
