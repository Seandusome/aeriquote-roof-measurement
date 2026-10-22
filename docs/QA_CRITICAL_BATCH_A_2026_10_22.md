# Approved critical fixes — Batch A, October 22, 2026

Starting GitHub checkpoint: 5725abe. Recovery branch only; no main, production or customer-account changes.

## Confirmed defects and fixes

The dropped-pin parser extracted the first two numbers from arbitrary strings, interpreting DMS/exponents as unrelated decimal coordinates. It now accepts exactly two decimal degrees with either no hemisphere letters or both correctly placed N/S and E/W letters. Extra values, arbitrary text, exponent/DMS syntax, contradictory signed hemisphere forms, nonfinite values and coordinates outside the map's Web Mercator range are rejected. Accepted dropped-pin values require explicit latitude/longitude order confirmation; valid reversed pairs cannot be distinguished mathematically without user intent. Existing coordinate URL input remains supported through the strict parser.

Replacement property loading previously cleared unsaved measurements and customer details before image decoding. Required aerials/masks now prepare on a separate offscreen Leaflet map, including successful ImageOverlay decoding. Only confirmed imagery is installed into the live workspace. Failed property/API/image/acceptance requests retain the prior token, geometry, pricing and customer fields. Address changes during staging are rejected before acceptance. A declined secondary-address match preserves the workspace and asks for the alternative's city/province rather than recursively awaiting the same in-flight promise.

New browser lookups use account-scoped prepared receipts. Preparation checks allowance under the owner lock without spending it; /property/accept spends once after browser imagery readiness. Repeated preparation and acceptance reuse the original operation and token. Mismatched tokens/contents/businesses, expired preparation and expired authentication fail safely. Legacy API callers retain their existing transactional lookup behavior. Provider API requests may still cost money even when preparation is not accepted; subscription credits are separate.

## Verification

Targeted scripts: test_property_loading.cjs and test_property_acceptance.py. They cover strict coordinate formats, rejected malformed inputs, rural-coordinate preparation, image/acceptance failures, stable retry IDs, workspace retention, successful swap, refresh/replay, eight simultaneous accepts, one credit, business isolation, expired login and invalid map latitudes. Existing saved editing, geometry, pricing, PDFs, imagery recovery and Batch 1–4 failure tests are included in the complete recovery workflow.

No claim of physical-device verification. Live authenticated Google imagery/PDF workflows require QA login and remain explicitly pending unless follow-up evidence is added. Forced-refresh/crash autosave is not introduced; the existing unsaved-work warning and saved-estimate reopening remain intact. Pending operations survive response loss in the same page; reload uses saved estimates and server receipt replay when the operation identifier is retained by the caller.

## Publishing

Publish complete Git tree, verify local/remote tree equality and wait for GitHub checks and Render LIVE. This document is committed with the Batch A fix; the resulting checkpoint is reported in the conversation. Batch B must start only after Batch A verification and checkpoint.
