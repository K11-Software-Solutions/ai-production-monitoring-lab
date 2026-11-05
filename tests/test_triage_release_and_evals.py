from prodlab import guardrails, release, triage
from prodlab.release import ShadowResult, decide
from evals.run_monitoring_evals import detection, main
from prodlab.monitors import Alert
from prodlab.simulate import SCENARIOS
from tests.conftest import make_trace


def test_global_change_is_separated_from_segments(incident_traces):
    assert triage.global_changes(incident_traces, 5) == {"model_version": (["model-a-2026-09"], ["model-a-2026-11"])}
    assert triage.global_changes(incident_traces, 3) == {}
    dims = {r["dimension"] for r in triage.segment_breakdown(incident_traces, 8, "unknown_topic_rate", top=50)}
    assert "model_version" not in dims


def test_segment_breakdown_finds_the_cause(incident_traces):
    assert triage.segment_breakdown(incident_traces, 9, "language_mismatch_rate")[0]["value"] == "es"
    assert triage.segment_breakdown(incident_traces, 8, "unknown_topic_rate")[0]["value"] == "none"


def test_regression_export_dedupes_and_never_contains_pii():
    traces = [make_trace(n=i, feedback="down", query="Why was I charged twice? [EMAIL]") for i in range(3)]
    traces.append(make_trace(n=9, feedback="down", query="call me 555-201-7788 about export"))
    cases = triage.export_regression_cases(traces)
    assert len(cases) == 2
    assert all(not guardrails.find_pii(c["query"]) for c in cases)
    assert "[PHONE]" in cases[1]["query"]


def test_export_skips_good_conversations():
    assert triage.export_regression_cases([make_trace(feedback="up")]) == []


def result(**kw):
    base = dict(model="m", n=1000, groundedness_failures=40, refusals=30, over_refusals=0, latency_p95=1000.0,
                cost_per_request=0.0002)
    base.update(kw)
    return ShadowResult(**base)


def test_decision_promotes_equal_or_better_candidates():
    assert decide(result(), result()).promote


def test_decision_rejects_on_each_regression():
    assert not decide(result(), result(groundedness_failures=100)).promote
    assert not decide(result(), result(over_refusals=50)).promote
    assert not decide(result(), result(latency_p95=1500.0)).promote
    assert not decide(result(), result(cost_per_request=0.0003)).promote
    assert not decide(result(), result(n=100, groundedness_failures=4)).promote  # too little traffic


def test_more_refusals_of_unanswerable_questions_is_not_a_regression():
    assert decide(result(), result(refusals=80, over_refusals=0)).promote


def test_shadow_decisions(incident_traces):
    assert release.shadow_test(incident_traces, "model-b-good").promote
    assert not release.shadow_test(incident_traces, "model-b-bad").promote
    assert not release.shadow_test(incident_traces, "model-a-2026-11").promote


def test_detection_scoring():
    scenario = SCENARIOS["incidents"]()
    alerts = [Alert(5, "avg_output_tokens", 1, 1, ""), Alert(6, "latency_p95", 1, 1, "")]
    det = detection(scenario, alerts)
    rows = {r["incident"]: r for r in det["rows"]}
    assert rows["silent_model_update"]["detected"] and rows["silent_model_update"]["delay_days"] == 0
    assert not rows["provider_latency_spike"]["detected"]
    assert [a["monitor"] for a in det["unexplained_alerts"]] == ["latency_p95"]  # no latency incident on day 6


def test_standard_monitors_pass_and_broken_monitors_fail(tmp_path):
    assert main(["--out", str(tmp_path / "a")]) == 0
    assert main(["--monitor", "mean-latency", "--out", str(tmp_path / "b")]) == 1
    assert main(["--monitor", "no-stats", "--out", str(tmp_path / "c")]) == 1
