import unittest
from decimal import Decimal as D
try:
    from SHADOW import historical_replay as r
except ImportError: r=None

class ReplayTests(unittest.TestCase):
    def setUp(self): self.assertIsNotNone(r,'chronological strategy replay must exist')

    def test_context_never_uses_future_close(self):
        from SHADOW.models import Candle
        bars=tuple(Candle(i*300,300,D(10),D(11),D(9),D(10),D(1)) for i in range(130))
        self.assertEqual(len(r.context_at(bars,36000)),120)
        self.assertEqual(r.context_at(bars,36000)[-1].start,35700)

    def test_outcome_gap_is_unavailable(self):
        from SHADOW.models import Candle
        bars={i*60:Candle(i*60,60,D(100),D(100),D(100),D(100),D(1)) for i in [0,1,3,4]}
        self.assertIsNone(r.signal_outcome(bars,0,3,D('.009')))

if __name__=='__main__': unittest.main()
