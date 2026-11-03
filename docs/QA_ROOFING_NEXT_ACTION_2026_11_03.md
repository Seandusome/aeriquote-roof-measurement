# Roofing next-action usability — November 3, 2026

Resumed checkpoint68b612f6 on landscaping-multi-area-recovery-oct11. Application source for this batch: f8c3d20a28aa51a33037e15ac09da11794e8ca00; app.py blob982a6e705057595fba0ff7e8bf490482759452e9. NOT DEPLOYED. Live recovery remains efb2d29ba72306ef718c62f1de86070af1e33ef7 / dep-dbl3b5gae00c73cfdh50. Auto-deploy OFF. Isolated QA binding unchanged (dpg-dbj4f7lg1s2s73eob8t0-a / aeriquote_recovery_qa). No main, production, customer data, database connection, imagery integration, allowance or pricing-policy changes.

## What changed

Manual Roofing now has one stage-specific explanation and visually emphasizes the existing next action:

1. Before a property is loaded: LOAD PROPERTY & TRACE ROOF; the guidance explains how to begin. If the first empty trace was cancelled, TRACE FIRST ROOF is the next action.
2. While tracing: guidance says to click roof corners. Pitch selection sits beside SAVE ROOF SECTION / SAVE SECTION CHANGES, with Cancel/Undo/Start Over secondary. After at least three corners, the next action is selecting an actual pitch; once selected, Save becomes the emphasized action. Default5/12 is never silently confirmed.
3. Saved sections retain their area and rise/run pitch with Edit/Delete. The existing explicit Confirm pitches and included roofs action appears only when saved sections exist and drawing/editing has finished.
4. After confirmation: a compact confirmed state remains, and guidance points to missing pricing, customer name, or Create. Progress chips follow the same current stage. Load/Create are visually secondary until they are the next action.

Duplicate instruction blocks, premature confirmation warnings, duplicate manual-section/property/dealer summaries, and the drawing banner are hidden only in the guided manual path. The current validation explanation remains in the next-action panel; critical non-routine failure messages are retained. Older Roofing snapshots containing legacy structures retain their existing summary and repair path, so the new presentation does not hide their priced measurements. Other five industries and customer/PDF layouts are unchanged.

Validation functions, explicit per-section pitch flags, final scope confirmation, geometry checks, quote pricing checks, server recalculation, Save/Cancel, operation IDs, drafts, stale protection, and allowance behavior were preserved. No Mapbox work or PDF redesign.

## Passed checks

- Manual Roofing Python policy/integrity regression: opt-in isolation, zero Solar calls, retry behavior, explicit pitch/multiple pitches, shared edges/garages, overlap/invalid/unconfirmed rejection, actual save/reopen.
- DOM/Leaflet regression: blank pitch cannot save; edit/save/Cancel/delete; confirmation invalidation; Cancel preserves exact geometry and pitch; individual controls re-enable; snapshot/zoom invariance; both exporter save entry points; legacy structures retain original summary path.
- Six-industry pricing validation regression: blank/negative/non-finite rates, taxes, discounts, extras, explicit zero, and actual save/report blocking unchanged.
- Focused actual Chromium desktop1440: property load, trace, blank-pitch Save rejection, explicit5/12, save, confirmation gating, price/customer next steps, edit/Cancel, edit pitch to9/12 and back, add0/12 section, add/delete12/12 section, reconfirm, save, history reopen/reconfirm, and Single/Expanded downloads. No uncaught JS errors or horizontal overflow. Reopened stored snapshot stays unchanged by review/export.
- Final desktop Single1page and Expanded2pages rendered and visually inspected. Both priced sections present with intended pitches, customer text and totals. Independent WGS84 + Decimal verification PASS: 1360.321795525055ft² ×0.27 →367.29; GST18.36; additional tax22.04; totalCAD407.69. WGS840.6% tolerance is existing spherical/geodesic comparison, not survey accuracy.
- Existing three-section real Chromium export check passed: explicit5/12,0/12 and12/12, adjacent facets plus garage, Cancel, save/reopen, both layouts; independent totalCAD253.89. Its visible-warning assertion now reads the new next-action panel and still asserts visible confirmation plus disabled estimate creation; no coverage weakened.
- Phone-sized390 UI passed tracing, saving sections, pitch/confirmation visibility, edit/Cancel and adding/deleting through the Create stage. This is browser width evidence, not physical-phone testing.

