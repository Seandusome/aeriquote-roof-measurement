# QA vector PDF design correction — 2026-10-23 UTC

Recovery branch only: `landscaping-multi-area-recovery-oct11`.
Starting GitHub checkpoint: `e4ac515e1a4d39bb1caa52cf2edcd3b55443ee8c` (tested local tree `f5f5108ce5fe3a3bb58b1b6646903b6a55f3a5c6`).

## Inspection and design target

Reviewed the supplied two-page Professional Roofing Estimate Brochure mockup and the existing four-page vector examples before changing code. The previous exporter used landscape pages, a short overview panel, one page per shape, a separate technical details page and branding at the end. This created small roof drawings and unnecessary pages.

The revised QA exporter uses portrait Letter pages, a repeated logo/company/contact header, navy headings and total band, pale-blue filled outlines, consistent spacing and a quiet QA footer. Page one contains customer/property information, large diagrams, a measurement key and the existing enabled marketing wording in compact cards. Page two contains enlarged individual views, horizontal edge dimensions, saved pitch-adjusted quantities and the frozen report's pricing breakdown. Ordinary examples fit two pages; long descriptions, numerous sections or dense outlines may continue.

No decorative roof ridges, valleys, roof sections, trees, driveways or property boundaries from the mockup were invented. The fixture buildings are widely separated. For two or three shapes with a sparse combined extent, explicitly labelled independently scaled insets enlarge individual saved outlines; a separate north-up location diagram preserves their real relative spacing. Each view uses uniform projected scaling. Buildings are never moved inside the location diagram. Other properties retain a shared overview.

## Scope and protections

Only `qa_vector_pdf.js` and three vector regression/fixture scripts changed, plus this document. `app.py`, existing Single/Expanded aerial exporters, flags/account allowlists, imagery integrations, AutoMeasure, manual roof tracing, saved estimates, prices/taxes and credits are unchanged. Vector mode remains behind the existing server flag AND QA business allowlist; aerial is still default. No QA flags were enabled remotely and no customer accounts were accessed.

Existing geometry/quantity validation still runs before PDF construction. Historical segment quantities remain text unless saved outlines exist. Price labels and formatted amounts are copied from the frozen customer report, without exporter arithmetic. Branding uses only the already loaded/frozen dealer logo and optional warranty asset. No property images or external provider requests are introduced. Disabled marketing is excluded, including when its parent panel is hidden. Overlong metadata and pricing rows continue instead of being silently truncated; dense outlines retain all dimensions on continuation pages.

## Verification

- Full recovery workflow regression runner: **67 commands passed, zero failed**. Targeted vector tests also rerun after the final pagination changes.
- Six-industry geometry and export regressions; independent analytical rectangle area, meridian distance, latitude-corrected aspect ratio, roof pitch and source immutability.
- Added portrait/two-page ordinary roof assertions, prominent actual vector path assertions, page text-bound checks, explicit distant-building inset labelling, disabled marketing, long pricing row pagination and 48-vertex continuation retaining the closing edge.
- Existing invalid/missing geometry, repeated adjacent/non-adjacent vertices, tiny legitimate edges, unchanged saved/reopened snapshot and no fabricated roof facets pass.
- Actual download wrapper in browser DOM emulation: single-flight double click, frozen customer/pricing/geometry, expired session rejection, unsaved-outline blocking, QA validation only and no provider paths pass.
- Actual customer report produced through the existing DOM/Leaflet manual-roof regression still passes original Single/Expanded PDF checks and QA vector export.
- Real jsPDF 2.5.1 bytes, embedded existing DejaVu font, rendered with Poppler. All six final example pages visually reviewed against the mockup's hierarchy and layout; no clipping or overflow observed.
- All three generated examples are **two portrait Letter pages**. The real customer report includes six approved benefit cards and page-two pricing. Two-point linear details use a compact view rather than a mostly empty full-size card.
- Independent Python Decimal server pricing accepted every example payload; independent server geodesic lengths matched all **26 closed-boundary dimensions** in extracted PDF text. Each final total matched source data. Area/pitch quantities also covered by independent geometry regression.

| QA example | Pages | Total CAD | GST | PST |
| --- | ---: | ---: | ---: | ---: |
| Actual DOM/Leaflet Alberta customer report | 2 | 416.34 | 19.83 | 0.00 |
| L-shaped roof + detached garage | 2 | 3,170.10 | 142.80 | 171.36 |
| Two service areas + linear measurement, seasonal | 2 | 1,618.43 | 72.90 | 87.48 |

The last two are synthetic 5%/6% tax examples, not Alberta tax examples. QA properties and prices are illustrative and must not be sent as real customer quotes.

Reproduce actual PDFs by setting `VECTOR_QA_JSPDF` to the jsPDF UMD file and `VECTOR_QA_OUTPUT` to a scratch output directory, then running `node scripts/test_vector_pdf.cjs --examples` and `node scripts/test_vector_full_report.cjs`. Standard regression commands remain in `.github/workflows/validate-landscaping-recovery.yml`.

## Remaining limitations

No authenticated live QA browser session, physical device, printer or production verification was performed. Browser work is DOM/Leaflet emulation; PDF rendering is real. PostgreSQL-specific concurrency is outside this presentation change and not rerun locally. Complex jobs and unusually long custom wording can legitimately exceed two pages. The existing embedded font's unsupported-character rejection remains. The brochure is a visual target, not a claim that decorative mockup structures exist in customer geometry. Imagery/tracing licensing remains unresolved and this contingency layout does not resolve it. Main and production must remain untouched.
