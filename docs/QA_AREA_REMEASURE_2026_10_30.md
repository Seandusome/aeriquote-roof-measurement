# Surface Area replacement — October 30, 2026

Base cd1c7e781c7c6969958c82992f2588ee9ec51729 on landscaping-multi-area-recovery-oct11. Baseline GitHub application/recovery checks and disposable PostgreSQL passed; Render exact commit LIVE. No main, production or real account changes.

REMEASURE AREA is now the primary action on each saved area across Snow Removal, Pressure Washing, Paving & Sealcoating, Landscaping and Commercial Properties. EDIT OUTLINE remains secondary. A replacement draft retains the saved record and its visible original boundary. The new outline can receive ordered taps; existing corner correction still ignores accidental background taps. Save explicitly says SAVE REPLACEMENT AREA. It validates self-intersection, quantity consistency and overlap against the other saved areas before committing. Invalid drafts do not overwrite records. Start Over only clears the draft; Cancel restores the original. Other areas, saved Linear geometry/rate and customer fields remain unchanged. Fields/delete actions cannot mutate saved areas while replacing. Map/touch locks remain active through repeated cycles and restore normal map dragging afterwards.

No server persistence, measurement formula, subscription accounting, imagery request, Roofing workflow or PDF design changed. This is in-memory job safety, not crash recovery/autosave. Existing saved estimates are unchanged until the contractor explicitly creates an updated version. Provider geometry/pricing/server guards remain authoritative.

Verification:
- Full 72-command recovery regression passed after changes. Initial stale test assumptions about button positions and the minimal VM's new state were updated to explicit action selectors/state; actual DOM and browser tests exercise the real initialization.
- Expanded DOM surface regression covers both areas repeatedly, crossing/duplicate overlap drafts, unchanged prices before Save, Cancel, valid replacement, other area/line/customer preservation, and restored map dragging across all five industries.
- Actual local Chromium141 at320/390/768px with hasTouch/isMobile and trusted CDP touch/pointer events: 15 industry/width combinations passed. Repeated Area1/Area2 replacement/Cancel, self-crossing rejection, valid explicit Save, secondary editor, repeated Linear drag/Cancel, stationary map, saved geometry and price sent to real Flask endpoints, then historical reopening all passed.
- Disposable SQLite accounts, synthetic labelled imagery, only loopback server; all unexpected external providers blocked. Not physical devices, live imagery or deployed customer accounts.
- Existing full-suite geometry/server-pricing, account/business isolation, allowance, Single/Expanded and QA Vector guards passed. Browser screenshots inspected; no PDF design or imagery edits.

Reproduce: PATH=<venv>/bin:$PATH NODE_PATH=<deps>/node_modules python scripts/run_linear_touch_qa.py scripts/test_surface_remeasure_touch.cjs. Dependencies match existing isolated touch harness. Machine evidence docs/qa/area-remeasure-2026-10-30.json. Actual iPhone Safari retest remains required. Keep manual Roofing safeguards and AI Trace removal.
