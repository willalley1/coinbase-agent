# Coinbase Spot Shadow Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Start durable, repeated Coinbase spot paper testing for six research strategy families and learn from cost-adjusted outcomes.

**Architecture:** A Python command-line service reads only public Coinbase Advanced Trade market endpoints, persists observations and paper events in SQLite, and produces Markdown/CSV learning reports. Strategy definitions are frozen research variants; execution simulation and a synthetic portfolio remain separate from independent strategy diagnostics. The existing Coinbase account connection supplies a timestamped fee snapshot, never background trading credentials.

**Tech Stack:** Python 3.14 already available; standard library urllib, sqlite3, decimal, dataclasses, unittest, argparse and zoneinfo. Windows PowerShell process controls. No external packages required.

**Spec:** DEPLOYMENT/SPOT_SHADOW_ENGINE_DESIGN.md (user approved October 5, 2026).

## Global Constraints
- Long-only, unleveraged paper entries.
- No live order tools, funding, transfers, paid data, live permission changes, or automatic strategy promotion.
- Scan every five minutes on closed candles; use 1m data or timestamped quotes for execution/outcome measurement and 15m/1h/4h/1d context as required.
- Preserve missing data rather than forward-fill executable prices.
- Separate all paper datasets from existing live trade/equity tables.
- Exchange-time UTC records with America/New_York user reports.
- Initial USD universe: BTC, ETH, SOL, XRP, DOGE, SUI, NEAR, HYPE, ZEC.
- Primary short holding policy: 60 minutes; 5/15/30/60-minute markouts are correlated diagnostics. Native Swing Trend primary time cap: 48 hours (research implementation default, not a modification of original v1).
- Start with taker-only simulated fills. Maker eligibility remains EXPIRED/NOT_SIMULATED without queue/trade-through evidence; no assumed candle-touch fills.
- Startup must read current HARD_LIMITS and fail closed if malformed. Original strategy files and live configuration are preserved.
- This directory is not a Git repository. Do not initialize Git or pretend commits were made; record changed files and validation evidence.

## Review Focus
1. Startup after machine sleep: recover events transactionally, mark unobserved execution intervals uncertain, never invent quote fills.
2. Public endpoint succeeds but returns old/partial data: reject stale, invalid or gapped observations and record the rejection.
3. Fee tier changes: reports identify snapshot source/time; snapshots older than 24 hours disable executable paper entries until refreshed.
4. A new signal's four horizon outcomes overlap other signals: count unique signals and nonoverlapping cohorts, never inflate independent sample size.
5. One network/product failure: existing positions remain recorded, affected market is blocked, other valid markets continue without losing checkpoints.

## Files and interfaces
Create package SHADOW/ with __init__.py and __main__.py.
SHADOW/models.py: frozen Candle, Book, MarketSnapshot, Candidate, PaperEvent and FeeSnapshot dataclasses.
SHADOW/market_data.py: allowlisted GET-only public Coinbase adapter and freshness checks.
SHADOW/strategies.py: deterministic research features, six detectors, decisions and reasons.
SHADOW/simulation.py: fills, protection, outcomes and synthetic portfolio gates.
SHADOW/storage.py: SQLite schemas, transactions, deduplication and checkpoints.
SHADOW/learning.py: reports, cohort statistics and proposed hypotheses.
SHADOW/runner.py: scan/replay/report/status/stop and persistence.
CONFIG/SHADOW_CONFIG.json: paper-only settings and timestamped fee snapshot.
STRATEGIES/SHADOW_RESEARCH_RULES.json: explicit new research definitions.
TESTS/test_shadow_*.py: meaningful unit/integration fixtures.
DEPLOYMENT/SHADOW_RUNBOOK.md: start/stop/status, limits and interpretation.
DATA/shadow/ and ANALYTICS/shadow/: generated paper outputs only.

Shared shapes:
Candle(start:int, seconds:int, open:Decimal, high:Decimal, low:Decimal, close:Decimal, volume:Decimal).
Book(product_id:str, source_time:int, fetched_at:int, bids:tuple, asks:tuple), levels are (Decimal price, Decimal size).
FeeSnapshot(maker:Decimal, taker:Decimal, observed_at:int, source:str).
MarketSnapshot(product_id:str, as_of:int, candles:dict[int,tuple[Candle,...]], book:Book, product:dict, fees:FeeSnapshot).
Candidate(signal_id:str, product_id:str, strategy_id:str, rules_version:str, bar_start:int, entry:Decimal, stop:Decimal, target:Decimal, expires_at:int, primary_minutes:int, score:int, reasons:tuple[str,...]).
PaperEvent(event_id:str, signal_id:str, timestamp:int, event_type:str, payload:dict).
No module exposes a live order API.

