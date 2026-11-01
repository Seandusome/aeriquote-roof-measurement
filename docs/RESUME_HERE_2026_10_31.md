# November 1 — browser exception/retry matrix executed and PASS

Read [browser QA and startup diagnosis](QA_BROWSER_CRASH_RECOVERY_2026_11_01.md). Final Chromium41355170665 at167a3ece executed all5jobs PASS; fresh1440/390contexts cover signup/login failures and success, six-industry measurement/preview/reopen/PDF, API503/imagery failures/acceptance401, expired/wrong-account save, capture interruption and retry. Full recovery41355170615 +application41355170587 PASS, including PostgreSQL16/18. All12 source snapshots pass independent WGS84/Decimal checks.

- Narrow reproduced signup-message defect fixed: browser network/JSON failures now explain retry and retained details. Recovery deployment dep-dbjrg1m7bikc738bl84g LIVE22:07:57UTC at167a3ece; running checkout, fix present, timeout overrideOff/default31days, diagnosticsOff and exact isolated QA DB all verified.
- Original41354803554 never executed browser tests: artifact log shows Flask started; erroneous readiness probe hit nonexistent/health404. Changed to/dealer-login200. Subsequent public test's canonical URL expectation corrected. Failed attempts are not passes.
- Known forced-tab-close limitation: never-saved in-memory draft is lost; saved estimates survive. Normal warning cancellation and caught-error recovery preserve work. No durable crash-draft restore claimed. Physical-phone/Safari/Messenger pending.
- Natural timed-expiry recovery already passed and timeout restored (f30833ff report below). QA helper defaultOff; diagnostics disabled; auto-deploy Off; isolated QA DB unchanged. Main/production/customer data untouched.

---

# November 1 — natural timed session expiry recovery PASS

Read [timed-expiry evidence](qa/timed-expiry-2026-11-01/progress.md). Real signed-cookie age validation, no logout/cookie deletion/clock mock: existing session200 at21:46:55; after deadline21:48:45, GET302 at21:49:04 and estimate POST401 at21:49:07. Unsaved DOM geometry/pricing unchanged; no database writes. Same-owner reauthentication saved exactly one revision; unchanged retry added nothing (estimates1, revisions19→20, receipts22→23). Exact stored customer note/fields/geometry/rates/total pass. Single1page and Expanded3pages visually checked, stress-fixture total$77,799.67 agrees with Decimal arithmetic.

- Instrumentation commit4da90f75 adds default-off QA-only Flask lifetime configuration guarded by exact recovery service AND isolated QA database. Full recovery41353462919 and application41353462905 PASS, including real elapsed expiry test and PostgreSQL16/18.
- Temporary timeout DISABLED after recovery. Cleanup dep-dbjr93gae00c73f2k5sg LIVE4da90f75; runtime overrideFalse, normal lifetime2678400seconds restored. Auto-deploy Off, QA database unchanged; no production/main/customer activity.
- Disposable real elapsed-expiry charged-account test consumes199→200 once; retries/wrong-account409 unchanged. Live charged-plan deductions not claimed.
- Next batch requested: browser JavaScript/crash/failure recovery across signup/login/property/measurement/preview/PDF, fresh contexts and phone-sized layouts. Physical-phone touch stays separately pending. Closing/crashing an unsaved tab remains distinct from authentication expiry.

---

# November 1 — real401 recovery and same-account save PASS

Read [expired-login recovery evidence](qa/expired-login-2026-11-01/progress.md). Unsaved Area2 geometry, custom rate, extra pricing and fictional customer/notes survived authentication loss in the original tab. Owner signed back in separately; account IDs matched. Same-owner retry saved exactly one revision: estimates1→1, revisions18→19, receipts21→22. Unchanged retry added nothing. Exact stored fields/quantities/rates/total passed. Actual Single1page /Expanded3pages visually reviewed; total$1,155.94 matches independent Decimal calculation.

