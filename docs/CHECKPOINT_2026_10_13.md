# AeriQuote verified checkpoint — October 13, 2026

Application baseline: e4e64ec05a6b866e1fbfff7b07751cf7b5e333a0.
Repository: Seandusome/aeriquote-roof-measurement.
Work only on landscaping-multi-area-recovery-oct11. Never modify main.
This checkpoint records verified behavior, not a production launch approval.

## Decisions to preserve
- AI surface tracing is retired and removed. Do not restore it or propose further paid tracing tests.
- Preserve manual area and linear tools, automatic roof measurement, wide aerial panning, saved estimates, prices, and PDFs.
- Use existing approved logos; do not recreate branding.
- Street View wall image at the test property is property-specific and is not a defect to fix.
- Refresh/deployment clears the active measurement workspace. Saved reports can be reopened, but that is not a complete editable-job recovery feature.

## Verified by live user tests
- Paving: two areas plus linear measurement, independent units, rates, taxes, PDF and saved reopening.
- Original paving version: 15,370 and 10,399 ft² plus 674.6 linear ft; total $6,644.64. Previous-version reopening retained original data.
- Fresh and reopened PDF labels render clearly and remain above outline strokes.
- Aerial labels, service-area rows and pricing agree after the stale-aerial export fix.
- Company logo/contact data and customer email appear in PDFs.
- Internal notes save and display in expandable history cards; they stay out of customer PDFs.
- Saved surface jobs use Service area; linear-only jobs use Service length and linear feet.
- Pressure Washing: linear first remains selected during loading and remains visible while drawing two areas.
- Latest Pressure Washing test: 12,680 and 11,864 ft² at $0.40/ft², 601.9 ft at $0.70/ft, subtotal $10,238.95, 5% and 6% taxes, total $11,365.24.
- Pressure Washing PDF and saved reopening retained both areas, length, rates, taxes, customer details and notes.
- Both GitHub workflows passed on e4e64ec.

## Automated checks
Engine checks for landscaping, paving, pressure and snow; DOM + Leaflet area/linear controls; linear-first visibility across five surface industries; delayed aerial/profile loading; saved historical canvas labels; PDF label capture and restoration; notes-only saving and reopening; history wording; Python and inline JavaScript syntax; aerial framing; recovery-account allowance isolation.

## Next steps, not yet live verified
1. Snow Removal: verify combined areas + linear, PDF and reopening with current shared fixes (earlier basic snow test passed).
2. Different per-area rates in the latest Pressure Washing workflow (latest live test used equal area rates).
3. Broader landscaping/commercial and roofing regressions after shared export changes.
4. Website wording audit: retire AI surface-tracing claims; do not imply automatic lawn/paving measurement.
5. Stripe subscription/payment integration and launch readiness are not established by measurement tests.

User is opening an AeriQuote bank account and asking about Stripe Canada onboarding. Resume software work from this verified baseline when they return; avoid repeating passed tests without a new reason.
