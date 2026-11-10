# Customer-facing review - hosted 09e795d0

## Hosted observations

Reviewed `aeriquote-commercial-test` on deployed `09e795d0fb30761a9b5e37a62dbe181e8ee18d2a`. Normal sign-in completed, and the signed-in profile showed **QA TEST FICTIONAL HOSTED ACCESS NOV05** with **Employees** owner controls. No estimate or allowance changes were made.

Owner click path today: **orange VIEW PLANS / UPGRADE** in the app header -> `/site/pricing` -> **CHOOSE PLAN** -> `/site/upgrade?plan=basic`. The upgrade page says: **Payment setup in progress. Checkout is not yet enabled.** No card collection or payment action is present.

There is **no hosted extra-measurement purchase entry point**. An authenticated GET to `/qa/purchases` returns 404. `qa_purchase_screen.py` is included in the deployed source, but its handler explicitly refuses Render environments, non-loopback hosts and non-disposable databases. It is **development-only simulated purchasing**, deliberately disabled on hosted QA, rather than a hidden functioning checkout. Do not remove these guards to expose it.

The earlier Library preview **AeriQuote_Purchase_Preview.html** was read and compared. It is a standalone simulation, not connected to any account. Its pack terms are:

| Term | Earlier simulation | Hosted pricing/upgrade |
|---|---|---|
| 25 extra measurements | Present | No pack offer |
| US$25 | Present | No pack price |
| Estimates included | Present | No extra-pack statement |
| Purchased extras carry forward | Says never expire; active paid/complimentary subscription required; retained on cancellation | Only monthly allowances discussed; no purchased-extras statement |
| Applicable tax | Before applicable tax; simulated jurisdiction-based tax and final USD total | General tax FAQ only, no extra-pack tax quote |

Simulation example SK tax of US$2.75 and total US$27.75 is a fictional configured fixture, not approved live tax policy.

## Current wording and proposed changes

| Screen | Hosted wording | Prepared local copy |
|---|---|---|
| Website | **Roof AutoMeasure**; loads available Google measurements and pitch information | **AI-assisted roof measurement, with your review**. Use AI-derived roof data from Google where available, review the outline and confirm the pitch. If incomplete or unavailable, trace manually. Other services use manual areas/lengths; own pricing and branded estimates. |
| Pricing | **Aerial property measurement**, **Branded PDF estimates**; monthly allowances | Add the distinction between automatic roofing with review/pitch confirmation and manual surface/linear tools. Add a clearly labelled planned extra-measurement offer. |
| Signup | **Start with 3 Free Property Measurements & Estimates**; no credit card/no automatic billing | Keep trial at three. Add roofing-specific review/pitch/manual fallback instructions; generic manual service-area/length instructions for other industries. |
| Measurement | **AUTOMEASURE / Roof • automatic**; **The main house will measure automatically**; tool-selection instructions | Qualify availability. Explain reviewing an available outline, confirming pitch, manual tracing when needed, then pricing and a branded estimate. Keep existing action buttons and coverage safeguards. |

No explicit stand-alone **AI** label was visible on the reviewed hosted pages. The proposed AI wording is limited to Google's automatic roof data, not manual tracing, all industries, universal coverage, or an AeriQuote-owned AI model.

Primary-source support: Google's announcement explains its Solar API uses an AI model to extract roof geometry from aerial imagery: https://blog.google/products-and-platforms/products/maps/google-maps-apis-environment-sustainability/ . Building Insights documentation also cautions that the returned building can differ from the geocoded address: https://developers.google.com/maps/documentation/solar/building-insights . These claims do not replace AeriQuote's outline/coverage checks or pitch confirmation.

## Small local review candidate

**Code commit:** `cd2786f1a6ce1194d92f5865fd0686271f650fd6`, branch `qa/customer-copy-09e795d0`, based exactly on hosted `09e795d0`. Not pushed or deployed.

