"""Transactional, paper-only event ledger. No live records are modified."""
from contextlib import contextmanager
from pathlib import Path
import json
import sqlite3
from .models import dumps, digest

class Store:
    TABLES=('scans','observations','signals','events','markouts','snapshots','checkpoints')
    def __init__(self,path):
        self.path=Path(path).resolve()
        if 'shadow' not in [p.lower() for p in self.path.parts]: raise ValueError('PAPER_PATH_REQUIRED')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.conn=sqlite3.connect(self.path,isolation_level=None,timeout=10)
        self.conn.execute('PRAGMA journal_mode=DELETE')
        self.conn.execute('PRAGMA synchronous=FULL')
        for table in self.TABLES:
            self.conn.execute(f'CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        self._depth=0

    def __enter__(self): return self
    def __exit__(self,*args): self.conn.close()

    @contextmanager
    def transaction(self):
        outer=self._depth==0
        if outer: self.conn.execute('BEGIN IMMEDIATE')
        self._depth+=1
        try:
            yield
            if outer: self.conn.execute('COMMIT')
        except BaseException:
            if outer: self.conn.execute('ROLLBACK')
            raise
        finally: self._depth-=1

    def put(self,table,key,payload,replace=False):
        if table not in self.TABLES: raise ValueError('INVALID_TABLE')
        verb='INSERT OR REPLACE' if replace else 'INSERT OR IGNORE'
        cur=self.conn.execute(f'{verb} INTO {table} (id,payload) VALUES (?,?)',(str(key),dumps(payload)))
        return bool(cur.rowcount)

    def rows(self,table):
        if table not in self.TABLES: raise ValueError('INVALID_TABLE')
        return [json.loads(row[0]) for row in self.conn.execute(f'SELECT payload FROM {table} ORDER BY rowid')]

    def count(self,table): return len(self.rows(table))

    def record_scan(self,scan_id,records):
        with self.transaction():
            if not self.put('scans',scan_id,{'scan_id':scan_id,'records':len(records)}): return
            for row in records:
                key=digest((scan_id,row.get('product_id'),row.get('strategy_id')))
                self.put('observations',key,row)

    def append_events(self,events):
        with self.transaction():
            for event in events: self.put('events',event.event_id,event)

    def save_snapshot(self,snapshot,raw):
        key=digest((snapshot.product_id,snapshot.as_of))
        folder=self.path.parent/'raw'; folder.mkdir(exist_ok=True)
        target=folder/(key+'.json')
        with self.transaction():
            if not target.exists(): target.write_text(dumps({'snapshot':snapshot,'raw':raw}),encoding='utf-8')
            self.put('snapshots',key,{'product_id':snapshot.product_id,'as_of':snapshot.as_of,'path':str(target),'sha256':digest({'snapshot':snapshot,'raw':raw})})

    def checkpoint(self,key,value): self.put('checkpoints',key,value,True)

    def read_checkpoint(self,key):
        row=self.conn.execute('SELECT payload FROM checkpoints WHERE id=?',(key,)).fetchone()
        return json.loads(row[0]) if row else None

    def active_candidates(self):
        return [row for row in self.rows('signals') if row.get('state')=='ACTIVE']
