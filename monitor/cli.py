"""Командная строка: crawl (снять снимок), report (сравнить и собрать Excel), run (оба шага + сводка)."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
from typing import Dict, Optional, Tuple

from .crawl import CrawlResult, crawl
from .diff import compare, summarize
from .fetch import Fetcher
from .models import KIND_RU
from .notify import format_digest, send_telegram
from .report import build_report
from .store import Store

log = logging.getLogger('monitor')

DEFAULTS = {
    'shop_name': 'Магазин',
    'user_agent': 'PriceMonitor/1.0',
    'delay_seconds': 1.0,
    'timeout_seconds': 10,
    'retries': 3,
    'backoff_seconds': 0.5,
    'alert_min_pct': 5.0,
    'drop_guard': 0.5,           # снимок, где товаров меньше половины от прошлого, считаем подозрительным
}


def load_config(path: str, base_url: Optional[str] = None) -> Dict:
    with open(path, encoding='utf-8') as f:
        cfg = {**DEFAULTS, **json.load(f)}
    if base_url:
        cfg['base_url'] = base_url
    if not cfg.get('base_url') or not cfg.get('categories'):
        raise SystemExit('В конфиге нужны base_url и categories')
    return cfg


def _now() -> str:
    return dt.datetime.now().isoformat(timespec='seconds')


def run_crawl(cfg: Dict, db_path: str, no_delay: bool = False) -> Tuple[int, CrawlResult]:
    fetcher = Fetcher(cfg['base_url'], cfg['user_agent'], cfg['timeout_seconds'], cfg['retries'],
                      cfg['backoff_seconds'], cfg['delay_seconds'], honor_crawl_delay=not no_delay)
    if no_delay:
        fetcher.delay = 0
    started = _now()
    res = crawl(fetcher, cfg['categories'])
    store = Store(db_path)
    try:
        prev = store.last_ok_runs(1)
        if not res.items:
            res.errors.append('каталог пуст: возможно, изменилась разметка сайта')
        elif prev and len(res.items) < prev[0]['items'] * cfg['drop_guard']:
            res.errors.append(f'товаров {len(res.items)} против {prev[0]["items"]} в прошлый раз: '
                              'снимок помечен неполным, проверьте разметку и доступность разделов')
        run_id = store.save_run(cfg['base_url'], res, started, _now())
    finally:
        store.close()
    if res.ok:
        log.info('Снимок №%d сохранён: товаров %d, страниц %d, запросов %d, дублей между разделами %d, предупреждений %d',
                 run_id, len(res.items), res.pages, fetcher.requests_made, res.duplicates, len(res.warnings))
    else:
        log.error('Снимок №%d сохранён как НЕПОЛНЫЙ и в сравнении участвовать не будет: %s', run_id, '; '.join(res.errors))
    return run_id, res


def run_report(cfg: Dict, db_path: str, out_xlsx: str, send: bool = False) -> Optional[str]:
    store = Store(db_path)
    try:
        runs = store.last_ok_runs(2)
        if len(runs) == 1:
            log.info('Это первый успешный снимок: сравнивать пока не с чем, отчёт появится после следующего запуска')
            return None
        if not runs:
            log.error('Успешных снимков нет: сначала выполните crawl')
            return None
        curr_run, prev_run = runs[0], runs[1]
        prev, curr = store.load_items(prev_run['id']), store.load_items(curr_run['id'])
    finally:
        store.close()
    changes = compare(prev, curr)
    build_report(out_xlsx, cfg['shop_name'], dict(prev_run), dict(curr_run), prev, curr, changes)
    cnt = summarize(changes)
    log.info('Сравнение снимков №%d и №%d: %s', prev_run['id'], curr_run['id'],
             ', '.join(f'{KIND_RU[k].lower()}: {v}' for k, v in cnt.items()) or 'изменений нет')
    rel = os.path.relpath(out_xlsx)
    log.info('Отчёт Excel: %s', out_xlsx if rel.startswith('..') else rel)
    digest = format_digest(changes, cfg['shop_name'], len(curr), len(prev), cfg['alert_min_pct'])
    token, chat = os.environ.get('TELEGRAM_BOT_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
    if send and token and chat:
        err = send_telegram(digest, token, chat)
        log.info('Отправка в Telegram: %s', 'ок' if err is None else f'ошибка ({err})')
    else:
        log.info('Отправка в Telegram не выполнялась (тестовый режим), текст сводки ниже')
    return digest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog='python -m monitor', description='Мониторинг цен: снимки каталога и отчёт в Excel')
    ap.add_argument('command', choices=['crawl', 'report', 'run'])
    ap.add_argument('--config', default='config.json')
    ap.add_argument('--base-url', help='перекрывает base_url из конфига')
    ap.add_argument('--db', default='out/prices.db')
    ap.add_argument('--out', default='out/price_report.xlsx')
    ap.add_argument('--no-delay', action='store_true', help='без пауз между запросами (только для своего или тестового сервера)')
    ap.add_argument('--send', action='store_true', help='отправить сводку в Telegram (нужны TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID)')
    ap.add_argument('-v', '--verbose', action='store_true')
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format='%(asctime)s %(levelname)-7s %(message)s',
                        datefmt='%H:%M:%S', stream=sys.stdout)
    cfg = load_config(a.config, a.base_url)
    os.makedirs(os.path.dirname(a.db) or '.', exist_ok=True)
    code = 0
    if a.command in ('crawl', 'run'):
        _, res = run_crawl(cfg, a.db, a.no_delay)
        code = 0 if res.ok else 1
    if a.command in ('report', 'run') and code == 0:
        digest = run_report(cfg, a.db, a.out, a.send)
        if digest:
            print('\n' + digest)
        elif a.command == 'report':
            code = 2                                     # отчёта нет: нечего сравнивать
    return code
