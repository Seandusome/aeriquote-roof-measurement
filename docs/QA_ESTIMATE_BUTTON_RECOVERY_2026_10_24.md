# Estimate button recovery — October 24, 2026

Recovery branch only. Starting remote checkpoint: `725472c14f9337be6a1e5bcf6e1dfec437a8ff8e` (local equivalent `67a7421`).

## Evidence and limitation

User supplied a screenshot showing CREATE CUSTOMER ESTIMATE disabled, a crossed-circle pointer and a previously reported save error. Two areas and a line remain visible. User reports no nearby warning. The user's open browser tab is not accessible through the available browser session, so its precise internal error and current unsaved estimate have not been inspected or recovered. Earlier hidden-draft reproduction does not prove that was the user's cause. Do not request developer-console commands or claim the existing tab was repaired by a server deployment.

## Confirmed additional defect

`showCustomerEstimate` acquired its in-progress lock and disabled the button before preparing report metadata/branding/pricing. Only the later imagery-building stage had a finally block. An exception during earlier report preparation escaped and left the lock/button stuck with no local failure message. Reproduced in the real DOM/Leaflet regression by making report marketing preparation fail: the pre-fix test failed because the exception escaped.

## Change

Wrap the entire post-lock report construction/save/open sequence with catch/finally. Preparation failure hides an incomplete overlay, reports that the estimate could not be prepared, preserves measurements and always releases the lock/button. Download stays disabled if the report was not successfully opened. Existing image fallback and duplicate-action guards remain.

Add a live status message adjacent to Create Estimate. It announces preparation, copies an existing save failure reason when saving fails, or displays a preparation failure locally. Text uses textContent; it is cleared when a report opens. Pricing and geometry validation are not bypassed. No measurements, rates, taxes, account records, credits, imagery or PDF generation engines are changed.

## Verification

Targeted actual DOM/Leaflet regression passes for Landscaping, Snow Removal, Pressure Washing, Paving and Commercial:

- Injected report-preparation exception is caught.
- Lock clears and Create Estimate is enabled.
- Failure message is visible next to the button.
- Saved area and line coordinates remain identical.
- Restoring report preparation and retrying sends exactly one save request and opens the report.
- Local failure status clears and geometry remains unchanged after retry.

Existing actual Single/Expanded and QA vector report entry tests and estimate-save integrity tests passed. Full recovery regression suite: 67 commands passed, zero failed. No authenticated live customer workflow or physical-device testing is claimed.

## User work protection

A deployment does not replace JavaScript already executing in the user's original tab. The current job remains unverified and potentially unsaved. Keep that tab open; do not instruct a refresh, destructive removal or retracing as if the work were already safely stored. This commit prevents the reproduced lock failure in newly loaded code but cannot remotely unlock an inaccessible old page.
