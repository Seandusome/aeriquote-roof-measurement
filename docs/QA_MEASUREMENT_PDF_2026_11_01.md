# Measurement and PDF integrity — November 1, 2026

## Verified environment

Started from remote recovery HEAD `37d4e658e192af51c21293dbbece2ad5e565d02c`. Recovery service `srv-db5a2g5ckfvc739fui70` remained LIVE at `4f2b233fccc9a8a2a44cfdd3bc7449195190f91d`, deployment `dep-dbjqlnijnfac738poig0`, auto-deploy Off. The already authenticated fictional QA owner and isolated PostgreSQL18 database `dpg-dbj4f7lg1s2s73eob8t0-a` were used. No connection, account, password, allowance, imagery integration, pricing or runtime code changes. Main remains `c049a04b2ac5cc4df3d5c253fe9ca12f1d85806a`; production/customer data untouched.

Read the active-scope and final October31 QA reports first. Historical resolved defects were not treated as current failures.

## Fresh live exports and visual review

14 actual browser-generated PDFs (21 pages) saved under `docs/qa/integrity-2026-11-01/`. All pages rendered with Poppler and visually inspected. This round closes the previously unverified fresh desktop PDF exports for the corrected revisions; it does not establish physical-phone compatibility.

| Industry / revision | Active measurement | Subtotal | 5% tax | 6% tax | Total | Single / Expanded |
|---|---|---:|---:|---:|---:|---|
| Roofing previous1 | 7,348.380392728047 ft²,22.6° pitch, one roof | $734.84 | $36.74 | $44.09 | $815.67 | PASS / PASS |
| Commercial previous14 | Areas6,125+6,227ft²; Linear188.2640110545814ft at$0.25 | $1,282.27 | $64.11 | $76.94 | $1,423.32 | PASS / PASS |
| Snow previous15 | Same Areas/Linear; Linear$0.10 | $1,254.03 | $62.70 | $75.24 | $1,391.97 | PASS / PASS |
| Pressure previous16 | Same Areas/Linear; Linear$0.10 | $1,254.03 | $62.70 | $75.24 | $1,391.97 | PASS / PASS |
| Paving previous17 | Same Areas/Linear; Linear$0.10 | $1,254.03 | $62.70 | $75.24 | $1,391.97 | PASS / PASS |
| Landscaping original current | Same Areas/Linear; Linear$0.10 | $1,254.03 | $62.70 | $75.24 | $1,391.97 | PASS / PASS |
| Paving new current after repeated retrace | Areas6,125+2,815ft²; Linear188.2640110545814ft at$0.10 | $912.83 | $45.64 | $54.77 | $1,013.24 | PASS / PASS |

All active priced geometry is visible in each PDF. Surface reports contain both purple Areas and the independent teal Linear, excluding historical orange roof/pitch outlines. Roofing retains its orange roof and confirmed pitch without surface outlines. No blank diagrams, clipping of the measurements/totals, wrong industry titles, stale quantities or stale retrace outlines found. Expanded exports have the large aerial on page1 and details on page2; Single exports have one complete page. Street View proportions and imagery attribution remain present. Decimal reference arithmetic, independent of application pricing code, agrees for all seven cases; exact reference inputs/results are in `independent-pricing.json`. Area/Linear geometry is fictional QA scope, not a surveyed measurement certification.

## Live history and retrace checks

Reopened in mixed order: latest Landscaping → original Roofing → corrected Commercial → Snow → Pressure → Paving. Original Roofing remained $815.67 after surface revisions. Commercial Area2 REMEASURE/CANCEL repeated twice retained Area1=6,125, Area2=6,227, Linear188.3 and total$1,423.32; no save/write of those canceled proposals.

Paving Area2 REMEASURE/SAVE repeated twice:6,227→2,382→2,815ft². Area1 stayed6,125; Linear stayed188.3ft and priced at existing$0.10. Intermediate total$965.18; final total$1,013.24 agrees with independent arithmetic. Created exactly one completed fictional saved revision after the second retrace, at21:20:15UTC. History now has current plus18 previous versions (19 OPEN ESTIMATE controls), rather than a duplicate property. Earlier versions were not overwritten. Both new-retrace PDFs show the final2,815ft² outline and exclude6,227/2,382ft² stale outlines. Reopening original Roofing then previous Paving17 after this save preserves original7,348ft²/$815.67 and12,352ft²/$1,391.97 respectively.

## Allowance workflow resolution reconfirmed

Original failure41349535401 was a date-dependent test fixture: real current-month usage was exhausted before a hardcoded November2 fresh-month assertion. Fix7e01cec2 freezes only the disposable allowance fixture to October20, preserves/strengthens the assertion and checks separate October/November counters. No monthly allowance runtime change.

GitHub API reconfirmed full recovery run41350107603 SUCCESS and application run41350107613 SUCCESS at7e01cec21aa29f4e67e36f648c81ad62c6e38c2f. Recovery plus PostgreSQL16/18 all passed, including previously skipped login diagnostics. These are the verified full workflow runs; this evidence-only checkpoint skips CI and does not change application source.

## Download tool limitation observed

When attempting two exports inside a single browser tool call, the second download twice returned a path that did not exist in either shared filesystem. Separate single-download calls produced actual non-empty files successfully. No application download error was demonstrated. Missing-path files are not counted as evidence. All14 included PDF blobs were byte-count checked, hashed, rendered, visually reviewed and checked against their uploaded Git blob SHA. `manifest.json` records filenames, sizes, pages, SHA256 and Git blob hashes.

## Remaining scope

No reproducible application defect was found; no speculative fix or deployment. This batch verifies desktop saved-revision reopening, PDF exports and repeated Area retrace Save/Cancel. Physical iPhone/Safari/Messenger touch behavior, actual expired-login recovery with unsaved work, a fresh Linear-drag Save/Cancel round and new traces independently created in every industry remain outstanding (earlier controlled/desktop evidence remains valid within its stated scope). Do not mark those passed from these PDF checks.
