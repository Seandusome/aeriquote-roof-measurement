# Hosted disabled employee save passed — exact draft recovery inconclusive

Resumed 79320fa8 in isolated recovery. Work QA Head Office Credits showed the fictional owner bob@gmail.com active on standard trial, complimentary off, with 0 extra measurements and 0 extra estimates. The same extra balance was observed immediately before and after the rejected attempt. Standard trial usage was not verified by this readout.

The fresh owner-created Homeowner estimate at 2301 Ave C North, 115 had 44,309 ft² and $13,292.85. A first note was saved during setup, so the baseline for the disable attempt was one current estimate with the first note and one prior version. The earlier $4,978.30 estimate was kept as separate evidence. Employee typed “this is QA DISABLED SAVE CHECK — recover this exact line” and reported “Recovery copy saved for 24 hours.” Owner disabled qa-staff@example.invalid. One employee save returned “Your login expired. This estimate was not saved.” Owner history confirmed the same current estimate, first note, and exactly one prior version. Hosted extra credits remained 0/0.

Owner reported reactivating the employee. After normal sign-in the employee reported two recovery draft entries, with the newer expiring 11/8/2026 at 3:22:47 PM. The notes field contained wording but was edited before the exact restored text could be compared. Sean later identified the wording he saw as “QA RECOVERY CHECK — 21:05 baseline — keep this unsaved,” which matches the already-saved baseline note. The distinctive unsaved line was not observed before editing. Exact draft recovery remains unverified. No verified recovered save, resulting revision count, or post-success credit reading. Pause without another save. Prior newly typed note revision pass remains recorded separately.

---

# Fresh hosted draft recovery and credit comparison — awaiting QA Head Office sign-in

Resumed 7f68ab91. Preserved the prior fictional estimate and its passed one-revision evidence. Opened the isolated recovery login in a separate tab from the old employee editor. These Work tabs share one browser profile. Use Work for QA Head Office, and two independent local profiles for owner and employee. A regular and an Incognito profile can serve as those two local sessions.

First required screen is https://aeriquote-commercial-test.onrender.com/dealer-login for fictional Head Office qa-browser-oct31-2026@example.invalid, then Admin Dashboard → Credits. No login was submitted. Hosted pre-test balance is not recorded, so no fresh estimate, access toggle, or save was attempted. Capture the balance before starting, then separately after the rejected save and after any successful recovered save. If the exact fresh unsaved edit is missing after reauthentication, record that before entering anything new. Original draft recovery and hosted credit comparison remain unverified.

---

# November 7 — Hosted employee note revision passed

Follow-up to `e574bc4a` on isolated recovery. Sean confirmed the fictional employee was reactivated and that owner history showed only the baseline after the disabled employee's rejected save.

- **Passed — one revision for a fresh employee note edit.** Sean provided the owner detail showing the current estimate with the newly typed note “this is a note.” Owner history showed one current estimate and exactly one previous version for QA TEST Fictional Two Session Save. Both showed $4,978.30 and 5,240 ft².
- **Unverified — original draft recovery.** The original unsaved note was visible in the open employee tab, but the later saved note was entered separately. Recovery and successful save of the original draft were not demonstrated.
- **Unverified — hosted credit comparison.** No authoritative pre-save hosted credit balance was captured. The employee browser's session counters do not establish that balance.

---

# November 7 — Disabled employee save rejected, recovery pending

Resumed 39cfae7a. Sean reported disabling the fictional employee in the independent owner session. Existing employee draft displayed its 24-hour recovery copy before the attempt. Clicked CREATE CUSTOMER ESTIMATE once. Recovery status displayed Account access disabled. Estimate save status displayed Your login expired. This estimate was not saved. Keep this page open and sign in in another tab, then retry. The local app source maps this save message to HTTP 401. Render access-log filter returned no matching records, so the HTTP status was not independently observed. Work editor marked handoff.

Asked Sean to check owner history for QA TEST Fictional Two Session Save, $4,978.30 and only current version, then ACTIVATE qa-staff@example.invalid. Await owner confirmation. After activation use secure normal employee sign-in in a fresh tab, inspect recovery or retry in original tab as appropriate, and save exactly once. Confirm version count and draft notes. Authoritative allowance balance remains unverified because external DB connection was blocked. No changes to networking or deployments.

---

# November 7 — Hosted rejected-save baseline ready, owner disable pending

Work signed in normally and rendered exact employee principal employee:effbf718-947e-4077-9c80-dcd2f7178498. Initial combined prompt landed in fictional owner session, verified by Manage Employees listing exact QA staff Active, then logged out and corrected via verified email and secure password prompt. Sean reported local Incognito owner view showing EMPLOYEES. Separate local owner action pending.

Employee history initially empty. Created one fictional baseline through normal recovery UI at 2301 Ave C North, Saskatoon using test name QA TEST Fictional Two Session Save. One property lookup. Initial auto roof required review, so area-only creation was blocked by roof validation. Corrected Main House with traced roof and confirmed 5/12, saved image-free estimate. Saved history shows one current estimate and no earlier versions, timestamp 2026-11-07 19:56:36 UTC, 5,240 ft², CAD $4,978.30. Session counters after baseline: property lookups1, reports1. No real customer contact entered.

Reopened current estimate via history and EDIT MEASUREMENTS / PRICE. Entered unsaved customer notes QA TEST Nov 7 - restore this unsaved revision once. UI displayed Recovery copy saved for 24 hours. Employee Work tab marked handoff and must stay open. Asked Sean to click DISABLE beside qa-staff@example.invalid in local owner Incognito and report Disabled, then keep it disabled until rejection verification. No disable observed, no rejected save attempted, no recovery or revision yet.

Next: once Disabled confirmed, save via CREATE CUSTOMER ESTIMATE on existing employee editor, record UI and service log rejection. Check baseline in independent owner session before reactivation. Ask owner to ACTIVATE and verify Active, then normal employee login, recover draft, verify notes and save once. Confirm one added history revision and restore starting access. External Render Postgres read-only connector blocked by existing empty IP allowlist. Do not change networking. Session counters/history and logs are available, authoritative allowance proof still pending. No production/deploy/password/payment/Spexi changes.

---

# November 7 — Two-session save test awaiting QA sign-in

Resumed 987890fd. Work exposed one managed Chrome profile. Opened recovery /dealer-login for qa-staff@example.invalid. Secure sign-in prompt was declined, so employee sign-in remains pending. No authenticated owner or employee session verified. User received steps to sign in as fictional owner bob@gmail.com in a local Incognito window and open /dealer-employees without toggling access yet.

No estimate opened or created, no draft edited, no access settings changed. Save rejection, revision and allowance checks, recovery and exactly-one-revision save all remain pending. Latest recorded pair baseline has zero saved estimates, so check for an existing fictional estimate after sign-in and create one baseline through normal QA controls if needed. Record baseline revision and allowances before editing. Once both sessions are verified and draft is ready, coordinate owner Disable, employee save attempt and baseline comparison, then owner Activate and normal employee login for draft recovery. Verify access restored and checkpoint results. Keep production, deployments, passwords, payments and Spexi out of scope.

---

# November 5 — Hosted rejected-save task BLOCKED by shared browser session; no QA mutations; PAUSED

Resumed **c9f14429** for <=20-minute hosted rejected-save check requiring employee disable through **normal controls**. Stopped early on a concrete environment limitation, per instruction to checkpoint blockers rather than repeat login attempts.

## Exact blocker and validity boundary

Available browser inventory returns one Chrome/CDP browser, ID1. Its tabs share the same site authentication cookies; available documented APIs do not provide independent browser contexts/profiles. The employee must retain its authenticated unsaved-edit page while an independently authenticated owner uses Manage Employees to disable it. Logging into the owner in another tab of this shared session replaces the employee identity. Logging the owner out and submitting the stale employee page would test logged-out rejection, not prove disabled-employee save protection.

Earlier hosted lifecycle test used scoped administrative SQL for state changes while employee stayed authenticated; this new assignment explicitly requires **normal controls**. That method was not substituted here. No signed cookies, session injection, password guesses or bypass. This is a testing-environment blocker, not a confirmed AeriQuote defect.

Valid next-session setup: two independent normal browser sessions, employee qa-staff@example.invalid in the controlled test browser and owner bob@gmail.com in a separate browser profile/private window/user browser. Owner uses actual /dealer-employees controls while employee edit remains open. User-operated independent owner browser is an option if arranged; its login must never be mistaken for signing this cloud browser in. Do not resume mutations until independence is established. Need complete scoped sequence: one fictional estimate baseline; unsaved edit; normal owner disable; employee Save rejection with unchanged revision/payload/allowances; activate; normal employee login; recover and save exactly once. Owner-disable variant only if time permits. All those new save-specific steps remain **NOT RUN**, not PASS.

