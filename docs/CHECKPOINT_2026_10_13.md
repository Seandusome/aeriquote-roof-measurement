# October 13 5:29 PM verified manual Roofing checkpoint

Application baseline: ad9a9e459d0c699ef2a253eb99a445ef75c11ed4. Both GitHub workflows passed.
Manual Roofing fresh PDF21 and reopened PDF22 PASSED:1715 2nd Ave North,1,137ft²,1roof,pitch22.6°,edges46.3/21.3/23.0/48.3ft,subtotalCAD5,400.24,GST270.01,PST324.01,totalCAD5,994.27. Every edge/pitch label and outline align in both PDFs. Do not repeat this test without reason.
Edit Line fresh/reopened PDFs46/47 also passed (one line only,551.6ft@.70,CAD386.10). Sean says prior Commercial combined/customer tests already completed; do not repeat them unnecessarily.
Next pending coverage: exact dropped-pin roof report path; Roofing pitch changes/corrections as needed; account/employee permissions and quotas; final launch regression. Payments remain deferred. No new app failure from latest PDF22.

---

# October 13 manual-Roofing PDF follow-up

- Edit Line live confirmed by Sean. Pressure Washing one-line PDFs46/47 (fresh/reopened): 551.6 ft @ .70, total CAD386.10, both segment labels retained. User explicitly drew only one line; no area-loss bug. Reopened labels round individual segments differently, but saved length/rate/total unchanged.
- Isolated engine CI failed after Edit Line because fixture omitted linearCorrectionOriginal. Fixed fixture in3c89963; GitHub recovery workflow passed. Application code unchanged by that fix.
- Commercial combined/customer tests already performed per Sean; do not request repeating them without reason.
- Roofing/Pressure Washing confusion: user thought Roofing selected, copied UI showed Pressure Washing, new-property line0.0ft so old geometry did not carry. No proven industry reset; no change made. Choose Roofing and confirm heading before loading.
- Manual Roofing PDF20:1,111ft², base5,278.00, GST263.90, PST316.68, CAD5,858.58. Orange outline present, feet/pitch labels absent. Root cause: manual-report static image path baked outline but did not draw labels.
- Fix: manual-map response exposes exact center/zoom/size; manual snapshot draws saved edge/pitch labels on its static canvas using that view and approved report outlines. Geometry/pricing unchanged. DOM+Leaflet manual canvas and server view tests pass, alongside existing PDF/imagery/linear tests. Live manual-PDF retest pending.
- Next: after deployment, regenerate manual Roofing estimate and verify all feet labels + selected pitch, then reopen saved version. Do not repeat passed automatic two-roof PDFs.

---

# October 13 evening continuation

Baseline parent: cec07fc3b587461f905f3abd0ebcb4b846466677. Authorized branch unchanged.
- Saved area controls now appear in Linear mode. Remove keeps the line and rate. Edit switches to Area with draggable corners; Sean clarified that Area dragging works, and he had attempted to drag the linear line.
- Website index/features now distinguish Google Roofing AutoMeasure from manual surface area/linear tools. AI Trace remains retired.
- Added Edit Line / Save Line Changes / Cancel Line Edit for all six industries. Dragged line points update length. Cancel restores geometry; switching tools cancels an unfinished edit. Creating an estimate requires Save/Cancel first. Rate and saved areas remain unchanged.
- DOM+Leaflet checks pass all six industries for draggable line correction, exact cancellation, saved changed length, unchanged areas/rate/usage and tool switching. Existing imagery/PDF and inline syntax/rendering checks pass. These are local checks; live Edit Line validation is pending.
- Sean's initial Pressure Washing test: Area1 18,995 ft² @ .20 = $3,799; Area2 11,401 ft² @ .70 = $7,980.70; Linear679.6 ft @ .70 = $475.72; total $12,255.42, no tax. User proceeded through area removal and confirmed finding Clear Linear; exact post-removal pricing/PDF still needs evidence.
- Next live test: saved Linear -> Edit Line -> drag point -> Cancel restores original; Edit again -> drag -> Save updates length/charge while keeping .70 rate and saved areas. Then export/reopen the changed report.
- Remaining broader commercial, manual Roofing/pitch/correction, dropped-pin, account permissions/quotas testing remains pending. Payments deferred.

---

# AeriQuote handoff — October 13, 2026, 4:38 PM MDT

Current application baseline: `64d28a2d7065a6af9f93b3d71a4bba41499aaebf`.
Repository: `Seandusome/aeriquote-roof-measurement`.
Authorized branch ONLY: `landscaping-multi-area-recovery-oct11`. Never modify main or roll the entire app back.
Test service: https://aeriquote-commercial-test.onrender.com/

