# Existing-job launch-readiness audit — November 2, 2026

Start: checkpoint `c4683d9e01b3ff6e99984aa7e8f82bff370cc006`, prior tested source `33448215`. Recovery live remains `69ab066c67cb429d4e12c8dad2d902140fbbc405`, `dep-dbke60u1egvs73cafea0`; auto-deploy OFF. No deployment in this batch.

## Isolation and selected gaps

All new mutations use fictional jobs in disposable loopback SQLite, synthetic imagery and normal trial/Basic allowance policy. Dedicated live QA PostgreSQL, main, production, customer data, account settings and payment/imagery integrations are unchanged. The dummy policy URL cannot open a PostgreSQL connection: the established explicit local DB adapter handles every query. The normal paid account is not complimentary and the recovery-service bypass is disabled. PostgreSQL16/18 integrity workflows independently exercise the existing database/charged-save regressions.

Existing evidence covered basic saved editing, snapshot scope and separate races. New coverage joins these into longer editing sequences across all six industries, uses native drawing/line dragging and visible controls, preserves old rows, and exercises existing edits at exhausted allowances. The real application report-map endpoints and Static Maps path-generation code execute. Only external imagery-provider bytes are replaced with a synthetic grid plus the requested projected paths; unexpected provider requests fail. This is application integrity evidence, not real-world roof accuracy or provider/licensing verification.

## Application defects reproduced and fixed

1. **Duplicate generated service-area names after delete/add.** Removing Area1 from a two-area job, then adding another, generated a second `Service Area 2`. Coordinates, amounts and taxes remained correct, but both quote rows had the same default name. Before-fix DOM assertion fails with one distinct name for two saved areas. New automatic names skip existing names; custom/existing names and quantities/rates are preserved. All five surface-industry regressions cover `Service Area 2` + `Service Area 3` after the sequence.
2. **Roof Cancel left saved-section controls disabled.** Edit a saved manual section, change its pitch, then Cancel: geometry and saved pitch were preserved, but Edit/Delete stayed disabled until another input caused a summary refresh. Actual Chromium timed out on the disabled second Edit; a focused DOM test reproduces the same state using the real Cancel button. Cancel now refreshes the summary and controls immediately. Existing pitch/scope confirmation requirements remain; measurements and history are not rewritten by Cancel.

3. **Industry wording changed user-authored report/PDF text.** Visual review of the new mixed-history Snow PDF found the stored address `1 Fictional roofing QA Street` displayed as `1 Fictional areaing QA Street`, and an extra-service description changed similarly. The global terminology walker treated user/provider data as interface copy. The correction protects address/customer/company/marketing/service/history data and PDF staging from translation, while retaining industry-specific interface labels. Exact text assertions cover all six industries, actual report addresses/customers/email/descriptions and mixed-history PDF exports. Before-fix PDF and source are retained under `before/`; stored data was never corrupted.

The application diff consists of these three narrow UI/display corrections. No geometry/pricing/allowance engine, schema, account, database connection, provider integration, feature or payment change.

## Test-fixture corrections (not application defects)

- Run41520117701 compared serialized objects with identical values but different property order. Geometry comparisons now canonicalize object keys using the existing stable serialization; array order and all values remain strict.
- Opening an old revision intentionally acquires the latest save lease, permitting an explicit revision-from-history edit. The stale case now commits an actual competing writer *after* acquiring that lease, then requires409 and exact retained work. No stale-write assertion is relaxed.
- Run41521041234 waited for a session after the fixture's new property callback redundantly persisted a session through a second SQLite connection inside an already-locked property transaction. Local testing exposed `database is locked`; removing only that fixture persistence yields immediate HTTP200. Property readiness condition and timeout are unchanged.
- Run41521728752: job-revisions reproduced the disabled Roof Edit control (application defect2 above). Drafts failed after matching the saved-copy badge before Restore cleanup completed. The old artifact has redacted server logs and no browser request trace, so its exact historical request sequence cannot be recovered. A new controlled delayed-cleanup case reproduces the same generic retry + pending-work state with **zero estimate POSTs** while Restore is busy. Releasing cleanup and explicitly retrying produces one HTTP200 save. The test now waits for the Restore choice panel to disappear, retains exact-work assertions and writes status-only HTTP traces. This establishes and fixes a test-readiness race; it does not assert that the old run proved a server failure. Final repeat results are recorded below.
- A further mixed-history display assertion compared unformatted totals against a thousands-formatted price. It now compares the exact numeric saved total and its currency-formatted display; the amount assertion remains.
- Each industry's initial job now has a distinct fictional address, including the fixture's canonical address, to distinguish new jobs from the application's intentional one-property revision behavior.

## Final results

Final source: `c7f2d013edf4425972c3fd8da48137a9b2d45882` (undeployed).