### Task 1: Public market ingestion and configuration

**Files:** SHADOW/models.py, SHADOW/market_data.py, CONFIG/SHADOW_CONFIG.json, TESTS/test_shadow_market_data.py.

**Interfaces:** CoinbasePublicClient.get_product(product_id:str)->dict; get_candles(product_id:str, seconds:int, start:int, end:int)->tuple[Candle,...]; get_book(product_id:str)->Book; validate_snapshot(snapshot:MarketSnapshot)->tuple[str,...].

- [ ] Write failing tests: test_closed_sorted_unique_candles rejects start+seconds>as_of; test_gap_blocks requires contiguous required lookback; test_invalid_ohlc rejects low>high/nonpositive prices/negative volume; test_get_only rejects paths outside the public market allowlist; test_stale_book_and_fee blocks book older than 30 seconds and fees older than 86400 seconds.
- [ ] Run python -m unittest discover -s TESTS -p test_shadow_market_data.py -v; expect missing module/interface failures before implementation.
- [ ] Implement exact dataclasses and client interfaces. Base URL https://api.coinbase.com/api/v3/brokerage/market; allow products, product details/candles, and product_book only. Use 15-second timeout, request throttling <=3/sec, max three retries for 429/5xx/timeouts, bounded backoff 1/2/4 seconds and capped Retry-After. Preserve raw source/fetch times and responses. No silently substituted products or sources.
- [ ] Fetch max 350 candles/request with explicit start/end/granularity. Map 60/300/900/3600/14400/86400 seconds to public API enums. Startup lookbacks: 120 closed candles for each of 1m, 5m, 15m, 1h, 4h and 1d; request a small extra boundary buffer so the incomplete candle does not reduce the required history. Cache larger frames between closes. Closed-candle completion delay: 10 seconds.
- [ ] Configure fees from the saved connected Coinbase snapshot (maker .005, taker .009, observed timestamp), no fee-free fallback. Synthetic equity 10000 USD is a disclosed research assumption, not allocated real capital.
- [ ] Run ingestion tests; expect all pass. Preserve implementation diff/file inventory since no Git is present.

Official API references:
https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/public/get-public-product-candles
https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/public/get-public-product-book

### Task 2: Six frozen research strategy detectors

**Files:** SHADOW/strategies.py, STRATEGIES/SHADOW_RESEARCH_RULES.json, TESTS/test_shadow_strategies.py.

**Interfaces:** evaluate(snapshot:MarketSnapshot, rules:dict)->tuple[dict,...], exactly six records with strategy_id, rules_version, decision, reasons and optional Candidate. features(candles:tuple[Candle,...])->dict. Outputs use the shared Candidate.

- [ ] Write failing tests: test_six_decisions_every_scan; test_no_lookahead mutating candles beyond as_of leaves decisions unchanged; test_wrong_regime_blocks; test_insufficient_context_blocks; test_each_detector_has_positive_and_negative_fixture; test_rules_frozen_candidate stable rule hash.
- [ ] Run detector tests; expect missing implementation failures.
- [ ] Implement new *_shadow_r1 definitions, preserving source v1. Shared features: EMA20/EMA50 (standard alpha 2/(n+1), first-close seed, >=100 bars), ATR14 (Wilder smoothing), RSI14 (Wilder), prior 20-bar high/low excluding trigger, relative volume against preceding 20 closed bars. Reject zero ATR/invalid features. Structure references prior bars only.
- [ ] Set uptrend = 1h EMA20>EMA50 and last close>EMA20 with matching 4h EMA direction. Range = abs(1h EMA20/EMA50-1)<=0.003 and prior 20-bar width>=4 ATR5m. Disorder = ATR5m/close>0.02 or last true range>3 ATR of preceding bars.
- [ ] Trend Pullback: uptrend; previous 15m low<=EMA20+0.5 ATR and close>=EMA50; latest 5m close>previous high, relative volume>=1.2. Stop prior five 5m lows minus .25 ATR; target 2R.
- [ ] Momentum Continuation: uptrend; among preceding six 5m bars an upward impulse >=1.5 ATR, following three-bar consolidation width<=1.5 ATR; trigger close>prior three highs and relative volume>=1.5; close<=EMA20+3 ATR. Stop consolidation low-.25 ATR; target 2R.
- [ ] Confirmed Breakout: previous 20 5m bars width<=6 ATR and last five-bar mean range<=.8 previous 20-bar mean range; latest close>prior 20 high+.1 ATR, relative volume>=1.5, 1h close>=EMA20. Stop prior five low-.25 ATR; target 2R.
- [ ] Range Mean Reversion: range regime; previous close in lower 20% of prior 20-bar range, previous RSI<=35; trigger close>previous high; stop range low-.25 ATR; target range midpoint and reject target<=entry.
- [ ] Exhaustion Reversal: research only; previous close<5m EMA20-2 ATR with RSI<=25; trigger close>prior three-bar high and relative volume>=1.5; reject ongoing disorder. Stop prior five-bar low-.25 ATR; target EMA20, reject target<=entry.
- [ ] Swing Trend: daily and 4h EMA20>EMA50; preceding 4h low<=EMA20+.5 ATR while close>=EMA50; latest 1h close>previous high with relative volume>=1.2. Stop prior five 4h lows-.25 ATR; target 2R; primary time cap 48h; prevent repeat signals on same 1h trigger.
- [ ] Candidate entry is contemporaneous ask, not historical trigger close; reject ask>trigger close+.25 ATR and insufficient target headroom after fees/book cost. Score is rule-based ranking, explicitly uncalibrated: base 70 +5 aligned daily trend +5 relative volume>=2 +5 projected net reward/risk>=2; no probability claims. Replay without quotes creates detection observations only.
- [ ] Run tests for all six fixtures and look-ahead rejection; expect pass. Save version/hash and research assumptions in the rule file.

