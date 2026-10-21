# October 20 live warranty QA checkpoint

Application 0135a4e remains deployed on the recovery branch. Main and roof safeguards were not changed.

- Sean completed password recovery manually and signed in. Fresh live profile confirmed `sean@shinglextra.com`, company AeriQuote QA, approved brand `shingle_guard`, no complimentary allowance or extra credits. The recovery page was reachable; no underlying recovery defect was established. The earlier automated reset submission was denied by browser security review and was not retried through another mechanism.
- Reopened `QA TEST Roofing First Estimate DO NOT SEND`, then its current version. The stored report showed 1,790 ft², manual trace with 5/12 pitch, $1,987.15. Old historical snapshots correctly did not acquire a new warranty shield.
- Entered saved-job edit mode; measurements and pitch restored. Selected the approved Shingle Guard logo and saved this QA profile with the shield checked. Profile saving applies its default job rate; explicitly restored this QA job's original $1.00 rate afterward.
- Created a labelled revision: `QA TEST - Shingle Guard Warranty Oct20 - DO NOT SEND`. Notes identify synthetic manual roof, assumed 5/12, not a customer measurement. Live report displayed the dealer logo and 6-Year Transferable Warranty shield, retained the roof and dimensions, and showed $1,790.22 + $89.51 + $107.41 = $1,987.14. The one-cent difference from the old snapshot is consistent with the previously fixed rounding calculation; no new pricing fix was made.
- First live Single-page PDF download attempt hit native credential-data protection and reset the browser kernel. No completed PDF download, visual PDF inspection, Expanded download, hide/re-export, ShingleXtra live export, or reopen of the NEW revision is claimed.
- Local `node scripts/test_warranty_shields.cjs` passed, including both brands, hidden preference, ordinary-account absence, Roofing-only display, historical choice and Expanded header inclusion/exclusion. This mocks export capture and is not actual live PDF visual verification.

Next: reopen the new QA revision, confirm persistence, inspect actual Single/Expanded PDFs with shield on/off, then ShingleXtra. Continue pending live isolation checks with QA accounts only. Leave real dealer Blake and all other real accounts unchanged. Never restore AI Trace or alter main.

## Resumed live PDF checks

- Used the existing signed-in AeriQuote QA session and labelled job above; report contact remained sean@shinglextra.com. No real dealer account or main branch was modified.
- Reopened the new saved revision through Previous Estimates > View History > Current Estimate > Open Estimate. Warranty shield, 1,790 ft², 5/12 and total $1,987.14 persisted.
- Downloaded ACTUAL Single and Expanded PDFs, rendered with Poppler and visually inspected all 3 pages. Shield present in Single and on both Expanded pages. Logo, aerial, dimensions, pricing, tax and contact retained. Synthetic outline is deliberately NOT a reliable customer measurement.
- Found an actual Expanded PDF defect: the Shingle Guard logo is stretched horizontally. Fixed the exporter to calculate explicit width/height from intrinsic dimensions within its 170 × 65 header limits rather than relying on html2canvas object-fit. Regression test added; warranty test and Python compile passed. Published recovery commit 243fc2ebef88d80a72a5c70d38cb21b18cdcdb9d; Render deploy dep-dbbsts8u01pc7387p5fg is live. Corrected actual PDF visual recheck is PENDING, not claimed.
- Saved QA profile with shield OFF. Profile save resets the job rate to the default $0.10; restored #jobPrice to original $1.00 BEFORE creating the estimate. Customer-name rename attempts timed out; retained the existing explicit QA / DO NOT SEND label.
- Created a new report with shield absent, downloaded ACTUAL Single and Expanded PDFs, rendered and inspected all 3 pages. Shield absent throughout, Shingle Guard logo retained, aerial/labels present, total unchanged at $1,987.14. Reopen/persistence of this OFF revision still pending.
- Raw downloads (scratch, not user deliverables): /workspace/scratch/da5b930b-e7d9-4156-8484-8082f54643c7/{f73f9d03-9302-4908-8c41-3322f6c23a4a,805455ec-9a73-4963-9334-350eedc95a0e,dbdf53d8-e50a-4db5-bae4-2ad79c411137,6f534820-571c-4a48-ae0a-4a3b3f3a3150} respectively SG ON Single/Expanded, SG OFF Expanded/Single. PNG renders in /workspace/scratch/5928230fe716/sg-*.png.
- Head Office credits page correctly returned Head Office permission required for the QA session. ShingleXtra brand reassignment needs an authorized Head Office session; do not grant office permissions to QA or touch real dealers/credits.
- Browser automatic approval review denied reload (possible loss of current QA job state), then also denied closing the report as an indirect continuation. STOPPED browser mutations; no bypass. User approval required before discarding/reloading the QA draft. Preserve the tab/current state.