- Authentication was cleared by normal logout in a second tab to exercise real401. Natural time-based expiry, closing/refreshing the unsaved tab and physical-phone touch remain pending; do not infer those from this result.
- Live QA allowances bypass unchanged. Disposable charged-account experiment using real password login at199/200 consumed exactly once; repeated/auth-retry and wrong-account409 did not deduct/write again. Live PostgreSQL charged-account recovery is not claimed.
- No application defect reproduced, runtime code change or deployment. Recovery stays4f2b233f /dep-dbjqlnijnfac738poig0; auto-deploy Off, diagnostics disabled, isolated QA database unchanged. Main/production/customer data untouched.
- QA session remains working; current fictional Paving revision now8,318ft² +188.2640110545814ft, Area2$0.17, extra$37.25, customer QA EXPIRED LOGIN NOV1, total$1,155.94. Prior revisions retained.

---

# November 1 — fresh six-industry PDFs and repeated retrace PASS

Read [current QA evidence](QA_MEASUREMENT_PDF_2026_11_01.md). All six industries now have fresh Single and Expanded PDFs rendered and visually inspected; fourteen PDFs/21 pages including a new repeated-retrace Paving revision. Independent quantities/pricing/taxes/totals agree. No reproducible runtime defect, code fix or deployment this batch.

- Recovery LIVE remains4f2b233f /dep-dbjqlnijnfac738poig0; auto-deploy Off, temporary diagnostics disabled, isolated QA database unchanged. Main/production/customer data untouched.
- Repeated Commercial Area2 Cancel preserved both Areas/Linear/total. Paving Area2 Save twice changed6,227→2,382→2,815ft² while Area1=6,125 and Linear188.2640110545814ft stayed intact. New fictional current revision at21:20:15UTC:8,940ft²/$1,013.24. Current plus18 previous versions retained. Prior Paving17 remains12,352ft²/$1,391.97; original Roofing remains7,348ft²/$815.67.
- Allowance fixture fix7e01cec2 confirmed: full recovery41350107603 and application41350107613 SUCCESS, including PostgreSQL16/18 and login diagnostics. No runtime allowance change.
- Physical touch, expired-login/unsaved-work recovery and fresh Linear-drag checks remain outstanding. Fresh desktop PDFs are now verified; do not repeat the historical missing-download report as a current app defect. Download files one per browser tool call.

---

# November 1 — live QA sign-in confirmed

At 21:09:39 UTC the owner-entered browser attempt emitted `received`, `owner_found`, `owner_verifier_pass`, `session_created`, correlated ID `440aa779f94c430a98e8332985b29ca4`. Authentication POST returned 302; subsequent application GET returned 200. Browser tab 5 reached `/` and displayed the authenticated measuring workspace with LOG OUT and PREVIOUS ESTIMATES. This proves credential verification, session creation, redirect and browser session continuity for this attempt. No password/account change occurred. The verified fictional QA email had been prefilled before the owner entered their password. Earlier failures remain unexplained; do not assert a password defect or email typo.

Temporary diagnostics disabled by merging only `AERIQUOTE_LOGIN_DIAGNOSTIC_EMAIL` to an empty value. Render automatically launched cleanup deployment `dep-dbjqlnijnfac738poig0` at commit `4f2b233fccc9a8a2a44cfdd3bc7449195190f91d`. Cleanup reached LIVE at 21:11:38 UTC. New runtime verified commit `4f2b233f`, diagnostics disabled=True, QA database unchanged=True; Render auto-deploy confirmed Off. Auto-deploy must remain Off. All connections, account settings, main, production and customer data remain untouched. Full CI on runtime-equivalent fixture fix `7e01cec2` passed, as recorded below. No new measurement/PDF batch this follow-up.

---

# November 1 — deterministic allowance fixture; login capture still pending

