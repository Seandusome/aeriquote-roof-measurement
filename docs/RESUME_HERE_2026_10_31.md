# November 3 — Tax-rounding blocker FIXED; all required checks PASS; UNDEPLOYED; PAUSED

Resumed47be65f9/f8c3d20a. Final tested application source **194c435b377dbcb23ad24a422c63763fcd931ed4**, app.py blob661a1f0b514e04c0a7b3b67945b7ec588ea449fe. Read [rounding fix and evidence](QA_TAX_ROUNDING_2026_11_03.md). Exact367.30×5% tax now rounds decimal half-up to18.37; subtotal367.30+GST18.37+additional22.04=407.71. Browser uses exact decimal/integer monetary arithmetic at the server's existing stages. Server validation/tolerances unchanged; original bad payload remains rejected. Roofing next-action/pitch-confirmation usability and measurement/Save/Cancel safeguards preserved.

Passed1894 cross-language boundary cases,70 real-API matrix fixtures plus forgery/invalid checks, old-source regression red/new-source green, desktop1440 and phone390 save/reopen and both PDFs (four files/six pages) independently verified. Correct totals407.69desktop and407.71phone for their actual traced quantities. A browser fixture wait now observes completed workspace restoration before reopening; customer assertions/timeouts unchanged.

Final-source workflows all completed SUCCESS: application41726151088; recovery41726151080 including PostgreSQL16/18 and backup/compatibility; browser41726151121 **10/10**. Previous9/10 report is superseded. No unresolved automated failures on final source; CI tracked directly.

**No deployment.** Live recovery remains **efb2d29b / dep-dbl3b5gae00c73cfdh50**, auto-deployOFF. QA database binding unchanged; only fictional/disposable loopback jobs/providers used, no live account/job changed. Main, production and customer data untouched. Original two untracked PDF copies preserved. Latest checkpoint is containing documentation commit; application source is distinct above.

Pause for Sean. Next session: visual review of saved Roofing usability before/after; deployment only if separately authorized after fresh QA-isolation verification. Owner manual desktop and physical-phone testing remain pending. Do not restart historical PDF/aerial or uncertain-draft investigations without new evidence/instruction.

---

# November 3 — Roofing next-action usability implemented; UNDEPLOYED; visual review pending

Resumed68b612f6. Application source **f8c3d20a28aa51a33037e15ac09da11794e8ca00**, app.py blob982a6e705057595fba0ff7e8bf490482759452e9. Read [Roofing usability implementation and evidence](QA_ROOFING_NEXT_ACTION_2026_11_03.md). One current action/explanation; pitch beside Save; explicit final confirmation appears only after saved sections and finished drawing/editing; area/pitch list retained; next missing price/customer/Create stage highlighted. Legacy saved-structure summary/repair path retained. No Mapbox/PDF redesign, pricing/measurement/allowance policy or database changes.

Passed locally: manual Roofing Python + DOM/Leaflet safeguards; six-industry pricing guards; actual desktop trace/save/confirm/edit/Cancel/add/delete/reopen; Single+Expanded PDFs independently407.69; three-section old exporter regression253.89. Phone-width UI reaches Create but a real existing half-cent GST bug blocks its save: subtotal367.30 sendsGST18.36; server expects18.37 and rejects, preserving measurements/draft. priceCalc unchanged from68b612f6. No assertion weakened or fixture changed to avoid it. **Not ready to deploy until this separate pricing blocker is resolved and required workflows pass.** Final-source application41723463942 PASS; recovery41723463840 PASS including PG16/18; browser41723463808 **9/10 PASS, roof-exports FAIL on exact390-width GST case**. All workflows completed; no checks still running. Do not assume all pass.

Live recovery stays **efb2d29b / dep-dbl3b5gae00c73cfdh50**, auto-deployOFF, isolated QA databaseunchanged. No deployment; main/production/customer data untouched. No live QA job/account edited in this batch. Two old untracked PDF copies preserved. Checkpoint is containing documentation commit; application source above is distinct.

Pause for Sean's visual review. Next authorized work should fix the exact half-cent rounding discrepancy, retain independent server validation, retest pricing matrix and blocked phone save/reopen/bothPDFs, then rerun required workflows. No further layout scope expansion. Owner manual desktop and physical-phone testing remain pending.

---

# November 3 — Snow rate discrepancy diagnosed; PAUSED