Only `app.py`, `site/index.html`, `site/pricing.html`, and `site/trial-signup.html` changed. The owner's existing orange header link becomes **PLANS / EXTRA MEASUREMENTS**, opening `/site/pricing#extra-measurements`. Non-owners retain the previous plan link.

The new pricing section says **25 extra property measurements for US$25, plus applicable tax. Estimates included.** It distinguishes no-expiry purchased extras from resetting monthly allowances, states the active subscription requirement, and plainly says **Purchasing is not available yet**. There is no purchase button, payment request, simulation link, ledger mutation, or activation of checkout. This makes the planned offer findable without implying a working payment service.

Review-only copy is included for the website, pricing, signup and measurement help. No outline eligibility, pricing formula, pitch calculation, limits, signup behavior, payment guards or PDF code changed.

## What Stripe still needs

- Server-side owner-authorized Checkout Session creation, with the fixed USD25 pack/25 measurements and stable order/business mapping. Never trust client amounts or a redirect as proof of payment.
- Stripe credentials and product/price configuration through secure server-side settings; choose and validate applicable tax treatment and billing location, then show final tax/total before payment.
- Signature-verified webhook processing, replay/idempotency protection and atomic one-time fulfillment into the business-scoped allowance ledger. The existing simulated order/ledger logic is disposable-only and is not wired to production account balances.
- Subscription/complimentary eligibility and canceled/reactivated states connected to actual account access, while retaining purchased extras.
- Receipt/history, failed and abandoned checkout, refunds/disputes and reconciliation. Complete Stripe test-mode end-to-end checks before separately approving live payments.

None of this integration was implemented or activated here.

## Verification and screenshots

- Hosted normal owner sign-in and fictional company: PASS.
- Owner navigation to pricing and disabled plan checkout: PASS.
- Hosted `/qa/purchases` unavailable: confirmed 404.
- Original simulated pack terms: confirmed by current Library file read and matching source.
- Existing full landscaping/roofing control suite on the copy patch: PASS, **Script errors: []**. This was run before the final static AI sentence adjustment; that adjustment changes only literal website/pricing text.
- Disposable SQLite purchase tests: PASS. Read-only GET, owner/employee/business/CSRF/origin/disposable/hosted guards, pending/failure/retry/success, concurrent/replayed confirmation, exactly one pack, tax fixture, cancellation/reactivation. No real money moved.
- Python/Jinja owner vs non-owner navigation rendering: PASS. Non-owner retains original link. No new behavioral tests added for copy-only edits.
- Local visual review of candidate: **PENDING**. Local Chromium cannot launch in this workspace; the managed browser refuses `file:` previews. No workaround was attempted. Screenshots below show actual **hosted before state**, not the undeployed candidate.

Screenshots in `docs/qa/customer-facing-2026-11-10/`:

- `hosted-owner-entry.jpg`: exact orange button to click today.
- `hosted-pricing.jpg`: monthly plans, no extra-measurement offer.
- `hosted-checkout-disabled.jpg`: Stripe/payment setup incomplete.
- `hosted-purchases-unavailable.jpg`: authenticated local-simulation route unavailable.
- `hosted-signup.jpg`: existing three-measurement signup copy, no explicit AI wording.

## Preserved hold state

Auto-Deploy freshly verified OFF via Render metadata (`autoDeploy=no`, trigger `off`). Hosted Google configuration was not changed. No deployment, push, main/production or customer-data changes. Payment processing stays inactive.

Mapbox PDF checkpoint remains saved separately at `../mapbox-review/docs/QA_MAPBOX_PDF_OUTLINE_2026_11_10.md`: application `b08406339b8b4822c6ef99c832a76338a6558e66`, evidence checkpoint `b4e1cb17b47ff3bc4affc5946347ec0557e67b51`. Native Single/Expanded Chromium visual verification, actual older/fresh estimate exports and fresh Google browser-export control remain **pending**. No Mapbox work was resumed during this customer-facing review.
