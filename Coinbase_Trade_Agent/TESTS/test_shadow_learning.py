import unittest
try:
    from SHADOW import learning as l
except ImportError: l=None

class LearningTests(unittest.TestCase):
    def setUp(self): self.assertIsNotNone(l,'learning reports must exist')

    def test_shortest_requires_independent_heldout_evidence(self):
        rows=[dict(horizon_minutes=1,independent_count=100,net_mean=.001,ci_low=-.001,positive_days=8,days=10),
              dict(horizon_minutes=5,independent_count=100,net_mean=.003,ci_low=.001,positive_days=9,days=10),
              dict(horizon_minutes=10,independent_count=100,net_mean=.005,ci_low=.002,positive_days=9,days=10)]
        result=l.select_windows(rows)
        self.assertEqual(result['shortest_provisional_minutes'],5)
        self.assertEqual(result['next_larger_minutes'],[10,15,20])
        self.assertFalse(result['validated'])

    def test_sparse_or_losing_no_consistency_claim(self):
        rows=[dict(horizon_minutes=1,independent_count=8,net_mean=.01,ci_low=.001,positive_days=2,days=2)]
        self.assertIsNone(l.select_windows(rows)['shortest_provisional_minutes'])

    def test_fee_drag_and_empty_metrics(self):
        m=l.trade_metrics([{'net_pnl':'-1','initial_risk':'2','realized_r':'-.5','uncertain':False}])
        self.assertEqual(m['expectancy_r'],-.5)
        self.assertEqual(m['net_pnl'],-1)
        self.assertIsNone(l.trade_metrics([])['expectancy_r'])

    def test_day_block_ci_and_unique_count(self):
        rows=[{'signal_id':str(i),'day':str(i//10),'net_return':'0.01'} for i in range(100)]
        m=l.outcome_metrics(rows+rows)
        self.assertEqual(m['independent_count'],100)
        self.assertEqual(m['positive_days'],10)
        self.assertGreater(m['ci_low'],0)

    def test_forward_overlap_excluded(self):
        self.assertTrue(hasattr(l,'forward_metrics'),'forward outcomes must exclude overlapping windows')
        rows=[dict(signal_id='a',product_id='BTC-USD',strategy_id='trend',horizon_minutes=5,status='OBSERVED',due_at=300,observed_at=300,net_return='.01'),
              dict(signal_id='b',product_id='BTC-USD',strategy_id='trend',horizon_minutes=5,status='OBSERVED',due_at=360,observed_at=360,net_return='.03'),
              dict(signal_id='c',product_id='BTC-USD',strategy_id='trend',horizon_minutes=5,status='OBSERVED',due_at=600,observed_at=600,net_return='.02')]
        result=l.forward_metrics(rows)
        self.assertEqual(result[0]['independent_count'],2)
        self.assertAlmostEqual(result[0]['net_mean'],.015)

    def test_rule_versions_are_separate_cohorts(self):
        rows=[dict(signal_id='a',product_id='BTC-USD',strategy_id='trend',rules_version='v1',horizon_minutes=5,status='OBSERVED',due_at=300,net_return='.01'),
              dict(signal_id='b',product_id='BTC-USD',strategy_id='trend',rules_version='v2',horizon_minutes=5,status='OBSERVED',due_at=600,net_return='-.03')]
        metrics=l.forward_metrics(rows)
        self.assertEqual(len(metrics),2)
        self.assertEqual({x['rules_version'] for x in metrics},{'v1','v2'})

if __name__=='__main__': unittest.main()
