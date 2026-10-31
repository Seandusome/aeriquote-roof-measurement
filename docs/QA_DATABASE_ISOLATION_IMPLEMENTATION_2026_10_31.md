# Dedicated QA database implementation — verification in progress

## Implemented, not yet full browser acceptance sign-off

Sean approved one fresh paid PG18 database and recovery-only connection switch at a maximumUS$6.30/month before tax. The core switch and controlled API verification are complete. **General live QA is not yet signed off**: interactive RETRACE/Save/Cancel and downloaded Single/Expanded PDFs on the deployed site still need authenticated browser verification. Do not report these as passed based on prior fixtures. A prepared fictional signup awaits Sean's own password entry; do not use or reset any production login.

## Resource, cost and configuration

| Item | Verified result |
|---|---|
| New DB | aeriquote-recovery-qa; dpg-dbj4f7lg1s2s73eob8t0-a |
| Compute |0.1c-256mb; PostgreSQL18; Ohio |
| Storage/cost |1GB. Actual creation form total **US$6.30/month**: $6compute+$0.30storage; US$75.60 annualized, before tax/FX, not an annual purchase |
| Network | Empty external IP allowlist from creation; internal connection used. No network access was opened |
| Extra paid features | HA off; autoscaling off; no replicas or workspace/web-service upgrade |
| Recovery target | Only srv-db5a2g5ckfvc739fui70 changed; auto deployments Off |
| Production | srv-db01g1p42hec73ehu1lg still main/unsuspended/auto-deploy unchanged; original DB dpg-db019ijncjis7383g3a0-a |
| Separation | New resource, logical database and database login role all distinct; new provider-generated credentials, no production credential reuse |
| Session/providers/code | Only recovery DATABASE_URL was changed. FLASK_SECRET_KEY and provider settings were not edited. No application runtime source change |
| Deployment |91b4d009b1b8fe565472e83c69eabf0441d228ec; dep-dbj4kr8u01pc73ef92gg verified LIVE |
| QA Recovery page | Three-day PITR entitlement shown. No export or restore initiated; exact selectable dates/end-to-end recovery remain untested |

The creation UI contradicts the public pricing page's “1GB included” wording. Its actual $6.30 total controlled the approved purchase and resolves the earlier budget uncertainty. The database was created through Render's dedicated connector after inspecting that form; it returned a fresh resource with a closed external allowlist. No second instance was created. The expiring Free PG16 database was neither deleted nor upgraded.

## Operation and safeguards

1. Verified ed2d24e recovery HEAD and successful checks. Main remained c049a04.
2. Set recovery Auto-Deploy Off and suspended only that service. Connector confirmed both states; production stayed running.
3. Created the fresh PG18/Ohio1GB resource; metadata confirmed distinct DB/user/resource and no HA/replicas/autoscale/public access. No cloning, restoring, exporting or customer data migration.
4. Read the new internal connection privately, edited only the recovery DATABASE_URL row, and verified its saved resource identity. The first UI save attempt retained the original URL; the post-save check caught it while recovery was stopped. Correctly submitting the actual environment form then persisted the new URL. No restart was allowed on a failed identity check.
5. Resumed recovery, then performed an explicit recovery-only deployment to apply the stored configuration with a recorded deployment ID before any fixture account writes. The first unauthenticated protected account-setup request returned401 and created no account; the corrected sequence first created a fictional trial owner, then used the existing protected setup API.
6. Existing application import initialized the new schema and legacy migration bookkeeping. Nine paid-plan fixtures plus a fictional trial/bootstrap owner and an employee were then created through the recovery application APIs. No manual DDL or SQL was run against the original database. New account histories were empty before tests. This is behavioral schema/persistence evidence, not a direct raw SQL inventory (the new external network remains closed).
7. Re-read production's masked URL: it still identifies the original resource, with a different database name and role from QA. Production get-service metadata is byte-equal to the starting metadata; no production settings or deployment changes were made. This operation never intentionally targets the original database for writes. No customer rows were read or hashed; unrelated legitimate production writes cannot be globally excluded by this audit.

Render secret fields return empty DOM values when hidden. An initial attempted comparison of masked field values was therefore discarded as invalid evidence; it was not interpreted as a missing secret. Final target verification used the selected revealed URL, returned only identity/equality results, then hid it. Other rows were not edited; no claim of a full plaintext secret-value comparison is made. No connection strings, admin keys, session values, generated passwords or cookie values are saved in this report/evidence. Temporary setup capability and fixture credentials stay in private non-repository files only until controlled verification finishes and should then be removed.

