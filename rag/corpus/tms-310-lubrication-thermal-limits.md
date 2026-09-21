---
doc_id: tms-310-lubrication-thermal-limits
title: "TMS-310: Spindle Lubrication and Thermal Operating Limits"
provenance: internal-synthetic
owner: Titan Manufacturing Reliability Engineering
revision: 3.0
---

# TMS-310: Spindle Lubrication and Thermal Operating Limits

## S1 Thermal limits

Front bearing temperature on a fleet CNC machining centre spindle has three defined
limits:

- Steady-state working range: 45 C to 60 C at rated speed after a 20 minute warm-up.
- Alarm limit: 75 C. Above this the lubricant film thins and bearing life falls sharply.
- Maximum permissible: 85 C. Above this the spindle must be stopped. Continued operation
  above 85 C will carbonise the grease and destroy the bearing within hours.

Bearing life is approximately halved for every 15 C rise above the steady-state working
range. A spindle that has spent 40 hours at 78 C has consumed a meaningful fraction of
its remaining life even if vibration has not yet risen.

## S2 The temperature-to-vibration lag

Temperature is a lagging indicator relative to vibration for bearing defects. A spalled
raceway produces a measurable vibration rise before it produces a measurable temperature
rise, because the defect first changes the dynamics and only later changes the friction.
The practical consequence is that a machine showing critical vibration and normal
temperature is still a critical machine. Do not treat a normal bearing temperature as
evidence against a bearing defect.

The reverse pattern, rising temperature with flat vibration, usually points at a
lubrication problem rather than a mechanical defect: a blocked grease line, a failed
lubricant pump, or the wrong grease grade.

## S3 Lubrication intervals

Grease-for-life sealed bearing units are not re-lubricated in service and are replaced as
a unit. Oil-air lubricated spindles are serviced on a 2000 operating hour interval, or
every 12 months, whichever comes first. The interval halves for spindles that routinely
operate above 80 percent of rated speed.

An over-greased bearing runs hotter than a correctly greased one. Adding grease to a
spindle that is already running warm is a common and damaging error.

## S4 Warm-up requirement

A cold spindle must be run through the published warm-up cycle before being taken to
rated speed. Vibration and temperature readings taken during warm-up are not valid for
condition assessment and must be excluded from any life estimate. Telemetry captured in
the first 20 minutes after a cold start is discarded by the condition monitoring pipeline
for this reason.

## S5 Coolant interaction

Coolant flow below nominal raises bulk machine temperature and can raise bearing
temperature indirectly, without any bearing defect being present. Before attributing a
temperature rise to the bearing, confirm that coolant flow is within nominal range. A
coolant flow alert and a bearing temperature alert on the same machine in the same window
are more likely to be one fault than two.
