---
doc_id: rolling-element-bearing-failure-modes
title: "Rolling Element Bearing Failure Modes: Diagnostic Reference"
provenance: internal-synthetic
owner: Titan Manufacturing Reliability Engineering
revision: 1.8
---

# Rolling Element Bearing Failure Modes: Diagnostic Reference

## S1 Why failure mode matters

The remaining life of a degrading bearing depends far more on the failure mode than on
the severity reading. A subsurface fatigue spall progresses over tens to hundreds of
hours and is predictable. A lubrication failure or a passage of electrical current can
destroy a bearing in a single shift. Reporting a life estimate without naming the
suspected failure mode leaves the reader unable to judge how much to trust the number.

## S2 Subsurface fatigue (spalling)

The classic end-of-life mode. Repeated rolling contact initiates a crack below the
raceway surface which propagates and breaks out as a spall. Signature: a gradual,
monotonic vibration rise over days to weeks, with characteristic defect frequencies
appearing in the envelope spectrum, and a temperature rise that lags the vibration.
Progression is relatively predictable, which is why fleet life estimates are calibrated
against this mode.

## S3 Lubrication failure

Loss of the elastohydrodynamic film through wrong grade, contamination, over-greasing,
starvation, or overheating. Signature: temperature rises first and fastest, vibration
follows, and the rise is steep rather than gradual. Progression to seizure can be a
matter of hours. A temperature-led signature must never be assigned the fatigue-mode life
estimate.

## S4 Contamination and abrasive wear

Hard particle ingress through a failed seal. Signature: a broadband noise floor rise
rather than discrete defect frequencies, and often a step change coinciding with a seal
or coolant event. Progression is variable. Replacing the bearing without replacing the
seal guarantees a repeat.

## S5 Electrical discharge damage

Current passing through the bearing, typically from a variable frequency drive without an
adequate shaft grounding path. Signature: fluting on the raceway, a distinctive
high-frequency acoustic signature, and often a repeat failure at similar intervals after
each replacement. The fix is the grounding path, not the bearing.

## S6 Misalignment and preload error

Installation-induced. Signature: elevated vibration at shaft-speed harmonics from the
first hours of operation, with an unusually flat trend afterwards, and a temperature that
is high but stable. A bearing that ran warm from day one was installed wrong. It will
fail early, but not suddenly.

## S7 Reading the signature before estimating life

The diagnostic order is: establish the trend shape (gradual, steep, or step), establish
which parameter led (vibration or temperature), then assign the likely mode, then apply
the life model for that mode. Applying a fatigue life model to a lubrication-led
signature produces a dangerous overestimate of remaining life.

## S8 Repeat failure as evidence

A bearing that fails a second time at a similar interval after replacement is evidence of
an uncorrected root cause in the system around the bearing: electrical, alignment,
lubrication supply, or loading. Recording the interval between replacements is therefore
part of the maintenance record, and a repeat interval is a reason to escalate to a
reliability engineer rather than to schedule another replacement.
