"""From alert to root cause to regression test.

1. `segment_breakdown` answers "which slice of traffic moved the metric?" by
   comparing each segment (topic, language, model version, prompt version)
   against the baseline.
2. `export_regression_cases` turns bad production conversations into
   candidate eval cases, so the next offline eval run covers what users hit.
   Queries are already redacted at trace time, and the export re-checks that
   no PII slipped through, because test datasets get copied everywhere.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Callable

from prodlab import guardrails, online_evals
from prodlab.traces import Trace

DIMENSIONS = ("topic", "language", "model_version", "prompt_version")

PREDICATES: dict[str, Callable[[Trace], bool]] = {
    "refusal_rate": lambda t: online_evals.is_refusal(t.answer),
    "unknown_topic_rate": lambda t: t.topic is None,
    "thumbs_down_rate": lambda t: t.feedback == "down",
    "groundedness_failure_rate": lambda t: not online_evals.grounded(t.answer, t.context),
    "language_mismatch_rate": lambda t: online_evals.language_mismatch(t.query, t.answer),
    "injection_flag_rate": lambda t: t.injection_flag,
}


def global_changes(traces: list[Trace], day: int, baseline_days: int = 4) -> dict[str, tuple]:
    """Dimensions that changed for ALL of today's traffic (e.g. a new model version). They
    explain everything and nothing at once, so they are reported separately from segments."""
    today = [t for t in traces if t.day == day]
    base = [t for t in traces if t.day <= baseline_days]
    out = {}
    for dim in DIMENSIONS:
        now, before = {getattr(t, dim) for t in today}, {getattr(t, dim) for t in base}
        if len(now) == 1 and now != before:
            out[dim] = (sorted(map(str, before)), sorted(map(str, now)))
    return out


def segment_breakdown(traces: list[Trace], day: int, metric: str, baseline_days: int = 4, top: int = 3) -> list[dict]:
    """Rank segments by how much they added to the metric's rate versus the baseline.

    contribution = (events in segment today / requests today) - (events in segment in baseline / baseline requests)
    Dimensions with a single value today (global changes) are skipped; see global_changes().
    """
    pred = PREDICATES[metric]
    today = [t for t in traces if t.day == day]
    base = [t for t in traces if t.day <= baseline_days]
    rows = []
    for dim in DIMENSIONS:
        if len({getattr(t, dim) for t in today}) == 1:
            continue
        values = {getattr(t, dim) for t in today} | {getattr(t, dim) for t in base}
        for v in values:
            seg_today = [t for t in today if getattr(t, dim) == v]
            seg_base = [t for t in base if getattr(t, dim) == v]
            contrib = (sum(map(pred, seg_today)) / max(len(today), 1)) - (sum(map(pred, seg_base)) / max(len(base), 1))
            rows.append({"dimension": dim, "value": "none" if v is None else v, "contribution": round(contrib, 4),
                         "share_today": round(len(seg_today) / max(len(today), 1), 3),
                         "share_baseline": round(len(seg_base) / max(len(base), 1), 3)})
    rows.sort(key=lambda r: -r["contribution"])
    return rows[:top]


def _normalise(q: str) -> str:
    return re.sub(r"\W+", " ", q.lower()).strip()


def export_regression_cases(traces: list[Trace], days: set[int] | None = None) -> list[dict]:
    """Thumbs-down and ungrounded answers become candidate eval cases (deduplicated, PII-free)."""
    seen, cases = set(), []
    for t in traces:
        if days and t.day not in days:
            continue
        reasons = []
        if t.feedback == "down":
            reasons.append("thumbs_down")
        if not online_evals.grounded(t.answer, t.context):
            reasons.append("ungrounded")
        if not reasons:
            continue
        key = _normalise(t.query)
        if key in seen:
            continue
        seen.add(key)
        query = guardrails.redact(t.query)
        if guardrails.find_pii(query):
            continue  # never put personal data into a test set
        cases.append({"query": query, "observed_answer": t.answer, "reasons": reasons, "day": t.day,
                      "topic": t.topic, "language": t.language,
                      "needs_label": "expected answer to be written by a human reviewer"})
    return cases
