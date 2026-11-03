# PDF amount wrapping fix — November 3, 2026

Resumed checkpoint **00e6db5e**. Application source **1cd73b65e973cfd135da9f7cabbc6f4510fe68c3**. **Undeployed**: live recovery remains **194c435b377dbcb23ad24a422c63763fcd931ed4**, deploy **dep-dbl5m4lbedkc73ekek60**. Render service/deploy freshly read-only checked; auto-deploy OFF. No connection, account, environment, main, production or customer-data changes. All new jobs and imagery were fictional on disposable loopback QA with DATABASE_URL blank and a temporary SQLite database. The isolated hosted QA database was not queried or changed in this batch.

## Reproduction and smallest correction

Reviewed the preserved live Expanded page showing `$293.8` then `2`. Real Chromium/exporter control, with only the two new CSS rules removed, reproduces **AMOUNT_LAYOUT wrapped $293.82** and intentionally fails. Evidence: `qa/pdf-amount-layout-2026-11-03/red-control.log`.

Cause: pricing rows use flex layout; Expanded gives blocks inherited `overflow-wrap:anywhere`. With a long description, the currency child could shrink and break between digits. Two scoped CSS rules now let the description shrink/wrap in remaining space and give the amount `flex-shrink:0`, `white-space:nowrap`, `text-align:right`. Both the source pricing panel (used by Single export) and Expanded clones use the same rules. The pricing-panel class selector survives the phone Single export removing element IDs; both widths are explicitly covered. No text truncation, calculations, rounding, payload, validation, measurement, image or pagination algorithm changes.

## Checks and inspected PDFs

Added `scripts/test_pdf_amount_layout.cjs`, reusing every existing prelaunch browser assertion. All three cases run at both1440 and390px widths. It creates/saves/reopens real fictional Roofing estimates at desktop1440 and phone390 widths, exports both layouts, asserts every complete pricing description/note/amount reaches capture in the same order, checks text ranges remain on one line for amounts and that columns do not overlap or overflow. Existing snapshot/customer/branding preservation and JavaScript-error checks remain. The new three-case regression is included in the existing roof-exports CI job; its path triggers that workflow. The disposable runner permits this new test target.

| Case | Content | Single | Expanded |
|---|---|---|---|
| Original description | Recorded long description with $293.82 extra | PASS, 1 page | PASS, 2 pages |
| Long text / large amounts | Complete repeated description and $999,999,999.99 extra; $1,110,000,079.29 total | PASS, 1 page | PASS, 2 pages |
| Continuation | Same large valid saved pricing plus 15 explicitly nonbillable DOM-only pagination notes; monetary rows pushed onto continuation | PASS, 1 page | PASS, 4 pages |

Twelve final PDFs / twenty-two rendered pages inspected. Description wraps naturally, complete currency remains aligned, headers/footers and continuation rows intact. Full-size critical pricing pages also inspected. Single retains its existing fit-to-one-page behavior; deliberately dense notes reduce its print size. Expanded is the readable multi-page layout for that stress case. No new Single pagination feature added.

The note blocks are export-only layout fixtures, not saved charges, measurements or customer records. Saved/reopened pricing remains independently reconciled: ordinary case roof $71.44 + extra $293.82 = base $365.26; taxes $18.26/$21.92; total $405.44. Large case roof $71.44 + extra $999,999,999.99 = base $1,000,000,071.43; taxes $50,000,003.57/$60,000,004.29; total $1,110,000,079.29. All six saved payloads passed independent WGS84 geometry and Decimal half-up reconciliation. This batch uses a different disposable roof; it does not replace the previous live $407.71 boundary evidence.

Local regression PASS: `test_expanded_pdf.cjs`, `test_phone_pdf.cjs`, `test_manual_roofing.cjs`, `test_price_rounding.cjs`, Python syntax. No assertion weakened or expected value changed. Initial environment-only missing-module setup was resolved using existing isolated dependency folders; no application dependency change.

## Required CI on final source

Final-source workflows completed SUCCESS: application **41732984453**, recovery **41732984504** including PostgreSQL16/18, browser **41732984587 (10/10 jobs)** including the new three-case desktop/phone PDF regression. No unresolved automated failures. The red control is an intentional negative test, not a failing CI job.

## Evidence and next step

Evidence: `docs/qa/pdf-amount-layout-2026-11-03/` contains the twelve PDFs, all rendered pages/contact sheets, exact saved source payloads, capture checks, independent results and red control. Two pre-existing untracked PDF copies remain untouched and excluded from the checkpoint.

No deployment authorized in this batch. Owner desktop review and physical-phone testing remain pending. At pause, leave live194c435b and auto-deployOFF. Next step is Sean's review of the corrected Expanded sample; deploy only after separate authorization and a fresh QA binding check. Do not expand into unrelated usability, imagery or historical PDF investigations.

Checkpoint is the documentation commit containing this report. Stop after saving it.
