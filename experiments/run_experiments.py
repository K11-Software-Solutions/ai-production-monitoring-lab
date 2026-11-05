"""Experiments behind the paper "Who Monitors the Monitors?".

    python -m experiments.run_experiments                # all experiments, 50 seeds (a few minutes)
    python -m experiments.run_experiments --seeds 5      # quick run
    python -m experiments.run_experiments --only e1 e3   # selected experiments

Every number is computed from the deterministic simulator, so results are
exactly reproducible from the seed list. Outputs go to experiments/results/:
one CSV per experiment plus summary.md.

E1  Monitor designs across seeds: incident recall, detection delay, false alarms
E2  Alert-rule thresholds: z-threshold x minimum-effect scale (recall vs false alarms)
E3  Sensitivity: detection probability vs incident magnitude (latency, injection, feature launch)
E4  Online-eval sampling: sample rate x risk-based inclusion (detection delay vs evaluation cost)
E5  Online evaluator validity across seeds (precision, recall vs hidden labels)
E6  Shadow-release decisions across seeds (accuracy of promote/reject)
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
import time
from dataclasses import replace
from pathlib import Path

from evals.run_monitoring_evals import detection
from prodlab import online_evals, release
from prodlab.monitors import MonitorConfig, evaluate
from prodlab.simulate import INCIDENTS, Magnitudes, Scenario, simulate

OUT = Path(__file__).parent / "results"
RATE_RULES = MonitorConfig().rate_rules


# --- statistics ------------------------------------------------------------------

def mean_ci(values: list[float]) -> tuple[float, float]:
    """Mean and 95% confidence half-width (normal approximation)."""
    if not values:
        return 0.0, 0.0
    m = statistics.fmean(values)
    if len(values) < 2:
        return m, 0.0
    return m, 1.96 * statistics.stdev(values) / math.sqrt(len(values))


def wilson(k: int, n: int) -> tuple[float, float, float]:
    """Proportion with a 95% Wilson score interval (lower, upper)."""
    if n == 0:
        return 0.0, 0.0, 0.0
    z, p = 1.96, k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return p, max(0.0, centre - half), min(1.0, centre + half)


def fmt(m: float, h: float, digits: int = 3) -> str:
    return f"{m:.{digits}f} ± {h:.{digits}f}"


# --- scenarios and monitor designs -------------------------------------------------

def incident_scenario(seed: int, mag: Magnitudes | None = None) -> Scenario:
    return Scenario("incidents", seed=seed, incidents=list(INCIDENTS), magnitudes=mag or Magnitudes())


def quiet_scenario(seed: int) -> Scenario:
    return Scenario("quiet", seed=seed)


DESIGNS = {
    "standard (p95, z>=3 + min effect)": lambda: MonitorConfig(),
    "mean latency": lambda: MonitorConfig(latency_stat="mean"),
    "significance only (z>=3, no min effect)": lambda: MonitorConfig(rate_rules={k: 0.0 for k in RATE_RULES}),
    "effect only (min effect, no z-test)": lambda: MonitorConfig(z_threshold=0.0),
    "no statistics (any increase)": lambda: MonitorConfig(z_threshold=0.0, rate_rules={k: 0.0 for k in RATE_RULES}),
}


# Incident-specific monitors for *attributed* detection. Incidents overlap in time (the model
# update persists from day 5), so an alert on a broad monitor such as groundedness could be
# caused by an earlier incident. For the experiments an incident counts as detected only via
# its own signals, inside a window that closes before the next incident starts.
SPECIFIC = {
    "silent_model_update": {"avg_output_tokens", "groundedness_failure_rate", "cost_per_request"},
    "feature_launch_not_in_docs": {"unknown_topic_rate", "topic_psi"},
    "language_shift": {"language_psi", "language_mismatch_rate"},
    "provider_latency_spike": {"latency_p95"},
    "prompt_injection_campaign": {"injection_flag_rate"},
    "prompt_bloat": {"avg_input_tokens", "cost_per_request"},
}

# Smaller incidents, where alert thresholds start to matter (E2).
SUBTLE = Magnitudes(injection_share=0.015, feature_share=0.04, language_share=0.04, slow_fraction=0.06)


def attribution_window(incident, incidents, max_delay: int = 1) -> tuple[int, int]:
    later = [i.start_day for i in incidents if i.start_day > incident.start_day]
    end = incident.start_day + max_delay
    if later:
        end = min(end, min(later) - 1)
    return incident.start_day, max(end, incident.start_day)


def attributed(scenario: Scenario, alerts) -> dict:
    rows = []
    for inc in scenario.incidents:
        lo, hi = attribution_window(inc, scenario.incidents)
        days = sorted(a.day for a in alerts if a.monitor in SPECIFIC[inc.name] and lo <= a.day <= hi)
        rows.append({"incident": inc.name, "detected": bool(days), "delay_days": (days[0] - inc.start_day) if days else None})
    return {"rows": rows, "recall": sum(r["detected"] for r in rows) / len(rows)}


def write_csv(name: str, rows: list[dict]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / f"{name}.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


# --- E1 --------------------------------------------------------------------------------

def e1_designs(seeds: list[int], cache: dict) -> str:
    rows, md = [], ["## E1. Monitor designs across seeds", "",
                    f"{len(seeds)} seeds of the incident scenario and {len(seeds)} of the quiet scenario. "
                    "Mean ± 95% CI; per-incident detection with 95% Wilson intervals. Recall uses attributed detection "
                    "(incident-specific monitors, window closing before the next incident).", "",
                    "| Design | Incident recall | Mean delay (days) | Quiet-period alerts per run | Quiet runs with zero alerts | Unexplained alerts per incident run |",
                    "|---|---|---|---|---|---|"]
    per_incident_tables = []
    for name, make in DESIGNS.items():
        recalls, delays, quiet_alerts, unexplained = [], [], [], []
        hits = {i.name: 0 for i in INCIDENTS}
        for seed in seeds:
            inc_traces, q_traces = cache["inc"][seed], cache["quiet"][seed]
            _, alerts = evaluate(inc_traces, make())
            _, q_alerts = evaluate(q_traces, make())
            det = detection(incident_scenario(seed), alerts)
            att = attributed(incident_scenario(seed), alerts)
            recalls.append(att["recall"])
            delays += [r["delay_days"] for r in att["rows"] if r["detected"]]
            for r in att["rows"]:
                hits[r["incident"]] += r["detected"]
            quiet_alerts.append(len(q_alerts))
            unexplained.append(len(det["unexplained_alerts"]))
            rows.append({"design": name, "seed": seed, "recall": att["recall"], "quiet_alerts": len(q_alerts),
                         "unexplained_alerts": len(det["unexplained_alerts"])})
        zero = sum(q == 0 for q in quiet_alerts)
        p, lo, hi = wilson(zero, len(seeds))
        md.append(f"| {name} | {fmt(*mean_ci(recalls))} | {fmt(*mean_ci(delays), 2)} | {fmt(*mean_ci(quiet_alerts), 1)} | "
                  f"{zero}/{len(seeds)} [{lo:.2f}, {hi:.2f}] | {fmt(*mean_ci(unexplained), 1)} |")
        per_incident_tables.append((name, hits))
    md += ["", "Per-incident attributed detection rate:", "",
           "| Design | " + " | ".join(i.name for i in INCIDENTS) + " |", "|---|" + "---|" * len(INCIDENTS)]
    for name, hits in per_incident_tables:
        cells = []
        for i in INCIDENTS:
            p, lo, hi = wilson(hits[i.name], len(seeds))
            cells.append(f"{p:.2f} [{lo:.2f}, {hi:.2f}]")
        md.append(f"| {name} | " + " | ".join(cells) + " |")
    write_csv("e1_designs", rows)
    return "\n".join(md)


# --- E2 --------------------------------------------------------------------------------

def e2_thresholds(seeds: list[int], cache: dict) -> str:
    z_values = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    scales = [0.0, 0.5, 1.0, 2.0]
    subtle = {seed: simulate(incident_scenario(seed, SUBTLE)) for seed in seeds}
    rows = []
    md = ["## E2. Alert-rule thresholds", "",
          f"Rate rules only; ratio and drift rules unchanged. {len(seeds)} seeds per cell. Each cell: attributed "
          "recall on the default incidents / attributed recall on subtle incidents / mean quiet-period alerts per run.",
          f"Subtle incidents: injection share {SUBTLE.injection_share}, feature share {SUBTLE.feature_share}, "
          f"language share {SUBTLE.language_share}.", "",
          "| z threshold | " + " | ".join(f"min effect x{s}" for s in scales) + " |", "|---|" + "---|" * len(scales)]
    for z in z_values:
        cells = []
        for sc in scales:
            cfg = lambda: MonitorConfig(z_threshold=z, rate_rules={k: v * sc for k, v in RATE_RULES.items()})
            rec_default, rec_subtle, quiet = [], [], []
            for seed in seeds:
                _, alerts = evaluate(cache["inc"][seed], cfg())
                _, alerts_s = evaluate(subtle[seed], cfg())
                _, q = evaluate(cache["quiet"][seed], cfg())
                rec_default.append(attributed(incident_scenario(seed), alerts)["recall"])
                rec_subtle.append(attributed(incident_scenario(seed, SUBTLE), alerts_s)["recall"])
                quiet.append(len(q))
            rd, rs, qa = statistics.fmean(rec_default), statistics.fmean(rec_subtle), statistics.fmean(quiet)
            rows.append({"z_threshold": z, "min_effect_scale": sc, "recall_default": round(rd, 4),
                         "recall_subtle": round(rs, 4), "quiet_alerts": round(qa, 3)})
            cells.append(f"{rd:.2f} / {rs:.2f} / {qa:.2f}")
        md.append(f"| {z:g} | " + " | ".join(cells) + " |")
    write_csv("e2_thresholds", rows)
    return "\n".join(md)


# --- E3 --------------------------------------------------------------------------------

def _detected(scenario: Scenario, alerts, incident: str, monitors: set[str] | None = None) -> bool:
    inc = next(i for i in scenario.incidents if i.name == incident)
    lo, hi = attribution_window(inc, scenario.incidents)
    allowed = monitors or SPECIFIC[incident]
    return any(a.monitor in allowed and lo <= a.day <= hi for a in alerts)


def e3_sensitivity(seeds: list[int]) -> str:
    rows, md = [], ["## E3. Detection probability vs incident magnitude", "",
                    f"{len(seeds)} seeds per point; attributed detection; 95% Wilson intervals.", ""]
    sweeps = [
        ("slow_fraction", [0.01, 0.02, 0.03, 0.04, 0.06, 0.08, 0.10, 0.15], "provider_latency_spike",
         {"p95 monitor": MonitorConfig(), "mean monitor": MonitorConfig(latency_stat="mean")}, {"latency_p95"}),
        ("injection_share", [0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12], "prompt_injection_campaign",
         {"standard": MonitorConfig()}, {"injection_flag_rate"}),
        ("feature_share", [0.02, 0.05, 0.10, 0.20, 0.30], "feature_launch_not_in_docs",
         {"standard": MonitorConfig()}, None),
    ]
    for param, values, incident, configs, monitors in sweeps:
        md += [f"**{param}** ({incident})", "", "| " + param + " | " + " | ".join(configs) + " |",
               "|---|" + "---|" * len(configs)]
        for v in values:
            mag = replace(Magnitudes(), **{param: v})
            hits = {c: 0 for c in configs}
            for seed in seeds:
                sc = incident_scenario(seed, mag)
                traces = simulate(sc)
                for cname, cfg in configs.items():
                    _, alerts = evaluate(traces, cfg)
                    hits[cname] += _detected(sc, alerts, incident, monitors)
            cells = []
            for cname in configs:
                p, lo, hi = wilson(hits[cname], len(seeds))
                cells.append(f"{p:.2f} [{lo:.2f}, {hi:.2f}]")
                rows.append({"parameter": param, "value": v, "monitor": cname, "detection_rate": round(p, 4),
                             "ci_low": round(lo, 4), "ci_high": round(hi, 4), "n": len(seeds)})
            md.append(f"| {v:g} | " + " | ".join(cells) + " |")
        md.append("")
    write_csv("e3_sensitivity", rows)
    return "\n".join(md)


# --- E4 --------------------------------------------------------------------------------

def e4_sampling(seeds: list[int], cache: dict) -> str:
    rates = [0.02, 0.05, 0.10, 0.20, 0.50, 1.00]
    inc = next(i for i in INCIDENTS if i.name == "silent_model_update")
    rows, md = [], ["## E4. Online-evaluation sampling", "",
                    f"Groundedness monitor only, silent model update (onset day {inc.start_day}). {len(seeds)} seeds. "
                    "Only alerts before the feature launch (day 8) are attributed to the update; undetected runs count as a 3-day delay (censored).", "",
                    "| Sample rate | Risk-based inclusion | Detected before day 8 | Mean delay (days, censored at 3) | Evaluations per day | Quiet-period groundedness alerts |",
                    "|---|---|---|---|---|---|"]
    for rate in rates:
        for risky in (True, False):
            delays, evals_per_day, quiet_alerts, by_day7 = [], [], [], 0
            for seed in seeds:
                cfg = MonitorConfig(sample_rate=rate)
                orig = online_evals.sample
                online_evals.sample = lambda t, r, seed=0, include_risky=True, _o=orig: _o(t, r, seed, include_risky=risky)
                try:
                    _, alerts = evaluate(cache["inc"][seed], cfg)
                    _, q = evaluate(cache["quiet"][seed], cfg)
                finally:
                    online_evals.sample = orig
                days = sorted(a.day for a in alerts if a.monitor == "groundedness_failure_rate" and inc.start_day <= a.day <= 7)
                delays.append((days[0] - inc.start_day) if days else 3)
                by_day7 += bool(days)
                quiet_alerts.append(sum(a.monitor == "groundedness_failure_rate" for a in q))
                n_eval = len(orig(cache["inc"][seed], rate, seed=seed, include_risky=risky))
                evals_per_day.append(n_eval / 14)
            p, lo, hi = wilson(by_day7, len(seeds))
            rows.append({"sample_rate": rate, "risk_based": risky, "detected_by_day7": round(p, 4),
                         "mean_delay": round(statistics.fmean(delays), 3), "evals_per_day": round(statistics.fmean(evals_per_day), 1),
                         "quiet_alerts": round(statistics.fmean(quiet_alerts), 3)})
            md.append(f"| {rate:g} | {'yes' if risky else 'no'} | {p:.2f} [{lo:.2f}, {hi:.2f}] | {fmt(*mean_ci(delays), 2)} | "
                      f"{statistics.fmean(evals_per_day):.0f} | {statistics.fmean(quiet_alerts):.2f} |")
    write_csv("e4_sampling", rows)
    return "\n".join(md)


# --- E5 and E6 ------------------------------------------------------------------------------

def e5_evaluator(seeds: list[int], cache: dict) -> str:
    rows, precisions, recalls = [], [], []
    for seed in seeds:
        sampled = online_evals.sample(cache["inc"][seed], 0.2, seed=seed)
        pred = [not online_evals.grounded(t.answer, t.context) for t in sampled]
        truth = [t.truth["hallucinated"] for t in sampled]
        tp = sum(p and y for p, y in zip(pred, truth))
        fp = sum(p and not y for p, y in zip(pred, truth))
        fn = sum(y and not p for p, y in zip(pred, truth))
        prec = tp / (tp + fp) if tp + fp else 1.0
        rec = tp / (tp + fn) if tp + fn else 1.0
        precisions.append(prec)
        recalls.append(rec)
        rows.append({"seed": seed, "n": len(sampled), "tp": tp, "fp": fp, "fn": fn, "precision": round(prec, 4), "recall": round(rec, 4)})
    write_csv("e5_evaluator", rows)
    return "\n".join(["## E5. Online groundedness evaluator vs hidden labels", "",
                      f"{len(seeds)} seeds, 20% random sample plus risky traces.", "",
                      f"- Precision: {fmt(*mean_ci(precisions))}", f"- Recall: {fmt(*mean_ci(recalls))}",
                      f"- False negatives across all seeds: {sum(r['fn'] for r in rows)} "
                      f"(of {sum(r['tp'] + r['fn'] for r in rows)} hallucinations)"])


def e6_release(seeds: list[int], cache: dict) -> str:
    expected = {"model-b-good": True, "model-b-bad": False, "model-a-2026-11": False}
    rows, correct = [], {c: 0 for c in expected}
    for seed in seeds:
        for cand, should in expected.items():
            d = release.shadow_test(cache["inc"][seed], cand)
            correct[cand] += d.promote == should
            rows.append({"seed": seed, "candidate": cand, "promote": d.promote, "expected": should, "reasons": "; ".join(d.reasons)})
    write_csv("e6_release", rows)
    md = ["## E6. Shadow-release decisions across seeds", "", "| Candidate | Expected | Correct decisions |", "|---|---|---|"]
    for cand, should in expected.items():
        p, lo, hi = wilson(correct[cand], len(seeds))
        md.append(f"| {cand} | {'promote' if should else 'reject'} | {correct[cand]}/{len(seeds)} [{lo:.2f}, {hi:.2f}] |")
    return "\n".join(md)


def main(argv: list[str] | None = None) -> int:
    global OUT
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seeds", type=int, default=50)
    parser.add_argument("--only", nargs="*", default=["e1", "e2", "e3", "e4", "e5", "e6"])
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)
    OUT = args.out
    inc_seeds = list(range(1000, 1000 + args.seeds))
    quiet_seeds = inc_seeds  # paired: the same seed list is used for both scenarios
    start = time.perf_counter()
    cache = {"inc": {s: simulate(incident_scenario(s)) for s in inc_seeds},
             "quiet": {s: simulate(quiet_scenario(s + 5000)) for s in quiet_seeds}}
    sections = [f"# Experiment results", "", f"Seeds: {inc_seeds[0]}–{inc_seeds[-1]} (incident scenario); "
                f"{inc_seeds[0] + 5000}–{inc_seeds[-1] + 5000} (quiet scenario). 14 days × 400 requests per run.", ""]
    runners = {"e1": lambda: e1_designs(inc_seeds, cache), "e2": lambda: e2_thresholds(inc_seeds, cache),
               "e3": lambda: e3_sensitivity(inc_seeds), "e4": lambda: e4_sampling(inc_seeds, cache),
               "e5": lambda: e5_evaluator(inc_seeds, cache), "e6": lambda: e6_release(inc_seeds, cache)}
    for key in args.only:
        t = time.perf_counter()
        sections += [runners[key](), ""]
        print(f"{key} done in {time.perf_counter() - t:.0f}s", file=sys.stderr)
    sections.append(f"_Total runtime: {time.perf_counter() - start:.0f} s._")
    OUT.mkdir(parents=True, exist_ok=True)
    text = "\n".join(sections)
    (OUT / "summary.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
