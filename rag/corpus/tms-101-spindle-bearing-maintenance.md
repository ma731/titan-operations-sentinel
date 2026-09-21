---
doc_id: tms-101-spindle-bearing-maintenance
title: "TMS-101: Spindle Bearing Condition Monitoring and Replacement"
provenance: internal-synthetic
owner: Titan Manufacturing Reliability Engineering
applies_to: cnc_machining_center
revision: 4.2
effective: 2026-01-15
---

# TMS-101: Spindle Bearing Condition Monitoring and Replacement

## S1 Scope and purpose

This standard covers condition monitoring, life estimation, and replacement of
angular-contact spindle bearings on CNC machining centres in the Titan fleet. It applies
to all machining centres of asset class `cnc_machining_center` regardless of plant. It
does not cover linear guideway bearings, ballscrew support bearings, or rotary table
bearings, which are covered by TMS-118.

The purpose of the standard is to convert raw vibration and temperature telemetry into a
defensible remaining-useful-life estimate, and to define who may authorise a spindle
intervention at each severity level.

## S2 Monitored parameters

Three signals are monitored continuously on every spindle:

1. Broadband vibration velocity, measured in mm/s RMS at the front bearing housing in the
   radial direction, sampled at 1 Hz and averaged over 60 seconds.
2. Front bearing temperature, measured in degrees Celsius by an embedded RTD, sampled at
   0.2 Hz.
3. Spindle motor current, measured in amperes RMS, used as a load-normalisation signal so
   that a vibration rise under a heavier cut is not mistaken for a defect.

Vibration is the primary indicator. Temperature confirms. Current disambiguates. A
vibration rise with flat current and rising temperature is a mechanical defect signature.
A vibration rise that tracks current is usually a process effect (deeper cut, harder
material, worn tool) and is not a bearing finding.

## S3 Severity bands and required response

| Band | Vibration (mm/s RMS) | Front bearing temp | Required response |
|---|---|---|---|
| Normal | below 3.5 | below 60 C | No action. Routine trending only. |
| Elevated | 3.5 to 5.0 | 60 to 65 C | Increase sampling. Review at next planning meeting. |
| Warning | 5.0 to 6.0 | 65 to 75 C | Raise a maintenance case. Plan an intervention inside 14 days. |
| Critical | above 6.0 | above 75 C | Raise an emergency case. Reduce spindle speed to the OEM safe limit. Plan an intervention inside the predicted failure window. |
| Trip | above 11.0 | above 85 C | Stop the spindle. Do not restart without a reliability engineer sign-off. |

A machine sits in the highest band that any single parameter reaches. Bands are not
averaged.

## S4 Remaining useful life estimation

Once a spindle enters the Critical band, the remaining useful life is estimated from the
rate of change of vibration rather than from its absolute value. The fleet rule of thumb,
derived from 41 historical spindle bearing failures across the Titan fleet, is:

- A doubling of vibration velocity over 6 hours or less indicates a failure window of
  roughly 40 to 80 operating hours.
- A doubling over 24 to 72 hours indicates a window of roughly 100 to 200 operating hours.
- A slow drift of less than 20 percent per week indicates a window of more than 500 hours
  and should be handled as planned maintenance, not as an emergency.

These figures are estimates with wide intervals. Report a range, never a point estimate,
and always report the confidence alongside it. A life estimate produced from fewer than
4 hours of continuous clean telemetry is not valid and must be reported as low confidence.

## S5 Speed reduction as a life extension measure

Reducing spindle speed to the OEM safe reduced-speed limit lowers the dynamic load on the
bearing and typically extends the remaining window by 15 to 20 operating hours on a
machine already in the Critical band. Speed reduction inside the OEM published envelope
is a routine operational change. It requires no safety sign-off and may be applied
automatically. Reducing speed does not reset the severity band and does not cancel the
requirement to intervene.

Speed reduction beyond the OEM published envelope, or any change to the spindle drive
parameter set, is not covered by this standard and requires OEM engineering approval.

## S6 Replacement procedure summary

A spindle bearing replacement is a 6 hour job requiring two technicians: one spindle
specialist and one hydraulics-certified technician. The machine must be isolated under
the lockout/tagout procedure (see `osha-1910-147-loto`) before the spindle nose is opened.

Parts required for a standard angular-contact replacement are a matched bearing pair kit
and a hydraulic seal set for the spindle nose and drawbar. Bearings are supplied as a
matched pair and must never be mixed between kits. A spindle rebuilt with mismatched
bearings will fail again inside 200 hours.

## S7 Records

Every spindle intervention produces: the telemetry window that triggered it, the life
estimate and its confidence, the parts consumed with lot numbers, the lockout/tagout
reference, the names of the technicians present, and the approver of any expedited
spend. These records are retained per `iatf-16949-traceability-records`.
