# Tester fixes — October 16, 2026

Recovery branch only; parent 629648a. Full-width measurement layout preserved.

## Roofing AutoMeasure regression
The tester reported Main house needs remeasurement on previously tested properties. Sean's supplied photograph shows the replacement marker. The October 15 main-roof calls to reviewAutomaticRoof applied condo heuristics to all main roofs, discarded their returned areas and hid outlines. These heuristics compare regional mask outlines, provider building bounds and partial solar coverage; they are not evidence that Google's returned measurement failed.

Main-roof outline/footprint disagreements now produce a review warning while preserving the automatic measurement and outline. Existing main-house confirmation acknowledges that review. No automatic correction or area scaling occurs. Unavailable or zero-area provider results remain subject to the existing fallback behavior. Additional-roof strict review and the explicit pitched remeasurement workflow remain available.

## Snow Removal wording
Corrected the additional-service placeholder (previously shingles/vent/roof repairs), translated hover/help attributes reversibly, and translated dynamic snow statuses immediately. Measurement-step help now excludes Roofing instructions when the selected industry is not Roofing. Snow's Area and Linear tools remain unchanged. Switch back to Roofing restores its wording. The in-app Help script version is bumped for cached browsers.

## Checks
DOM/Leaflet tests cover the real Roofing property loader with a footprint/coverage disagreement, retained automatic area and pricing, and normal main-house confirmation. Existing condo replacement/cancellation, multi-area/linear pricing, aerial detail, saved snapshots and PDF regressions remain covered. Snow tests check placeholders, tooltips, statuses and restoring Roofing terms; Help dialog tests check snow-specific instructions. JavaScript rendering/parser and public routes are checked. No paid API calls, live Render logs or live account data were used.

Deploy the branch to the commercial test service, refresh, and repeat the tester's two addresses. Review each actual outline/area; automated fixtures do not independently certify Google coverage. Verify Snow's Additional Services placeholder, measurement help and hover help. Main/production untouched.

## Render startup and live imagery deadlock
The c79bcc5 build succeeded but the old start command (`gunicorn app:app`, sync worker) timed out during Render port detection. The exact platform detection cause was not proven. Direct dashboard access became available; only the commercial test service start command was updated to explicit 0.0.0.0:$PORT, one worker, four threads, timeout 90, access/error logs to stdout. Deployment dep-db97o1bl550s73d264ag became Live for c79bcc5 in 44.1 seconds. Free hosting remains; no paid upgrade was made.

The first live Roofing test returned /property 200, then /rgb 500. Render's actual traceback shows psycopg.errors.DeadlockDetected in require_dealer_login -> estimate_db -> ALTER TABLE estimates. Every authenticated image request was running all schema migrations, so concurrent RGB/Street View requests could deadlock on exclusive table locks. This is an application database-initialization failure, not evidence that Google rejected imagery.

Correction: run the existing schema setup once per process/database under a thread lock; use a PostgreSQL transaction advisory lock to serialize initialization between processes, commit before caching success, close failed initialization connections, and allow a later retry. Ordinary authenticated connections no longer run schema DDL. Connection establishment is bounded by 10 seconds. Existing schema SQL and account/estimate records are preserved; there is no data deletion or measurement/pricing change. Regression tests cover 24 concurrent authenticated RGB/mask/Street View requests, absence of repeated DDL, PostgreSQL serialization/lock, and retry after failed initialization. PostgreSQL coordination uses a mocked driver in automated tests; live request logs remain the deployment verification.

Sean requested broad verification before further user testing. Run the complete recovery workflow's Python/Node checks plus the concurrency regression, deploy the fix directly, and verify Live and fresh logs. Do not claim that mocked tests independently validate live Google measurements or a backup restore. Main untouched.