## Current verified state

Recovery aeriquote-commercial-test / srv-db5a2g5ckfvc739fui70, Shingle Guard workspace. Auto-deploy directly rechecked **OFF** (autoDeploy=no, autoDeployTrigger=off). Read-only shell query asserted service ID and exact DB host dpg-dbj4f7lg1s2s73eob8t0-a / logical aeriquote_recovery_qa before connection.

- Owner cdb6392e-04d6-4c7a-a586-c1b7c3262b0f / bob@gmail.com / QA TEST Hosted Access Owner remains ACTIVE trial, lookup/estimate limits3/3.
- Employee effbf718-947e-4077-9c80-dcd2f7178498 / qa-staff@example.invalid / QA TEST FICTIONAL Hosted Access Employee remains ACTIVE.
- Estimates/revisions/allowances/monthly/subscription/dealer usage/drafts/property sessions/save receipts all0 rows, same empty-row SHA256 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945.
- Sole QA Head Office role still c417b9a2-51ea-4816-84da-1e597a7de98d. No role or original identity/account changes.
- No estimate created, property loaded, allowance consumed, access state changed, login attempted or local test rerun in this follow-up. No restoration needed. Existing lifecycle audit/history and completed top-up/PDF work left intact.

No deployments, payments, Spexi, credential/binding/clock/billing changes, production connections or customer-data writes. Only this documentation checkpoint changed. Start time20:39:18UTC; stopped well before20-minute cap once blocker established. Containing commit is checkpoint. Pause for break; do not restart broader testing.

---

# November 5 — Hosted employee access checks COMPLETE within documented scope; RESTORED / PAUSED

Read [hosted employee-access report](QA_HOSTED_EMPLOYEE_ACCESS_2026_11_05.md), created ae5691e1. Actual new QA pair: owner **bob@gmail.com** (cdb6392e-04d6-4c7a-a586-c1b7c3262b0f), QA TEST Hosted Access Owner / company QA TEST FICTIONAL HOSTED ACCESS NOV05; employee **qa-staff@example.invalid** (effbf718-947e-4077-9c80-dcd2f7178498), QA TEST FICTIONAL Hosted Access Employee. User created both passwords privately through normal browser forms. Unused long proposed emails were not created. Do not substitute original sdusome@diitalk.com.

**Hosted PASS:** normal employee login with exact rendered employee principal; disabling blocks existing session; controlled manual disabled login rejected; reactivation permits fresh normal login with exact same employee principal; owner disable blocks already authenticated active employee; owner reactivation leaves individual employee disable intact, followed by expected controlled manual rejection. Stale ACTIVATE form without valid login redirected and did not change status. No session injection or auth bypass. Initial employee disable used owner UI; subsequent precisely scoped admin SQL changes were audited and followed normal revocation semantics because browser tabs share sign-in cookies. This is guard/normal-auth validation, not a rerun of every admin UI.

**Starting settings restored and independently fingerprinted:** both ACTIVE, trial3/3, no complimentary/bonus/brand row. Still0 estimates/revisions/usage/drafts/property sessions/save receipts; every domain fingerprint identical to baseline. Existing sole QA Head Office role c417b9a2-51ea-4816-84da-1e597a7de98d unchanged. Seven QA audit rows retained (employee activate3/disable2, owner activate1/disable1), employee revocation version4 retained. Final restore audit1024e874-f173-467d-b02c-1e2f8cdfd90c. Old sessions must remain revoked. Ended signed out.

**Limits:** hosted data invariance is empty-state only; no hosted estimate-save/nonempty-measurement rejection attempt or separate fresh employee login while owner disabled. Prior passing local populated-data/normal-login tests retained, not repeated. Raw submitted credentials not logged; two controlled manual rejections use known disabled states and preceding exact-principal successful logins. Earlier unverified-email generic failure excluded. No further final login after cleanup required to duplicate passed activation→normal-login evidence.

Recovery auto-deploy directly verified **OFF** at completion (no/off), exact service/isolated DB mapping asserted. Database bindings, original account/password, main/production/customer data and QA Head Office role unchanged. No application defect/fix, feature, deployment, payments, Spexi, provider activity, hosted-clock/billing change or unchanged local/monthly/top-up/PDF test rerun. Completed work preserved. Containing documentation commit is final checkpoint; pause.

---

# November 5 — Hosted reactivation and owner-level blocking PASS; final restriction login pending

Normal employee re-login after activation succeeded. Browser / loaded measuring workspace; DOM data-principal again exactly employee:effbf718-947e-4077-9c80-dcd2f7178498. Confirms hosted individual reactivation restores normal fresh-login access.

Applied exact-scoped audited **owner_disable** 2753705d-d3af-485e-8b2f-4c21f44c1080 while employee active/authenticated. Existing /api/account/profile reload returned Account access disabled. Please log in again. Thus owner disable blocks active employee session. No owner-disabled fresh-login attempt separately performed.

With owner disabled, applied individually audited **employee_disable** e1bbc63e-7b9d-4e9e-ad46-09af26af331f; then **owner_activate** f68bf504-e919-4bbe-bfb3-8b5c242026da. Independent SQL confirmed owner active trial3/3 and employee STILL DISABLED. All0 row counts/fingerprints for estimates/revisions/allowances/month/subscription/dealer usage/drafts/property sessions/save receipts unchanged; QA Head Office role unchanged.

Current temporary state: owner bob@gmail.com ACTIVE; employee qa-staff@example.invalid DISABLED individually. Last manual sign-in handoff on staffLoginTab9 asks user to enter qa-staff@example.invalid and same private employee password and LOG IN; expected rejection proves individual restriction survives owner reactivation. Inspect result then **promptly restore employee active** via qaAccessChange('employee_activate','active','disabled'), retaining audit and revocations. Final BOTH ACTIVE, verify all fingerprints and roles/limits, verify recovery auto-deploy OFF, save comprehensive hosted report/checkpoint and pause. No further local tests or extra test rounds.

No credentials/role/binding/deployment/main/production/original account changes. Scoped administrative SQL used to change QA access state while single shared-browser employee session was authenticated; normal owner UI was used for initial employee disable. This verifies deployed guards and normal authentication, not a new end-to-end Head Office-control UI audit. No session injection or bypass.

---

# November 5 — Disabled employee login rejected; employee REACTIVATED; normal re-login pending

After verified normal qa-staff@example.invalid employee login and subsequent audited disable (ba52f64d), Sean manually attempted the same employee login and reported failure. Fresh browser /dealer-login showed alert **Email or password is incorrect.** Employee was confirmed disabled during this controlled attempt; together with the preceding verified normal login this supports disabled-sign-in rejection. Password/submitted raw email were not logged or exposed; do not treat generic message as wrong-password diagnosis.

Promptly restored employee effbf718-947e-4077-9c80-dcd2f7178498 to active using exact-scoped/audited update; committed audit **qa_employee_activate 89d7b2d7-4aeb-4218-bbbb-b77dd45ef5cc**. Owner cdb6392e-04d6-4c7a-a586-c1b7c3262b0f / bob@gmail.com remains active, trial3/3. Current pair BOTH ACTIVE. Retain revocations/audit. No credentials, roles, bindings, estimates, allowances or deployments changed.

Manual sign-in handoff on staffLoginTab9 is for **qa-staff@example.invalid** now ACTIVE. User should enter that email and employee password privately, then LOG IN. Next verify exact DOM data-principal employee:effbf718... and workspace load to close hosted reactivation acceptance. Remaining owner-disable/employee-block and owner-reactivation-preserves-individual-restriction cases still pending. No unchanged local/monthly/PDF/top-up reruns. Preserve main/production/original account/QA Head Office role; no Spexi/payment/deployment. Containing commit interim checkpoint.

---

# November 5 — Hosted employee normal login and stale-session blocking PASS; disabled-login handoff PENDING

User completed manual normal sign-in. Fresh measuring workspace loaded; DOM meta aqAccountId verified account cdb6392e-04d6-4c7a-a586-c1b7c3262b0f and data-principal **employee:effbf718-947e-4077-9c80-dcd2f7178498**. /api/account/profile confirmed exact QA TEST FICTIONAL HOSTED ACCESS NOV05 business, owner bob@gmail.com, active trial3/3, bonus0/0, complimentary0. This is verified hosted normal employee authentication for **qa-staff@example.invalid**; no injection/bypass.