Resumed65512eed. Read [Snow rate diagnosis](QA_SNOW_RATE_DIAGNOSIS_2026_11_03.md). Cloud fill+Tab reproduced displayed/preview mismatch; genuine changed-value typing plus Tab/click-away works. Retyping the same fill-inserted value explains misleading prior follow-up. No user-input application defect reproduced; no app fix/deployment. Test must use keyboard and verify committed state rather than only DOM value.

Focused disposable browser regression PASS: typed rates match active pricing, POST, saved/reopened estimate and Single/Expanded PDFs; independent totalCAD178.14. Blank/negative blocked; explicit zero valid; geometry/Cancel and aborted-save preservation pass. Added standalone test, no new workflow. Final application remains efb2d29b, auto-deployOFF; isolated QA unchanged; main/production/customer data untouched. Live fictional workspace returned to Commercial0.27/linear0.25 and278.65; no additional live revision created. Two old untracked PDFs preserved. Checkpoint is containing commit. Owner desktop and physical-phone review pending. Pause; no usability implementation authorized.

---

# November 3 — First-estimate usability REVIEW ONLY; PAUSED

Resumed 754fe24e; live recovery verified efb2d29ba72306ef718c62f1de86070af1e33ef7 / dep-dbl3b5gae00c73cfdh50, auto-deploy OFF. No code, configuration, deployment or workflow changes. QA isolation preserved; main/production/customer data untouched.

Read [first-estimate usability findings](QA_FIRST_ESTIMATE_USABILITY_2026_11_03.md). Roofing fresh property/draw/explicit pitch confirmation/customer/create/reopen/download completed. Other five industries compared using saved fictional QA geometry; each reached create/reopen/download. Screenshots, DOM snapshots and six PDFs saved. This was not six fresh onboardings or a new full PDF/allowance audit.

Five recommendations: one current next action/blocker; drawing+save together with task-specific labels; one authoritative measurement summary; predictable rate editing in Price with dealer details secondary; direct reopen/download and clear draft-versus-estimate wording. No implementation authorized in this batch.

Separate unverified Snow rate-field/preview discrepancy (input0.10 versus preview0.27); restored matching0.27 before saving. Next authorized diagnostic batch should establish input/change/blur evidence before deciding whether application defect. Do not treat as confirmed. Owner desktop and physical-phone review pending. Preserve two old untracked PDF copies. Latest checkpoint is the containing documentation commit. Pause for Sean's instruction.

---

# November 3 — Roofing confirmation fixed, verified and deployed to isolated recovery; PAUSED

**Launch requirement — ease of use:** Next focused review must follow a new contractor through the complete first-estimate flow and identify unnecessary complexity before layout changes. Aim for one prominent next action, one clear blocking explanation, fewer repeated instructions/status messages, and secondary tools/dealer calculations shown only when needed. Preserve every measurement, pricing and confirmation safeguard; do not add controls to explain other controls. See [next usability review](QA_NEXT_USABILITY_REVIEW_2026_11_03.md). Record only for now: no new tests, layout changes or deployment. Preserve application checkpoint `f42e62b5` and the live source below.

Latest checkpoint is the containing documentation commit. Read [Roofing confirmation evidence](QA_ROOF_CONFIRMATION_2026_11_03.md). Final source and live recovery application: **efb2d29ba72306ef718c62f1de86070af1e33ef7**; recovery deploy **dep-dbl3b5gae00c73cfdh50**. All required exact-source workflows PASS: application41702397105, recovery41702397163 including PostgreSQL16/18 and unchanged backup/previous-version drill, browser41702396986 (10/10).

Prominent **Confirm pitches and included roofs** action replaces the visible checkbox; saved pitches use rise/run; unconfirmed estimates show **Roof confirmation required** with exact instructions. No default 5/12 is silently verified. Edit/Add/Delete invalidate confirmation immediately; Cancel preserves geometry and requests reconfirmation. Manual-only instructions no longer promise automatic main-house measurement. Actual live confirmation, edits, Cancel, add/delete, reopening and both PDFs passed. PDF total $2,262.53 independently reconciled.

QA hostname/database verified immediately before deploy and from the final running instance: dpg-dbj4f7lg1s2s73eob8t0-a / aeriquote_recovery_qa (PostgreSQL18.6). Auto-deploy OFF. Main, production, customer data and connections untouched. Earlier incomplete-upload/previous-app CI failures are superseded by final passing checks; assertions unchanged. Two old untracked PDF copies preserved.

