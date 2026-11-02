# Interrupted-save desktop QA — November 2, 2026

Resumed from checkpoint0d940e35. Remote recovery HEAD and live deployment metadata matched0d940e35 /0f065b9d before work. Read the latest resume and desktop closeout. This batch focuses on additional response-loss cases; prior completed tab-close/PDF checks were repeated only as regressions for the changed save queue. No owner interaction was requested.

## Reproduced and fixed

1. A successful HTTP200 estimate response with truncated JSON, an empty object or missing save identity/version incorrectly cleared pending work and marked the workspace clean. The real save function now requires a readable object with nonempty estimate ID/version before marking success. A malformed response keeps the frozen operation/payload, unsaved warning and blocked report; receipt confirmation/idempotent retry can finish the original save.
2. A malformed HTTP200 autosave acknowledgement incorrectly announced a recovery copy and assigned an undefined version. Autosave now validates the next integer version and numeric expiry before announcing durability.
3. An autosave accepted by the server with a lost acknowledgement could strand later edits on a version conflict. The queue now retains that uncertain write in memory, retries its exact version/payload first, then acknowledges the newest workspace. A local revert to the earlier acknowledged value must also reconcile the intervening uncertain write. Temporary account rejection retains that retry identity; returning to the original account can continue. Definitive account/stale conflicts remain blocked, and background retries never fork a consumed draft.

Only the existing client save/recovery behavior changed. No schema, pricing, allowance, imagery, authentication configuration, account settings or new UI feature changed. Customer information remains out of browser persistent storage; the uncertain write exists only in the current tab's memory.

## Validation

- Controlled tests execute the actual save function and recovery client. Old code fails the new assertions; fixed code passes. Evidence is under qa/interrupted-saves-2026-11-02.
- Local SQLite API checks passed: individual/business/employee isolation; mismatched-account writes blocked; interrupted/lost-response replay exactly once; atomic draft deletion; stale editors; concurrent saves; rollback and allowance protection; pricing validation.
- Independent WGS84/Decimal checks passed for the restored Snow job and new interrupted-response job. Both restored Snow PDFs were rendered/visually checked: Single1page, Expanded2pages, two659ft² areas and62.0ft line, customer name/phone/email, subtotal138.00 +GST6.90 +PST8.28 =153.18 match the restored source. Synthetic aerial, no live-provider imagery claim.
- Final application commit **69ab066c67cb429d4e12c8dad2d902140fbbc405**: full recovery **41505173423 PASS**, PostgreSQL18 job125482504270 PASS and PostgreSQL16 job125482505092 PASS; recovery job125482504815 PASS. The manual-roofing assertion and EVERY subsequent check executed successfully: vector Python/client/download/full-report, API-cost routing and logo cache. No test steps skipped. GitHub action cleanup completed; final workflow success verified.
- Application **41505173311 PASS**. Actual Chromium **41505173632: all8jobs PASS**, including draft-races125482506545 and roof-exports125482506688. Fresh desktop and phone-sized layouts are automated coverage, not physical-phone testing. Full job/step results are saved in workflows.json. No unresolved CI failures remain.
- New Chromium response cases prove the newest acknowledged note survives the stopped malformed-PUT injection; truncated successful estimate JSON blocks report and preserves exact work; retry confirms the original receipt without another revision. Concurrent saved editors retain the stale second workspace/base version with409; delayed Restore cleanup retains newer original work; explicit Create from the original consumed tab succeeds. Charged exactly-once allowance proof is from disposable PostgreSQL fixtures, not the live QA bypass account.

## User-reported manual Roofing exporter fixture failure

Run41503616072 failed at test_manual_roofing.cjs:44 with1/2 exports. Instrumented reproduction identified Single:0 saves after Single,1 after Expanded. The mock returnedHTTP200 `{}` for estimate saving. The new real acknowledgement guard correctly rejected it; `showCustomerEstimate` left the report unopened and pending work intact. Single then entered its map-canvas fallback with an unprepared report and the synthetic canvas had no DOM parent (`clientWidth` was undefined). Expanded's generated synthetic pages still reached its save sink. The immediate error was canvas setup, not the fixture's price assertion. This is an outdated success fixture exposed by the new guard, not evidence of a real Single exporter defect.

Fix: the disposable estimate-POST mock returns the actual API contract's nonempty `id` and `version`. Added assertions require an opened, acknowledged real customer report and exactly one save from EACH named layout. The original `exports.length===2` and unchanged quote assertions remain. Local manual Roofing and downstream vector-full-report checks pass. No PDF application code or safeguard was weakened. A new actual Chromium suite covers three roof sections: adjacent facets plus detached garage at22.62/0/45 degrees; both real download formats and unchanged stored/customer/pricing data are required. Actual PDFs from final application commit69ab066c were downloaded, rendered and visually checked: Single1page, Expanded2pages. All three sections/pitches appear; customer name/phone/email agree; pitch-adjusted area2,287.301677ft² (display2,287), rate0.10, subtotal228.73 +GST11.44 +PST13.72 =253.89. Independent WGS84/Decimal checks pass. Evidence under qa/interrupted-saves-2026-11-02/roofing. No real provider imagery or physical-phone claim.

A separate injected-failure browser case was intermittently asserting while a background PUT still consumed its deliberately broken response. The test now stops injection, drains route handlers, waits for recovery, and asserts that the server acknowledges the exact NEWEST note before proceeding. The original recovery/preservation assertions remain. This was a harness synchronization change; the runtime queue was not relaxed.

## Deployment and limits

No deployment was started. Recovery deployment metadata remains0f065b9d /dep-dbjsosetlv9c73e6ck3g and auto-deploy Off. QA PostgreSQL18 resource dpg-dbj4f7lg1s2s73eob8t0-a is available with its external IP allowlist still empty. The previous cloud-browser sessions are unavailable; the recovery Render shell opens a login page. Consequently, the running process/database binding could not be independently reasserted internally today. Preserve the closed database network; do not deploy until that binding is verified again.

All executed tests use disposable loopback QA fixtures and fictional data. No live QA estimate/customer row was changed. Main, production and customer data were not modified. Physical-phone/Safari/Messenger testing and the owner's manual desktop review remain pending. Current fixes are checkpointed on recovery, not live.

## Resume checkpoint

The containing documentation/evidence commit is the final checkpoint. Source69ab066c is fully checked but not deployed; live remains0f065b9d. Resume notes link here. Tracked code has no unfinished edits; only generated interpreter caches may remain outside the checkpoint. Stop after saving it.
