# Recovery/session/account binding batch — October 27, 2026

## Base and boundaries

Started from verified GitHub3b0d1a15e1007b8ab24c02e4596fb4c57e311912, treec23112c1d0997d0a768ec91f1d7fcb21446ed255; Renderdep-dbggjivb9u1s73aj2ap0 LIVE. Work only on recovery branch. No imagery/provider/Solar, measurement arithmetic, PDF design/vector flags, billing policy, schema migration, Stripe or CRM changes. Real customer/production accounts and main untouched. AI Trace remains absent.

## Confirmed defects and narrowly scoped fix

1. The workspace called prepareAccountBrandingCache using aqAccountId, but that meta element existed only in the login HTML. The actual workspace did not render its business ID. Account separation of cached profile/logo could therefore be skipped, especially before/without successful profile hydration. Add the already-supplied server ACCOUNT_ID to the workspace meta. An actual isolated Flask render asserts it; a real Chromium newly opened second-business page with failed profile fetch confirms previous-business company defaults are cleared.
2. Original pageA can survive logout/session expiration. Signing into businessB in another tab changes the shared cookie; an old draft's POST previously saved intoB and could consumeB's allowance. Reproduced against real disposable Flask/SQLite routes: mismatched expected business header returned200 and created an estimate before the repair. Old branding POST could similarly overwriteB.

Risk explained before implementation: modern workspace estimate/profile writes now carry the business ID rendered in their original page, and authentication rejects a mismatch with409 before any write/credit transaction. Original draft/entries stay in memory; reauthenticate to original business then retry. Valid same-business retry remains idempotent. This is save validation, not autosave, record migration, a new allowance policy or a replacement for authorization. A forged header does not grant access; authenticated session ownership remains authoritative. Legacy clients omitting the optional header retain existing behaviour. **Already-loaded older code lacks the new header: do not pretend a deployment upgrades its JavaScript, and never refresh an unsaved job simply to obtain the fix.**

A profile mismatch shows the server's business-mismatch message instead of a generic connection explanation. No existing saved record is rewritten by deployment. Tests verify no estimate/profile/usage changes for either business on rejection; same-account save plus repeats use one estimate/credit; expired auth remains401. Existing employee/owner authorization is unchanged.

## Actual local Chromium recovery evidence

Isolated fixture server only,390px viewport/mouse, two saved rectangles and a line with customer data:

- Attempt refresh; cancel native beforeunload; exact draft snapshot remains.
- Attempt website navigation; cancel warning; customer and measurements remain.
- Expire shared cookie via real logout; estimate creation returns login-expired status, opens no customer report and keeps draft.
- Log into other disposable business; actual old-page save displays another-business error, creates no foreign estimate and retains draft.
- Re-login to original business; create/save/reopen/download succeeds with matching customer/total.
- Newly opened other-business workspace with blocked profile fetch does not show the previous business cache.
- A separate disposable unsaved tab asks on ordinary close; cancel keeps it open. A forced Chromium target close bypasses warning. A fresh page has no discarded geometry; only the explicit saved estimate exists. This simulates forced discard, not an operating-system crash or physical-device test.

Harness detail: after cancelling Playwright close(runBeforeUnload:true), reusing Page.close can wait on Playwright's close bookkeeping. Use explicit Chromium Target.closeTarget for the forced-close test. This tool behaviour is not an AeriQuote failure. Initial customer-reset timers are allowed to finish before supplying the deliberately injected second-tab fixture. The main measured job uses actual pointer drawing, not injected geometry.

## Unsaved recovery / autosave analysis — no autosave introduced

Current safe paths: cancel navigation, keep original page open after a failed save, sign into the SAME business elsewhere and retry, or reopen an explicitly saved server estimate. Property-session recovery preserves imagery/session metadata, not unsaved browser geometry. Confirmed forced discard loses an unsaved draft. No claim of crash recovery.

A future draft design needs approval after this analysis:

- Distinguish a draft from an estimate/revision; never spend measurement/estimate allowance merely for storing a draft.
- Stable per-business/per-tab operation identity and idempotent writes must prevent duplicate revisions/debits after lost responses.
- Version/If-Match conflict checks must prevent a stale draft overwriting a newer saved estimate; restoring should be explicit and show which property/date/version will be restored.
- Bind storage and recovery to authenticated business and employee permissions, including cookie/account changes. Never hydrate another business's customer data from shared browser storage.
- Browser-only sessionStorage survives some reloads but not reliable discard/closure; persistent local storage contains customer data, can be blocked/cleared and requires retention/privacy decisions. Server drafts require access rules, bounded storage/TTL, cleanup and separate credit semantics.
- beforeunload is not guaranteed on crashes/mobile termination. Recovery cannot rely on a final unload write. Network retries, expiry and simultaneous tabs need race tests.

No draft database/localStorage/IndexedDB autosave, backup control or recovery prompt was added. The current branch warning is protection against accidental navigation, not data persistence.

## Verification and current limitations

-68/68 full local recovery workflow commands passed after repairs. Added test_workspace_account_binding.py to the recovery CI job. Existing test_account_access stub now supplies request.headers as a real request does; authorization assertions remain intact.
- New real local browser recovery script passes. Independent WGS84/Decimal checks pass six saved industry snapshots. Another real local Chromium matrix completes six industries, standard login, property/drawing/pricing/customer/save/fresh-page/reopen and12 actual Single/Expanded downloads. Local provider imagery is synthetic and labelled; not live provider ground truth. Roofing uses existing QA manual mode only in local fixtures.
- Existing employee permissions, business isolation, shared25/75/200 allowances, password reset mock delivery, disable/reactivate and stale-session revocation tests pass in the full suite. Existing actual PostgreSQL CI covers concurrency; verify the new checkpoint's terminal results after publishing.
- Physical touch/drag/pinch/rotation/native print unavailable. Local Chromium uses viewport/mouse, not physical devices.
- Live browser: secure login initially rejected credentials. User subsequently signed in; workspace showed Head Office, so no estimates were created there. User selected switching to the existing sean@shinglextra.com QA account. Live provider verification is pending isolated QA authentication at this checkpoint; append actual evidence if it becomes available, never infer it from synthetic runs.
- Existing signup/onboarding tests cover all six real isolated route/profile flows; no claim of an observed untrained contractor or complete live fresh-signup session. Five-step UI preserved. No speculative wording/control additions.
- Branch protection remains off; licensing remains unresolved. Normal API callers without a workspace header and already-open old scripts do not acquire the new accidental-switch guard automatically.

Use scripts/test_browser_recovery.cjs against scripts/prelaunch_browser_server.py only on loopback. The two fictional accounts/passwords are disposable test fixtures, never real logins. Current checkpoint's final CI/deploy and any later live QA evidence belong in the final handoff/resume. Stop before testing a non-QA account.
