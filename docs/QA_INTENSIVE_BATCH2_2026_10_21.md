# Intensive prelaunch bug hunt — batch 2 (2026-10-21)

Recovery branch only: landscaping-multi-area-recovery-oct11. Main, real customers, and Ali demo account untouched. AI Trace remains removed.

## Confirmed defects and fixes

- Saved area and linear quantities were trusted even when coordinates were missing or described a different measurement. New dependency-free server module independently integrates spherical area and calculates Haversine length, validates outlines and manual pitched-roof quantities, compares repeated totals, and rejects incomplete snapshots before writes/credits/revisions. For auto-mode Roofing, included automatic/manual roof sums must match the estimate's area; a missing garage in the total is rejected. Existing saved records can still be read; new saves require a complete measurement snapshot.
- Duplicate and partially overlapping surface areas silently counted coverage twice. Client pre-report validation and server save validation now reject them. Adjacent shared boundaries and separated areas remain valid. Concave U-shaped duplicates and an area inside the U's empty gap are covered.
- Client polygon arithmetic lost precision from subtracting large global coordinates (tiny WGS84 reference approximately 4% error) and interpreted a longitude ±180 crossing as an almost-worldwide polygon. Local-origin arithmetic and longitude unwrapping fix both. Numerical references from GeographicLib 2.1 WGS84 cover Saskatchewan, Florida, Alaska, tiny Vancouver geometry and the dateline. Normal spherical model differs from WGS84 by up to approximately0.44% in these fixtures: this is a documented approximation, not survey-grade accuracy.
- Amount-paid metadata accepted Infinity (reproduced against actual Flask endpoint), NaN and negative/bool coercion. Reject nonfinite/negative/bool values; regular estimate saves also validate amount_paid.
- Public signup could create a second owner identity using an existing employee's email (reproduced with isolated QA account). Case-insensitive owner/employee collision checks now cover public signup, both admin owner creation APIs and setup-dealer. Existing employee creation already checks both tables. No existing accounts changed.

## Automated evidence

47 workflow checks passed. Added independent geometry and client overlap checks to CI. Price-only unit test isolates geometry in its adapter; actual geometry helpers have separate real-function tests. Old security/editing fixtures used arbitrary100ft2 for a much larger triangle; updated fixtures to true measured quantities without changing permission assertions. After final snapshot-required changes, reran affected pricing API, shared-credit and geometry tests successfully. Owner/employee permission and cross-business read/write/revision/editing/imagery isolation tests pass. Password-recovery regression covers mocked mail, CSRF, expiration, single use, old-session revocation, disabled accounts, owner/employee resets, and throttling. Allowance tests cover production policy in temporary SQLite, named test bypass, shared quotas, extra credits, 200 monthly quotas and free revisions. No real mail/password changes or malformed live API requests. git diff --check passes.

## Mobile browser evidence before deployment

Existing /static/scripts/mobile_visual_qa.html harness; real authenticated browser, CSS-width iframe, not device/touch emulation. All six industry workspaces inspected at320,390,768px (18 combinations): document scrollWidth equaled clientWidth; no horizontal overflow. Opened saved QA mixed Landscaping estimate at390 and320px; report and pricing rows fit within their containers, quantities and seasonal total preserved. Actual post-fix live mobile editing/save/reload/PDF pending at this checkpoint.

## Limits / next work

Cannot independently infer absent buildings from imagery: Google whole-building/Pinehouse coverage issue remains guarded and unresolved. Automatic multi-plane roof geometry, adjusted-area pricing, independent full server price recalculation and arbitrary overlapping roof-plane combinations are not fully verified. Client overlap checks and server guards prevent known surface overlap cases; no general GIS proof for all possible polygons. Production PostgreSQL concurrency, simultaneous cross-table signup races, physical touch placement/drag/pinch/rotation/keyboards, native mobile PDF/print, real email delivery and live employee/password reset remain unverified this batch. Browser QA stays in isolated AeriQuote QA account.

## Final live verification

Code commit7a8d88d9bbe992da5c4c7d6939fa5414094a38ec deployed LIVE, dep-dbcinpbncjis73asvkbg, finished2026-10-21T21:19:45Z. Source, test scripts, dependencies and workflow fetched from GitHub and confirmed identical to locally tested source. Full explicit212-entry tree preserves previous source and checkpoint documents. Render startup took approximately140sec after build; not a failed build.

Actual320px browser workflow on deployed code, isolated AeriQuote QA account: reopened Landscaping combined job; Edit Line disabled quote creation; Cancel retained463.2ft. Edit Outline disabled quote creation; Save Area Changes retained16,372ft2 (no corner drag performed). Changed area rate0.10 to0.12 through real keyboard events; linear rate remained0.70. Created quote successfully, reloaded iframe, reopened current history. Verified persisted area16,372ft2, area charge1,964.64, linear charge324.27, subtotal2,288.91, sales tax5%=114.45, additional tax6%=137.33, totalCAD2,540.69 per season. Previous2,177.23 seasonal revision remains in history.

Actual phone-width downloads on reopened revised record: Single page (one page) and Expanded (two pages). All three pages rendered with Poppler and visually checked: area and line outlines/labels present, street imagery present, both quantities/rates, subtotal, taxes and seasonal total match saved estimate. Existing expanded numbered-callout line overlaps area label; cosmetic issue remains. A predeployment phone PDF click caused browser-tool download-event timeout/reset, but application showed downloaded and actual matching file was found and rendered. Subsequent downloads completed through UI with files verified; no app PDF failure inferred from tool timeout. Captured final320px pricing screenshot successfully.

After final snapshot-required restriction, reran pricing API, shared-credit, geometry, password-recovery, saved-editing-session and business-isolation tests successfully. The47-check workflow run passed; targeted reruns cover the subsequent API tightening. No live malformed payloads, employee account creation, real password change or customer accounts touched.

Resume next batch from this file. Do not repeat completed47-check evidence or current mobile save/PDF check without a new change. Remaining gaps listed above, including physical device gestures and independent full price recomputation, are still open.
