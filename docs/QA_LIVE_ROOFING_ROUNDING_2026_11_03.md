# Recovery deployment and live verification — November 3, 2026

Deployed exact tested source **194c435b377dbcb23ad24a422c63763fcd931ed4** to recovery service srv-db5a2g5ckfvc739fui70 only. Deploy **dep-dbl5m4lbedkc73ekek60**, LIVE2026-11-03T22:09:04Z. Recovery link: https://aeriquote-commercial-test.onrender.com/ . Auto-deploy remains OFF. No main, production, customer-data, environment or connection changes.

## Isolation and source

Before deployment, recovery Shell asserted DATABASE_URL host dpg-dbj4f7lg1s2s73eob8t0-a and database aeriquote_recovery_qa. A read-only actual connection returned that database and PostgreSQL18.6. Credentials never printed. A first metadata query used incorrect SQL identifier quoting; it was corrected without any data write.

After deployment, new instance **t99jq** asserted RENDER_GIT_COMMIT194c435b377dbcb23ad24a422c63763fcd931ed4 and the same exact QA host/database before its read-only saved-estimate query. Deployment metadata independently reports that commit LIVE. Auto-deploy OFF freshly rechecked after verification. No configuration change.

Exact-source required checks were reverified before deployment: application41726151088, recovery41726151080 including PostgreSQL16/18, browser41726151121(10/10), allSUCCESS. No new code changes or workflows in this deployment batch.

## Live Roofing flow

Reused the existing signed-in qa-browser-oct31-2026@example.invalid session; no password/account change. Started a separate draft rather than discard older QA drafts. Previous Estimates → View History → current Open Estimate → Edit Measurements/Price restored the fictional saved Roofing job.

- New simplified initial flow shows LOAD PROPERTY & TRACE ROOF and the current action, without premature confirmation.
- Saved roof shows7,348ft² and5/12. Edit clears the pitch selector; confirmation is hidden during edit. Cancel preserved the saved section. Add Section also clears pitch and hides confirmation; Cancel preserved the section.
- Explicit confirmation succeeds and points to the next stage. Later Edit → explicitly select5/12 → SAVE SECTION CHANGES preserves area/pitch and requires confirmation again. No default pitch was automatically accepted.
- Live report save succeeded, recovery copy deletion acknowledged, customer preserved. History reopen shows the same customer, measurements, rates, extras, taxes and total.
- Final workspace is left open on the saved section, **unconfirmed after reopening/editing**, as intended for Sean's visual review. This does not alter the stored confirmed estimate or create another revision. No geometry changed.

This was an existing-property/saved-roof live verification, not a new lookup or new trace accuracy audit. Physical-phone and Sean's manual desktop review remain pending.

## Exact monetary boundary

Fictional customer **FICTIONAL LIVE ROUNDING NOV3**, estimate5449ffd8-52ac-41db-81c2-9a8e924cc301. To exercise the original367.30 tax boundary on live imagery, used the existing fictional QA roof plus a fictional extra, rather than import the disposable fixture's different geometry:

| Component | Independently calculated |
|---|---:|
| 7348.380392728047ft² ×0.01, half-up to cents |73.48|
| Fictional extra |293.82|
| Tax base |367.30|
| GST5% |18.37|
| Additional tax6% |22.04|
| TotalCAD |407.71|

Browser preview, actual stored pricing (read-only QA SQL), current report and history-reopened report match every amount. Stored plane22.62°/5/12, pitch_confirmed and roofScopeConfirmed true. Revision count increased once from27 to28; only one completed estimate save was submitted. Subsequent section save is workspace-only. Live QA bypass is not new normal-plan allowance evidence; prior disposable tests cover normal rules.

Single1page and Expanded2pages were downloaded after saving, rendered and inspected: correct fictional customer, original priced roof, pitch/edge labels and all amounts, including GST18.37/total407.71. Reopened Single downloaded and inspected again with the same amounts. Reopened Expanded export also returned a completed download, but its extra browser file could not be retained after the tool returned; it is not counted as an additional inspected artifact. The original inspected Expanded file matches the stored/reopened report. Three valid PDF copies are preserved.

## Fresh minor visual finding

The long fictional extra-service description causes the Expanded PDF's293.82 amount to wrap its final digit onto the next line. All digits and totals are present and correct; Single is readable. This is a fresh formatting follow-up, not the historical white-PDF/aerial issue. No code or layout changes were made in this authorized deployment batch. Keep this noted for a focused follow-up; do not call the Expanded layout visually flawless.

Evidence: `docs/qa/live-rounding-2026-11-03/` contains sanitized preflight, stored-value reconciliation, live layout/report screenshots, saved Single/Expanded PDFs, reopened Single and verified page renders. Two pre-existing untracked PDF copies preserved.

## Sean's short desktop review

1. Load a fictional job/property: is starting the roof trace obvious?
2. While tracing or editing, is pitch beside Save, with Cancel easy to find?
3. After saving, can you read every section's area/pitch and see the single confirmation action?
4. After confirming, does the next missing price/customer/Create step feel clear?
5. Reopen the estimate and try Single/Expanded download. Note any competing buttons or confusing wording.

The shared review tab is already on FICTIONAL LIVE ROUNDING NOV3. Confirm its saved5/12 section to continue; no need to recreate the rounding test. Do not treat0.01/ft² as a suggested business rate; it is fictional QA input only.

Checkpoint is the documentation commit containing this report. Pause for Sean's review; no further tests, changes or deployments without instruction.