## Latest live result: PASSED
User reopened the prior two-roof Roofing estimate and downloaded PDF (19).
Property: 1715 2nd Ave North, Saskatoon, SK.
Main house 1,097 ft², garage 453 ft², combined 1,550 ft², two roofs.
Main house $822.50, garage $340.09, subtotal $1,162.59, taxes $58.13 + $69.76, total CAD $1,290.48.
Both roof outlines align; all eight feet labels and all four pitch labels appear in the reopened PDF.
Main house edge labels 45.0, 48.3, 19.7, 22.2 ft; pitch labels 29.6°,31.7°.
Garage labels 24.5,25.4,15.6,15.6 ft; pitches 24.0°,22.9°.
Do not repeat these tests unless new code or evidence warrants it.

## Afternoon progress after the earlier checkpoint
- Snow Removal combined workflow passed: 17,729 + 11,432 ft², 667.4 ft, $150 salt, 5% + 6% taxes, CAD $13,188.07. Saved reopen preserves Nancy contact details and internal note de-ice. PDF guarantee prompt removed.
- Saved-area count and message corrected for all five surface industries (23de83a).
- Empty new draft blocked removing a saved area. Fixed f510923; tests cover all five surface industries, retaining remaining geometry/rate and linear.
- User removed Snow Area 2, then edited Area 1: 17,808→17,409 ft² at .25, 669.4 ft at .40, final CAD $5,128.20; PDF aligned.
- User confirmed improved imagery at 1715 2nd Ave North. Wide imagery now scale=2; zoom/pan detail up to zoom20, with retained 3x3 coverage. Surface industries and normal address-based Roofing share loader. Exact-pin special route remains separate.
- Estimate source resolution now selected from saved areas, lines, roofs and manual outlines; fallback estimate uses improved loader. User confirmed clearer PDF.
- Roofing setup finish button was disconnected. Fixed missing finishSetup ID, setupIndustry roofing mapping, profile field IDs, price/taxes and Roofing benefits in be963b3. All six setup-button flows tested with mocked profile save/navigation.
- Roofing label backgrounds were clipped. Fixed full text width and included Roofing labels in shared canvas export (da5c9e0).
- Roofing PDF SVG shifted outline. Fixed e2bae01: use approved live polygon LatLngs/style on pixel canvas, detach transformed SVG during capture and restore afterward. Edge labels anchor to true midpoints rather than geographically offset locations.
- Label suppression dropped 3 of 4 roof edges. Fixed a3ce1e8. Live PDF13 passed four edge labels, pitch and outline at 1,097 ft², CAD $912.97.
- Added detached garage: live PDF14 passed both polygons, feet/pitch, area1,550 and CAD $1,290.48.
- Removed garage: PDFs15/16 one roof1,097 and CAD $912.97. PDF16 initially appeared blank in Poppler but embedded JPEG and PyMuPDF confirmed valid report; this was a renderer issue, NOT an app blank-PDF regression.
- Previous version PDF18 retained two-roof price/geometry but missed labels. Fixed64d28a2: draw saved roof edges and segment pitch labels into historical canvas. Latest PDF19 confirms fix live.

## Preserve / avoid confusion
AI Trace is permanently retired. Keep Google AutoMeasure Roofing, manual tools, wide panning, saved versions, internal notes and pricing.
Opening a saved estimate shows a frozen report, not editable workspace recovery. Copied page text may include hidden background workspace; it already has a fixed report overlay. No UI hiding change was needed.
Refresh/deployment clears active unfinished job; reopening saved report does not restore active measurement state.
Use approved logos only; no redesign. Roof test profile was intentionally sparse (Your Company/Homeowner, empty contact); no evidence of a profile-persistence regression from those placeholders alone.
Street View wall at2301AveC is property-specific, not a bug.

## Next work
No live failure remains from the latest two-roof saved-PDF test. Choose next cleanup/feature with Sean; do NOT repeat passed industry creation tests unnecessarily.
Known usability gap: saved area edit/remove buttons hidden in Linear mode; user switches AREA to remove. Not fixed yet.
Further testing pending: differing per-area rates live; broader commercial workflow; manual Roofing/pitch/correction and dropped-pin paths after shared export changes; complete account/permissions/quotas and launch regression pass.
Website AI wording audit and payments remain pending. Do not claim production ready.
Stripe/bank work deferred until software cleanup/features/heavy testing complete. Sean plans actual Alberta operations, may use Shingle Guard Inc. legal entity and dedicated USD business account, public AeriQuote branding, subscriptionsUSD; tax registration specifics require accountant confirmation. Do not resume payments unsolicited.

