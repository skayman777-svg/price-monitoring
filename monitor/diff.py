"""Сравнение двух снимков каталога."""
from __future__ import annotations

from collections import Counter
from typing import Dict, List

from .models import KIND_ORDER, Change, Item


def compare(prev: Dict[str, Item], curr: Dict[str, Item]) -> List[Change]:
    out: List[Change] = []
    for sku, c in curr.items():
        p = prev.get(sku)
        if p is None:
            out.append(Change('new', sku, c.title, c.category, c.url, None, c.price_kop))
            continue
        if p.price_kop != c.price_kop:
            if p.price_kop is None:
                kind = 'price_set'
            elif c.price_kop is None:
                kind = 'price_unset'
            else:
                kind = 'price_down' if c.price_kop < p.price_kop else 'price_up'
            out.append(Change(kind, sku, c.title, c.category, c.url, p.price_kop, c.price_kop))
        if p.in_stock != c.in_stock:
            out.append(Change('back_in_stock' if c.in_stock else 'out_of_stock',
                              sku, c.title, c.category, c.url, p.price_kop, c.price_kop))
    for sku, p in prev.items():
        if sku not in curr:
            out.append(Change('removed', sku, p.title, p.category, p.url, p.price_kop, None))
    return sort_changes(out)


def sort_changes(changes: List[Change]) -> List[Change]:
    """Сначала по типу изменения, внутри цен — по величине (сильные движения выше)."""
    return sorted(changes, key=lambda c: (KIND_ORDER.index(c.kind), -abs(c.pct or 0), c.title))


def summarize(changes: List[Change]) -> Counter:
    return Counter(c.kind for c in changes)
