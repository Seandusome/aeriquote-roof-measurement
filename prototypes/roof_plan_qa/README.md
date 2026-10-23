# Isolated fictional roof-plan prototype — October 22, 2026

Starting recovery checkpoint: `3a4c39604e24096cb5f72735165faaa7bf6a78b8`.

**Fictional QA data only. No real property or contractor verification is claimed.** User explicitly authorized these fictional gable buildings. This directory is not imported or routed by AeriQuote. No existing application, PDF, measurement, subscription, pricing or saved-estimate code was changed. AutoMeasure is unchanged; AI Trace remains removed. No customer account, main or production was touched.

## Defined geometry

Local coordinates are feet; positive Y is north in the top-down view. Each building's Z=0 means its own eave reference, not ground elevation. Main house: 40 × 30 ft, two 6/12 planes, ridge from (0,15,7.5) to (40,15,7.5). Garage: 24 × 20 ft, two 4/12 planes, ridge at Y=10 and Z=10/3. Garage origin (55,8) explicitly defines relative placement. All vertices, ridge endpoints, pitches and simulated confirmation flags are stored in `fixture.json`; no architectural features are guessed. No walls, hips, valleys or dormers are added.

The PDF contains a common-scale plan view, independently enlarged detail views with horizontal dimensions, and orthographic roof-form illustrations projected directly from the same explicitly defined 3D vertices. Orthographic projection preserves the defined 3D shape, rather than depicting a perspective building invented from a flat footprint.

| Building | Each plane plan area | Each plane surface area | Building surface area | Pitch | Ridge |
| --- | ---: | ---: | ---: | --- | ---: |
| Main house | 600 ft² | 670.82039325 ft² | 1341.64078650 ft² | 6/12, 26.56505118° | 40 ft |
| Garage | 240 ft² | 252.98221281 ft² | 505.96442563 ft² | 4/12, 18.43494882° | 24 ft |

Total unrounded surface area: 1847.60521213 ft². At CAD 0.85/ft²: main CAD 1140.39; garage CAD 430.07; subtotal CAD 1570.46; GST 5% CAD 78.52; PST 6% CAD 94.23; total **CAD 1743.21**. Totals use unrounded areas; displayed quantities are rounded and the PDF explicitly says so. Tax rates are illustrative QA inputs.

## Contractor confirmation demonstration

The standalone HTML starts with the four fictional planes already drawn, all interactive confirmations empty. It demonstrates confirmation, not a new tracing engine:

1. Review/select each building's planes.
2. Select each plane's actual pitch. Wrong pitches block review because they cannot match this fixture's specified 3D vertices.
3. Confirm two explicit shared ridge lines.
4. Confirm all four intended planes/buildings are included, then review the fictional estimate.

Changing a confirmation hides the previous reviewed result. Reset clears everything. No API calls, local storage, account connection, credits, estimate saving or customer PDF download exist in the demo. The PDF is a separately generated prototype artifact using the identical validated fixture, not an installed AeriQuote PDF feature.

### Estimated extra actions

The demo itself needs four pitch selections, two ridge confirmations, one completeness checkbox and one Review click: eight interactions after geometry is supplied. These are counted interface controls, not a usability timing study.

Compared with today's correct per-plane tracing, the new structural work could be only **two ridge confirmations**, plus up to four building assignments if grouping is not already established: approximately **2–6 additional actions**. Pitch selection and overall scope review already exist.

Compared with tracing just one whole-roof outline per building, four separate rectangular planes require approximately eight extra corner placements, two extra pitch selections, two extra saves, two ridge confirmations, and zero to four building assignments: **14–18 additional actions**. Shared-edge snapping might reduce this, but is not implemented or assumed in the count. Whole-outline tracing cannot establish internal structure by itself.

## Targeted verification

- `python prototypes/roof_plan_qa/test_model.py`: three test groups pass, including independent 3D cross-product triangulation, Pythagorean slope lengths, shared ridge endpoints, exact plan coverage, input immutability, arbitrary-precision Decimal reference pricing, and agreement with the existing read-only server pricing function.
- Thirteen malformed/unconfirmed cases rejected: missing fictional label/wrong units, unconfirmed plane/ridge, wrong structural class, inconsistent vertex elevation/pitch/ridge location, missing plane, overlapping buildings, boolean vertex, nonfinite origin and duplicate plane ID.
- `NODE_PATH=... node prototypes/roof_plan_qa/test_demo.cjs`: DOM-emulated interaction test passes. Four planes/two ridges; initial blocking; missing/wrong pitch, missing ridge/completeness; stale review clearing; plane selection/focus; reset; no network resource dependencies.
- Five existing regression commands passed: `scripts/test_vector_pdf.cjs`, `scripts/test_vector_download.cjs`, `scripts/test_vector_full_report.cjs`, `scripts/test_geometry_integrity.py`, `scripts/test_server_pricing.py`. Includes original aerial Single/Expanded regression paths, six-industry vector coverage, actual save/reopen API checks in isolated storage, and 70 existing pricing fixtures.
- Actual ReportLab PDF generated and both pages rendered at 1700-pixel height with Poppler. Both pages and side-by-side composite visually inspected against the approved mockup's hierarchy, branding and page use. Exactly two Letter pages; all required dimensions, pitches, areas, amounts/taxes, and fictional notices verified in extracted text. Only branding bitmap resources; roof drawings are vector paths. No provider imagery.

## Reproduce locally

From repository root, with ReportLab available:

```
python prototypes/roof_plan_qa/render.py /absolute/scratch/output
python prototypes/roof_plan_qa/build_demo.py /absolute/scratch/output
python prototypes/roof_plan_qa/test_model.py
NODE_PATH=/path/to/node_modules node prototypes/roof_plan_qa/test_demo.cjs
```

Open `Contractor_Confirmation_Demo.html` locally. No server or login is required. The code reads existing licensed font/logo assets without modifying them.

## Practical result and limits

**Practical for explicitly defined simple gables:** verified planes can produce recognizable roof plans and derived roof-form illustrations with correct quantities. The confirmation interaction is compact. This does not prove that contractors can trace real roofs quickly or accurately; the drawing steps, touch interaction, snapping, arbitrary geometry, unequal-pitch/off-centre ridges, complex roof junctions, hidden sections, server persistence and professional contractor usability remain unverified/unimplemented. No physical-device or authenticated live-browser testing was performed. The UI test is DOM emulation; PDF generation and rendering are actual.

Keep this prototype isolated. Any real-property version still needs reliable evidence, confirmed slope directions/plane boundaries, robust topology and completeness checks, revision invalidation and licensing review. Do not connect it to customer workflows without further explicit approval.
