# Remaining employee-access checks — November 5, 2026

Resumed checkpoint 8afeeda8. No confirmed runtime defect or application fix. This session does **not** close hosted employee-login verification.

## Hosted recovery — read only, credentials unavailable

Recovery service aeriquote-commercial-test / srv-db5a2g5ckfvc739fui70 in confirmed Shingle Guard workspace tea-daaurjp5efls7391kvj0. Render connector verified autoDeploy=no / autoDeployTrigger=off. Shell asserted service ID, host dpg-dbj4f7lg1s2s73eob8t0-a and logical database aeriquote_recovery_qa before opening read-only transactions. No production connection or binding/settings changes.

Existing owner: cf26ec4b-b649-4983-bd35-a4d7c2e773a9, qa-isolation-snow-basic-aa5b2061-0@example.invalid, QA TEST Isolated snow, active Basic. Employee: qa-isolation-employee-aa5b2061@example.invalid, QA TEST FICTIONAL EMPLOYEE, active. Hosted fictional owner/employee credentials were not available to the agent; no login guesses, credential prompts, password changes, replacements or session injection. No hosted employee disable/reactivate was performed without a normal authenticated test session.

Starting/final read-only state matched exactly:
- Owner active Basic; employee active.
- Absent account_allowances and account_month_usage rows: effective complimentary off, no brand, zero bonus.
- Five estimates and two revisions, unchanged row fingerprints (including saved payloads/measurements).
- One subscription-usage row, no dealer_usage row; fingerprints unchanged.
- Five retained credit-audit rows, unchanged.
- Sole QA Head Office role remains c417b9a2-51ea-4816-84da-1e597a7de98d (qa-browser-oct31-2026@example.invalid).

Before/after SHA256 fingerprints, computed over deterministically ordered full row JSON:
| Table | Rows | SHA256 |
| --- | --- | --- |
| estimates | 5 | 607b902e0f0406cb03a7ab0040510c4eaa0ee03319ddfd64f827d786e8e1b08c |
| estimate_revisions | 2 | d758f3e16b71499b2b27c91088b6b88e6b1acaa6c820a7bf4a5874fc24bbfb93 |
| account_allowances / account_month_usage / dealer_usage | 0 each | 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945 |
| account_subscription_usage | 1 | b013d4c5b92d971782ef8e5112afd81d78a93b4edc6fc757f500410a70acdd43 |
| account_credit_audit | 5 | 151a1f900cad5a22c477431fc4732387af70971a3254f8fddbe430785ac9119e |

No hosted changes needed restoration. Existing audit and revoked-session history from prior checkpoint retained untouched.

## Local targeted verification — PASS

Used deployed194c435b application/account-credit source in disposable SQLite, with fictional owner, two employees and Head Office fixture. Normal /dealer-login password POST created every client session; no session_transaction, forged cookies or bypass. Password generated only for temporary fictional fixture, never printed or stored in report. No provider traffic.

Independent live source hashes matched the previously extracted source apart from its documented single additional terminal newline:
- app.py: 39f29b56d1e011f378202135ee5690bb50c4f2643c3032bd46d285f757fcae9a
- account_credits.py: b466219fa876a83307e39d12fc7005075e22ed06e2a3af49dd4ff4e5e9185f7c

Passed:
1. Individually disabled employee normal login rejected with generic credential error; existing session cannot read/save estimates, load property or write draft.
2. Individual activation allows a fresh normal login and estimate read; dormant pre-disable session remains revoked.
3. Business owner disable blocks normal employee sign-in and existing employee requests, including an otherwise active employee.
4. Re-enabling business preserves individually disabled employee status. Restricted employee still cannot sign in; independently active employee can sign in normally. Prior sessions remain revoked.
5. Separate pre-existing sessions test each initial read/save/property/draft rejection, so success does not rely on a previous rejected read already clearing that client's session. Each response was401; unauthenticated access-change attempt redirected to login.
6. Rejected actions made zero urllib provider calls. Exact whole-row snapshots of estimates, revision history, persisted/in-memory measurement geometry, drafts, save receipts, bonus/monthly/subscription/billing records and lookup counters remained equal. Seeded bonuses7/9 preserved.
7. Local owner/employee starting active settings restored; domain snapshot identical to baseline. Head Office role unchanged. Two expected business-control audit rows retained through verification; disposable fixture then discarded.

Reproduction: [check_employee_access_remaining.py](qa/employee-access-2026-11-05/check_employee_access_remaining.py). To reproduce, copy it into scripts/ of an isolated deployed194c435b checkout and run with Flask/runtime dependencies. It explicitly clears DATABASE_URL and uses TemporaryDirectory SQLite. Do not run against hosted database. Initial harness run could not import requests for a network sentinel; corrected it to the application's actual urllib client. No application defect was implicated. Strengthened separate-client run then passed.

Command: PYTHONPATH=/workspace/scratch/59efc9acddbc/qa-deps python head-office-check/scripts/check_employee_access_remaining.py
Final output: PASS for authentication/restriction matrix and all rejection invariants. Final baseline SHA256 8b22ff21695ee64d00a7b87c96c9587b6ae178bcc3298952489eeb1f541d8571 (random fixture/time-specific; equality asserted within that run).

## Limits and preserved work

Hosted normal employee/owner sign-in, existing-session rejection and employee toggles remain unverified, pending secure availability of those existing fictional credentials. This is an explicit limitation, not a password-failure diagnosis or permission to reset/create accounts. Do not repeat login guesses.

Reuse passing monthly-rollover evidence from QA_HEAD_OFFICE_CONTROLS_2026_11_05.md; no clock/billing-date changes or rollover rerun. No full audit/top-up/PDF rerun. Existing top-up/PDF work preserved. No deployment, payments, Spexi, real-account/customer writes, QA role changes or infrastructure changes. Documentation and test evidence only on recovery branch. Save containing resume commit and pause.
