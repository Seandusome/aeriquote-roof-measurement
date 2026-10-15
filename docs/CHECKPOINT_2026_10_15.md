# AeriQuote checkpoint — October 15, 2026, afternoon break

## Resume instructions
Read this checkpoint first, then docs/SUPPORT_AND_STORAGE_2026_10_15.md, docs/UI_AUDIT_2026_10_15.md and docs/CHECKPOINT_2026_10_14.md. Recover latest branch head before changing code. Do not repeat completed work.

- Repository: Seandusome/aeriquote-roof-measurement
- Authorized working branch: landscaping-multi-area-recovery-oct11
- Commercial test site: https://aeriquote-commercial-test.onrender.com/
- Render commercial test service: srv-db5a2g5ckfvc739fui70
- Latest application commit at this checkpoint: 2f40155071312193153ca0febf168986f95a9741.
- Its Validate landscaping recovery workflow passed.
- Sean's latest feedback after deployment: "looks good", then requested an hour break and a durable checkpoint.
- This checkpoint is a documentation-only follow-up. No new application deployment is required just to save it.
- Main/production must remain untouched. Do not restore AI Trace. Preserve completed measurement, pricing, imagery and PDF improvements.
- Existing project is GitHub/Render, not a new Sites build. Do not restart or replace it.

## Confirmed completed work
### Previous baseline preserved
October 13 measurement/pricing/aerial/PDF improvements remain protected. October 14 account login and secure password recovery were implemented and live tested by Sean. Existing plan pricing remains Basic $29/25, Pro $59/75, Business $99/200; use the full allowance wording "Per measurement & estimate". Payments/Stripe remain deliberately separate.

### October 15 website and onboarding
- Implemented website audit cleanup in 65b6d09: responsive navigation, layout/contrast/form/FAQ/legal consistency, approved imagery reuse, sample estimate, browser icon, clean website routes and login/recovery styling.
- Setup completion on clean URLs was fixed across all six industries in c89ddc9.
- Sean confirmed the setup finish action worked and looked cleaner.
- Measurement system is being independently audited for more feedback. Wait for actual findings rather than speculate or alter its engine.

### Support intake and staff workflow
- Six icon topics: Getting Started, Account & Login, Measurement & PDF Help, Report a Bug, Billing & Subscription, Feature Request.
- Requests save to the existing database before notification; validated public form, CSRF, limits, reference IDs and duplicate-safe submission.
- Links to Support requests and Deployment storage check are on the CURRENT Admin Dashboard. An initial link-placement mistake on the legacy dealer page was corrected in 92a0fa8.
- Open / In Progress / Resolved, timestamped private notes, archive/restore and confirmed deletion for test/spam requests.
- Deletion requires exact ticket reference and removes its related notes/replies/imported messages/routing record. It does not delete emails from external mailboxes.
- Sean live-tested ticket deletion successfully.
- Current remaining test ticket: AQ-3594CE9E7B63, customer address sdusome@diitalk.com.
- One ordered conversation combines original request, outgoing replies and incoming customer messages. One status selector is by the heading; Send reply is the primary action. Internal notes and More actions are collapsed.
- Outbound customer emails use approved AeriQuote logo, readable HTML layout, paragraph spacing, compact ticket footer and plain-text fallback. Sean confirmed receipt and approved the appearance.
- Recognized quoted email history is collapsed under Show quoted email. Display-only cleanup applies to existing incoming messages; stored original text is unchanged. Unknown formats remain visible.
- Sean approved the latest quoted-history cleanup: 2f40155.

### Incoming email connection — working live
- Webhook: https://aeriquote-commercial-test.onrender.com/api/public/support/inbound
- Resend event: email.received.
- Receiving domain: oiwhaestoi.resend.app.
- Outgoing replies have persisted random per-ticket Reply-To routing addresses.
- Raw-body Svix signature verification, five-minute timestamp tolerance, receiving API retrieval and received-email UUID deduplication.
- Matching uses routing token/domain plus original customer's sender; DMARC failures or unmatched messages remain separate. Matching replies reopen/unarchive the ticket; automated replies do not reopen it.
- HTML email is converted to readable text, never rendered raw. Attachments remain in Resend with a count notice.
- Received matching replies also attempt a team email notification, with saved failure state and retry.
- The initial 503 was AeriQuote's "Email retrieval temporarily unavailable." The original Resend key had Sending access only.
- Sean created a separate Full access receiving key in Render as RESEND_RECEIVING_API_KEY, leaving the working sending key unchanged.
- After that deployment, Sean confirmed customer replies appeared in the ticket. Do not repeat the receiving-domain/webhook/API-key setup.
- All secrets were entered directly into Render. Never request or store their values in chat/docs.

