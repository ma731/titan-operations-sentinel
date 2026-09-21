from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import observability
from tools.runtime_inputs import current, runtime_inputs
from tools.sensor_query import sensor_query


def test_nested_inputs_restore_after_failure():
    with runtime_inputs("outer", {"vibration": 7}):
        try:
            with runtime_inputs("inner", {"vibration": 2}):
                raise RuntimeError("test")
        except RuntimeError:
            pass
        assert current()["machine_id"] == "outer"
    assert current() == {}


def test_readings_are_copied_and_reach_sensor_tool():
    original = {"vibration": 6.2}
    with runtime_inputs("CNC-07-LEI", original):
        original["vibration"] = 100
        result = sensor_query("CNC-07-LEI", "72h", ["vibration"])
        assert result["readings"]["vibration"] == [6.2]


def test_simultaneous_usage_and_inputs_do_not_cross_runs():
    barrier = Barrier(2)

    def work(i):
        with runtime_inputs(str(i), {}), observability.instrument_run("test") as usage:
            barrier.wait(timeout=5)
            tracker = observability.active_tracker()
            with observability.instrumented_agent(str(i)):
                tracker.on_llm_end(SimpleNamespace(llm_output={"token_usage": {"prompt_tokens": i}}))
            assert current()["machine_id"] == str(i)
            return usage.to_dict()

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(work, [1, 2]))
    assert [r["total_tokens"] for r in results] == [1, 2]
    assert [list(r["by_agent"]) for r in results] == [["1"], ["2"]]
    assert observability.active_tracker() is None
