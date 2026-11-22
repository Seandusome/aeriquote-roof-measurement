# Draft choice expiry and safe Discard — November 22, 2026

Base: e5bebda3cb6bdec3097cd90d466c037883f35514. Deployed comparison: 80dc173805143382eff6c29dd381dee24d6fd903.

Sean reports reopening his previous session without deliberately switching accounts or businesses. Two old recovery choices remained visible after their displayed November 21 expiry, and Discard was followed by an account-context warning. His affected tab and hosted records were not accessed, refreshed, discarded or modified in this round. The personal property address is omitted from shared evidence.

## Established facts and remaining uncertainty

The deployed and isolated base versions have identical workspace_drafts.js and identical relevant server functions (home, draft identity, authentication gate, draft API). Fictional DOM reproduction establishes:

- Existing open chooser entries do not expire themselves or revalidate on pageshow. A page retained overnight can therefore show an expired choice even though a fresh authenticated server list would exclude it.
- Discard sends no version, allowing a newer acknowledged version from another tab to be consumed without a conflict.
- Discarding the last old choice rotates the current tab's independent draft ID, unnecessarily abandoning its acknowledgement identity.

The warning is produced by a comparison of page-supplied account context with the current authenticated session. It does not prove Sean intentionally changed businesses. A stale page, stale/cached response or different authenticated session can produce that comparison; none is established as Sean's exact cause. With an unchanged fictional login and a freshly rendered page, bindings match and authorized Discard works. No claim that Sean's exact session was reproduced.

## Isolated fix

- Filter initial expired choices and retire expired chooser entries on the existing periodic tick, visibility changes and pageshow, calibrated to server time when supplied. This removes UI choices only. It does not discard current work or issue DELETE because an entry expired.
- Discard sends the listed saved version. A newer version produces an explicit conflict and remains untouched. Refresh the owned version for an explicit later user retry; never silently delete the newer work.
- Require a version for server DELETE. Older pages fail safely with instructions to keep the tab open and use a fresh same-account tab to review the choice. They cannot perform unversioned destructive discard.
- Retain the existing Restore cleanup deleted:false protocol when another tab has saved a newer version. A successful explicit discard can be retried idempotently after a lost response.
- Keep current tab ID, acknowledgement and RAM workspace intact when removing an older choice.
- Show Discard progress/failures beside the specific entry, starting “Draft was not discarded.” Do not turn a discard error into a measurement-sync notification.
- Give account/principal conflicts specific codes and neutral page/login-context wording. Do not rebind identities or bypass server ownership/origin/employee checks.
- Mark workspace HTML, the recovery script and recovery responses private/no-store; request recovery data without cache reuse. This does not promise every browser will evict an already-open page.

No schema/migrations, retention duration, pitch/calculation, pricing, allowance, subscription enforcement, Stripe or imagery behavior changed. Existing server expiry purge behavior is unchanged. Only fictional local records were used for test deletions and transaction failures.

## Fresh verification

1. Nine jsdom scenarios: expired initial entry, expiry/pageshow, authorized discard preserving current exact RAM work and draft ID, stale version conflict/review/retry, 401 retry, 503 retry, stale account binding, stale principal binding and lost acknowledgement. Controlled HTTP boundary, not real browser/device verification.
2. New real-Flask/disposable-SQLite checks: exact 24-hour boundary and expired list filtering, server clock, no-store headers, unchanged-login page bindings, rejected stale/foreign account and principal requests, foreign origin and signed-out requests, missing-version denial, version conflict, delayed Restore cleanup, rollback after a fictional write-before-commit failure, authorized discard and idempotent replay. Independent SQL snapshots assert retained workspace and seeded allowance/usage records; unrelated draft remains exact.
3. Existing affected draft API suite passes: business/user/employee isolation, restore without allowance use, atomic save cleanup, exact retry receipt and one committed estimate/deduction, late autosave denial.
4. Existing affected pure storage and save-retry DOM suites pass. Syntax and diff-whitespace checks pass.

No completed industry, imagery, accuracy, PDF or payment suites rerun. No Chromium/Codespace/physical-phone verification in this round. PostgreSQL-specific execution not performed; the route uses the existing account lock and unchanged transaction/storage helpers. No browser launch attempted in the previously restricted runtime.

## Resume and limits

Fix remains isolated, not pushed or deployed. Sean's open tab still runs the old code. Preserve that tab and do not ask him to refresh, discard more records or repeat measurements before any recoverable workspace is privately preserved. Obtain its exact URL and inspect page/session bindings read-only before attributing the original warning.

Preserve source ancestry, all earlier fixes, Sean's complete phone-workflow confirmation against 80dc173 and existing backups. Accuracy comparison paused. Stripe paused; enforcement/deletion and Auto-Deploy unchanged/OFF. Google billing case #77793344, imagery licensing and mailbox delivery remain open. Final commit, backup verification and durable delivery are recorded in the companion closeout checkpoint.
