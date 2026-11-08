"""One clock for a simulated run.

Scenario data carries plant time (the Friday Cascade is 12 June, 14:32). The draft tools
used to stamp the real date, so a careful model saw two different "nows" in one run and
flagged the data as stale. Inside `sim_clock(...)` every draft uses plant time instead,
and says so. Outside it nothing changes: real runs keep the wall clock.

The audit log keeps the wall clock on purpose. It records when the software ran, not
what time it was in the plant.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone

# (plant time at start, wall time at start). Plant time advances with the wall clock from
# there, so two drafts in one run still get distinct, ordered timestamps.
_CLOCK: ContextVar[tuple[datetime, datetime] | None] = ContextVar("tos_sim_clock", default=None)


def _parse(at: datetime | str) -> datetime:
    if isinstance(at, str):
        at = datetime.fromisoformat(at.replace("Z", "+00:00"))
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def now() -> datetime:
    """Plant time inside a simulated run, wall-clock UTC otherwise."""
    clock = _CLOCK.get()
    real = datetime.now(timezone.utc)
    if clock is None:
        return real
    plant_start, wall_start = clock
    return plant_start + (real - wall_start)


def basis() -> str:
    """What `now()` is measuring, so a draft can tell its reader."""
    return "simulated_plant_time" if _CLOCK.get() is not None else "wall_clock"


@contextmanager
def sim_clock(at: datetime | str | None):
    """Run the block on plant time starting at `at`. None leaves the wall clock alone,
    so callers can pass an alert's optional timestamp straight through."""
    if at is None:
        yield
        return
    token = _CLOCK.set((_parse(at), datetime.now(timezone.utc)))
    try:
        yield
    finally:
        _CLOCK.reset(token)