**Pause until Sean instructs otherwise.** His desktop review and physical-phone testing remain pending, along with the previously separate fresh-property manual-rate sequence. Do not expand into old uncertain drafts or promotional sequences. QA app remains signed in as qa-browser-oct31-2026@example.invalid; Render email is sdusome@diitalk.com. Latest fictional job is FICTIONAL PITCH CONFIRMATION NOV3. Its reopened workspace was reconfirmed and autosave acknowledged; no additional estimate save was made after reopening.

---

# November 2 — STATUS/PRESERVATION ONLY; STOPPED

The conversation reloaded after the Stop control failed. The user explicitly prohibited resuming tests, fixes, workflows or deployments. This preservation note supersedes earlier continuation instructions. Await a fresh instruction before doing further application work.

- Verified recovery checkpoint before this note: `851e668212c8213e98c5197ef6c91108241810d2`. Application source remains `c7f2d013edf4425972c3fd8da48137a9b2d45882`. Local and remote checkpoint trees match; working tree was clean. This turn changes only these resume notes and saves them in a documentation checkpoint with `[skip ci] [skip render]`.
- Existing final-source workflows are completed SUCCESS: application41524565882, recovery41524565618 (including PostgreSQL16/18), browser41524565651 (10/10). No workflow was started or rerun during this status/preservation turn. No unresolved CI failure on the final source. The exact old untraced drafts failure request remains a historical evidence limitation; the controlled cleanup-race regression and complete final suites passed. See the audit report below.
- Render still reports `69ab066c67cb429d4e12c8dad2d902140fbbc405` LIVE at `dep-dbke60u1egvs73cafea0`; auto-deploy OFF. No deployment occurred in the audit or this preservation turn. QA database connections/settings, main, production and customer data were not changed.
- Next steps, ONLY after renewed authorization: (1) read `QA_EXISTING_JOB_AUDIT_2026_11_02.md` and review the saved fixes/evidence; (2) if explicitly authorized, reconfirm isolated QA configuration and deploy the tested application source only to recovery, keeping auto-deploy OFF, then verify live; (3) keep owner desktop review and physical-phone/Safari/Messenger testing pending; (4) prioritize the still-unverified long editing/Restore/PDF sequences under tax-included/discount pricing after the above. No new features or payment work.
- STOP FOR TODAY. No pending local application work needs recovery; all application fixes and evidence were already checkpointed. The containing documentation commit is the latest preservation checkpoint.

---

# November 2 — existing-job audit complete; three fixes verified, NOT deployed

Read [existing-job audit and evidence](QA_EXISTING_JOB_AUDIT_2026_11_02.md). The containing documentation commit is the new checkpoint. Final tested source `c7f2d013edf4425972c3fd8da48137a9b2d45882`; live recovery remains `69ab066c67cb429d4e12c8dad2d902140fbbc405` /`dep-dbke60u1egvs73cafea0`, auto-deploy OFF. No deployment, main/production/customer/account/connection/allowance change.

- Fixed three reproduced defects: delete/add generated duplicate Service Area2 labels; Roof Cancel left saved section controls disabled; terminology translation changed user-authored address/description/customer/branding/history/PDF text (stored values remained correct). Focused regressions fail against old source and pass now; assertions/geometry/pricing/security safeguards preserved.
- Six actual Chromium existing-job lifecycles PASS: replacement/add/delete, line drag Save/Cancel/remove/re-add, three differently pitched roofs, customer/rate/extras/decimal-tax changes, exact draft Restore, lost response/retry exactly one revision/receipt, true stale older editor409 with work retained.24 invalid active measurement requests400 leave history/allowance unchanged.
- Same-property Roof→five surface industries retains dormant roof history, sends only priced two Areas+Line to real report endpoint; reverse version reopen and every prior row unchanged. Paid cap25/25 still permits legitimate existing revisions;6estimates/17intentional revisions/23save receipts, only6estimate allowances spent. Normal trial3 cap, provider503, retries, existing edit at cap, stale/invalid no-charge PASS.
- Final source full recovery41524565618 inclPostgreSQL16/18, application41524565882, browser41524565651 all PASS (10/10browser). Drafts41521728752: old request untraced/redacted; new delayed-Restore cleanup reproduces early Create warning+pending with zero estimate POST, then one200 retry. Test now waits for actual completion and records HTTP statuses. Job-revisions from that run exposed the real Roof Cancel defect. Other fixture corrections are documented; no current CI failure.
- 34final PDFs/63pages,17snapshots independently reconciled (WGS84/Decimal) and visually checked. Surface edited totals383.26; Roof253.89→1192.06; mixed surface352.61/381.31/409.99/438.68/467.37. Final44pages raster-identical to reviewed prior output;19changed pages reviewed again. Correct Roof/Garage text retained; inactive roof outlines excluded. Before-fix Snow PDF/source preserved separately.
- Pending: separately authorized recovery deployment/live verification of this batch and preceding manual-rate fix; owner desktop review; physical-phone/Safari/Messenger. New long-sequence promotional/tax-included PDF checks remain unverified (existing policy regressions pass). Synthetic providers are not real imagery/measurement accuracy evidence. Stop for today; do not deploy this documentation checkpoint.

