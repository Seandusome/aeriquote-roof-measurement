# Optional Vector Diagram PDF - QA contingency, October 22, 2026

## Scope and activation

Based on remote recovery checkpoint `8c1a51377888533847a729a7edcdfcbf1db41fc0` (local equivalent tree `201ec8d634d027c0d1d59aa85a7462a5ce55fe8c`). Work only on `landscaping-multi-area-recovery-oct11`. No main/production changes, customer-account activity, provider replacements, credit changes or AutoMeasure/Leaflet engine changes. AI Trace stays removed. This is not a licensing clearance: removing pixels from a PDF does not independently authorize deriving measurements from a provider's imagery.

Default remains Single aerial PDF. Expanded aerial PDF implementation is unchanged. New Vector Diagram option is rendered only when BOTH `AERIQUOTE_VECTOR_PDF_QA=1` AND `AERIQUOTE_VECTOR_PDF_QA_IDS` explicitly includes the signed-in QA business's dealer_id. Neither setting was enabled remotely. Do not put paying/customer businesses in this allowlist. Employee access inherits the explicitly listed business; unlisted businesses receive 404 for QA script and validation endpoints. Disable the flag to reverse availability; no data migration is needed. The separate manual-roof QA flags/code are preserved.

## Implementation

- `qa_vector_pdf.js`: SVG diagrams and native jsPDF vector paths/text share the same projection model. All six industries supported. No property image, basemap, Street View, mask, Solar or Mapbox resource is read by the exporter.
- Only geometry belonging to the quote's active measurement mode/source is included. Old traces from unpriced tools are excluded. Service areas and priced linear work remain combined. Each included building/area/line receives its own enlarged diagram page and horizontal vertex-to-vertex dimension schedule; overview preserves relative position, aspect and north-up orientation.
- Saved pitch-adjusted roof surface quantities are printed unchanged, alongside saved pitch. Horizontal dimensions are explicitly distinct from sloped surface quantities. An automatic building with only an outer outline remains an outer outline; numerical roof segments and pitches are listed, with no invented facet polygons.
- QA validation endpoint calls existing independent `snapshot_error` checks without writes, reservations or provider calls. Incomplete, overlapping, mismatched or unverified measurements are rejected. Module adds coordinate, extent, area/pitch, distance and geometry checks. Historical `adjusted` roof-source quotes are explicitly blocked pending scope review; existing aerial PDF remains available.
- Customer report details and geometry are frozen together before asynchronous validation. Quotes/prices/taxes/discounts/additional services/recurring terms are copied from the prepared report, not recalculated by this exporter. Double-clicks are single-flight. Expired sessions and unsaved report-outline edits block export.
- Company/contact information, customer phone/email, marketing text and prepared estimate wording are retained. Already-loaded dealer logo/warranty badge may be copied as branding images; no property imagery is embedded. Thus the product is property-image-free, with raster branding allowed. Branding not ready or canvas access failing stops export rather than dropping branding silently.
- Licensed DejaVu Sans font and notices included, embedded to avoid host font-substitution corruption. QA unsupported character cases fail with a clear message directing the existing PDF; broad multilingual typography is not certified. Dense outlines, extreme latitudes >=85 degrees, property extents >1 degree and historical adjusted-source cases are not launch-approved.
- No changes to `/api/estimates` saving, pricing arithmetic, measurement calculations, monthly credits, property loading or provider selection. Reopening a saved estimate still follows its existing workflow and can load existing aerial imagery; this feature does not make that entire workflow provider-free.

## Verification

Four new commands added to the recovery workflow:

1. `python scripts/test_vector_pdf.py`: isolated SQLite QA identities; flag/default/account isolation, actual save/reopen for all six industries, existing server geometry rejection, unchanged saved payloads and no provider calls.
2. `node scripts/test_vector_pdf.cjs`: all industries, area/linear and manual multi-pitch roofs, analytical independent spherical-rectangle and meridian references, projection aspect/north checks, reopen invariance, invalid/missing coordinates/quantities/pitch rejection, SVG escaping, no fabricated automatic facets, inactive trace exclusion, long metadata and preserved customer/pricing text.
3. `node scripts/test_vector_download.cjs`: actual download entry points in an emulated DOM; rapid repeated clicks, frozen details during workspace changes, validation failure/session expiry and unsaved-outline blocking. No html2canvas/aerial dependency for vector export.
4. `node scripts/test_vector_full_report.cjs`: uses the real existing DOM/Leaflet manual-roof test workflow to generate the actual customer report, then invokes its QA vector download. Displayed total and snapshot are unchanged; only QA validation requested. Existing Single/Expanded exporter regression also executes. Emulation, not physical-device/live authenticated testing.

Complete local recovery suite: 67/67 commands passed. Included all existing measurement, pricing, tax, seasonal, save/reopen, authentication, credit, provider routing, manual roofing and Single/Expanded regressions. Final artifact checks independently validate all three example payloads with server Decimal pricing. Release-file checker now includes JS/font/licence (20 required files). No real PostgreSQL instance was exercised locally; unchanged disposable PostgreSQL CI job remains in workflow.

## Actual PDF evidence

Actual jsPDF 2.5.1 output bytes, rendered through Poppler and visually reviewed. Shared geometry produces SVG files too; SVG XML and dimensions checked. No live authenticated cloud-browser download or physical-device test claimed.

- `simple-roof.pdf`: 5 pages, generated from the actual DOM/Leaflet manual-roof customer report. Two roof sections, flat confirmed section and 45-degree added section. Exact saved surface quantities retained; independently checked total CAD 440.13.
- `complex-roof-garage.pdf`: 4 pages; L-shaped roof at approximately 6/12 pitch plus detached 45-degree garage, dimensions, branding logo and estimate details. CAD 3170.10; extra CAD25.50, 10% promotion, GST5% and PST6%.
- `multi-area-linear.pdf`: 5 pages; two separate service areas with per-area rates, linear work, extra/discount/taxes and seasonal wording. Independently checked CAD1618.43 per season.

Examples are synthetic QA records, not real customer accounts or verified roof surveys. JSON source payloads and SVGs travel with the PDF example bundle outside the application source tree. Raster objects in the branded example belong to the dealer logo (shared PDF resources), not property images. Unbranded examples have no image resources.

## Remaining limits / stop state

QA flag stays OFF. No manual deployment or Render configuration changes. Authenticated live browser download, real mobile/native print, very dense vertex-label layouts, comprehensive Unicode and real logos through browser canvas are not verified. The default aerial layouts remain the fallback. Government/provider imagery and measurement-derivation licensing still require written resolution. Do not activate customer access or change providers without Sean's separate approval.
