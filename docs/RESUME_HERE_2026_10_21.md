# AeriQuote — end-of-day resume checkpoint, October 21, 2026

## Stop state and operating rules

Work stopped at Sean's request after Batch 4. Do not start another batch until asked. Work ONLY on `landscaping-multi-area-recovery-oct11`; never merge, reset, push to or deploy main. Preserve approved industry headings, measurement tools, pricing, branding, imagery, PDFs, account access and all Batch 1–4 safeguards. Keep AI Trace removed. Never use real customer or Ali demo accounts for QA/concurrency/destructive tests. A customer estimate must not silently proceed from incomplete, mismatched or unverified measurements.

Repository: Seandusome/aeriquote-roof-measurement. Test service: aeriquote-commercial-test, `srv-db5a2g5ckfvc739fui70`, workspace Shingle Guard `tea-daaurjp5efls7391kvj0`, https://aeriquote-commercial-test.onrender.com/. Auto-deploy is on commit. Do not trigger an extra deploy after a push. PostgreSQL is the deployed storage backend.

## Authoritative GitHub checkpoints

| Checkpoint | Meaning |
| --- | --- |
| c5367155cd775a7ed6165b1275fa9d1e56c7fd23 | Complete recovery source tree restored after incomplete-tree deployment failures; Batch 1 fixes retained |
| 34a6e522de3a2712feb4696d8f8096bfc1b840ce | Batch 1 checkpoint: 45 checks and actual seasonal save/PDF |
| 7a8d88d9bbe992da5c4c7d6939fa5414094a38ec | Batch 2 geometry, overlap, identity and completeness guards |
| 25a571ce863827b5427e80183a300c21fa4120e5 | Final Batch 2 checkpoint and explicit six-industry mobile layout matrix |
| dd41831b44ca6e95e78d6e709ad3929395425145 | Batch 3 independent server pricing, automatic roof coverage checks and account tests |
| 991b410e6e1dc766a35ae78d95dbcbd31c1dac85 | Expanded PDF photo/date pagination fix |
| a62cd85c058fcf0056cb01e9bdd498dc045a4564 | Final Batch 3 actual two-page PDF verification |
| 11827febde8bfd0ba2dc3f5dce2bb6f88b9eabc8 | GitHub/Render reliability cleanup, obsolete patch retirement, release-file guard |
| 152c9b11341b94c125a62eb549ada13461fa44f0 | Batch 4 transactional retry receipts, quota rollback, concurrent job-data protections, session fixes, precision and PostgreSQL CI |
| a1f58585700a8a43d8a28fa09b3776c0470bef71 | Address-input retention and prevention of quotes from a changed address with old measurements |
| 13b5ba9e2f0f53954f62b4a72384c136b40da79e | Verified final Batch 4 evidence checkpoint before this resume document |

This document's commit is the final end-of-day checkpoint and a child of13b5ba9. It changes documentation only. Its hash is reported in the final handoff, not embedded recursively here. All application files remain identical to13b5ba9.

At end-of-day inspection,13b5ba9 was on GitHub and LIVE on Render: `dep-dbcjpvrm8hqs73ad81ug`, finished2026-10-21T22:31:28Z. GitHub application run39686978361 and full regression run39686978406 both completed successfully; the latter includes successful real PostgreSQL job119523422217. The final documentation commit triggers the same automatic checks/deployment; verify their terminal results before reporting the end-of-day save complete.

Main was read only to record its ref: `c049a04b2ac5cc4df3d5c253fe9ca12f1d85806a`. No main write/checkout/merge/deploy was performed. Check the ref remains unchanged after publishing this document.

## Completed work to preserve

### Batch 1 and recurring estimates

New estimate saves reject disagreeing top-level/pricing totals, contradictory tax sums, invalid/nonfinite/negative quantities and rates, malformed snapshots and roofs flagged for review before revisions or credits are consumed. Explicit zero/free service remains valid. Recurring periods persist for Snow Removal, Landscaping and Commercial; they label the quote amount and never multiply it by visits or months. The real estimatePeriodValue helper is included in isolated test harnesses.

### Batch 2

Independent server geometry recalculates polygon areas, linear lengths and manually pitched roof quantities, checks required coordinates and repeated totals, and blocks incomplete snapshots. Duplicate/overlapping service areas are blocked, while adjacent boundaries and disjoint regions remain valid. Client area arithmetic uses a local origin and unwraps longitude to avoid small-polygon cancellation and dateline failures. Independent GeographicLib/WGS84 references cover several latitudes; normal spherical approximation in those fixtures differs by up to about0.44%, not survey accuracy. Invalid amount-paid values are rejected. Case-insensitive owner/employee email collisions are checked in signup and owner creation paths.

### Batch 3

