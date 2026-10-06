"""Resumable, single-instance, read-only paper runner."""
from dataclasses import asdict
from datetime import datetime,timezone,timedelta
from decimal import Decimal as D
from pathlib import Path
import argparse
import calendar
import json
import os
import time
from .models import FeeSnapshot,MarketSnapshot,dumps,digest
from .market_data import CoinbasePublicClient,GRANULARITIES,validate_snapshot,freshness_errors
from .strategies import NAMES,evaluate
from .storage import Store
from .simulation import qualify,advance,markout,walk_depth
from .learning import summarize,propose_hypotheses

ROOT=Path(__file__).resolve().parent.parent

def eastern(ts):
    # Standard-library fallback for US Eastern rules since 2007 on Windows.
    year=datetime.fromtimestamp(ts,timezone.utc).year
    def sunday(month,n):
        first=datetime(year,month,1,tzinfo=timezone.utc)
        return 1+(6-first.weekday())%7+7*(n-1)
    start=datetime(year,3,sunday(3,2),7,tzinfo=timezone.utc).timestamp()
    end=datetime(year,11,sunday(11,1),6,tzinfo=timezone.utc).timestamp()
    offset=-4 if start<=ts<end else -5
    return datetime.fromtimestamp(ts,timezone(timedelta(hours=offset)))