## Verification and workspace notes
Latest local DOM+Leaflet suite and rendering/inline-JS syntax checks passed. New checks cover Roofing imagery requestzoom20, saved labels, polygon pixel export, midpoint anchors, all rectangularroofedge labels, and all five surface-industry removal cases. These are mocked-source/export checks; live PDF results above provide visual evidence.
GitHub CI green was verified earlier at e4e64ec; later commits were not individually checked for workflow conclusions. Check actual REST actions/runs?head_sha=... if needed (wrapper fetch_commit_workflow_runs incorrectly filters and returns[]).
Local repo /workspace/scratch/423ffc3aefb0/aeriquote-roof-measurement; local Git index remains oldc52de63 with many remote-published changes showingmodified/untracked. Compare against remote branch, not index. Leave pre-existing site/assets/commercial-approved.png modification untouched.
Node dependency path: /workspace/scratch/423ffc3aefb0/test-deps/node_modules. Run NODE_PATH=... node scripts/test_landscaping_controls.cjs. python scripts/test_landscaping_rendering.py checks syntax and saved aerial framing. Flask not installed globally; scripts ASTextract routes. Browserbinaryinstall failed; do not claim full browser automation.
Publish via GitHub connector create_blob/create_tree(base current remote tree)/create_commit/update_ref expected_sha. Only authorized branch. app.py huge1.35MB embedded assets, avoid truncating; small docs use structured blob.

---
Earlier checkpoint retained below for history. Its next-step list is superseded by this handoff.

# AeriQuote verified checkpoint — October 13, 2026

Application baseline: e4e64ec05a6b866e1fbfff7b07751cf7b5e333a0.
Repository: Seandusome/aeriquote-roof-measurement.
Work only on landscaping-multi-area-recovery-oct11. Never modify main.
This checkpoint records verified behavior, not a production launch approval.

## Decisions to preserve
- AI surface tracing is retired and removed. Do not restore it or propose further paid tracing tests.
- Preserve manual area and linear tools, automatic roof measurement, wide aerial panning, saved estimates, prices, and PDFs.
- Use existing approved logos; do not recreate branding.
- Street View wall image at the test property is property-specific and is not a defect to fix.
- Refresh/deployment clears the active measurement workspace. Saved reports can be reopened, but that is not a complete editable-job recovery feature.

## Verified by live user tests
- Paving: two areas plus linear measurement, independent units, rates, taxes, PDF and saved reopening.
- Original paving version: 15,370 and 10,399 ft² plus 674.6 linear ft; total $6,644.64. Previous-version reopening retained original data.
- Fresh and reopened PDF labels render clearly and remain above outline strokes.
- Aerial labels, service-area rows and pricing agree after the stale-aerial export fix.
- Company logo/contact data and customer email appear in PDFs.
- Internal notes save and display in expandable history cards; they stay out of customer PDFs.
- Saved surface jobs use Service area; linear-only jobs use Service length and linear feet.
- Pressure Washing: linear first remains selected during loading and remains visible while drawing two areas.
- Latest Pressure Washing test: 12,680 and 11,864 ft² at $0.40/ft², 601.9 ft at $0.70/ft, subtotal $10,238.95, 5% and 6% taxes, total $11,365.24.
- Pressure Washing PDF and saved reopening retained both areas, length, rates, taxes, customer details and notes.
- Both GitHub workflows passed on e4e64ec.

## Automated checks
Engine checks for landscaping, paving, pressure and snow; DOM + Leaflet area/linear controls; linear-first visibility across five surface industries; delayed aerial/profile loading; saved historical canvas labels; PDF label capture and restoration; notes-only saving and reopening; history wording; Python and inline JavaScript syntax; aerial framing; recovery-account allowance isolation.

## Next steps, not yet live verified
1. Snow Removal: verify combined areas + linear, PDF and reopening with current shared fixes (earlier basic snow test passed).
2. Different per-area rates in the latest Pressure Washing workflow (latest live test used equal area rates).
3. Broader landscaping/commercial and roofing regressions after shared export changes.
4. Website wording audit: retire AI surface-tracing claims; do not imply automatic lawn/paving measurement.
5. Stripe subscription/payment integration and launch readiness are not established by measurement tests.

User is opening an AeriQuote bank account and asking about Stripe Canada onboarding. Resume software work from this verified baseline when they return; avoid repeating passed tests without a new reason.

