"""Frozen research variants; scores are uncalibrated rankings, not probabilities."""
from decimal import Decimal as D
from .models import Candidate, digest

NAMES=('TREND_PULLBACK','MOMENTUM_CONTINUATION','CONFIRMED_BREAKOUT','RANGE_MEAN_REVERSION','EXHAUSTION_REVERSAL','SWING_TREND')

def closed(bars,as_of):
    return tuple(c for c in bars if c.start+c.seconds<=as_of)

def ema(values,n):
    v=values[0]; alpha=D(2)/D(n+1)
    for x in values[1:]: v+=alpha*(x-v)
    return v

def features(bars):
    if len(bars)<100: raise ValueError('INSUFFICIENT_HISTORY')
    closes=[c.close for c in bars]
    tr=[max(c.high-c.low,abs(c.high-bars[i-1].close),abs(c.low-bars[i-1].close)) for i,c in enumerate(bars) if i]
    atr=sum(tr[:14])/14
    for v in tr[14:]: atr=(atr*13+v)/14
    changes=[b-a for a,b in zip(closes,closes[1:])]
    gain=sum(max(D(0),x) for x in changes[:14])/14
    loss=sum(max(D(0),-x) for x in changes[:14])/14
    for x in changes[14:]:
        gain=(gain*13+max(D(0),x))/14; loss=(loss*13+max(D(0),-x))/14
    rsi=D(100) if not loss else 100-100/(1+gain/loss)
    volume=sum(c.volume for c in bars[-21:-1])/20
    return dict(ema20=ema(closes,20),ema50=ema(closes,50),atr=atr,rsi=rsi,
                prior_high=max(c.high for c in bars[-21:-1]),prior_low=min(c.low for c in bars[-21:-1]),
                rv=bars[-1].volume/volume if volume else D(0),true_range=tr[-1])

def condition(name,f):
    if f.get('disorder',True): return False
    requirements={
        'TREND_PULLBACK':('uptrend','pullback','reclaim'),
        'MOMENTUM_CONTINUATION':('uptrend','impulse','flag','flag_break','not_extended'),
        'CONFIRMED_BREAKOUT':('compressed','breakout','h1_positive'),
        'RANGE_MEAN_REVERSION':('range_regime','near_floor','oversold','reclaim'),
        'EXHAUSTION_REVERSAL':('exhausted','reversal'),
        'SWING_TREND':('daily_up','h4_up','swing_pullback','swing_reclaim'),
    }
    valid=all(f.get(key,False) for key in requirements[name])
    rv=D(str(f.get('swing_rv' if name=='SWING_TREND' else 'rv',0)))
    threshold=D('1.2') if name in ('TREND_PULLBACK','SWING_TREND') else D('1.5')
    return bool(valid and (name=='RANGE_MEAN_REVERSION' or rv>=threshold))

