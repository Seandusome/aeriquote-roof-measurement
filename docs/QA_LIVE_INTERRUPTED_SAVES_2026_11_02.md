# Live recovery deployment and interrupted-save QA — November 2, 2026

Continued from checkpoint `cfd5fecc`. The owner explicitly authorized deploying application commit `69ab066c67cb429d4e12c8dad2d902140fbbc405` only to recovery. No new application code or feature was added in this batch: the previously checkpointed fixes were deployed and verified live.

## Deployment and isolation — PASS

- Required workflows on that exact application commit were rechecked: recovery **41505173423**, application **41505173311**, browser **41505173632** all successful. PostgreSQL 16/18 and all eight browser jobs passed; previously skipped downstream checks executed.
- Before deployment, the running recovery process asserted service `srv-db5a2g5ckfvc739fui70`, database host `dpg-dbj4f7lg1s2s73eob8t0-a` and logical database `aeriquote_recovery_qa`. A read-only query scoped to the fictional QA owner established 1 estimate / 21 revisions / 24 save receipts.
- Dashboard **Deploy a specific commit** selected exactly `69ab066c`; deployment **dep-dbke60u1egvs73cafea0** became LIVE at **19:23:34 UTC / 13:23:34 Saskatchewan time**. New instance `cp56m` independently asserted the exact running Git SHA, the same isolated database, and both acknowledgement/uncertain-write fixes present.
- Auto-deploy remains **OFF**. No database connection, network allowlist, account/password, pricing/allowance setting, imagery integration or production configuration changed. Normal owner-entered authentication was used; no credentials were read or changed.

## Actual live browser cases — PASS

### Restore in another tab, then save further edits in the original

Used the existing fictional Paving job, avoiding another property lookup. Original tab3 changed fictional customer details, Area2 rate to0.27 and extra service to53.25. Once acknowledged, tab5 restored that draft. Whole quote and ALL captured form values matched by canonical SHA-256; Restore created no estimate/revision/receipt. Original tab3 retained its later note after its source recovery ID was consumed. Its background warning was visible; explicit Create saved the exact later workspace under the existing safeguards, adding exactly one revision/receipt.

Tab5 then tried to save a different note using the old base version. The live UI explained: “This estimate changed in another session. Your measurements are still here. Reopen the latest saved version before saving changes.” The stale note remained both in the form and in the acknowledged user-scoped draft. Counts did not change. After preserving evidence, the completed fictional stale draft was discarded through normal recovery controls.

### Real lost response through the browser's ordinary save timeout

A temporary transaction held **only the fictional QA estimate row**, without changing it, from19:43:57.714 to19:44:47.715UTC. The browser initiated Create at19:44:09.206. Its ordinary30-second timeout returned the retry warning and kept the workspace. The server completed the original save after the row lock released; read-only SQL proved the intended note was committed with exactly one added revision/receipt. The browser retried at19:45:22.018, recognized the original receipt and reopened the report. **No additional estimate, revision or receipt** was created by retry. This exercised an actual live delayed request/aborted response, not a mocked HTTP result or changed timeout setting.

### Interrupted autosave followed by newer edits, actual tab closure and Restore

A first35-second setup had insufficient overlap because of browser-tool latency and is **not counted as a timeout pass**. A second attempt gated the edit on a confirmed QA-only draft-row lock held for55seconds (19:48:58.272–19:49:53.273UTC), crossing the client's ordinary12-second acknowledgement deadline. The unacknowledged warning remained visible. Newer note/pricing edits were made around release; normal background recovery eventually acknowledged the newest note and54.25 extra service. No estimate was created by autosave.

After the UI explicitly acknowledged storage, original tab3 was actually closed. Fresh tab6 restored its server draft. The entire quote and ALL captured fields matched the acknowledged source by SHA-256, including the newest note, customer details, rates and extra amount. Restore again added no estimate/revision/receipt. Explicit Create saved the recovered workspace exactly once and deleted its recovery payload.

