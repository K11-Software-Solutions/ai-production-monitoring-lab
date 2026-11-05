"""Test the monitoring itself, and gate it in CI.

Usage (from the repo root):

    python -m evals.run_monitoring_evals                    # standard monitors, gates on
    python -m evals.run_monitoring_evals --monitor mean-latency   # negative control: must FAIL
    python -m evals.run_monitoring_evals --monitor no-stats       # negative control: must FAIL

Questions answered:
    Detection   did every injected incident raise an expected alert, and how fast?
    Precision   how many alerts were false alarms (incident run and quiet run)?
    Guardrails  PII and injection detection error rates on labelled examples
    Evaluators  does the online groundedness check agree with ground truth?
    Triage      does segment analysis point at the real cause?
    Feedback    do bad conversations become PII-free regression cases?
    Release     does shadow testing promote the good candidate and reject the bad ones?

Writes evals/results/monitoring_report.md and .json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from prodlab import guardrails, online_evals, release, triage
from prodlab.monitors import MonitorConfig, evaluate
from prodlab.simulate import SCENARIOS, simulate

HERE = Path(__file__).parent

MONITOR_VARIANTS = {
    "standard": lambda: MonitorConfig(),
    # Classic mistake 1: averages hide tail latency.
    "mean-latency": lambda: MonitorConfig(latency_stat="mean"),
    # Classic mistake 2: alert on any increase, with no statistical test or minimum effect size.
    "no-stats": lambda: MonitorConfig(z_threshold=0.0, rate_rules={k: 0.0 for k in MonitorConfig().rate_rules}),
}


def detection(scenario, alerts, max_delay: int = 1) -> dict:
    rows = []
    for inc in scenario.incidents:
        hits = sorted(a.day for a in alerts if a.monitor in inc.expected_monitors
                      and inc.start_day <= a.day <= min(inc.end_day, inc.start_day + max_delay))
        rows.append({"incident": inc.name, "start_day": inc.start_day, "detected": bool(hits),
                     "delay_days": (hits[0] - inc.start_day) if hits else None,
                     "first_monitors": sorted({a.monitor for a in alerts if hits and a.day == hits[0]
                                               and a.monitor in inc.expected_monitors})})
    unexplained = [a for a in alerts if not any(i.start_day <= a.day <= i.end_day and a.monitor in i.expected_monitors
                                                for i in scenario.incidents)]
    return {"rows": rows, "recall": round(sum(r["detected"] for r in rows) / len(rows), 3),
            "max_delay": max((r["delay_days"] or 0) for r in rows),
            "unexplained_alerts": [{"day": a.day, "monitor": a.monitor, "detail": a.detail} for a in unexplained]}


def guardrail_metrics() -> dict:
    rows = [json.loads(line) for line in (HERE / "datasets" / "guardrail_labels.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    out = {}
    for name, fn in (("pii", lambda t: bool(guardrails.find_pii(t))), ("injection", guardrails.is_injection)):
        tp = sum(fn(r["text"]) and r[name] for r in rows)
        fp = sum(fn(r["text"]) and not r[name] for r in rows)
        fn_ = sum(not fn(r["text"]) and r[name] for r in rows)
        out[f"{name}_precision"] = round(tp / (tp + fp), 3) if tp + fp else 1.0
        out[f"{name}_recall"] = round(tp / (tp + fn_), 3) if tp + fn_ else 1.0
        out[f"{name}_misses"] = [r["id"] for r in rows if r[name] and not fn(r["text"])]
        out[f"{name}_false_positives"] = [r["id"] for r in rows if fn(r["text"]) and not r[name]]
    return out


def evaluator_validation(traces) -> dict:
    sampled = online_evals.sample(traces, 0.2)
    pred = [not online_evals.grounded(t.answer, t.context) for t in sampled]
    truth = [t.truth["hallucinated"] for t in sampled]
    tp = sum(p and y for p, y in zip(pred, truth))
    fp = sum(p and not y for p, y in zip(pred, truth))
    fn = sum(not p and y for p, y in zip(pred, truth))
    missed = sorted({t.answer for t, p, y in zip(sampled, pred, truth) if y and not p})
    return {"n": len(sampled), "precision": round(tp / (tp + fp), 3) if tp + fp else 1.0,
            "recall": round(tp / (tp + fn), 3) if tp + fn else 1.0, "missed_examples": missed[:3]}


def triage_checks(traces) -> dict:
    top_topic = triage.segment_breakdown(traces, 8, "unknown_topic_rate")[0]
    top_lang = triage.segment_breakdown(traces, 9, "language_mismatch_rate")[0]
    global5 = triage.global_changes(traces, 5)
    checks = {
        "feature_launch_points_to_unknown_topic": (top_topic["dimension"], top_topic["value"]) == ("topic", "none"),
        "language_shift_points_to_spanish": (top_lang["dimension"], top_lang["value"]) == ("language", "es"),
        "model_update_reported_as_global_change": "model_version" in global5,
    }
    return {"checks": checks, "accuracy": round(sum(checks.values()) / len(checks), 3)}


def feedback_export(traces) -> dict:
    cases = triage.export_regression_cases(traces, days=set(range(5, 15)))
    leaks = [c for c in cases if guardrails.find_pii(c["query"]) or guardrails.find_pii(c["observed_answer"])]
    return {"cases": len(cases), "pii_leaks": len(leaks), "examples": cases[:3]}


def release_checks(traces) -> dict:
    expected = {"model-b-good": True, "model-b-bad": False, "model-a-2026-11": False}
    rows = []
    for cand, should_promote in expected.items():
        d = release.shadow_test(traces, cand)
        rows.append({"candidate": cand, "promote": d.promote, "expected": should_promote, "reasons": d.reasons})
    return {"rows": rows, "accuracy": round(sum(r["promote"] == r["expected"] for r in rows) / len(rows), 3)}


def check_gates(summary: dict, thresholds: dict) -> list[str]:
    failures = []
    for key, rule in thresholds.items():
        if key.startswith("_"):
            continue
        v = summary[key]
        if "min" in rule and v < rule["min"]:
            failures.append(f"{key}: {v} < min {rule['min']}")
        if "max" in rule and v > rule["max"]:
            failures.append(f"{key}: {v} > max {rule['max']}")
    return failures


def to_markdown(variant, summary, det, quiet_alerts, guards, evals_, tri, fb, rel, thresholds, failures) -> str:
    L = [f"# Monitoring evaluation report", "", f"Monitor configuration: `{variant}`", "",
         "| Metric | Value | Gate |", "|---|---|---|"]
    for k, v in summary.items():
        rule = thresholds.get(k, {})
        gate = ", ".join(f"{a} {b}" for a, b in rule.items() if a in ("min", "max"))
        mark = "" if not gate else (" ❌" if any(f.startswith(k + ":") for f in failures) else " ✅")
        L.append(f"| {k} | {v} | {gate}{mark} |")
    L += ["", "## Incident detection", "", "| Incident | Start day | Detected | Delay (days) | First alerts |", "|---|---|---|---|---|"]
    for r in det["rows"]:
        L.append(f"| {r['incident']} | {r['start_day']} | {'yes' if r['detected'] else '**no**'} | "
                 f"{r['delay_days'] if r['delay_days'] is not None else '-'} | {', '.join(r['first_monitors'])} |")
    L += ["", f"Unexplained alerts in the incident run: {len(det['unexplained_alerts'])}; alerts in the quiet run: {len(quiet_alerts)}"]
    for a in quiet_alerts[:5]:
        L.append(f"- quiet day {a.day}: {a.monitor}: {a.detail}")
    L += ["", "## Guardrails (labelled examples)", "",
          f"PII precision {guards['pii_precision']}, recall {guards['pii_recall']}; misses {guards['pii_misses']}, false positives {guards['pii_false_positives']}",
          f"Injection precision {guards['injection_precision']}, recall {guards['injection_recall']}; misses {guards['injection_misses']}, false positives {guards['injection_false_positives']}",
          "", "## Online evaluator vs ground truth", "",
          f"groundedness check on {evals_['n']} sampled traces: precision {evals_['precision']}, recall {evals_['recall']}"]
    L += [f"- missed: {m!r}" for m in evals_["missed_examples"]]
    L += ["", "## Triage", ""] + [f"- {k}: {v}" for k, v in tri["checks"].items()]
    L += ["", "## Feedback loop", "", f"{fb['cases']} regression cases exported, {fb['pii_leaks']} containing PII"]
    L += ["", "## Shadow release decisions", ""]
    L += [f"- {r['candidate']}: promote={r['promote']} (expected {r['expected']}) {r['reasons']}" for r in rel["rows"]]
    L += ["", "## Gate result", "", "PASSED" if not failures else "FAILED: " + "; ".join(failures), ""]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--monitor", choices=sorted(MONITOR_VARIANTS), default="standard")
    parser.add_argument("--no-gate", action="store_true")
    parser.add_argument("--out", type=Path, default=HERE / "results")
    args = parser.parse_args(argv)

    cfg = MONITOR_VARIANTS[args.monitor]()
    scenario = SCENARIOS["incidents"]()
    traces = simulate(scenario)
    quiet_traces = simulate(SCENARIOS["quiet"]())
    _, alerts = evaluate(traces, cfg)
    _, quiet_alerts = evaluate(quiet_traces, cfg)

    det = detection(scenario, alerts)
    guards = guardrail_metrics()
    evals_ = evaluator_validation(traces)
    tri = triage_checks(traces)
    fb = feedback_export(traces)
    rel = release_checks(traces)
    summary = {
        "incident_recall": det["recall"], "max_detection_delay_days": det["max_delay"],
        "unexplained_alerts": len(det["unexplained_alerts"]), "quiet_period_alerts": len(quiet_alerts),
        "pii_recall": guards["pii_recall"], "pii_precision": guards["pii_precision"],
        "injection_recall": guards["injection_recall"], "injection_precision": guards["injection_precision"],
        "evaluator_precision": evals_["precision"], "evaluator_recall": evals_["recall"],
        "triage_accuracy": tri["accuracy"], "regression_cases_exported": fb["cases"], "regression_case_pii_leaks": fb["pii_leaks"],
        "release_decision_accuracy": rel["accuracy"],
    }
    thresholds = json.loads((HERE / "thresholds.json").read_text(encoding="utf-8"))
    failures = check_gates(summary, thresholds)

    args.out.mkdir(parents=True, exist_ok=True)
    report = {"monitor": args.monitor, "summary": summary, "gate_failures": failures, "detection": det,
              "guardrails": guards, "evaluator": evals_, "triage": tri, "feedback": fb, "release": rel,
              "alerts": [a.__dict__ for a in alerts], "quiet_alerts": [a.__dict__ for a in quiet_alerts]}
    (args.out / "monitoring_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    md = to_markdown(args.monitor, summary, det, quiet_alerts, guards, evals_, tri, fb, rel, thresholds, failures)
    (args.out / "monitoring_report.md").write_text(md, encoding="utf-8")
    print(md)
    if failures and not args.no_gate:
        print("Quality gate FAILED", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
