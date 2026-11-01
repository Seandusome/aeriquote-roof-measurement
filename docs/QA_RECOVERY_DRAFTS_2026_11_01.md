> Follow-up: authenticated live tab-close/Restore, exact data equality, one saved revision, unchanged retry/PDF counts, and Discard/refresh checks subsequently passed. Read [live QA results](QA_LIVE_RECOVERY_DRAFTS_2026_11_01.md). Earlier pending status below is historical. Physical-phone testing remains pending.

# Server-side recovery drafts — November 1, 2026

Owner approved implementation on recovery only, after checkpoint 965ec111. Production, main, customer data, database connections, prices and allowances are outside scope. Physical-phone/Safari/Messenger testing remains pending.

## Recovery contract

- Recovery records are separate from estimates, revisions, PDFs and credit counters. The authenticated business **and individual owner/employee identity** scope every read/write/restore/discard. A stale page's business and principal headers must match its signed-in session.
- Each tab starts with a random draft ID. Explicit Restore copies the acknowledged source into a new tab-specific record, acknowledges that copy, then deletes the source. Start a separate draft retains other recovery records. Restore/Discard are explicit choices; existing estimate history is never autosaved as a new workspace.
- Text changes debounce for 700 ms; measurement-summary changes use the same queue, with a 1.8-second periodic fallback. The visible status warns until server acknowledgement, and reports interruptions/login conflicts. Customer/pricing entries before property loading are included once the user edits them.
- Geometry, saved and unfinished measurements, source/mode, per-area/linear rates, taxes/discounts/extra service, customer details, pending save operation and base version are retained. Canonical fingerprints avoid treating JSON field ordering as an edit after recovery.
- Existing estimate saves retain single-flight/idempotency and If-Match protection. Draft data is deleted in the **same transaction** as a successful estimate save. A minimal 24-hour tombstone (identity, draft ID and save operation ID; no workspace/customer/imagery payload) rejects delayed autosaves. Receipt confirmation handles a committed save whose response was lost.
- Recovered property imagery sessions use only owned metadata retained when the draft was acknowledged. Restore does not invoke property lookup, estimate creation, PDF generation or credit consumption. Imagery initialization must not replace the retained measurement source/rates; Chromium reproduced and caught that issue for manual Roofing, and the restore sequence was corrected.

## Retention and privacy

The 24-hour recovery window starts at the latest acknowledged change; identical periodic checks do not extend it. Expired records cannot be read/restored. Physical deletion of expired records occurs on subsequent recovery API activity; this is not a dedicated background purge schedule. Successful save/discard erases workspace and imagery metadata immediately within its transaction. Existing database backups follow their existing retention policy.

No customer workspace is written to localStorage/sessionStorage. Passwords, API credentials, cookies and image bytes are excluded. Provider keys are stripped from retained imagery metadata and attached only to runtime requests. Pending save image bytes remain in the original tab's RAM; a recovered retry with an omitted image cannot bypass the existing server payload-hash conflict guard. Recovery guarantees only the latest server-acknowledged workspace, not edits made offline or after the last acknowledgement. External imagery may be fetched again, but stored measurement coordinates/quantities are not remeasured or silently replaced.

## Verification status

Verified source: `0f78e40f3acfd24979e53c1931b0c4448062ed29`. Full recovery **41358627500** PASS (recovery125004006982, PostgreSQL16/18 jobs125004007194/125004007215); application **41358627501** PASS; actual Chromium **41358627517** all six jobs PASS. No downstream checks are inferred from earlier failed runs.

User-reported **41357915739** at e8463abf failed exactly at scripts/test_failure_recovery.cjs:40:150. The fixture extracted workspaceSaveFingerprint without its new stableWorkspaceJSON dependency. The caught ReferenceError returned null; a null clean fingerprint then left beforeunload prevention active. Fix aa711367 includes the dependency in the VM extraction. The saved/no-warning, unsaved/warning, no-property/no-warning and empty-workspace/no-warning assertions are unchanged. Controlled A/B reproduction: omitting the helper reproduces true !== false; including it passes the entire existing test. The full recovery rerun above passes this test and every later check.

