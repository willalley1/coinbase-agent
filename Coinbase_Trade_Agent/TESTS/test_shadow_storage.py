import unittest
import tempfile
from pathlib import Path
try:
    from SHADOW.storage import Store
except ImportError: Store=None

class StorageTests(unittest.TestCase):
    def setUp(self): self.assertIsNotNone(Store,'durable paper ledger must exist')

    def test_duplicate_and_restart_preserves_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'shadow'/'paper.sqlite'
            with Store(path) as store:
                store.record_scan('one',[{'product_id':'BTC-USD','strategy_id':'trend','decision':'NO_TRADE'}])
                store.record_scan('one',[{'product_id':'BTC-USD','strategy_id':'trend','decision':'NO_TRADE'}])
                store.checkpoint('portfolio',{'equity':'10000'})
                self.assertEqual(store.count('observations'),1)
            with Store(path) as store: self.assertEqual(store.read_checkpoint('portfolio'),{'equity':'10000'})

    def test_transaction_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            with Store(Path(tmp)/'shadow'/'paper.sqlite') as store:
                store.checkpoint('p',{'value':1})
                with self.assertRaises(RuntimeError):
                    with store.transaction():
                        store.checkpoint('p',{'value':2})
                        raise RuntimeError('injected')
                self.assertEqual(store.read_checkpoint('p'),{'value':1})

    def test_paper_paths_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError): Store(Path(tmp)/'DATA'/'live.sqlite')

if __name__=='__main__': unittest.main()