Next: with user approval, reload/reopen OFF revision to establish persistence; inspect actual corrected Expanded header after deployment. Then Head Office changes ONLY sean@shinglextra.com brand to ShingleXtra (no credits/complimentary change), and repeat both PDFs shield on/off using QA job. Current profile preference OFF. Do not claim ShingleXtra live QA complete.

## Follow-up after Sean approved reload

- User explicitly approved reloading the QA draft. Reload succeeded. Current estimate timestamp 20:27:00 retained shield OFF, 1,790 ft², 5/12 and $1,987.14. Thus OFF revision persistence is now verified.
- Downloaded actual corrected Expanded OFF PDF: /workspace/scratch/da5b930b-e7d9-4156-8484-8082f54643c7/3ccadf8d-cfe2-4e36-943f-7f75d6bbc22e. Both pages rendered/visually inspected. Logo proportions fixed, badge absent; all measurements and amounts intact.
- Reopened Previous Version 2 (the earlier shield ON snapshot) while current profile remains OFF. Shield correctly remained visible in that historical snapshot. Downloaded actual corrected Expanded ON PDF: /workspace/scratch/da5b930b-e7d9-4156-8484-8082f54643c7/63693465-f0a9-4033-bf75-8e26846b46eb. Both rendered pages inspected: proportional logo, shield on both pages, aerial/dimensions/pricing intact. Fix is now verified in actual live PDFs.
- ShingleXtra still needs QA-only brand change through Head Office. Opened normal dealer-login form in second tab to request secure Head Office login; QA report tab preserved. Do not modify real dealers or account credits.

## Head Office brand switch completed

- Sean explicitly authorized Head Office sign-in solely for QA brand switch. Initial secure login was rejected; Sean manually signed in successfully as Head Office (Admin Dashboard visible).
- Head Office credits search returned exactly AeriQuote QA / sean@shinglextra.com, trial, standard allowance, zero extra credits, complimentary unchecked. Changed Approved warranty brand to ShingleXtra only. Saved audit at 2026-10-20T20:40:17.819491+00:00: complimentary 0 → 0; brand shingle_guard → shinglextra; existing usage preserved. No real account modified.
- Navigated QA report tab to normal dealer-login to sign back in as QA. Secure credential request submitted, but visible result says Email or password is incorrect. No QA login success claimed, no ShingleXtra report/PDF created. Manual QA login handoff needed for sean@shinglextra.com, not Head Office.

## ShingleXtra report created; actual exports blocked by browser credential protection

- Sean manually signed QA account back in. QA owner UI (EMPLOYEES, Roofing, no Admin Dashboard) and prior QA-only history confirmed.
- Saved approved brand logo using USE APPROVED BRAND LOGO and checked Show warranty shield; saved QA profile BEFORE restoring the job, so job rate remained $1.00 when restored.
- Opened current synthetic QA roof through history, selected EDIT MEASUREMENTS / PRICE, then CREATE CUSTOMER ESTIMATE. Fresh report displayed warranty image, 1,790 ft², 5/12, subtotal $1,790.22, tax $89.51/$107.41, total $1,987.14 and sean@shinglextra.com. Existing QA TEST - Shingle Guard Warranty Oct20 - DO NOT SEND label retained; it is reused for brand testing, NOT a real customer job.
- Attempted actual Single download (before Expanded). Browser failed before command with native credential retained_data_restricted, reset kernel; no download path returned. Rebinding existing QA tab 4 failed: native credential state cannot be safely resumed. Stopped; did not create alternate tabs, use alternate browser or bypass protection.
- Therefore ShingleXtra actual Single/Expanded ON/OFF export visual verification is still PENDING. ShingleXtra profile now approved logo + shield ON; QA brand is ShingleXtra, zero extra credits, complimentary off. Shingle Guard actual exports and corrected Expanded ON/OFF visual tests remain passed.
- Next session: read this file; resume QA-only ShingleXtra report from saved history in a working browser session, download actual Single/Expanded, inspect all pages, hide shield and re-export both, verify reopen. Do not claim mock tests or HTML report as actual PDF verification. Main, real dealers, credits and roof safeguards unchanged.

