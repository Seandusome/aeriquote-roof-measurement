# Head Office identity after QA isolation — November 5, 2026

## Finding

Sean's existing Head Office account was found **active, with its admin role intact, in the original database**. It was not deleted or replaced by this investigation. The recovery service uses a different, intentionally fresh database that has no matching account. This explains the current correct-email lookup failure on recovery; it does not establish the cause of every historical login failure or the origin of a browser/secure-form typo.

Exact account email for all future work: **sdusome@diitalk.com**. No login attempts or password requests were made in this investigation.

## Current read-only evidence

| Check | Result |
|---|---|
| Workspace | Shingle Guard, tea-daaurjp5efls7391kvj0, explicitly confirmed by Sean |
| Recovery service | aeriquote-commercial-test, srv-db5a2g5ckfvc739fui70, recovery branch |
| Recovery auto-deploy | Direct get_service reports autoDeploy=no, autoDeployTrigger=off |
| Running source |194c435b377dbcb23ad24a422c63763fcd931ed4 |
| Running master/worker | Read /proc environment for Gunicorn PIDs58/59 in instance t99jq; both service IDs match and DATABASE_URL equals the inspected shell mapping |
| Recovery database | dpg-dbj4f7lg1s2s73eob8t0-a / aeriquote_recovery_qa / aeriquote_recovery_qa_user |
| Recovery SQL mode | default_transaction_read_only=on; queried transaction_read_only=on; rolled back/closed |
| Correct-email account in QA |0 matching owners; prior bounded read also found0 matching employees |
| Original account ID in QA |0 matching rows for58279332-0996-4bdd-9a6c-e202f40c5c0c |
| QA admin roles |0; head-office-role-v1 migration marker present |
| Original database | dpg-db019ijncjis7383g3a0-a / aeriquote_database |
| Existing identity there | account58279332-0996-4bdd-9a6c-e202f40c5c0c; email sdusome@diitalk.com; dealer name Sean Dusome; active; created2026-10-02T21:23:03Z |
| Original Head Office role | account_admin_roles contains that same account ID |
| Original query scope | Independent Render connector read-only SELECTs restricted to Sean's matching account and role; no recovery connection to production, no original application import or writes |

No password/hash/token/session values were queried, printed or compared. No estimates or other businesses' records were inspected.

## Historical cause and migration/configuration review

[October31 dashboard findings](RENDER_DASHBOARD_VERIFICATION_2026_10_31.md) record that recovery and the old main service formerly used the same original database, logical DB and role. This is where the previously working real identity was accessible to recovery.

[Approved isolation plan](QA_DATABASE_ISOLATION_PLAN_2026_10_31.md) explicitly required a fresh empty QA database and prohibited copying customer/account IDs, password hashes, account rows or sessions. [Implementation record](QA_DATABASE_ISOLATION_IMPLEMENTATION_2026_10_31.md), recorded in82fdd044 and2381a609, documents the October31 recovery-only DATABASE_URL switch, independent deployment and fictional fixture seeding. It explicitly says no cloning, restoring, exporting or customer-data migration occurred. That is a connection-isolation change, not relocation of Sean's identity.

Reviewed deployed194c435b code:
- estimate_db uses the configured DATABASE_URL consistently. Its schema initialization creates tables/indexes and migration bookkeeping; it does not fetch identities from the original database.
- dealer_login looks up the active owner/employee in that database before verifying credentials or creating a session. A missing owner/employee returns the generic rejection even when the submitted password is unchanged.
- is_head_office requires an authenticated active owner and recognizes the exact email sdusome@diitalk.com or an explicit account_admin_roles entry. Merely hard-coding an authorized email is not an account record.
- account_credits.init_credit_db's head-office-role-v1 migration inserts admin roles only for qualifying dealers already present, then records completion. It does not create a dealer or migrate a password. Running against a fresh database explains a recorded marker with zero roles. The exact original execution time was not independently reconstructed.
- The trial-usage reset migration only resets trial lookup counters; reviewed recovery-token code deletes expired counters/tokens, not dealer identities. No evidence from reviewed paths supports an account-deletion diagnosis.
- Historical fix_aeriquote_head_office_identity.py modifies source authorization/bypass logic; it is not a data restoration tool and was not run.
- Original main sourcec049a04 recognizes an active owner's exact email or legacy Head Office name. Its existing account is therefore configured to qualify; no login or dashboard success was attempted or claimed.

The failure is an **access/QA-bootstrap gap following intentional isolation**, not evidence that the real password was changed. Do not undo isolation to fix it.

## Proposed correction — not executed

1. Preserve the original real Head Office account, role and credentials in the original environment. Do not move/delete/rename/reset it or reconnect recovery to that database. Record clearly which environment each login serves.
2. If Head Office administration must be tested in recovery, propose an explicit, separately approved admin-role assignment to an **existing fictional QA owner**, using the existing role system. This would be an account-permission change and is not authorized by this read-only investigation. Do not create a replacement real account or copy real password hashes.
3. For future QA bootstraps, add an approved acceptance requirement that a designated fictional admin can access the QA dashboard. Do not silently grant access by editable display name, rerun all migrations, or clear migration markers.
4. A future real Head Office environment/URL decision should be confirmed before any release. The original main deployment is oldc049a04; locating the account there is not a recommendation to run latest-feature QA against it.

No correction was applied. No login/dashboard verification is claimed; the real account cannot authenticate to recovery while it is absent there. Credential re-entry cannot resolve that absence.

## Boundaries and checkpoint

No passwords requested, login attempts, credential/account changes, new accounts, role grants, schema/data migration, database-binding changes, environment updates, service restart or deployment. No code fix was needed to establish the cause. Recovery auto-deploy remains verified OFF; main's existing settings were read but not changed. Spexi and payments remain paused. Existing top-up/PDF work is untouched.

This report and the linked resume entry are documentation-only, with CI/deployment skip markers. Containing resume commit is the checkpoint. Pause for Sean's review of the proposal before any account or infrastructure changes.
