# Support intake and deployment storage verification — October 15, 2026

Branch: landscaping-multi-area-recovery-oct11. Main remains untouched.

## Support
- Contact & Support now has six accessible SVG topic cards: Getting Started, Account & Login, Measurement & PDF Help, Report a Bug, Billing & Subscription, Feature Request.
- Public web/mobile form validates input and CSRF, applies submission limits, saves requests in the existing account/estimate database before notifying Resend. Reference IDs and idempotent submission protect network retries from duplicate requests.
- Notification recipient is sean@aeriquote.com, explicitly selected by Sean. Optional SUPPORT_INBOX overrides it. Uses the existing RESEND_API_KEY, PASSWORD_RESET_FROM and AERIQUOTE_PUBLIC_URL configuration. Reply-To is the submitter’s email. No additional API secret is needed.
- Head Office → Support requests lists the latest 100 saved requests, escapes user input and can retry failed notification attempts. Accepted means accepted by Resend, not inbox delivery confirmation.
- Optional page links have query strings/fragments removed to avoid storing reset tokens. No attachments, chat, phone queue or CRM was added.

## Storage
- Corrected PostgreSQL dict-row compatibility in /api/estimate-storage-status count queries.
- Head Office → Deployment storage check shows the connected backend and whether a stable FLASK_SECRET_KEY is configured; never reveals connection strings or secrets.
- Save a pre-deployment checkpoint. It records per-row hashes for accounts, employee accounts, business profiles, estimates, revisions and support requests. No raw account contents are copied into the checkpoint.
- After a real Render redeploy, reload and confirm the same checkpoint remains and Missing is zero in every row. Changed rows may reflect legitimate activity. New rows are allowed. Process identity changes alone do not prove a deployment occurred.
- Checkpoints are comparison records, not backups. SQLite requires a configured persistent disk. PostgreSQL backup policy must be verified in Render separately.

## Validation and remaining live steps
- Backend tests cover actual public intake, CSRF, malformed input, redacted URLs, saved email failures, idempotent retries, admin authorization/escaping and checkpoint survival across module restart, including missing-record detection.
- Frontend tests cover all six SVG cards, failed-network retry with retained values/same request ID, and saved reference confirmation.
- Existing account-access, password-recovery, clean public routes and public UI checks pass locally. Embedded measurement application HTML is unchanged.
- No real support email was sent during automated tests. After deployment, submit a clearly labeled test request, check sean@aeriquote.com and Head Office. Then save a storage checkpoint, redeploy the same commit, reload and inspect Missing counts. Render persistence is not yet proven by local tests.

## Support workflow follow-up
- Added Open, In Progress and Resolved ticket states, plus timestamped private support notes. Notes are internal and do not send customer email. Replies still use the support email inbox.
- Resolved requests can be archived, viewed separately and restored. Test/spam deletion has a separate confirmation page and requires the exact ticket reference; it removes the ticket and its private notes, but does not remove previously sent emails.
- Existing tickets migrate to Open with their messages intact. Email notification status is labeled separately from resolution.
- Lifecycle tests cover migration, access/CSRF, notes escaping, status validation, archive/restore and confirmed deletion. No live customer tickets were changed during development.
- Adding workflow columns can show existing support rows as Changed in a prior storage checkpoint; deliberate deletion of a test ticket will show it as Missing. This is expected and must not be confused with deployment data loss. Save a fresh checkpoint after cleanup before testing another deployment.

## Customer replies and quieter internal notes
- Reply to customer is the main ticket action, with an explicit recipient, Send reply button and saved outgoing email history. Uses existing Resend sender; Reply-To is sean@aeriquote.com (or SUPPORT_INBOX override).
- Customer-facing replies are stored before transmission. Provider acceptance is distinguished from inbox delivery. Failed/uncertain attempts preserve text and can be retried using the same provider idempotency key; accepted replies are not re-sent on repeated form submissions.
- Internal notes are collapsed by default in a native details control beneath replies/status. Private note submission is separate from email sending.
- Customer email responses arrive in the support mailbox; inbound email synchronization is not implemented. No live email was sent by automated tests.
- New tests cover admin/CSRF, exact recipient and Reply-To, private-note exclusion, escaped reply history, saved send failures, retries, repeated submissions and deletion cleanup.

