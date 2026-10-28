# Repeated Area and Roofing touch editing — October 28, 2026

Base recovery checkpoint:2e94561140f1cc843c74582ad852f50eaa35e361. Sean supplied a physical-phone observation:Area first edit/save works,second edit moves the aerial instead of reliably adjusting the corner. No assumption that the preceding Linear-only fix covered polygons.

## Independently confirmed defects

1. Area correction left map.dragging enabled. In the actual second correction after Save,a touch adjacent to a corner panned the geographic map from[52,-106] to[51.99995936072346,-106.00009292364122]. The exact corner hit moved correctly in Chromium;the adjacent-finger failure and missing drag lock were independently reproduced. Do not claim Chromium exactly reproduced every aspect of Sean's physical-device touch hit. Red log:/tmp/polygon-area-red.log.
2. Reviewed Roofing polygon markers still had autoPan:true,and the correction did not lock map dragging. After first Save and second Edit,a corner drag near the edge panned centre[51.99998743339703,-106.0000003874302] to[51.99998743339703,-106.00038528442384]. Red log:/tmp/polygon-roof-red.log. Tested independently with QA_POLYGON_PROBE=roof to avoid stopping at the Area failure.

## Narrow fix

Shared drag-state guard now explicitly recognizes each editor:Linear correction,Area correction,reviewed roof outline,and QA-only manual roof section editing. Polygon correction adds its own polygon-correcting CSS touch-action:none,not an assumption about the Linear class. Preserve the prior map-drag enabled state;release only once all active corrections end. Keep Leaflet touchZoom unchanged. Disable reviewed-roof corner autoPan. New drawings retain existing behaviour;no new tools.

Invoke synchronization at Area UI updates,roof workspace/review updates,and manual section edit entry. Save/Cancel paths already use these refreshes. Reset clears the stale Area correction buffer before changing properties,preventing a new interaction lock or Cancel from retaining an old property's edit context. No stored measurements are rewritten. Existing coordinate,area,distance,pitch,pricing,tax,imagery/API and PDF code is unchanged. No account/credit/schema changes. AutoMeasure and QA-only features preserved;AI Trace remains removed.

## Actual testing and evidence

Local Chromium141 mobile/touch emulation at320,390,768px,using trusted Input.dispatchTouchEvent for finger motion and real touch taps for UI controls. Disposable loopback SQLite accounts,fictional imagery only. No deployed/customer credentials or data. Reproduce:NODE_PATH=<installed browser test deps> python scripts/run_linear_touch_qa.py. The expanded test remains scripts/test_linear_touch_browser.cjs;the name does not imply polygons reuse the Linear lifecycle.

Area:enter correction,drag corner,Save,reopen correction,drag again;confirm centre and aerial viewport remain stationary during finger movement. Adjacent background touch cannot pan or change coordinates. Third edit/Cancel preserves exact saved points;Save/Cancel restore map dragging. Save an actual fictional estimate,reopen its stored version/measurement workspace,and touch-edit/cancel the Area again while retaining the saved polygon.

Roof outline:three review cycles with two real verified-pitch saves followed by Cancel,including near-edge corner motion on the second cycle. Exact saved roof survives Cancel. Save/reopen its actual fictional estimate,restore editing,touch a reviewed corner and cancel. Separately exercise the QA manual roof-section editor with two saves and third Cancel;one plane remains,confirmed pitch preserved. Background map panning resumes outside correction. Prior-disabled map state and invalid-Save lock retention remain covered by existing tests. Linear repeated saves,Cancel,reopened editing,independent saved-distance checks and two-finger background pinch remain in the same run.

The test checks geographic centre after dragging and aerial viewport position during the gesture (<1px rendering tolerance). Release-time instruction/status text can reflow the surrounding page;this is separated from map movement during the finger gesture. Fixture setup seeds known polygons;actual corner changes come from Leaflet receiving browser-trusted touch/pointer input,not marker.fire or fake dragend. Saved/reopened polygons are compared to their stored snapshots. No pricing or geometry is changed by entering/canceling correction.

Six-industry DOM regressions explicitly check repeated Area locks and cleanup,alongside existing Linear state restoration,invalid geometry and analytical area/pricing checks. Full regression suite72/72 passed. Python source compilation/whitespace checks remain clean. Final successful touch run:/tmp/polygon-touch-final.log;committed results:docs/qa/polygon-touch-2026-10-28.json. GitHub checks/PostgreSQL/Render must be confirmed at final recovery tip before completion.

## Limits and handoff

No agent physical iOS/Android verification and no authenticated live-provider geometry/PDF test in this batch. Sean's report is the physical-device evidence;reload the final test deployment and retest both first and second adjustments on his phone. Roof-outline tests use fictional uniformly pitched QA geometry,not real roof ground truth. Manual roof sections are still QA-only. No main,production,real customer account or saved record changed. Final GitHub checkpoint and exact deployment status are supplied in the completion response. Stop after this batch.
