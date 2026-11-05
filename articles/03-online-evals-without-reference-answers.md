# 03. Online Evals Without Reference Answers

> **Series:** AI Production Monitoring Lab · [Index](../README.md#articles) · Previous: [02](02-tracing-what-to-record.md) · Next: [04. Monitors and Drift](04-monitors-and-drift.md)

Offline evals compare answers with expected answers. In production there are none. **Online evals** check properties that can be judged from the trace alone ([`prodlab/online_evals.py`](../prodlab/online_evals.py)).

## 1. Reference-free checks

| Check | Question | Needs |
|---|---|---|
| **Groundedness** | is every factual sentence supported by the retrieved context? | answer + context |
| **Refusal** | did the assistant decline? | answer |
| **Language match** | is the answer in the user's language? | query + answer |
| **Unknown topic** | did retrieval find anything at all? | retrieval result |

Groundedness ignores conversational filler ("I hope this helps!"), which is not a factual claim. Without that rule, the chattier model in the silent update would be flagged for every answer, and the real signal would drown in noise.

## 2. Sampling: spend the evaluation budget wisely

Running evaluators on every request is often too expensive, especially LLM-based judges. The lab uses **risk-based sampling**:

- a **random 20%** of traffic, which gives an unbiased estimate of overall quality;
- **plus every risky trace**: thumbs-down, injection-flagged, or no retrieval match.

Random sampling alone would see few of the rare, important failures. Risky-only sampling would give a biased picture of overall quality. Combining the two gives you both. When you report rates, remember the sample is enriched with risky traces; compare like with like (sampled baseline against sampled today), which is what the monitors do.

## 3. Validate the online evaluator

An online evaluator is a model of quality, and it can be wrong. Because the simulator knows which answers were really hallucinated, we can measure the groundedness check directly (`python -m evals.run_monitoring_evals`):

| | Value at time of writing |
|---|---|
| Precision (flagged answers that really were hallucinated) | 1.0 |
| Recall (hallucinations that were flagged) | about 0.99 |

The misses are instructive. All of them are **subtle fabrications**: almost the right words, one wrong fact.

```text
context: "Refunds are available within 30 days of the first payment."
answer:  "Refunds are available within 60 days of the first payment."   ← passes the overlap check
```

A word-overlap check cannot see a changed number. That is the same blind spot measured in the first lab's judge-agreement study. In production you would cover it with fact-level checks on high-risk claims (prices, time limits, legal terms) or with a validated LLM judge, and you would re-validate whenever the evaluator changes.

## 4. Online evals as monitors

Evaluator results become **rates per day** (`groundedness_failure_rate`, `language_mismatch_rate`, `refusal_rate`) and are monitored like any other metric (article 04). In the incident run, groundedness failures jump when the silent model update starts inventing details and again when users ask about the undocumented feature.

## Validating evaluators in real life

There is no simulator in production, so:

1. Every week, have humans label a random sample of traces.
2. Compare the labels with the online evaluator: precision, recall and agreement (for example Cohen's kappa).
3. Read every disagreement; add the interesting ones to the eval set.
4. Re-run the validation whenever the evaluator's prompt, model or thresholds change.

---
Next: [04. Monitors and Drift](04-monitors-and-drift.md)
