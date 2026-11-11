# Manual-first CI correction

Parent: exact1bab0ca306929d1b92524cc308a59cb2daaf07be. Application code unchanged; fixture and CI updates only. Deployment paused, payments inactive, Mapbox branch separate.

## Reproduced actual responses

- test_complex_roofs: structure() returns a Flask (JSON,409) tuple. Normalized response is HTTP409 with {"error":"Automatic roofing is unavailable in the manual roofing workflow."}. The old fixture wrongly expected an automatic roof dictionary and called get_json directly on the tuple. This is the intended customer manual-first guard, not a roof-route regression.
- test_failure_recovery line103: HTTP200, {"center":{"latitude":52.0,"longitude":-106.0},"exact_pin_display":true,"fallback":true,"fallback_aerial":"static","formatted_address":"52.000000, -106.000000","manual_roof_only":true,"parts":{"city":"","postal":"","province":"","street":""},"street_date":null,"token":"<fixture token redacted>"}. Solar building mock was never invoked. Old unprepared successful request appropriately raised fixture lookup usage199→200; it was not a failed request consuming allowance. Reproduction stubbed optional Street View only to avoid outbound calls. CI16/18 failed at the same assertion; their original logs did not print response bodies.

## Correction and retained coverage

Complex-roof suite now first asserts default409 and no provider requests/state mutation, then exercises all original stable building, area, own-mask/cache, ownership, preservation and503 assertions through the explicit localhost account-allowlisted AutoMeasure test gate. Flask return values are normalized using make_response.

Recovery suite injects a real geocoding timeout in the normal workflow and asserts HTTP400/exact error and no allowance consumed. Invalid coordinates and address-not-found remain. A separate fictional owner prepares a valid direct-coordinate manual lookup with an assertion that Solar is not called. Preparation and failed imagery both leave usage199; imagery failure is exact400 with expected fixture error. All existing concurrency, rollback, stale/replay, revision, employee and expired-session assertions remain unchanged.

The measurement-edge DOM suite also asserted superseded “selected tool” introduction text. Its copy assertion now checks pitch confirmation and manual tracing; every invalid-geometry and editing assertion remains.

A further stale fixture in test_api_cost_routing expected Solar on every roofing lookup. Normal mode now asserts zero Solar on all six industries, correct static/manual roofing response and uncharged preparation. Optional --automatic retains original automatic Solar route inventory via explicit isolated gate; both modes run in CI. Legacy nonroofing RGB fallback, malformed industries, address mismatch and exactly-once accept checks remain.

## Verification before publication

PASS focused complex-roof suite, SQLite failure/concurrency/recovery suite, API URL inventory in default and explicit automatic modes. No live provider calls. Existing Python manual-roofing, pricing/geometry/draft/acceptance suites included in broader local checks; final results retained separately under docs/qa/manual-first-ci-2026-11-10. PostgreSQL16/18 binaries unavailable locally: actual server verification must come from full GitHub Actions on the correction, not SQLite substitution. No safety rules, allowance implementation, geometry validation, application route or payment behavior changed.

Auto-Deploy was freshly confirmed no/off on aeriquote-commercial-test. Remote recovery branch verified1bab0ca before publishing. No deployment or settings changes authorized here. Publication/CI outcome to be recorded after the actual run; this document alone is not a CI pass.
