---
doc_id: tms-610-production-reroute-and-shift-rules
title: "TMS-610: Production Reroute and Shift Coverage Rules"
provenance: internal-synthetic
owner: Titan Manufacturing Plant Operations
revision: 3.4
---

# TMS-610: Production Reroute and Shift Coverage Rules

## S1 When a reroute is required

Jobs are rerouted off a machine when the machine is taken out of production for an
emergency window, when it is running under a speed reduction that puts the job outside
its cycle time commitment, or when a quality containment prevents further production on
it.

A reroute is a production decision with safety, quality and staffing consequences. It is
not complete until all three have been checked.

## S2 Target machine eligibility

A target machine is eligible only if all of the following hold:

1. It is listed as an equivalent machine in the asset profile of the source machine.
2. It has enough uncommitted capacity in the window to absorb the jobs without displacing
   another committed job.
3. It is not itself in the Warning, Critical or Trip severity band.
4. Its recent quality performance is within the baseline escape rate.

A machine that is merely idle is not automatically eligible. Idleness often means it is
reserved, in changeover, or itself under observation.

## S3 Quality safety of the target

Loading a target machine above its normal duty raises its own escape risk. Before a
reroute is committed, the target machine recent escape rate is compared against the site
baseline. A target already running above baseline is rejected, and the reroute is
re-planned. The check applies to each target separately, not to the pair as a group.

## S4 Operator and shift conflicts

Each rerouted job carries an operator requirement. The shift roster is checked for the
full window of the reroute, not only its start. A conflict exists when an operator or a
certified technician is assigned to two positions whose time windows overlap, or when a
reroute leaves a cell without its required certified coverage.

A conflict involving a collaborative robot cell is a safety finding as well as a
scheduling one, and is handled under `iso-10218-ts15066-collaborative-robots`.

## S5 Resolution order for a conflict

When a conflict is found, resolve it in this order:

1. Move the job to an alternative eligible machine.
2. Move the job to an adjacent shift inside the window.
3. Assign relief coverage from the plant relief pool.
4. Escalate to the shift supervisor to re-plan.

Splitting an operator across the conflicting positions is never an acceptable resolution.

## S6 Recording the reroute

The committed reroute records: each job, the source and target machine, the window, the
assigned operator, the checks performed with their results, and the person who approved
it. The record is the input to the quality traceability chain for every part produced
under the reroute.
