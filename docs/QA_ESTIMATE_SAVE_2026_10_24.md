# Estimate save investigation — October 24, 2026

Recovery branch only; starting GitHub checkpoint `7df356a399539b4f7b1f3c385b97ccfc6cafe951`.

## Live evidence

User reported Snow Removal, two areas and one linear measurement, failing to create an estimate. Render recovery test-service access logs show POST /api/estimates returning HTTP 400 at 21:35:23, 21:35:30 and 21:36:01 UTC, each 102 response bytes. A prior Roofing save returned 200. No matching error-level crash log was found. This establishes validation rejection rather than a transport failure for those requests, but does not establish the exact user's payload or validation cause.

The 102-byte response length matches the generic independent pricing exception response; length alone is not proof of its contents. The user subsequently reported a normal-looking estimate button apparently doing nothing. The user's local browser tab is not accessible in the available browser session. Its state has not been inspected or modified, and no refresh was requested.

## Confirmed reproduced defects

1. The save wrapper discarded server validation errors other than 401/409 and presented all remaining failures as a connection problem. Corrected: other 4xx JSON validation messages are displayed with an estimate-not-saved prefix and assurance that measurements remain. Network/timeout and server failures retain the generic retry message; login/conflict handling is unchanged.
2. In a real DOM/Leaflet combined Area + Linear flow, a saved service-area list containing valid areas plus a zero-area unfinished record passed quotePricingError in Linear view. The independent server price calculator then rejected it with `Save every service area before quoting`, caught as a generic pricing validation response. Corrected: unfinished/nonfinite area records block creation explicitly on the client, and zero-area records receive the same clear server validation message before pricing. No records are silently discarded or changed.

The incomplete-record reproduction matches a possible path to the reported failure, but the specific user's current measurement has **not** been verified to contain that record. Do not claim the user's exact root cause or live successful save has been confirmed.

3. A real control sequence reproduces the orphan record without injecting state: two saved areas and a line, click Add Area, place no points, then switch to Linear. The old tool switch left the empty record in commercialAreas while rendering only the two positive saved areas. New navigation uses the existing Cancel behaviour when leaving an empty area draft. Saved polygons, line points and rates remain unchanged. A draft containing any points still blocks switching and requires an explicit Save/Cancel; it is never silently discarded.

## Verification

- Full recovery regression suite: **67 commands passed, zero failures**.
- Existing DOM/Leaflet combined two-area/line workflows passed for Snow Removal, Landscaping, Pressure Washing, Paving and Commercial. Their captured complete snapshots also passed independent Python geometry/pricing checks during investigation.
- Added five-industry regression coverage: real empty Add Area → Linear navigation cancels only the empty draft, and synthetic unfinished records still disable quote creation in combined Linear view, with saved areas/line unchanged. Removing only the synthetic test draft restores quote readiness.
- Added actual API regression: unfinished area rejected with clear message, saved estimate and revision history unchanged; deliberately free positive-area quotes remain supported.
- Added actual save-wrapper regression: HTTP 400 validation reason shown, no connection-blame message, snapshot/last-successful key unchanged, retry succeeds.
- Existing failure, idempotency, expired session, PDF, pricing, manual roof, account isolation and credit regressions passed within the full suite.

## Scope and limitations

Only recovery-branch application error/validation handling and related tests changed. Measurement geometry, quantities, rate/tax arithmetic, PDF renderers, imagery and credits are unchanged. No real customer account or database record was accessed or modified. Main/production untouched. All destructive/regression data used isolated local QA storage. User's unsaved work remains in their original browser tab, outside agent visibility.

After deployment, validate a fresh isolated QA combined Snow Removal estimate and continue diagnosing the user's original tab without refreshing away unsaved work. Live confirmation of the user's exact failing payload is still needed if the issue persists.