---

# November 2 — fresh-user manual-rate correction verified; NOT deployed

Read [fresh-user desktop QA and evidence](QA_FRESH_USER_DESKTOP_2026_11_02.md). The containing documentation commit is the new checkpoint. Final tested source `3344821509fd3ef82c37cbacdfed04d1fbc88140`; live recovery remains `69ab066c67cb429d4e12c8dad2d902140fbbc405` / `dep-dbke60u1egvs73cafea0`, auto-deploy OFF. No deployment in this batch. Main/production/customer data and isolated QA PostgreSQL configuration unchanged.

- Reproduced manual-rate onboarding silently enabling $0 quotes (Pressure instead substitutes default). Fix respects per-job manual selection, retains blank/unentered rates through area/linear transitions and next-property reset, and uses existing blocking instructions. Deliberately entered zero remains valid. Six-industry DOM guard regression PASS; no pricing/allowance policy change.
- Actual fresh signup/business setup/first mixed Paving measurement/customer/save/history reopen/Single+Expanded PDFs PASS in disposable Chromium with normal trial, not QA bypass. Missing region/rate and invalid tax preserve work and prevent incomplete saves. Trial cap3 and paid24→25, failed imagery no-charge, retained previous measurements/customer, exhausted retries PASS. One estimate/zero revisions/one save receipt at first save. Policy-only repeat acceptance also idempotent.
- Exact final source full recovery41518595807 (including PostgreSQL16/18), application41518595816 and all9browser jobs41518595902 PASS. Fixture boolean/receipt scope/dialog navigation corrections are documented; assertions/protections remain. No unresolved CI failure on final source.
- Single1page/Expanded3pages rendered/visually checked; independent WGS84/Decimal PASS. Two659ft² areas@0.10 plus62.04996ft@0.10 yield138.00+6.90+8.28=CAD153.18. Fictional customer/company match. Evidence at qa/fresh-user-desktop-2026-11-02.
- Pending: separately authorized recovery deployment/live check of this batch's fix, owner manual desktop review and physical-phone/Safari/Messenger. Synthetic fixture does not prove external provider uptime or payment integration. No new features/payment work. Stop for today.

---

# November 2 — 69ab066c LIVE; actual interrupted saves and recovered PDFs PASS

Read [live deployment and evidence](QA_LIVE_INTERRUPTED_SAVES_2026_11_02.md). This supersedes the preceding deployment-pending note. The containing documentation commit is the new checkpoint; do not deploy it.

