# Pre-user QA pass — October 20, 2026

Sean authorized a final broad check before live users: signup, setup, six industry measurement/pricing, save/reopen, actual PDFs, mobile and permissions. Recovery branch only; main, real dealer accounts, credit grants and complimentary settings remain untouched. Payments remain outside this pass.

## Current verification

- Ran all 40 Python/Node script invocations from the recovery CI workflow. All 40 passed. Includes signup/onboarding and real isolated Flask setup flows; six-industry controls/measurement edges/saved editing/pricing; actual route isolation/permissions/credits; property-session recovery; support/recovery; public UI accessibility; phone PDF capture; shields and geometry/export regression. Local log: /workspace/scratch/93dfcfceb87a/prelaunch-regressions.json.
- Isolated tests use synthetic/temp local data, not live dealer mutations. No actual live email messages were sent by these checks.
- Local application blob 1dc71ad20112ed92ae0543ffa1f7df930e9ac27c exactly matches recovery branch app.py confirmed through GitHub. Local checkout remains preserved; automatic review rejected git switch -C because it could discard ahead local commits. No branch reset was retried or bypassed. Existing application fixes remain intact. Remote recovery app d62cb19 and later docs-only checkpoint 7a3e3c7 are the prior session's published state.
- Browser started with no tabs. Opened the test app; Render free-service wake page eventually redirected to login. No persistent QA login survived into this browser session.
- Secure browserAuth request submitted, but visible application result says Email or password is incorrect. No successful login, password reset, profile/account change or live six-industry checks claimed for THIS pass. Offer manual sign-in to existing QA owner sean@shinglextra.com, company AeriQuote QA. Never ask for credentials in chat or use Head Office/real dealers for this pass.

## Next

1. Complete QA login through secure/manual handoff, verify QA identity and retain warranty profile choice (currently OFF).
2. Check public selected-industry/signup flow and four setup screens; account creation/terms needs user completion. Existing one-account/six-setup live evidence from October 18 is in NEW_USER_FLOW_2026_10_18.md; do not mislabel it six independent accounts.
3. Live six-industry end-to-end checks and actual PDF downloads/rendering on current build, with labelled synthetic QA properties only. Earlier six-industry Single/Expanded pass remains valid prior evidence, not a newly completed current pass.
4. Mobile responsive/device checks and permissions gaps. Actual physical devices, separate ordinary-owner live foreign-ID mutation/images, backup restore, API cost/usage and retention remain outstanding broader prelaunch items. Do not declare launch readiness based on local green tests alone.
5. Reproduce/fix issues, verify deployed behavior and append exact evidence here. Preserve Pinehouse partial-scope safeguards; whole-building automatic accuracy remains unresolved. AI Trace stays removed.
