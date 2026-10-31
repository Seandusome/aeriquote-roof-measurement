# Dedicated QA database implementation — isolated and verified, acceptance exception recorded

## Outcome

The approved database isolation is complete. Recovery now uses fresh QA-only PostgreSQL18 with a distinct database and login role; the original paid database and production service were not modified. Live QA writes were made only after the new connection and recovery deployment were verified. **This is not commercial launch sign-off:** one mixed-history Expanded PDF stale-overlay defect was discovered during acceptance and remains unfixed in this infrastructure scope. Physical iPhone/Safari/Messenger and several operational checks remain pending.

Sean completed the fictional browser signup himself. No password was requested, read or reported. Existing manual Roofing/Vector guards were enabled only for new QA owner c417b9a2-51ea-4816-84da-1e597a7de98d, using both the existing flags and ID allowlists. Features remain restricted for other accounts.

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
| Deployment |82fdd0441d8c9adc1c54670e4011f030bef5e4e9; dep-dbj4t6t659jc739gvv7g verified LIVE after QA-only flag settings |
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

Render secret fields return empty DOM values when hidden. An initial attempted comparison of masked field values was therefore discarded as invalid evidence; it was not interpreted as a missing secret. Final target verification used the selected revealed URL, returned only identity/equality results, then hid it. Other rows were not edited; no claim of a full plaintext secret-value comparison is made. No connection strings, admin keys, session values, generated passwords or cookie values are saved in this report/evidence. Temporary setup capability and generated fixture credential files were removed after the API checks; private browser variables containing connection/admin capabilities were cleared. Sean’s browser test password was never read.

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

## Authenticated browser and actual PDF acceptance

- Newly fictional browser owner setup saved Canada/SK, company branding, $0.10 default rate and explicit 5%/6% taxes; session survived recovery deployment. Actual authorized property imagery loaded at 2301 Avenue C North, Saskatoon; Street View dated 2015-07. Test boundaries and customer details are fictional, not a professional estimate for that property.
- Manual Roofing: drew one fictional section, explicitly confirmed5/12 pitch and complete-scope checkbox; saved estimate subtotal$734.84, GST$36.74, PST$44.09, total$815.67. This does not claim real roof accuracy, multiple-building UI coverage or commercial imagery licensing.
- Surface UI: drew an irregular six-corner Area1 (7,834ft²), separate Area2 (7,508ft²), independent three-point Linear (205.4ft displayed). Created all five industry estimates using the same controlled job geometry; historical versions are expected under one property record, not six duplicate properties.
- Visible Estimate-stage RETRACE Area1 starts empty and hides only the selected original. Area2 and Linear remain visible, PDF is disabled while unfinished, and Save/Cancel/Undo sit directly below the aerial. Proposed change7,834→6,125ft² /$1,725.76→$1,536.06 was shown. Cancel restored original; repeat retrace/Save persisted only Area1 and retained Area2/Linear. No pricing or measuring code was changed.
- All six live browser estimates and **12 actual PDFs /18 rendered pages** were produced and visually reviewed: Single is one page, Expanded two. Actual aerial/Street View photographs and attribution appear; Street View remains proportional, customer/company and totals readable. The five surface totals use explicit rate settings; Commercial existing Linear rate was$0.25, others$0.10. Independent Decimal checks confirm the three shown tax/total combinations. Earlier29 live API checks independently cover geometry,18 industry/tax fixtures and saved revision/pricing integrity.
- Saved history was opened through the actual UI; current Commercial total$1,570.25 and6,125+7,508ft²/205.4ft were retained. Its OPEN ESTIMATE action restored the job and rates. All-six API reopen checks are separate evidence; no claim that every historical UI revision was reopened.
- Initially four Expanded download handles had no completed file after rapid report navigation. Retrying and confirming file availability before navigation recovered all12 files. One browser tool operation timed out/reset; browser was rebound without repeating completed tests. No download application defect was inferred solely from those tool failures.

### Confirmed failed acceptance check — stale roof in reopened Commercial Expanded PDF

