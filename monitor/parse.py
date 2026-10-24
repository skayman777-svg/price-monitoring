"""Разбор HTML: карточки товаров, цены, наличие, ссылка на следующую страницу."""
from __future__ import annotations

import re
from typing import List, Optional, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .models import Item

_SPACES = re.compile(r'[\s   ]+')
_NUMBER = re.compile(r'(\d[\d\s   ]*)(?:[.,](\d{1,2})(?!\d))?')


def clean(text: Optional[str]) -> str:
    """Схлопывает переводы строк и все виды пробелов (в том числе неразрывные)."""
    return _SPACES.sub(' ', text or '').strip()


def parse_price(text: Optional[str]) -> Optional[int]:
    """'от 64 990 ₽' → 6499000 (копейки); '1 299,5 руб.' → 129950; 'Цена по запросу' → None.

    Берётся первое число в строке, поэтому передавать нужно только текст элемента с ценой.
    """
    m = _NUMBER.search(clean(text))
    if not m:
        return None
    rub = int(re.sub(r'\D', '', m.group(1)))
    kop = int((m.group(2) or '0').ljust(2, '0'))
    return rub * 100 + kop


def parse_card(card, page_url: str, category: str) -> Tuple[Item, Optional[str]]:
    """Возвращает товар и предупреждение (если чего-то не хватает). Без артикула/названия — ValueError."""
    sku = clean(card.get('data-sku'))
    title_el = card.select_one('.product-card__title')
    if not sku or title_el is None:
        raise ValueError('в карточке нет артикула или названия')
    href = title_el.get('href')
    cur = card.select_one('.price--current')
    old = card.select_one('.price--old')
    ask = card.select_one('.price--ask') is not None
    price = parse_price(cur.get_text(' ')) if cur is not None else None
    price_from = bool(cur is not None and re.search(r'(?<!\w)от(?!\w)', clean(cur.get_text(' ')), re.I))
    note = 'цена по запросу' if ask else 'цена «от»' if price_from else 'цена не найдена' if price is None else ''
    item = Item(
        sku=sku,
        title=clean(title_el.get_text(' ')),
        url=urljoin(page_url, href) if href else '',
        category=category,
        price_kop=price,
        old_price_kop=parse_price(old.get_text(' ')) if old is not None else None,
        in_stock=card.select_one('.stock--in') is not None,
        note=note,
    )
    warn = f'{sku}: цена не найдена в карточке' if price is None and not ask else None
    return item, warn


def parse_listing(html: str, page_url: str, category: str) -> Tuple[List[Item], Optional[str], List[str]]:
    """Страница каталога → (товары, адрес следующей страницы или None, предупреждения)."""
    soup = BeautifulSoup(html, 'lxml')
    items: List[Item] = []
    warnings: List[str] = []
    for i, card in enumerate(soup.select('article.product-card'), 1):
        try:
            item, warn = parse_card(card, page_url, category)
        except ValueError as e:
            warnings.append(f'{page_url}: карточка №{i} пропущена ({e})')
            continue
        items.append(item)
        if warn:
            warnings.append(warn)
    nxt = soup.select_one('a.pagination__next')
    next_url = urljoin(page_url, nxt['href']) if nxt is not None and nxt.get('href') else None
    return items, next_url, warnings
