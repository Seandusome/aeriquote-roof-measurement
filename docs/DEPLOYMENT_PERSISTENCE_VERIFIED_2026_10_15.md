# Live deployment persistence verification — October 15, 2026

## Result: passed for the captured records
Sean opened /head-office/storage on the commercial test service and confirmed:
- Connected database: PostgreSQL.
- Stable session secret configured: Yes.
- Saved checkpoint: 1b4bfae2ab51, created 2026-10-15T21:43:20.549323Z.
- Before redeployment, the page showed the same application process.
- After the requested Render redeployment and page refresh, Sean supplied the same checkpoint with "A different application process is running."
- All compared record counts and hashes matched:

| Record group | Before | After | Missing | Changed | Added |
| --- | ---: | ---: | ---: | ---: | ---: |
| dealers | 38 | 38 | 0 | 0 | 0 |
| dealer_employees | 2 | 2 | 0 | 0 | 0 |
| dealer_profiles | 38 | 38 | 0 | 0 | 0 |
| estimates | 41 | 41 | 0 | 0 | 0 |
| estimate_revisions | 62 | 62 | 0 | 0 | 0 |
| support_requests | 1 | 1 | 0 | 0 | 0 |

This is user-supplied before/after evidence in the redeployment test; the assistant did not independently operate or inspect Render.
The result verifies persistence of the checkpoint and these captured account/profile/estimate/revision/support-request rows across this test. It supersedes the unverified-persistence status in the earlier October 15 checkpoint for this specific test.
Do not repeat it merely to recover context.

## Limits and next task
- This was not a backup or restore test.
- Paid/free database plan, backup recovery window and ability to restore remain unverified.
- The snapshot does not include support_notes, support_replies, support_incoming or support_reply_routes; do not claim their individual hashes were compared.
- No guarantee against future configuration mistakes, deletion or all failure modes is established by one deployment test.
- Next: inspect the connected PostgreSQL service's plan and Recovery page in Render, verify available recovery, then plan an isolated restore exercise that does not overwrite the live database.
- Live database byte size and aggregate estimate/revision payload sizes remain to be measured for the 100/250-customer forecast.
- No production/main change, database mutation or application change is included in this documentation update.
