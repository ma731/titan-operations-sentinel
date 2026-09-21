"""
Continuous alert stream: the system triggers itself instead of waiting for a human.

Until now a run started because somebody typed a command. That is fine for a demo and
wrong for the story the project tells, which is that a plant produces tens of thousands
of signals a day and the hard part is noticing the one that matters.

Three pieces:

  simulator.py  A seeded fleet simulator. Every tick it emits a reading per machine,
                with a degradation model on the machines that are actually failing and
                noise on the ones that are not.
  triage.py     The gate. It scores each reading against the documented severity bands
                and decides whether this is worth waking six agents for. Most readings
                are not. It also enforces a cooldown, because a machine that is degrading
                stays above threshold for hours and must not start a run per tick.
  run.py        The loop that wires the two together and invokes the graph when triage
                says so.

The triage gate is deliberately cheap and deterministic. Spending model tokens to decide
whether to spend model tokens is how an autonomous system quietly becomes expensive.
"""
from .simulator import AlertSimulator, Reading
from .triage import TriageGate, TriageVerdict

__all__ = ["AlertSimulator", "Reading", "TriageGate", "TriageVerdict"]
