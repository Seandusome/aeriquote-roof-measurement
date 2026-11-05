# Hosted employee-access QA — November 5, 2026

Continued daed21f5 with owner-approved creation of a clearly QA-labelled pair. Hosted access lifecycle checks below are complete within the stated scope; no runtime defect or application fix found.

## Exact accounts and secure setup

| Identity | Actual login email | ID |
| --- | --- | --- |
| QA TEST Hosted Access Owner | bob@gmail.com | cdb6392e-04d6-4c7a-a586-c1b7c3262b0f |
| QA TEST FICTIONAL Hosted Access Employee | qa-staff@example.invalid | effbf718-947e-4077-9c80-dcd2f7178498 |

Company: QA TEST FICTIONAL HOSTED ACCESS NOV05. Both created by Sean through normal browser forms; passwords entered directly by Sean and never read, logged or stored in repository/chat. Owner signup used bob@gmail.com rather than proposed qa-hosted-owner-nov05-2026@example.invalid; proposed employee email was shortened at Sean's request. Do not silently substitute the unused proposed identities. These are newly created QA-labelled identities, not changes to original sdusome@diitalk.com or any pre-existing business.

Sign in at https://aeriquote-commercial-test.onrender.com/dealer-login with the actual email and privately chosen password. No reset or password change performed. Secure prompt selected real sdusome@diitalk.com once; screenshot caught it before a password-only request/submission. Switched to user-controlled normal sign-in. Earlier unverified-email generic rejection excluded from acceptance.

## Isolation

Recovery aeriquote-commercial-test / srv-db5a2g5ckfvc739fui70, Shingle Guard workspace tea-daaurjp5efls7391kvj0. Every direct DB connection asserted service ID, host dpg-dbj4f7lg1s2s73eob8t0-a and logical database aeriquote_recovery_qa. No original/production database connection. Auto-deploy independently verified no/off at completion. No deployment, environment/binding changes, Head Office role changes, payment, Spexi, clock or billing-date work.

## Hosted results

1. **Normal employee login PASS.** Sean entered credentials on normal /dealer-login. Fresh measuring workspace loaded. DOM meta aqAccountId = owner cdb6392e... and data-principal = employee:effbf718-947e-4077-9c80-dcd2f7178498. Account-profile page showed exact fictional company and trial limits3/3.
2. **Disabled existing session PASS.** Scoped employee disable and revocation while employee authenticated. Fresh profile request returned Account access disabled. Please log in again. Stale owner ACTIVATE form submitted without valid session redirected to login; SQL confirmed employee stayed disabled.
3. **Disabled normal login PASS for controlled manual workflow.** Sean attempted the same instructed employee identity/password while DB state disabled; reported failure; fresh browser showed Email or password is incorrect. No password/request body logging. Generic text is expected rejection, not evidence of a wrong password.
4. **Individual reactivation PASS.** Restored employee active; Sean normally signed in again. Fresh workspace and exact employee data-principal verified. No old session injection or resurrection.
5. **Owner disable blocks active employee PASS.** Owner disabled/revoked while employee individually active and authenticated. Existing profile reload returned Account access disabled. Please log in again.
6. **Owner reactivation preserves individual restriction PASS.** With owner disabled, employee individually disabled. Owner re-enabled; independent SQL showed owner active and employee still disabled. Sean attempted instructed employee login and reported failure; fresh browser again showed expected generic rejection.
7. **Restoration PASS.** Employee then explicitly re-enabled. Final independent state/fingerprint comparison exactly matched starting access/data/allowance state. Owner/employee both active, trial limits3/3; no bonus or complimentary allowance.

Initial employee disable used the owner's actual Manage Employees DISABLE button. Subsequent state changes used narrowly scoped administrative SQL with exact expected status/identity assertions, owner row locking, matching revocation semantics and explicit QA audit entries, because cloud-browser tabs share authentication cookies. Authentication itself was always normal. This demonstrates deployed authentication/session guards; it is not a fresh end-to-end run of every Head Office/owner control UI. No service secret, signed-cookie construction or session injection used.

## Starting/final values and invariants

| Item | Start | Final |
| --- | --- | --- |
| Owner / employee status | active / active | active / active |
| Plan / lookup limit / estimate limit | trial /3 /3 | trial /3 /3 |
| Allowance row / complimentary / bonus | absent /off /0 | absent /off /0 |
| Estimates / revisions | 0 /0 | 0 /0 |
| Month/subscription/dealer usage rows | 0 /0 /0 | 0 /0 /0 |
| Drafts / property sessions / save receipts | 0 /0 /0 | 0 /0 /0 |
| QA Head Office role | c417b9a2-51ea-4816-84da-1e597a7de98d | unchanged |

Each domain table's deterministic full-row fingerprint remained SHA256 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945 (empty array). Rejected profile requests, normal login attempts and stale access-change submission created no estimates, measurement sessions, allowance usage or drafts. No imagery/provider operations. This is hosted empty-state invariance, not a populated-estimate measurement-preservation test. Prior populated local invariants remain the evidence for that case and were not rerun.

Audit retained: qa_employee_activate3, qa_employee_disable2, qa_owner_activate1, qa_owner_disable1 (7 new QA rows). Initial ordinary owner UI disable's normal revocation retained as well. Employee auth revocation version4 retained; old sessions intentionally remain invalid. Restoration does not roll back audit or revive revoked sessions. Final activation audit1024e874-f173-467d-b02c-1e2f8cdfd90c. Do not delete this QA pair merely as restoration; its creation was authorized for continuing hosted QA.

## Limits and preserved work

- No separate fresh employee login while owner disabled; owner-level hosted block was demonstrated on an already authenticated active employee. Prior local normal-login coverage retained.
- Rejected hosted estimate-save and nonempty measurement payload cases were not repeated; earlier local exact-data checks remain valid. This new pair had no saved work.
- Raw submitted email/password/request bodies were not captured; controlled manual rejections are correlated with instructed identity, verified preceding successful exact employee sessions and independently known disabled states.
- No final employee login after the last cleanup activation; final active states verified in database, and activation→normal-login behavior already passed earlier in the same hosted sequence.
- No unchanged local tests, monthly-rollover, full browser audit, top-up or PDF reruns. All completed top-up/PDF code and evidence preserved.
- No new feature or runtime change, deployments, payments, Spexi or original-account/customer changes. Existing QA Head Office role untouched. End signed out at normal login page. Save containing resume checkpoint and pause.