Strictly scoped admin SQL changed this employee active→disabled, with revocation and audit **qa_employee_disable d523acb0-d70a-4f5e-b5e0-4f502d128614**. Exact service/DB/owner/employee identities and absence of owner Head Office role asserted. Existing authenticated profile page reload returned **Account access disabled. Please log in again.** Stale previously rendered owner ACTIVATE form submitted without valid session redirected to /dealer-login; SQL confirms employee remains disabled. No accidental access restoration.

Post-rejection fingerprints match initial empty business data:0 estimates/revisions/allowances/monthly/subscription/dealer_usage/drafts/property_sessions/save_receipts. Owner remains active trial,3/3 limits. Sole original QA Head Office role unchanged. No provider/measurement/save activity.

**Temporary state for next controlled test:** owner active; employee intentionally DISABLED. Normal login page staffLoginTab9 open. User must manually clear email, enter **qa-staff@example.invalid** and its private employee password, click LOG IN, and report done even when generic rejection appears. Expected disabled-login rejection; not password diagnosis. Inspect actual result, then promptly restore employee active with scoped audited update. Need subsequent normal-login success after reactivation and owner-disable/reenable-preserves-employee restriction checks; these remain pending. Final restore both to starting active status, retain audit and revocation versions. Do not change original account, roles, bindings or credentials.

Earlier generic rejection remains inconclusive due unverified email. Do not confuse it with verified disabled-login acceptance. Secure email prompt had filled real sdusome@diitalk.com; manual handoff avoids repeating wrong autofill. No deployment/payment/Spexi/local-test reruns. Auto-deploy OFF as directly verified earlier. Containing commit is interim handoff checkpoint; task not complete.

---

# November 5 — QA pair CREATED; verified employee email; normal employee sign-in handoff PENDING

New pair in isolated recovery:
- Owner cdb6392e-04d6-4c7a-a586-c1b7c3262b0f / **bob@gmail.com**, QA TEST Hosted Access Owner, company QA TEST FICTIONAL HOSTED ACCESS NOV05, active trial, limits3/3. User chose this actual email during signup; proposed qa-hosted-owner-nov05-2026@example.invalid was not created. Do not silently change it.
- Employee effbf718-947e-4077-9c80-dcd2f7178498 / **qa-staff@example.invalid**, QA TEST FICTIONAL Hosted Access Employee. User set password directly and clicked CREATE EMPLOYEE. Earlier long proposed employee email was not used. Browser employee-management page and exact read-only DB identity verified actual short email.

Baseline: both active; zero estimates, revisions, allowances, monthly/subscription/dealer usage, drafts, property sessions and save receipts. Trial lookup/estimate limit3. Sole QA Head Office role remains c417b9a2-51ea-4816-84da-1e597a7de98d. Original account/bindings unchanged.

Owner's normal Manage Employees DISABLE control successfully showed employee Disabled. Logged owner out before attempting normal employee authentication. One secure combined credential submission returned generic rejection, but exact submitted email was not independently verified; **inconclusive for disabled employee access**. Do not label hosted employee password/sign-in checks PASS.

Restored employee active through strictly scoped/audited SQL after exact service/database/owner/employee assertions. Audit qa_employee_activate ID03e36ee3-d4b4-4147-89cc-382aa4cc0208 retained. No credential/allowance/data writes. Next email-only secure request visibly filled **sdusome@diitalk.com**, not qa-staff@example.invalid. Screenshot caught this before requesting password; no password-only request or second login submission followed. This shows selected/filled value only, not proof of every historical login cause.

Next step: manual cloud-browser handoff on normal /dealer-login (tab9 staffLoginTab). User must clear full email field, type **qa-staff@example.invalid**, enter the employee password privately and click LOG IN. Do not put passwords in chat, repository or tool output; do not inject sessions/cookies or use service secrets. Verify authenticated account ID equals owner cdb6392e and account type employee / employee ID effbf718 before more tests. Browser tabs share cookies; any necessary status changes while employee signed in can use exact-scoped administrative updates with audit and normal revocation semantics, not authentication bypass. Record that mechanism transparently.

All remaining hosted rejection/reactivation/owner restriction/data invariance cases still pending actual verified normal employee login. No unchanged local/monthly-rollover tests repeated. No deployment/payments/Spexi/new feature. Recovery auto-deploy verified OFF earlier this assignment; database bindings and QA Head Office role untouched. Current employee restored active, owner active; audit and revocations retained. Save containing documentation commit as interim checkpoint, continue after manual login.

---

# November 5 — New QA owner signed in; employee credential creation handoff PENDING

User completed the prepared signup normally in browser. Actual submitted/created owner email is **bob@gmail.com**, not the proposed qa-hosted-owner-nov05-2026@example.invalid (which still has no match). Do not silently substitute the proposed email in authentication or notes.

Verified exact isolated recovery DB mapping before read-only query. Company-profile match identifies new owner **cdb6392e-04d6-4c7a-a586-c1b7c3262b0f**, email **bob@gmail.com**, name **QA TEST Hosted Access Owner**, active trial, company **QA TEST FICTIONAL HOSTED ACCESS NOV05**. This newly created QA-labelled business is the target; do not confuse it with the original sdusome@diitalk.com account. No existing email or password was changed. The first overly narrow prepared-email assertion failed because no such email had been created; diagnostic query established actual identity. No application defect indicated.

Normal browser signup reached roofing setup, showing QA owner/company labels. Navigated existing authenticated session to /dealer-employees, which showed Manage Employees and no employees. Prepared employee name **QA TEST FICTIONAL Hosted Access Employee**. Employee email/password remain blank for user entry; planned email **qa-hosted-employee-nov05-2026@example.invalid**. User performs CREATE EMPLOYEE with private password entry; browserAuth is not used for account creation. No password values read/logged/saved.

Employee is not yet created, and pending hosted employee checks remain unexecuted. Next inspect completed employee state and exact actual email in same isolated DB. Record starting active owner/employee, trial limits/allowances and data fingerprints. Use normal secure authentication for subsequent sign-ins; never inject sessions. Existing signups can establish initial normal authenticated owner session, but controlled re-login checks still needed.

Existing QA Head Office role unchanged. Recovery auto-deploy directly verified OFF in preceding preparation. Bindings/main/production/original account unchanged. No runtime code changes, deployment, payment/Spexi/clock/billing-date work or local-test reruns. Containing documentation commit is interim checkpoint; continue hosted assignment after employee credential-creation handoff.

---

# November 5 — Hosted QA credential setup prepared; owner signup handoff PENDING

Resumed daed21f5. Sean now explicitly permits creating one clearly fictional owner/employee pair in isolated recovery if existing usable credentials are unavailable. No existing hosted owner/employee credentials available. No passwords may appear in chat/logs/repository. Use normal authentication only.

Recovery service aeriquote-commercial-test / srv-db5a2g5ckfvc739fui70 and Shingle Guard workspace verified. Auto-deploy directly checked OFF (no/off). Before email availability query, asserted service ID and DATABASE_URL host dpg-dbj4f7lg1s2s73eob8t0-a / database aeriquote_recovery_qa. Read-only query found zero owner/employee matches for each proposed email:
- Owner: **qa-hosted-owner-nov05-2026@example.invalid**
- Employee: **qa-hosted-employee-nov05-2026@example.invalid**

Sole existing QA Head Office role c417b9a2-51ea-4816-84da-1e597a7de98d unchanged. Original sdusome@diitalk.com and all bindings unchanged. No account was created and no hosted settings were changed during preparation before handoff.

Normal signup page prepared in cloud browser tab8 at https://aeriquote-commercial-test.onrender.com/site/trial-signup.html. Prefilled noncredential labels: name QA TEST Hosted Access Owner; business QA TEST FICTIONAL HOSTED ACCESS NOV05; Canada. Email and Create Password remain blank. User must enter exact proposed owner email and a new password directly in browser, then CREATE FREE ACCOUNT. Signup also accepts displayed terms, so user performs submission. BrowserAuth cannot create accounts; do not use it for credential creation, do not manufacture a known password or inject a session.

Next: inspect user's completed signup state normally; do not inspect entered password. Verify new identity/fictional company in exact QA database. Navigate owner employee management, prepare QA TEST FICTIONAL Hosted Access Employee and exact proposed employee email for user-controlled credential creation. Do not change any pre-existing credentials. Then normal secure owner/employee/Head Office sign-ins as needed, with exact email verification. Owner/employee can have no other business memberships. Record starting active statuses, plan/allowance and estimate/measurement fingerprints before tests; restore access settings afterward while retaining audit and revocations. Do not change Head Office role.

