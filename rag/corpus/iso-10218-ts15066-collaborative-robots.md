---
doc_id: iso-10218-ts15066-collaborative-robots
title: "ISO 10218 and ISO/TS 15066: Industrial Robot and Collaborative Operation Safety"
provenance: public-standard-paraphrase
paraphrases: ISO 10218-1, ISO 10218-2, ISO/TS 15066
owner: Titan Manufacturing EHS
revision: 2.0
---

# ISO 10218 and ISO/TS 15066: Robot and Collaborative Operation Safety

> Paraphrase note: a plain-language summary written for retrieval. Not the standard text.
> Cite the published standards for any compliance determination.

## S1 The two parts of ISO 10218

Part 1 sets safety requirements for the robot itself, as built by the manufacturer. Part
2 sets requirements for the integrated robot system and the cell, which is where the
employer duty sits. A robot that is compliant as a product can still be integrated into a
non-compliant cell, so the cell is assessed separately.

## S2 The four collaborative operation modes

ISO/TS 15066 describes four ways a human and a robot may share a workspace:

1. Safety-rated monitored stop. The robot halts when a person enters the collaborative
   workspace and resumes when they leave.
2. Hand guiding. The operator moves the robot directly using a hand-operated device with
   an enabling switch and an emergency stop.
3. Speed and separation monitoring. The robot slows as the person approaches and stops
   before the protective separation distance is violated.
4. Power and force limiting. The robot is designed and controlled so that contact with a
   person cannot exceed defined pain and injury thresholds.

A cell may use more than one mode, but the applicable mode must be unambiguous at any
moment, and the transition between modes must itself be safe.

## S3 Protective separation distance

Under speed and separation monitoring, the minimum protective separation distance is
calculated from the speed of the human, the speed of the robot, the stopping distance of
the robot, the reaction time of the system, and uncertainty in position measurement. The
distance is not a fixed number: it changes as the robot moves and as its speed changes.

If the separation distance is violated, the robot must stop. Restoring the distance is
not sufficient to resume automatically unless the application risk assessment permits it.

## S4 Power and force limiting thresholds

ISO/TS 15066 provides biomechanical limits by body region for transient and quasi-static
contact. The limits are lower for the head and face than for the limbs, and lower for
quasi-static (clamping) contact than for transient contact. A cell relying on power and
force limiting must be validated by measurement against those limits, not by assumption.

## S5 Risk assessment is mandatory and cell-specific

Every collaborative application requires its own risk assessment covering the robot, the
end effector, the workpiece, the fixture, and the task. The end effector and the
workpiece often present the higher hazard: a compliant robot arm carrying a sharp
workpiece is not a safe collaborative application.

## S6 Operator assignment and shift conflicts

Where a cell relies on a safety-rated monitored stop or on speed and separation
monitoring, the assignment of operators to cells is a safety-relevant control, not only a
scheduling matter. One operator assigned to two collaborative cells in the same shift
window can be presumed to be in one cell while the other resumes automatic operation,
which defeats the monitored stop assumption.

A production reroute that creates such a double assignment must be treated as a safety
finding, corrected before the reroute is committed, and recorded.

## S7 Safety shutdowns as a leading indicator

A rising count of safety-rated stops in a cell is a leading indicator of a layout, task
or scheduling problem, not a nuisance to be tuned out. Investigate the cause before
relaxing any protective parameter. Reducing a separation distance or raising a speed
limit to cut shutdown frequency is prohibited without a revised risk assessment and a
safety officer sign-off.
