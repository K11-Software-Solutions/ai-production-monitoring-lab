"""Daily metrics, drift statistics and alert rules.

    python -m prodlab.monitors data/incidents.jsonl     # print the daily table and alerts

Three kinds of rule:
    ratio  value > baseline × factor             (latency, cost, tokens)
    rate   two-proportion z-test vs baseline      (refusals, thumbs-down, flags, ...)
           AND an absolute change big enough to matter
    psi    population stability index > limit    (topic and language mix)
"""
from __future__ import annotations

import argparse
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from prodlab import online_evals
from prodlab.traces import Trace, read_traces


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct / 100
    lo, hi = math.floor(k), math.ceil(k)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def psi(expected: Counter, actual: Counter, eps: float = 1e-4) -> float:
    """Population stability index. Rule of thumb: < 0.1 stable, 0.1-0.2 moderate, > 0.2 significant shift."""
    cats = set(expected) | set(actual)
    e_total, a_total = sum(expected.values()) or 1, sum(actual.values()) or 1
    total = 0.0
    for c in cats:
        e = max(expected[c] / e_total, eps)
        a = max(actual[c] / a_total, eps)
        total += (a - e) * math.log(a / e)
    return total


def two_proportion_z(x1: int, n1: int, x2: int, n2: int) -> float:
    """z statistic for p2 > p1. Positive means the current window is worse."""
    if n1 == 0 or n2 == 0:
        return 0.0
    p = (x1 + x2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return 0.0 if se == 0 else (x2 / n2 - x1 / n1) / se


@dataclass
class Window:
    """Everything a monitor needs about one day, computed only from traces."""
    day: int
    n: int
    latencies: list[float]
    costs: list[float]
    tokens_in: list[int]
    tokens_out: list[int]
    counts: dict[str, tuple[int, int]]  # rate metric -> (events, denominator)
    topics: Counter
    languages: Counter

    def rate(self, name: str) -> float:
        x, n = self.counts[name]
        return x / n if n else 0.0


def build_window(day: int, traces: list[Trace], sample_rate: float, seed: int) -> Window:
    sampled = online_evals.sample(traces, sample_rate, seed=seed + day)
    feedback = [t for t in traces if t.feedback]
    counts = {
        "error_rate": (sum(t.error for t in traces), len(traces)),
        "refusal_rate": (sum(online_evals.is_refusal(t.answer) for t in traces), len(traces)),
        "unknown_topic_rate": (sum(t.topic is None for t in traces), len(traces)),
        "injection_flag_rate": (sum(t.injection_flag for t in traces), len(traces)),
        "pii_rate": (sum(bool(t.pii_detected) for t in traces), len(traces)),
        "thumbs_down_rate": (sum(t.feedback == "down" for t in feedback), len(feedback)),
        "groundedness_failure_rate": (sum(not online_evals.grounded(t.answer, t.context) for t in sampled), len(sampled)),
        "language_mismatch_rate": (sum(online_evals.language_mismatch(t.query, t.answer) for t in traces), len(traces)),
    }
    return Window(day, len(traces), [t.latency_ms for t in traces], [t.cost_usd for t in traces],
                  [t.tokens_in for t in traces], [t.tokens_out for t in traces], counts,
                  Counter(t.topic or "none" for t in traces), Counter(t.language for t in traces))


def daily_metrics(w: Window, baseline: Window) -> dict[str, float]:
    m = {
        "requests": w.n,
        "latency_mean": round(sum(w.latencies) / w.n, 1),
        "latency_p95": round(percentile(w.latencies, 95), 1),
        "cost_per_request": round(sum(w.costs) / w.n, 6),
        "avg_input_tokens": round(sum(w.tokens_in) / w.n, 1),
        "avg_output_tokens": round(sum(w.tokens_out) / w.n, 1),
        "topic_psi": round(psi(baseline.topics, w.topics), 3),
        "language_psi": round(psi(baseline.languages, w.languages), 3),
    }
    m.update({name: round(w.rate(name), 4) for name in w.counts})
    return m


def merge(windows: list[Window]) -> Window:
    counts = {k: (sum(w.counts[k][0] for w in windows), sum(w.counts[k][1] for w in windows)) for k in windows[0].counts}
    return Window(0, sum(w.n for w in windows), [x for w in windows for x in w.latencies],
                  [x for w in windows for x in w.costs], [x for w in windows for x in w.tokens_in],
                  [x for w in windows for x in w.tokens_out], counts,
                  sum((w.topics for w in windows), Counter()), sum((w.languages for w in windows), Counter()))


@dataclass
class MonitorConfig:
    baseline_days: int = 4
    sample_rate: float = 0.2
    latency_stat: str = "p95"   # "mean" is the classic mistake: averages hide tail latency
    ratio_rules: dict = field(default_factory=lambda: {
        "latency": 1.5, "cost_per_request": 1.3, "avg_input_tokens": 1.3, "avg_output_tokens": 1.3})
    rate_rules: dict = field(default_factory=lambda: {   # minimum absolute increase that matters
        "error_rate": 0.01, "refusal_rate": 0.05, "unknown_topic_rate": 0.05, "injection_flag_rate": 0.02,
        "thumbs_down_rate": 0.05, "groundedness_failure_rate": 0.04, "language_mismatch_rate": 0.05})
    z_threshold: float = 3.0
    psi_limit: float = 0.2
    seed: int = 0


@dataclass
class Alert:
    day: int
    monitor: str
    value: float
    baseline: float
    detail: str


def evaluate(traces: list[Trace], cfg: MonitorConfig | None = None) -> tuple[dict[int, dict], list[Alert]]:
    cfg = cfg or MonitorConfig()
    by_day: dict[int, list[Trace]] = defaultdict(list)
    for t in traces:
        by_day[t.day].append(t)
    windows = {d: build_window(d, ts, cfg.sample_rate, cfg.seed) for d, ts in sorted(by_day.items())}
    base = merge([windows[d] for d in sorted(windows)[:cfg.baseline_days]])
    base_m = daily_metrics(base, base)
    table, alerts = {}, []
    for day, w in windows.items():
        m = daily_metrics(w, base)
        table[day] = m
        if day <= cfg.baseline_days:
            continue
        latency_key = "latency_p95" if cfg.latency_stat == "p95" else "latency_mean"
        for rule, factor in cfg.ratio_rules.items():
            key = latency_key if rule == "latency" else rule
            if base_m[key] and m[key] > base_m[key] * factor:
                name = "latency_p95" if rule == "latency" else rule
                alerts.append(Alert(day, name, m[key], base_m[key], f"{key} {m[key]} > {factor}x baseline {base_m[key]}"))
        for rule, min_delta in cfg.rate_rules.items():
            x1, n1 = base.counts[rule]
            x2, n2 = w.counts[rule]
            z = two_proportion_z(x1, n1, x2, n2)
            delta = w.rate(rule) - base.rate(rule)
            if z >= cfg.z_threshold and delta >= min_delta:
                alerts.append(Alert(day, rule, round(w.rate(rule), 4), round(base.rate(rule), 4),
                                    f"+{delta:.3f} vs baseline (z={z:.1f}, n={n2})"))
        for rule in ("topic_psi", "language_psi"):
            if m[rule] > cfg.psi_limit:
                alerts.append(Alert(day, rule, m[rule], 0.0, f"PSI {m[rule]} > {cfg.psi_limit}"))
    return table, alerts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("traces")
    args = parser.parse_args(argv)
    table, alerts = evaluate(read_traces(args.traces))
    cols = ["latency_p95", "cost_per_request", "avg_output_tokens", "refusal_rate", "unknown_topic_rate",
            "thumbs_down_rate", "groundedness_failure_rate", "injection_flag_rate", "topic_psi", "language_psi"]
    print("day  " + "  ".join(c[:14].rjust(14) for c in cols))
    for day, m in table.items():
        print(f"{day:>3}  " + "  ".join(str(m[c]).rjust(14) for c in cols))
    for a in alerts:
        print(f"ALERT day {a.day}: {a.monitor}: {a.detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
