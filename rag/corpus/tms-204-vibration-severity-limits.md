---
doc_id: tms-204-vibration-severity-limits
title: "TMS-204: Vibration Severity Assessment (ISO 10816-3 aligned)"
provenance: public-standard-paraphrase
paraphrases: ISO 10816-3 / ISO 20816-3 machine vibration evaluation
owner: Titan Manufacturing Reliability Engineering
revision: 2.1
---

# TMS-204: Vibration Severity Assessment

> Paraphrase note: this document summarises the evaluation approach of ISO 10816-3 and its
> successor ISO 20816-3 in plain language, for retrieval. It is not the standard text.
> Compliance decisions must cite the published standard.

## S1 What the standard measures

The ISO approach evaluates machine health from broadband vibration velocity in mm/s RMS,
measured on the bearing housing or another non-rotating structural part of the machine.
It deliberately uses a single broadband number rather than a spectrum, so a machine can
be classified quickly without a specialist reading an FFT.

Velocity is used rather than displacement or acceleration because velocity is roughly
proportional to vibration energy across the frequency band where most rotating-machine
faults appear, which is about 10 Hz to 1000 Hz.

## S2 Machine groups and mounting

Classification depends on two things: the size and power class of the machine, and
whether it is rigidly or flexibly mounted. A large machine on a flexible foundation
tolerates more vibration than a small rigidly mounted one before the same evaluation zone
is reached. A CNC machining centre spindle assembly is evaluated as a small to medium
machine on a rigid foundation, which is the most conservative grouping.

## S3 Evaluation zones

Four zones are defined:

- Zone A: newly commissioned machines. Vibration is at or near the as-built level.
- Zone B: acceptable for unrestricted long-term operation.
- Zone C: unsatisfactory for long-term continuous operation. The machine may be run for a
  limited period while a corrective intervention is arranged.
- Zone D: severe. Vibration at this level is capable of causing damage to the machine.

The practical reading of the zones is that the A/B boundary is a commissioning acceptance
criterion, the B/C boundary is the alarm threshold, and the C/D boundary is the trip
threshold. For a rigidly mounted small machine those boundaries fall at approximately
1.4, 2.8, 4.5 and 7.1 mm/s RMS, and shift upward for larger or flexibly mounted machines.

## S4 Change is more diagnostic than absolute level

The standard is explicit that a change in vibration level from an established baseline is
more significant than the absolute level itself. A rise by a factor of two from a stable
baseline warrants investigation even when the absolute reading is still inside Zone B.
Conversely, a machine that has run stably in Zone C for years is not in the same
condition as a machine that reached Zone C last Tuesday.

This is why the Titan fleet standard TMS-101 estimates remaining life from the rate of
change rather than from the absolute value.

## S5 Limitations

A broadband velocity reading cannot identify a failure mode. It tells you that something
is wrong and roughly how urgent it is. Identifying whether the source is a bearing defect,
an imbalance, a misalignment, or a looseness condition requires spectral analysis,
envelope demodulation, or another diagnostic technique. Do not present a broadband
severity classification as a root cause diagnosis.
