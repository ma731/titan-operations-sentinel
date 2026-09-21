"""Run-scoped inputs for simulated telemetry and labelled evaluation fixtures.

Context variables propagate into LangGraph's workers without rewriting shared data files.
They provide tool inputs only: model tool selection, calculations and policy still run.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy

_INPUTS: ContextVar[dict | None] = ContextVar("tos_inputs", default=None)


def current() -> dict:
    return deepcopy(_INPUTS.get() or {})


@contextmanager
def runtime_inputs(machine_id: str, readings: dict, telemetry_status: str = "OK",
                   sourcing: dict | None = None):
    token = _INPUTS.set(deepcopy({"machine_id": machine_id, "readings": readings,
                               "telemetry_status": telemetry_status, "sourcing": sourcing}))
    try:
        yield
    finally:
        _INPUTS.reset(token)
