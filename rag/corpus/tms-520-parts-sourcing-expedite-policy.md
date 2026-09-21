---
doc_id: tms-520-parts-sourcing-expedite-policy
title: "TMS-520: Parts Sourcing, Expedite and Cross-Plant Transfer Policy"
provenance: internal-synthetic
owner: Titan Manufacturing Supply Chain
revision: 5.1
---

# TMS-520: Parts Sourcing, Expedite and Cross-Plant Transfer Policy

## S1 Sourcing order of preference

For a critical spare needed inside a predicted failure window, sources are considered in
this order:

1. On-site stock at the affected plant.
2. Regional warehouse stock serving the affected plant.
3. Cross-plant transfer from a sister plant holding the part.
4. Expedited supply from the Tier-1 supplier.
5. Expedited supply from an approved alternate supplier.

The order reflects cost and certainty, not just cost. A cross-plant transfer that arrives
inside the window is preferred over a cheaper supplier order that does not, and an option
that does not fit the failure window is not a valid option however cheap it is.

## S2 The fit-to-window test

Every sourcing option is tested against the lower bound of the predicted failure window,
not the upper bound. An option whose lead time exceeds the lower bound is marked as not
fitting, and is ranked below every option that fits, regardless of ROI.

Costing the benefit against the lower bound is deliberate: it produces the most
conservative return figure and it avoids recommending an option that only works if the
machine survives to the optimistic end of its predicted life.

## S3 Return on investment calculation

The benefit of an expedite is the downtime avoided, calculated as the hours between the
option arrival time and the lower bound of the failure window, multiplied by the hourly
production value of the machine. The cost is the incremental cost of the expedite over
the standard option, plus any premium labour it triggers.

The resulting ratio is a decision aid, not an authorisation. A high ratio does not remove
the approval requirement.

## S4 Autonomous spend ceiling

Commitments at or below the autonomous ceiling of 500 EUR may be made without a specific
human approval, provided the option also passes the fit-to-window test. Every commitment
above the ceiling requires named human approval recorded before the commitment.

A commitment may not be split into several sub-ceiling commitments to avoid the approval.
Splitting is assessed on the total value of the intervention, not on the individual
purchase order.

## S5 Tier-2 exposure

A Tier-1 supplier quote is not a complete risk picture. Before recommending a source, the
Tier-2 dependency behind it is checked. Two Tier-1 options that both depend on the same
Tier-2 raw material supplier are one option, not two, and must be reported as such.

Where Tier-2 exposure is rated high, the recommendation includes a fallback source even
when the primary option is expected to deliver.

## S6 Cross-plant transfer mechanics

A cross-plant transfer is an internal stock movement, not a purchase. It is valued at
standard cost plus the actual freight, which is typically several hundred euros within
Europe. The sending plant must confirm the transfer does not drop its own cover below its
reorder point for the part. A transfer that creates a stockout at the sending plant has
moved the risk rather than removed it.

Transfers of safety-critical spares require the receiving plant to verify the part
certification and lot documentation on arrival, before installation.

## S7 Supply disruption handling

When the primary supply route is disrupted, the assessment does not stop at reporting the
disruption. It re-runs the sourcing order of preference under the disrupted assumption
and reports the best option that still fits the window, together with what it costs and
what it risks. Reporting that nothing is available without testing cross-plant transfer
is an incomplete assessment.
