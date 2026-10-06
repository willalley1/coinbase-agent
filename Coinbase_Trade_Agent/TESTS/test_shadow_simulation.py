import unittest
from decimal import Decimal as D
try:
    from SHADOW import simulation as s
except ImportError: s=None

class SimulationTests(unittest.TestCase):
    def setUp(self): self.assertIsNotNone(s,'cost-aware paper simulation must exist')

    def test_fee_math(self):
        self.assertAlmostEqual(float(s.fee_hurdle(D('.009'),D('.009'))),.01816347124,places=10)
        self.assertEqual(s.net_return(D(100),D(101),D('.009'),D('.009')),D('-.00809'))

    def test_depth_partial_fill(self):
        qty,price=s.walk_depth(((D(100),D(1)),(D(101),D(2))),D(4))
        self.assertEqual(qty,D(3)); self.assertEqual(price,D(302)/3)

    def test_ambiguous_stop_first_and_gap(self):
        from SHADOW.models import Candle
        bar=Candle(0,60,D(100),D(105),D(95),D(102),D(1))
        self.assertEqual(s.bar_exit(bar,D(98),D(104)),('STOP',D(98)))
        gap=Candle(60,60,D(90),D(95),D(88),D(94),D(1))
        self.assertEqual(s.bar_exit(gap,D(98),D(104)),('STOP_GAP',D(90)))

    def test_loss_limits_and_correlation(self):
        import json
        from pathlib import Path
        limits=json.loads(Path('CONFIG/HARD_LIMITS.json').read_text())
        p=dict(equity='10000',peak='10000',daily_start='10000',weekly_start='10000',loss_streak=3,open_risk='0',cash='10000')
        self.assertEqual(s.allowed_risk(p,limits,'TREND_PULLBACK_shadow_r1'),D('.0025'))
        self.assertEqual(s.allowed_risk(p|{'loss_streak':4},limits,'TREND_PULLBACK_shadow_r1'),D(0))
        self.assertEqual(s.allowed_risk(p|{'equity':'9850'},limits,'TREND_PULLBACK_shadow_r1'),D(0))
        self.assertEqual(s.allowed_risk(p|{'open_risk':'100'},limits,'TREND_PULLBACK_shadow_r1'),D(0))

    def test_limit_touch_not_fill(self):
        self.assertEqual(s.maker_fill_policy(), 'NOT_SIMULATED')

    def test_fill_and_close_accounts_for_both_fees(self):
        from SHADOW.models import Candidate,MarketSnapshot,Book,FeeSnapshot
        import json
        from pathlib import Path
        limits=json.loads(Path('CONFIG/HARD_LIMITS.json').read_text())
        fees=FeeSnapshot(D('.001'),D('.001'),0,'test')
        book=Book('BTC-USD',0,0,((D('99.99'),D(1000)),),((D(100),D(1000)),))
        product={'base_increment':'.01','base_min_size':'.01','quote_min_size':'1'}
        snap=MarketSnapshot('BTC-USD',0,{},book,product,fees)
        candidate=Candidate('signal','BTC-USD','TREND_PULLBACK_shadow_r1','test',0,D(100),D(98),D(106),60,60,75,())
        p=dict(equity='10000',peak='10000',daily_start='10000',weekly_start='10000',loss_streak=0,open_risk='0',cash='10000')
        result=s.qualify(candidate,snap,p,limits)
        self.assertEqual(result['decision'],'PAPER_FILLED')
        state=result['position']
        later=MarketSnapshot('BTC-USD',60,{},Book('BTC-USD',60,60,((D(106),D(1000)),),((D('106.01'),D(1000)),)),product,fees)
        events=s.advance(candidate,state,later)
        self.assertEqual(state['state'],'CLOSED')
        self.assertEqual(state['exit_reason'],'TARGET_OBSERVED')
        self.assertEqual(D(state['net_pnl'])/D(state['quantity']),D('5.794'))
        self.assertEqual(len(events),1)
        self.assertEqual(s.advance(candidate,state,later),())

    def test_markout_late_unavailable_and_not_independent(self):
        from SHADOW.models import MarketSnapshot,Book,FeeSnapshot
        state=dict(signal_id='one',product_id='BTC-USD',strategy_id='trend',opened_at=0,entry='100',quantity='1',fee='.009')
        snap=MarketSnapshot('BTC-USD',100,{},Book('BTC-USD',100,100,((D(101),D(2)),),()),{},FeeSnapshot(D('.009'),D('.009'),0,'test'))
        row=s.markout(state,1,snap)
        self.assertEqual(row['status'],'UNAVAILABLE_LATE')
        self.assertFalse(row['independent_trade'])

    def test_off_boundary_review_does_not_skip_stop_candle(self):
        from SHADOW.models import MarketSnapshot,Book,FeeSnapshot,Candle
        state=dict(signal_id='one',product_id='BTC-USD',strategy_id='trend',state='ACTIVE',opened_at=10,last_review=10,
                   entry='100',quantity='1',fee='.001',entry_fee='.1',initial_risk='2.298',stop='98',target='106',due_at=3610,mae='0',mfe='0',uncertain=False)
        bar=Candle(0,60,D(100),D(102),D(97),D(100),D(10))
        snap=MarketSnapshot('BTC-USD',70,{60:(bar,)},Book('BTC-USD',70,70,((D(100),D(10)),),((D('100.01'),D(10)),)),{},FeeSnapshot(D('.001'),D('.001'),0,'test'))
        s.advance(None,state,snap)
        self.assertEqual(state['state'],'CLOSED')
        self.assertTrue(state['uncertain'])
        self.assertLess(D(state['mae']),0)

    def test_soft_risk_states_require_greater_selectivity(self):
        import json
        from pathlib import Path
        limits=json.loads(Path('CONFIG/HARD_LIMITS.json').read_text())
        self.assertTrue(hasattr(s,'risk_state'),'soft risk responses must be explicit')
        p=dict(equity='9650',peak='10000',daily_start='9650',weekly_start='10000',loss_streak=0,open_risk='0',cash='9650')
        self.assertEqual(s.risk_state(p,limits)['state'],'CAUTION')
        self.assertEqual(s.risk_state(p,limits)['minimum_score'],80)
        p.update(equity='9000',daily_start='9000',weekly_start='9000')
        self.assertEqual(s.risk_state(p,limits)['state'],'SUSPENDED_REVIEW')

    def test_stop_obligation_survives_insufficient_depth(self):
        from SHADOW.models import MarketSnapshot,Book,FeeSnapshot,Candle
        state=dict(signal_id='one',product_id='BTC-USD',strategy_id='trend',state='ACTIVE',opened_at=0,last_review=0,entry='100',quantity='2',fee='.001',
                   entry_fee='.2',initial_risk='4.596',stop='98',target='106',due_at=3600,mae='0',mfe='0',uncertain=False)
        bar=Candle(0,60,D(100),D(101),D(97),D(100),D(10)); fees=FeeSnapshot(D('.001'),D('.001'),0,'test')
        first=MarketSnapshot('BTC-USD',70,{60:(bar,)},Book('BTC-USD',70,70,((D(100),D(1)),),((D(101),D(10)),)),{},fees)
        s.advance(None,state,first)
        second=MarketSnapshot('BTC-USD',130,{},Book('BTC-USD',130,130,((D(100),D(10)),),((D(101),D(10)),)),{},fees)
        s.advance(None,state,second)
        self.assertEqual(state['state'],'CLOSED')
        self.assertTrue(state['exit_reason'].startswith('STOP'))

if __name__=='__main__': unittest.main()
