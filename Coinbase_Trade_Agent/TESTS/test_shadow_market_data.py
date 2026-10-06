import unittest
from decimal import Decimal as D
try:
    from SHADOW import market_data as md
except ImportError:
    md = None

class MarketTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(md, 'read-only market adapter must exist')

    def test_closed_sorted_unique_candles(self):
        raw = [dict(start=str(t), open='10', high='11', low='9', close='10', volume='2') for t in [120, 60, 0, 60]]
        bars = md.parse_candles(raw, 60, 180)
        self.assertEqual([c.start for c in bars], [0, 60, 120])
        self.assertEqual(len(md.parse_candles(raw, 60, 179)), 2)

    def test_invalid_ohlc_rejected(self):
        for bad in [dict(low='12'), dict(close='0'), dict(volume='-1')]:
            raw = dict(start='0', open='10', high='11', low='9', close='10', volume='2') | bad
            with self.assertRaises(ValueError): md.parse_candles([raw], 60, 100)

    def test_gaps_and_stale_inputs(self):
        self.assertEqual(md.candle_errors([0, 60, 180], 60, 240), ['CANDLE_GAP'])
        self.assertIn('STALE_CANDLES', md.candle_errors([0, 60], 60, 600))
        self.assertIn('STALE_BOOK', md.freshness_errors(100, 100, 0, 131))
        self.assertIn('STALE_FEES', md.freshness_errors(90000, 90000, 0, 90001))

    def test_get_only_allowlist(self):
        client = md.CoinbasePublicClient()
        for path in ['orders', '../orders', 'products/BTC-USD/../orders', 'https://other.test']:
            with self.assertRaises(ValueError): client.request(path, {})

    def test_missing_latest_completed_candle_is_stale(self):
        self.assertIn('STALE_CANDLES',md.candle_errors([0],300,610))
        self.assertEqual(md.candle_errors([0,300],300,610),[])

if __name__ == '__main__': unittest.main()