- Exact application69ab066c67cb429d4e12c8dad2d902140fbbc405 deployed only to recovery, dep-dbke60u1egvs73cafea0 LIVE19:23:34UTC. Pre/post running-process assertions confirm exact isolated QA host/database. Auto-deploy OFF; diagnostics/QA timeout override OFF. Main/production/customer data untouched.
- Actual live cross-tab Restore matches full quote/all field hashes; original consumed tab saves later edits once; stale second tab warns and retains its acknowledged work. Real50-second QA-row delay crosses normal30-second save timeout: eventual commit then receipt-confirming browser retry adds no extra revision/receipt. Live55-second draft-row delay crosses normal12-second autosave deadline; newest edits acknowledge, actual tab closure/Restore matches exact hashes, explicit save once. Temporary locks released; test connections0.
- Counts1/21/24 baseline →1/22/25 original explicit save →1/23/26 delayed save →retry unchanged →1/24/27 recovered save. Both PDFs and fresh history reopen leave1/24/27 unchanged. Active drafts0; closed retained payloads0. QA bypass unchanged/month usage[]; paid-plan proof remains disposable PostgreSQL16/18, not a live paid debit.
- Actual Single1page/Expanded3pages rendered and visually checked:6,125ft²@0.10 +1,733@0.27 +188.264ft@0.10 +extra54.25; tax base1,153.49 +57.67 +69.21 =1,280.37. Customer/geometry/pricing match; no inactive Roofing outlines. WGS84/Decimal independent checks pass. Street View assessment placeholder is expected under approved byte-exclusion policy.
- Source69ab required recovery41505173423, application41505173311 and browser41505173632 all PASS, including PostgreSQL16/18 and8browser jobs; no application code changed this live batch. No new application defect reproduced. Browser extension metadata errors are tooling observations only; actual downloads completed.
- Pending: owner manual desktop review and physical-phone/Safari/Messenger. Tab7 saved recovered report, tab6 post-save report, Render shelltab4 retained if available. Stop after saving this bounded batch; await the next instruction.

---

# November 2 — interrupted-save fixes and manual Roofing fixture diagnosis

Read [the current QA report](QA_INTERRUPTED_SAVES_2026_11_02.md) first. Recovery source is69ab066c; the containing documentation commit is the new resume checkpoint. Recovery deployment remains0f065b9d /dep-dbjsosetlv9c73e6ck3g, auto-deploy OFF. Current source fixes are NOT deployed.

- Fixed reproduced response-integrity defects: malformed estimate-save responses no longer clear pending work; malformed autosave acknowledgements no longer claim durability; uncertain accepted autosaves are reconciled with their exact version/payload before newer edits (including local revert and temporary wrong-account rejection). Pending operation/base versions and account/stale guards remain intact. No new features or schema/pricing/allowance/integration changes.
- User-reported41503616072 manual Roofing failure: Single did not reach save because an obsolete HTTP200 `{}` mock left the real report unprepared. Valid id/version mock plus stricter per-layout/report-ready assertions fixes the fixture. Original both-exporters assertion retained. No PDF runtime change. Actual Chromium roof-exports downloaded Single1page/Expanded2pages with three22.62/0/45degree sections, customer and253.89 total; independent WGS84/Decimal and visual inspection pass.
- User-reported41504755573 draft-races failure was a test synchronization race against the last deliberately malformed background PUT. Injection now drains before recovery; exact newest server note is asserted. Latest browser41505173632 all8jobs PASS, including draft-races and roof-exports. Application41505173311 PASS. Full recovery41505173423 PASS, including PostgreSQL16/18, the manual-roofing assertion and every previously skipped downstream check. Final cleanup completed. All required workflows pass on69ab066c; no unresolved CI failures. Results are recorded in the QA report/evidence.
- Mainc049a04b /productiondep-db5b726k1f9s73e862ug unchanged. QA PostgreSQL18 resource available, external allowlist remains empty. Prior browser sessions are absent and Render shell needs login, so internal runtime-to-database binding was NOT reverified. No deployment or live-data write was attempted. Do not deploy until that binding is verified again; do not open DB networking or ask the owner to test today.
- Pending: recovery-only deployment/live verification after isolation check; owner manual desktop review; physical-phone/Safari/Messenger. Owner is unavailable for manual testing. Automated work used fictional loopback/disposable QA only. After saving this checkpoint, STOP. Continue only on new instruction; track CI failures directly.

---

# November 1 — desktop race fixes; end-of-day checkpoint