## Further testing while browser remained blocked

- User asked to keep testing. Existing tab access still failed native credential-state protection. Did not bypass or switch browser surfaces.
- Ran and passed 11 local regression scripts: test_warranty_shields.cjs, test_phone_pdf.cjs, test_estimate_save_integrity.cjs, test_saved_editing.cjs, test_surface_workspace.cjs, test_measurement_edges.cjs, test_price_rounding.cjs, test_account_access.py, test_business_isolation.py, test_complex_roofs.py, test_saved_editing_session.py.
- Coverage: six-industry editing restoration; reversible area/linear controls and independent rates; crossed/zero-area/unfinished-draft guards; removing last area retains priced line; displayed money/tax rounding; failed-save retry; mobile PDF clone/map preservation; actual Flask business and employee isolation, foreign image/revision/edit rejection; complex roof ownership/cache/recoverable failures.
- Three Python scripts initially lacked Flask in this fresh runtime. Installed Flask 3.1.2 into scratch-only /workspace/scratch/5928230fe716/qa-python-deps and reran with PYTHONPATH; all passed. No dependency or app code changes made; tests use isolated local QA data, no live dealer writes.
- These passes are automated local checks, NOT actual ShingleXtra PDF downloads. Remaining live export blocker and checklist above unchanged.

## ShingleXtra actual PDF QA completed

- Resumed in working browser session on AeriQuote test. Existing signed-in owner profile showed AeriQuote QA / sean@shinglextra.com and ShingleXtra logo. No sign-in, Head Office, credits or real-dealer actions were needed.
- Reopened CURRENT ESTIMATE timestamp 2026-10-20 20:48:49 through saved history. ShingleXtra logo and shield ON persisted; 1,790 ft², confirmed 5/12 pitch and total $1,987.14 retained.
- Downloaded ACTUAL Single ON and Expanded ON PDFs. Rendered with Poppler and visually inspected all three pages. ShingleXtra logo proportional; correct ShingleXtra shield present in Single and on both Expanded pages. Aerial, outline, edge dimensions, pitch, street image, contact and pricing/taxes intact.
- Edited only the synthetic QA job. Unchecked Show warranty shield and saved QA profile. As documented, profile saving reset current job price to $0.10; explicitly restored original $1.00 BEFORE creating the updated estimate. New current revision timestamp 2026-10-20 20:56:22.
- Downloaded ACTUAL Expanded OFF and Single OFF PDFs. Rendered and visually inspected all three pages. Shield absent throughout; proportional ShingleXtra logo retained. Aerial, dimensions, pitch, contact, subtotal $1,790.22, taxes $89.51/$107.41 and total $1,987.14 intact. No application defect found in these four exports; no application code changed.
- Reloaded after save, reopened CURRENT ESTIMATE through Previous Estimates > View History > Open Estimate. ShingleXtra logo, shield OFF, 1,790 ft², 5/12 and $1,987.14 persisted. Left this saved report open; QA profile preference remains OFF. Historical QA/DO NOT SEND customer label still contains Shingle Guard from the reused synthetic fixture; actual branding under test is ShingleXtra.
- Actual raw downloads (scratch-only QA evidence, in order ON Single / ON Expanded / OFF Expanded / OFF Single): /workspace/scratch/da5b930b-e7d9-4156-8484-8082f54643c7/{b3d69e21-f890-49a1-8deb-96f4d60db47c,bac06e29-4204-44b9-99b0-6e40e4e99c3d,283e10b2-2548-4ffc-a6c6-3b1f89df4627,b32a05df-39a5-4acf-9d89-6f10cafcfcb1}. Rendered evidence under /workspace/scratch/93dfcfceb87a/sx-*. Persisted report screenshot /workspace/scratch/shinglextra-qa-off-persisted.jpg.
- Both brands' requested actual Single/Expanded shield ON/OFF PDF visual checks are now complete. Main, existing fixes, roof safeguards, account credits and real dealers were untouched. This checkpoint update is documentation only on the recovery branch.
