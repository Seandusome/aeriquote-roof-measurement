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

## Live continuation and profile-save fix

- Sean manually signed QA back in. Initial browser inventory hit native credential-data restriction; documented canonical navigation on retained tab recovered the document. Verified AeriQuote QA, owner controls (no Admin Dashboard), shield preference OFF.
- Opened current `QA TEST Phone Width Area and Line DO NOT SEND` revision: Commercial, 11,560 ft² and 291.7 ft, total $1,364.12. EDIT MEASUREMENTS / PRICE restored geometry, imagery and rates without a new property lookup.
- Added a second illustrative QA area, 3,991 ft². Create was disabled during the active drawing and re-enabled after SAVE AREA. Two areas and original line retained. Normal keyboard rate entry changed second area to $0.20/ft²; first $0.10 and line $0.35/ft stayed independent. Summary/rows updated.
- Saved new revision `QA TEST Prelaunch Commercial Oct20 DO NOT SEND`, with explicit synthetic QA notes. 15,551 ft² + 291.7 ft. Service amounts $1,156.00 + $798.20 + $102.11 = $2,056.31; taxes $102.82 + $123.38; total CAD $2,282.51. No profile save, customer communication, grants or real dealer edits. Old versions retained.
- At first actual Single PDF download attempt, native retained credential-data protection blocked command before a download path and reset browser kernel. No completed export, actual PDF visual inspection, Expanded download, reopen of this NEW revision or remaining industry live pass claimed. Stopped browser interaction; no alternate browser/tab/credential extraction bypass.
- Code audit reproduced profile-save defect: saveDealerDefaults wrote local cache and showed saved immediately while ignoring HTTP/network failure. Fixed to await explicit server {ok:true}, prevent concurrent submissions, leave entries/cache/job rate intact on failure, show a retry message, and allow successful account save when localStorage is unavailable. Existing successful-save default-rate behavior preserved; no measurement math, profile permissions, shields, main or real accounts altered.
- New scripts/test_profile_save.cjs exercises actual handler with HTTP/network/unconfirmed-response failures, in-flight duplicate clicks, retry, logo/shield payload, unchanged entries/cache/job rate on failure, and browser-storage quota failure after server success. Passed. Added to recovery CI.
- After fix: warranty shield regression, all six saved-edit restorations, 12 setup flows, six isolated real-Flask signup/profile persistence paths and business isolation passed. Python compilation/diff whitespace checks passed. One rerun initially lacked NODE_PATH for nested JS; corrected environment and passed. Earlier 40-script full pass remains prior evidence; no claim that all 41 reran after this change.
- Publishing profile-save fix to recovery; actual live success/error UI recheck pending browser recovery. Public setup/mobile/remaining live industries are still pending for this current pass. User should not be told everything is ready for live users yet.