pricing_integrity.py independently calculates Decimal line charges, discounts, extras, included/added taxes and totals. Client service charges round to cents before summing. Every submitted calculation field and quantity must agree; forged mutually consistent totals are rejected. Automatic roofs require outline, whole-building footprint/coverage and consistent sections/pitches; missing data cannot be hidden by clearing a client warning. Duplicate automatic buildings and unflagged partial roofs are blocked. Historical automatic previews rerun coverage review. Head Office owner-email edits reject employee-email collisions. Expanded PDF photos and dates travel together, with readable continuation and no date-only third page.

### Reliability cleanup

Investigated GitHub runs39674947826,39674947755,39674947843,39674947854 and39669385233. Four obsolete one-shot correction workflows/scripts were retired only after checking their intended fixes were already present and covered. The fifth was the stale test-harness helper, already fixed. Render failures66bba8a and2fbb280 both lacked requirements.txt because their Git trees were incomplete. Complete-tree restoration and subsequent successful deployments resolved them. check_release_files.py now verifies17 essential deployment files; active recovery checks are read only and branch guarded. Historical red runs are retained honestly.

### Batch 4

Account-scoped transactional receipts make estimate and property lookup retries idempotent, including replay after a response was lost and a newer edit exists. A reused operation identifier with changed contents returns409. Identical saves do not create redundant revisions. New browser editors use version hashes/If-Match to reject stale saves. Pricing edits preserve current booking/date/payment fields; those dedicated endpoints share the owner lock to prevent lost concurrent updates. Failed/invalid provider lookups roll back credit reservations. Same lookup retries run the provider once and debit once. Save requests are single flight, freeze their contents, retain retry identity and abort an unresponsive POST after30seconds. JSON session expiry returns401; failed saves cannot open the customer estimate.

Typing another address retains the loaded job/geometry/customer and blocks quote creation until the new property is accepted or original address restored. Request failure leaves the prior workspace intact. Unsaved changes warn before refresh/navigation, but there is no crash/forced-discard autosave. Employee creation serializes duplicate checks. Disabling an employee revokes old sessions once, so reactivation cannot revive them. PostgreSQL estimate/revision amount and area columns widen from REAL/float32 to DOUBLE PRECISION, avoiding customer-visible cents lost on large new quotes. Historical rounded column values are not backfilled.

## Verification already completed — do not repeat without a reason

- Batch 1:45 workflow commands after harness correction; actual seasonal quote/PDF verified.
- Batch 2:47 commands plus targeted tightening checks; explicit six-industry320/390/768px layout matrix,18 combinations with no page overflow. These were CSS-width authenticated browser iframes, not physical touch devices. Actual320px mixed measurement edit/cancel/save/rate change/reload and both PDFs verified.
- Batch 3:52 full commands after pagination fix;70 actual-client pricing fixtures across six industries plus500 seeded arithmetic comparisons (seed31). Roof completeness and integrated QA account/reset tests passed. Browser mouse line/area dragging, cancellation and line save verified; not touch input.
- Batch 4:55/55 final local commands passed after address-handler fixes. New targeted Python/JavaScript failure tests and repeated actual PDF-exporter calls passed. GitHub application/full checks passed for152c9b1,a1f5858 and13b5ba9.
- Actual PostgreSQL16.15 in a disposable GitHub postgres:16 service passed real Flask/DB concurrency, rollback, retry, business isolation, job-field and employee-session tests. This is not the old fake PostgreSQL adapter. The precision probe confirmed a1.5-cent float32 loss for1234567.89; widened new-record storage passed.
- Controlled network tests cover response loss after commit, retries, timeout abort, rapid actions,401,409 and unchanged workspace. Network/provider responses are fixtures; physical devices and live cloud-browser network outages were not simulated by claiming them physical.

## Last actual browser/PDF evidence

Only the existing AeriQuote QA account `sean@shinglextra.com` was used. Saved Landscaping job: `QA TEST Landscaping Area plus Linear DO NOT SEND`,2301 Avenue C North,Saskatoon,SK,Canada. Do not send it to anyone.

Invalid street999999999 QA NONEXISTENT STREET produced an actual Google mismatch409. The16,372ft² area,454.8ft line,rates,customer and original loaded address remained; quote creation stayed disabled. Restoring original address/city/province restored pricing without reloading the property. QA-only internal notes saved and survived reload/reopen: `QA TEST Batch 4 recovery verification - DO NOT SEND`.

Verified quote: area charge1964.64 at0.12/ft²; line charge318.35 at0.70/ft using saved underlying length; additional service25.50;10% discount228.30; taxable subtotal2080.19;5% tax104.01;6% tax124.81; total CAD2309.01 per season. Displayed length is rounded to454.8ft. Reopening/editing/resaving unchanged contents retained current timestamp22:27:49 and17previous versions: no version18/duplicate revision.

