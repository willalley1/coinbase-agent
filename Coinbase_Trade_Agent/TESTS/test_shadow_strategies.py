import unittest
from decimal import Decimal as D
try:
    from SHADOW import strategies as s
except ImportError: s=None

class StrategyTests(unittest.TestCase):
    def setUp(self): self.assertIsNotNone(s,'six deterministic research detectors must exist')

    def test_each_detector_has_positive_and_negative_fixture(self):
        cases=[
            ('TREND_PULLBACK',dict(uptrend=True,pullback=True,reclaim=True,rv=1.3)),
            ('MOMENTUM_CONTINUATION',dict(uptrend=True,impulse=True,flag=True,flag_break=True,not_extended=True,rv=1.6)),
            ('CONFIRMED_BREAKOUT',dict(compressed=True,breakout=True,h1_positive=True,rv=1.6)),
            ('RANGE_MEAN_REVERSION',dict(range_regime=True,near_floor=True,oversold=True,reclaim=True)),
            ('EXHAUSTION_REVERSAL',dict(exhausted=True,reversal=True,rv=1.6)),
            ('SWING_TREND',dict(daily_up=True,h4_up=True,swing_pullback=True,swing_reclaim=True,swing_rv=1.3)),
        ]
        for name,f in cases:
            with self.subTest(name=name):
                self.assertTrue(s.condition(name,{'disorder':False}|f))
                self.assertFalse(s.condition(name,{'disorder':True}|f))
                self.assertFalse(s.condition(name,{'disorder':False}))

    def test_insufficient_context_gives_six_rejections(self):
        from SHADOW.models import MarketSnapshot,Book,FeeSnapshot
        snap=MarketSnapshot('BTC-USD',1000,{},Book('BTC-USD',1000,1000,((D(10),D(1)),),((D(11),D(1)),)),{},FeeSnapshot(D('.005'),D('.009'),1000,'test'))
        rows=s.evaluate(snap,{})
        self.assertEqual(len(rows),6)
        self.assertTrue(all(r['decision']=='NO_TRADE' for r in rows))

    def test_no_lookahead_and_features(self):
        from SHADOW.models import Candle
        bars=tuple(Candle(i*300,300,D(100+i),D(102+i),D(99+i),D(101+i),D(10)) for i in range(120))
        f=s.features(bars)
        self.assertGreater(f['ema20'],f['ema50'])
        self.assertEqual(f['prior_high'],D(220))
        self.assertEqual(s.closed(bars,36000),bars)
        self.assertEqual(len(s.closed(bars,35999)),119)

if __name__=='__main__': unittest.main()
