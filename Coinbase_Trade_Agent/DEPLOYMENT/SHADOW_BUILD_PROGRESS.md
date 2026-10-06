# Native execution ledger — plan: docs/superpowers/plans/2026-10-05-spot-shadow-engine.md

User approved design, written design and Native execution. Latest steering: seek the shortest cost-adjusted profitable windows, then neighboring larger windows.
Ruling: Work in place and preserve this ledger because no Git repository exists; Git-only workspace/commit helpers cannot apply. Cost if wrong: no Git rollback; existing live files will not be edited.
Ruling: Extend horizon ladder to 1/2/3/5/10/15/20/30/45/60/90/120/180/240 minutes under user steering. Counterfactual horizons are diagnostic, not independent trades. Cost if wrong: multiple comparison bias; explicitly require held-out and forward evidence.
Pre-flight: market snapshot types -> detectors -> simulator -> ledger -> learning/runner; shared types consistent. Persist exact candidate/rules/fee snapshots.
Baseline: python unittest discovery has no executable tests before this implementation.
Task 1: complete — four adapter tests observed RED then GREEN; closed-bar/gap/price/allowlist checks pass. No live network validation yet.
Task 2: complete — detector positive/negative, six-decision, insufficient context and closed-feature tests RED then GREEN; suite 7/7. Strategy rule hash will additionally include implementation source in runner.
Task 3: complete — duplicate scans, restart, rollback and paper-path tests RED then GREEN; suite 10/10.
Task 4: initial implementation verified — fee math, partial depth, stop-first/gap and risk gates RED then GREEN; suite 15/15. More lifecycle/restart checks will be added with runner integration.
Ruling: Historical candle stop fills are explicitly uncertain modeled exits and use adverse observed/stop price plus buffer, rather than claiming historical executable liquidity. Cost if wrong: pessimistic results; excludes uncertain fills from consistency promotion.
Task 5: core reporting RED/GREEN 4/4; history tests exposed incorrect fixture expectation: 180/240/300 form a valid contiguous 2-minute window after the gap. Corrected expected start to 180, not 240. This is a fixture correction, not ignoring a missing bar.
Task 5: implemented historical window research and chronological strategy detection replay; source data downloading/cached. Outcome uniqueness, overlapping-forward filtering, cost drag, sparse confidence and heldout screening tests pass.
Task 6: implemented scanner/lock/start-stop/status/ledger recovery; first public scan returned 54 decisions and seven valid markets; DOGE/HYPE 1m gaps rejected. Suite 30/30 passes. Background launch pending final review.
Ruling: Minute gaps in DOGE/HYPE block live-paper entry but historical diagnostic screens skip affected intervals and disclose sample coverage. Cost if wrong: fewer signals, no invented executable prices.
Ruling: Native final fresh reviewer is required by executing-plans skill; delegate only this review, not implementation.
Final review: independent reviewer found eight Important correctness issues; all reproduced or pinned to behavioral checks, repaired in one pass. Suite 41/41 passes.
Final fixed: candle overlap and pending stop obligation; transaction-local portfolio state; validate quotes before exits/markouts/equity; exact trailing-candle freshness; refresh product metadata each entry scan; separate rule-version cohorts and save complete source/rules; explicit soft-risk states and complete threshold schema; persist rejected evidence and clear per-market raw buffers in finally.
Final minor (deferred): full regime/session/score attribution, aggregated MAE/MFE/execution/compliance summaries and benchmark comparisons remain unavailable; report labels them unavailable. Cost: learning report is preliminary, not validation-complete.
Final minor (deferred): detector fixtures cover computed-feature gates and basic context/closed-bar behavior, not complete candle-to-candidate fixtures for every family. Cost: research detector correctness is not fully established; no live promotion.
Final minor (deferred): slow network scans can miss exact short-horizon quote tolerances; coverage is retained as unavailable rather than fabricated. Cost: fewer usable 1–3-minute observations.
Final declined-to-judge rulings: no live profitability/strategy approval inferred; public API verified separately through real read-only scans; historical replay completed separately with errors={} and 827 genuine detected research triggers. Cost: no statistical validation is claimed.
Tasks implemented; Task 5 reporting is explicitly partial.
Operational verification complete: hidden paper runner PID 47940; two background scans completed at 2026-10-06T03:23:47Z and 03:25:22Z, each 54 decisions / seven valid markets / DOGE and HYPE missing-1m rejections. Intermediate review succeeded. stderr empty. No active or closed paper positions at verification.
Fresh full suite: 41 tests pass; compileall passes. Independent review fixes verified, no second review dispatched per executing-plans workflow.
Historical research complete: nine markets x fourteen horizons =126 cost-screen cells; all final-third mean net returns negative. All six research families produced827 unique historical triggers; no provisional consistent window. Chronological markouts omit historical spreads/depth/protective-exit simulation and are explicitly nonexecutable.
Ruling: no Git finish/merge menu or ledger cleanup applies because this workspace is not a repository; preserve source and evidence in place. Cost if wrong: user must add version control/backup separately.