- All six existing-job lifecycles execute: reopen, Cancel without changing saved geometry/pitch, add/replace/delete areas or roof sections, native line endpoint drag Save/Cancel, remove/re-add line, change independent rates/extras/decimal taxes/customer details, acknowledge draft, refresh/Restore exact work, commit with a lost response, retry the same operation once, and retain the original payload unchanged.
- Each six-industry lost-response sequence adds exactly one revision and one save receipt. Retrying adds none. No new estimate or paid lookup/estimate debit occurs. A separate competing current edit creates its own explicit revision; the older open editor's subsequent save returns409, retains its acknowledged work and changes no history or allowance.
- Twenty-four malformed active-measurement attempts (four per industry: missing points, wrong quantity, invalid rate/pitch, missing active scope) return400 with an error; current/older payloads, receipt/revision counts and allowances remain unchanged. Incomplete replacement and negative extras are also blocked through visible UI.
- Roofing starts with three actual traced sections at22.62°/0°/45°. After edit/Cancel, pitch change, flat-section deletion and replacement:36.87°/45°/26.57°. Original diagrams retain the original three sections; updated diagrams show only the current three.
- Same-property Roofing→Commercial→Landscaping→Paving→Pressure→Snow creates five explicit surface revisions while retaining three dormant roof sections in each source. Actual diagram endpoint requests contain exactly two priced areas and one line, no dormant roofs. Both actual PDF layouts are downloaded for each. Out-of-order reopening `[6,0,2,-1,1,3]` preserves every saved row and selects the correct industry/customer/total.
- Normal Basic allowance: six initial jobs consume six estimate allowances; property lookups are normally spent up to25/25. Failed imagery requests and exhausted attempts retain existing work and do not charge. Existing Roof edits/restores/retries plus five mixed-industry revisions still work at25/25 without a new debit. End state: six estimates,17 intentional revisions,23 estimate-save receipts,25/25 lookups and6/25 estimates used. No QA bypass or top-up.
- Separate normal trial: provider503 spends zero; three accepted properties/three estimates exhaust trial limits; repeat acceptance spends once; fourth lookup/new estimate403; existing edit at cap succeeds once; duplicate operation replay, stale409 and invalid geometry400 preserve allowance/history. End: three estimates, one intentional revision, four estimate-save receipts, three lookups.
- Independent WGS84 and Decimal active-scope calculations PASS for17 frozen snapshots. Tolerance0.6% reflects the application's spherical measurements, not survey accuracy. Regular pricing with fractional area/linear rates, extras, 5%/6% and7.25%/2.5% tax is independently reconciled.
- **34 current PDFs /63 pages** rendered. All pages reviewed; after the final text fix,44 pages are raster-identical to the already reviewed versions and all19 changed pages were reviewed again. Customer names/emails, unmodified address/description text, active outlines, pitch labels, price rows and totals match. No stale roof paths in surface diagrams, no missing priced scope, clipping or blank output observed. Before-fix incorrect Snow PDF is retained separately and is not counted as a passing output.

| Industry | Original total | Edited/restored total | Same-property mixed-history total |
| --- | ---: | ---: | ---: |
| Snow |153.18|383.26|467.37|
| Pressure Washing |153.18|383.26|438.68|
| Paving |153.18|383.26|409.99|
| Landscaping |153.18|383.26|381.31|
| Commercial |163.52|383.26|352.61|
| Roofing |253.89|1,192.06|—|

Amounts CAD. `independent-reconciliation.json` records every active quantity, rate, rounded charge, extra, tax base, tax and total; individual audit JSON records row/allowance invariants and request scope. `visual-review-index.json` records every reviewed page and final raster changes. PDF/source checksums are in `evidence-manifest.json`.

All required workflows **PASS on exact final source c7f2d013**:

| Workflow | Run | Result |
| --- | --- | --- |
| Validate AeriQuote application |41524565882|PASS|
| Validate landscaping recovery |41524565618|PASS, every recovery test and PostgreSQL16/18|
| Isolated browser crash and recovery QA |41524565651|PASS, all10jobs including drafts and job-revisions|

`ci-results.json` records the final head SHA and every job. No unresolved CI failure remains on this source. Earlier failed runs are superseded, with causes distinguished above. The exact failed draft request in the old untraced run remains a historical diagnostic limitation, not evidence of a current unresolved server defect.

The browser/recovery checks and original bug guards are preserved. No assertions or production safeguards were weakened. Unresolved application defects are not inferred from test-fixture failures.


## Pending and next session

- Keep this batch undeployed. Review evidence and obtain separate authorization before any recovery deployment/live retest. The preceding manual-pricing correction also remains undeployed.
- Owner manual desktop review and physical-phone/Safari/Messenger testing remain pending.
- External imagery/provider accuracy and availability are not proven by synthetic fixtures; payment integration remains outside scope.
- New end-to-end money checks in this batch use regular pricing; tax-included/discount policies continue to pass existing server regressions, but these exact long edit/Restore/PDF sequences under promotions were not newly exercised. Prioritize those after deployment/live verification and device review.
- Prioritized next session: (1) review these three fixes plus the earlier manual-rate fix, separately authorize recovery-only deployment and verify live against isolated QA; (2) owner desktop edit/reopen/Restore/PDF review; (3) physical phone/Safari/Messenger touch and download checks. No payment/feature work is authorized by this handoff.
- Stop after checkpointing this bounded batch.
