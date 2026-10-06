"""Conservative synthetic fills and independent markouts, never live orders."""
from dataclasses import asdict
from decimal import Decimal as D, ROUND_FLOOR
from .models import PaperEvent, digest

def fee_hurdle(entry_fee,exit_fee): return (1+entry_fee)/(1-exit_fee)-1

def net_return(entry,exit_price,entry_fee,exit_fee):
    return (exit_price*(1-exit_fee)-entry*(1+entry_fee))/entry

def maker_fill_policy(): return 'NOT_SIMULATED'

def walk_depth(levels,requested):
    remaining=requested; cost=D(0); filled=D(0)
    for price,size in levels:
        take=min(size,remaining)
        if take<=0: break
        cost+=take*price; filled+=take; remaining-=take
    return filled,cost/filled if filled else D(0)

def bar_exit(bar,stop,target):
    if bar.low<=stop: return ('STOP_GAP',bar.open) if bar.open<stop else ('STOP',stop)
    if bar.high>=target: return ('TARGET',target)
    return None

def risk_state(p,limits):
    equity=D(p['equity']); dd=(1-equity/D(p['peak']))*100
    weekly=(1-equity/D(p['weekly_start']))*100; daily=(1-equity/D(p['daily_start']))*100; streak=int(p['loss_streak'])
    pd=limits['portfolio_drawdown_pct']; wd=limits['weekly_drawdown_pct']; ls=limits['loss_streak']; state='NORMAL'; reasons=[]
    if dd>=D(str(pd['suspend_review'])): state='SUSPENDED_REVIEW'; reasons.append('PORTFOLIO_SUSPEND')
    elif dd>=D(str(pd['defensive'])): state='DEFENSIVE_NO_NEW_RESEARCH_RISK'; reasons.append('PORTFOLIO_DEFENSIVE')
    elif dd>=D(str(pd['risk_reduction'])) or streak>=ls['half_risk']: state='REDUCED_RISK'; reasons.append('DRAWDOWN_OR_STREAK_REDUCTION')
    elif dd>=D(str(pd['warning'])) or weekly>=D(str(wd['soft'])) or streak>=ls['reassess']: state='CAUTION'; reasons.append('REASSESS_AND_INCREASE_SELECTIVITY')
    if weekly>=D(str(wd['hard'])) or daily>=D(str(limits['daily_loss_limit_pct'])) or streak>=ls['halt_new_entries'] or p.get('halted'):
        state='HALTED' if state!='SUSPENDED_REVIEW' else state; reasons.append('LOSS_LIMIT_OR_REVIEW_HALT')
    return dict(state=state,reasons=reasons,minimum_score=80 if state!='NORMAL' else 70)

def allowed_risk(p,limits,strategy):
    equity=D(p['equity']); peak=D(p['peak']); daily=D(p['daily_start']); weekly=D(p['weekly_start'])
    if equity<=0: return D(0)
    dd=(1-equity/peak)*100; daily_loss=(1-equity/daily)*100; weekly_loss=(1-equity/weekly)*100
    streak=int(p['loss_streak'])
    if p.get('halted') or streak>=limits['loss_streak']['halt_new_entries'] or daily_loss>=D(str(limits['daily_loss_limit_pct'])) or dd>=D(str(limits['portfolio_drawdown_pct']['defensive'])): return D(0)
    if weekly_loss>=D(str(limits['weekly_drawdown_pct']['hard'])): return D(0)
    risk=min(D(str(limits['risk_per_trade_pct']['default'])),D(str(limits['risk_per_trade_pct']['absolute_max'])))/100
    if strategy.startswith('RANGE'): risk=min(risk,D('.0035'))
    if strategy.startswith('EXHAUSTION'): risk=min(risk,D('.0025'))
    if streak>=limits['loss_streak']['half_risk'] or dd>=D(str(limits['portfolio_drawdown_pct']['risk_reduction'])): risk/=2
    cluster=D(p.get('cluster_risk_pct','1.0'))/100*equity-D(p.get('open_risk','0'))
    daily_available=daily*D(str(limits['daily_loss_limit_pct']))/100-max(D(0),daily-equity)-D(p.get('open_risk','0'))
    return max(D(0),min(risk,cluster/equity,daily_available/equity))

