# New-user flow audit — October 18, 2026

Recovery branch only. Starting head e3a41d3f46bbfaf69e3e6cecd2d43538abd28b2f. Sean requested reviewing signup -> setup -> first saved estimate/PDF for all six industries, with plain language and obvious next steps. Payments remain deferred. Main, AI Trace removal, Roofing scope guard and 5/12 manual default preserved.

## Diagnosis before changes
Live public flow: signup did not show which industry was selected or explain the 8-character password requirement. Network failures had no usable retry feedback or duplicate-submit protection. The nine-screen setup allowed empty business information, repeated contact details, included an information-only screen and had US State options still listing Canadian provinces. Source audit additionally found missing contact-name/website/region IDs in Pressure, Paving and Landscaping, missing default-rate IDs in Pressure/Paving, and missing tax IDs and tax-mode values in Pressure/Paving/Landscaping. These values were disconnected from the shared save handler.

## Changes
Four setup screens: business (optional service/property selections collapsed), starting price + explicit tax rates, optional branding/message, review + Save & measure. Contact details hydrate from the signed-in account and flow into estimate contacts without repeat entry; late hydration respects current edits. Canadian provinces/territories and US states use canonical codes. Blank taxes require a value (0 when not charged); no location-based tax calculation is claimed. Final review shows actual business/location/rate/taxes. Validation/error/retry remains on screen. Account save precedes local cache and navigation; browser-storage failure cannot strand a successful signup. Signup confirms selected industry with Change and Log in links and explains password length.

## Verification
Local: 12 clean/legacy setup paths, six signup flows, duplicate clicks, failure/retry, country changes, late responses, values persisted by the real Flask signup/profile routes using isolated databases and actual shared-JS payloads. Public routes/assets/inline JS, 29-page accessibility checks, account access/isolation, six-industry wording and measurement edge regressions, and five-industry surface workspace tests passed. No measurement/PDF application code modified.

## Live verification and remaining scope
Application 2d9d0def105f2b7ad3aa51630f089c789fd6bdd3 deployed and recovery CI passed. Built-in browser walked all four setup screens in all six industries using clearly labelled QA input, stopping before saving to Head Office. Roofing: California/United States and 0% tax final review. Other five: Saskatchewan/Canada, $0.37/ft² and 5% + 6% tax final review. Required Company Name validation, automatic estimate contact preview and optional collapsed fields worked.

Live Landscaping first measurement on 2301 Ave C North #115: illustrative rectangle 10,107 ft² at $0.10, tax 5% + 6%, total CAD $1,121.88. Saved a labelled QA estimate, no customer correspondence. First attempt coincided with deployment and failed to rebuild the aerial; a fresh property load after rollout rebuilt the estimate aerial and dimensions correctly. The earlier failed QA version remains in history; no records deleted. Do not claim a confirmed cause beyond that observation.

Subsequent live PDF/all-industry estimate checks were interrupted by browser native credential-state protection. A documented fresh tab and runtime-reset recovery also failed. Do not repeatedly probe protected browser state. Remaining: live new-account signup (manual credential/terms step), first-estimate/live PDF checks in Roofing, Snow, Pressure, Paving and Commercial, fresh Landscaping PDF export, mobile visual QA. Yesterday's actual PDF visual pass is still valid evidence for yesterday's fixture, not completion of this new-user pass.

Follow-up aligns tax labels with country and clears stale rates when changing country. US exposes the single sales-tax field the existing estimate engine supports; Canadian second tax is not silently carried into US setup. Local tests cover this; final follow-up live visual check remains pending browser recovery.

Signed in securely to Head Office for measurement testing; do not save test setup over its profile. Actual new account creation in the live browser requires manual signup/terms acceptance; do not claim it was completed by automation. Isolated signup/profile integration tests are separate from live new-account verification.
