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
