import unittest
import tempfile
import json
import shutil
from unittest.mock import patch
from pathlib import Path
try:
    from SHADOW import runner as r
except ImportError: r=None

class RunnerTests(unittest.TestCase):
    def setUp(self): self.assertIsNotNone(r,'repeated paper runner must exist')

    def test_second_instance_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'runner.lock'
            with r.ProcessLock(path):
                with self.assertRaises(RuntimeError):
                    with r.ProcessLock(path): pass
            with r.ProcessLock(path): pass

    def test_config_rejects_live_and_invalid_limits(self):
        with self.assertRaises(ValueError): r.validate_config({'paper_only':False}, {})
        with self.assertRaises(ValueError): r.validate_config({'paper_only':True}, {'risk_per_trade_pct':{}})

    def test_next_scan_boundary(self):
        self.assertEqual(r.next_scan_at(301),310)
        self.assertEqual(r.next_scan_at(609),610)

    def test_failed_market_still_records_all_six(self):
        rows=r.failed_market_rows('BTC-USD',1000,'network error')
        self.assertEqual(len(rows),6)
        self.assertTrue(all(x['decision']=='NO_TRADE' for x in rows))

    def test_scan_restart_does_not_duplicate(self):
        from SHADOW.models import Candle,Book
        from SHADOW.storage import Store
        from decimal import Decimal as D
        class FakeClient:
            raw=[]
            def get_product(self,product):
                return dict(product_id=product,product_type='SPOT',status='online',base_increment='.01',base_min_size='.01',quote_min_size='1')
            def get_candles(self,product,seconds,start,end):
                return tuple(Candle(t,seconds,D(100),D(101),D(99),D(100),D(1)) for t in range(start,end,seconds))
            def get_book(self,product): return Book(product,20000000,20000000,((D('99.99'),D(100)),),((D(100),D(100)),))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for folder in ('CONFIG','STRATEGIES','SHADOW'): (root/folder).mkdir()
            for filename in ('CONFIG/HARD_LIMITS.json','STRATEGIES/SHADOW_RESEARCH_RULES.json','SHADOW/strategies.py'):
                shutil.copyfile(filename,root/filename)
            config=json.loads(Path('CONFIG/SHADOW_CONFIG.json').read_text())
            config['products']=['BTC-USD']; config['fee_snapshot']['observed_at']=20000000
            (root/'CONFIG/SHADOW_CONFIG.json').write_text(json.dumps(config))
            with patch('SHADOW.runner.time.time',return_value=20000000):
                first=r.Engine(root,client=FakeClient()).cycle()
                second=r.Engine(root,client=FakeClient()).cycle()
            self.assertEqual(first['observations'],6)
            self.assertEqual(second['observations'],6)
            with Store(root/'DATA/shadow/paper.sqlite') as store:
                self.assertEqual(store.count('observations'),6)
                self.assertEqual(store.read_checkpoint('portfolio')['cash'],'10000')

    def test_invalid_book_does_not_close_position(self):
        from SHADOW.models import MarketSnapshot,Book,FeeSnapshot
        from decimal import Decimal as D
        from SHADOW.storage import Store
        engine=r.Engine()
        position=dict(signal_id='one',product_id='BTC-USD',strategy_id='trend',state='ACTIVE',quantity='1',entry='100',fee='.001',entry_fee='.1',initial_risk='2.298',
                      stop='98',target='106',opened_at=10,last_review=10,due_at=3610,mae='0',mfe='0',uncertain=False,markouts=[])
        snap=MarketSnapshot('BTC-USD',70,{},Book('BTC-USD',70,70,((D(107),D(10)),),((D(99),D(10)),)),{},FeeSnapshot(D('.001'),D('.001'),70,'test'))
        with tempfile.TemporaryDirectory() as tmp:
            with Store(Path(tmp)/'shadow/paper.sqlite') as store:
                store.put('signals','one',position)
                p=dict(cash='9899.9',realized_equity='10000',loss_streak=0)
                engine.review_market(store,snap,p)
                self.assertEqual(len(store.active_candidates()),1)
                self.assertEqual(store.active_candidates()[0]['state'],'ACTIVE')
                self.assertEqual(p['cash'],'9899.9')

    def test_review_rollback_preserves_in_memory_portfolio(self):
        from SHADOW.models import MarketSnapshot,Book,FeeSnapshot
        from decimal import Decimal as D
        from SHADOW.storage import Store
        engine=r.Engine()
        position=dict(signal_id='one',product_id='BTC-USD',strategy_id='trend',state='ACTIVE',quantity='1',entry='100',fee='.001',entry_fee='.1',initial_risk='2.298',
                      stop='98',target='106',opened_at=10,last_review=10,due_at=3610,mae='0',mfe='0',uncertain=False,markouts=[])
        snap=MarketSnapshot('BTC-USD',70,{},Book('BTC-USD',70,70,((D(107),D(10)),),((D(108),D(10)),)),{},FeeSnapshot(D('.001'),D('.001'),70,'test'))
        with tempfile.TemporaryDirectory() as tmp:
            with Store(Path(tmp)/'shadow/paper.sqlite') as store:
                store.put('signals','one',position)
                p=dict(cash='9899.9',realized_equity='10000',loss_streak=0)
                with patch('SHADOW.runner.markout',side_effect=RuntimeError('injected after exit')):
                    with self.assertRaises(RuntimeError): engine.review_market(store,snap,p)
                self.assertEqual(store.active_candidates()[0]['state'],'ACTIVE')
                self.assertEqual(p['cash'],'9899.9')

    def test_complete_limit_schema_required(self):
        config=json.loads(Path('CONFIG/SHADOW_CONFIG.json').read_text())
        limits=json.loads(Path('CONFIG/HARD_LIMITS.json').read_text())
        del limits['weekly_drawdown_pct']['soft']
        with self.assertRaises(ValueError): r.validate_config(config,limits)

if __name__=='__main__': unittest.main()
