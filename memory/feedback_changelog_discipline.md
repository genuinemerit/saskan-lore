---
name: changelog discipline — log all changes in release design.md
description: Any changes made during a release, including housekeeping and docs, must be noted in the design.md for the active release
type: feedback
---

All changes made while working on a release — including housekeeping clean-ups, minor
refactors, and doc updates — should be recorded in the `design.md` for that release
(e.g. `docs/design/pull_requests/r3_extraction/design.md`).

**Why:** Keeps the design doc as a complete record of what changed and when, not just
the planned deliverables.

**How to apply:** After making any file change (code, docs, config, memory), add a note
to the active release's design.md under a "Changes Made" or "Progress Log" section.
