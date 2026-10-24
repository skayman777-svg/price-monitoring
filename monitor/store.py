"""Хранилище снимков в SQLite: таблица запусков и таблица цен по каждому запуску."""
from __future__ import annotations

import sqlite3
from typing import Dict, List

from .crawl import CrawlResult
from .models import Item

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL, finished_at TEXT NOT NULL, base_url TEXT NOT NULL,
  status TEXT NOT NULL,                       -- ok | partial
  pages INTEGER NOT NULL, items INTEGER NOT NULL, duplicates INTEGER NOT NULL,
  warnings INTEGER NOT NULL, errors TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS prices (
  run_id INTEGER NOT NULL REFERENCES runs(id), sku TEXT NOT NULL,
  title TEXT NOT NULL, category TEXT NOT NULL, url TEXT NOT NULL,
  price_kop INTEGER, old_price_kop INTEGER,
  in_stock INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '',
  PRIMARY KEY (run_id, sku)
);
"""


class Store:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    def save_run(self, base_url: str, res: CrawlResult, started: str, finished: str) -> int:
        status = 'ok' if res.ok else 'partial'
        with self.db:                                    # одна транзакция: либо весь снимок, либо ничего
            cur = self.db.execute(
                'INSERT INTO runs (started_at, finished_at, base_url, status, pages, items, duplicates, warnings, errors) '
                'VALUES (?,?,?,?,?,?,?,?,?)',
                (started, finished, base_url, status, res.pages, len(res.items), res.duplicates,
                 len(res.warnings), '\n'.join(res.errors)))
            run_id = cur.lastrowid
            self.db.executemany(
                'INSERT INTO prices VALUES (?,?,?,?,?,?,?,?,?)',
                [(run_id, i.sku, i.title, i.category, i.url, i.price_kop, i.old_price_kop, int(i.in_stock), i.note)
                 for i in res.items.values()])
        return run_id

    def last_ok_runs(self, n: int = 2) -> List[sqlite3.Row]:
        """Последние успешные снимки, новые первыми. Неполные снимки в сравнении не участвуют."""
        return self.db.execute("SELECT * FROM runs WHERE status='ok' ORDER BY id DESC LIMIT ?", (n,)).fetchall()

    def load_items(self, run_id: int) -> Dict[str, Item]:
        rows = self.db.execute('SELECT * FROM prices WHERE run_id=? ORDER BY sku', (run_id,)).fetchall()
        return {r['sku']: Item(r['sku'], r['title'], r['url'], r['category'], r['price_kop'], r['old_price_kop'],
                               bool(r['in_stock']), r['note']) for r in rows}
