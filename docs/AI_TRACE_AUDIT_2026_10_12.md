# AI tracing review — October 12, 2026

## Product assessment

The current pilot has not demonstrated a time saving over manual measurement on the user’s property. One accepted area is not evidence that it handles the job. Manual area/linear tools remain the reliable primary workflow; tracing remains a recovery-branch experiment and must not be released on main as validated automatic measurement.

The useful next test is bounded: trace the three intended grass sections without losing drafts, forced waits, manual setup, repeated requests, or incorrect neighboring areas; review and save them with the controls at the aerial. Compare actual completion time with manual tracing. Stop iterative paid tests if it still misses sections or takes longer.

## Verified code defects and corrections

1. AeriQuote imposed a 15-second delay between completed requests. Removed it while retaining a one-request-at-a-time guard and a 20-starts/minute property burst cap. A route test now makes consecutive requests for different sections without an artificial wait.
2. Any transparent pixel made the decoder use the alpha channel as its mask. An opaque black background could become foreground. Grayscale mask intensity is now combined with alpha, so transparent padding does not turn the rest of the image into selected area. A real PNG regression fixture reproduces this defect.
3. Saved AI sections were not checked when selecting a surface again. They are now recognized before a new provider call. A DOM test confirms no new request for a saved section.
4. A hidden 2% source-image margin rejected complete masks near an edge. Click tracing now permits the full source image, while still rejecting masks touching the actual image boundary.
5. AI activation always scrolled the aerial into view, even when it was visible. It now scrolls only if the aerial is outside the viewport.
6. Resuming an earlier manual area restored both area and linear snapshots. It could overwrite newer saved linear work. Resume now restores only the channel that was paused and preserves the other channel’s current data/rate. Resuming an old linear drawing is blocked if it would overwrite a newer saved linear measurement.

## Remaining limitations

- Internal gaps/holes are rejected because existing editable area polygons have no hole representation. Filling them would overstate measured area.
- Cropped surfaces, materially different overlapping masks, missing-click matches and insufficient confidence still result in no outline.
- Shape overlap and area thresholds verify polygon conversion against the returned mask. They do not verify whether the mask actually represents the correct lawn or paving.
- A valid provider response, passing mocks, or a precisely projected polygon does not prove semantic measurement accuracy.
- The development workspace has no live fal credentials. No claim is made that the provider now detects the second or third grass section correctly.

## Validation

Python SAM/route tests, actual DOM controls, inline JavaScript parsing, multi-area/linear pricing, aerial coverage, customer estimate rendering and PDF capture checks pass. Tests cover sequential requests, mask transparency, edge regions, draft accumulation, saved-section duplicate clicks and preservation of newer linear work when resuming an older manual drawing.

Changes are limited to landscaping-multi-area-recovery-oct11. Main is untouched.
