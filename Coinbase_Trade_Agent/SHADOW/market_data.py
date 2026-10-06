"""GET-only public Advanced Trade data; no credentials accepted."""
from datetime import datetime
from decimal import Decimal as D
import json
import re
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from .models import Candle, Book, MarketSnapshot

GRANULARITIES = {60:'ONE_MINUTE',300:'FIVE_MINUTE',900:'FIFTEEN_MINUTE',3600:'ONE_HOUR',14400:'FOUR_HOUR',86400:'ONE_DAY'}

def parse_candles(raw, seconds, as_of):
    bars = {}
    for row in raw:
        t = int(row['start'])
        vals = [D(row[k]) for k in ('open','high','low','close','volume')]
        o,h,l,c,v = vals
        if not all(x.is_finite() for x in vals) or min(o,h,l,c)<=0 or v<0 or not l<=min(o,c)<=max(o,c)<=h:
            raise ValueError('INVALID_OHLCV')
        if t % seconds: raise ValueError('UNALIGNED_CANDLE')
        bar = Candle(t,seconds,o,h,l,c,v)
        if t in bars and bars[t]!=bar: raise ValueError('CONFLICTING_CANDLE')
        if t+seconds<=as_of: bars[t]=bar
    return tuple(bars[t] for t in sorted(bars))

def candle_errors(starts, seconds, as_of):
    if not starts: return ['MISSING_CANDLES']
    errors=[]
    if any(b-a!=seconds for a,b in zip(starts,starts[1:])): errors.append('CANDLE_GAP')
    expected=((as_of-10)//seconds-1)*seconds
    if starts[-1]<expected: errors.append('STALE_CANDLES')
    return errors

def freshness_errors(source_time,fetched_at,fee_time,as_of):
    errors=[]
    if as_of-source_time>30 or as_of-fetched_at>30 or source_time>as_of+5: errors.append('STALE_BOOK')
    if as_of-fee_time>86400 or fee_time>as_of+5: errors.append('STALE_FEES')
    return errors

def execution_errors(snapshot):
    b=snapshot.book
    errors=[e for e in freshness_errors(b.source_time,b.fetched_at,snapshot.fees.observed_at,snapshot.as_of) if e!='STALE_FEES']
    if b.product_id!=snapshot.product_id: errors.append('BOOK_IDENTITY')
    if not b.bids or not b.asks or b.bids[0][0]>=b.asks[0][0]: errors.append('INVALID_BOOK')
    for levels in (b.bids,b.asks):
        if any(not p.is_finite() or not q.is_finite() or p<=0 or q<=0 for p,q in levels): errors.append('INVALID_BOOK_LEVEL')
    return tuple(sorted(set(errors)))

def validate_snapshot(snapshot):
    errors=freshness_errors(snapshot.book.source_time,snapshot.book.fetched_at,snapshot.fees.observed_at,snapshot.as_of)+list(execution_errors(snapshot))
    for sec in GRANULARITIES:
        bars=snapshot.candles.get(sec,())
        if len(bars)<100: errors.append('INSUFFICIENT_HISTORY_'+str(sec))
        errors.extend(e+'_'+str(sec) for e in candle_errors([c.start for c in bars],sec,snapshot.as_of))
    b=snapshot.book
    if not b.bids or not b.asks or b.bids[0][0]>=b.asks[0][0]: errors.append('INVALID_BOOK')
    if snapshot.product.get('product_type')!='SPOT' or snapshot.product.get('status','').lower()!='online': errors.append('PRODUCT_NOT_TRADABLE')
    if snapshot.product.get('trading_disabled') or snapshot.product.get('view_only'): errors.append('PRODUCT_DISABLED')
    if snapshot.product.get('_metadata_error') or snapshot.as_of-snapshot.product.get('_fetched_at',snapshot.as_of)>300: errors.append('STALE_PRODUCT_METADATA')
    if not (D(0)<=snapshot.fees.maker<D(1) and D(0)<=snapshot.fees.taker<D(1)): errors.append('INVALID_FEES')
    return tuple(sorted(set(errors)))

class CoinbasePublicClient:
    base='https://api.coinbase.com/api/v3/brokerage/market/'
    def __init__(self):
        self.last_request=0
        self.raw=[]

    def request(self,path,params):
        if not re.fullmatch(r'products(?:/[A-Z0-9]+-[A-Z0-9]+(?:/candles)?)?|product_book',path):
            raise ValueError('PUBLIC_GET_ALLOWLIST')
        url=self.base+path+('?' + urlencode(params) if params else '')
        for attempt in range(3):
            time.sleep(max(0,.34-(time.monotonic()-self.last_request)))
            self.last_request=time.monotonic()
            try:
                with urlopen(Request(url,headers={'User-Agent':'CoinbaseShadowResearch/1.0','Cache-Control':'no-cache'}),timeout=15) as response:
                    data=json.load(response)
                self.raw.append({'url':url,'fetched_at':int(time.time()),'response':data})
                return data
            except HTTPError as exc:
                if exc.code not in (429,500,502,503,504) or attempt==2: raise
                delay=min(10,float(exc.headers.get('Retry-After',2**attempt)))
            except (URLError,TimeoutError):
                if attempt==2: raise
                delay=2**attempt
            time.sleep(delay)

    def get_product(self,product_id):
        return self.request('products/'+product_id,{})

    def get_candles(self,product_id,seconds,start,end):
        if seconds not in GRANULARITIES or end-start>350*seconds: raise ValueError('CANDLE_WINDOW')
        raw=self.request('products/'+product_id+'/candles',{'start':start,'end':end,'granularity':GRANULARITIES[seconds],'limit':350})
        return tuple(c for c in parse_candles(raw.get('candles',[]),seconds,end) if c.start>=start)

    def get_book(self,product_id):
        raw=self.request('product_book',{'product_id':product_id,'limit':50})['pricebook']
        if raw.get('product_id')!=product_id: raise ValueError('BOOK_IDENTITY')
        fetched=int(time.time())
        stamp=int(datetime.fromisoformat(raw['time'].replace('Z','+00:00')).timestamp())
        def levels(side,reverse):
            values=tuple(sorted(((D(v['price']),D(v['size'])) for v in raw.get(side,[])),reverse=reverse))
            if any(not p.is_finite() or not s.is_finite() or p<=0 or s<=0 for p,s in values): raise ValueError('INVALID_BOOK_LEVEL')
            return values
        return Book(product_id,stamp,fetched,levels('bids',True),levels('asks',False))