### Task 3: Durable event ledger

**Files:** SHADOW/storage.py, TESTS/test_shadow_storage.py.

**Interfaces:** Store(path:Path); record_scan(scan_id:str, records:list[dict])->None; append_events(events:list[PaperEvent])->None; active_candidates()->list[Candidate]; save_snapshot(snapshot:MarketSnapshot, raw:dict)->None; checkpoint(key:str,value:dict)->None; read_checkpoint(key:str)->dict|None.

- [ ] Write failing tests: test_duplicate_scan_and_signal_ignored; test_rollback_preserves_previous_checkpoint; test_restart_restores_active_position; test_paper_paths_only; test_concurrent_writer_rejected.
- [ ] Run storage tests and confirm failures.
- [ ] Implement SQLite transactions with unique scan/product/strategy/bar/rules keys; immutable signal/rule/fee snapshots; scans, observations, signals, events, fills, markouts, portfolio snapshots and checkpoints. Store no live portfolio identifiers. Keep raw data in timestamped JSON and checksum it.
- [ ] Use rollback journal and busy timeout, not WAL assumptions on OneDrive; fail clearly on lock/corruption and retain prior data. Enforce a Windows process-lifetime exclusive lock in runner. SQLite plus raw files remain within DATA/shadow.
- [ ] Run transaction/restart tests; expect pass.

### Task 4: Conservative simulation and risk gates

**Files:** SHADOW/simulation.py, TESTS/test_shadow_simulation.py.

**Interfaces:** qualify(candidate:Candidate,snapshot:MarketSnapshot,portfolio:dict,limits:dict)->dict; advance(candidate:Candidate,state:dict,snapshot:MarketSnapshot)->tuple[PaperEvent,...]; markout(candidate:Candidate,horizon:int,snapshot:MarketSnapshot)->dict.

- [ ] Write failing tests: test_fees_on_both_sides exact fee-only hurdle; test_depth_partial_fill records remainder; test_stop_first_on_ambiguous_bar; test_limit_touch_not_fill; test_three_losses_half_risk; test_four_losses_halt; test_daily_limit_and_correlation_block; test_sleep_gap_is_uncertain; test_horizon_count_is_one_signal.
- [ ] Run simulation tests; expect failure.
- [ ] Size from stop and initial dedicated synthetic equity 10000; normal .50%, absolute .75%, lower strategy caps .35% range/.25% reversal. Include fees and estimated exit slippage in risk-per-unit; floor product increments; reject unmet minimum or insufficient cash. Leverage exactly 1.
- [ ] Simulate taker entry through fresh ask depth and exit through bid depth; cap quantity to observed liquidity, record partial/unfilled quantity. Unobserved future stop execution is conservatively modeled and labeled; a gap exits at next observable adverse price, never guaranteed stop price. Reject cost-adjusted target profit<=0 or target net reward/risk<1.5.
- [ ] Apply daily 1.5%, weekly 3/4%, portfolio 5/6/8/10%, and 2/3/4 loss-streak responses from current config. Treat all initial crypto longs as one correlated cluster; provisional paper cap total risk<=1.0%, combined planned loss plus realized daily loss<=daily ceiling. Independent strategy cohorts do not bypass combined synthetic portfolio reporting.
- [ ] Freeze entry rule version/fees/stop/target. Markouts use observed executable bid and costs, or explicitly nonexecutable candle markouts; missing exact horizon data -> unavailable, not invented. Stop/target/time exit primary policy is separate from counterfactual diagnostics.
- [ ] Run tests with hand-calculated fee and risk fixtures; expect pass.