## Counter evidence

All rows are scoped to fictional QA owner `c417b9a2-51ea-4816-84da-1e597a7de98d` and estimate `5449ffd8-52ac-41db-81c2-9a8e924cc301`.

| Stage | Estimates | Revisions | Save receipts |
|---|---:|---:|---:|
| Baseline; initial Restore | 1 | 21 | 24 |
| Original tab's explicit later save | 1 | 22 | 25 |
| Stale second-tab rejection | 1 | 22 | 25 |
| Eventual save after browser timeout | 1 | 23 | 26 |
| Receipt-confirming retry | 1 | 23 | 26 |
| Interrupted autosave and close/Restore | 1 | 23 | 26 |
| Explicit recovered save | 1 | 24 | 27 |
| Both PDFs and fresh history reopen | 1 | 24 | 27 |

Three distinct intentional changes produced three revisions and receipts; retries, Restore, PDFs and reopening added none. Final active drafts=0; closed drafts retaining workspace/image metadata=0; temporary test lock connections=0. Login diagnostics and QA session-timeout override remain OFF.

**Allowance scope:** live QA has its existing bypass; monthly usage rows stayed empty and no new property lookup occurred. This proves no additional live debit in this QA configuration. Paid-plan199→200 exactly-once behavior remains supported by the passing disposable PostgreSQL16/18 fixtures; a live paid-plan deduction is not claimed. The bypass/plan/allowances were not changed to run these tests.

## Estimate and actual PDFs — PASS

Saved customer is `FICTIONAL QA LIVE RECOVERY NOV2`, phone306-555-0182, email`nov2-live-qa@example.invalid`. The final internal note is `FICTIONAL NOV2 AUTOSAVE NEWEST AFTER LOST ACK` and stays out of customer-facing PDFs.

- Area1:6,125ft² ×0.10 =612.50.
- Area2:1,733ft² ×0.27 =467.91.
- Linear:188.264011ft ×0.10 =18.83.
- Extra service54.25 gives tax base1,153.49; GST57.67 +PST69.21 gives **CAD1,280.37**.

Actual live **Single1page** and **Expanded3pages** were downloaded one at a time, rendered, and every page visually inspected. Both diagrams show both priced areas and the full line, with lengths; inactive historical Roofing outlines are excluded. Customer details, rates, taxes and totals match the recovered/source record. A fresh signed-in tab7 reopened the current estimate from history with the same values and no draft choices or writes.

Independent WGS84 geometry and Decimal money checks passed against the saved active Paving scope. `recovered-source.json` is explicitly an active-scope projection for that independent checker; it also records the SHA-256 of the original COMPLETE quote, which was not modified by projection. Existing spherical-versus-WGS84 tolerance0.6% is not a survey-accuracy claim. Restored Street View bytes are excluded by the approved design; the labelled assessment placeholder is expected. Actual aerial/measurements remained available without a new lookup.

Evidence: `qa/live-interrupted-saves-2026-11-02/` contains source/proofs, PDFs, independent output and viewport screenshots. A browser full-page screenshot produced a mixed-layer stitch and was excluded; actual PDF pages and ordinary viewport screenshots are used. Collected console entries contained cloud-browser extension metadata errors, with no application exception observed; no claim is made that the tooling itself is error-free.

## Remaining state

No new reproducible application defect or failed application check remains from this batch. Manual desktop review by the owner and physical-phone/Safari/Messenger touch testing remain pending. No physical device or newly charged live subscription was tested. Keep the current QA session if available; tab7 shows the saved recovered report, tab6 its report after save, and Render shelltab4 is available for scoped verification.

Main remains `c049a04b2ac5cc4df3d5c253fe9ca12f1d85806a`; production remains `dep-db5b726k1f9s73e862ug` at that commit. No production or customer database was accessed or modified. The containing documentation/evidence commit is the next checkpoint; do not deploy it. Live application remains the fully checked `69ab066c`.
