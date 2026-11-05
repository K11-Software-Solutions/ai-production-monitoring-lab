# Experiment results

Seeds: 1000–1049 (incident scenario); 6000–6049 (quiet scenario). 14 days × 400 requests per run.

## E1. Monitor designs across seeds

50 seeds of the incident scenario and 50 of the quiet scenario. Mean ± 95% CI; per-incident detection with 95% Wilson intervals. Recall uses attributed detection (incident-specific monitors, window closing before the next incident).

| Design | Incident recall | Mean delay (days) | Quiet-period alerts per run | Quiet runs with zero alerts | Unexplained alerts per incident run |
|---|---|---|---|---|---|
| standard (p95, z>=3 + min effect) | 0.957 ± 0.020 | 0.00 ± 0.00 | 0.1 ± 0.1 | 46/50 [0.81, 0.97] | 0.1 ± 0.1 |
| mean latency | 0.837 ± 0.007 | 0.00 ± 0.00 | 0.1 ± 0.1 | 46/50 [0.81, 0.97] | 0.1 ± 0.1 |
| significance only (z>=3, no min effect) | 0.957 ± 0.020 | 0.00 ± 0.00 | 0.2 ± 0.1 | 43/50 [0.74, 0.93] | 0.1 ± 0.1 |
| effect only (min effect, no z-test) | 0.957 ± 0.020 | 0.00 ± 0.00 | 1.6 ± 0.4 | 15/50 [0.19, 0.44] | 0.7 ± 0.2 |
| no statistics (any increase) | 0.957 ± 0.020 | 0.00 ± 0.00 | 45.9 ± 1.8 | 0/50 [0.00, 0.07] | 22.7 ± 0.8 |

Per-incident attributed detection rate:

| Design | silent_model_update | feature_launch_not_in_docs | language_shift | provider_latency_spike | prompt_injection_campaign | prompt_bloat |
|---|---|---|---|---|---|---|
| standard (p95, z>=3 + min effect) | 1.00 [0.93, 1.00] | 1.00 [0.93, 1.00] | 1.00 [0.93, 1.00] | 0.74 [0.60, 0.84] | 1.00 [0.93, 1.00] | 1.00 [0.93, 1.00] |
| mean latency | 1.00 [0.93, 1.00] | 1.00 [0.93, 1.00] | 1.00 [0.93, 1.00] | 0.02 [0.00, 0.10] | 1.00 [0.93, 1.00] | 1.00 [0.93, 1.00] |
| significance only (z>=3, no min effect) | 1.00 [0.93, 1.00] | 1.00 [0.93, 1.00] | 1.00 [0.93, 1.00] | 0.74 [0.60, 0.84] | 1.00 [0.93, 1.00] | 1.00 [0.93, 1.00] |
| effect only (min effect, no z-test) | 1.00 [0.93, 1.00] | 1.00 [0.93, 1.00] | 1.00 [0.93, 1.00] | 0.74 [0.60, 0.84] | 1.00 [0.93, 1.00] | 1.00 [0.93, 1.00] |
| no statistics (any increase) | 1.00 [0.93, 1.00] | 1.00 [0.93, 1.00] | 1.00 [0.93, 1.00] | 0.74 [0.60, 0.84] | 1.00 [0.93, 1.00] | 1.00 [0.93, 1.00] |

## E2. Alert-rule thresholds

Rate rules only; ratio and drift rules unchanged. 50 seeds per cell. Each cell: attributed recall on the default incidents / attributed recall on subtle incidents / mean quiet-period alerts per run.
Subtle incidents: injection share 0.015, feature share 0.04, language share 0.04.

| z threshold | min effect x0.0 | min effect x0.5 | min effect x1.0 | min effect x2.0 |
|---|---|---|---|---|
| 0 | 0.96 / 0.97 / 45.88 | 0.96 / 0.92 / 5.62 | 0.96 / 0.69 / 1.58 | 0.96 / 0.62 / 0.04 |
| 1 | 0.96 / 0.97 / 8.04 | 0.96 / 0.92 / 4.34 | 0.96 / 0.69 / 1.58 | 0.96 / 0.62 / 0.04 |
| 2 | 0.96 / 0.94 / 1.58 | 0.96 / 0.92 / 1.34 | 0.96 / 0.69 / 0.64 | 0.96 / 0.62 / 0.04 |
| 3 | 0.96 / 0.88 / 0.16 | 0.96 / 0.87 / 0.16 | 0.96 / 0.69 / 0.08 | 0.96 / 0.62 / 0.00 |
| 4 | 0.96 / 0.80 / 0.00 | 0.96 / 0.80 / 0.00 | 0.96 / 0.67 / 0.00 | 0.96 / 0.62 / 0.00 |
| 5 | 0.96 / 0.70 / 0.00 | 0.96 / 0.70 / 0.00 | 0.96 / 0.66 / 0.00 | 0.96 / 0.62 / 0.00 |
| 6 | 0.96 / 0.66 / 0.00 | 0.96 / 0.66 / 0.00 | 0.96 / 0.64 / 0.00 | 0.96 / 0.62 / 0.00 |