- Storage tests: business/individual isolation, separate IDs, lost autosave acknowledgement, stale writes, secret/image rejection, expiry/purge and discard tombstones pass locally.
- Real Flask API tests: owner/employee isolation, cross-origin rejection, exact workspace retrieval, expired imagery with provider calls forbidden, zero restore side effects, atomic save deletion, receipt replay and late-autosave rejection pass. Charged fixture starts at 199 and reaches 200 once; restore and retries do not add lookups or estimates. CI runs this on disposable PostgreSQL 16 and 18 as well as SQLite.
- Actual Chromium restoration suite covers 1440/390 widths, surface and manual Roofing, actual forced tab closure/refresh, interrupted autosave/retry, distinct simultaneous tabs, per-tab discard, exact geometry/pricing/customer equality, a committed save with its response lost, and Single/Expanded PDF generation/reopening. All four restored cases passed exact geometry, pricing and customer equality, actual tab close and refresh, interrupted autosave/retry and simultaneous-tab discard isolation. The Snow1440 case also passed receipt confirmation after a real committed response was aborted. Pre-property customer/pricing recovery passed without loading a property.

Eight restored-job PDFs (12 pages: Single1/Expanded2, Roofing/Snow at1440/390) were rendered and visually inspected. Independent WGS84/Decimal checks pass all4 restored sources plus12 six-industry baseline sources. Restored Roofing total79.30 =71.44+3.57+4.29; restored Snow153.18 =138.00+6.90+8.28. These are fictional grid-imagery fixtures, not survey accuracy or physical-phone evidence. PDF hashes, source snapshots, results, screenshots, independent outputs and complete job/step conclusions are saved under qa/recovery-drafts-2026-11-01.
- Full application/recovery and six-industry browser/failure workflows passed before deployment. Physical phones remain unverified.

## Reproductions and fixes during this batch

1. Recovery autosave initially hid the expired-login status behind a generic save failure. HTTP status is now retained, preserving existing login/409 guidance.
2. Manual Roofing's imagery initialization reset source to Google, producing zero recovered price. Exact-match browser assertion failed; retained fields are now reapplied after imagery initialization.
3. Saved historical viewing could create an unnecessary recovery record. Historical-view context is excluded; editing remains recoverable after explicit Edit.
4. Test integration fixes: focus protected notes before typing; target the unique injection anchor; include the canonical fingerprint helper in the VM fixture; explicitly choose a separate draft in fresh-session regression flows. Assertions for geometry, prices, allowances and save counts remain intact.

## Recovery-only deployment and remaining checks

Deployment **dep-dbjs3aajnfac738t6vs0** reached LIVE at2026-11-01T22:48:55UTC. Running checkout0f78e40f, exact service srv-db5a2g5ckfvc739fui70 and isolated PostgreSQL host dpg-dbj4f7lg1s2s73eob8t0-a /logical DB aeriquote_recovery_qa were verified before and after deployment without displaying credentials. Auto-deploy remains Off. Temporary login diagnostics and QA timeout remain disabled.

Live HTTP smoke: /dealer-login200; /static/workspace_drafts.js200; unauthenticated /api/workspace-drafts401. Read-only QA counts remain1estimate,20revisions,23save receipts. No live estimate/customer/account/allowance data was changed during this batch. Main remainsc049a04b; production remainsdep-db5b726k1f9s73e862ug/c049a04b.

**Pending:** a fresh cloud-browser request reached the login screen; live authenticated Restore/Discard smoke requires QA sign-in. Do not infer its cause or ask for password retries. No password or account setting was changed. Automated same-account recovery, employee isolation, charged-save recovery and actual Chromium flows passed in disposable fixtures. Physical-phone touch/Safari/Messenger remains separately pending.

The containing documentation/evidence commit is the resume checkpoint; live remains the verified source commit above. Do not deploy this documentation-only checkpoint. Resume with the known QA account qa-browser-oct31-2026@example.invalid and preserve the original measuring/report tab if available.