Read [desktop closeout](QA_DESKTOP_CLOSEOUT_2026_11_01.md) and [tomorrow's short desktop checklist](QA_TOMORROW_DESKTOP_2026_11_02.md).

- Two reproduced defects fixed: delayed Restore cleanup no longer removes a newer acknowledged source or already-committed receipt; explicit Create can preserve later edits after its original recovery ID closed elsewhere, retaining operation/base version. Background resurrection/account/stale conflicts remain blocked. No new features.
- Runtime source0f065b9d. Full recovery41362491708 PASS including PostgreSQL16/18; application41362491712 PASS; actual Chromium41362491734 all7jobs PASS, new delayed-cleanup/original-tab/stale-editor cases included. Evidence in qa/desktop-closeout-2026-11-01.
- Recovery deployment/runtime/isolation verification appears in the closeout report. Auto-deploy Off; main/production/customer data untouched. No live QA estimate was edited in this batch. Prior fictional job remains1,200.65 and prior live recovery/PDF evidence is retained.
- Pending: physical-phone/Safari/Messenger. New race paths verified in actual automated browser/disposable DB fixtures; not manually repeated live after deployment. Owner requested no more manual testing today.
- The containing docs/evidence commit is the final checkpoint; do not deploy it. STOP FOR TODAY. Tomorrow: refresh recovery, use QA only, follow the three-item checklist.

---

# November 1 — live acknowledged draft recovery and Discard PASS

Read [live recovery evidence](QA_LIVE_RECOVERY_DRAFTS_2026_11_01.md). Owner signed in; actual tab9 closure/newtab10 Restore preserved the full quote and all captured fields by canonical SHA256. New Paving Area2=1,733ft²@0.23; Area1=6,125@0.10; Linear188.264ft@0.10; extra51.75. Independent total1,200.65 =1,081.67+54.08+64.90. Actual Single1page/Expanded3pages rendered and visually inspected; all active measurements/customer/pricing match.

- Restore: counts1/20/23 unchanged. Explicit save:1/21/24. Unchanged retry and PDF downloads:1/21/24 unchanged. Save deleted the recovery payload. Discarded a separately acknowledged note-edit draft, refreshed, confirmed zero Restore choices/active drafts/retained payloads; saved note unchanged. Saved current estimate reopened intact afterward.
- Live QA allowance bypass unchanged; monthly usage rows stayed empty. Charged-plan199→200 exactly-once coverage is from prior passing disposable PostgreSQL16/18 tests, not a new live charge. Street View bytes are excluded by design; recovered job uses a labelled assessment placeholder. See report for scope.
- Runtime/deployment unchanged:0f78e40f /dep-dbjs3aajnfac738t6vs0; auto-deploy Off; exact isolated QA DB verified. No code fix/deploy/account/network/pricing/allowance change this batch. Main/production/customer data untouched.
- Tab11 is signed in and displays the saved recovered current estimate. Render shelltab3 is read-only verification. Originaltab5 remains available. Physical-phone/Safari/Messenger still pending.
- The containing documentation/evidence commit is the next resume checkpoint. Do not deploy it. Previous b975e036 authenticated-smoke pending item is resolved by this live batch.

---

# November 1 — server recovery drafts deployed; full regression rerun PASS

Read [recovery drafts and evidence](QA_RECOVERY_DRAFTS_2026_11_01.md). Owner-approved24-hour server drafts are implemented with business+individual isolation, separate tab records, Restore/Discard, immediate save/discard payload deletion, stale-write tombstones, retained save IDs/base versions, acknowledged/offline status and no-charge imagery-session rehydration. No production/main/account/connection/pricing/allowance change.

- Verified source0f78e40f; full recovery41358627500 PASS including PostgreSQL16/18 and every check after the previously failing test; application41358627501 PASS; actual Chromium41358627517 all6jobs PASS. Independent WGS84/Decimal16sources pass;8restored PDFs/12pages rendered/visually checked. Evidence under qa/recovery-drafts-2026-11-01.
- User-reported41357915739 line40:150 was a missing VM dependency: extraction omitted stableWorkspaceJSON, causing null fingerprints and an unwanted saved-work warning. Fixaa711367 includes the real helper; all warning/idempotency assertions unchanged. Omitting the helper reproduces failure, corrected fixture passes, and full CI now passes.
- Recovery dep-dbjs3aajnfac738t6vs0 LIVE22:48:55UTC at0f78e40f. Running commit, exact isolated QA DB and service verified; auto-deploy Off; diagnostics/QA timeout Off. Live login200, script200, unauthenticated drafts API401. Read-only QA counts unchanged1/20/23.
- Pending live authenticated Restore/Discard smoke: fresh browser tab9 reached login. No password/account change; do not guess why or repeat credentials. Known QA identity qa-browser-oct31-2026@example.invalid. Automated owner/employee/charged recovery passed. Physical-phone/Safari/Messenger pending.
- Original saved measuring/report tab5 remains available; Render shelltab3 verified newinstance6d7rr. Preserve these if continuing. The containing docs/evidence commit is the final checkpoint; do not deploy it. Mainc049a04b and productiondep-db5b726k1f9s73e862ug untouched.

---

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
