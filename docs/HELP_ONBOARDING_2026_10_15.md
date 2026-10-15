# Help and first-estimate guidance — October 15, 2026

Working branch only: landscaping-multi-area-recovery-oct11. Main/production untouched.

## Implemented
- Public /site/help with six searchable guides: first estimate, tools/corrections, pricing/branding, PDF/history, account recovery, allowances/records. Static text is available without JavaScript.
- Five-step first-estimate walkthrough follows the actual current controls. Optional industry guidance covers Roofing, Snow, Pressure, Paving, Landscaping and Commercial.
- Approved practice address: 2301 Ave C North #115, Saskatoon, SK, Canada. Practice loading may consume an allowance; help never loads a property automatically.
- App header now offers HELP / FIRST ESTIMATE and each workflow step has optional Help with this step. A keyboard-accessible dialog opens alongside the work and can be closed/reopened; guide navigation does not advance or change the actual job.
- Mobile navigation and public footer link to Help. Support form points users to the first-estimate guide before submitting a request.
- Uses current AutoMeasure / + ADD AREA / + LINEAR / FINISH & SAVE AREA / FINISH & SAVE LINEAR / CREATE CUSTOMER ESTIMATE / DOWNLOAD ESTIMATE PDF / PREVIOUS ESTIMATES terminology.
- Explains that customer-estimate outline corrections change the picture rather than measured quantities/price. Advises verifying saved history and downloaded PDF instead of promising every save succeeded.
- Does not promise monthly quota resets, direct estimate emailing, automatic retention deletion, or unimplemented account features.
- No screenshots were fabricated, no imagery regenerated, no customer details included. Actual workflow screenshots from the approved property can be added after a live walkthrough if they materially improve instructions. Initial guide uses clear steps rather than blocking on images.

## Validation
- All existing inline application JavaScript remains identical to the pre-change baseline; only help markup, external assets and public-page routing changed in app.py.
- New functional test covers six guide searches/deep links, all industry explanations, the optional five-step walkthrough, keyboard focus and close, and zero job mutation or API calls.
- Public page tests cover 29 pages, clean/legacy routes and help assets. Existing measurement/control, onboarding and pricing tests remain in CI. Browser visual/live walkthrough is still Sean's next review after deployment.

## Pending independent work
- PostgreSQL deployment persistence was already verified; do not repeat it for context recovery. Paid AeriQuote database was upgraded to 0.1c-256mb by Sean; recovery was initializing. Backup export/isolated restore still need verification.
- Nancy is Sean's co-owner, initially unpaid, with a small wage planned around 300 customers. Customer support cash costs and developer maintenance should be budgeted separately.
- Main developer priority remains reliable first-use flow and protecting customer work, not adding a CRM. Measurement audit feedback is pending independently.
