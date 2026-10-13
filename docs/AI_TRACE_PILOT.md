# Shared surface tracing pilot — SAM 3

Work stays on `landscaping-multi-area-recovery-oct11`. Do not deploy to main.

## Configure the commercial test service

1. Create a fal API key and put it in Render as the secret environment variable `FAL_KEY`.
2. The default tracing provider is now `fal`, using `fal-ai/sam-3/image`. Optional explicit setting: `AERIQUOTE_AI_TRACE_PROVIDER=fal`.
3. Deploy the recovery branch with `gunicorn app:app --workers 1 --threads 4 --timeout 90`.
4. Load the property, choose AI TRACE, select Lawn or Paved Surface if needed, and click once inside the section on the aerial. The click starts the request automatically. No job box or manual diagonal is needed.
5. Compare the draft against the exact source image; Review & Edit each section before Finish & Save Area.

The same integration serves Landscaping, Commercial, Paving & Sealcoating, Pressure Washing and Snow Removal. Existing roof auto-measurement remains separate.

## What changed

SAM 3 returns segmentation masks. AeriQuote converts actual mask pixel edges into geographic outlines instead of asking a language model to generate coordinates. Only a complete detected region containing the selected point is proposed. Other disconnected regions are ignored. To include another grass or paved section, save the reviewed outline and select AI TRACE again. Narrow strips preserve pixel-cell area. Mask output resolution is mapped to the original 640×640 source image. The source image is centered on the selected point at zoom 18. The provider receives a foreground point prompt at the corresponding source pixel (320, 320).

Masks are requested with `apply_mask=false`, `sync_mode=true` and multiple-mask output. Conversion rejects cropped regions, masks with internal holes, ambiguous touching edges, low-confidence results and shapes that cannot be simplified to 40 corners with at least 97% mask overlap and no more than 2% area deviation. At most six sections are proposed; omitted sections generate a visible warning. These are conversion checks, not a guarantee that the model selected the correct grass or pavement.

The server requires a valid selected point and includes it in the cache key. Returned components must contain that point after mask resolution scaling. Neighbouring sections are not offered. Multiple materially different masks containing the point are rejected as ambiguous. A human must verify the actual surface boundary; connected pavement may still join a road, and segmentation does not determine ownership or legal parcel lines. Drafts never enter pricing automatically. Existing measurements, estimates and PDFs use the same save path as before.

## Billing and failure behavior

fal billing is separate from OpenAI billing. This default never silently falls back to the prior OpenAI provider. An explicit legacy setting `AERIQUOTE_AI_TRACE_PROVIDER=openai` remains available for recovery/testing but is not the recommended tracing path.

The server sends image bytes rather than a Google URL containing its key. Only the server uses `FAL_KEY`. Binary masks can be returned inline; external mask downloads are limited to fal.media hosts and do not receive the key. Requests use bounded waits and disable fal retries. Identical successful traces reuse the session cache.

Published fal SAM 3 image price checked October 12, 2026: US$0.005/request. Google image requests are additional. No fal account or key is available in development, so no paid live inference has been performed.

## Checks and remaining validation

- `python scripts/test_sam_trace.py`: actual PNG mask decoding and vectorization, three separated grass sections, thin strips, exclusions, cropping, duplicates, resolution conversion, provider payload/errors, missing credentials, no OpenAI fallback, point-only selection, resolution-aware point matching, and rejection of missing or invalid selected points before a paid request.
- `python scripts/test_ai_trace.py`: existing provider/route isolation, cache and cleanup checks.
- `node scripts/test_ai_trace_controls.cjs`: button timeouts, visible errors, expired sessions, source comparison and unchanged saved areas. DOM controls test AI activation and automatic request from a single map click without adding manual area points.
- Existing landscaping rendering and DOM tests cover areas, linear measurement, aerial imagery, customer estimates and PDF capture.

These checks validate integration and conversion. Real SAM 3 grass/pavement accuracy still requires a live test with `FAL_KEY` on the user's property. Do not describe live accuracy as proven until that test passes.

Primary documentation:
- https://fal.ai/models/fal-ai/sam-3/image/api
- https://fal.ai/docs/documentation/model-apis/inference/synchronous
- https://fal.ai/models/fal-ai/sam-3/image
