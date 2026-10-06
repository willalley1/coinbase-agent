# Coinbase spot shadow research engine — proposed design
Date: 2026-10-05 America/New_York
Status: written design and Native execution approved by user October 5, 2026. Initial paper runner implemented and launched; two background scans verified. Learning reports have documented remaining validation/attribution limitations. No live execution enabled.

## Objective and boundaries
Evaluate the six documented strategy families using fresh Coinbase spot data, collect prospective paper outcomes at 5, 15, 30 and 60 minutes, and identify positive net expectancy after actual fees and realistic execution assumptions.
Long-only, unleveraged paper entries. Bearish signals become avoid/exit observations; do not simulate naked spot shorts.
No live order tools, funding, transfers, paid data, live permission changes, or automatic strategy promotion.
Initial reviewed universe: BTC, ETH, SOL, XRP, DOGE, SUI, NEAR, HYPE, ZEC USD pairs. This is a sample, not a complete exchange scan.

## Proposed components
1. Read-only Coinbase adapter: products, closed candles, timestamped bid/ask, depth and fees. Save immutable raw observations; reject stale data, gaps and inconsistent timestamps.
2. Versioned research definitions: translate each qualitative strategy into deterministic eligibility, triggers, entry zone, stop, targets, expiry and failure conditions. Name research variants separately; never claim exact implementation of qualitative v1 without reviewed definitions.
3. Scan every five minutes on closed candles; use 1m data or timestamped quotes for execution/outcome measurement and 15m/1h/4h/1d context as required. Preserve missing data rather than forward-fill executable prices.
4. Paper lifecycle: candidate, qualified, submitted, filled/expired, active, closed, reconciled. Record no-trade decisions. Deduplicate strategy/product/bar signals and freeze all rules at entry.
5. Execution simulation: taker buys at ask and sells at bid, depth-aware slippage, actual maker/taker fees charged on each side. Maker orders require conservative queue/trade-through evidence, expire unfilled, and never infer a fill from a mere candle touch. If stop and target are both touched in one candle, use stop-first or mark ambiguous.
6. At each eligible signal, assign a primary holding policy in advance; retain 5/15/30/60-minute counterfactual markouts as correlated diagnostics. Do not count four outcomes as four independent trades. Protective stop/target wins over time cap; distinguish markout from executable trade return.
7. Swing Trend retains native multi-hour/day horizon. Its short horizon measurements are explicitly experimental markouts, not validated Swing Trend exits. Exhaustion Reversal remains research.
8. Learning reports: net expectancy, win rate, profit factor, drawdown, MAE/MFE, fee/slippage drag, regime/product/session attribution, no-trade/fill rates, sample confidence, and process compliance. No score-as-probability.
9. Separate all paper datasets from existing live trade/equity tables. Independent strategy cohorts are diagnostics, not a combined tradable portfolio. Add a synthetic portfolio layer with disclosed starting equity and project risk/correlation/loss limits before reporting portfolio performance.
10. Hypotheses and proposed parameter changes are append-only/versioned. Historical replay, held-out/walk-forward and forward shadow evidence stay separately labeled. Live rules and permissions remain unchanged.

## Alternatives
Recommended: local read-only paper runner with durable checkpoints; efficient repeated collection while machine is awake.
Chat-only periodic sessions: useful manual reviews, but gaps and no reliable continuous sampling.
Hosted always-on runner: better availability, but introduces deployment, credentials and hosting decisions; defer until local runner is verified.

## Persistence and reporting
An explicit start/stop/status control, single-instance lock, resumable checkpoints, bounded retries/backoff, disk-based ledger, and graceful recovery.
No recurring Codex automation tool is available in this session. Do not claim unattended recurring execution has been scheduled.
Notify on failures, meaningful new evidence or review gates; avoid unchanged scan spam.
Exchange-time UTC records with America/New_York user reports.

## Verification and promotion
Meaningful fixtures for no look-ahead, incomplete candles, gaps, fee math, duplicate signals, ambiguous bars, no-fill limits, restart recovery and risk gates.
Compare deterministic replay against hand-calculated examples. Run fault injections before extended collection.
Provisional assessment around 30 representative independent outcomes; stronger evidence preferably 100+ plus regime diversity. Use block-aware uncertainty and account for multiple strategy/product/horizon comparisons.
User design review -> written implementation plan review/method selection -> implementation and checks -> start repeated paper collection.
Promotion needs positive cost-adjusted out-of-sample/forward expectancy, acceptable drawdown, execution feasibility and no unresolved critical incidents. Autonomy and live deployment require separate explicit permission.

## Initial evidence
Account fee tier: Intro, maker 0.005 and taker 0.009 per side.
Exact fee-only long price hurdle: (1+entry_fee)/(1-exit_fee)-1.
Maker/maker: 1.005025%; maker/taker: 1.412714%; taker/taker: 1.816347%.
Observed sampled windows are overlapping, retrospective and not strategy backtests.
