from collections import Counter

import pytest

from prodlab.monitors import MonitorConfig, evaluate, percentile, psi, two_proportion_z
from tests.conftest import make_trace


def test_percentile():
    values = list(range(1, 101))
    assert percentile(values, 50) == pytest.approx(50.5)
    assert percentile(values, 95) == pytest.approx(95.05)
    assert percentile([], 95) == 0.0


def test_psi_is_zero_for_identical_and_large_for_shifted_distributions():
    a = Counter({"en": 90, "es": 10})
    assert psi(a, a) == pytest.approx(0.0)
    assert psi(a, Counter({"en": 50, "es": 50})) > 0.2


def test_two_proportion_z():
    assert two_proportion_z(10, 1000, 10, 1000) == pytest.approx(0.0)
    assert two_proportion_z(10, 1000, 60, 1000) > 5
    assert two_proportion_z(10, 1000, 2, 1000) < 0
    assert two_proportion_z(0, 0, 5, 10) == 0.0


def days(n_days, per_day=200, overrides=None):
    overrides = overrides or {}
    traces = []
    for d in range(1, n_days + 1):
        for i in range(per_day):
            traces.append(make_trace(day=d, n=i, **overrides.get(d, {})))
    return traces


def test_no_alerts_on_stable_traffic():
    _, alerts = evaluate(days(7))
    assert alerts == []


def test_baseline_days_never_alert():
    _, alerts = evaluate(days(6, overrides={2: {"latency_ms": 9000.0}}))
    assert all(a.day > 4 for a in alerts)


def test_ratio_rule_fires_on_cost_increase():
    _, alerts = evaluate(days(6, overrides={6: {"cost_usd": 0.001}}))
    assert [(a.day, a.monitor) for a in alerts] == [(6, "cost_per_request")]


def test_rate_rule_needs_significance_and_effect_size():
    traces = days(6)
    for t in traces[-200:][:1]:        # 1 error in 200 (0.5%): below the 1% minimum effect size
        t.error = True
    _, alerts = evaluate(traces)
    assert not [a for a in alerts if a.monitor == "error_rate"]
    for t in traces[-200:][:40]:       # 40 in 200: significant and large
        t.error = True
    _, alerts = evaluate(traces)
    assert [a.monitor for a in alerts] == ["error_rate"]


def test_psi_rule_fires_on_language_shift():
    traces = days(6)
    for t in traces[-200:][:80]:
        t.language = "es"
    _, alerts = evaluate(traces)
    assert "language_psi" in {a.monitor for a in alerts}


def test_mean_latency_monitor_misses_tail_latency():
    traces = days(6)
    for t in traces[-200:][:14]:       # 7% of day-6 requests become very slow
        t.latency_ms = 4000.0
    _, p95_alerts = evaluate(traces, MonitorConfig(latency_stat="p95"))
    _, mean_alerts = evaluate(traces, MonitorConfig(latency_stat="mean"))
    assert "latency_p95" in {a.monitor for a in p95_alerts}
    assert "latency_p95" not in {a.monitor for a in mean_alerts}