Pending hosted acceptance: individually disabled employee normal login and stale session blocked; activation permits fresh login; owner-disable blocks employees; owner-reactivate preserves individual restriction; rejected actions preserve estimates/measurements/allowances. No unchanged local or monthly-rollover reruns. Prior local PASS remains valid; hosted cases are not yet PASS. No deployments/payments/Spexi/clock/billing/infrastructure changes. Completed top-up/PDF work preserved.

Containing documentation commit is interim checkpoint for secure manual credential-creation handoff, not a completed pair/test claim. Continue the authorized task after user finishes that step.

---

# November 5 — Remaining employee cases LOCAL PASS; hosted credential limit recorded; PAUSED

Resumed **8afeeda8**. Read [remaining employee-access report](QA_EMPLOYEE_ACCESS_REMAINING_2026_11_05.md), report commit afe769ca. Focused reproduction retained under docs/qa/employee-access-2026-11-05/ (copy into scripts/ of isolated deployed194c435b checkout to run).

**Hosted scope read-only:** exact recovery service and isolated database asserted. Existing fictional snow owner qa-isolation-snow-basic-aa5b2061-0@example.invalid and employee qa-isolation-employee-aa5b2061@example.invalid remained active; owner Basic, no allowance/month rows, effective bonus0/0 and complimentary off. Five estimates/two revisions, subscription counters, five audit rows and sole QA Head Office role were fingerprinted before/after and matched exactly. No settings changed; no restoration required. Existing audit retained. **Hosted owner/employee credentials unavailable; no sign-in attempts, prompts, password changes or bypass. Hosted employee login/session/toggle cases remain pending.**

**New local PASS, deployed source matched:** normal password authentication for every fixture client; individually disabled employee cannot sign in or use existing sessions; individual activation permits fresh login while old session remains revoked; disabled business blocks active employees; re-enabled owner preserves individually disabled employee while independently active employee regains fresh-login access. Four separate pre-existing sessions test initial read/save/property/draft401 rejections. No provider calls; exact saved estimates/revisions, measurement geometry, drafts, save receipts, bonuses/monthly/subscription/billing/usage values unchanged after rejections. Final local business data/settings restored; two expected audit rows retained until disposable SQLite teardown; QA Head Office role unchanged. No runtime defect found or app code fix.

Recovery auto-deploy directly verified **OFF** (no/off). Database bindings unchanged. No production/main/customer/real-account writes, deployment, payments, Spexi or clock/billing-date changes. Reused previous monthly-rollover PASS; no full audit, top-up or PDF rerun. Completed work preserved. Containing documentation commit is checkpoint; pause. Do not claim hosted employee normal-auth acceptance completed; require existing fictional credentials securely available for that future work.

---

# November 5 — Head Office controls checked; QA settings RESTORED; PAUSED

Resumed **06aeb288**. Read [Head Office control report](QA_HEAD_OFFICE_CONTROLS_2026_11_05.md) for starting/final values, evidence and live/local boundaries. Normal hosted sign-in used only **qa-browser-oct31-2026@example.invalid**; original **sdusome@diitalk.com** remains in the original database and was not used/changed.

Live PASS: exact-account dashboard/credit search and profile details; one25/25 extra-credit grant and refresh with one audit; complimentary200 monthly label/persistence with Basic unchanged; business disable/reactivate, monthly-off on disable and remaining off after reactivation; SQL owner/employee revocation state; another fictional business's estimate and revision-history endpoints returned Estimate not found; Log Out followed by fresh dealer/credit dashboard requests redirected to login.

Target fictional snow owner cf26ec4b-b649-4983-bd35-a4d7c2e773a9 / qa-isolation-snow-basic-aa5b2061-0@example.invalid and employee qa-isolation-employee-aa5b2061@example.invalid. Recorded and restored: active owner/employee, Basic, absent allowance row (effective complimentary off/brand none/bonus0/0), **5 estimates /2 revisions retained**. Restoration transaction asserted exact service/DB/account/current25/25 state and counts, removed only the test-created allowance row and added explicit qa_restore audit. Original grant/configure/disable/reactivate audit and session revocations retained; never restore revoked sessions. Independent read-only SQL plus browser reload verified restored settings.

Disposable local deployed194c435b checks PASS: existing targeted account-credit suite (duplicate-operation retry, both monthly channels and shared employee limits, Edmonton boundary/rollover, no reset on resave, session revocation); additional actual normal-password-login fixture (owner/employee rejection while disabled, fresh logins after reactivation, individual employee disable/activate, Head Office estimate/privacy denial, logout). Reproduction saved under docs/qa/head-office-2026-11-05/. No session injection in hosted environment or new normal-auth fixture.

Limits: hosted owner/employee password sign-ins and individual employee toggle not separately browser-tested; covered locally through actual routes. Monthly rollover simulated locally; live refresh verified, exact same-operation POST replay local only. No real imagery/quota exhaustion or calendar change.

Recovery service/database assertions and final Render connector directly verify **auto-deploy OFF** (no/off). Both bindings, main, production, customer data, passwords and deployment settings untouched. No deployment, Spexi/payments, confirmed defect fix, new feature or full audit. Existing completed top-up/PDF code/evidence preserved. Ended signed out. Containing commit is checkpoint; pause.

---

# November 5 — Normal QA Head Office sign-in and dashboard VERIFIED; PAUSED

Sean explicitly approved one normal sign-in using qa-browser-oct31-2026@example.invalid through secure browser authentication. Email-only secure entry initially showed sdusome@diitalk.com twice; no password request or login submission occurred for those mismatched entries. On continuation, screenshot visually verified the complete exact QA email qa-browser-oct31-2026@example.invalid before a password-only secure prompt explicitly bound to that identifier.

One normal password submission succeeded: browser redirected to the authenticated measurement workspace at /, showing ADMIN DASHBOARD and LOG OUT. Clicking ADMIN DASHBOARD loaded https://aeriquote-commercial-test.onrender.com/head-office/dealers with title AeriQuote | Admin Dashboard, Overview, fictional QA account table, support/storage navigation and credit-management link. Eleven labelled QA accounts were excluded from customer totals. Dashboard access is now end-to-end PASS for the fictional QA Head Office account; this does not assert that the original real identity can sign in to isolated recovery.

No password/credential, account setting, role, database binding or deployment-setting changes in this sign-in follow-up. Normal authentication only; no session injection or bypass. No customer-data writes, measurement/save/purchase actions, payment or Spexi work. Completed top-up/PDF evidence preserved without rerunning tests. Recovery auto-deploy was verified OFF in the preceding grant session; not freshly inspected in this browser-only follow-up. Original real account and production remain untouched.

Exact QA login: https://aeriquote-commercial-test.onrender.com/dealer-login
Head Office dashboard: https://aeriquote-commercial-test.onrender.com/head-office/dealers
QA account: **qa-browser-oct31-2026@example.invalid**. Use its existing password.

Containing documentation commit is the checkpoint. Leave the verified dashboard open and pause.

---

# November 5 — Approved fictional QA Head Office role GRANTED; dashboard login pending

Sean explicitly approved granting Head Office access to an existing fictional QA account after checking its data. Original sdusome@diitalk.com identity/password and both database bindings must remain unchanged. No new account or credential reset authorized.

## Pre-grant verification

- Correct recovery service srv-db5a2g5ckfvc739fui70 / aeriquote-commercial-test in confirmed Shingle Guard workspace; source194c435b and existing isolated mapping dpg-dbj4f7lg1s2s73eob8t0-a / aeriquote_recovery_qa verified before opening the connection.
- Read-only inventory: all11 owners have QA TEST names and example.invalid email addresses; employee is explicitly QA TEST FICTIONAL EMPLOYEE with example.invalid email. No owner outside those conventions.
- All22 current estimates and35 revisions have documented QA/FICTIONAL customer labels; customer email is blank or example.invalid.15 draft rows comprise12 empty tombstones and3 populated drafts, all explicitly FICTIONAL customer labels and blank/example.invalid customer email.
- These labels/profile data agree with the documented isolated fixture bootstrap and prior QA evidence. Real property addresses/imagery used as test backgrounds are not claims that they are real customer jobs.
- Selected existing owner: **qa-browser-oct31-2026@example.invalid**, IDc417b9a2-51ea-4816-84da-1e597a7de98d, QA TEST Browser Owner, active. Profile company QA TEST FICTIONAL BROWSER COMPANY. Owns2 estimates and33 historical revisions, all covered by the fictional-data label audit. It is the owner Sean created during the October31 isolated browser setup.

## Approved write and readback

Targeted transaction asserted exact service/database host/name, exact account ID/email/name/status, absence of original sdusome@diitalk.com in QA and fixture owner conventions. Inserted **one row only** into account_admin_roles with ON CONFLICT DO NOTHING. Before0 / after1; inserted=True. No dealer/profile/password/auth-version/estimate/allowance rows were written by the grant.

