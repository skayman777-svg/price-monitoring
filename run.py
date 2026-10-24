#!/usr/bin/env python3
"""Тестовый запуск целиком: тестовый магазин -> снимок 1 -> магазин меняется -> снимок 2 -> сравнение -> Excel.

Запуск:  python run.py
Результат в папке out/: prices.db (история снимков), price_report.xlsx (отчёт), run.log (журнал).
"""
import logging
import pathlib
import sys

from mock_shop.shop import MockShop
from monitor.cli import load_config, run_crawl, run_report

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'


def main() -> int:
    OUT.mkdir(exist_ok=True)
    db, xlsx, logfile = OUT / 'prices.db', OUT / 'price_report.xlsx', OUT / 'run.log'
    for f in (db, xlsx, logfile):
        f.unlink(missing_ok=True)
    fmt = logging.Formatter('%(asctime)s %(levelname)-7s %(message)s', '%H:%M:%S')
    handlers = [logging.StreamHandler(sys.stdout), logging.FileHandler(logfile, encoding='utf-8')]
    for h in handlers:
        h.setFormatter(fmt)
    logging.basicConfig(level=logging.INFO, handlers=handlers)
    log = logging.getLogger('demo')

    shop = MockShop(day=1)
    base = shop.start()
    try:
        log.info('Тестовый магазин запущен: %s (вымышленный каталог, чужие сайты не затрагиваются)', base)
        cfg = load_config(str(HERE / 'config.json'), base)

        log.info('=== Снимок 1: исходный каталог ===')
        run_crawl(cfg, str(db), no_delay=True)

        shop.day = 2
        shop.fail_once['/catalog/phones/?page=2'] = 1      # одна страница один раз ответит 503
        log.info('=== В магазине изменились цены, наличие и ассортимент ===')
        log.info('=== Снимок 2: каталог после изменений (одна страница даст временный сбой 503) ===')
        run_crawl(cfg, str(db), no_delay=True)

        log.info('=== Сравнение и отчёт ===')
        digest = run_report(cfg, str(db), str(xlsx))
        print('\n' + (digest or ''))
        with open(logfile, 'a', encoding='utf-8') as f:            # сводку сохраняем рядом с журналом
            f.write('\n' + (digest or '') + '\n\n')

        log.info('=== Проверка сбоя: раздел «Смартфоны» полностью недоступен ===')
        shop.fail_once['/catalog/phones/'] = 99
        _, res = run_crawl(cfg, str(db), no_delay=True)
        log.info('Отчёт строится только по полным снимкам, поэтому файл остался прежним (снимки №1 и №2).')
        return 0 if not res.ok else 1                      # здесь «неполный снимок» ожидаем
    finally:
        shop.stop()


if __name__ == '__main__':
    main()