Actual downloaded Single PDF has1page; Expanded has2pages. All3pages were rendered and visually inspected: geometry, rates, discount, extra, taxes and2309.01 seasonal total agree. Street View caption stays with photo. Raw browser download IDs69a7c725-101a-4ab3-a5ae-e8dd087917df and5d05db82-b142-4896-8832-6730fdd613e5; screenshot aq-batch4-verified.jpg. These raw scratch files are supporting evidence, not the durable source of truth. Durable evidence is in the batch documents and GitHub run records.

## Outstanding issues, limits and next priorities

1. Test simultaneous public signup versus employee creation across both identity tables. Current employee-only identity locking does not prove that combined race safe. Use isolated PostgreSQL/QA identities only.
2. Verify real expired-login recovery with a measurement draft, including sign-in in another tab and retry. Automated401/revocation tests passed; this live workflow has not been performed.
3. Define/test crash and deliberately forced-refresh recovery. Current guard warns, but local drafts are not automatically persisted if the user confirms discard or browser crashes. Test image decode/unavailability after a property request has already been accepted; do not claim complete workspace recovery for that later phase.
4. Small polish fixes: street-number mismatch error currently repeats identical city/province rather than naming the unmatched street number; quote remains safely blocked. Expanded aerial numbered leader crosses the area label. History recurring suffix/helper wording watch items remain documented in earlier batches; audit current behavior before changing approved text.
5. Physical iPhone/Android touch placement/drag/pinch/rotation/keyboards and native PDF/print remain unverified. Browser mouse and CSS-width checks do not establish physical-device behavior.
6. Roof ground truth/Pinehouse whole-building coverage remains unresolved and guarded. Provider geometry cannot independently reveal a building absent from all supplied data. No survey-grade accuracy claim or automatic scaling of missing roof sections.
7. Live reset-email delivery was not retested in these batches. Password/reset simulations use mocked delivery and isolated identities. Do not change real passwords/accounts for QA.
8. Legacy API pricing callers without If-Match still have last-write behavior with history; new browser editors use conflict detection. Lookup owner locks are held during upstream provider requests, potentially delaying writes for that business. Old PostgreSQL column values already rounded by float32 cannot be recovered just by widening the column.

Do not add payments/features or merge main as part of resuming these priorities unless Sean explicitly asks. No tests should silently manufacture a quote from incomplete data.

## Working tree, environments and safe publishing

End-of-day inspection found no uncommitted application/source work. Only generated untracked __pycache__/*.pyc files remain; leave them uncommitted. Do not git add everything or delete unrelated files. All important Batch 1–4 source, regression scripts, workflows and reports are committed.

Local commits and GitHub connector commits have different hashes because they were created separately, but complete Git trees were compared and matched. Do not reset/rebase away verified work to make their hashes match. Local repo at save time: /workspace/scratch/c13e42512364/aeriquote; local equivalent of13b5ba9 is1b55edb. Reacquire a fresh checkout of the recovery branch if scratch disappears.

Critical publishing rule: this connector previously did not reliably preserve base_tree_sha. Build the complete explicit recursive file tree, preserving all source/assets/reports, before create_tree. Use expected_sha lease on the recovery ref, force:false. Fetch and compare resulting tree to the tested local tree. Never publish a documentation-only partial tree or repeat retired patch scripts. Wait for actual Render live status and completed successful GitHub checks; accepted/queued is not success.

Local QA venv at /workspace/scratch/c13e42512364/qa-venv. NODE_PATH used /workspace/scratch/6aef46eaaafc/aeriquote/node_modules. Full regression workflow .github/workflows/validate-landscaping-recovery.yml is authoritative. New PostgreSQL test accepts QA_POSTGRES_URL only for localhost/127.0.0.1 database aeriquote_qa; never point it at DATABASE_URL/customer storage. Avoid printing credentials.

A free unused Render database aeriquote-qa-batch4-isolated (`dpg-dbcjg2brjlhs73dn1g7g-a`,expires2026-11-20) was provisioned during Batch 4. Empty external allowlist blocked connector access; no data was written and no access rules weakened. Actual PostgreSQL testing used disposable GitHub services instead. Review whether to retain/remove this unused QA resource later; do not alter the existing customer database.

## Detailed supporting reports

- docs/QA_INTENSIVE_BATCH1_2026_10_21.md
- docs/QA_INTENSIVE_BATCH2_2026_10_21.md
- docs/QA_INTENSIVE_BATCH3_2026_10_21.md
- docs/RELIABILITY_CLEANUP_2026_10_21.md
- docs/QA_INTENSIVE_BATCH4_2026_10_21.md
- docs/QA_COMMERCIAL_LANDSCAPING_MONTHLY_2026_10_21.md
- docs/RECURRING_ESTIMATES_2026_10_21.md

Resume by reading this document and checking current recovery HEAD/status before acting. Do not repeat completed fixes or reinterpret old pending notes as current failures when newer batch evidence supersedes them.
