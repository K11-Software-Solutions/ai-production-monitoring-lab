import pytest

from prodlab.simulate import SCENARIOS, simulate
from prodlab.traces import Trace


@pytest.fixture(scope="session")
def incident_traces():
    return simulate(SCENARIOS["incidents"]())


@pytest.fixture(scope="session")
def quiet_traces():
    return simulate(SCENARIOS["quiet"]())


def make_trace(day=1, n=0, **overrides) -> Trace:
    base = dict(trace_id=f"t{day}-{n}", day=day, query="How do I export my notes?", language="en",
                answer="You can export all notes from Settings under Data.", model_version="m", prompt_version="v1",
                topic="export", retrieval_score=0.3,
                context="You can export all notes from Settings under Data. Exports are delivered as a ZIP file.",
                tokens_in=400, tokens_out=15, latency_ms=800.0, cost_usd=0.0002)
    base.update(overrides)
    return Trace(**base)