## Incoming email — prepared, external setup still required
- New signed endpoint: `/api/public/support/inbound`. Verifies raw bytes against Resend/Svix signature and a five-minute timestamp window. Received-email UUID deduplication prevents re-import and duplicate ticket reopening.
- Retrieves body from Resend Receiving API; stores readable text, never renders raw email HTML or loads attachments. Attachments remain in Resend with a count notice in the ticket.
- Outgoing support replies use a persisted, random per-ticket Reply-To address once configured. Matching requires that route plus the original customer sender; DMARC failures and unmatched emails stay separate for review. Automated responses are recorded without reopening. A matched customer reply reopens and unarchives its ticket.
- Matching replies also notify the configured SUPPORT_INBOX; failures leave the customer message saved and can be retried from the ticket. No real mail was sent during development.
- Sean specified production support recipient **Nancy@aeriquote.com** on October 15. Set `SUPPORT_INBOX=Nancy@aeriquote.com` on the production service when going live. Keep the commercial test service on Sean's inbox. Nancy does not automatically gain Head Office access; staff permissions remain unchanged.

### Activation steps
1. Deploy this recovery-branch update on the commercial test service.
2. Resend → Emails → Receiving → receiving address (three-dot menu). Copy the account's actual `<id>.resend.app` domain. This option requires no GoDaddy DNS changes. A custom receiving subdomain can be configured later; do not replace MX records for aeriquote.com or disrupt existing mailboxes.
3. Resend → Webhooks → Add webhook: `https://aeriquote-commercial-test.onrender.com/api/public/support/inbound`; select only `email.received`.
4. Render Environment: set `SUPPORT_REPLY_DOMAIN` to the actual receiving domain (no @ or username), and `RESEND_WEBHOOK_SECRET` to that webhook's signing secret. Enter the secret directly in Render, not in chat or GitHub. The receiving API needs read permissions; if the existing sending key cannot retrieve received email, add `RESEND_RECEIVING_API_KEY` with appropriate access without changing the working sending key.
5. Save/redeploy. Send a NEW customer reply from the dashboard to a real test inbox, reply from that inbox, then refresh Support requests. Verify the customer message appears once, a resolved/archived ticket reopens, and Sean's test inbox receives the notification. Test signed-webhook retry handling through Resend if needed.
6. Historical outgoing emails still point at the old Reply-To mailbox and are not retroactively imported. New outgoing replies use routing addresses after activation. Configuration presence is not proof of live delivery; run the full loop before claiming completion.

Official references: https://resend.com/docs/dashboard/receiving/introduction ; https://resend.com/docs/dashboard/receiving/get-email-content ; https://resend.com/docs/webhooks/verify-webhooks-requests ; https://docs.svix.com/receiving/verifying-payloads/how-manual

## Support screen simplification
- One conversation per ticket combines the original request, outgoing replies and received customer messages in chronological order. No duplicated message sections or empty incoming-reply notices.
- One status selector sits by the ticket heading; the primary Send reply action sits directly under the conversation.
- Internal notes and More actions (archive/delete/notification details) are collapsed by default. Accepted outgoing email details are secondary; failed/uncertain sends keep a visible retry action.
- Incoming-mail setup guidance appears once above the inbox. This UI change does not activate the receiving connection or send email.
- Extended reply tests check chronological interleaving, no duplicated original message, one status control, collapsed secondary actions and preserved escaping/retries.

## Customer support email presentation
- Sean confirmed a dashboard reply arrived in the customer mailbox on October 15; outbound sending is live-tested.
- New replies include branded HTML with the existing approved logo, a readable single-column layout, preserved paragraphs/line breaks and a compact reference footer. Plain text remains available.
- Message and reference content are escaped before entering HTML. Private notes are excluded. Sender, recipient, reply routing and provider idempotency remain unchanged.
- Automated tests inspect both email formats and HTML escaping with a mocked provider. Appearance in a real email client still requires a new test reply after deployment.

## Incoming support reply confirmed and quote cleanup
- Sean confirmed a customer reply appeared in its ticket after adding RESEND_RECEIVING_API_KEY with Full access. The original sending-only key remains unchanged. Outbound branded email appearance was also approved live.
- Recognized quoted email history now appears in a collapsed Show quoted email disclosure. The customer’s new message remains prominent. This is display-only and applies to previously saved replies without changing their stored text.
- Familiar dated reply headers, Original Message/Outlook blocks and final quoted lines are recognized conservatively. Unrecognized formats remain visible. No text is deleted, and quoted content is escaped in the disclosure.
- Tests cover the reported reply format, single-line variants, Outlook, bottom-posted/ordinary replies, stored-text preservation and escaped disclosure markup.
