# Approval Note Workflow (Illustrative Reference)

> Illustrative reference material written for the UrjaKavach prototype.

## Purpose

An Approval Note converts inspection findings into a formal record that
routes to the responsible engineer for sign-off.

## Required Sections

1. **Header** — source document reference, generation date, task ID.
2. **Key Findings** — one line per distinct finding, preserving equipment
   tags and numeric readings exactly as recorded by the inspector.
3. **Severity Summary** — highest severity present across all findings.
4. **Recommendation** — the action proposed by the inspecting engineer.
5. **Sign-off block** — left blank for the responsible engineer.

## Routing Rules

- Notes containing any **Critical** finding route to the Unit Head and the
  Safety Officer simultaneously.
- Notes with **Major** findings route to the Maintenance Planner within
  24 hours of generation.
- Notes containing only **Observation** and **Minor** findings are batched
  into the weekly maintenance planning review.

## Mandatory Disclaimer

Every automatically drafted note must carry a line stating that the note
was machine-drafted from a scanned source and requires human verification
before formal sign-off. Automated drafting never replaces engineer
judgement.

## Data Handling

Approval notes may contain confidential process data. They are generated,
stored and circulated entirely within the plant's internal network. No
content may be transmitted to any external or cloud-hosted service.
