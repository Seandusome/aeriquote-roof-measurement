# Live QA resumed — October 20, 2026

Recovery branch only; source unchanged during this pass. Read RESUME_HERE_2026_10_20.md and QA_SAVE_TIMING_2026_10_20.md first. Browser session successfully resumed on the test service, company AeriQuote QA / sean@shinglextra.com. No credential access or protection bypass used.

## Deployment

Render workspace Shingle Guard tea-daaurjp5efls7391kvj0. Test service srv-db5a2g5ckfvc739fui70. Render confirms df34b1ffcabd5a4612b7f19d6d97ce26ee7287a6 LIVE in dep-dbbup4k9v7es738rik40, finished 2026-10-20T22:35:38.156588Z. Live UI loaded successfully.

## Actual live checks

- Commercial QA record reopened through Previous Estimates > View History > current Open Estimate. Two areas 11,560 and 3,991 square feet at $0.10/$0.20; line 291.7 feet at $0.35. Subtotal $2,056.31, taxes $102.82/$123.38, total CAD $2,282.51. Original QA-only notes retained. Edit Measurements / Price restored both areas, line and rates.
- ACTUAL Single PDF downloaded and rendered: one page. ACTUAL Expanded PDF downloaded and rendered: three pages, aerial then details then marketing continuation. All pages visually inspected: imagery, outlines, edge labels, Street View and correct prices present. Expanded area-number callout overlaps the area-1 label/outline slightly; pricing is readable. No new layout fix made.
- Blank saved-area rate after committed blur and negative rate block Create with explicit warning. Explicit zero restores enabled Create and free area service. 101% discount blocks Create with discount warning. Negative GST blocks Create with tax warning. Original rates/taxes restored before leaving; invalid test prices never submitted.
- Some automation fill operations changed displayed values without committing onchange; definitive checks used focused keyboard entry, blur, and a separate subsequent DOM observation. Do not count pre-commit snapshots as successful validation evidence.
- One same-price QA revision was saved during initial field-event investigation at 22:38:51 UTC. Total remained $2,282.51; original previous versions retained. No real dealers touched.
- Profile website marker qa-save-check.example saved with success feedback and restored after reload along with company, default $0.10 rate and 5%/6% taxes. Temporary website removed, original Roofing account profile saved again, shield remains OFF. Subsequent reload displayed Roofing. No account allowance or complimentary settings changed.
- Unsaved-note interruption: edited notes to a disposable marker, reloaded BEFORE creating estimate, reopened saved record. Original notes and $2,282.51 total survived; unsaved marker absent. This checks leaving before save, NOT an in-flight failure.

## Isolated test rerun

Existing local preserved checkout: test_estimate_save_integrity.cjs, test_profile_save.cjs and test_profile_restore.cjs all passed again. Includes delayed image response/frozen payload, HTTP/network/unconfirmed profile failures, retry, duplicate-click prevention, storage failure and settings hydration. These are synthetic tests, not forced live network failures.

## Remaining live evidence gap

Deliberately delayed/failed in-flight saves and profile restoration with unavailable browser storage remain NOT live-verified. Supported browser interface has no network-interception/offline/storage fault-injection API; do not bypass browser controls or force failures on real accounts. Normal live save/reload and interruption before save passed.

Main, application source, real dealer accounts, credits/grants and complimentary settings untouched. No estimate sent. QA browser tab retained for continuation. Published as a separate documentation checkpoint on the recovery branch.

Downloaded proof paths (ephemeral):
- Single: /workspace/scratch/04ed5b86-cf6b-4fe2-ac71-c7dce29d5e60/da72b0ad-d61a-47cc-ab09-d7e6da4f3eb1
- Expanded: /workspace/scratch/04ed5b86-cf6b-4fe2-ac71-c7dce29d5e60/a79ba44f-c398-4896-a69d-fe9a6d752b97
- UI proof: /workspace/scratch/aq-live-qa-commercial-oct20.jpg

## Final additional live check

Commercial linear rate cleared through focused keyboard entry and blur: warning "Enter a linear service rate of 0 or more" displayed and Create disabled. Restored $0.35 through keyboard entry and blur: Create enabled, line $102.11, taxes $102.82/$123.38, total $2,282.51. No new save/export/account-profile change in this final check. Screenshot /workspace/scratch/aq-final-linear-check-oct20.jpg. Stop for the day at user request; live in-flight failure testing remains pending.