## E3. Detection probability vs incident magnitude

50 seeds per point; attributed detection; 95% Wilson intervals.

**slow_fraction** (provider_latency_spike)

| slow_fraction | p95 monitor | mean monitor |
|---|---|---|
| 0.01 | 0.00 [0.00, 0.07] | 0.00 [0.00, 0.07] |
| 0.02 | 0.00 [0.00, 0.07] | 0.00 [0.00, 0.07] |
| 0.03 | 0.02 [0.00, 0.10] | 0.00 [0.00, 0.07] |
| 0.04 | 0.20 [0.11, 0.33] | 0.00 [0.00, 0.07] |
| 0.06 | 0.74 [0.60, 0.84] | 0.02 [0.00, 0.10] |
| 0.08 | 1.00 [0.93, 1.00] | 0.40 [0.28, 0.54] |
| 0.1 | 1.00 [0.93, 1.00] | 0.92 [0.81, 0.97] |
| 0.15 | 1.00 [0.93, 1.00] | 1.00 [0.93, 1.00] |

**injection_share** (prompt_injection_campaign)

| injection_share | standard |
|---|---|
| 0.005 | 0.00 [0.00, 0.07] |
| 0.01 | 0.02 [0.00, 0.10] |
| 0.02 | 0.58 [0.44, 0.71] |
| 0.03 | 0.98 [0.90, 1.00] |
| 0.05 | 1.00 [0.93, 1.00] |
| 0.08 | 1.00 [0.93, 1.00] |
| 0.12 | 1.00 [0.93, 1.00] |

**feature_share** (feature_launch_not_in_docs)

| feature_share | standard |
|---|---|
| 0.02 | 0.02 [0.00, 0.10] |
| 0.05 | 0.42 [0.29, 0.56] |
| 0.1 | 0.98 [0.90, 1.00] |
| 0.2 | 1.00 [0.93, 1.00] |
| 0.3 | 1.00 [0.93, 1.00] |


## E4. Online-evaluation sampling

Groundedness monitor only, silent model update (onset day 5). 50 seeds. Only alerts before the feature launch (day 8) are attributed to the update; undetected runs count as a 3-day delay (censored).

| Sample rate | Risk-based inclusion | Detected before day 8 | Mean delay (days, censored at 3) | Evaluations per day | Quiet-period groundedness alerts |
|---|---|---|---|---|---|
| 0.02 | yes | 0.40 [0.28, 0.54] | 2.30 ± 0.26 | 116 | 0.00 |
| 0.02 | no | 0.04 [0.01, 0.13] | 2.90 ± 0.14 | 8 | 0.02 |
| 0.05 | yes | 0.52 [0.39, 0.65] | 2.06 ± 0.29 | 125 | 0.04 |
| 0.05 | no | 0.18 [0.10, 0.31] | 2.62 ± 0.24 | 20 | 0.06 |
| 0.1 | yes | 0.62 [0.48, 0.74] | 1.66 ± 0.34 | 140 | 0.04 |
| 0.1 | no | 0.28 [0.17, 0.42] | 2.40 ± 0.29 | 40 | 0.06 |
| 0.2 | yes | 0.64 [0.50, 0.76] | 1.56 ± 0.35 | 168 | 0.00 |
| 0.2 | no | 0.54 [0.40, 0.67] | 1.94 ± 0.31 | 80 | 0.04 |
| 0.5 | yes | 0.90 [0.79, 0.96] | 0.64 ± 0.27 | 256 | 0.00 |
| 0.5 | no | 0.90 [0.79, 0.96] | 0.70 ± 0.28 | 200 | 0.02 |
| 1 | yes | 1.00 [0.93, 1.00] | 0.26 ± 0.15 | 400 | 0.00 |
| 1 | no | 1.00 [0.93, 1.00] | 0.26 ± 0.15 | 400 | 0.00 |

## E5. Online groundedness evaluator vs hidden labels

50 seeds, 20% random sample plus risky traces.

- Precision: 1.000 ± 0.000
- Recall: 0.995 ± 0.001
- False negatives across all seeds: 187 (of 35387 hallucinations)

## E6. Shadow-release decisions across seeds

| Candidate | Expected | Correct decisions |
|---|---|---|
| model-b-good | promote | 50/50 [0.93, 1.00] |
| model-b-bad | reject | 50/50 [0.93, 1.00] |
| model-a-2026-11 | reject | 50/50 [0.93, 1.00] |

_Total runtime: 834 s._