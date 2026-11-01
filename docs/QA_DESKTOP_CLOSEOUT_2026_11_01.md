# Desktop launch-readiness closeout — November 1, 2026

Continued from901c8085 for a bounded desktop-only batch. No new features or manual testing requested from the owner. Physical-phone testing remains pending. Earlier tab-close/PDF/Discard work was not repeated manually; regression workflows ran because the save/recovery path changed.

## Fixed — two reproduced multi-tab defects

**Late Restore cleanup could delete newer acknowledged work.** Reproduction against the actual901c8085 application in a disposable database: tabB reads source v1; tabA acknowledges newer v2; tabB acknowledges its separate copy of v1; tabB's delayed source DELETE removes v2. The new API assertion failed on old code. Restore cleanup now supplies the version it read. Under the existing account transaction lock, cleanup only closes that exact open version. A newer source stays recoverable and the restored copy remains separate. Cleanup also leaves an already-committed tombstone/save-operation receipt intact, preserving lost-response confirmation.

**The original tab could not explicitly save later edits after another tab consumed/discarded its draft ID.** A controlled client reproduction against the901c8085 JavaScript failed: background autosave returned409 for the closed ID, and Create could never progress. An explicit Create now re-acknowledges the current workspace under a fresh tab-specific draft ID only for the server's typed `draft_closed` response. The pending save operation and base version remain unchanged. Background retries never fork/resurrect discarded work; account and stale-version conflicts remain blocked. No UI feature, pricing, allowance, imagery integration or schema migration was added.

## Passed

Source runtime commit **0f065b9de44b7ad8e9a90ad0c78ad73b43e515d6** (fix6f57b0f3 plus independent-editor fixture setup).

- Full recovery **41362491708** PASS: recovery125015637713; PostgreSQL16/18 jobs125015637876/125015637930. Includes charged-save recovery, individual/business isolation, conditional source cleanup, lost-response receipt preservation and every downstream regression.
- Application **41362491712** PASS.
- Actual Chromium **41362491734**, all7jobs PASS, including new draft-races job125015638060. New cases actually executed: delayed Restore cleanup preserves the newer acknowledgement and older copied snapshot; explicit Create after a remotely closed ID saves exact later edits; two concurrent saved editors permit the first save once and reject the stale second with409 while retaining its acknowledged workspace/base version.
- Controlled client queue checks: original pending operation/base version retained, no background resurrection, account/stale conflicts do not silently fork. Old client and old actual application failures are preserved alongside corrected outputs.
- Synthetic browser evidence/results and complete workflow job/step conclusions are under `qa/desktop-closeout-2026-11-01`. Browser PDF export regression ran; this batch did not repeat the prior live manual PDF visual inspection.

## Deployment verification

Recovery-only deployment **dep-dbjsosetlv9c73e6ck3g** reached LIVE at23:34:58UTC (17:34:58 Saskatchewan time), running **0f065b9d**. Exact isolated QA host/database and recovery service were asserted again in the new instance. Read-only SQL confirms the prior full quote hash is unchanged, total1,200.65 unchanged, counts1estimate/21revisions/24receipts unchanged and0active drafts. The new explicit-retry client is present. No live QA job was edited this batch.

Auto-deploy was rechecked Off. Main remainsc049a04b; production remainsdep-db5b726k1f9s73e862ug/c049a04b. No connection, account, pricing or allowance setting changed. Runtime HTTP smoke is recorded with deployment evidence. No further owner testing is requested today.

## Pending / limits

- Physical-phone touch, Safari and Messenger remain pending.
- New race behavior was exercised in actual Chromium and disposable SQLite/PostgreSQL fixtures; it was not manually repeated against live QA after deployment. No owner interaction is needed tonight.
- This is focused coverage, not a claim that every possible desktop/network failure has been tested. The prior live recovery/PDF result at901c8085 remains valid for its documented scope.
- Existing tabs need a safe refresh to load the new client. Tomorrow's checklist is in `QA_TOMORROW_DESKTOP_2026_11_02.md`.

The containing documentation/evidence commit is the final checkpoint. Do not deploy the documentation-only checkpoint. Stop for today after saving it.