def context(snapshot):
    bars={sec:closed(snapshot.candles.get(sec,()),snapshot.as_of) for sec in (300,900,3600,14400,86400)}
    fs={sec:features(v) for sec,v in bars.items()}
    b=bars[300]; m=fs[300]; prev=features(b[:-1]); a=m['atr']
    if a<=0: raise ValueError('ZERO_ATR')
    h=fs[3600]; q=fs[14400]; d=fs[86400]; fifteen=bars[900][:-1]; p=features(fifteen)
    last=b[-1]; previous=b[-2]; width=m['prior_high']-m['prior_low']
    flag=b[-4:-1]
    impulse=any(c.close-c.open>=D('1.5')*prev['atr'] for c in b[-10:-4])
    range_avg=sum(c.high-c.low for c in b[-21:-1])/20
    f=dict(
        disorder=a/last.close>D('.02') or m['true_range']>3*prev['atr'],
        uptrend=h['ema20']>h['ema50'] and bars[3600][-1].close>h['ema20'] and q['ema20']>q['ema50'],
        pullback=fifteen[-1].low<=p['ema20']+D('.5')*p['atr'] and fifteen[-1].close>=p['ema50'],
        reclaim=last.close>previous.high,rv=m['rv'],
        impulse=impulse,flag=max(c.high for c in flag)-min(c.low for c in flag)<=D('1.5')*prev['atr'],
        flag_break=last.close>max(c.high for c in flag),not_extended=last.close<=m['ema20']+3*a,
        compressed=width<=6*prev['atr'] and sum(c.high-c.low for c in b[-6:-1])/5<=D('.8')*range_avg,
        breakout=last.close>m['prior_high']+D('.1')*prev['atr'],h1_positive=bars[3600][-1].close>=h['ema20'],
        range_regime=abs(h['ema20']/h['ema50']-1)<=D('.003') and width>=4*a,
        near_floor=previous.close<=m['prior_low']+D('.2')*width,oversold=prev['rsi']<=35,
        exhausted=previous.close<prev['ema20']-2*prev['atr'] and prev['rsi']<=25,
        reversal=last.close>max(c.high for c in b[-4:-1]),
        daily_up=d['ema20']>d['ema50'],h4_up=q['ema20']>q['ema50'],
        swing_pullback=bars[14400][-2].low<=features(bars[14400][:-1])['ema20']+D('.5')*features(bars[14400][:-1])['atr'] and bars[14400][-2].close>=features(bars[14400][:-1])['ema50'],
        swing_reclaim=bars[3600][-1].close>bars[3600][-2].high,swing_rv=h['rv'])
    regime='DISORDER' if f['disorder'] else 'UPTREND' if f['uptrend'] else 'RANGE' if f['range_regime'] else 'MIXED_OR_BEARISH'
    return bars,fs,f,regime

def evaluate(snapshot,rules):
    version=rules.get('version','shadow_r1')+':'+digest(rules)[:12]
    def rejection(name,why,regime='UNKNOWN'):
        return dict(strategy_id=name+'_shadow_r1',rules_version=version,decision='NO_TRADE',reasons=[why],regime=regime)
    try: bars,fs,f,regime=context(snapshot)
    except (ValueError,KeyError,IndexError): return tuple(rejection(n,'INSUFFICIENT_OR_INVALID_CONTEXT') for n in NAMES)
    result=[]
    for name in NAMES:
        if not condition(name,f): result.append(rejection(name,'SETUP_NOT_CONFIRMED',regime)); continue
        sec=3600 if name=='SWING_TREND' else 300
        trigger=bars[sec][-1]
        entry=snapshot.book.asks[0][0] if snapshot.book.asks else trigger.close
        if entry>trigger.close+D('.25')*fs[sec]['atr']:
            result.append(rejection(name,'ENTRY_EXTENDED',regime)); continue
        stop=min(c.low for c in bars[14400 if name=='SWING_TREND' else 300][-6:-1])-D('.25')*fs[14400 if name=='SWING_TREND' else 300]['atr']
        if name=='RANGE_MEAN_REVERSION': stop=fs[300]['prior_low']-D('.25')*fs[300]['atr']
        target=entry+2*(entry-stop)
        if name=='RANGE_MEAN_REVERSION': target=(fs[300]['prior_low']+fs[300]['prior_high'])/2
        if name=='EXHAUSTION_REVERSAL': target=fs[300]['ema20']
        if not D(0)<stop<entry<target:
            result.append(rejection(name,'INVALID_STRUCTURE',regime)); continue
        score=70+5*int(f['daily_up'])+5*int(f['rv']>=2)
        signal_id=digest((snapshot.product_id,name,trigger.start,version))
        candidate=Candidate(signal_id,snapshot.product_id,name+'_shadow_r1',version,trigger.start,entry,stop,target,snapshot.as_of+60,
                            2880 if name=='SWING_TREND' else 60,score,('UNVALIDATED_RESEARCH',))
        result.append(dict(strategy_id=candidate.strategy_id,rules_version=version,decision='CANDIDATE',reasons=['CONFIRMED_RESEARCH_TRIGGER'],regime=regime,candidate=candidate))
    return tuple(result)
