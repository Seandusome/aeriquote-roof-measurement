# Simplified Roofing measurement workspace - October 17, 2026

Sean's direction: an experienced operator of 300+ roofs finds the interface overwhelming; a first-time user should be able to follow it without a course. Consolidate controls rather than adding more visible choices.

## Normal flow
Load property -> check roof measurement -> price -> estimate.
Roofing keeps AutoMeasure visible. Area/linear tools remain available inside one collapsed Area / linear tools section, which opens when those modes are selected and closes on return to AutoMeasure.
The other five industry toolbars retain their existing layout and tools.

## Corrections
- Each roof has ONE action: FIX ROOF for flagged coverage; EDIT ROOF otherwise.
- The action opens the selected roof's latest usable boundary in the existing editor, or starts a manual trace if no usable boundary exists.
- The selected row becomes Editing this roof, with no duplicate review/retrace buttons. Other roof actions are disabled while a trace is active.
- START OVER is the existing editor control. From detected-boundary review it switches to an empty manual replacement trace. Cancel and save preserve established measurement safety.
- The manual editor is beside the aerial only while editing (or during initial manual fallback). Saving/cancelling returns it to collapsed advanced tools.
- Advanced roof tools holds manual missing-roof tracing and display options. The redundant main-house confirmation prompt is hidden. The old destructive whole-main reset entry is hidden once roofs exist; targeted correction replaces it. Compatibility functions are retained.
- Active editor labels identify the selected roof; replacement warning copy directs the user to finish the active editor rather than click another Fix action.
- Existing calculation, rates, imagery, saved-estimate/customer report/PDF logic and mismatch safeguards are unchanged. This remains dealer correction with verified uniform pitch, NOT certified automatic whole-building/mixed-pitch measurement.

## Verification completed
Python compilation; full real DOM/Leaflet controls suite without script errors; six-industry analytical measurement edge cases; six-industry wording/estimate/switching tests.
New first-time-flow test verifies collapsed secondary/advanced tools; exactly one action per roof; actual Fix -> Start Over -> pitch -> Save button flow; only the second roof replaced; editor collapses after save; estimate readiness returns; industry switches restore original surface toolbars without duplicating nodes or changing measurements.
Existing PDF/saved-source/cleanup regression cases in the controls suite also passed locally.

## Still pending
Direct live-browser layout inspection and actual newly downloaded PDFs remain blocked by the native credential-protection runtime failure. Do not claim these checks passed or describe the layout as visually verified.
No main/production changes, no AI Trace restoration, no customer records modified, no profile saved, no external messages sent.
