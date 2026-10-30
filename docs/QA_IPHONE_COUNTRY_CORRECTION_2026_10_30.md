# Physical iPhone report follow-up — October 30, 2026

Application checkpoint:2277d632b3da8668278dddfde31bf1c75c986a79, recovery only. Starting HEAD27133057b752257751b555ccac2a1d07e87d6484 was current and live (Renderdep-dbideo3bc2fs73d5b5l0). Its recovery/PostgreSQL jobs were confirmed SUCCESS before changes. Do not confuse initially queued collection results with the later completed jobs.

## Screenshot findings and confidence
Inspected all three supplied physical-iPhone screenshots IMG_7247/7248/7249. The first is the estimate with Area1 plus an independent two-segment Linear measurement. The latter two explicitly show Messenger's embedded browser, the measurement map and a disabled Edit Line button. That is consistent with Area replacement being active, not proof that the Linear control was selected. The map was scrolled into view while the Area Save/Cancel controls were above it. Clipped labels and map repositioning are visible; screenshots cannot expose JavaScript exception/state history.

**The complete physical iPhone first-tap freeze has NOT been independently reproduced or conclusively attributed to one cause. It remains pending physical Safari/Messenger retest.** Do not describe emulation, a user-agent string, or installed-but-unlaunchable WebKit as physical/Safari verification.

Confirmed independent defects repaired:
- Property address region dropdown was still mixed (51U.S. states/DC before13Canadian provinces/territories).
- Snow Removal's full-page terminology MutationObserver observed its own mutations and rescheduled indefinitely. Instrumented baseline:33passes in1.2seconds after taps with no input. Disconnect during its own wording pass, then reconnect:initial controlled after-test2passes and no repeating idle loop. Browser matrix passes1–3 settling calls rather than continuous churn. This is a real main-thread workload defect; evidence does not prove it alone caused Sean's physical freeze.
- Area remeasurement entered through a transient corner-edit/tool-toggle lifecycle. Replaced with direct draft initialization, explicit Area and pending-tool state, protected original snapshot, preserved independent Linear data/rate and unchanged overlap/invalidity guards. A stale pending Linear tool while already in Area mode is now explicitly corrected. Linear correction also explicitly sets its pending tool after activation.
- Report return scrolled directly to map center with smooth scrolling, leaving active Save/Cancel above the visible map. It now preserves map center while refreshing Leaflet size and immediately shows the existing active correction controls above the map. No new drawing control/tool or geometry formula.

Ruled out in Chromium:prior real emulated map pan alone did not reproduce a frozen click handler; Leaflet clears its moved flag when dragging is disabled. No speculative moved-flag reset or synthetic coordinate change added.

## Country/region audit
| Surface | Findings and result |
| --- | --- |
| Trial signup | Already Country first, Canada/United States; region belongs to next setup step. Preserved. |
| All six onboarding pages | Shared onboarding.js already filters13/51; preserved and browser-tested at three widths. |
| Business profile | Existing country-first13/51 fix preserved; browser-tested plus legacy full country-name/code profile restoration. |
| Property address | Added Property Country before address. Exactly13Canadian or51U.S./DC options. Country switch remembers prior in-page region, uses blank instead of selecting a new region silently, preserves accepted address/customer/measurements/taxes/history. Address-part restoration and saved editing set matching country before restoring SK/NU/YT/CA/TX/DC codes. CaliforniaCA remains U.S., not Canada. Empty unchosen defaults may follow profile country; loaded property location does not follow business-tax changes. |
| Legacy head-office new-dealer dropdown | Found U.S.-only; added country filter and13Canadian codes. Existing server state field contract retained; no account/data changes. DOM/Jinja verified. |
| Legacy head-office edit / initial bootstrap | State values are free-text inputs, not a combined state/province dropdown. Preserved exactly; no silent normalization/migration or changes to existing account controls. |
| Checkout mockup | Country-only selector; no state/province list to filter. Billing/Stripe unmodified. |

No tax auto-selection introduced. Profile country and property country remain independent. Property country is frontend selection context; property location is still derived from verified region/address or coordinates. Provider endpoints and request code unchanged. No allowance or persistence changes.

## Verification evidence
- Full regression:74/74 commands PASS on final batch, including independent geometry/server pricing, all existing account/business/employee/allowance protections, saved records, failed loads, both aerial exporters, QA Vector and Roofing safeguards. New targeted DOM tests also cover property address restoration, no tax/history changes, legacy admin13/51, explicit pending-tool state and no idle Snow wording loop.
- Normal mobile Chromium:15/15 (five surface industries x320/390/768px), actual trusted touch pan before estimate, report Area replacement, first/second/third taps all reach draft, no JavaScript errors, Cancel restores pan, wording loop settles.
- Messenger-style Chromium emulation:additional15/15, same sequence at844px viewport height with iPhone/Messenger user agent. This tests viewport/UA code compatibility ONLY; Chromium is not iOS WebKit or the actual Messenger app.
- Property/profile/signup controls at320/390/768px, all six setup pages each width. Correct Canadian/U.S. lists, region round trips, saved server payload unchanged after location switches. Browser selectOption is not native iOS-picker usability proof. Property390px screenshot visually inspected.
- Existing trusted-touch suite passed at320/390/768:repeated Linear, Area, reviewed Roofing and QA manual Roofing corrections, Save/Cancel/reopen, pan restored and pinch retained.
- Correction matrix15/15 with repeated replacement Save/Cancel, independent Area/Line preservation, exact report overlays from frozen saved geometry, no editing handles, server-save/reopen equivalence and independent haversine/cent pricing/tax checks.
-30 actual Single/Expanded downloads,45 pages Poppler rendered and all reviewed on three contact sheets. Two intended saved Areas and one independent Line; quantities/pricing agree with saved payloads. PDF exporter source block byte-identical to2713305. Independent GeographicLib WGS84 check of30polygons:max0.16838% difference from existing local projection/whole-ft2 rounding; no formula changes or property-survey accuracy claim.
- Controlled fictional imagery/temp SQLite QA accounts only. No live customer or production accounts. Reopened persisted data was verified; live provider image regeneration and Street View quality are not established by synthetic tests. Fixture marketing fields are reused deliberately and are not a fresh branding-isolation test.

## Runtime limitations
Playwright WebKit downloaded, but host libraries were absent; dependency fetches failed with503responses. WebKit/Safari tests were not run. An attempted disposable local PostgreSQL setup was unavailable due environment permissions; PostgreSQL verification is through the repository's isolated GitHub PostgreSQL16 job, not a customer database. Record the new commit's terminal job/deployment evidence in resume notes before declaring it passed/live. Never infer success from a running or queued job.

## Required physical retest
Do not mark the reported physical freeze resolved until Sean confirms. Reload recovery test page in standard Safari first, then Messenger separately. Choose Canada and check province list. Create Area1+Area2+Line; create estimate; REMEASURE AREA1 should show active Area controls, accept first and subsequent taps, retain original until valid Save, and Cancel should restore it. Repeat Area2 and EDIT LINEAR MEASUREMENT, Save/Cancel/reopen, recreate updated estimate and export both PDFs. Preserve independent measurements; never hide a billed Line to simplify the image. If freezing persists, capture which button was selected, browser and whether Save/Cancel can still be tapped.

Main/production/customer data untouched. AutoMeasure preserved; manual Roofing/Vector remain QA-only; AI Trace removed. No imagery migration, paid services, subscriptions, Stripe, CRM, historical data migration or PDF redesign.
