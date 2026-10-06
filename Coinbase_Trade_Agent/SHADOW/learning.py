"""Evidence summaries; never modifies strategy parameters or live permissions."""
from collections import defaultdict, Counter
from pathlib import Path
from statistics import mean
import csv
import json
import random
from datetime import datetime,timezone
from .models import dumps

HORIZONS=(1,2,3,5,10,15,20,30,45,60,90,120,180,240)

def trade_metrics(rows):
    rs=[float(r['realized_r']) for r in rows]
    pnls=[float(r['net_pnl']) for r in rows]
    wins=sum(p for p in pnls if p>0); losses=-sum(p for p in pnls if p<0)
    return dict(trades=len(rows),net_pnl=sum(pnls),expectancy_r=mean(rs) if rs else None,
                win_rate=sum(p>0 for p in pnls)/len(pnls) if pnls else None,
                profit_factor=wins/losses if losses else None,
                uncertain_trades=sum(bool(r.get('uncertain')) for r in rows))

def outcome_metrics(rows):
    unique={r['signal_id']:r for r in rows}
    rows=list(unique.values()); days=defaultdict(list)
    for r in rows: days[r['day']].append(float(r['net_return']))
    vals=[v for day in days.values() for v in day]
    ci=None
    if len(vals)>=30 and len(days)>=5:
        rng=random.Random(7); blocks=list(days.values()); samples=[]
        for _ in range(1000):
            sample=[v for block in rng.choices(blocks,k=len(blocks)) for v in block]
            samples.append(mean(sample))
        samples.sort(); ci=samples[24]
    return dict(independent_count=len(rows),days=len(days),positive_days=sum(mean(v)>0 for v in days.values()),
                net_mean=mean(vals) if vals else None,win_rate=sum(v>0 for v in vals)/len(vals) if vals else None,ci_low=ci)

def select_windows(rows):
    eligible=[r for r in rows if r['independent_count']>=100 and r['days']>=10 and r['positive_days']/r['days']>=.8
              and r['net_mean'] is not None and r['net_mean']>0 and r['ci_low'] is not None and r['ci_low']>0]
    shortest=min((r['horizon_minutes'] for r in eligible),default=None)
    larger=[h for h in HORIZONS if shortest is not None and h>shortest][:3]
    return dict(shortest_provisional_minutes=shortest,next_larger_minutes=larger,validated=False,
                reason='Exploratory threshold only; requires untouched holdout, forward evidence and correction for multiple comparisons')

def forward_metrics(rows):
    grouped=defaultdict(list)
    for r in rows:
        if r['status']=='OBSERVED': grouped[(r['product_id'],r['strategy_id'],r['horizon_minutes'],r.get('rules_version','LEGACY_UNSPECIFIED'))].append(r)
    results=[]
    for key,values in grouped.items():
        clean=[]; next_start=0
        for r in sorted(values,key=lambda x:x['due_at']):
            start=r['due_at']-key[2]*60
            if start<next_start: continue
            next_start=r['due_at']
            clean.append(dict(r,day=datetime.fromtimestamp(start,timezone.utc).date().isoformat()))
        results.append(dict(product_id=key[0],strategy_id=key[1],horizon_minutes=key[2],rules_version=key[3],**outcome_metrics(clean)))
    return results

def summarize(store,output_dir):
    output_dir=Path(output_dir); output_dir.mkdir(parents=True,exist_ok=True)
    signals=store.rows('signals'); closed=[r for r in signals if r.get('state')=='CLOSED']
    grouped=defaultdict(list)
    for r in closed: grouped[r['strategy_id']+'/'+r.get('rules_version','LEGACY_UNSPECIFIED')].append(r)
    observations=store.rows('observations'); reasons=Counter(reason for r in observations for reason in r.get('reasons',[]))
    p=store.read_checkpoint('portfolio') or {}
    markouts=store.rows('markouts'); forward=forward_metrics(markouts)
    evidence=dict(unique_signals=len(signals),active=sum(r.get('state')=='ACTIVE' for r in signals),closed=trade_metrics(closed),
                  by_strategy={k:trade_metrics(v) for k,v in grouped.items()},rejection_reasons=dict(reasons),portfolio=p,
                  fee_snapshot=store.read_checkpoint('fees'),forward_window_metrics=forward,validated=False)
    (output_dir/'latest.json').write_text(dumps(evidence),encoding='utf-8')
    text=['# Coinbase spot paper learning report','',
          'Research only. No strategy or holding period is validated by this report.',
          f"Unique recorded signals: {len(signals)}. Active: {evidence['active']}. Closed primary paper trades: {len(closed)}.",
          'Horizon markouts from the same signal are related observations; uncertain modeled fills are excluded from promotion evidence.',
          '', '## Primary trade results','',dumps(evidence['closed']),'','## Rejection reasons','']
    text.extend(f'- {reason}: {count}' for reason,count in reasons.most_common())
    text+=['','## Forward holding-window observations','',dumps(forward),
           '', 'Counterfactual quote observations include rejected research signals. These are not independently executed trades.',
           '', '## Synthetic portfolio','',dumps(p),'','## Fees','',dumps(evidence['fee_snapshot']),
           '', 'No automatic parameter changes. Historical results and forward quote evidence remain separate.']
    text+=['','## Measures not yet implemented','',
           'Regime/session/score attribution, aggregate MAE/MFE, execution-drag and compliance-rate summaries, historical baselines and independent primary cohort counts are unavailable in this first report. Do not treat the report as full validation.',
           'Minute reviews can miss the 30-second markout tolerance on slow networks; unavailable marks are retained and never fabricated.']
    target=output_dir/'latest.md'; target.write_text('\n'.join(text)+'\n',encoding='utf-8')
    if markouts:
        keys=sorted({k for r in markouts for k in r})
        with (output_dir/'forward_markouts.csv').open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=keys); writer.writeheader(); writer.writerows(markouts)
    return target

def propose_hypotheses(store):
    observations=store.rows('observations')
    costs=sum('COSTS_CONSUME_EDGE' in r.get('reasons',[]) for r in observations)
    return [{'hypothesis':'Test longer holding periods or conservative maker execution on held-out data',
             'evidence':{'cost_rejections':costs},'status':'PROPOSED_ONLY','live_change':False}] if costs else []
