"""All-six-strategy historical detection and next-bar candle markouts."""
from bisect import bisect_right
from datetime import datetime,timezone
from decimal import Decimal as D
from pathlib import Path
import json
from .history import load_range
from .models import Book,MarketSnapshot,FeeSnapshot,dumps,digest
from .market_data import CoinbasePublicClient,candle_errors
from .strategies import evaluate
from .simulation import net_return
from .learning import outcome_metrics,select_windows

def context_at(bars,as_of):
    if not bars: return ()
    starts=[b.start for b in bars]
    end=bisect_right(starts,as_of-bars[0].seconds)
    return bars[max(0,end-125):end]

def signal_outcome(by_time,start,horizon,fee):
    keys=range(start,start+horizon*60,60)
    if any(t not in by_time for t in keys): return None
    entry=by_time[start].open; exit_price=by_time[start+(horizon-1)*60].close
    return net_return(entry,exit_price,fee,fee)

def run_replay(root,days=14):
    root=Path(root); config=json.loads((root/'CONFIG'/'SHADOW_CONFIG.json').read_text())
    rules=json.loads((root/'STRATEGIES'/'SHADOW_RESEARCH_RULES.json').read_text())
    rules['implementation_sha256']=digest((root/'SHADOW'/'strategies.py').read_text())
    raw=root/'DATA'/'shadow'/'historical'; output=root/'ANALYTICS'/'shadow'; output.mkdir(parents=True,exist_ok=True)
    anchor=json.loads((raw/'research_anchor.json').read_text())['end']; start=anchor-days*86400
    split=start+(anchor-start)*2//3; client=CoinbasePublicClient(); fee=D(config['fee_snapshot']['taker'])
    groups={}; summary=[]; errors={}; decisions=[]
    fee_snapshot=FeeSnapshot(D(config['fee_snapshot']['maker']),fee,anchor,'current fees applied historically; approximation')
    for product in config['products']:
        try:
            frames={}
            for sec in (60,300,900,3600,14400,86400):
                # Warmup before research period must be available at decision time.
                frames[sec]=load_range(client,product,sec,start-130*sec if sec!=60 else start,anchor,raw)
            by_time={c.start:c for c in frames[60]}; seen=set(); next_allowed={}; evaluations=0; triggers=0
            for bar in frames[300]:
                t=bar.start+300
                if t<start or t>=anchor: continue
                context={sec:context_at(bars,t) for sec,bars in frames.items() if sec!=60}
                if any(len(v)<101 or candle_errors([c.start for c in v],sec,t) for sec,v in context.items()): continue
                next_bar=by_time.get(t)
                if not next_bar: continue
                book=Book(product,t,t,((next_bar.open,D(1)),),((next_bar.open,D(1)),))
                snapshot=MarketSnapshot(product,t,context,book,{'product_type':'SPOT','status':'online'},fee_snapshot)
                for row in evaluate(snapshot,rules):
                    evaluations+=1; candidate=row.get('candidate')
                    if not candidate or candidate.signal_id in seen: continue
                    seen.add(candidate.signal_id); triggers+=1
                    decisions.append(dict(product_id=product,strategy_id=candidate.strategy_id,signal_id=candidate.signal_id,as_of=t,sample='HELDOUT' if t>=split else 'RESEARCH',executable_trade=False))
                    for horizon in config['horizons_minutes']:
                        key=(product,candidate.strategy_id,horizon,'HELDOUT' if t>=split else 'RESEARCH')
                        # Each product/strategy/horizon cohort uses nonoverlapping intervals.
                        if t<next_allowed.get(key,0): continue
                        value=signal_outcome(by_time,t,horizon,fee)
                        if value is None: continue
                        next_allowed[key]=t+horizon*60
                        groups.setdefault(key,[]).append(dict(signal_id=candidate.signal_id,net_return=str(value),day=datetime.fromtimestamp(t,timezone.utc).date().isoformat(),start=t))
            for key,rows in groups.items():
                if key[0]!=product: continue
                summary.append(dict(product_id=key[0],strategy_id=key[1],horizon_minutes=key[2],sample=key[3],**outcome_metrics(rows)))
            (output/'strategy_replay.json').write_text(dumps(dict(days=days,as_of=anchor,split_at=split,rows=summary,errors=errors,
                decisions=decisions,source='HISTORICAL_SIGNAL_CANDLE_MARKOUTS',executable_trade=False,validated=False)),encoding='utf-8')
            print(dumps({'replay_product_complete':product,'detector_evaluations':evaluations,'unique_triggers':triggers}),flush=True)
        except Exception as exc:
            errors[product]=type(exc).__name__+': '+str(exc); print(dumps({'replay_product_error':product,'error':errors[product]}),flush=True)
    selections={}
    for product,strategy,_,sample in groups:
        if sample!='HELDOUT': continue
        key=product+'/'+strategy
        if key not in selections: selections[key]=select_windows([r for r in summary if r['product_id']==product and r['strategy_id']==strategy and r['sample']=='HELDOUT'])
    result=dict(days=days,as_of=anchor,split_at=split,rows=summary,errors=errors,selections=selections,decisions=decisions,
                source='HISTORICAL_SIGNAL_CANDLE_MARKOUTS',executable_trade=False,validated=False,
                limitations='Next-bar opens and horizon closes with current taker fees; no historical spreads/depth or protective-exit simulation. Not executable backtest. Holdout is exploratory, multiple comparisons uncorrected.')
    (output/'strategy_replay.json').write_text(dumps(result),encoding='utf-8')
    lines=['# Historical strategy holding-window research','',result['limitations'],'',
           '| Product | Strategy | Sample | Minutes | Nonoverlapping signals | Mean net % | Win % |',
           '|---|---|---|---:|---:|---:|---:|']
    for r in summary:
        lines.append(f"| {r['product_id']} | {r['strategy_id']} | {r['sample']} | {r['horizon_minutes']} | {r['independent_count']} | {r['net_mean']*100:.3f} | {r['win_rate']*100:.1f} |")
    lines+=['','Selections: '+dumps(selections),'','Errors: '+dumps(errors)]
    (output/'strategy_replay.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return result