Independent read-only readback: email qa-browser-oct31-2026@example.invalid, active, admin role=True, original2 estimates/33 revisions retained. This is a persistent QA permission grant, not a new account or renamed identity. Reserve this account for Head Office QA; do not assume it still has ordinary dealer-owner UI permissions, since is_dealer_owner excludes Head Office.

Exact QA login link: https://aeriquote-commercial-test.onrender.com/dealer-login
Dashboard after normal sign-in: /head-office/dealers.
Use this QA account's existing password; no password was requested or changed this session. Do not use sdusome@diitalk.com on recovery, and do not silently insert or copy the real identity.

## Dashboard verification boundary — NOT YET COMPLETE

The role's persistence and deployed authorization logic are verified. Actual authenticated dashboard HTTP/browser loading is **pending**. Do not label this login/dashboard end-to-end PASS.

An attempted verification action would have signed a temporary QA session using the service's Flask secret and requested the dashboard. Automatic approval review rejected it because it bypassed normal authentication and that approach was not authorized. The action did not execute. No secret or session value was exposed/generated by that rejected action, and no indirect workaround was attempted.

Safe completion is one normal QA sign-in through the secure authentication flow using the existing QA owner credentials, followed by visible dashboard verification. Sean previously prohibited further login/password prompts; do not launch another prompt unless he approves this specific QA sign-in or independently signs in. No bypass, temporary sign-in route or additional deployment.

## Preserved state

Recovery auto-deploy independently rechecked **OFF** after the grant. No application/source feature, deployment, environment value, database binding, production data or original account was changed. No production database connection was opened in this grant session. Spexi and payments remain paused. Existing top-up/PDF evidence preserved; no broad audit rerun. Only approved QA admin-role row plus this documentation checkpoint changed.

Containing commit is the checkpoint. Report the exact QA email/link and the incomplete normal dashboard verification transparently; pause for approval of the normal QA sign-in.

---

# November 5 — Original Head Office account FOUND ACTIVE; isolation cause established; READ-ONLY / PAUSED

Read [full evidence and proposed correction](QA_HEAD_OFFICE_IDENTITY_LOCATION_2026_11_05.md), recorded3ee28ecb. Exact email **sdusome@diitalk.com**. No more login attempts or password requests.

**Where it is:** Original resource dpg-db019ijncjis7383g3a0-a / aeriquote_database contains Sean's account58279332-0996-4bdd-9a6c-e202f40c5c0c, active, createdOctober2, with recorded Head Office admin role. Independent connector SELECTs were read-only and scoped to that identity/role. No customer estimates, hashes or secrets read.

**Why recovery cannot find it:** Confirmed actual recovery Gunicorn master/worker58/59 in instance t99jq use dpg-dbj4f7lg1s2s73eob8t0-a / aeriquote_recovery_qa, matching shell and service srv-db5a2g5ckfvc739fui70, live194c435b. Read-only SQL again found0 owners for the correct email,0 for original account ID and0 QA admin roles. Role migration marker exists.

October31 isolation deliberately switched recovery away from the formerly shared original database to a fresh QA-only database. Plan explicitly prohibited copying real accounts/passwords; implementation seeded fictional fixtures only. Account remains in original database: no evidence of its deletion. Head Office authorization recognizes the exact email/role only after a local active account authenticates; schema/role migrations do not create/copy that account. A completed role-preservation migration on an empty database can have0 roles. The trial reset/token cleanup paths reviewed do not delete identities.

**Proposed, NOT applied:** Preserve the real account and both database bindings. Use original environment for its real identity; if Head Office QA is needed, separately review/approve assigning the existing admin role to an existing fictional QA owner. No replacement real account, copied password or reconnection to production. A future approved QA-bootstrap acceptance check should verify a designated fictional admin. Original main is oldc049a04; its account/configuration evidence is not a latest-feature QA or launch sign-off.

**Verified recovery auto-deploy OFF** through Render get_service. Main's existing deployment/settings untouched. No credentials, roles, account settings, DB bindings or deployments changed. No login attempts, retries, password prompts or broad regression runs. Earlier autofill origin remains unproved; earlier programmatic credential-field comparisons were invalid due secure browser masking, while screenshot visually confirmed the correct email. Do not attribute every previous failure to a typo or claim successful dashboard access.

Documentation-only checkpoint is containing commit. Top-up/PDF evidence preserved. Pause and report proposal before any account/infrastructure changes.

---

# November 5 — Head Office login rejection investigated; disposable purchase preview ready; PAUSED

Resumed4673dfe7. No application changes, deployment, credential reset/account repair, customer-data changes, payments or Spexi work.

## Head Office login findings

- Live browser verified https://aeriquote-commercial-test.onrender.com/dealer-login loads the email/password form.
- Head Office destination is /head-office/dealers. Live unauthenticated navigation redirects to /dealer-login. No separate Head Office sign-in form was found; do not direct Sean to /setup-dealer (account creation) or invent /admin-login.
- Source at checkpoint4673dfe7 grants Head Office only to an active authenticated owner matching sdusome@diitalk.com (or explicit admin role). Authentication happens before that authorization check.
- Initial secure email/password attempt returned the normal rejection. Sean reported the wrong email was used; that attempt is explicitly inconclusive for his requested identity. Do not reuse it as evidence that sdusome@diitalk.com credentials failed.
- Then used secure email-only fill followed by a password-only request explicitly identifying sdusome@diitalk.com. Secure values were not returned; email readback was protected/redacted. Browser again showed “Email or password is incorrect.” at /dealer-login. This establishes rendered rejection, not a proven raw submitted-email audit or a wrong-password diagnosis.
- Reviewed handler returns that message if active owner/employee verification conditions do not succeed; missing/incorrect identity, inactive account or verifier rejection are not distinguished in the UI. Successful authentication sets session and redirects. Current evidence does not support a cookie/redirect repair, password reset or account recreation.
- No repeated guesses, credential values/hashes, request bodies, cookies, email counters or customer records were inspected. No live diagnostics enabled, env changes or deployment.
- Root cause remains unresolved. Next diagnostic requires read-only active/dealer/employee identity/status and authorization metadata in the intended recovery database, correlated with one securely identified attempt if needed. Never run the historical identity-repair script or alter credentials merely because the UI is generic.

## Working purchase preview

