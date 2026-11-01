# Live recovery drafts — November 1, 2026

Continued from b975e036 on recovery application0f78e40f. The owner signed in with the verified QA identity. Exact owner principal, dedicated isolated QA PostgreSQL host/database, recovery service and auto-deploy Off were verified. Only fictional QA job data was edited; main, production, real customer data, account settings, passwords, database connections and allowances were untouched. No runtime fix or deployment was needed.

## Live results

1. Opened the fictional Paving version20 and selected Edit. This rehydrated imagery without another property lookup. Replaced Area2 by drawing four new corners (2,193→1,733ft²), retained Area1=6,125ft² and Linear188.2640110545814ft, set Area2 to0.23, extra service51.75, and new fictional customer/name/phone/email/note.
2. Waited for **Recovery copy saved for24hours**. A read-only database query confirmed exact intended fields and recorded canonical SHA256 fingerprints for the whole quote and all captured fields. Closed the actual tab9. A new tab10 offered Restore; no estimate/PDF was created automatically.
3. Selected Restore. The new tab's acknowledged record had an individual new draft ID. Both canonical fingerprints matched exactly. Counts stayed1estimate/20revisions/23save receipts; monthly allowance rows stayed empty. Correct authenticated owner was confirmed from the page's principal binding.
4. Selected Create once. The saved payload's full quote hash, customer fields, note and extra amount matched. One revision/receipt was added:1/21/24. The recovery payload was deleted immediately. The prior stress estimate remains revision21, and all earlier revisions remain available.
5. Downloaded actual Single1page and Expanded3pages, rendered and visually inspected all4pages. Both contain both active Areas, the saved Linear, matching fictional customer/branding/rates/taxes and total1,200.65. No retained Roofing geometry appears in the Paving PDFs. Independent WGS84 geometry checks and Decimal arithmetic passed for the active Paving scope.
6. Returned to the unchanged workspace and selected Create again. After that retry and both PDF downloads, counts remained1/21/24; no extra persisted save/revision/receipt or monthly usage appeared.
7. Changed only the note to a unique fictional Discard-test marker; waited for server acknowledgement; closed that tab. New tab11 offered the draft. Selected Discard, refreshed and waited for initialization: **Recovery autosave is ready**, zero Restore choices. Read-only SQL after refresh:3minimal closed tombstones,0active drafts,0retained workspace/imagery payloads. Counts remain1/21/24, and the saved estimate retains the original recovered note, not the discarded note.
8. Reopened the saved current estimate from history after Discard. Both Areas, Linear, fictional customer details and1,200.65 remain intact. Tab11 is left open on that saved report.

## Independent calculation and evidence

Area1:6,125×0.10=612.50. Area2:1,733×0.23=398.59. Linear188.2640110545814×0.10 rounds to18.83. Service subtotal1,029.92 +extra51.75 =tax base1,081.67; GST5%=54.08; PST6%=64.90; total **1,200.65 CAD**.

Evidence is in `qa/live-recovery-drafts-2026-11-01`: original/restored/reopened screenshots, both actual PDFs, the saved measurement/pricing snapshot, a repeatable independent checker/output, result/count evidence and SHA256 manifest. The generic fresh-fixture browser verifier initially counted retained inactive manual Roofing history as another charge; this mixed-history evidence uses an explicit active-Paving checker. No quote assertion or runtime safeguard was weakened.

Whole-quote SHA256 before closing =after Restore =saved payload:
`a9abf3d553ed77bd6c0ef1b8d90c7f7b6e09332b5b67c21b7dbb1716b3999466`.
All captured field values before closing =after Restore:
`4c82ae696dea5b26b5610d7b1ff324a1fce0b27e2c9868ec2b9aeded7da5b766`.

## Scope and limitations

- Live QA retains its existing recovery allowance bypass. No live charged-plan deduction is claimed; actual charged fixtures199→200 once, retries unchanged, already passed on PostgreSQL16/18 in full source workflow41358627500. No plan or allowance was changed to manufacture a live charge.
- Street View image bytes are deliberately excluded from recovery drafts. This historical-job recovery used a visibly labelled Property Assessment placeholder; pixel-identical Street View restoration is not claimed. Aerial measurement coordinates/quantities were unchanged, and imagery rehydration did not invoke property lookup or credit consumption.
- The session-only “estimates created” badge displayed2 after opening the report twice. Database counts above establish there was exactly one persisted revision/receipt. This badge was not used as allowance evidence and was not changed in this batch.
- PostgreSQL external access remains blocked. The connector confirmed that it cannot reach the empty IP allowlist; networking was not opened. Database checks used the existing recovery shell with exact host/database assertions and explicit read-only transactions.
- Physical-phone touch/Safari/Messenger remains pending. No new expired-cookie or provider-outage batch was inferred from these tab-close checks.

Recovery remains live at0f78e40f /dep-dbjs3aajnfac738t6vs0, auto-deploy Off. Main remainsc049a04b. The containing documentation/evidence commit is the next checkpoint; do not deploy it.
