# AI tracing retired — October 12, 2026

The owner ended the pilot after live tests failed to save time or reliably outline multiple lawn sections. AI tracing controls, client requests, backend endpoints, provider modules and segmentation dependencies are removed.

Manual multi-area and linear measurements, wide aerial imagery, saved estimates, pricing and PDF behavior remain. Existing saved polygons (including those marked ai-assisted) remain normal editable measurements. No database records are deleted.

Render must deploy the recovery branch commit to apply this removal. FAL_KEY and OPENAI_API_KEY are no longer used by measurement; removing those environment variables is optional. Paid provider credits remain with their providers. The historical audit is retained for reference.

Validation: shipped JavaScript syntax; rendered DOM and Leaflet manual area/linear controls across surface industries; wide aerial requests; pricing and estimate output; PDF vector cleanup.
