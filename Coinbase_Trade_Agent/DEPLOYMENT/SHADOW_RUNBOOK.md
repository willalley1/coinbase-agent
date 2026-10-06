# Coinbase spot paper research runbook

This runner uses public Coinbase market data and synthetic capital only. It contains no live order, transfer, funding, paid-data or account-authentication functionality.

## Operation

Run from the Coinbase_Trade_Agent folder:

```powershell
python -m SHADOW status
python -m SHADOW report
python -m SHADOW stop
```

Stop writes DATA/shadow/STOP. The running process finishes its current bounded market reads, releases its lock and records stopped status. Verify running=false before restarting. Do not kill unrelated Python processes.

To start interactively after a verified stop, remove only DATA/shadow/STOP and run:

```powershell
python -m SHADOW run
```

The installed background process uses the same command with a hidden window. Its PID, last scan, heartbeat and errors are available through status. Logs are DATA/shadow/runner.stdout.log and runner.stderr.log. A process can be alive while data collection fails: inspect successful_markets, errors and heartbeat_age_seconds together.

The machine must remain awake with network access. There is no installed recurring Codex automation or Windows startup task. Process restarts resume SQLite paper records, but historical quote gaps are not invented. OneDrive synchronization is not a database backup strategy; avoid opening a second runner from another machine.

## Scan and evidence policy

Strategy scans every five minutes, 10 seconds after the boundary. Active paper positions and pending counterfactual markouts are reviewed about once a minute. Nine USD markets and six separately versioned research strategy families are evaluated. Any required data gaps/staleness reject entries rather than forward-fill prices.

Holding-window ladder: 1, 2, 3, 5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240 minutes. Primary intraday paper trade time cap is 60 minutes; Swing Trend cap is 48 hours. Counterfactual markouts do not apply primary protective exits and are not counted as independent executed trades. Signal observations rejected on fees/risk remain useful for horizon diagnostics.

Each strategy is a new shadow_r1 research implementation of qualitative source rules, not a validated v1 strategy. Entry-time implementation hashes freeze definitions. Exhaustion Reversal remains research. Uncalibrated scores are ranking tools, not win probabilities.

Paper portfolio assumes $10,000 synthetic equity, spot longs, 1x leverage, project hard limits and a provisional 1% correlated-cluster stop-risk ceiling. No real capital is allocated. Portfolio entries use current ask depth, exits use bid depth, and fees apply to both sides. Future historical stop-touch execution cannot be known from candles: those fills are flagged uncertain and conservatively modeled.

Maker fills are NOT_SIMULATED without queue/trade-through evidence. The current account-fee snapshot is in CONFIG/SHADOW_CONFIG.json; refresh it from connected Coinbase read-only fees. After 24 hours it blocks new executable paper entries. Existing exits continue to be monitored using the frozen entry fee assumption, with the stale-fee limitation visible. Do not infer zero fees or silently use a cheaper tier.

## Reports and research

- ANALYTICS/shadow/latest.md and latest.json: forward paper trade and signal evidence, rejection reasons, synthetic risk state and fees.
- ANALYTICS/shadow/window_research.md/.csv/.json: nonoverlapping historical minute-candle holding-window cost screens. These are unconditional observations, not strategy backtests.
- ANALYTICS/shadow/strategy_replay.md/.json: all-six-strategy historical detection and next-bar candle markouts. No historical spread/depth or protective-exit simulation; not executable backtests.
- DATA/shadow/paper.sqlite: durable forward ledger. DATA/shadow/raw: source evidence. DATA/shadow/historical: resumable research downloads.

```powershell
python -m SHADOW research --days 14
python -m SHADOW replay --days 14
```

Research uses a saved fixed endpoint so interrupted downloads are reproducible. Historical fees use the current snapshot as an approximation. Chronological final-third evaluation remains exploratory because many products/strategies/horizons are compared.

A provisional smallest window requires at least 100 nonoverlapping outcomes, 10 observed days, positive net mean, positive day-block-bootstrap lower confidence bound and at least 80% positive days. This is a screening criterion, not validated consistency. Require untouched holdout, forward paper evidence, acceptable drawdown and multiple-comparison controls before promotion. Once a shortest candidate clears screening, compare the next three larger ladder windows.

## Verification

```powershell
python -m unittest discover -s TESTS -p test_shadow_*.py -v
python -m compileall -q SHADOW
```

No learning report changes strategy parameters or live permissions. Proposed hypotheses require a new research version and separate validation. Live execution remains APPROVAL_REQUIRED and disabled in this runner.
