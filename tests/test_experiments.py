"""Smoke test: the paper's experiment runner works end to end on a couple of seeds."""
from experiments.run_experiments import attributed, attribution_window, incident_scenario, main, wilson
from prodlab.monitors import Alert
from prodlab.simulate import INCIDENTS


def test_attribution_window_closes_before_the_next_incident():
    by_name = {i.name: i for i in INCIDENTS}
    assert attribution_window(by_name["feature_launch_not_in_docs"], INCIDENTS) == (8, 8)   # language shift starts day 9
    assert attribution_window(by_name["language_shift"], INCIDENTS) == (9, 10)
    assert attribution_window(by_name["prompt_bloat"], INCIDENTS) == (13, 14)


def test_attributed_detection_ignores_alerts_from_other_incidents():
    sc = incident_scenario(1)
    # A groundedness alert on day 8 is caused by the model update, not the feature launch.
    rows = {r["incident"]: r for r in attributed(sc, [Alert(8, "groundedness_failure_rate", 1, 0, "")])["rows"]}
    assert not rows["feature_launch_not_in_docs"]["detected"]


def test_wilson_interval():
    p, lo, hi = wilson(50, 50)
    assert p == 1.0 and 0.9 < lo < 1.0 and hi == 1.0


def test_runner_smoke(tmp_path):
    assert main(["--seeds", "2", "--only", "e1", "e5", "e6", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "summary.md").is_file() and (tmp_path / "e1_designs.csv").is_file()
