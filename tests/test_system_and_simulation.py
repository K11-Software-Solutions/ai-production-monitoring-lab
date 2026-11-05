import random

import pytest

from prodlab import guardrails
from prodlab.simulate import INCIDENTS, SCENARIOS, detect_language, simulate
from prodlab.system import MODELS, REFUSAL, answer, retrieve
from prodlab.traces import read_traces, write_traces


@pytest.mark.parametrize("query, topic", [
    ("How do I get a refund?", "refund"),
    ("What is the API rate limit?", "api"),
    ("How do team workspaces work?", None),
    ("¿Cómo puedo obtener un reembolso?", None),
])
def test_retrieval(query, topic):
    assert retrieve(query)[0] == topic


def test_known_retrieval_gap_word_forms():
    """Documented: keyword retrieval misses 'syncing' (only 'sync' is listed)."""
    assert retrieve("Why are my notes not syncing?")[0] is None


def test_answer_is_deterministic_for_a_seed():
    a = answer("How do I export my notes?", MODELS["model-a-2026-09"], "v1", random.Random(1))
    b = answer("How do I export my notes?", MODELS["model-a-2026-09"], "v1", random.Random(1))
    assert a == b


def test_unanswerable_question_refuses_or_hallucinates():
    outcomes = {answer("How do team seats work?", MODELS["model-a-2026-09"], "v1", random.Random(i)).text
                for i in range(50)}
    assert REFUSAL in outcomes and len(outcomes) > 1


def test_silent_update_is_chattier():
    q = "How do I export my notes?"
    old = answer(q, MODELS["model-a-2026-09"], "v1", random.Random(3))
    new = answer(q, MODELS["model-a-2026-11"], "v1", random.Random(3))
    assert new.tokens_out > old.tokens_out * 1.5


def test_prompt_bloat_increases_input_tokens_and_cost():
    q = "How do I export my notes?"
    lean = answer(q, MODELS["model-a-2026-09"], "v1", random.Random(3))
    bloated = answer(q, MODELS["model-a-2026-09"], "v2-bloated", random.Random(3))
    assert bloated.tokens_in > lean.tokens_in + 1000 and bloated.cost_usd > lean.cost_usd


def test_language_detection():
    assert detect_language("¿Cuánto cuesta el plan Pro?") == "es"
    assert detect_language("How much does the plan cost?") == "en"


def test_simulation_is_reproducible():
    a = simulate(SCENARIOS["quiet"]())
    b = simulate(SCENARIOS["quiet"]())
    assert [t.answer for t in a] == [t.answer for t in b]


def test_incidents_happen_on_schedule(incident_traces):
    by_day = {d: [t for t in incident_traces if t.day == d] for d in range(1, 15)}
    assert {t.model_version for t in by_day[4]} == {"model-a-2026-09"}
    assert {t.model_version for t in by_day[5]} == {"model-a-2026-11"}
    assert {t.prompt_version for t in by_day[13]} == {"v2-bloated"}
    assert any(t.injection_flag for t in by_day[12]) and not any(t.injection_flag for t in by_day[11])
    assert any(t.language == "es" for t in by_day[9]) and not any(t.language == "es" for t in by_day[8])
    assert {i.name for i in INCIDENTS} == {i.name for i in SCENARIOS["incidents"]().incidents}


def test_quiet_scenario_has_no_incidents(quiet_traces):
    assert SCENARIOS["quiet"]().incidents == []
    assert {t.model_version for t in quiet_traces} == {"model-a-2026-09"}


def test_raw_pii_is_never_stored_in_traces(incident_traces):
    with_pii = [t for t in incident_traces if t.pii_detected]
    assert with_pii, "the simulator should include some PII"
    assert all(not guardrails.find_pii(t.query) for t in incident_traces)


def test_trace_round_trip(tmp_path, quiet_traces):
    path = tmp_path / "t.jsonl"
    write_traces(quiet_traces[:5], path)
    assert read_traces(path) == quiet_traces[:5]