## Open blocker: safe save rejection at a half-cent tax boundary

The390-width focused scenario reproducibly reaches the server with subtotal367.30, GST18.36 and total407.70. Independent Decimal calculation requires GST18.37 and total407.71. The server correctly rejects it (`Estimate gstAmt does not match independently calculated measurements, rates and taxes`), preserves work and acknowledges its recovery draft. This is a real existing browser arithmetic edge, not a usability fixture visibility issue. priceCalc is byte-identical to checkpoint68b612f6 (proof in rounding-blocker.json); JS rounding at367.30×5% falls below the half-cent boundary.

No pricing code was changed, no assertion was relaxed and the failing fixture was not changed to dodge this edge. Phone save/reopen/PDF completion is therefore FAILED/BLOCKED for this case. Desktop verification above passed. This issue must be fixed in a separately authorized pricing batch before calling the branch launch-ready or deploying this work. Required CI outcomes below must be read with this unresolved failure; do not claim all required checks passed.

## Evidence

`docs/qa/roofing-next-action-2026-11-03/` contains original before screenshots, final desktop stage screenshots/state/save requests/PDFs, phone stage screenshots/failed request, logs, independently verified PDF renders, and unchanged-pricing proof. `before-after-drawing.jpg` compares the same drawing stage. Before captures were taken from the unchanged preceding application; that exploratory before run later stopped on an out-of-viewport synthetic corner. Final fixture recenters each added roof and retains every-click-recorded assertions. A report-readiness wait was added before comparing reopened customer/snapshot content. These fixture corrections do not change application behavior or safeguards.

Local execution uses the existing loopback-only fictional provider and normal Basic allowance fixture. Python dependencies from requirements; Playwright1.56.1, Leaflet, html2canvas, jsPDF and jsdom isolated under/tmp. No live business job or account was edited in this usability batch. Existing two untracked PDF copies preserved.

## CI status

All final-source workflows completed on f8c3d20a28aa51a33037e15ac09da11794e8ca00:

| Workflow | Run | Result |
|---|---|---|
| Validate AeriQuote application |41723463942|PASS|
| Validate landscaping recovery |41723463840|PASS recovery plus PostgreSQL16/18, including backup/previous-version drill|
| Isolated browser crash/recovery |41723463808|FAIL:9/10 jobs passed; roof-exports failed only on the new390-width rounding case|

The exact failing job126221985977 logs confirm the original three-section Single/Expanded test passed, the new desktop usability/PDF path passed, and the new phone case was safely rejected on gstAmt. Every other browser job passed: baseline, recovery, public, drafts, job-revisions, fresh-user, draft-races, pdf-failure and property-failure. No required workflow remains running. No assertion was weakened and no failing fixture was changed to bypass the defect. No deployment occurred. CI summary and selected failure log are saved beside evidence.

Earlier source2aeb1ae/4555327 runs are superseded by this final source; the first browser attempt also found the moved warning assertion, corrected to the visible panel without weakening validation.

## Next session — pause for visual review

Review the before/after captures before further layout changes. Separately authorize a focused half-cent currency-rounding correction, preserving independent server validation, and retest the exact367.30/5% failure plus pricing regressions. Then complete the blocked phone-width save/reopen/both-PDF path and required workflows. Do not deploy this batch. Owner desktop review and physical-phone testing remain pending. Pause for Sean's instruction.

## Later follow-up — rounding blocker resolved

Source194c435b fixes the half-cent discrepancy using decimal ROUND_HALF_UP while preserving strict server validation and this Roofing usability work. Desktop/phone save/reopen and both PDFs now pass; required application/recovery/PG16/18 and browser10/10 workflows all pass. Live remains efb2d29b, undeployed. See [tax-rounding correction](QA_TAX_ROUNDING_2026_11_03.md). Earlier failure details remain the original regression evidence.