def qualify(candidate,snapshot,portfolio,limits):
    fee=snapshot.fees.taker
    risk_pct=allowed_risk(portfolio,limits,candidate.strategy_id)
    if risk_pct<=0: return {'decision':'NO_TRADE','reasons':['PORTFOLIO_RISK_GATE']}
    if candidate.score<risk_state(portfolio,limits)['minimum_score']: return {'decision':'NO_TRADE','reasons':['CAUTION_SELECTIVITY_GATE']}
    if snapshot.as_of>candidate.expires_at: return {'decision':'NO_TRADE','reasons':['EXPIRED']}
    unit_risk=candidate.entry-candidate.stop+fee*(candidate.entry+candidate.stop)+candidate.entry*D('.001')
    unit_reward=candidate.target-candidate.entry-fee*(candidate.target+candidate.entry)-candidate.entry*D('.001')
    minimum=D(portfolio.get('minimum_net_reward_risk','1.5'))
    if unit_risk<=0 or unit_reward/unit_risk<minimum: return {'decision':'NO_TRADE','reasons':['COSTS_CONSUME_EDGE']}
    increment=D(snapshot.product.get('base_increment','0.00000001'))
    if increment<=0: raise ValueError('INVALID_INCREMENT')
    qty=min(D(portfolio['equity'])*risk_pct/unit_risk,D(portfolio['cash'])/(candidate.entry*(1+fee)))
    qty=(qty/increment).to_integral_value(rounding=ROUND_FLOOR)*increment
    filled,actual=walk_depth(snapshot.book.asks,qty)
    filled=(filled/increment).to_integral_value(rounding=ROUND_FLOOR)*increment
    if filled<=0: return {'decision':'NO_TRADE','reasons':['NO_LIQUIDITY']}
    _,actual=walk_depth(snapshot.book.asks,filled)
    actual_unit_risk=actual-candidate.stop+fee*(actual+candidate.stop)+actual*D('.001')
    actual_reward=candidate.target-actual-fee*(candidate.target+actual)-actual*D('.001')
    if actual_reward/actual_unit_risk<minimum or actual_unit_risk*filled>D(portfolio['equity'])*risk_pct or actual*filled*(1+fee)>D(portfolio['cash']):
        return {'decision':'NO_TRADE','reasons':['DEPTH_COST_OR_RISK_GATE']}
    if filled<D(snapshot.product.get('base_min_size','0')) or actual*filled<D(snapshot.product.get('quote_min_size','1')):
        return {'decision':'NO_TRADE','reasons':['PRODUCT_MINIMUM']}
    state=dict(candidate=asdict(candidate),signal_id=candidate.signal_id,product_id=candidate.product_id,strategy_id=candidate.strategy_id,
               rules_version=candidate.rules_version,state='ACTIVE',opened_at=snapshot.as_of,last_review=snapshot.as_of,
               entry=str(actual),quantity=str(filled),requested_quantity=str(qty),fee=str(fee),fee_snapshot=asdict(snapshot.fees),
               entry_fee=str(actual*filled*fee),initial_risk=str(actual_unit_risk*filled),stop=str(candidate.stop),target=str(candidate.target),
               due_at=snapshot.as_of+candidate.primary_minutes*60,mae='0',mfe='0',uncertain=False,markouts=[])
    return {'decision':'PAPER_FILLED','reasons':['TAKER_DEPTH_SIMULATION'],'position':state}

