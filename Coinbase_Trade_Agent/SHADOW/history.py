"""Chronological historical research; candle markouts are not executable fills."""
from bisect import bisect_right
from dataclasses import asdict
from datetime import datetime,timezone
from decimal import Decimal as D
from pathlib import Path
import csv
import json
import time
from .models import Candle,Book,MarketSnapshot,FeeSnapshot,dumps,digest
from .market_data import CoinbasePublicClient,parse_candles
from .simulation import net_return
from .learning import HORIZONS,outcome_metrics,select_windows
from .strategies import evaluate

def window_outcomes(product,bars,horizon,fee):
    rows=[]; n=horizon; i=1
    while i+n<len(bars):
        a=bars[i]; b=bars[i+n]
        if any(bars[j+1].start-bars[j].start!=60 for j in range(i,i+n)):
            i+=1; continue
        rows.append(dict(signal_id=digest((product,a.start,horizon)),product_id=product,horizon_minutes=horizon,
                         start=a.start,day=datetime.fromtimestamp(a.start,timezone.utc).date().isoformat(),
                         net_return=str(net_return(a.close,b.close,fee,fee)),gross_return=str(b.close/a.close-1),
                         executable_trade=False,source='HISTORICAL_CANDLE_COST_SCREEN'))
        i+=n
    return rows

def load_range(client,product,seconds,start,end,folder):
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    bars={}; cursor=start-start%seconds
    while cursor<end:
        stop=min(end,cursor+349*seconds)
        target=folder/f'{product}-{seconds}-{cursor}-{stop}.json'
        if target.exists():
            values=parse_candles(json.loads(target.read_text(encoding='utf-8'))['candles'],seconds,stop)
        else:
            values=client.get_candles(product,seconds,cursor,stop)
            target.write_text(dumps({'source':'COINBASE_PUBLIC_ADVANCED','candles':[asdict(c) for c in values]}),encoding='utf-8')
        bars.update({c.start:c for c in values if start<=c.start and c.start+seconds<=end})
        cursor=stop
    return tuple(bars[t] for t in sorted(bars))

def research(config,root,days=None):
    root=Path(root); output=root/'ANALYTICS'/'shadow'; output.mkdir(parents=True,exist_ok=True)
    raw=root/'DATA'/'shadow'/'historical'
    anchor_file=raw/'research_anchor.json'; raw.mkdir(parents=True,exist_ok=True)
    if anchor_file.exists(): end=json.loads(anchor_file.read_text())['end']
    else:
        end=int(time.time())//60*60
        anchor_file.write_text(dumps({'end':end,'created_at':int(time.time())}),encoding='utf-8')
    days=days or config['history_days']; start=end-days*86400
    fee=D(config['fee_snapshot']['taker']); client=CoinbasePublicClient(); rows=[]; errors={}
    for product in config['products']:
        try:
            bars=load_range(client,product,60,start,end,raw)
            product_rows=[]
            for horizon in config['horizons_minutes']:
                values=window_outcomes(product,bars,horizon,fee)
                # Final third is chronological holdout; candidate screen remains exploratory.
                holdout=[r for r in values if r['start']>=start+(end-start)*2//3]
                m=outcome_metrics(holdout)
                product_rows.append(dict(product_id=product,horizon_minutes=horizon,**m,
                                         total_windows=len(values),holdout_start=start+(end-start)*2//3,
                                         interpretation='UNCONDITIONAL_CANDLE_SCREEN_NOT_STRATEGY_BACKTEST'))
            rows.extend(product_rows)
            (output/'window_research.json').write_text(dumps({'as_of':end,'days':days,'fees':config['fee_snapshot'],'rows':rows,'errors':errors}),encoding='utf-8')
            print(dumps({'historical_product_complete':product,'minute_bars':len(bars),'windows':sum(r['total_windows'] for r in product_rows)}),flush=True)
        except Exception as exc:
            errors[product]=type(exc).__name__+': '+str(exc)
            print(dumps({'historical_product_error':product,'error':errors[product]}),flush=True)
    keys=sorted({k for r in rows for k in r})
    if rows:
        with (output/'window_research.csv').open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=keys); writer.writeheader(); writer.writerows(rows)
    selections={p:select_windows([r for r in rows if r['product_id']==p]) for p in config['products']}
    result=dict(as_of=end,days=days,fees=config['fee_snapshot'],rows=rows,errors=errors,selections=selections,
                limitation='Historical nonoverlapping unconditional candle returns, missing spreads/depth; not strategy fills or proof of consistency')
    (output/'window_research.json').write_text(dumps(result),encoding='utf-8')
    text=['# Shortest holding-window research','',result['limitation'],'',
          f'Historical span: {days} days. Final third used for chronological evaluation. Current fee assumptions applied to both sides.',
          'No window is validated. A profitable historical selection still needs untouched holdout and forward testing.',
          '', '| Product | Minutes | Evaluation windows | Mean net % | Win % | Positive days / days |',
          '|---|---:|---:|---:|---:|---:|']
    for r in rows:
        avg='n/a' if r['net_mean'] is None else f"{r['net_mean']*100:.3f}"
        win='n/a' if r['win_rate'] is None else f"{r['win_rate']*100:.1f}"
        text.append(f"| {r['product_id']} | {r['horizon_minutes']} | {r['independent_count']} | {avg} | {win} | {r['positive_days']}/{r['days']} |")
    text+=['','Selections: '+dumps(selections),'','Errors: '+dumps(errors)]
    (output/'window_research.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    return result

def replay(snapshots,rules,split_at):
    rows=[]
    for snapshot in sorted(snapshots,key=lambda x:x.as_of):
        for row in evaluate(snapshot,rules):
            rows.append(dict(row,as_of=snapshot.as_of,product_id=snapshot.product_id,
                             sample='HELDOUT' if snapshot.as_of>=split_at else 'RESEARCH',executable_trade=False,source='HISTORICAL_DETECTION_ONLY'))
    return {'rows':rows,'validated':False}
