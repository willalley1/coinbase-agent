# Shortest profitable holding-window search — initial findings
Date: October 5, 2026, America/New_York.

## Result
No consistently profitable holding window has been demonstrated.
Tested 1, 2, 3, 5, 10, 15, 20, 30, 45, 60, 90, 120, 180 and 240 minutes on nine Coinbase USD spot markets.
Downloaded approximately 14 days of one-minute candles. Historical coverage includes missing intervals; affected windows were skipped, not filled.
Unconditional chronological evaluation returned negative average after-fee returns for all product/horizon combinations.
All six versioned research detectors were replayed chronologically; 827 unique historical triggers were recorded:
Trend Pullback 528; Momentum Continuation 29; Swing Trend 135; Range Mean Reversion 105; Confirmed Breakout 28; Exhaustion Reversal 2.
These are research signals, not executed trades. Signals across families/products can be correlated; markouts are not independent trades.

## Smallest isolated positive signal window
NEAR Momentum Continuation had one evaluation-period signal with a positive 15-minute after-fee candle markout of approximately +0.015%.
That is only one signal and excludes historical spread/slippage/depth. The remaining margin is too small to establish executable profit.

| Window on that same NEAR signal | Candle markout after assumed taker fees |
|---|---:|
| 1 minute | -1.713% |
| 2 minutes | -1.774% |
| 3 minutes | -1.902% |
| 5 minutes | -1.857% |
| 10 minutes | -1.075% |
| 15 minutes | +0.015% |
| 20 minutes | -0.104% |
| 30 minutes | +0.588% |
| 45 minutes | -0.561% |
| 60 minutes | -0.328% |
| 90 minutes | -0.015% |
| 120 minutes | +0.777% |
| 180 minutes | -0.076% |

The next three larger windows after the isolated 15-minute result are 20, 30 and 45 minutes. Only 30 minutes was positive on that observation.
Longer windows do not improve monotonically. Do not select exits retrospectively based on this outcome.

## Longer-window watchlist
NEAR Momentum Continuation at 30/120 minutes: positive single observations; insufficient sample.
ZEC Range Mean Reversion at 120 minutes: mean +0.262% across two observations, one win and one loss.
ZEC Range Mean Reversion at 180/240 minutes: +1.444%/+2.294%, each one nonoverlapping observation.
SUI Momentum Continuation at 240 minutes: +0.850%, one observation.
All remain unvalidated research candidates. There is no confidence interval supporting consistency and no multiple-comparison-adjusted finding.

## Learning priorities
1. Collect prospective signals and quotes before outcomes occur; preserve losers and no-trade decisions.
2. Focus cost-sensitive research on NEAR momentum 15/20/30/45 minutes and compare 60/90/120 minutes; watch ZEC range 120/180/240 minutes.
3. Keep the full horizon ladder frozen while testing. Treat this initial ranking as hypothesis generation; reserve new untouched data for confirmation.
4. At current .50% maker/.90% taker per-side account fees, very short trades require unusually large moves or evidenced maker execution. Do not assume cheaper fills.
5. Require independent/nonoverlapping observations, regime diversity, positive net expectancy, acceptable drawdown, fee-inclusive execution and block-aware uncertainty before any promotion.
6. Use primary stop/target/time-exit paper trades to check whether candle markout hypotheses survive actual protective-exit logic.
7. Swing Trend's native long holding policy remains separate from the short-window experiment.

No live trades, capital transfers, strategy promotions or autonomous live permissions were enabled.
