# Final end-of-day checkpoint — cross-industry QA

Read [final round results and limitations](QA_FINAL_CROSS_INDUSTRY_2026_10_31.md) first. This containing documentation/evidence commit is the latest checkpoint; preserve newer recovery HEAD if advanced.

- No new confirmed high-severity application defect, runtime change or deployment this round. Application remains **60ae098f7f2010dea2c9bbde767b0a35d3395f57**, recovery LIVE **dep-dbj5esc9v7es7395qou0**, auto-deploy Off. QA database connections/credentials/infrastructure unchanged; main/production/original DB untouched.
- New live saved revisions across all six industries; Area2 RETRACE Cancel/Save and Linear Cancel/Save preserved other geometry and pricing. Latest surface scope12,352ft² +188.2640110545814ft. Corrected Commercial$1,423.32; other four surface industries$1,391.97. Original Roofing$815.67 and older Commercial$1,570.25 retained through out-of-order reopening.
- New controlled coverage:180 mixed revisions /1,080 renders;540 independent pricing cases;24 failure/retry cases; WGS84 geometry/pitch reference. Passed. Full79/79 and PG16/18 verified through successful b74bc3b workflows41242172010 /41242172011. No need to repeat these merely to resume.
- **Fresh PDFs NOT verified:** two Roofing Single transfers and one Landscaping Expanded transfer after one refresh failed in Cloud Browser while AeriQuote said downloaded; extension errors/runtime reset observed. No new PDFs obtained. Cause unresolved; no speculative application fix. Prior actual60ae098 PDF evidence remains valid historical evidence only.
- First next step: isolated-QA Single/Expanded downloads in a normal browser/physical iPhone, then visual inspection of newest corrected revisions; separate product failures from tool transfer limitations. Physical Safari/Messenger touch testing remains pending. Do not reset real accounts or use production for this.
- End-of-day stop. No imagery migration, Stripe, account/allowance changes, infrastructure changes or new development authorized without a next assignment.

---

Earlier checkpoints below are historical.

# Latest checkpoint — saved-estimate PDF scope fix

Read [focused diagnosis, tests and actual PDF evidence](QA_PDF_ACTIVE_SCOPE_2026_10_31.md). Application fix **60ae098f7f2010dea2c9bbde767b0a35d3395f57** is committed on the recovery branch and LIVE at **dep-dbj5esc9v7es7395qou0**. This containing documentation commit is the final checkpoint; it skips Render.

- Root cause: historical renderer/label painter used every saved geometry family, unlike pricing’s active scope. Both reopened Single and Expanded could show an inactive roof. Read-only projection now follows existing pricing selection without changing snapshots/history, geometry math or pricing.
- Full local **79/79**; GitHub runs41241456362 /41241456410 SUCCESS, recovery job124656051282 and disposable PG16/18 jobs124656051141 /124656051267 SUCCESS. Do not repeat completed testing just to resume.
- Exact fictional Commercial revision7 reopened; actual Single/Expanded rendered and visually inspected, only its two Areas and Linear remain. Quantities13,633ft² /205.4ft; total$1,570.25 unchanged. Original Roofing revision1 /7,348ft² /$815.67 and its actual Single PDF preserved. Four before/after PDFs and screenshots committed. No live estimate Save or historical rewrite in this follow-up.
- Dedicated QA DB **dpg-dbj4f7lg1s2s73eob8t0-a** configuration/credentials untouched; recovery auto-deploy still Off. Production deployment/main remainc049a04 /dep-db5b726k1f9s73e862ug. No production/original paid database/customer activity.
- Physical iPhone/Safari/Messenger still pending. Other live workflows remain bounded by the isolation acceptance report. Imagery licensing, billing and operational launch blockers remain; this is not commercial launch sign-off.
- Stop for review. Do not add features, change providers or alter infrastructure. Never reconnect recovery to the original database as rollback.

---

Earlier checkpoint history follows; the stale PDF failure below is resolved by the focused report above.

