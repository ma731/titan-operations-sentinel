---
doc_id: tms-705-telemetry-data-quality-and-abstention
title: "TMS-705: Telemetry Data Quality, Alert Triage and Abstention Rules"
provenance: internal-synthetic
owner: Titan Manufacturing Reliability Engineering
revision: 2.2
---

# TMS-705: Telemetry Data Quality, Alert Triage and Abstention Rules

## S1 The alert noise problem

A Titan plant generates tens of thousands of condition and process alerts per day. The
overwhelming majority are informational or are duplicates of a single underlying event
seen by several systems. Triage exists to reduce that stream to the small number of
genuinely actionable events, and its output is what a human or an agent should act on.

Triage is a ranking problem, not a filtering problem. An alert that is deprioritised is
still recorded and still trended. It is not discarded.

## S2 Deduplication and correlation

Alerts are deduplicated on machine, sensor and event window, then correlated across
sensors on the same machine. Several sensors crossing thresholds on one machine inside a
short window are one event, not several. Correlated events are ranked above isolated ones
at the same severity, because correlation across independent sensors is strong evidence
that the reading is real rather than a sensor fault.

## S3 Priority scoring

The priority score combines: how far the reading is beyond its threshold, the direction
and rate of the trend, whether the signature matches a known historical failure on the
same asset class, and the production value at risk on that machine. A stable reading
slightly below nominal scores low even when it is technically an exception. A rising
reading that matches a prior failure signature scores high.

## S4 Data quality requirements for a life estimate

A remaining-life estimate may only be produced from telemetry meeting all of these
conditions:

1. At least 4 hours of continuous samples in the assessment window.
2. No gap longer than 10 minutes inside that window.
3. Samples excluded from the first 20 minutes after a cold start, per `tms-310-lubrication-thermal-limits`.
4. At least two independent sensors reporting, so a single sensor fault cannot drive the
   estimate on its own.

## S5 The abstention rule

Where the data quality requirements are not met, the correct output is an explicit
abstention, not a low-confidence estimate. The assessment states what is missing, what it
would take to produce a valid estimate, and routes the case to a human for manual
inspection.

This is a deliberate design choice. A confident-sounding estimate produced from a
telemetry dropout is worse than no estimate, because it will be acted on. Abstention is a
correct answer and is recorded as such, not as a failure of the system.

## S6 Sensor fault versus machine fault

A reading that goes to zero, saturates at a rail value, flatlines exactly, or disappears
entirely is a suspected sensor or acquisition fault until proven otherwise. A genuine
mechanical fault almost never produces a perfectly clean signal loss. Sensor faults are
raised as maintenance cases against the instrumentation, not as machine condition
findings.

## S7 What to do while abstaining

Abstaining from a life estimate does not mean doing nothing. The machine stays under the
severity band implied by the last valid reading, any protective measure already applied
stays applied, the alert stays open, and the case is re-run automatically once a clean
window exists.