def advance(candidate,state,snapshot):
    if state['state']!='ACTIVE': return ()
    now=snapshot.as_of; stop=D(state['stop']); target=D(state['target']); entry=D(state['entry'])
    quantity=D(state['quantity']); fee=D(state['fee']); last=int(state['last_review'])
    if now-last>120: state['uncertain']=True
    cursor=int(state.get('last_bar_end',state['opened_at']))
    bars=[b for b in snapshot.candles.get(60,()) if b.start+b.seconds>cursor and b.start+b.seconds<=now]
    if bars:
        if bars[0].start>cursor or bars[0].start<int(state['opened_at']): state['uncertain']=True
        if any(b.start-a.start!=60 for a,b in zip(bars,bars[1:])): state['uncertain']=True
        state['last_bar_end']=bars[-1].start+60
    elif now-cursor>90: state['uncertain']=True
    if bars:
        state['mae']=str(min(D(state['mae']),min(b.low for b in bars)/entry-1))
        state['mfe']=str(max(D(state['mfe']),max(b.high for b in bars)/entry-1))
    modeled=state.get('pending_exit')
    for bar in bars:
        result=bar_exit(bar,stop,target)
        if result:
            if not modeled: modeled={'reason':result[0],'price':str(result[1]),'bar_end':bar.start+60}
            break
    if modeled: state['pending_exit']=modeled
    filled,price=walk_depth(snapshot.book.bids,quantity)
    if filled<quantity:
        state['uncertain']=True; state['last_review']=now
        return (PaperEvent(digest((state['signal_id'],now,'EXIT_LIQUIDITY')),state['signal_id'],now,'EXIT_LIQUIDITY_INSUFFICIENT',{'requested':str(quantity),'available':str(filled)}),)
    reason=None
    if modeled:
        reason=modeled['reason']; modeled_price=D(modeled['price'])
        # Delayed quotes cannot establish a historical fill: adverse price wins.
        price=min(price,modeled_price)*(1-D('.001'))
        state['uncertain']=True
    elif price<=stop: reason='STOP_OBSERVED'
    elif price>=target: reason='TARGET_OBSERVED'
    elif now>=int(state['due_at']): reason='TIME_EXIT'
    state['last_review']=now
    if not reason: return ()
    proceeds=quantity*price*(1-fee)
    cost=quantity*entry+D(state['entry_fee'])
    pnl=proceeds-cost
    state.update(state='CLOSED',closed_at=now,exit=str(price),exit_fee=str(quantity*price*fee),net_pnl=str(pnl),
                 realized_r=str(pnl/D(state['initial_risk'])),exit_reason=reason,process_result='PROCESS_PASS',execution_evidence='UNCERTAIN_MODELED' if state['uncertain'] else 'OBSERVED_QUOTES',
                 duration_seconds=now-int(state['opened_at']))
    return (PaperEvent(digest((state['signal_id'],'CLOSED')),state['signal_id'],now,'CLOSED',dict(state)),)

def markout(candidate,horizon,snapshot):
    due=int(candidate['opened_at'])+horizon*60
    error=snapshot.as_of-due
    result=dict(signal_id=candidate['signal_id'],product_id=candidate['product_id'],strategy_id=candidate['strategy_id'],horizon_minutes=horizon,due_at=due,observed_at=snapshot.as_of,
                rules_version=candidate.get('rules_version','LEGACY_UNSPECIFIED'),source='FORWARD_QUOTE_MARKOUT',independent_trade=False)
    if error<0: return result|{'status':'NOT_DUE'}
    if error>30: return result|{'status':'UNAVAILABLE_LATE'}
    qty,exit_price=walk_depth(snapshot.book.bids,D(candidate['quantity']))
    if qty<D(candidate['quantity']): return result|{'status':'INSUFFICIENT_DEPTH'}
    return result|{'status':'OBSERVED','net_return':str(net_return(D(candidate['entry']),exit_price,D(candidate['fee']),D(candidate['fee'])))}
