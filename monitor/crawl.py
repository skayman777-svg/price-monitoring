"""Обход разделов каталога с пагинацией; дубли между разделами убираются по артикулу."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List
from urllib.parse import urljoin

from .fetch import Fetcher, FetchError
from .models import Item
from .parse import parse_listing

log = logging.getLogger('monitor.crawl')


@dataclass
class CrawlResult:
    items: Dict[str, Item] = field(default_factory=dict)
    pages: int = 0
    duplicates: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def crawl(fetcher: Fetcher, categories: Dict[str, str], max_pages: int = 100) -> CrawlResult:
    res = CrawlResult()
    for name, path in categories.items():
        url, seen, found = urljoin(fetcher.base_url + '/', path.lstrip('/')), set(), 0
        while url and url not in seen and len(seen) < max_pages:
            seen.add(url)
            try:
                html = fetcher.get(url)
            except FetchError as e:
                # Не знаем, что на этой странице и дальше: раздел неполный, а значит и весь снимок неполный.
                log.error('раздел «%s»: %s', name, e)
                res.errors.append(f'{name}: {e}')
                break
            items, nxt, warns = parse_listing(html, url, name)
            res.pages += 1
            for it in items:
                if it.sku in res.items:
                    res.duplicates += 1
                else:
                    res.items[it.sku] = it
                    found += 1
            for w in warns:
                log.warning(w)
            res.warnings.extend(warns)
            log.info('раздел «%s», стр. %d: карточек %d', name, len(seen), len(items))
            url = nxt
        log.info('раздел «%s»: новых позиций %d', name, found)
    return res
