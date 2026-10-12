# Shared AI tracing pilot

Recovery baseline before this feature: `906826ef63efa5df8b3bb31f8cd49289098d14c6`.
Work stays on `landscaping-multi-area-recovery-oct11`; do not deploy this pilot to production/main.

The same AI Trace panel is available in Landscaping, Commercial, Paving & Sealcoating,
Pressure Washing and Snow Removal. It suggests lawn/turf or asphalt/concrete outlines.
Roofing retains its existing Google roof measurement and pitch workflow.

## Enable on the commercial test service

1. Add `OPENAI_API_KEY` as a secret environment variable in Render. Never put it in GitHub or chat.
2. Optional: `AERIQUOTE_AI_TRACE_MODEL` changes the model. The default is `gpt-4.1-2025-04-14`.
3. Deploy this recovery commit. API billing belongs to the OpenAI account providing the key.
4. Load a property, center the target surface, choose Lawn or Paved Surface and request suggestions.
5. Select Review & Edit, correct the corners, then Finish & Save Area. Drafts never enter the quote automatically.

This is an AI-assisted pilot, not a validated segmentation or surveying product. Live tracing
accuracy has not been tested: the development environment has no API key. Vision models can
misplace corners and miss exclusions. Review actual aerial examples before release. Beds,
occluded edges and ambiguous boundaries can still require manual measurement.

## Costs

GPT-4.1 pricing checked October 12, 2026: USD $2 per million input tokens and $8 per million
output tokens. Illustrative usage of 2,000 input and 1,000 output tokens costs $0.012 per request.
This is an assumption, not measured usage. Google Static Maps requests are billed separately.
The server logs actual token usage without addresses or API keys. Repeating the identical
request within the same property session reuses the last result rather than charging again.

Sources:
- https://developers.openai.com/api/docs/models/gpt-4.1
- https://developers.openai.com/api/docs/guides/images-vision

## Validation

`python scripts/test_ai_trace.py` tests structured request/response parsing, projection,
invalid outlines, account isolation, missing-key behavior, caching and cleanup after failure.
The rendered-control tests exercise review/save across all five industries and stale responses.
All provider calls in tests are mocked; passing tests does not prove real image tracing quality.