### Task 5: Learning reports and historical research

**Files:** SHADOW/learning.py, TESTS/test_shadow_learning.py.

**Interfaces:** summarize(store:Store,output_dir:Path)->Path; propose_hypotheses(store:Store)->list[dict]; replay(snapshots:list[MarketSnapshot],rules:dict,split_at:int)->dict.

- [ ] Write failing tests: test_unique_signal_sample_count; test_fee_drag_changes_expectancy; test_zero_loss_profit_factor_label; test_sparse_sample_unvalidated; test_replay_is_separate_from_forward; test_no_auto_parameter_changes; test_equity_includes_open_exposure.
- [ ] Run learning tests; expect failure.
- [ ] Report by strategy/version/product/regime/session/score bucket/horizon: unique signals, nonoverlapping primary trades, fill/no-trade reasons, win rate, net expectancy in R, profit factor, portfolio drawdown, MAE/MFE, execution drag and process compliance. Undefined metrics display insufficient data; no fabricated health evidence.
- [ ] Add seeded block-bootstrap intervals when >=30 independent outcomes, explicitly exploratory; warn about strategy/product/horizon multiple comparisons and do not choose winners solely on best sample. >=100 plus regime diversity remains evidence guidance, not automatic promotion.
- [ ] Build chronological historical detection replay and held-out split; never call close-based markouts historical executable fills without historical quotes. Compare against cash/buy-hold/basic trend with disclosed execution assumptions. Append proposed hypotheses with evidence/test plan; do not modify active rules.
- [ ] Run report tests; expect pass; verify CSV/Markdown agree on sample counts.

### Task 6: Repeated runner, operational validation and launch

**Files:** SHADOW/runner.py, SHADOW/__main__.py, TESTS/test_shadow_runner.py, DEPLOYMENT/SHADOW_RUNBOOK.md.

**Interfaces:** scan_once(config_path:Path)->dict; run(config_path:Path,stop_path:Path)->None; CLI scan/run/status/stop/report/replay via python -m SHADOW.

- [ ] Write failing tests: test_scan_restart_does_not_duplicate; test_stop_flag_graceful; test_second_instance_rejected; test_market_failure_isolated; test_stale_fee_halts_entries_but_updates_exits; test_sleep_reports_missing_intervals; test_no_order_endpoints_or_credentials.
- [ ] Run runner tests; expect failure.
- [ ] Implement next-five-minute-boundary plus 10-second scan scheduling and 60-second active-position quote reviews; use monotonic waiting in interruptible <=1-second increments. Cache higher timeframes only until next close, refresh books before fills, reconcile checkpoint before new signals, persist errors.
- [ ] Restrict commands to paper functionality. Status includes PID/process liveness, heartbeat, last successful cycle, markets evaluated/rejected, active/closed paper counts, fee age, data gaps and halt reasons. Stop via flag and verified process exit; no broad process killing.
- [ ] Run python -m unittest discover -s TESTS -p test_shadow_*.py -v and python -m compileall -q SHADOW; both must pass. Run offline failure injections and a read-only scan. Verify only paper output paths changed.
- [ ] Refresh connected Coinbase fee snapshot immediately before launch. If public endpoints cannot be verified reachable, report blocked ingestion rather than simulate current data.
- [ ] Launch python -m SHADOW run using hidden Windows Start-Process with explicit workspace and separate stdout/stderr files; record PID. Verify two successful five-minute cycles, durable checkpoints, and that all six strategy decisions exist per eligible product. Quote reviews between boundaries do not count as completed strategy scans.
- [ ] Write runbook with exact start/stop/status commands, machine-awake/network requirements, fee-refresh policy, synthetic capital, incomplete execution assumptions, and interpretation. Do not claim a Codex recurring automation or 24/7 uptime.
- [ ] Produce first learning report even if zero eligible trades; report zero honestly and keep collection running only while healthy. Live deployment/autonomy remain separate user decisions.

## Self-review and execution handoff
All ten design components map to Tasks 1–6. Read-only network restrictions, immutable research versions, conservative fills, related horizons, native swing duration, risk gates, reports, separate paper paths and restart recovery have concrete checks.
No implementation has started. User reviews this plan and chooses execution method before coding.
Recommended Native: one implementation flow because the six tasks share tightly coupled types and the project is paper-only. Use superpowers:executing-plans; perform final independent review under that workflow if permitted by its instructions.
Subagent-driven is available if the user prefers task-by-task independent reviews.
