# AeriQuote end-of-day checkpoint — October 14, 2026, 5:38 PM Edmonton

## Resume here
Repository: Seandusome/aeriquote-roof-measurement.
Authorized branch ONLY: landscaping-multi-area-recovery-oct11.
Test service: https://aeriquote-commercial-test.onrender.com/
Latest application baseline: b16b31cdd0b40de143d829aa214d899bf8b07dad.
Sean confirmed deployed password-reset flow and new-password login both worked live this evening.
Do not restart development, roll back the app, restore AI Trace, modify main, or repeat already-passed measurement/PDF tests without new evidence.
Read this checkpoint first, then docs/CHECKPOINT_2026_10_13.md for previous verified measurement work, and docs/ACCOUNT_RECOVERY_SETUP.md for recovery configuration.

## Today's recovered and completed work
- Recovered October 13 verified automatic/manual Roofing, multi-area/linear, pricing, imagery and fresh/reopened PDF progress from GitHub. Preserved all of it.
- Existing October 14 activation dashboard: Today/week/month signups and first measurements, cohort conversion, Edmonton timezone, Monday week start; employee measurements attribute to owning business. Revenue correctly remains Not connected. No retroactive activation timestamps invented.
- 7e3bb0b renamed navigation Admin Dashboard. 55f0b53 moved activation recording ahead of Area/Linear early returns. 3367174 added read-only employee login lookup.
- Deployment disruption was Render's all-region build/deploy incident, including free-instance pause. Official incident resolved Oct14 22:18UTC (4:18PM Edmonton). No application rollback or code patch was used to address provider incident.
- ff7ed6188d7ff48997c7848d8fbecf3ef8a4a527: backend new-account allowances Basic25/Pro75/Business200, trial3, legacy unchanged; pricing FAQ and all remaining site allowance wording aligned. Homepage, FAQ, checkout, choose-plan and upgrade corrected (including stale Pro125). Prices remain USD29/59/99 and unit costs1.16/.79/.50. Upgrade intro no longer incorrectly declares trial exhaustion for every visitor. Existing account quota rows were not migrated.
- Employee profile POST now denied; employees retain GET access needed by measurement setup. Authenticated requests revalidate owning business status and employee membership/status. Disabling rejects an already-open session on next request; reactivation requires signing in again.
- b16b31cdd0b40de143d829aa214d899bf8b07dad: website login placeholder replaced with working same-service login/recovery links. Existing application login now has Forgot password.
- New account_recovery.py: owner and employee password recovery, random token links expire30min, only token hashes stored, atomic single-use consumption, token bound to existing password/login email, other issued links invalidated after reset. Password reset revokes existing sessions through persisted account_auth_versions. Disabled account/business status remains blocked.
- Existing admin password change increments owner auth version too. Login requests and reset requests have persisted fixed-window limits. CSRF checks on recovery forms; no-store and no-referrer recovery responses; generic unknown-email response.
- Resend HTTPS email API integration avoids free Render SMTP restrictions. Recovery explains unavailable when configuration missing rather than exposing a reset token.
- No CRM added. No Stripe/payment handling activated.

## Live confirmations from Sean
1. ff7ed61 deployed on test service. Website prices and allowances good.
2. Head Office login works through /dealer-login; Admin Dashboard accessible.
3. Employee Login Lookup works:
   employee name sam smoith; login employee-test@example.com; Disabled;
   owning business steve; owner login yntes@gmail.com.
   Sean did not remember that business owner's password. Do not keep asking him to sign in using a forgotten password.
4. Credit/refund panels remain Coming Later; no money moved.
5. b16b31c recovery page is live.
6. Resend domain aeriquote.com verified through GoDaddy DNS:
   TXT resend._domainkey plus CNAME rsend and send, using exact provider values supplied by Sean.
   Do not replace unrelated DNS records or recreate domain setup.
7. Sean created a Sending-access Resend key (UI only offered All domains) and entered all3 variables into commercial test Render Environment, saved and deployed:
   RESEND_API_KEY [secret stored in Render; never reproduce];
   PASSWORD_RESET_FROM = AeriQuote <accounts@aeriquote.com>;
   AERIQUOTE_PUBLIC_URL = https://aeriquote-commercial-test.onrender.com.
8. Head Office reset email reached sdusome@diitalk.com. Sean used the emailed link, changed password privately, and confirmed everything worked, including new-password login.
   No password/API key/reset token is recorded in this checkpoint. Do not request them in chat.

## Verification
Both GitHub workflows passed at ff7ed61 and b16b31c.
Local actual Flask-route tests with isolated SQLite/mocked sender cover login and site routing, owner/employee reset, unknown-email generic response, CSRF, expiry/single use, confirmation/minimum length, old-session rejection, disabled employee after reset, request limits and missing/insecure email configuration.
Existing DOM+Leaflet measurement/imagery/pricing/PDF suite, rendering/inline-JavaScript syntax and account access checks passed.
Live email receipt + new-password login are confirmed; this does not establish all production configuration or employee reset live coverage.

## Morning priorities
1. Resume from this baseline and confirm actual branch/deployed commit; no repeat signup/measurement tests solely to recover context.
2. Finish live business-owner password recovery and employee activate/login/disable-open-session/reactivate checks with an inbox Sean controls. employee-test@example.com is a placeholder and cannot receive a real email; do not expect delivery there. Head Office has read-only lookup, not business owner employee management.
3. Connect real support intake, including support-assisted forgotten-email recovery with ownership verification; current Contact Support form still does nothing. Avoid automatic email disclosure.
4. Verify persistent PostgreSQL DATABASE_URL, stable FLASK_SECRET_KEY, backup/restore and monitoring on actual deployment before claiming launch readiness. Remote environment inaccessible to agent; no live DB persistence verified this session.
5. Paid allowances still lifetime counters; monthly renewal/usage period and feature entitlement enforcement not established. Plan defaults corrected, existing paid account row migration still needs deliberate design. Payments remain deferred.
6. Email verification and trusted-proxy/rate-limit behavior review remain launch tasks. Current limits count successful login attempts too; counters use request.remote_addr and fixed windows.
7. Continue signup/onboarding/navigation and overall launch-gap audit without adding a CRM. Preserve approved logos, website style and feature differences.
8. No production/main merge or launch approval.

## Workspace and publishing
Local repo: /workspace/scratch/423ffc3aefb0/aeriquote-roof-measurement.
Its Git index is stale relative to remote; never commit all local modifications. Existing site/assets/commercial-approved.png modification is unrelated and must remain untouched.
Publish focused files via GitHub blobs/tree based on current remote tree, create_commit and update_ref expected_sha on authorized branch.
Node deps: /workspace/scratch/423ffc3aefb0/test-deps/node_modules.
Flask/Jinja local test deps: /workspace/scratch/8900f653a175/test-deps (PYTHONPATH).
Uploaded screenshot813711975.jpg used only to guide domain-field entry; approved logos not modified.
No remaining unpublished application edits from today's pushed features; local old checkpoint copy is stale—use remote checkpoint.
