---
doc_id: iatf-16949-traceability-records
title: "IATF 16949: Traceability, Records and Nonconforming Product Control"
provenance: public-standard-paraphrase
paraphrases: IATF 16949:2016 clauses on traceability, control of records, and nonconforming output
owner: Titan Manufacturing Quality
revision: 1.6
---

# IATF 16949: Traceability, Records and Nonconforming Product Control

> Paraphrase note: a plain-language summary written for retrieval. Not the standard text.
> Cite the published standard and the customer-specific requirements for any compliance
> determination.

## S1 Why traceability exists

Traceability exists so that when a defect is found, the organisation can determine
precisely which product is affected and contain it. The test of a traceability system is
not whether records exist: it is whether the organisation can define the suspect
population quickly and defend that definition to the customer.

## S2 What must be traceable

The traceability plan must let the organisation identify, for any piece of product: the
manufacturing date and time, the process and equipment used, the operators involved, the
incoming material lots consumed, and the results of any inspection or test. Where
customer-specific requirements impose a narrower definition of a batch, the narrower
definition applies.

## S3 Linking machine data to quality records

A quality record that cannot be linked back to the machine condition at the time of
manufacture cannot support a root cause investigation. Where condition monitoring data
exists for a machine, the quality record must reference the time window so the two can be
joined later. Separating MES and QMS records from OT telemetry is the most common reason
a root cause investigation takes weeks instead of hours.

## S4 Suspect population when a machine fault is confirmed

When a machine fault is confirmed and correlated with a rise in defect rate, the suspect
population is defined as all product manufactured on that machine from the earliest point
at which the fault signature is detectable in the telemetry, not from the point at which
the alarm fired. The two are usually different, and the earlier bound is the defensible
one.

Containment is applied to the whole suspect population until inspection narrows it.

## S5 Control of nonconforming output

Nonconforming product must be identified and controlled to prevent unintended use or
delivery. Rework and repair are distinct: rework returns the product to specification,
repair makes it acceptable for use without meeting the original specification and
requires customer concession. Both require a documented instruction that has been
authorised, and both require records.

Releasing product for delivery under a concession requires the customer authorisation on
file before shipment.

## S6 Record retention

Production part approval records, tooling records, product and process design records are
retained for the length of time the product is active for production and service, plus
one calendar year, unless the customer or a regulator requires longer. Internal audit and
management review records are retained for a minimum of three years.

## S7 Records for an emergency maintenance intervention

An emergency maintenance intervention on a production machine produces quality-relevant
records as well as maintenance records: the last good part before the intervention, the
first article after it, the requalification result, and the disposition of any product
made in the suspect window. An intervention is not closed until those records exist.
