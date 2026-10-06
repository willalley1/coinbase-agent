import unittest
from decimal import Decimal as D
try:
    from SHADOW import history as h
except ImportError: h=None

class HistoryTests(unittest.TestCase):
    def setUp(self): self.assertIsNotNone(h,'historical holding-window research must exist')

    def test_nonoverlapping_windows_and_fees(self):
        from SHADOW.models import Candle
        bars=[Candle(i*60,60,D(100+i),D(100+i),D(100+i),D(100+i),D(1)) for i in range(11)]
        rows=h.window_outcomes('BTC-USD',bars,2,D('.009'))
        self.assertEqual(len(rows),4)
        self.assertEqual(rows[0]['start'],60)
        self.assertAlmostEqual(float(rows[0]['net_return']),.001623762376,places=10)
        self.assertTrue(all(not r['executable_trade'] for r in rows))

    def test_missing_bar_blocks_window(self):
        from SHADOW.models import Candle
        bars=[Candle(i*60,60,D(100),D(100),D(100),D(100),D(1)) for i in [0,1,3,4,5]]
        rows=h.window_outcomes('BTC-USD',bars,2,D('.009'))
        self.assertEqual([r['start'] for r in rows],[180])

if __name__=='__main__': unittest.main()
