"""Shadow testing a release candidate against production traffic.

The candidate answers the same real queries as production, but its answers
are only recorded, never shown to users. A deterministic decision rule then
promotes or rejects it. Because both models see identical queries with
identical random seeds, differences come from the models, not the traffic.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from prodlab import online_evals
from prodlab.monitors import percentile, two_proportion_z
from prodlab.system import MODELS, answer
from prodlab.traces import Trace


@dataclass
class ShadowResult:
    model: str
    n: int
    groundedness_failures: int
    refusals: int
    over_refusals: int  # refused although the help articles had the answer
    latency_p95: float
    cost_per_request: float

    @property
    def groundedness_failure_rate(self) -> float:
        return self.groundedness_failures / self.n

    @property
    def refusal_rate(self) -> float:
        return self.refusals / self.n

    @property
    def over_refusal_rate(self) -> float:
        return self.over_refusals / self.n


def replay(queries: list[str], model_name: str, prompt_version: str = "v1", seed: int = 0) -> ShadowResult:
    model = MODELS[model_name]
    fails = refusals = over = 0
    latencies, costs = [], []
    for i, q in enumerate(queries):
        ans = answer(q, model, prompt_version, random.Random(seed * 100_000 + i))
        fails += not online_evals.grounded(ans.text, ans.context)
        refused = online_evals.is_refusal(ans.text)
        refusals += refused
        over += refused and bool(ans.context)
        latencies.append(ans.latency_ms)
        costs.append(ans.cost_usd)
    return ShadowResult(model_name, len(queries), fails, refusals, over, round(percentile(latencies, 95), 1),
                        round(sum(costs) / len(costs), 6))


@dataclass
class Decision:
    promote: bool
    reasons: list[str]
    production: ShadowResult
    candidate: ShadowResult


def decide(prod: ShadowResult, cand: ShadowResult, min_samples: int = 300, quality_tolerance: float = 0.01,
           latency_tolerance: float = 1.2, cost_tolerance: float = 1.2) -> Decision:
    reasons = []
    if cand.n < min_samples:
        reasons.append(f"not enough shadow traffic ({cand.n} < {min_samples})")
    z = two_proportion_z(prod.groundedness_failures, prod.n, cand.groundedness_failures, cand.n)
    if cand.groundedness_failure_rate > prod.groundedness_failure_rate + quality_tolerance and z > 2:
        reasons.append(f"groundedness failures up: {cand.groundedness_failure_rate:.3f} vs {prod.groundedness_failure_rate:.3f} (z={z:.1f})")
    # Refusing an unanswerable question is correct; only refusals of answerable ones count.
    # A naive "refusal rate" check would reject a candidate for being more honest (article 06).
    if cand.over_refusal_rate > prod.over_refusal_rate + quality_tolerance:
        reasons.append(f"over-refusals up: {cand.over_refusal_rate:.3f} vs {prod.over_refusal_rate:.3f}")
    if cand.latency_p95 > prod.latency_p95 * latency_tolerance:
        reasons.append(f"p95 latency up: {cand.latency_p95} vs {prod.latency_p95}")
    if cand.cost_per_request > prod.cost_per_request * cost_tolerance:
        reasons.append(f"cost up: {cand.cost_per_request} vs {prod.cost_per_request}")
    return Decision(not reasons, reasons, prod, cand)


def shadow_test(traces: list[Trace], candidate: str, production: str = "model-a-2026-09", days: int = 4) -> Decision:
    queries = [t.query for t in traces if t.day <= days]
    return decide(replay(queries, production), replay(queries, candidate))
