# 04. Monitors and Drift: Rates, Ratios, PSI, and Why Averages Lie

> **Series:** AI Production Monitoring Lab · [Index](../README.md#articles) · Previous: [03](03-online-evals-without-reference-answers.md) · Next: [05. Guardrails in Production](05-guardrails-in-production.md)

[`prodlab/monitors.py`](../prodlab/monitors.py) computes daily metrics, compares them with a **baseline** (days 1–4), and raises alerts with three kinds of rule.

```bash
python -m prodlab.monitors data/incidents.jsonl
```

## 1. Ratio rules: latency, cost and tokens

`value > baseline × factor`: p95 latency × 1.5, cost per request × 1.3, average input and output tokens × 1.3. Simple and robust, suited to continuous metrics with a stable baseline.

## 2. Rate rules: a statistical test *and* a minimum effect

Refusals, thumbs-down, unknown topics, injection flags, groundedness failures, language mismatches and errors are **proportions**, and proportions are noisy. A day with 400 requests will rarely match the baseline exactly. Each rate rule needs **both**:

- a **two-proportion z-test** with z ≥ 3 (very unlikely to be chance), **and**
- an **absolute increase** large enough to matter (for example +5 points for thumbs-down).

Why both? Significance without effect size alerts on tiny, irrelevant changes once traffic is large. Effect size without significance alerts on noise when traffic is small.

**Evidence from the lab:** the `no-stats` negative control alerts on *any* increase. On the quiet scenario, where nothing happens, it raises **31 false alarms**; the standard monitors raise **zero**. Alert fatigue is how real incidents get ignored.

## 3. Drift rules: the population stability index

**Who** is using the system can change before **how well** it works does. The lab tracks the distribution of topics and languages with the **population stability index (PSI)**:

```text
PSI = Σ (actual% − expected%) × ln(actual% / expected%)
rule of thumb: < 0.1 stable · 0.1–0.2 moderate · > 0.2 significant shift
```

When team-workspace questions appear (day 8), topic PSI jumps far above 0.2. When Spanish-speaking users arrive (day 9), language PSI does too. Drift alerts are early warnings: they tell you the eval set no longer represents your users.

## 4. Why averages lie: p95 versus mean latency

During the latency incident only about 6% of requests are slowed, but each by three seconds.

| Day 11 | Baseline | Incident day |
|---|---|---|
| mean latency | ~700 ms | ~1,010 ms (×1.44) |
| p95 latency | ~1,000 ms | ~3,720 ms (about ×3.8) |

With the same ×1.5 rule, a **mean-based** monitor stays silent while one user in twenty waits four seconds. The `mean-latency` negative control proves it: it misses the incident and fails the gate. **Monitor percentiles, not averages**, for anything users wait on.

## 5. Which monitor caught which incident

| Incident | First alerts (same day) |
|---|---|
| Silent model update | output tokens (groundedness follows a day later) |
| Feature launch without docs | unknown-topic rate, topic PSI, refusals, thumbs-down, groundedness |
| Language shift | language PSI, language mismatch, unknown topics, refusals, thumbs-down |
| Latency spike | p95 latency |
| Injection campaign | injection-flag rate |
| Prompt bloat | input tokens, cost per request |

Notice that the **silent model update was caught by a cost-and-tokens metric first**, not by a quality metric. Cheap operational signals are often the earliest evidence of a behavioural change.

## 6. Design choices to discuss with your team

- **Baseline:** fixed (as here), rolling, or seasonal (weekday vs weekend)?
- **Window size:** daily windows are easy to read; hourly windows catch outages faster but are noisier.
- **Alert grouping:** one incident should page once, not twelve times. Group alerts by time and probable cause.
- **Ownership:** every alert needs an owner and a runbook entry (article 07).

---
Next: [05. Guardrails in Production](05-guardrails-in-production.md)