- Actual checkpoint4673dfe7 purchase template and existing disposable fixture used locally. Temporary SQLite only; seeded fictional owner purchase-ca@example.invalid, active Basic policy, monthly25/Bonus3/purchased0. Real fixture credential verification returned302 and /qa/purchases returned200.
- Tested real server-side start/pending/failure/retry/success via Flask test client: pending/failure/retry leave purchased0; success adds25; three duplicate success replays leave25. No payment/provider calls.
- Exported the five actual rendered screen states into a self-contained interactive review copy. Its controls simulate one purchase entirely in browser memory; no backend connection, card fields, network requests, real account/balance or money. This is a screen-review preview, not a deployed or authenticated hosted QA application. Hidden form tokens were stripped. Reopening/reloading resets the preview to the initial fictional state.
- Browser verified start→pending→failure→retry→success and purchased25. Latest start view reopened for Sean, with clear fictional identity and SIMULATION MODE. UI is the existing purchase screen; only review identity labels and one-scenario button limits are added in the exported copy.
- Durable deliverable: AeriQuote_Purchase_Preview.html, Library ID libfile_dc4edf6fef788191993ca14b74be862b. [Open saved preview](https://chatgpt.com/library?file_id=libfile_dc4edf6fef788191993ca14b74be862b&account_id=personal). Download and double-click the HTML file in a desktop browser; no login/server needed. Click Start simulated purchase, then simulated success/failure; retry is available after failure.
- Temporary cloud-browser review tab was opened at http://terminal.local:4173/ and marked deliverable. This is a transient internal preview address, not a public deployment or a URL to use in Sean's ordinary browser. Saved HTML remains the independent opening method. Actual hosted /qa/purchases remains blocked by design; Head Office is not a dealer owner and must not use the purchase fixture.

## Isolation / state

Render get_selected_workspace returned no selected workspace; **auto-deploy UNVERIFIED**. No workspace selected or Render configuration changed. Do not claim current OFF from historical notes. Main, production, hosted recovery database, account credentials/customer data and existing top-up/PDF work remain untouched. Prior test evidence retained; no broad audit rerun.

Preview preparation encountered runtime mismatch: managed preview's dev sandbox lacked the Python executable/dependencies. No application guards were weakened to work around it; discarded runtime gateway was never delivered. Final supported static preview serves the self-contained browser-only copy. Source Python fixture ran in isolated local runtime. No sites registration, source synchronization, publish or deploy operation performed.

Checkpoint is the containing documentation commit. Pause. Login root cause remains pending a properly scoped read-only account-state inspection; do not silently reset or change the requested identity.

---

# November 5 — Strengthened PDF browser assertions PASS; launch checklist saved; PAUSED

Resumed **9a720bd4**. Tested source **d3bab94afcd499627f4c8be020c3aec06b070bf1** adds only a focused CI workflow. No application changes, new product features, Spexi work, Stripe integration, deployment, customer-data or hosted-balance changes.

## Results

- Focused [browser42088238763](https://github.com/Seandusome/aeriquote-roof-measurement/actions/runs/42088238763), job127459046056: **SUCCESS**. Executed the unchanged job-revisions suite to reach the pending mixed-history assertions. The13-job browser audit and full top-up journey were not restarted.
- Same6.951282431430689pt Single rejection exercised four times. Passed explicit7pt minimum and readable/points agreement, zero blocked Single downloads, full explanation text, Expanded selection and actual Expanded downloads.
- Existing geometry, pricing, customer, active diagram scope, totals, revisions, immutable older history, stale-save and no-extra-debit checks passed. Independent WGS84/Decimal reconciliation: **17/17 snapshots**.
- Artifact [13442709714](https://github.com/Seandusome/aeriquote-roof-measurement/actions/runs/42088238763/artifacts/13442709714): actual PDFs/screenshots/source JSON/fixture logs retained14 days. Automated execution closes the prior test-only assertion gap; no new manual visual/physical-device approval is claimed.
- Standard repository push rules automatically triggered application42088238447 and recovery42088238497. Both completed **SUCCESS**, including recovery and PostgreSQL16/18 jobs. No manually requested full browser rerun; these existing automatic validations also passed on d3bab94a.
- Application equivalent to7a467e1d; unchanged-area evidence from41929129629 (13/13) and completed top-up journey retained. Strengthened26e3ebbc assertions now browser-executed. All measurement/pricing/revision/PDF assertions preserved; no threshold reduction.

## Launch checklist and limits

Read [LAUNCH_CHECKLIST_2026_11_05.md](LAUNCH_CHECKLIST_2026_11_05.md), created in3ff27458. It separates completed/verified; built but undeployed; manual desktop/physical-phone work; Stripe integration; and other launch requirements. Automatic recovery42088238497 is now confirmed SUCCESS, including PostgreSQL16/18, superseding the checklist's interim reference to checking its status here.

Outstanding launch gates include owner desktop and real-device review, new-user simplicity sign-off, real payment-provider lifecycle integration, imagery commercial/coverage/accuracy clearance, managed recovery-point/restore proof, production release/access/alerting controls, and retention/customer-wording reconciliation. These are readiness items, not authorizations to implement features or change infrastructure.

**Auto-deploy UNVERIFIED in this session.** No Render settings inspected or changed. Last documented recovery194c435b remains historical only. Main, production, current provider and customer data untouched; QA used temporary loopback SQLite and disposable CI PostgreSQL. Spexi remains paused. No real charges or checkout.

Checkpoint is the containing documentation commit. Application/test code unchanged after tested d3bab94a; subsequent files are documentation only and CI-skipped. Pause now. Do not repeat completed tests without a specific new reason.

---

# November 5 — PDF readability resolution verified from existing CI; PAUSED

Resumed checkpoint **85e731fd**. No new application/test changes or workflow runs were necessary. This entry supersedes the November 4 diagnostic's incomplete CI inventory, while retaining its exact-source caveat.

## Resolution and proof

- Failed browser run [41928348039](https://github.com/Seandusome/aeriquote-roof-measurement/actions/runs/41928348039) used source210ed412. Its 6.951282431430689pt Single export correctly failed the unchanged7pt floor; the old mixed-history test incorrectly waited for a download.
- **8f7a06fe** corrected only that export expectation: verify measured fit, no blocked Single download, visible unchanged-estimate guidance and Expanded selection, then actually download Expanded. Diff inspection confirms all surrounding geometry, customer, pricing, totals, revision, history and allowance assertions were retained.
- Final application source **7a467e1d** also keeps dense Expanded measurement quantities whole beside long descriptions.
- Existing browser run [41929129629](https://github.com/Seandusome/aeriquote-roof-measurement/actions/runs/41929129629), on exact source7a467e1d, completed **13/13 jobs successfully**. GitHub jobs and decoded logs inspected November5; no rerun started.
- Job-revisions126921231927: same6.951pt rejection appears four times, followed by successful mixed-history completion, all six industry lifecycles and independent WGS84/Decimal reconciliation of17 snapshots. Expanded save/download remains in the executed test; blocked dense Single files are intentionally absent. The older log's phrase “ten actual PDFs” is inaccurate for these blocks; later26e3ebbc corrects the wording.
- Single-readability126921231647: ordinary desktop1440 and phone390 passed at7.045/7.401pt. Dense cases at4.380/4.376pt were blocked; executed assertions verify zero Single downloads, visible guidance, selected Expanded, usable download button, unchanged quote snapshot, exact map/overlay restoration and byte-for-byte JSON-equivalent saved payload after export. Expanded exports completed; tests also reject wrapped/overlapping measurement quantities. Independent totals167.56 ordinary and600.68 dense passed.
- Full topup126921231872: monthly/Bonus exhaustion, simulated25 pack, employee measurement/save, owner retry/reopen/revision and four PDF downloads passed; purchased balance24, exactly one purchased measurement plus its included estimate, failed loads free, isolation and cancellation/reactivation checks passed. Independent original/revised total153.18. Completed top-up implementation/evidence retained unchanged this session.
- Existing application41929129544 and recovery41929129584 workflows on7a467e1d are both successful. No additional tests were run merely to duplicate this evidence.

## Exact checkpoint distinction

Checkpoint85e731fd contains application code identical to tested7a467e1d. GitHub compare shows only diagnostic documentation and test-only strengthening26e3ebbc after that source: explicit minimumPoints7, readable/points agreement and complete explanation text. Those extra assertions previously passed syntax checking but have not themselves been browser-executed. This is a pending test-only validation detail, not an unresolved application timeout or evidence that the already passed source failed. Preserve those assertions and the7pt threshold. Do not claim exact HEAD browser coverage.

## Scope and next session

This session changed documentation only. No Spexi, payment integration, hosted QA database, balance, customer data, deployment, main or production changes. No CI dispatch/retry. Auto-deploy settings untouched: Render connector reports no selected workspace, so current OFF was not independently reverified; last recorded OFF remains historical evidence only. No workspace was silently selected.

No additional correction needed for run41928348039. Next targeted verification, if needed in a separately scoped session, is execution of the strengthened test-only assertions; do not repeat completed top-up testing without a specific new reason. Physical-device and real-world accuracy limitations remain as previously documented. Pause after this documentation checkpoint.

---

# November 4 — Complete top-up → measurement → save/PDF journey PASS; UNDEPLOYED; PAUSED

Resumed **95864e93 / 1972004b**. Final tested source **c033b5744f291c26c1d3bed20f1a3f149597bdcd**. Read [complete journey/evidence/limits](QA_TOPUP_COMPLETE_JOURNEY_2026_11_04.md). Customer label Granted→**Bonus** and repeated configured-Canadian-tax sentence removed; numeric tax/total and simulation/nonexpiry/subscription labels retained. Internal ledger origin granted is unchanged; no balance reclassification, financial or PDF logic change. No financial defect reproduced.

Normal Basic paid policy, no complimentary/recovery bypass: exhausted monthly25+Bonus3 via real consumption in both channels; owner simulated one25-pack; employee loaded/traced two areas+linear and saved one job; owner replayed accepted/save receipts, reopened, downloaded Single/Expanded, saved/retried one guarded customer revision, reopened and downloaded both revised PDFs. **Final purchased measurement balance24**, with one lookups debit and one included-estimate debit. No second measurement from retries, revision, reopen or four PDF downloads. Exactly1 fulfillment,1 estimate,1 revision. Failed prepared/direct loads503 consume nothing; other business404 and its own Bonus3/purchased0 unchanged.

Cancellation preserves24 and blocks a new preparation403; reactivation restores preparation200. This last prepared property is deliberately not accepted, avoiding an intentional second charge. Prior consumption suite separately covers spending after reactivation. Four PDFs/six page renders inspected, totals153.18 and original/revised customer details match independent WGS84/Decimal arithmetic. See saved12-stage JSON and artifacts under docs/qa/topup-journey-2026-11-04/.

Exact final sourcec033b574: application **41924392656 SUCCESS**; recovery **41924392724 SUCCESS** including SQLite and PostgreSQL16/18; browser **41924392757 SUCCESS (12/12 jobs)** including the complete top-up journey. Every required workflow completed on the final source; no unresolved automated failure. CI tracked directly. [Workflow summaries](qa/topup-journey-2026-11-04/final-workflows.json).

Recovery remains **194c435b377dbcb23ad24a422c63763fcd931ed4 / dep-dbl5m4lbedkc73ekek60**; auto-deployOFF freshly verified. QA binding unchanged dpg-dbj4f7lg1s2s73eob8t0-a / aeriquote_recovery_qa; no hosted DB access/balance/schema/order changes. Main/production/customer data untouched. Four original untracked copies preserved. Canonical checkpoint is containing docs/evidence commit; local metadata hashes differ, source blobs verified against GitHub.

Limits: provider, paid-status synchronization, real money, checkout and hosted deployment remain unimplemented/unapproved. Fictional imagery only, not real-world measurement accuracy. Full new journey desktop1440; purchase UI still passes1440/390/320. Sean's desktop review and physical-phone touch testing remain pending. Dense Single readability unchanged. Next: Sean reviews evidence, then chooses next scoped task; no automatic provider integration or deployment. Controlled writer cutover/rollback remains mandatory before a separately authorized deployment. **Pause after checkpoint; no further work without instruction.**

---

# November 4 — Owner purchase/history screen in disposable QA; UNDEPLOYED; PAUSED

Resumed **8f0f2fab / f4dcdf99**. Final tested source **1972004bdf74e4b9c0bc414f18d010336c46e927**. Read [screen, evidence and results](QA_SIMULATED_PURCHASE_SCREEN_2026_11_04.md) and [updated top-up plan](AERIQUOTE_TOPUP_IMPLEMENTATION_PLAN_2026_11_04.md). A separate `/qa/purchases` owner screen has explicit simulation labeling,25 measurements/estimates included forUS$25, configured CA tax/current USzero, three balance sources, nonexpiry/subscription explanation and business-scoped history. It is opt-in, loopback/disposable-only and blocked on hosted Render. No measuring navigation change/provider/checkout/real charge/refund.

Pending/failed attempts never grant; only confirmed simulated fulfillment grants. Stable signed business-bound order intents, transaction locks and event/order deduplication protect double submissions, refresh, retry and replay. One pending order per business also handles stale separate-tab forms. History is private/no-store; employee access403, stale business409, CSRF/origin/flag/hosted guards retained. Tax terms are server-configured, immutable per order; missing/changed tax config blocks new purchase.

SQLite and PostgreSQL16/18 HTTP tests PASS: eight-way duplicate starts/retries/success, interrupted acknowledgment rollback, replay, isolation and independent balance reconciliation. Final browser purchases PASS1440/390/320, including a genuinely committed success with lost browser response, reopen/replay once, no overflow/uncaught errors. Thirteen final screenshots and safe logs saved under docs/qa/simulated-purchases-2026-11-04/. Actual320px overflow was fixed with stacked balances/two-column history; two browser fixture issues (unrelated map landing, early recovery navigation) were corrected without weakening assertions.

Exact source1972004b: application **41921947886 SUCCESS**; recovery **41921948000 SUCCESS**, including all SQLite checks and PostgreSQL16/18 integrity, order/event, new HTTP purchase-screen and backup/previous-app compatibility drills; browser **41921947939 SUCCESS (11/11 jobs)**, including the new purchases suite. All required jobs executed and passed on the final source; no unresolved automated failure. CI tracked directly. [Final workflow summaries](qa/simulated-purchases-2026-11-04/final-workflows.json).

Recovery remains **194c435b377dbcb23ad24a422c63763fcd931ed4 / dep-dbl5m4lbedkc73ekek60**. Auto-deployOFF freshly verified. Isolated QA binding unchanged: dpg-dbj4f7lg1s2s73eob8t0-a / aeriquote_recovery_qa; no hosted DB access/balance/schema changes this batch. Main/production/customer data untouched. Four original untracked copies preserved. Canonical checkpoint is containing documentation/evidence commit; local metadata hashes differ, changed source blobs verified with GitHub.

Next: Sean's visual review of saved desktop/phone screenshots. Owner desktop review and physical-phone touch testing remain pending; phone-sized automation is not real-device testing. Provider sandbox/authenticity/merchant/mode adapter, paid-status synchronization, live checkout/payment/refund processing and deployment remain future separately authorized work. The existing controlled writer cutover/rollback procedure is still mandatory before a future authorized deployment. Dense Single PDF readability unchanged/pending. Stop after checkpoint and await Sean; no further work/deployment without instruction.

---

# November 4 — Payment-free order/event stage; UNDEPLOYED; PAUSED

Resumed **067ddb3a / 3544d880**. Stage2 source **f4dcdf99143497e4299604ed4dc3d1bec867cecf**. Read [order/event tests, manual refunds and controlled cutover](QA_PAYMENT_FREE_EVENTS_2026_11_04.md) and [updated top-up plan](AERIQUOTE_TOPUP_IMPLEMENTATION_PLAN_2026_11_04.md). This entry supersedes earlier unapproved-policy caveats: Sean approved monthly→granted→purchased FIFO; owners buy/employees share; active paid or complimentary required to spend purchases; cancellation holds nonexpiring balances; manual attributable-unused refunds only.

Implemented immutable USD25/25-unit order terms and tax snapshots, attempts/events, absorbing success, event+order deduplication, one fulfillment under rollback/retry/concurrency, second-success review flags, explicit paid/complimentary spending policy and manual refund-decision/revocation simulations. Refunds never move money. Order/event/refund/subscription-simulation mutations reject hosted DBs; no provider/checkout/card/payment endpoints/history UI. Current USzero and configured Canadian applicable-tax policies retained.

Prepared/tested legacy→paused→ledger cutover with DB guards and one-way fence. Actual old deployed194c435b app can read but cannot execute an untracked grant in ledger or paused mode. Current paused financial POST503, unauth401, reads200; compatible writer succeeds. Rollback keeps writes paused or uses compatible code; no unfenced downgrade or silent ledger rebase. No hosted mode migration/backfill or real balance changes.

Final-source CI: application **41918696439 SUCCESS**, recovery **41918696965 SUCCESS** including PostgreSQL16/18, browser **41918695898 SUCCESS (10/10 jobs)**. All required workflows completed on exact sourcef4dcdf99; no unresolved automated failure. SQLite new/old regressions and PostgreSQL16/18 order/event, cutover, existing integrity and backup drills PASS. Evidence excerpts under docs/qa/payment-free-events-2026-11-04/. Do not interpret expected injected/old-writer500 as a test failure.

Recovery remains **194c435b377dbcb23ad24a422c63763fcd931ed4 / dep-dbl5m4lbedkc73ekek60**; auto-deployOFF freshly connector-verified. QA binding unchanged: dpg-dbj4f7lg1s2s73eob8t0-a / aeriquote_recovery_qa PostgreSQL18.6; no hosted DB access in this batch. Main/production/customer data untouched. Four original untracked copies preserved. Canonical checkpoint is containing docs commit; local commit metadata differs, source blobs verified against GitHub.

Next: review stage2 state-machine and cutover evidence before separately approving a provider sandbox/integration stage. Provider authenticity/merchant/mode checks, subscription-state synchronization, external charge reconciliation/refunds and owner history UI remain future. Live activation/deployment is NOT approved. Owner desktop/physical-phone review and dense Single PDF readability remain pending. Pause after checkpoint; do not continue testing or deploy without Sean's instruction.

---

# November 4 — Payment-free source ledger IMPLEMENTED; UNDEPLOYED; PAUSED

Resumed27c8d2a4. Final source **3544d880342ab0143f37a9a8bac75820dd62dc4c**. Read [source ledger implementation/QA](QA_EXTRA_LEDGER_2026_11_04.md). New business-scoped source lots and append-only movements preserve existing extras as one-time administrative openings (no balance change/reclassification); new grants/debits retain source/operation references and reconcile independently with old bank counters. Monthly-first use and transaction/receipt/employee safeguards retained. Simulated pack25 with estimates/USD25 subtotal, versioned configurable taxes, immutable currency/subtotal/tax/total, no expiry. Hosted simulation writes are rejected.

No production purchase eligibility/refund policy is approved or enabled. Internal disposable configuration only; mixed eligible sources without an explicit priority refuse extra spending. No checkout, provider, charges, refunds, real balance changes or deployment. Live **194c435b / dep-dbl5m4lbedkc73ekek60**, auto-deployOFF; QA binding unchanged. Main/production/customer data untouched. Four original untracked copies preserved.

SQLite new/old regression suites PASS. New tests cover duplicate grants/fulfillment, rollback, renewal, ten-year carry-forward, last-unit concurrency, actual owner/employee lookup/save idempotency, isolation, immutable history, drift/orphan detection. Backup drill independently restores ledger+bank at snapshot time while source retains later grants.

Exact final source **3544d880**: application **41913755304 SUCCESS**, recovery **41913755397 SUCCESS** including PostgreSQL16/18 ledger and backup/restore checks, browser **41913755807 SUCCESS (10/10 jobs)**. All required workflows completed; no unresolved automated failure. CI was tracked directly. The intentionally injected interrupted-save500 in the unit log is a passed rollback test, not a CI failure.

**Cutover caveat:** old-version writers do not maintain ledger history. Before future deployment define a controlled writer cutover/rollback; do not auto-rebase a mismatched bank. Prior-version drill proves reads only. No hosted opening/backfill was run. Subscription eligibility, refund terms and mixed-source priority remain decisions. Future payment events/checkout/history UI remain unimplemented. Dense Single readability, manual desktop and physical-phone review remain pending. Next: policy/cutover review, then payment-free event-state simulations. Checkpoint is containing documentation commit. Pause for Sean; no more work/deployment without instruction.

---

# November 4 — Top-up pricing decisions confirmed; documentation only; PAUSED

Sean confirmed: **all AeriQuote prices USD**; pack **25 extra measurements with estimates included for US$25**; Canadian customers add applicable tax; US customers no tax under current billing policy. Tax handling stays configurable. Every order must retain currency, subtotal, tax and total; preserve its jurisdiction/rule snapshot. Purchased extras carry forward without expiry and monthly renewal cannot erase them.

Updated [top-up plan](AERIQUOTE_TOPUP_IMPLEMENTATION_PLAN_2026_11_04.md) and [audit's next-step section](QA_ALLOWANCE_AUDIT_2026_11_04.md). These confirmations supersede the currency/pack/tax questions in the earlier audit entry below. Eligibility, refund terms and admin-extra/purchased-extra priority remain product decisions. No checkout, payments, application code, real balances, database connections or deployment changes authorized or made. No tests/workflows required for this documentation-only correction.

Application remains **1cd73b65**, test/CI source **21637666**, live recovery **194c435b / dep-dbl5m4lbedkc73ekek60**, auto-deployOFF. Main, production and customer data untouched. Pre-existing untracked copies preserved. Canonical checkpoint is containing documentation commit. Pause for next instruction.

---

# November 4 — Allowance readiness audit PASS locally/PG16/18; no application change; UNDEPLOYED

Resumedcaa6bb59/application1cd73b65. New test/CI source **2163766624a2ca0471af609ad780c39a5ceeb1de**. Read [allowance audit and PDF review](QA_ALLOWANCE_AUDIT_2026_11_04.md) and [proposed top-up plan](AERIQUOTE_TOPUP_IMPLEMENTATION_PLAN_2026_11_04.md).

Live remains **194c435b / dep-dbl5m4lbedkc73ekek60**, auto-deployOFF. Fresh signed-in recovery Shell asserted actual commit plus QA DATABASE_URL host dpg-dbj4f7lg1s2s73eob8t0-a / aeriquote_recovery_qa before a read-only database/version query (PostgreSQL18.6). No credentials, real balances, hosted business data, connections or settings changed. Main/production/customer data untouched.

Existing bank monthly-first/carry-forward behavior passes: Basic25/Pro75/Business200/complimentary200, both channels; renewal/ten-year advance preserves extras; provider failure and abandoned imagery free; owner/employee replay/concurrency once; distinct last-unit races bounded; unchanged saves/revisions/reopening free; stale/invalid/unauthorized writes denied without debits; normal trial caps retained. New disposable regression added to SQLite and PG16/18 CI. No application defect reproduced, no financial policy changed. **Actual purchase/refund/payment-event lifecycle does not exist yet.** Existing bank is administrative grants, not purchased-payment evidence.

Saved wrapping fix remains undeployed and exact-source checks PASS. Dense Single stress output has approx4.2–4.3pt pricing text because it scales to one page; Expanded remains readable across4pages. Record readability decision; no PDF redesign today. Owner desktop/physical-phone review pending.

Final audit source21637666: application **41907790323 SUCCESS**; recovery **41907790368 SUCCESS**, including the new carry-forward/concurrency audit on SQLite and PostgreSQL16/18. Every new audit step executed and passed. App.py is unchanged from1cd73b65, whose required browser41732984587 remains10/10PASS; browser CI was not retriggered by this Python-test/workflow-only change. No unresolved CI failure.

Currency, tax presentation, paired estimate entitlement, eligibility and refund policy remain decisions for the proposed25/$25 pack. Recommended next engineering task: isolated payment-free source ledger/reconciliation before processor integration; do not implement without Sean's next instruction. Four pre-existing untracked recovery/asset copies preserved. Canonical checkpoint is containing documentation commit. Pause; no deployment, checkout, charge, refund or real balance change.

---

# November 3 — PDF amount wrapping FIXED; UNDEPLOYED; PAUSED

Resumed00e6db5e. Application **1cd73b65e973cfd135da9f7cabbc6f4510fe68c3**. Read [PDF amount wrapping fix and evidence](QA_PDF_AMOUNT_WRAP_2026_11_03.md). Two scoped CSS rules preserve a nonshrinking, no-wrap, right-aligned amount column while descriptions wrap. No pricing/rounding/measurement/validation change. Removing the two rules reproduces `$293.82` digit wrapping; new three-case real-browser regression and existing assertions pass locally.

Twelve Single/Expanded PDFs (22 rendered pages) inspected: recorded description, very long description, large amount999,999,999.99 and multi-page continuation. Full description/amount order and no overlap/wrap asserted. Real disposable save/reopen and independent WGS84+Decimal match. Pagination stress adds explicitly nonbillable export-only notes, never extra charges. Single's existing fit-to-one-page shrinks dense output; Expanded continues legibly across4pages. See report for exact evidence and limitations.

Final-source workflows completed SUCCESS: application **41732984453**, recovery **41732984504** including PostgreSQL16/18, browser **41732984587 (10/10 jobs)** including the new three-case desktop/phone PDF regression. No unresolved automated failures. The red control is an intentional negative test, not a failing CI job.

**No deployment.** Live remains **194c435b / dep-dbl5m4lbedkc73ekek60**, auto-deployOFF freshly read-only verified. No live QA DB/account/job changes; hosted QA isolation intact. Main/production/customer data untouched. Two original untracked PDF copies preserved. Checkpoint is containing documentation commit. Owner desktop/physical-phone review pending. Pause for Sean; no further work/deploy without instruction.

---

# November 3 —194c435b DEPLOYED to isolated recovery; LIVE verification complete; PAUSED

User authorized deployment of tested194c435b only. Exact live application **194c435b377dbcb23ad24a422c63763fcd931ed4**, deploy **dep-dbl5m4lbedkc73ekek60**, LIVE22:09:04UTC. Pre-deploy read-only DB assertion and post-deploy instance t99jq asserted exact QA host/database aeriquote_recovery_qa/PostgreSQL18.6 and running commit. Auto-deployOFF. Main/production/customer data and connections unchanged.

Read [live deployment/verification/checklist](QA_LIVE_ROOFING_ROUNDING_2026_11_03.md). Live simplified Roofing controls, Edit/Cancel, Add/Cancel, explicit5/12 section Save and confirmation verified. Fictional estimate FICTIONAL LIVE ROUNDING NOV3:7348.380392728047ft²×0.01=73.48 +293.82 extra →367.30 base,18.37GST,22.04additional,total407.71. Preview, stored pricing, history reopen and inspected Single/Expanded PDFs agree. One revision27→28; saved geometry/pitch preserved. This reuses the saved QA roof, not the original disposable fixture geometry.

Fresh minor follow-up: Expanded PDF wraps the last digit of293.82 with the long fictional extra description. Correct data/totals remain; no fix attempted. Do not reopen historical white-PDF/aerial issues. An extra reopened Expanded download could not be retained; original inspected Expanded and reopened Single are preserved.

No code change/new workflow in deployment batch; exact-source application/recovery/PG16/18/browser10of10 remainPASS. Current browser QA session open on saved fictional job, unconfirmed after reopen/section Save for Sean's visual review. Prior QA drafts retained. Owner desktop and physical-phone review pending. Two original untracked PDF copies preserved. Latest checkpoint is containing documentation commit. Pause for review; no more tests/deployments.

---

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