def next_scan_at(now): return ((int(now)-10)//300+1)*300+10

def failed_market_rows(product,now,error):
    return [dict(product_id=product,strategy_id=n+'_shadow_r1',as_of=now,decision='NO_TRADE',reasons=['MARKET_DATA_ERROR'],error=error) for n in NAMES]

def validate_config(config,limits):
    if config.get('paper_only') is not True: raise ValueError('PAPER_ONLY_REQUIRED')
    try:
        if not D(0)<D(str(limits['risk_per_trade_pct']['default']))<=D(str(limits['risk_per_trade_pct']['absolute_max']))<=D('.75'): raise ValueError('RISK_LIMIT')
        for value in [limits['daily_loss_limit_pct'],*limits['weekly_drawdown_pct'].values(),*limits['portfolio_drawdown_pct'].values()]:
            if not D(0)<D(str(value))<=100: raise ValueError('LOSS_LIMIT')
        if not 0<limits['loss_streak']['half_risk']<limits['loss_streak']['halt_new_entries']: raise ValueError('LOSS_STREAK')
        if not D(0)<D(config['synthetic_equity_usd']): raise ValueError('SYNTHETIC_EQUITY')
        if not config['products'] or any(not p.endswith('-USD') for p in config['products']): raise ValueError('SPOT_USD_ONLY')
    except (KeyError,TypeError): raise ValueError('INVALID_HARD_LIMITS_OR_CONFIG') from None

class ProcessLock:
    def __init__(self,path): self.path=Path(path)
    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.file=self.path.open('a+b')
        self.file.seek(0); self.file.write(b'0'); self.file.flush(); self.file.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.file.close(); raise RuntimeError('ANOTHER_SHADOW_INSTANCE_RUNNING') from None
        return self
    def __exit__(self,*args):
        if os.name=='nt':
            import msvcrt
            self.file.seek(0); msvcrt.locking(self.file.fileno(),msvcrt.LK_UNLCK,1)
        self.file.close()

class Engine:
    def __init__(self,root=ROOT,config_path=None,client=None):
        self.root=Path(root)
        self.config_path=Path(config_path or self.root/'CONFIG'/'SHADOW_CONFIG.json')
        self.client=client or CoinbasePublicClient(); self.cache={}; self.products={}
        self.db=self.root/'DATA'/'shadow'/'paper.sqlite'
        self.reload()

    def reload(self):
        self.config=json.loads(self.config_path.read_text(encoding='utf-8'))
        self.limits=json.loads((self.root/'CONFIG'/'HARD_LIMITS.json').read_text(encoding='utf-8'))
        validate_config(self.config,self.limits)
        self.rules=json.loads((self.root/'STRATEGIES'/'SHADOW_RESEARCH_RULES.json').read_text(encoding='utf-8'))
        self.rules['implementation_sha256']=digest((self.root/'SHADOW'/'strategies.py').read_text(encoding='utf-8'))
        f=self.config['fee_snapshot']; self.fees=FeeSnapshot(D(f['maker']),D(f['taker']),int(f['observed_at']),f['source'])

    def collect(self,product,review=False):
        now=int(time.time()); candles={}
        if product not in self.products: self.products[product]=self.client.get_product(product)
        for sec in ([60] if review else GRANULARITIES):
            boundary=(now-10)//sec*sec
            key=(product,sec)
            cached=self.cache.get(key)
            if cached and cached[0]==boundary: candles[sec]=cached[1]
            else:
                bars=self.client.get_candles(product,sec,boundary-125*sec,boundary)
                candles[sec]=bars; self.cache[key]=(boundary,bars)
        book=self.client.get_book(product)
        return MarketSnapshot(product,book.fetched_at,candles,book,self.products[product],self.fees)

    def portfolio(self,store,now):
        p=store.read_checkpoint('portfolio')
        if not p:
            equity=self.config['synthetic_equity_usd']
            p=dict(equity=equity,cash=equity,peak=equity,daily_start=equity,weekly_start=equity,loss_streak=0,open_risk='0',
                   realized_equity=equity,day=eastern(now).date().isoformat(),week=eastern(now).strftime('%G-%V'),halted=False)
        if p['day']!=eastern(now).date().isoformat():
            p['day']=eastern(now).date().isoformat(); p['daily_start']=p['equity']
        if p['week']!=eastern(now).strftime('%G-%V'):
            p['week']=eastern(now).strftime('%G-%V'); p['weekly_start']=p['equity']
        p['cluster_risk_pct']=self.config['cluster_risk_pct']
        p['minimum_net_reward_risk']=self.config['minimum_net_reward_risk']
        return p

    def review_market(self,store,snapshot,p):
        errors=freshness_errors(snapshot.book.source_time,snapshot.book.fetched_at,self.fees.observed_at,snapshot.as_of)
        if 'STALE_BOOK' in errors: return
        for state in store.rows('signals'):
            if state['product_id']!=snapshot.product_id: continue
            with store.transaction():
                if state['state']=='ACTIVE':
                    events=advance(None,state,snapshot)
                    store.append_events(events)
                    if state['state']=='CLOSED':
                        qty=D(state['quantity']); proceeds=qty*D(state['exit'])-D(state['exit_fee'])
                        p['cash']=str(D(p['cash'])+proceeds)
                        p['realized_equity']=str(D(p['realized_equity'])+D(state['net_pnl']))
                        p['loss_streak']=int(p['loss_streak'])+1 if D(state['net_pnl'])<0 else 0
                        if p['loss_streak']>=self.limits['loss_streak']['halt_new_entries']: p['halted']=True
                for h in self.config['horizons_minutes']:
                    if h in state['markouts']: continue
                    row=markout(state,h,snapshot)
                    if row['status']!='NOT_DUE':
                        store.put('markouts',digest((state['signal_id'],h)),row)
                        state['markouts'].append(h)
                store.put('signals',state['signal_id'],state,True)
                store.checkpoint('portfolio',p)

    def mark_equity(self,store,p):
        active=store.active_candidates(); value=D(p['cash']); risk=D(0)
        for state in active:
            cached=store.read_checkpoint('quote:'+state['product_id'])
            if cached and int(time.time())-cached['timestamp']<=120:
                bid=D(cached['bid']); value+=D(state['quantity'])*bid*(1-D(state['fee']))
            else:
                value+=D(state['quantity'])*min(D(state['entry']),D(state['stop']))*(1-D(state['fee']))
            risk+=D(state['initial_risk'])
        p['equity']=str(value); p['peak']=str(max(value,D(p['peak']))); p['open_risk']=str(risk)
        p['drawdown_pct']=str((1-value/D(p['peak']))*100)
        store.checkpoint('portfolio',p)

    def cycle(self,scan=True):
        self.reload(); start=int(time.time()); rows=[]; errors={}; successful=[]
        with Store(self.db) as store:
            p=self.portfolio(store,start); store.checkpoint('fees',asdict(self.fees))
            tracked={s['product_id'] for s in store.rows('signals') if s['state']=='ACTIVE' or len(s['markouts'])<len(self.config['horizons_minutes'])}
            products=self.config['products'] if scan else [v for v in self.config['products'] if v in tracked]
            for product in products:
                try:
                    snapshot=self.collect(product,review=not scan)
                    store.checkpoint('quote:'+product,{'bid':str(snapshot.book.bids[0][0]),'timestamp':snapshot.as_of})
                    self.review_market(store,snapshot,p); self.mark_equity(store,p)
                    if not scan: continue
                    issues=validate_snapshot(snapshot)
                    if issues: rows.extend(failed_market_rows(product,snapshot.as_of,','.join(issues))); errors[product]=','.join(issues); continue
                    store.save_snapshot(snapshot,self.client.raw); self.client.raw=[]
                    successful.append(product)
                    for decision in evaluate(snapshot,self.rules):
                        row=dict(decision,product_id=product,as_of=snapshot.as_of)
                        candidate=row.pop('candidate',None)
                        if candidate:
                            with store.transaction():
                                duplicate=store.conn.execute('SELECT 1 FROM signals WHERE id=?',(candidate.signal_id,)).fetchone()
                                overlap=any(s['product_id']==product and s['strategy_id']==candidate.strategy_id for s in store.active_candidates())
                                if duplicate or overlap: row.update(decision='NO_TRADE',reasons=['DUPLICATE_OR_OVERLAPPING_SIGNAL'])
                                else:
                                    result=qualify(candidate,snapshot,p,self.limits); row.update(decision=result['decision'],reasons=result['reasons'])
                                    # Every research trigger is retained, including fee/risk rejections, for diagnostic markouts.
                                    state=result.get('position')
                                    if state:
                                        store.put('signals',candidate.signal_id,state)
                                        p['cash']=str(D(p['cash'])-D(state['quantity'])*D(state['entry'])-D(state['entry_fee']))
                                        self.mark_equity(store,p)
                                        store.put('events',digest((candidate.signal_id,'OPEN')),dict(event_type='PAPER_OPEN',timestamp=snapshot.as_of,signal_id=candidate.signal_id))
                                    else:
                                        store.put('events',digest((candidate.signal_id,'REJECT')),dict(event_type='SIGNAL_REJECTED',candidate=asdict(candidate),timestamp=snapshot.as_of,reasons=result['reasons']))
                                        store.put('signals',candidate.signal_id,dict(signal_id=candidate.signal_id,product_id=product,strategy_id=candidate.strategy_id,
                                                  rules_version=candidate.rules_version,state='OBSERVATION',opened_at=snapshot.as_of,entry=str(candidate.entry),quantity='1',
                                                  fee=str(self.fees.taker),markouts=[],candidate=asdict(candidate),rejection_reasons=result['reasons']))
                        rows.append(row)
                except Exception as exc:
                    errors[product]=type(exc).__name__+': '+str(exc)
                    if scan: rows.extend(failed_market_rows(product,int(time.time()),errors[product]))
                    self.client.raw=[]
            now=int(time.time()); self.mark_equity(store,p)
            if scan:
                store.record_scan(str(start//300),rows)
                prior=store.read_checkpoint('status') or {}
                store.checkpoint('status',{'pid':os.getpid(),'heartbeat':now,'last_scan':now,'scan_started':start,'successful_markets':successful,
                                         'errors':errors,'cycles':int(prior.get('cycles',0))+1,'observations':len(rows),'fee_age_seconds':now-self.fees.observed_at})
                summarize(store,self.root/'ANALYTICS'/'shadow')
                for h in propose_hypotheses(store):
                    file=self.root/'ANALYTICS'/'shadow'/'hypotheses.jsonl'
                    if not file.exists(): file.write_text(dumps(h)+'\n',encoding='utf-8')
            else:
                status=store.read_checkpoint('status') or {}; status.update(heartbeat=now,pid=os.getpid(),review_errors=errors)
                store.checkpoint('status',status)
            return {'scan':scan,'timestamp':now,'successful_markets':successful,'errors':errors,'observations':len(rows),'active_positions':len(store.active_candidates())}

def scan_once(config_path):
    engine=Engine(config_path=config_path)
    with ProcessLock(engine.db.parent/'runner.lock'): return engine.cycle()

def run(config_path,stop_path):
    engine=Engine(config_path=config_path); stop_path=Path(stop_path)
    with ProcessLock(engine.db.parent/'runner.lock'):
        # A previous intentional stop requires explicit removal by start command.
        if stop_path.exists(): raise RuntimeError('STOP_FLAG_PRESENT')
        next_scan=0; next_review=0
        while not stop_path.exists():
            now=time.time()
            if now>=next_scan:
                print(dumps(engine.cycle()),flush=True); next_scan=next_scan_at(time.time()); next_review=time.time()+60
            elif now>=next_review:
                print(dumps(engine.cycle(scan=False)),flush=True); next_review=time.time()+60
            time.sleep(.5)
        with Store(engine.db) as store:
            s=store.read_checkpoint('status') or {}; s.update(stopped_at=int(time.time()),running=False); store.checkpoint('status',s)

def status(root=ROOT):
    db=Path(root)/'DATA'/'shadow'/'paper.sqlite'
    if not db.exists(): return {'running':False,'reason':'NOT_STARTED'}
    with Store(db) as store:
        result=store.read_checkpoint('status') or {}
        try:
            with ProcessLock(db.parent/'runner.lock'): result['running']=False
        except RuntimeError: result['running']=True
        result['heartbeat_age_seconds']=int(time.time())-int(result.get('heartbeat',0))
        result['active_positions']=len(store.active_candidates()); result['closed_positions']=sum(s['state']=='CLOSED' for s in store.rows('signals'))
        return result

def main():
    parser=argparse.ArgumentParser(description='Coinbase paper research only')
    parser.add_argument('command',choices=['scan','run','status','stop','report','research','replay'])
    parser.add_argument('--days',type=int,default=None)
    args=parser.parse_args(); config=ROOT/'CONFIG'/'SHADOW_CONFIG.json'; stop=ROOT/'DATA'/'shadow'/'STOP'
    if args.command=='scan': print(dumps(scan_once(config)))
    elif args.command=='run': run(config,stop)
    elif args.command=='status': print(dumps(status()))
    elif args.command=='stop': stop.parent.mkdir(parents=True,exist_ok=True); stop.write_text('user stop\n'); print('Stop requested; verify status after current read finishes.')
    elif args.command=='report':
        with Store(ROOT/'DATA'/'shadow'/'paper.sqlite') as store: print(summarize(store,ROOT/'ANALYTICS'/'shadow'))
    elif args.command=='research':
        from .history import research
        research(json.loads(config.read_text()),ROOT,args.days)
    elif args.command=='replay':
        from .historical_replay import run_replay
        run_replay(ROOT,args.days or 14)
