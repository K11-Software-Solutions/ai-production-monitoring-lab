# 02. Tracing: What to Record (and What Never to Store)

> **Series:** AI Production Monitoring Lab · [Index](../README.md#articles) · Previous: [01](01-why-production-decides-ai-quality.md) · Next: [03. Online Evals](03-online-evals-without-reference-answers.md)

Every monitor, evaluation and investigation in this lab reads one thing: **traces**. If a field is not in the trace, you cannot alert on it, slice by it or debug with it later. Trace design is therefore a quality decision, not just an engineering one.

## The trace record ([`prodlab/traces.py`](../prodlab/traces.py))

| Group | Fields | Used for |
|---|---|---|
| Identity | `trace_id`, `day` | joining, time windows |
| Input | `query` (**redacted**), `language` | drift, triage, regression cases |
| Versions | `model_version`, `prompt_version` | attributing changes, rollbacks |
| Retrieval | `topic`, `retrieval_score`, `context` | groundedness, unknown-topic rate |
| Output | `answer` | online evals |
| Performance | `tokens_in`, `tokens_out`, `latency_ms`, `cost_usd`, `error` | SLOs, budgets |
| Safety | `pii_detected`, `injection_flag` | guardrail monitoring |
| Feedback | `feedback` (`up` / `down` / none) | user-perceived quality |

Three fields deserve emphasis:

- **Versions on every trace.** "What changed?" is the first question in every incident. Without `model_version` and `prompt_version` you cannot answer it, and you cannot compare before and after.
- **The retrieved context.** Groundedness can only be checked if you stored what the model was given.
- **Cost and tokens.** Prompt bloat and verbose models are cost incidents, and they show up in tokens before they show up on an invoice.

## Never store raw personal data

Users paste emails, phone numbers and card numbers into support chats. The simulator does this in about 4% of requests. The lab **redacts at write time**:

```text
user typed:   "My card is 4111 1111 1111 1111, why was it charged twice?"
trace stores: "My card is [CARD], why was it charged twice?"   pii_detected: ["card"]
```

The trace keeps the *fact* that PII was present (useful for monitoring) without the data itself. A test enforces it across the whole simulated stream: `test_raw_pii_is_never_stored_in_traces`. Traces get copied into dashboards, exports, eval datasets and vendor tools; anything stored raw will eventually leak.

## The hidden `truth` field

Each simulated trace also carries `truth`: whether the answer was really hallucinated, refused or answerable. **No monitor or evaluator reads it.** It exists only so the lab can measure how good the monitors and evaluators are (articles 03 and 08). In real production you would approximate it with human review of a sample.

## Mapping to real tools

The JSON Lines format here maps directly onto tracing platforms:

| This lab | Langfuse / LangSmith / OpenTelemetry |
|---|---|
| one `Trace` | one trace, with spans for retrieval and generation |
| `model_version`, `prompt_version` | trace metadata or tags; prompt management versions |
| `feedback` | scores or user feedback attached to the trace |
| online eval results | evaluation scores attached to sampled traces |

The concepts transfer; only the storage changes.

## Try it

```bash
python -m prodlab.simulate --scenario incidents --out data/incidents.jsonl
head -n 2 data/incidents.jsonl
```

---
Next: [03. Online Evals Without Reference Answers](03-online-evals-without-reference-answers.md)
