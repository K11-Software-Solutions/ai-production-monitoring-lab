# 08. Testing the Monitoring System

> **Series:** AI Production Monitoring Lab · [Index](../README.md#articles) · Previous: [07](07-from-alert-to-regression-test.md)

Monitoring is software, and untested software fails quietly. A monitor that never fires looks exactly like a system that never breaks. This lab tests its monitoring the way you would test anything else: with known inputs, expected outputs and negative controls.

```bash
python -m evals.run_monitoring_evals
cat evals/results/monitoring_report.md
```

## 1. What is gated

[`evals/thresholds.json`](../evals/thresholds.json):

| Gate | Requirement | Why |
|---|---|---|
| incident_recall | 1.0 | every injected incident must raise an expected alert |
| max_detection_delay_days | ≤ 1 | late detection is a missed incident |
| unexplained_alerts | 0 | no alerts outside an active incident's expected monitors |
| quiet_period_alerts | 0 | a quiet week must stay quiet |
| pii_recall / precision | 1.0 / ≥ 0.9 | privacy controls on the labelled set |
| injection_recall / precision | ≥ 0.7 / ≥ 0.9 | with the known paraphrase gap documented |
| evaluator_precision / recall | ≥ 0.9 | the online groundedness check against ground truth |
| triage_accuracy | 1.0 | segment analysis points at the real cause |
| regression_case_pii_leaks | 0 | exported test cases never contain personal data |
| release_decision_accuracy | 1.0 | shadow testing promotes good and rejects bad candidates |

## 2. Negative controls

CI runs two deliberately broken monitoring configurations, and the build **fails if either passes**:

| Broken monitor | Mistake | What the gate sees |
|---|---|---|
| `mean-latency` | alerts on average latency instead of p95 | misses the latency incident: recall 0.83 |
| `no-stats` | alerts on any increase, without a z-test or minimum effect | 31 false alarms in the quiet period, 15 unexplained in the incident run |

Each mistake is one that real teams make, and each is caught by a different gate: one by **recall**, the other by **precision**. A monitoring test suite needs both, just as a classifier evaluation does.

## 3. The pipeline

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml): unit tests (system, guardrails, evaluators, monitors, triage, release), then the monitoring evaluation with the report in the job summary, the two negative controls, and the simulated traces uploaded for inspection. There are no dependencies beyond pytest, and no API keys.

## 4. Doing this without a simulator

Real production has no ground truth, but the same ideas apply:

- **Replay past incidents.** Keep traces from real incidents and check that today's monitors would have fired on them.
- **Inject synthetic faults in staging.** Slow a dependency, change a prompt or swap a model, and confirm the alert fires.
- **Run "game days"** where the team investigates a planted incident using only the dashboards and runbooks.
- **Track alert quality:** the share of alerts that led to action, and the time from alert to acknowledgement.

## 5. Findings from building this lab

- **Averages hide tail latency:** a mean-based monitor missed an incident that p95 caught immediately.
- **Statistical tests prevent alert fatigue:** without them, a quiet week produced 31 false alarms.
- **The cheapest signal often fires first:** the silent model update showed up in output tokens before quality metrics.
- **Guardrails have locale bugs:** a UK phone number slipped through, and a bare order number was flagged as a phone number.
- **Release metrics encode values:** a naive refusal metric rejected the more honest model.
- **Global changes confound segment analysis:** the new model version "explained" every alert until it was separated out.
- **Overlap-based evaluators miss changed numbers:** the same blind spot found in lab 1.

## 6. Limitations

- **Simulated traffic:** real traffic has seasonality, bursts, bots and correlated failures the simulator does not model.
- **Fixed baseline:** real systems need rolling or seasonal baselines.
- **Daily windows:** fine for teaching; outages need minute-level detection.
- **Simple evaluators:** overlap-based groundedness and keyword refusal detection, measured but limited.
- **No alert grouping or paging policy:** each rule fires independently.

## 7. Presenting this lab in an interview

> "I built a deterministic production simulator for a support assistant, with six scheduled incidents: a silent model update, an undocumented feature launch, a language shift, a provider latency spike, an injection campaign and prompt bloat. The monitors use ratio rules, z-tested rate rules with minimum effects, and PSI for drift. Then I tested the monitoring itself: all six incidents are detected on day one, with zero false alarms on a quiet scenario. CI rejects a mean-latency monitor that misses the latency spike and a no-statistics monitor that raises 31 false alarms. Shadow testing promotes the good candidate and would have caught the silent update. My favourite finding was that a naive refusal metric rejected the more honest model."

---
Back to the [index](../README.md#articles).
