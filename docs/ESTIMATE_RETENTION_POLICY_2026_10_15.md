# Approved estimate retention policy — October 15, 2026

Sean approved this policy after the afternoon checkpoint. It supersedes the earlier one-year full-estimate storage assumption.

- Full estimate content, including saved imagery and any stored PDF files: retain for six months.
- Lightweight estimate record: retain for one year. Preserve estimate wording, customer/property information, measurements, pricing and dates.
- After full-content expiry, identify the retained record clearly: "Images and PDF expired". Do not present it as the complete original estimate or promise an identical original PDF can be recreated.
- Apply the same full-content limits to relevant estimate revisions so old revisions do not retain expired imagery unintentionally.
- This policy concerns estimates. It does not authorize expiring accounts, company branding, reusable business wording/templates or support records on this schedule.
- Existing customer downloads or emailed attachments cannot be removed by server cleanup. The policy covers content held by AeriQuote.
- This is approved product policy only. Automatic expiry/deletion has NOT been implemented or enabled. No current records were changed.

## Implementation requirements before enabling cleanup
Inventory actual stored media and PDFs first; a policy mentioning PDFs does not mean the current app already stores generated PDF files on the server.
Define the retention clock (including handling of revisions, subsequent edits and calendar-month boundaries) before implementing scheduled cleanup.
Separate heavy media from lightweight fields while preserving estimate content, ownership and revision relationships. Test using synthetic expired records in isolation.
Show retention periods to customers and provide download guidance before activating the policy. Verify backup retention and restore behavior so expired media is not silently reintroduced.
Actual record sizes and the extra six months of lightweight records still need measurement. This is not a verified database capacity or legal compliance assessment.

## Resume order
Read this alongside docs/CHECKPOINT_2026_10_15.md and docs/HOSTING_CAPACITY_COSTS_2026_10_15.md.
Sean is still on a break; no application or infrastructure changes are included in this documentation update.
