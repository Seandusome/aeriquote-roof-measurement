# AeriQuote launch checklist — November 5, 2026

Engineering test evidence is not commercial launch approval. Recovery branch only; no release performed.

## This session's targeted verification

Resumed9a720bd4. Tested source **d3bab94afcd499627f4c8be020c3aec06b070bf1** adds only a focused QA workflow; application code and strengthened test assertions are unchanged.

- [Focused run42088238763](https://github.com/Seandusome/aeriquote-roof-measurement/actions/runs/42088238763), job127459046056: **SUCCESS**. Executed existing full job-revisions suite solely because it constructs the mixed-history state required for the pending assertions. Did not restart the13-suite browser audit or top-up journey.
- Four measured6.951282431430689pt cases were unreadable against the unchanged7pt minimum. Strengthened assertions passed: measured fit, explicit minimumPoints7, readable/points agreement, no Single download, visible reason, Expanded selection, download instruction and unchanged-saved-estimate explanation.
- Expanded downloads completed after the blocks. All existing customer, geometry, active-map-request, pricing, total, revision, old-history, stale-save and allowance assertions remained enabled and passed.
- Independent WGS84/Decimal reconciliation passed17 saved snapshots. Geometry tolerance0.6% is an existing model tolerance, not survey certification.
- Artifact [13442709714](https://github.com/Seandusome/aeriquote-roof-measurement/actions/runs/42088238763/artifacts/13442709714) retains source snapshots, actual PDFs, screenshots and fixture log for14 days. No new manual visual/physical-device approval is inferred.
- Existing application validation42088238447 passed automatically after the workflow-only push. Recovery validation42088238497 also started automatically under repository push rules; its final status is recorded in the resume checkpoint. These automatic runs were not a manually repeated full browser audit.
- Application source remains equivalent to7a467e1d. Prior13/13 browser evidence and completed top-up results are reused. The strengthened-assertion browser gap is now closed.

## Completed and verified

- Measurement/pricing/revision integrity: saved scope, inactive outlines excluded, immutable old revisions, interrupted-save/retry handling, and independent geometry/Decimal reconciliation. Existing browser run41929129629 passed13/13 on application7a467e1d; application41929129544 and recovery41929129584 passed.
- PDF readability: unchanged7pt floor; ordinary Single succeeds; dense Single explains the block and selects Expanded; Expanded exports retain saved work. Existing ordinary/dense1440/390 checks also preserve quote snapshots and exact imagery/overlays.
- Payment-free top-up journey: monthly/Bonus exhaustion → simulated25-pack → employee measurement/save → owner reopen/revise and four PDFs; final purchased balance24, one measurement plus included estimate, no extra charge from retries/revisions/downloads. Existing browser126921231872 and original final-source SQLite/PG16/18 evidence reused. No real payments implied.
- Recovery/account/permission checks remain backed by the recorded scoped evidence; no claim that every live or real-device scenario has passed.

## Built but undeployed

- Latest PDF readability protection and Expanded amount/quantity wrapping fixes.
- Source allowance ledger, order/event idempotency, attributable-unused refund decision simulations and controlled writer cutover/rollback safeguards.
- Owner purchase/history screen remains explicitly disposable-QA-only, with simulated fulfillment and no live checkout.
- Before promotion: approve exact source/environment, review schema/writer compatibility and cutover/rollback procedure, then separately authorize deployment. Last documented recovery runtime194c435b is historical; it was not freshly read here.

## Manual desktop and physical-phone testing

- Sean's desktop sign-off: first-time signup/setup → first measurement → prices/taxes/customer → save/reopen/revise → ordinary Single and dense-to-Expanded download; include attached garage, multiple areas and linear.
- First-user simplicity review: one obvious next action and clear blocking explanations. Record findings; no layout/features are authorized by this checklist.
- Physical iPhone/Safari and Android/Chrome: touch tracing/drag/Save/Cancel, keyboard/scroll, connection interruption/login recovery, PDF download/open/share and messaging/email handoff. Phone-sized Chromium automation is supporting evidence, not physical-device approval.
- Inspect actual PDFs for readable details, complete imagery/outlines, customer text and totals. Manual approvals remain pending.

## Stripe integration — pending separate work

- Establish/verify merchant account and bank onboarding; approve sandbox scope.
- Implement and test checkout/subscriptions, verified server-side notifications, merchant/test-live/amount/currency checks, idempotent fulfillment and paid-status synchronization with the existing ledger.
- Verify billing-period/renewal, failed-payment/cancellation/reactivation, pending/lost-response/replay handling, receipt/history and paid-but-unfulfilled reconciliation.
- Configure confirmed USD pricing and jurisdiction-specific tax treatment; validate operational tax/refund policy with the appropriate business advisers. Manual refunds must remain attributable to unused purchased units.
- Separate reviewed approval for live keys/checkout/real charges. Current simulated evidence does not establish real billing readiness. No Stripe work was performed this session.

## Other unresolved launch requirements

- Imagery commercial clearance: obtain applicable written SaaS tracing, retained measurements, imagery/customer-PDF/history rights, confirm launch-area coverage and actual field alignment/accuracy. Existing vendor correspondence/documents are not a completed production integration approval. Spexi stays paused.
- Managed database recovery: verify usable backup/PITR points, retention and approved new-instance restore drill with measured recovery objectives. Disposable backup tests do not prove hosted disaster recovery.
- Release/access controls: production CI/approval gates, explicit release owner, compatible rollback/build retention, correct isolated database mapping and credential/network-scope review. Historical proposals are not evidence these settings are applied.
- Operations: monitoring/readiness, privacy-safe error reporting, verified alert delivery and named primary/backup responder; publish support and incident process.
- Retention/customer terms: reconcile published policy with implementation. Approved October15 policy is six months full imagery/PDF content and one year lightweight estimate details; later supplier correspondence referenced a year of PDFs. Confirm intended policy, expiry behavior across revisions, backup handling and customer wording before promising retention or enabling cleanup.
- Confirm production privacy/terms, customer support readiness, launch geography and real-world measurement limitations at owner sign-off.
- **Auto-deploy: UNVERIFIED this session.** No setting changed; do not substitute historical OFF for a direct current inspection.

Sources: [latest resume](RESUME_HERE_2026_10_31.md), [top-up evidence](QA_TOPUP_COMPLETE_JOURNEY_2026_11_04.md), [top-up implementation](AERIQUOTE_TOPUP_IMPLEMENTATION_PLAN_2026_11_04.md), [launch blockers](LAUNCH_BLOCKERS_2026_10_31.md), [release/monitoring proposal](MONITORING_DEPLOYMENT_APPROVAL_PLAN_2026_10_31.md), [retention policy](ESTIMATE_RETENTION_POLICY_2026_10_15.md), [usability review](QA_NEXT_USABILITY_REVIEW_2026_11_03.md). Older unresolved entries remain pending confirmation; no fresh vendor/legal/infrastructure audit was performed.
