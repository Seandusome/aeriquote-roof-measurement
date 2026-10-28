# Linear endpoint touch correction — October 28, 2026

Base:7bf0208326fd4a61487ffacbd6c94a6a867ac58a on landscaping-multi-area-recovery-oct11 only. Sean reported the defect on an actual touchscreen phone. Agent verification below uses local Chromium141 mobile/touch emulation, NOT physical hardware or the deployed customer database.

## Reproduction and narrow fix

A genuine Chromium touch drag at320px, starting on a saved Linear endpoint and ending near the map edge, reproduced map drift. Before correction:map dragging remained enabled, marker autoPan:true, centre[52,-106] moved to[52.00000064406087,-105.99893152713777]. The endpoint also moved. Trusted touchstart and pointerdown(pointerType:touch) were both observed. Failure evidence:/tmp/linear-touch-red.log. The regression fails on the unmodified base.

While linearCorrectionOriginal is active, temporarily disable map dragging and remember its previous enabled state. Restore that state on Save,Cancel,tool cancellation or property reset through the existing Linear UI state refresh. An invalid collapsed-line Save remains in edit mode with its lock. Set Linear marker autoPan:false so a near-edge endpoint cannot pan the aerial independently of the map drag handler. Leave Leaflet touchZoom unchanged. Previously disabled map dragging is never accidentally enabled.

No measurement/distance formula,credit accounting,imagery request/provider,Leaflet library version,pitch calculation,pricing or PDF-layout change. No new drawing tools or wording changes. Area and Roofing handlers remain untouched. AutoMeasure and QA-only options preserved; AI Trace remains removed.

## Touch evidence and checks

Run NODE_PATH=<installed browser dependencies> python scripts/run_linear_touch_qa.py using the repository Python dependencies and installed Playwright Chromium. The wrapper refuses an occupied fixture port,starts prelaunch_browser_server.py with a disposable SQLite database,and terminates it afterwards. The Node test aborts external hosts and supplies clearly fictional grid imagery. It uses Chrome DevTools Input.dispatchTouchEvent with hasTouch/mobile context,which generates browser-trusted touch and touch-pointer events. It does not use mouse-only drag,dispatchEvent,marker.fire or synthesized dragend to claim touch success. Fixture geometry is deliberately seeded; endpoint changes are produced by actual touch input through Leaflet.

At320,390,768px:near-edge endpoint moves while centre remains exactly[52,-106];saved distance independently agrees with haversine sum of final endpoints;Save retains new coordinates;edit reopening retains them;Cancel restores exact originals;one-finger map pan stays blocked during correction;two-finger background pinch zoom increases zoom;ordinary map dragging resumes afterwards. Existing intentionally disabled dragging stays disabled. Create/save/reopen a fictional estimate and restore its editing session;touch-edit and cancel its saved line successfully. Area corner touch dragging and Save still work after Linear;Roof reviewed-outline touch dragging works and Cancel preserves its original roof. No browser script errors.

Expected fixture results (different viewport-adapted fictional lines,not the same property measurement):320px134.15904065065203ft;390px174.9263450177292ft;768px383.3417585254802ft. See committed docs/qa/linear-touch-2026-10-28.json for exact successful run evidence. Scratch logs:/tmp/linear-touch-verified.log;initial failing run:/tmp/linear-touch-red.log. Screenshots and JSON are produced under/tmp/aq-linear-touch;all imagery fictional.

The existing six-industry test_measurement_edges.cjs now asserts map-pan locking,no marker auto-pan,invalid-Save lock retention,Save/Cancel restoration,prior disabled state and property-reset cleanup. It continues to exercise area validity,independent geometry,roof trace guards and combined pricing. No CI dependency or workflow redesign;the real-touch browser runner remains explicit,opt-in,like the existing local browser QA scripts.

Final post-fix full regression:72/72 command checks passed,zero failures. Six-industry measurement/editing,independent pricing,saved estimates and all existing PDF/account regressions remain green. Python runner compiles and git diff whitespace check passes. Final GitHub and PostgreSQL results must be confirmed at the published tip.

## Limits and resume

Physical iOS Safari/Android Chrome and real-provider aerials were not available to the agent. Sean's original report is the physical-device evidence;the fix still needs his phone recheck after reloading the test deployment. Two-finger pinch was verified on the background,not with a finger anchored on an endpoint. Releasing an endpoint outside the map/browser or OS-level gesture interruption is not claimed verified. Existing unsaved crash-recovery limits unchanged. No real accounts used. Never touch main,production or customer data. Final checkpoint and exact GitHub/Render result are supplied in completion response;verify branch tip before resuming.
