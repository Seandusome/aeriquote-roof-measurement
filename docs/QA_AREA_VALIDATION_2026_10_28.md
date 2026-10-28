# Area correction — accidental vertex insertion and self-intersection, October 28

Base:9bf10b0fdf06ce432381251d3dfc67da072034b4,verified recovery HEAD before changes. Work exclusively on landscaping-multi-area-recovery-oct11. No production or real customer account touched.

## Physical evidence and limits

Sean supplied two actual iPhone screenshots (IMG_7232(1).png,IMG_7233(1).png). They were read locally after attachment arrival,not copied into the repository. The first shows Save Area Changes disabled,an explicit crossing warning,and a7,947ft² draft. The second shows saved-in-job Area1 at16,466ft² and Area2 at16,240ft²,total32,706ft²,at$0.10/ft². Closely clustered central purple corners/overlaid labels obscure exact edge connectivity. A screenshot does NOT supply the ordered latitude/longitude list,so the exact crossing pair,vertex insertion history,and cause of this specific phone draft remain unverified. No saved customer/job data was fetched to investigate it.

Current visual feedback is the outlined draft plus generic crossing warning;there is no edge-pair-specific highlight. The screenshots demonstrate that label overlap makes it hard to locate the crossing. No speculative geometry repair,label redesign or new highlight feature was added in this narrow fix.

## Confirmed interaction defect and exact reproduction

Edit Area left its map click handler in point-placement mode. A real browser-trusted touch tap near an existing boundary,missing its corner handle,appended a NEW last vertex rather than adjusting an existing vertex. A four-corner fixture became five corners and produced the exact displayed self-intersection warning. Red:/tmp/area-validation-red.log. The validator was correctly rejecting this deliberately reproduced crossing;no evidence justified weakening it.

QA-only manual-roof section editing had the same background-tap insertion defect:four corners became five (/tmp/area-validation-roof-red.log). Reviewed roof outlines already reject new tap points through addTracePoint;that working guard remains unchanged.

Fix:ignore background point-placement requests while an Area correction snapshot is active,with guidance to drag an existing corner or Cancel. Ignore map taps while manualRoofEditIndex identifies an active manual roof-section correction. Preserve programmatic loading of saved roof vertices and normal tap placement for NEW areas/roofs. No vertex deletion,reordering,clamping,snapping or coordinate correction. Existing invalid drafts are not automatically repaired. Validation,area/length/pitch formulas,pricing,taxes,imagery/API requests,PDFs,accounts and credits are unchanged. Linear and polygon drag/native-touch locks from prior checkpoints remain intact. AI Trace remains removed.

## Verification

New scripts/test_area_correction_touch.cjs reuses only the disposable setup of the existing touch harness. Run NODE_PATH=<browser dependencies> python scripts/run_linear_touch_qa.py scripts/test_area_correction_touch.cjs. Runner accepts only the two approved loopback touch scripts. Local Chromium141 mobile/touch emulation at320,390,768px with CDP trusted touch motion and native browser touch taps;fictional imagery,temporary SQLite accounts only. Not physical-device testing.

At every width:accidental background taps preserve four existing vertices and their order. Repeatedly edit Area1 and Area2 in alternation;drag one corner into a genuinely crossing draft;independently verify nonadjacent segment intersection with a separate orientation test. Only the dragged corner changes,the other vertices retain their order,and map centre remains fixed. Invalid Save stays disabled;neither stored area is overwritten. Cancel restores the exact original points,square footage,rate/name and full saved-area list. Make a legitimate small corner adjustment and explicitly Save;the other area's complete data stays unchanged. Repeat both areas twice. No automatic point deletion.

QA manual roof tap count remains4→4. Reviewed roof background taps preserve corner order;an intentionally crossed touch adjustment remains unsaveable even after a valid pitch/boundary confirmation is supplied. Cancel restores the exact original roof. Broader scripts/test_linear_touch_browser.cjs repeated Linear/Area/reviewed-roof/manual-roof Save/Cancel and saved-estimate reopening also passed all320/390/768px widths. Actual output:/tmp/area-validation-final.log,/tmp/area-validation-polygons.log;machine results:docs/qa/area-validation-touch-2026-10-28.json.

Full72-command post-fix regression passed,including six-industry geometry/pricing/account/PDF guards. Existing six-industry measurement-edge regression now also checks that map clicks cannot append vertices during Area correction. Git diff whitespace check clean. Final GitHub/PostgreSQL checks and Render status must be verified at the published recovery tip before completion;completion response supplies its checkpoint.

## Handoff and remaining limits

Actual iPhone Safari/WebKit behaviour after this fix remains unverified by the agent. Exact user's draft geometry cannot be reconstructed from screenshots alone. Individual crossing edges remain unhighlighted;generic warning and outline are the current feedback. Do not silently enable Save for a crossed outline or repair old invalid drafts. For an existing invalid correction,Cancel restores the prior in-job measurement. “Saved in this job” is not necessarily a server-saved estimate:do NOT instruct a refresh until the user has canceled the invalid correction and saved their completed estimate,or unsaved work could be lost. No autosave added.

All application changes committed to the recovery branch;main/production/customer accounts,imagery providers,AutoMeasure,approved PDFs and pricing preserved. Stop after deployment/report;physical-phone recheck follows the report,not a claimed test result.