`pdfs/commercial-expanded.pdf`, exported after saved Commercial reopening, shows an orange old manual Roofing section/dimensions in addition to the priced purple service Areas and teal Linear. The Commercial Single example and the other four surface Expanded examples do not contain that old roof; their current surface quantities/prices match. The mixed job originated in manual Roofing before switching industries and saving revisions. Saved history retained a roof version and surface versions, as expected, but the reopened surface export must not present unpriced roof geometry.

This is a genuine displayed-geometry versus priced-scope mismatch, not a subscription/DB isolation failure. Source inspection shows Expanded captures `customerMap` pixels; reopening/mixed-mode renderer cleanup must be investigated before changing code. Exact root cause is not yet proven. **Do not claim all acceptance checks passed or silently hide this finding.** No historical estimate was modified to force a pass, and no unrelated application fix or PDF redesign was made. Preserve the reproduction artifact and fix in a separately scoped recovery batch.

### Remaining unverified

- Physical iPhone/Safari/Messenger and actual touch input; browser was desktop Chromium. This Cloud Browser exposes no supported viewport/touch emulator, so no fresh320/390/768 emulation is claimed. Prior CI/mobile evidence remains historical.
- Visible repeated Area2/Linear drag corrections, all-five-industry retrace cycles, multi-section/detached-roof UI and interrupted-save browser recovery were not exhaustively repeated. Disposable automated suites cover existing cases.
- Live allowance exhaustion/renewal, complimentary fixtures, password-reset email delivery are not newly proven; controlled PG16/18 lifecycle/concurrency suites passed and live plan profiles show25/75/200. No Stripe/billing changes.
- Managed PG18 restore, exact selectable recovery timestamps, full table inventory and expiring Free DB external dependency/content audit remain outside this switch. No network rules were weakened.

## Final infrastructure verification and checkpoints

- Recovery latest deployment **dep-dbj4t6t659jc739gvv7g LIVE**, commit **82fdd0441d8c9adc1c54670e4011f030bef5e4e9**; auto-deploy remains Off and service running. QA flag update auto-triggered dep-dbj4t649v7es7394iq30; an unnecessary explicit same-config deploy queued afterward and is the current live deployment. Both succeeded; no additional deployment is needed for this documentation.
- New QA DB rechecked available,PG18/Ohio/0.1c-256mb; external IP allowlist still empty. No HA/autoscale/replica purchase.
- Production metadata remains byte-equal to pre-operation metadata. Its original database mapping was verified independently through masked resource/database/role identities. Main and production deployment remain c049a04b2ac5cc4df3d5c253fe9ca12f1d85806a /dep-db5b726k1f9s73e862ug. No customer rows were queried for this audit.
- Runtime application source unchanged.91b4d009b1b8fe565472e83c69eabf0441d228ec is CI-only PG16/18 matrix.82fdd0441d8c9adc1c54670e4011f030bef5e4e9 is the interim evidence checkpoint, both workflows passed at41238481814 /41238482183. This containing documentation/evidence commit is the final checkpoint; it intentionally skips Render.
- No original DB, production config, old Free DB, imagery integration, pricing, allowance, measurement engine or PDF layout was modified. Stable session secret preserved. No credentials in documentation/evidence.

## Resume safely

Review the failed Commercial Expanded mixed-history overlay before launch sign-off; do not rerun the completed29 API tests or full CI simply to resume. Use only fictional accounts on the isolated recovery database. Keep recovery auto-deploy Off. Never reconnect recovery to the original paid database as rollback; if identity becomes unverifiable, stop recovery and preserve both databases.

Evidence: [live API](qa/db-isolation-2026-10-31/results.json), [follow-up](qa/db-isolation-2026-10-31/followup.json), [infrastructure](qa/db-isolation-2026-10-31/infrastructure-evidence.json), [browser/PDF manifest](qa/db-isolation-2026-10-31/browser-acceptance.json), and the actual PDFs/visual sheets in `qa/db-isolation-2026-10-31/pdfs/`. All data/geometry fictional; actual imagery is existing authorized QA access, not proof of commercial rights.
