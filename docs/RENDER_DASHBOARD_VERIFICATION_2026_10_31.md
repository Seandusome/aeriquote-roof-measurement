# Authorized Render Dashboard review — October 31, 2026

## Critical confirmed finding

**Recovery and the old main/production-candidate service share the same paid PostgreSQL resource, logical database and login role.** This supersedes the earlier unverified-isolation assessment. Account-level application isolation is not infrastructure separation: changes, initialization, errors or QA writes from recovery can affect the common database. No customer data was inspected, and no breach or damaged records were established.

| Service | Resource identity | Logical DB / role comparison | Connection |
|---|---|---|---|
| aeriquote-commercial-test / srv-db5a2g5ckfvc739fui70 | dpg-db019ijncjis7383g3a0-a | Same as main service | Internal |
| aeriquote-roof-measurement / srv-db01g1p42hec73ehu1lg | dpg-db019ijncjis7383g3a0-a | Same as recovery service | Internal |

Connection values were inspected through selected visible Dashboard fields and immediately hidden. Only resource IDs, presence booleans and equality results were emitted. Logical database and role names were compared transiently and discarded, not recorded. Passwords were not extracted or compared; both URLs include password authentication. Shared login identity is confirmed, exact password-value equality was not separately measured. No connection tests were sent to the app and no records were read.

## Session configuration and groups

Both AeriQuote services have a nonempty persisted FLASK_SECRET_KEY environment setting. This removes the earlier uncertainty about the configured setting; actual restart/session continuity was not tested. Secret-value equality, strength, rotation history and any later override remain unverified. Session values were never returned or recorded.

Workspace Environment Groups page explicitly says there are no environment groups. Both AeriQuote service pages show no linked groups. Their shared database connection is configured at service level, not through a linked group. The project environment named Production contains the two other Shingle Guard/ShingleXtra services; that label does not make the ungrouped AeriQuote recovery service isolated.

## Paid Recovery page — observed, not inferred

The actual page for dpg-db019ijncjis7383g3a0-a states point-in-time recovery is available from the **past three days**, with an option to upgrade the workspace for seven. No logical exports were listed. The page describes export retention of at least seven days; this is not evidence that an export exists.

No exact earliest/latest timestamp was displayed on the overview. Restore database was not clicked or opened, as explicitly prohibited. Therefore exact selectable recovery dates, restore completion, recovery cost and end-to-end usable chain remain unverified. Earlier healthy WAL statistics support archiving, not a completed recovery drill. No paid plan/settings were changed.

Verified page: https://dashboard.render.com/d/dpg-db019ijncjis7383g3a0-a/recovery . No URLs containing credentials were recorded.

## Expiring isolated QA dependency review

The QA database Info page confirms expiry November 20, 2026. Its contents remain inaccessible through the existing connector and were not opened in a database client or exported.

All four visible web services were reviewed for their DATABASE_URL configuration:

- AeriQuote recovery: paid AeriQuote DB above, not the expiring QA resource.
- AeriQuote main candidate: same paid AeriQuote DB, not the QA resource.
- shinglextra-us-roof-assessment: dpg-dam4jnou01pc73bf5i9g-a, a separate resource, not the QA resource.
- shingle-guard-dealer-beta: no DATABASE_URL or standard PGHOST/PGDATABASE/PGUSER/PGPASSWORD keys shown. This does not establish its storage architecture or exclude custom settings/code references.

No current service DATABASE_URL dependency on dpg-dbcjg2brjlhs73dn1g7g-a was found. No shared environment groups exist in this workspace. The inventory contains no worker/cron service, but external scheduled scripts, GitHub secrets/jobs, custom settings, secret files, historical deployments and current QA table contents were not exhaustively verified. Therefore unattended expiry still cannot be certified harmless. Leave it unchanged until a final content/reference assessment is authorized; no upgrade, export or migration performed.

## Recommended separation plan — not implemented

1. Pause authenticated live QA writes against recovery. Continue offline/disposable local and CI tests only. Do not change production while planning.
2. Prepare an isolated QA database and distinct QA runtime role/credentials, using synthetic data rather than a customer-data clone. First review costs and schema-startup permissions; do not create or upgrade anything without approval. Do not assume the expiring free database is a durable solution.
3. After exact owner approval, change ONLY recovery's database connection to that isolated target, preserve production's current connection and customer records, and verify the correct service/branch. Keep session secrets scoped to environments and review cookie/domain behavior.
4. Review startup schema/migration compatibility and roles. A separate runtime role without current startup DDL permissions can fail; stage the change rather than blindly revoke privileges. No data migration is authorized by this review.
5. Verify masked mapping, disposable owner/employee accounts, save/reopen, allowances, account isolation and PDFs in the isolated QA target before resuming live QA. These are proposed tests, not newly passed results.
6. Separately approve a managed new-instance restore rehearsal and external network restrictions only after dependencies, responder access and costs are known. Never restore over the existing common database.

This is a proposal for approval, not permission to create a database, change environment variables, deploy, rotate secrets or move records.

## Scope, safety and remaining evidence

User completed Render login manually through Cloud Browser. Review used only existing pages. No Restore/Create export/Delete/Upgrade/Deploy controls were activated; no values were edited or saved. Main and production configurations, customer records, imagery, pricing, allowances and RETRACE were untouched.

Automatic review rejected a broad environment accessibility capture because it could disclose secret values. The safer alternative returned only approved key names, structure, presence booleans and masked identities. No broad environment snapshot, screenshots of secret-bearing fields, credentials, tokens or reusable hashes were saved. An initial masked-field parsing failure was corrected using the actual revealed textarea; no failed parse was treated as an absent setting.

Starting checkpoint is 9676758a292d93369c0dfc1394e7bafcfbc1982d. This containing commit is documentation only and uses [skip render]. No application tests or manual deployments were initiated. Existing regression results remain prior evidence; new documentation CI status is reported separately, without prolonged polling. Stop for owner approval before infrastructure changes.
