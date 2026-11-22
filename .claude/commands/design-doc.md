---
description: Write a design doc for a change and stop for human approval before any code.
argument-hint: <what to change>
---

Write a design document for: $ARGUMENTS

No code changes until the human approves the document. Read `AGENTS.md`, the code the change
touches and `docs/design/` (if it exists) first, so the design fits what exists.

Save it as `docs/design/NNNN-<slug>.md` (next free number, starting at `0001`) with these sections, in English, short
and specific (numbers, file names, dates instead of adjectives):

1. **Goal and context**: what changes and why; the problem in one paragraph.
2. **Scope**: what is in, what is out.
3. **Proposed change**: files, behaviour, data and API changes; migrations if any.
4. **Alternatives and decisions**: a table of decision / choice / rejected / why.
5. **Risks and costs**: what can go wrong and the mitigation for each.
6. **Rollout plan and acceptance criteria**: steps (one PR each where possible) and a checklist
   that proves the change works.
7. **Open questions**: each with your recommendation.

Then stop and ask the human to approve, change or reject it. If the implementation later departs
from the approved design, update the document in the same PR and say so.