## Passed verification

- GitHub application-validation run41237372117 SUCCESS and full recovery run41237372109 SUCCESS.
- Recovery/full regression job124643862692 SUCCESS. Canonical78-command regression coverage remains unchanged.
- PostgreSQL16 job124643862903 and PostgreSQL18 job124643862908 both SUCCESS, including concurrency, idempotency, failed property acceptance, renewal, employee/password security, identity races, roof overlap, logging privacy and native disposable restore drill. These run only on isolated localhost CI databases, not Render/customer storage.
- CI-only change91b4d00 adds a16/18 matrix; app.py, geometry, pricing and allowance source are unchanged from764f1ff.
- **22 live API checks plus7 follow-up checks passed (29 total)** against only aeriquote-commercial-test with the newly deployed isolated connection.
- **18 live saved/reopened estimate cases**: all six industries × regular/included/discount tax modes; fictional geometry/customer/branding and independent Decimal pricing. Independent WGS84 area/length references pass the existing spherical tolerance.
- Four concurrent identical saves returned one ID/receipt; paid estimate usage increased exactly3→4, not four deductions. Reopening and rejected geometry/property requests preserved counters. Stale revisions409 preserve the latest saved detail.
- Cross-business estimate access404; employee shares correct owner/branding, cannot modify owner profile403, owner opens employee-created estimate, disabling rejects old session401 and reactivation does not revive it; new login succeeds.
- Live overlap, self-cross, incomplete polygon and zero-length line snapshots were rejected400 without changing the saved estimate or allowance. A selected-Area saved correction retained the other saved Area and independent Linear coordinates/quantity and validated total.

## Still pending — do not mark accepted yet

- Authenticated visible UI: all-six-industry creation/navigation, repeated RETRACE OUTLINE, Edit, Undo/Save/Cancel, mobile320/390/768, no stale overlays or accidental drag.
- Actual Single and Expanded downloads/rendered visual checks from the deployed isolated site. Prior36/38 synthetic PDFs are historical evidence and are not relabeled as this switch's PDF acceptance.
- Live property loading/imagery and failed-save browser recovery where authorized; live API snapshots in this batch use fictional data and do not verify actual provider photographs.
- Live exhaustion/renewal boundaries, complimentary fixture behavior and password-reset email delivery are not newly proven. The disposable PG16/18 suite verifies controlled allowance/lifecycle cases; actual live plan profiles confirm25/75/200. No billing/Stripe changes.
- Physical iPhone/Safari/Messenger tests remain owner/device checks, never inferred from API or viewport emulation.
- Direct managed PG18 restore, full table-content inventory and external/custom dependency review of the expiring Free DB remain outside this completed switch. No network restriction was weakened to run tests.

## Where to resume now

Cloud Browser prepared signup uses fictional name/company and qa-browser-oct31-2026@example.invalid. Sean must choose a test-only password and complete signup; never request that password in chat. Once he confirms signed in, inspect only the completed page, record the newly created QA owner ID from its own authenticated profile, and continue browser acceptance. If manual Roofing/Vector need activation, change only existing QA guards/ID allowlists for this newly created fictional account as approved; do not expose them to all accounts. Preserve DATABASE_URL and FLASK_SECRET_KEY when applying those settings. A recovery-only deployment may be needed; never reconnect to the original.

If the new target becomes unverifiable or switch fails, stop recovery and preserve both databases. Do not blank DATABASE_URL, fall back to SQLite, restore over original or use a historical connection rollback. Leave auto-deploy Off pending explicit future approval. Do not promote main or production.

Evidence: [sanitized live results](qa/db-isolation-2026-10-31/results.json), [geometry/correction follow-up](qa/db-isolation-2026-10-31/followup.json), [infrastructure/CI summary](qa/db-isolation-2026-10-31/infrastructure-evidence.json), [non-sensitive plan screenshot](qa/db-isolation-2026-10-31/qa-db-plan.jpg). Fictional payload samples in the same directory contain no imagery tokens or credentials.

This containing documentation commit is an interim resume checkpoint. It deliberately skips Render deployment; current application deployment remains91b4d00. Do not repeat completed API/CI tests merely to resume the browser handoff.
