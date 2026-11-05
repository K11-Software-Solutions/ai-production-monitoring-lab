"""Trace records: one per production request, stored as JSON Lines.

This is the data a tracing platform (Langfuse, LangSmith, an OpenTelemetry
backend) would hold. Every monitor, online eval and investigation in this lab
reads only these records, never the simulator's internals, except for the
hidden `truth` field, which exists solely to validate the evaluators.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Trace:
    trace_id: str
    day: int
    query: str                 # already PII-redacted: raw PII is never stored
    language: str
    answer: str
    model_version: str
    prompt_version: str
    topic: str | None
    retrieval_score: float
    context: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    cost_usd: float
    error: bool = False
    pii_detected: list[str] = field(default_factory=list)
    injection_flag: bool = False
    feedback: str | None = None  # "up" | "down" | None
    truth: dict = field(default_factory=dict)  # simulator-only labels; never used by monitors


def write_traces(traces: list[Trace], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for t in traces:
            fh.write(json.dumps(asdict(t)) + "\n")


def read_traces(path: Path) -> list[Trace]:
    with Path(path).open(encoding="utf-8") as fh:
        return [Trace(**json.loads(line)) for line in fh if line.strip()]