# Latest checkpoint — dedicated QA isolation implemented

Read [implementation and acceptance report](QA_DATABASE_ISOLATION_IMPLEMENTATION_2026_10_31.md) first. This containing commit is the final documentation checkpoint; preserve newer recovery HEAD if advanced.

- New QA DB **dpg-dbj4f7lg1s2s73eob8t0-a**,PG18/Ohio0.1c-256mb1GB, **US$6.30/month before tax**, closed external access. Recovery alone uses it with distinct DB/login; original production unchanged.
- Live recovery **82fdd0441d8c9adc1c54670e4011f030bef5e4e9**, **dep-dbj4t6t659jc739gvv7g**. Auto-deploy Off; no deploy for this final doc. QA-only manualRoof/Vector flags+IDs scoped to new fictional owner c417b9a2-51ea-4816-84da-1e597a7de98d. Session secret preserved.
- Full regression and disposable PG16/18 passed.29 live API checks +18 six-industry/tax saved/reopen cases passed. Browser created all six estimates on real authorized QA imagery, RETRACE Area1 Cancel/Save retained Area2+Linear,12 actual PDFs/18 pages rendered and visually reviewed. Do not repeat completed testing merely to resume.
- **Failed acceptance:** reopened mixed-history Commercial Expanded PDF contains an old unpriced Roofing overlay. Single/current surface totals agree; exact stale renderer/snapshot cause needs a scoped follow-up. No PDF code was changed during DB isolation. Do not claim launch/full acceptance success.
- Physical iPhone/Safari/Messenger/mobile emulation, exhaustive UI correction cases, managed restore and live reset email remain unverified. Details and actual PDF manifest in implementation report.
- Production main remains c049a04b2ac5cc4df3d5c253fe9ca12f1d85806a,dep-db5b726k1f9s73e862ug. No original data was cloned/exported; no original DB or real account writes. Generated fixture capability files removed; no secrets recorded.
- Stop for owner review. No new code, provider migration, Stripe or infrastructure change authorized by this checkpoint. If QA connection cannot be verified, stop recovery; never use the shared original database as fallback.

---

The earlier entries below are chronological history and are superseded where they describe shared storage or pending implementation.

## Database-only follow-up checkpoint

- Reverified starting recovery HEAD cde3d5b7f41a04584ccf90809a319b88da41f98e; GitHub runs 41227746551 and 41227746432 SUCCESS, including recovery/PG jobs 124615339714 and 124615339925. Do not rerun completed application/PDF tests merely to resume.
- Recovery remains live at application 764f1ff, dep-dbj2ldrm8hqs73fc0ao0. Main/production candidate c049a04 and dep-db5b726k1f9s73e862ug unchanged. New documentation commit uses [skip render]; any automatic GitHub results must be checked on that exact commit. No manual deployment authorized.
- Paid system SELECT now shows 4,612 successful WAL archives, zero recorded failures, latest archive October31 19:13:07.422881 UTC. Actual recovery dates/base-backup chain/workspace retention still inaccessible. No restore/export attempted.
- Connector role: non-superuser, no RLS bypass, but CREATE DATABASE/ROLE privileges and ownership of 28 user tables. App role mapping remains unknown; do not equate connector and application roles. Startup uses DDL, so blind privilege revocation could break it.
- Test/production DB identities, linked env groups, credentials equality and stable session secret presence remain unverified. Missing DATABASE_URL would choose ephemeral SQLite; missing FLASK_SECRET_KEY would generate a per-process secret. These are code risks, not confirmed deployed mistakes.
- QA remains available Free PG16, expiry November20 22:09:13.900851 UTC /15:09 MST. One aggregate query blocked by empty external allowlist; no retries or rule changes. Do not approve expiry until masked references and current metadata are verified via an authorized internal path.
- New practical incident plan covers deletion, corruption, unavailability, code rollback, bad migrations and preserving post-backup writes/revocations. RTO/RPO values are proposed goals, not measured commitments.
- Next step: read-only Dashboard Recovery and masked service/environment review with named responder. Obtain separate approval before restore rehearsal/costs, network rules, roles, connections or infrastructure changes. No secrets should be sent in chat. Stop for review.