Recovery diagnostics are deployed at commit `dc28613942b57eab773121e463caf2d354d9b444`, deployment `dep-dbjqfq3bc2fs73djc4og`. Running checkout, recovery service, exact isolated QA database (`dpg-dbj4f7lg1s2s73eob8t0-a`, logical DB `aeriquote_recovery_qa`) and single-email gate were verified internally. Auto-deploy remains Off. Main and production untouched.

The owner authorized publishing/deploying diagnostics. They are enabled only for `qa-browser-oct31-2026@example.invalid`. Browser failure observed at 21:05:39 UTC, but it produced no scoped diagnostic events and no retained known-QA identity counter; do not infer the submitted identity or password from this absence. Worker configuration was rechecked: exact QA database, exact diagnostic gate and recovery service all true. A single controlled server request with the known QA email and a deliberately invalid synthetic password at 21:07:45 successfully emitted received/owner_found/owner_verifier_fail/employee_missing/rejected, ID `ae1f7ce4f9914bafaa664cf10a30ea3d`. This validates the instrumentation, not the cause of the user failure. No real password was read or changed. A user-entered attempt with the verified identity prefilled is still required. Do not claim the failing login stage is known. Capture one owner-entered sign-in, then disable the temporary diagnostic variable and verify the resulting deployment. Never change the password/account or create a replacement.

Workflow 41349535401 failed in the account-credit fixture at line 81; PostgreSQL 16/18 integrity jobs passed and later recovery checks were skipped. Controlled reproduction: unchanged fixture passes with allowance clock October 20, fails at the exact assertion with November 1. It exhausted the wall-clock current month and incorrectly assumed November 2 was a new month. This checkpoint freezes only the disposable fixture's allowance clock to October 20, preserving the original rollover assertion and strengthening it to require `(True,1,200)` plus separate October=225/November=1 counters. No runtime allowance, pricing or database-connection code changed.

Local validation: complete credit fixture passes under host-clock simulations October 31, November 1, December 1 and January 1, 2027. Existing subscription-period coverage (25/75/200, anniversaries, leap/short months, concurrency, isolation) and login-diagnostic tests pass. Full GitHub rerun on `7e01cec21aa29f4e67e36f648c81ad62c6e38c2f` PASSED: recovery workflow 41350107603 (recovery job 124978248619 and PostgreSQL 16/18 jobs 124978248413/124978248616), including the previously skipped login diagnostics; application workflow 41350107613 also PASSED.

---

# November 1 — login diagnosis prepared; live capture pending

Read [login diagnosis and exact evidence](QA_LOGIN_DIAGNOSIS_2026_11_01.md) before continuing. Sean has used only `qa-browser-oct31-2026@example.invalid` for these failed attempts. The email is directly verified for QA owner `c417b9a2-51ea-4816-84da-1e597a7de98d`; do not suggest alternative emails or repeat password resets.

- Owner-approved recovery compute upgrade is live at US$7/month. It automatically deployed documentation checkpoint `b1562019` as `dep-dbjq0jcs728c738gen3g`; application source remains equivalent to `60ae098`. Auto-deploy Off; QA database connection unchanged. Production/main untouched.
- Owner personally completed a QA-only password reset; auth version now 1. No new password/reset/account replacement authorized. Saved estimates unchanged by that operation.
- Failed login requests reach the recovery server and return the rejection page before its ordinary successful redirect. Exact lookup/verifier decision for a correlated attempt remains unproven. A prepared secure browser-auth attempt was declined; do not repeatedly prompt.
- This containing commit adds default-off, recovery-only, single-email diagnostic stages and random request IDs. Targeted diagnostics, existing login/reset tests and real Gunicorn secret-canary tests PASS. Not deployed or enabled. Owner approval is required before deploying and enabling `AERIQUOTE_LOGIN_DIAGNOSTIC_EMAIL` for this fictional email.
- Fresh live PDF and login/session success remain unverified. Preserve all measurement, pricing, PDF and isolation safeguards.

---

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