## Environment configuration and support ownership
Working configuration includes:
- RESEND_API_KEY: original sending key (password resets and outgoing emails).
- PASSWORD_RESET_FROM: existing verified AeriQuote sender at accounts@aeriquote.com.
- AERIQUOTE_PUBLIC_URL: commercial test site's HTTPS base URL.
- SUPPORT_REPLY_DOMAIN: oiwhaestoi.resend.app.
- RESEND_WEBHOOK_SECRET: signing secret for the configured webhook.
- RESEND_RECEIVING_API_KEY: separate Full access key for reading received content.
- SUPPORT_INBOX: optional override; code currently defaults to sean@aeriquote.com.
- Production decision: actual support/team notification emails must go to Nancy@aeriquote.com when live. Set SUPPORT_INBOX on the production service at that time; no production service was changed.
- Sean later clarified sean@aeriquote.com is NOT yet an established mailbox. We suggested using SUPPORT_INBOX=sdusome@diitalk.com for testing, but that change and actual team-notification inbox delivery have NOT been confirmed. Check this before declaring team notifications complete.
- Nancy does not yet have separate limited support access. Do not assume configuring her email grants admin permission.

## Storage, persistence and backups — NOT yet verified live
- Protected Head Office page: /head-office/storage.
- Shows connected backend and presence of stable FLASK_SECRET_KEY without exposing values.
- Saves a baseline of per-record hashes for accounts, employees, business profiles, estimates, estimate revisions and support requests; compares missing/changed/added records after restart.
- Fixed PostgreSQL dict-row compatibility in /api/estimate-storage-status.
- Local tests proved checkpoint comparison/restart/missing detection. No live before/after checkpoint results were supplied by Sean.
- Support tickets appeared across multiple reported deployments, which is encouraging evidence for those records only. Do NOT claim this proves accounts/estimates, backup recovery or the database configuration.
- Determine actual connected PostgreSQL vs SQLite from the protected page. SQLite needs a Render persistent disk. External PostgreSQL still requires backup/restore verification.
- Save a NEW checkpoint after intentional ticket cleanup. Deliberately deleted tickets show as Missing; support schema changes may show as Changed.
- Checkpoints are comparison records, not backups. No customer database export or restore exercise has been completed.
- This git checkpoint protects source code and development continuity, not an unverified live database.

## Agreed commercial readiness priorities, excluding payments
Sean explicitly wants proactive ownership of missing essentials, not only reactive individual fixes. Assess the whole customer journey without adding a CRM.
1. Make the testing support notification inbox deliverable; confirm notification delivery, not just provider acceptance.
2. Verify live account/profile/estimate/revision persistence across deployment, then establish backups and a realistic restore check.
3. Audit full signup → industry setup → measurement → pricing → customer estimate → PDF → saved estimate reopening without assistance. Classify must-fix-before-feedback / before-paid-launch / later.
4. Check lost-work handling for reloads, expired sessions, connectivity failures and navigation.
5. Finish account readiness: email verification, forgotten-email ownership recovery, disabled-account guidance, profile controls and employee permission checks.
6. Complete real monthly allowance/reset rules and clear remaining-usage/limit communication. Correct displayed plan prices alone do not prove billing-period quotas are ready.
7. Verify error reporting, uptime alerts, email failure visibility and business-data isolation/security.
8. Provide Nancy appropriate separate support access before public operations; avoid sharing Head Office credentials.
9. Initial feedback can use downloaded PDFs attached manually. Sean agreed to prioritize Email estimate before paid launch, after support/storage essentials. Do not start it prematurely.
10. Payments/Stripe are known pending and intentionally excluded from this immediate discussion.

## Validation
Existing CI includes account access, password recovery, website routes/UI, onboarding completion, activation controls and industry measurement regressions.
Support tests:
- scripts/test_support_storage.py
- scripts/test_support_workflow.py
- scripts/test_support_replies.py
- scripts/test_support_inbound.py
- scripts/test_support_quote_display.py
These cover authorization/CSRF, legacy migration, notes, archive/delete, outgoing payload isolation/escaping/retries, signed inbound matching/deduplication/reopening, ordered conversations and display-only quoted history.
Automated email tests use mocks; live confirmations above are Sean's actual tests.

## Practical resume notes
- Staged local files: /workspace/scratch/8900f653a175/ui-audit-work; scratch is transient, GitHub is authoritative.
- Older checkout /workspace/scratch/423ffc3aefb0/aeriquote-roof-measurement has stale/unrelated modifications; never bulk-commit it. In particular, do not publish an unrelated commercial-approved.png modification.
- Changes were published with explicit GitHub blobs/tree/commit and a leased update of this recovery branch only.
- Sean manually deploys latest commit in Render; do not claim to have operated Render.
- First task on return: read this checkpoint, confirm live state, resolve the test notification inbox if still pending, then proceed to storage/backup proof. Do not re-test already approved support features just to recover context.
