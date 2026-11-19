# Public website package/fallback QA — November 19, 2026

Parent:ac330227729fcb86ae021c4881d76cb1e471d401. Prior public checkpoint/checklist read first. Isolated worktree/branch; existing checkouts, preview work, databases and fixes preserved. Stripe remains PAUSED until Sean approves after site readiness. Enforcement OFF. No paid setup/integration, hosted or application-data changes.

## Small change and behavior

Removed the obsolete939447-byte `EMBEDDED_SITE` dictionary (pricing, trial/signup, roofing setup, CSS/JS/logo snapshots) and its now-unused base64 import. It could previously serve old50/150/300 plan allowances when site files were missing. Replaced it with one small self-contained HTML503 response: approved BasicUSD29/25,ProUSD59/75,BusinessUSD99/200 with separate lookup/new-estimate units, draft/purchasing-unavailable notice, paused Stripe status, operator and approved email-only contact. It explicitly says full website/policies are unavailable and it is not a checkout or substitute for the complete policies. No card controls, signup fallback, automatic-measurement promise or payment action. Cache-Control:no-store. No invented expiry/renewal/legal/license or delivery promise.

`site/public-package.json` declares71 current HTML/CSS/JS/image/icon files and SHA256 values. Historical README text files are not required web resources. Before serving HTML, `_public_site_package_ready(filename)` checks the manifest is valid, all listed files exist, and the requested HTML hash matches. Missing/corrupt requested HTML or an incomplete package yields503, including home/policies/onboarding; no stale embedded resource is used. Missing non-HTML resources return404. Normal complete disk-backed pages/assets and canonical redirects retain their original content/behavior. The estimator's `/site` CSS/JS assets still serve normally when present; no estimating or pricing interface changed.

`python3 scripts/check_public_site_package.py` is the mandatory local/pre-package integrity check: all71 hashes, not just requested HTML. It exits nonzero for missing/changed/invalid files. This is not a newly configured deployment pipeline. Non-HTML asset contents are not rehashed on every live request; preflight checks all of them. When deliberately updating public files, regenerate the reviewed manifest from verified source as part of that source change; never blindly regenerate it during deployment to bless a mixed/stale package. Ship the complete site directory plus manifest. No deployment performed.

## Fresh verification

Seven focused tests PASS on final implementation:
1. Complete package:71 files hash-match;27 canonical disk-backed public HTML pages return200 with exact disk bytes; public login redirects to app login; HTML alias/index redirects and all packaged assets checked.
2. Missing pricing/checkout/home package:503 contains approved rates/units and paused/no-purchase notice, no payment fields.
3. Missing stylesheet/logo:HTML fails closed503, direct missing assets404; old embedded CSS/image never returned.
4. Missing terms/signup/roofing setup:503 rather than unsupported fallback promises.
5. Missing manifest or entire site:503 HTML/404 assets, no obsolete fallback.
6. Changed pricing file:preflight fails AND runtime requested page503; no stale disk content served.
7. Old embedded payload/alias entirely absent.

Tests construct separate copies omitting files, never remove existing source/work/data. An initial test-harness assertion incorrectly expected index.html200 instead of its existing308; corrected, response streams closed, then all focused tests passed. Earlier noisy test log retained. No application behavior fix resulted from that harness correction.

Additional public route/link harness PASS across19 pages:all local navigation, policy anchors/footer links and assets resolve; no failures. Actual extracted application public file routes and public-login guard are used in Flask, with no database/app startup or form submissions. This is NOT a full estimating-app or hosted-session/browser check. No completed payment/industry/PDF suite repeated.

AST comparison:102 other existing top-level functions/classes and existing app constants (except removed embedded dictionary) unchanged. Existing estimating markup, job pricing, account/credit/draft/address and payment-QA module hashes preserved. Website HTML/CSS/JS/policy files are byte-identical to parent; only manifest added. No approved policy choice reopened.

## Browser limit — NOT a visual pass

Available browser-surface inventory showed no existing Codespace tab. Exactly ONE local Playwright Chromium startup attempted this round; it failed before any page loaded with TargetClosedError/SIGABRT. Exact cause reported by Chromium: `FATAL:chrome/browser/process_singleton_posix.cc:297 ... socket() failed: Operation not permitted (1)`. Crashpad additionally reported ptrace Operation not permitted. Full startup log preserved. No repeated launch attempts, access/security changes, Render fallback or public preview.

Desktop1280px and narrow375/320px visual layout/readability, pricing/contact/policy rendering, keyboard/mobile navigation interaction remain BLOCKED/UNVERIFIED. Static viewport/CSS evidence and GET navigation do not count as these visual checks. No screenshot/synthetic substitute or phone-emulation claim. Next visual check must use a working authorized isolated browser/Codespace environment with the complete package.

## Remaining launch gaps / next task

- Working-browser public desktop/375/320 verification first; Chrome physical-phone Create Customer Estimate/pricing/recovery/save/reopen/PDF still pending. Earlier phone touch passes remain historical; lost geometry unrecovered.
- Independent field/pitch validation; manual tracing/user-confirmed pitch is not survey accuracy.
- Approved support@aeriquote.com delivery and actual request-handling procedures/accountable privacy role unverified; no emails sent.
- Actual retention/backup lifetimes, restore safeguards, required-record exceptions and legal/privacy review; no deletion implementation or backup-erasure promise.
- Google billing case#77793344 unresolved; no confirmed extension/protection or exact trial/billing access/paid-status resolution. Imagery licensing remains open separately.
- Paid launch/tax/billing lifecycle remains deferred. Stripe account/credentials/connection/activation paused until Sean approves after rest-of-site readiness; default-OFF enforcement unchanged. Completed Render database backup/restore not repeated or upgraded.

Full source bundle must be verified and fresh-cloned, with uncommitted files and evidence separately preserved before any cleanup. No source/checkouts/databases or preview work removed. No push, deployment, hosted-setting/credential changes, payments, email or deletion. Stop this focused round.