---

# Resume here — October 31, 2026

## Branch and checkpoint

Use ONLY `landscaping-multi-area-recovery-oct11`. Start from the latest remote HEAD; do not overwrite newer work. This document's containing commit is the final documentation checkpoint. Latest verified application commit: `764f1ff67d1d86f53fdefb44b28182ae8cc6dbbf`, following separate roof-integrity fix `e9edb235236a8a09874a0c90a54fb680b732e490`. Starting checkpoint was `b4e69d4`.

Read [today's batch evidence](QA_LAUNCH_RELIABILITY_2026_10_31.md), [database audit](DATABASE_SAFETY_2026_10_31.md), [monitoring/release proposal](MONITORING_DEPLOYMENT_APPROVAL_PLAN_2026_10_31.md), [blockers](LAUNCH_BLOCKERS_2026_10_31.md), [supplier status](SUPPLIER_STATUS_2026_10_31.md), developer handover and emergency recovery guide before continuing.

## Saved and verified

- Reject overlapping billable roof scopes independently of client QA flags; block unsafe PDF/Print before capture. No historical data migration.
- Stable evaluation of the existing server spherical area formula fixes tiny-area cancellation. Same model/tolerances; independent geodesic differences documented.
- Full local 78/78 commands; both application commits pass GitHub regression/PostgreSQL. Latest runs 41226577977 / 41226578063, PG job 124611878682.
- 1,200 randomized geometries; 72 valid API estimates; 276 manipulated requests rejected; 60 revision/conflict cases.
- Actual isolated Chromium 19 cases; 38 downloaded PDFs, 69 pages rendered and inspected. Synthetic imagery only. No fresh physical-device, Safari/Messenger or real-provider verification.
- Recovery live deployment dep-dbj2ldrm8hqs73fc0ao0 at 764f1ff. Documentation checkpoint intentionally skips Render deployment. Verify final GitHub checks again on resume.
- Main remained c049a04; production dep-db5b726k1f9s73e862ug. Production settings/databases/customer accounts untouched.

## Highest priorities next session — obtain authorization before infrastructure changes

1. Dashboard read-only verification of actual paid DB backup/recovery timestamps and workspace plan retention. WAL archiving alone is insufficient. Confirm test/production DATABASE_URL and roles by masked identities, never expose secrets.
2. Expiring QA dpg-dbcjg2brjlhs73dn1g7g-a: available free PG16, expiry November 20 at 22:09:13.900851 UTC. External SQL refused; no content verified. Inspect authorized internal schema/count metadata and every service/env-group reference before declaring disposable. Do not upgrade/delete/export/change access without approval.
3. Paid DB external allowlist currently 0.0.0.0/0; propose restricting authenticated external access after dependency inventory. Internal clients require separate assessment. No setting changed.
4. Review unapplied CI patch and production settings proposal. Production currently On Commit and lacks confirmed approval gates. No production gate, branch protection, monitor or alert recipient was configured.
5. Choose owner + technical responder; approve affordable uptime/error monitoring with strict event allowlisting and no PII/session replay. Trial/free service terms and actual notification delivery remain to verify.
6. Continue targeted genuine reliability testing only with QA data; owner physical iPhone confirmation remains distinct from emulation. Preserve RETRACE interface and all imagery/PDF designs.
7. Supplier: Stadia removed from active shortlist following explicit standard-terms tracing rejection reported by Sean. Spexi verbal CAD2,500/year ~13,333 lookups, Aaron coverage and written rights pending. Mapbox indicative 25,000/year with currency/inclusions/rights unsigned. No vendor contacted or integration approved. Stripe remains on hold.

No autosave, new tool, imagery change, allowance/price change or major infrastructure change authorized by this batch. Stop for owner review.
