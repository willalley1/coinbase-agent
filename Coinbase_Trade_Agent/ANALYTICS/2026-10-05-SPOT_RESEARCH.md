# Initial Coinbase spot research
Observation date: October 5, 2026, approximately 10:10–10:12 p.m. America/New_York.
Source: connected Coinbase read-only product, fee, candle and order-book tools.

## Completed
Retrieved 51 USD spot product records (not asserted to be the entire exchange catalog).
Reviewed nine markets in detail: BTC, ETH, SOL, XRP, DOGE, SUI, NEAR, HYPE and ZEC.
Collected 5m, 15m, 1h, 4h and 1d OHLCV plus order books. Closed 5m sample: 59 bars per market, approximately five hours.
Calculated 5/15/30/60-minute overlapping close-to-close historical returns. This is a fee feasibility screen, not a strategy backtest or prospective shadow trade.
Logged 54 strategy/product readiness reviews as NOT_EVALUATED because deterministic strategy implementations are absent.
Saved raw evidence separately from live trading files. No live orders, paid resources, funds movements, or permission changes.

## Fee hurdle
Connected account reported Intro: maker 0.50%, taker 0.90% each side.
Fee-only breakeven = (1+entry_fee)/(1-exit_fee)-1.
Maker/maker ~1.005%; maker/taker ~1.413%; taker/taker ~1.816%.
Spread, slippage and queue/fill uncertainty increase the required edge.

## Research ranking
NEAR: strongest observed short-horizon expansion and aligned 1h/4h price versus 20-bar mean. Maximum sampled gross gains: 5m 2.056%, 15m 3.634%, 30m 4.163%, 60m 4.669%. Some past windows exceeded taker fees. These moves already happened; do not chase.
ZEC: one sampled 60m window exceeded taker fees, maximum 2.044%. Intraday strength contrasted with price below the daily 20-bar mean; insufficient evidence of a fresh qualified entry.
BTC/ETH/SOL/XRP/DOGE/SUI/HYPE: zero sampled windows above the taker/taker hurdle. HYPE maximum 60m gain ~0.916%, below even the maker/maker hurdle.
Current execution decision: NO TRADE. No validated strategy trigger, entry/stop, score, independent expectancy or portfolio state has been established.

## Learning conclusions
Cost sensitivity is the first bottleneck. Shorter holding periods must prove an unusually strong edge or conservative executable maker fills.
Historical best returns do not establish predictive power; mean sampled returns after fees were negative even for NEAR. Overlapping windows are dependent.
Five hours is inadequate regime coverage. Do not treat the sample as evidence that future short-horizon trades cannot work.
Source strategy files use qualitative terms (e.g. meaningful confirmation, acceptable extension and volatility buffers), requiring explicit versioned research definitions before reproducible repeated strategy tests.
There is currently a documented learning framework, not a functioning learning engine. No learned model or parameter calibration was performed.

## Next actions
1. Review written shadow-engine design, then its implementation plan.
2. Implement/test read-only ingestion, versioned detectors, conservative paper execution, ledger and learning reports.
3. Start resumable five-minute scanning with disclosed uptime limitations and no live execution capabilities.
4. Preserve rejection reasons and forward observations for every strategy, not just successful-looking signals.
5. Build historical regime coverage and chronological held-out validation; report separately from forward testing.
6. Compare net results against cash, buy/hold and simple trend baselines.
7. Prioritize independent observations, blocked uncertainty estimates and correction for multiple experiments.
8. Collect native Swing Trend duration evidence alongside experimental short-horizon markouts.
9. Verify operational safeguards and strategy evidence before considering approval-required small live deployment.
