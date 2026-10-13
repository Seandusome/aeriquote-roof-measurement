# Shared surface tracing pilot — SAM 3

Work stays on `landscaping-multi-area-recovery-oct11`. Do not deploy to main.

## Configure the commercial test service

1. Create a fal API key and put it in Render as the secret environment variable `FAL_KEY`.
2. The default tracing provider is now `fal`, using `fal-ai/sam-3/image`. Optional explicit setting: `AERIQUOTE_AI_TRACE_PROVIDER=fal`.
3. Deploy the recovery branch with `gunicorn app:app --workers 1 --threads 4 --timeout 90`.
4. Load the property, choose SET JOB BOUNDARY, and click two opposite corners around only the intended job. Choose Lawn or Paved Surface, then request outlines once.
5. Compare the draft against the exact source image; Review & Edit each section before Finish & Save Area.

The same integration serves Landscaping, Commercial, Paving & Sealcoating, Pressure Washing and Snow Removal. Existing roof auto-measurement remains separate.

## What changed

SAM 3 returns segmentation masks. AeriQuote converts actual mask pixel edges into geographic outlines instead of asking a language model to generate coordinates. Disconnected regions become separate draft sections. Narrow strips preserve pixel-cell area. Mask output resolution is mapped to the original 640×640 source image. Tracing starts at zoom 18 and reduces zoom only when needed to fit the selected job box. Source coordinates always use the actual requested image zoom.

Masks are requested with `apply_mask=false`, `sync_mode=true` and multiple-mask output. Conversion rejects cropped regions, masks with internal holes, ambiguous touching edges, low-confidence results and shapes that cannot be simplified to 40 corners with at least 97% mask overlap and no more than 2% area deviation. At most six sections are proposed; omitted sections generate a visible warning. These are conversion checks, not a guarantee that the model selected the correct grass or pavement.

The server requires the selected job box, includes it in the cache key, and sends it as a model box prompt. Entire detected sections outside the box or crossing its edge are omitted; they are never clipped into fabricated measurement boundaries. A human must verify service scope. The job box is a user-selected tracing limit, not a surveyed parcel boundary. Segmentation does not determine property ownership or legal parcel lines. The box must exclude neighbouring service areas; regions outside it are rejected. Drafts never enter pricing automatically. Existing measurements, estimates and PDFs use the same save path as before.

## Billing and failure behavior

fal billing is separate from OpenAI billing. This default never silently falls back to the prior OpenAI provider. An explicit legacy setting `AERIQUOTE_AI_TRACE_PROVIDER=openai` remains available for recovery/testing but is not the recommended tracing path.

The server sends image bytes rather than a Google URL containing its key. Only the server uses `FAL_KEY`. Binary masks can be returned inline; external mask downloads are limited to fal.media hosts and do not receive the key. Requests use bounded waits and disable fal retries. Identical successful traces reuse the session cache.

Published fal SAM 3 image price checked October 12, 2026: US$0.005/request. Google image requests are additional. No fal account or key is available in development, so no paid live inference has been performed.

## Checks and remaining validation

- `python scripts/test_sam_trace.py`: actual PNG mask decoding and vectorization, three separated grass sections, thin strips, exclusions, cropping, duplicates, resolution conversion, provider payload/errors, missing credentials, no OpenAI fallback, and exclusion of neighbouring and boundary-crossing regions.
- `python scripts/test_ai_trace.py`: existing provider/route isolation, cache and cleanup checks.
- `node scripts/test_ai_trace_controls.cjs`: button timeouts, visible errors, expired sessions, source comparison and unchanged saved areas.
- Existing landscaping rendering and DOM tests cover areas, linear measurement, aerial imagery, customer estimates and PDF capture.

These checks validate integration and conversion. Real SAM 3 grass/pavement accuracy still requires a live test with `FAL_KEY` on the user's property. Do not describe live accuracy as proven until that test passes.

Primary documentation:
- https://fal.ai/models/fal-ai/sam-3/image/api
- https://fal.ai/docs/documentation/model-apis/inference/synchronous
- https://fal.ai/models/fal-ai/sam-3/image
