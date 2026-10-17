# Roof pitch selection and replacement Save UI - October 17, 2026

This supersedes earlier docs requiring a separate pitch-confirmation checkbox.

Sean's screenshot 813958986.jpg showed the replacement Save button alongside pitch and trace controls, with an unchecked pitch-confirmation checkbox below. Save was correctly blocked by that checkbox, but feedback was remote and unclear. Sean explicitly requested removing the extra checkbox.

## Result
- Manual replacement starts with an explicit Select roof pitch placeholder. Selecting a valid pitch IS the pitch confirmation; there is no separate pitch-confirmation checkbox.
- Missing/custom empty/invalid pitch cannot silently become a zero-degree roof or reuse the old 5/12 default.
- Custom degrees now have an actual visible number input and inline validation.
- Detected-outline review also uses its verified UNIFORM pitch selection as confirmation, without an extra pitch checkbox. Full-boundary confirmation and explicit replacement of overlapping manual traces remain.
- Replacement pitch, instructions, local feedback and actions use a responsive grid. Confirmation/instructions occur before Save in DOM order; errors/readiness appear beside the controls.
- Save stays disabled until the trace and selected pitch are valid. A direct handler attempt still refuses invalid data.
- Replacement labels say Verified pitch for this roof / CLEAR THIS ROOF DRAWING and identify the target roof. These survive industry terminology passes.
- Successful actual DOM button-click save replaces only the intended roof and preserves the main roof.
- Valid Google AutoMeasure still supplies pitch automatically. Partial Google pitch data is not asserted to represent the full manually traced building.

## Verification
Python compilation and full real DOM/Leaflet controls regression passed, including new required selection, no extra pitch checkbox, inline feedback, DOM order, custom pitch rejection, and actual Save-button replacement. All earlier roof safety/source/cancel/restart/PDF regression checks passed locally without script errors.
Six-industry measurement edge-case tests also passed.
Direct live-browser visual/PDF checks remain blocked by the credential-protection runtime failure. Do not describe them as completed. Main/production untouched; AI Trace remains removed.
