"""
Continuous alert stream, so the system triggers itself instead of waiting for a command.

  simulator.py  Seeded fleet simulator. Degradation on the machines that are failing,
                noise on the ones that are not.
  triage.py     The wake gate. Scores each reading against the documented severity bands
                and decides whether it is worth waking six agents. Most are not.
  run.py        The loop that joins the two and invokes the graph when triage says so.

The gate is cheap and deterministic on purpose: spending model tokens to decide whether
to spend model tokens is how an autonomous system quietly gets expensive.
"""
from .simulator import AlertSimulator, Reading
from .triage import TriageGate, TriageVerdict

__all__ = ["AlertSimulator", "Reading", "TriageGate", "TriageVerdict"]
