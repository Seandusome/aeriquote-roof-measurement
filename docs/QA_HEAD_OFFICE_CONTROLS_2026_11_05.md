# Head Office control checks — November 5, 2026

Resumed 06aeb288. Recovery only: aeriquote-commercial-test / srv-db5a2g5ckfvc739fui70, confirmed Shingle Guard workspace tea-daaurjp5efls7391kvj0. Recovery auto-deploy independently verified OFF before and after checks (autoDeploy=no, autoDeployTrigger=off). No deployment, binding changes, real-account changes, payment or Spexi work. Original sdusome@diitalk.com remains in its original database; it is not the isolated recovery login.

## Environment and authentication

The old displayed dashboard had a stale session: navigating to credits redirected to login. One fresh normal QA authentication succeeded after a screenshot visually verified qa-browser-oct31-2026@example.invalid, followed by a secure password-only request for that exact account. No credentials logged or changed; no injected session or bypass used in the hosted environment.

Shell queries asserted exact recovery service ID, database host dpg-dbj4f7lg1s2s73eob8t0-a and logical database aeriquote_recovery_qa before connecting. No production database opened.

## Starting and restored state

Target owner cf26ec4b-b649-4983-bd35-a4d7c2e773a9 / qa-isolation-snow-basic-aa5b2061-0@example.invalid, QA TEST Isolated snow; profile company displayed QA TEST FICTIONAL snow. Employee 1d778b06-b807-4b86-a4a0-db7fad16dca7 / qa-isolation-employee-aa5b2061@example.invalid, QA TEST FICTIONAL EMPLOYEE.

| Setting | Start | Final independent SQL readback |
| --- | --- | --- |
| Owner status / plan | active / basic | active / basic |
| Employee status | active | active |
| Allowance row | absent | absent |
| Complimentary / brand | effective off / none | effective off / none |
| Measurement / estimate bonus | effective 0 / 0 | effective 0 / 0 |
| Estimates / revisions | 5 / 2 | 5 / 2 |

The roofing account searched first was read only: d5db3af6-ee53-4b97-812f-63304cc3fdb7 / qa-isolation-roofing-basic-aa5b2061-5@example.invalid, active Basic, absent allowance row, 3 estimates / 0 revisions. It was not modified.

## Live browser and database evidence

- Dashboard email search showed only the correct fictional roofing business; credit search showed its QA TEST FICTIONAL roofing profile company and exact email. Snow credit search likewise matched exact email/company, with one result. Owner-name and profile-company labels differ intentionally; no cross-business mismatch found.
- One intended 25-credit grant changed snow bonuses 0/0 to 25/25. Successful POST redirected to GET. Reload retained 25/25, with exactly one grant audit row independently checked in SQL.
- Complimentary monthly access enabled and persisted after reload: 200 measurements and estimates per calendar month, first-of-month America/Edmonton renewal, no rollover, employee-shared allowance. Display showed 0/0 month usage; Basic plan and 25/25 extra credits unchanged.
- Disable changed owner active to disabled, stopped complimentary access and retained credits/data. SQL readback: owner disabled, employee's own status active, effective access blocked through disabled parent; owner auth version 1, employee version 2, estimates/revisions 5/2. Employee status need not be overwritten to block business access.
- Reactivate returned owner to active; monthly access stayed off, underlying Basic retained, bonuses stayed 25/25.
- Starting settings restored under an exact-identity, row-locking SQL transaction. Assertions required expected active Basic owner, precisely 25/25 unspent extras, complimentary off, brand empty, unchanged 5/2 records and one grant audit. Removed only the test-created allowance row and appended explicit qa_restore audit entry amount -25 explaining removal of both unspent channels. No estimate/revision/usage/password writes. Reload and independent read-only SQL verified final starting values.
- Kept audit entries for grant/configure/disable/reactivate/QA restoration. Session revocation versions deliberately retained; previously revoked sessions must never be revived by restoration. These are expected test/security history, not un-restored allowance or account settings.
- While authenticated as Head Office, direct requests for snow estimate 0d8a402c-59b6-471f-b2af-0db26e0b684f and its /versions route returned {"error":"Estimate not found"}. No private estimate content was returned. Dashboard exposes account management, not a business-estimate viewer.
- Clicked Log Out. Fresh navigation to /head-office/dealers and, in a separate tab, /head-office/credits redirected to /dealer-login. Ended signed out.

## Disposable local checks and limits

Used deployed 194c435b source in a temporary SQLite fixture, with no hosted DB connection. Source hashes independently matched service bytes after removing the single extra terminal newline introduced by local extraction:
- app.py SHA256 39f29b56d1e011f378202135ee5690bb50c4f2643c3032bd46d285f757fcae9a
- account_credits.py SHA256 b466219fa876a83307e39d12fc7005075e22ed06e2a3af49dd4ff4e5e9185f7c

Existing scripts/test_account_credits.py PASS: CSRF/invalid inputs, duplicate POST operation accepted once, shared owner/employee quotas, 200 monthly limits in both channels, Edmonton boundary and rollover, no reset on resave/brand changes, free revisions, immediate owner/employee session revocation and stale-session rejection after reactivation. This targeted run was justified by the current Head Office assignment; full audit/top-up/PDF suites were not repeated.

Additional normal-authentication check PASS: fresh synthetic credentials through the actual /dealer-login POST (no session_transaction), Head Office denied another owner's estimate/history, owner and employee stale requests rejected after disable, normal logins rejected while disabled, fresh logins succeed after reactivation, individual employee disable/activate via owner route, and logout blocks both dashboard routes. Only disposable local fictional identities/passwords; fixture discarded.

Limits: hosted owner/employee password login and individual employee toggle were not separately exercised, since their credentials were not requested; those cases passed locally with actual normal-auth routes. Future-calendar monthly rollover was simulated locally rather than altering hosted time or consuming 200 real imagery operations. Live duplicate same-operation POST was not forced through browser internals: live refresh passed; exact duplicate-operation protection passed locally.

No confirmed application defect and no runtime source changes. Existing built-but-undeployed top-up/PDF changes and prior evidence preserved. No full audit rerun. Containing resume-note commit is checkpoint; pause.
