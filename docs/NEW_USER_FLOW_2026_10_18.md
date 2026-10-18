# New-user flow audit — October 18, 2026

Recovery branch only. Starting head e3a41d3f46bbfaf69e3e6cecd2d43538abd28b2f. Sean requested reviewing signup -> setup -> first saved estimate/PDF for all six industries, with plain language and obvious next steps. Payments remain deferred. Main, AI Trace removal, Roofing scope guard and 5/12 manual default preserved.

## Diagnosis before changes
Live public flow: signup did not show which industry was selected or explain the 8-character password requirement. Network failures had no usable retry feedback or duplicate-submit protection. The nine-screen setup allowed empty business information, repeated contact details, included an information-only screen and had US State options still listing Canadian provinces. Source audit additionally found missing contact-name/website/region IDs in Pressure, Paving and Landscaping, missing default-rate IDs in Pressure/Paving, and missing tax IDs and tax-mode values in Pressure/Paving/Landscaping. These values were disconnected from the shared save handler.

## Changes
Four setup screens: business (optional service/property selections collapsed), starting price + explicit tax rates, optional branding/message, review + Save & measure. Contact details hydrate from the signed-in account and flow into estimate contacts without repeat entry; late hydration respects current edits. Canadian provinces/territories and US states use canonical codes. Blank taxes require a value (0 when not charged); no location-based tax calculation is claimed. Final review shows actual business/location/rate/taxes. Validation/error/retry remains on screen. Account save precedes local cache and navigation; browser-storage failure cannot strand a successful signup. Signup confirms selected industry with Change and Log in links and explains password length.

## Verification
Local: 12 clean/legacy setup paths, six signup flows, duplicate clicks, failure/retry, country changes, late responses, values persisted by the real Flask signup/profile routes using isolated databases and actual shared-JS payloads. Public routes/assets/inline JS, 29-page accessibility checks, account access/isolation, six-industry wording and measurement edge regressions, and five-industry surface workspace tests passed. No measurement/PDF application code modified.

Live deployment, visual inspection and fresh first-estimate/PDF checks pending at this checkpoint. Signed in securely to Head Office for measurement testing; do not save test setup over its profile. Actual new account creation in the live browser requires manual signup/terms acceptance; do not claim it was completed by automation. Isolated signup/profile integration tests are separate from live new-account verification.
