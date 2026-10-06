# Initial paper-service verification

Verified October 5, 2026, approximately 11:25 p.m. America/New_York.

- Hidden local process PID 47940 remains running.
- First two background strategy scans completed at 11:23:47 p.m. and 11:25:22 p.m. EDT. Each produced 54 strategy/product decisions; seven markets had valid required inputs. DOGE/HYPE new paper entries were rejected for missing minute candles.
- A minute review completed between the scans; stderr log was empty.
- Zero active and zero closed paper positions at verification. One retained cost-rejected signal observation; unavailable historical quote horizons are labeled unavailable.
- Synthetic portfolio: $10,000, no allocated real capital, NORMAL risk state.
- Full executable test discovery: 41/41 pass; compilation check passes. Independent review defects reproduced and corrected with regressions.
- Historical research: 14 days, nine USD spot markets, fourteen holding windows; 126 unconditional evaluation cells all had negative mean after-taker-fee returns.
- Strategy research replay:827 unique triggers across all six frozen research families; no provisional consistent holding-window result. Positive evaluation cells have only one or two observations.
- No live trading, paid data, funding, transfers, or autonomous live permission enabled.

The process needs an awake machine/network and is not a startup task or Codex automation. Account fees expire24 hours after their saved refresh; entries are blocked until fees are refreshed, while existing simulated protection remains monitored. Full attribution reports, full candle-to-candidate detector fixtures and improved due-time sampling remain documented follow-up work. No strategy is validated or approved for live deployment.
