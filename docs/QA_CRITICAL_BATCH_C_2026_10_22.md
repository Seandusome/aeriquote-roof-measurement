# Approved critical fixes — Batch C, October 22, 2026

Starting Batch B checkpoint 5e3ec19: application/full recovery workflows passed; PostgreSQL job120021160918 passed and Render dep-dbd5mhek1f9s738nqma0 LIVE. Batch A b734d96 remains its ancestor. Recovery branch only.

## Confirmed problems fixed

Profile saves previously accepted malformed contact email and could overwrite other valid branding in the same request. Client and server now validate common unquoted email address syntax, including local/domain lengths, dot placement, domain labels and whitespace/header injection. Invalid, blank and non-string supplied email values are rejected before database writes. Valid surrounding whitespace is trimmed. Partial updates that omit email retain the existing address. This checks format, not mailbox existence/ownership; a syntactically valid typo cannot be detected without an email verification process, which was not added.

Dealer logo rendering previously depended on browser localStorage even though the server stored the image. Logo data now has an account-scoped in-memory authoritative value populated by the server; browser caching is optional. Server-loaded branding updates the visible preview. Empty server logo data clears stale cached images. Uploads and approved brand choices work when browser storage is blocked/full; unsaved local logo choices are protected against a late profile response. Account changes clear logo memory/cache so another business cannot inherit branding. Explicit removal still requires saving the profile to persist, preserving the approved workflow.

## Verification

Actual isolated Flask routes verify invalid writes preserve the entire profile, not just email; valid plus-address format/trim; persistent company/logo/taxes/marketing through independent authorized sessions; employee receives owner's branding and cannot change it; business isolation; saved logo removal; expired authentication. JavaScript tests exercise the real logo helpers and profile restore with blocked storage, stale images, account switching and active-job protection. Profile-save tests verify client rejection makes no request and existing failure/retry safeguards still hold. Complete regression suite is required before publication.

Independent sessions and simulated storage are not physical-device testing. Actual cloud-browser QA login is unavailable in this run; no claim is made of a fresh live login/logo upload/PDF visual pass. Existing Single/Expanded PDF, shield, saved geometry/pricing and account tests remain in the full suite. Real customer/production accounts and main were not modified. AI Trace remains absent.

## Resume

All three approved batches are separate recovery commits. Find final hashes and completed CI/deployment results in the conversation; this report is published in Batch C's complete Git tree. Billing anchors remain explicitly provisional until trusted Stripe period data is connected and reconciled. No Stripe integration, credit sales or CRM changes were made.
