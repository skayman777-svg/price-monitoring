"""Тестовый магазин «ТехноДом»: локальный HTTP-сервер с вымышленным каталогом.

Нужен, чтобы показать работу парсера без обращения к чужим сайтам.
Бренды и товары выдуманы. Разметка сделана «как в жизни»: неразрывные пробелы в ценах,
цена «от», «Цена по запросу», зачёркнутая старая цена, дубли товаров в разделе «Акции»,
блок рекомендаций с ценами, которые парсер не должен трогать, карточка без цены,
пагинация и robots.txt.

Дни: day=1 — «вчерашний» каталог, day=2 — «сегодняшний» (цены, наличие и ассортимент изменились).
"""
from __future__ import annotations

import html
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlsplit

PAGE_SIZE = 8
SHOP_NAME = 'ТехноДом'
CATEGORIES = {'laptops': 'Ноутбуки', 'phones': 'Смартфоны', 'headphones': 'Наушники', 'sale': 'Акции'}


@dataclass
class Product:
    sku: str
    cat: str
    title: str
    price: Dict[int, Optional[int]]            # день -> цена в рублях (None: цену не показываем)
    stock: Dict[int, str] = field(default_factory=dict)   # день -> in | out | soon
    old: Dict[int, int] = field(default_factory=dict)     # день -> «старая» цена для акций
    days: tuple = (1, 2)                       # в какие дни товар есть в каталоге
    ask: bool = False                          # «Цена по запросу»
    price_from: bool = False                   # «от 8 990 ₽»
    sale: Dict[int, bool] = field(default_factory=dict)   # день -> показывать ещё и в «Акциях»

    def stock_on(self, day: int) -> str:
        return self.stock.get(day, 'in')


def _p(sku, cat, title, d1, d2=None, **kw) -> Product:
    """d2=None → цена не менялась."""
    return Product(sku, cat, title, {1: d1, 2: d1 if d2 is None else d2}, **kw)


PRODUCTS: List[Product] = [
    # Ноутбуки
    _p('NB-1001', 'laptops', 'Ноутбук Aster Book 15 (Core i5 / 16 ГБ / 512 ГБ)', 64990, 59990),
    _p('NB-1002', 'laptops', 'Ноутбук Aster Book 15 (Core i7 / 16 ГБ / 1 ТБ)', 82990),
    _p('NB-1003', 'laptops', 'Ноутбук Aster Air 13 (Ryzen 5 / 8 ГБ / 256 ГБ)', 49990, 44990, old={2: 49990}, sale={2: True}),
    _p('NB-1004', 'laptops', 'Ноутбук Aster Air 14 (Ryzen 7 / 16 ГБ / 512 ГБ)', 67990),
    _p('NB-1005', 'laptops', 'Ноутбук Nordik Pro 16 (Core i7 / 32 ГБ / 1 ТБ / RTX 4060)', 129990, 119990),
    _p('NB-1006', 'laptops', 'Ноутбук Nordik Pro 14 (Core i5 / 16 ГБ / 512 ГБ)', 74990, stock={2: 'out'}),
    _p('NB-1007', 'laptops', 'Ноутбук Vektor Go 15 (Celeron / 8 ГБ / 256 ГБ)', 29990, old={1: 32990, 2: 32990}, sale={1: True, 2: True}),
    _p('NB-1008', 'laptops', 'Ноутбук Vektor Go 15 (Core i3 / 8 ГБ / 512 ГБ)', 38990, days=(1,)),
    _p('NB-1009', 'laptops', 'Ноутбук Lumen Studio 16 (Ryzen 9 / 32 ГБ / 2 ТБ)', 149990, 139990),
    _p('NB-1010', 'laptops', 'Ноутбук Lumen Slim 14 (Core i5 / 16 ГБ / 512 ГБ)', 71990),
    _p('NB-1011', 'laptops', 'Ноутбук Orbita Edu 11 (N100 / 4 ГБ / 128 ГБ)', 19990, stock={1: 'out', 2: 'in'}),
    _p('NB-1012', 'laptops', 'Ноутбук Orbita Work 15 (Core i5 / 16 ГБ / 512 ГБ)', 57990, 62990),
    _p('NB-1013', 'laptops', 'Ноутбук Kvant Max 17 (Ryzen 7 / 32 ГБ / 1 ТБ / RTX 4070)', None, ask=True),
    _p('NB-1014', 'laptops', 'Ноутбук Kvant One 15 (Core i3 / 8 ГБ / 256 ГБ)', 34990),
    _p('NB-1015', 'laptops', 'Ноутбук Nordik Pro 14 (Core i7 / 32 ГБ / 1 ТБ)', 94990, days=(2,)),
    # Смартфоны
    _p('PH-2001', 'phones', 'Смартфон Zefir S5 128 ГБ', 17990, old={1: 19990, 2: 19990}, sale={1: True, 2: True}),
    _p('PH-2002', 'phones', 'Смартфон Zefir S5 256 ГБ', 21990, 19990),
    _p('PH-2003', 'phones', 'Смартфон Zefir S5 Pro 256 ГБ', 32990),
    _p('PH-2004', 'phones', 'Смартфон Zefir S5 Ultra 512 ГБ', 59990, stock={2: 'out'}),
    _p('PH-2005', 'phones', 'Смартфон Aster Nova 8 128 ГБ', 24990, 27990),
    _p('PH-2006', 'phones', 'Смартфон Aster Nova 8 Pro 256 ГБ', 38990),
    _p('PH-2007', 'phones', 'Смартфон Lumen X 256 ГБ', None, stock={1: 'soon', 2: 'soon'}),
    _p('PH-2008', 'phones', 'Смартфон Lumen X Max 512 ГБ', 71990, 64990),
    _p('PH-2009', 'phones', 'Смартфон Nordik Fold 512 ГБ', 94990, stock={1: 'out', 2: 'in'}),
    _p('PH-2010', 'phones', 'Смартфон Vektor A2 64 ГБ', 9990, 8490, old={2: 9990}, sale={2: True}),
    _p('PH-2011', 'phones', 'Смартфон Vektor A2 128 ГБ', 12490),
    _p('PH-2012', 'phones', 'Смартфон Orbita Lite 128 ГБ', 13990, days=(1,)),
    _p('PH-2013', 'phones', 'Смартфон Zefir S6 256 ГБ', 29990, days=(2,)),
    # Наушники
    _p('HP-3001', 'headphones', 'Наушники Zefir Buds 2 (TWS)', 3990, 3890),
    _p('HP-3002', 'headphones', 'Наушники Zefir Buds Pro (TWS, ANC)', 8990, price_from=True),
    _p('HP-3003', 'headphones', 'Наушники Aster Sound ANC (накладные, Bluetooth)', 12990, 9990, old={2: 12990}, sale={2: True}),
    _p('HP-3004', 'headphones', 'Наушники Aster Sound Studio (проводные)', 6990, old={1: 7990, 2: 7990}, sale={1: True, 2: True}),
    _p('HP-3005', 'headphones', 'Наушники Lumen Air (TWS)', 5490, 5990),
    _p('HP-3006', 'headphones', 'Наушники Lumen Max (полноразмерные, ANC)', 24990, 22990),
    _p('HP-3007', 'headphones', 'Наушники Nordik Run (спортивные, Bluetooth)', 2990, stock={2: 'out'}),
    _p('HP-3008', 'headphones', 'Наушники Vektor Mini & кейс «Pocket» (проводные)', 990, stock={1: 'out', 2: 'in'}),
    _p('HP-3009', 'headphones', 'Наушники Orbita Kids (с ограничением громкости)', 2490, 2290, old={1: 2990, 2: 2990}, sale={1: True, 2: True}),
    _p('HP-3010', 'headphones', 'Наушники Kvant Pulse (TWS, игровые)', 4490),
    _p('HP-3011', 'headphones', 'Наушники Aster Sound Air (TWS, ANC)', 7490, days=(2,)),
]
BY_SKU = {p.sku: p for p in PRODUCTS}

# Что изменилось между днями: нужно тестам и описанию (считается из данных, не вписывается руками)
def expected_changes() -> Dict[str, int]:
    out = {'price_down': 0, 'price_up': 0, 'new': 0, 'removed': 0, 'back_in_stock': 0, 'out_of_stock': 0}
    for p in PRODUCTS:
        if 1 in p.days and 2 not in p.days:
            out['removed'] += 1
        elif 2 in p.days and 1 not in p.days:
            out['new'] += 1
        else:
            a, b = p.price[1], p.price[2]
            if a is not None and b is not None and a != b:
                out['price_down' if b < a else 'price_up'] += 1
            s1, s2 = p.stock_on(1) == 'in', p.stock_on(2) == 'in'
            if s1 != s2:
                out['back_in_stock' if s2 else 'out_of_stock'] += 1
    return out


def products_for(cat: str, day: int) -> List[Product]:
    if cat == 'sale':
        return [p for p in PRODUCTS if day in p.days and p.sale.get(day)]
    return [p for p in PRODUCTS if p.cat == cat and day in p.days]


# ----------------------------------------------------------------- HTML
def _money(n: int, sep: str) -> str:
    return f'{n:,}'.replace(',', sep).replace(' ', '&nbsp;').replace(' ', '&#8239;')


def _card(p: Product, day: int) -> str:
    sep = ' ' if p.sku.startswith('PH') else ' '          # у телефонов «тонкий» неразрывный пробел
    st = p.stock_on(day)
    cls = 'product-card' + ('' if st == 'in' else ' product-card--out')
    price, old = p.price[day], p.old.get(day)
    if p.ask:
        prices = '<span class="price price--ask">Цена по запросу</span>'
    elif price is None:
        prices = ''                                               # «битая» карточка: блок цены пустой
    else:
        prefix = '<small>от</small> ' if p.price_from else ''
        old_html = f'<span class="price price--old">{_money(old, sep)}&nbsp;₽</span>\n      ' if old else ''
        badge = f'<span class="badge">−{round((1 - price / old) * 100)}%</span>' if old else ''
        prices = f'{old_html}<span class="price price--current">{prefix}{_money(price, sep)}&nbsp;₽</span>{badge}'
    stock_html = {
        'in': '<div class="stock stock--in">В наличии</div>',
        'out': '<div class="stock stock--out">Нет в наличии</div>',
        'soon': '<div class="stock stock--soon">Ожидается поставка</div>',
    }[st]
    title = html.escape(p.title)
    slug = p.sku.lower()
    return f'''  <article class="{cls}" data-sku="{p.sku}">
    <a class="product-card__title" href="/product/{slug}/">
      {title}
    </a>
    <div class="product-card__prices">
      {prices}
    </div>
    {stock_html}
  </article>'''


def render_listing(cat: str, page: int, day: int) -> Optional[str]:
    items = products_for(cat, day)
    pages = max(1, -(-len(items) // PAGE_SIZE))
    if page < 1 or page > pages:
        return None
    chunk = items[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]
    base = f'/catalog/{cat}/'
    pager = ''
    if pages > 1:
        nums = ''.join(f'<a class="pagination__item{" is-active" if n == page else ""}" href="{base}?page={n}">{n}</a>'
                       for n in range(1, pages + 1))
        nxt = f'<a class="pagination__next" href="{base}?page={page + 1}">Далее →</a>' if page < pages else ''
        pager = f'<nav class="pagination">{nums}{nxt}</nav>'
    reco = ''.join(
        f'<div class="reco-item"><a href="/product/{p.sku.lower()}/">{html.escape(p.title)}</a>'
        f'<span class="price price--current">{_money(p.price[day] or 0, " ")}&nbsp;₽</span></div>'
        for p in products_for('laptops', day)[:2])
    cards = '\n'.join(_card(p, day) for p in chunk)
    return f'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>{CATEGORIES[cat]} — {SHOP_NAME}</title></head>
<body>
<header><a href="/">{SHOP_NAME}</a>
  <nav>{''.join(f'<a href="/catalog/{k}/">{v}</a>' for k, v in CATEGORIES.items())}</nav></header>
<div class="promo-banner">Скидка 10% на аксессуары по промокоду DEMO10 — только сегодня за 990&nbsp;₽</div>
<h1>{CATEGORIES[cat]}</h1>
<p class="count">Товаров в разделе: {len(items)}</p>
<section class="product-list">
{cards}
</section>
{pager}
<aside class="reco"><h2>Вам может понравиться</h2>{reco}</aside>
<footer>© {SHOP_NAME}. Вымышленный тестовый магазин.</footer>
</body></html>'''


def render_product(p: Product, day: int) -> str:
    return (f'<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>{html.escape(p.title)}</title></head>'
            f'<body><h1>{html.escape(p.title)}</h1><p>Артикул: {p.sku}</p></body></html>')


ROBOTS = 'User-agent: *\nDisallow: /admin/\nDisallow: /cart/\nCrawl-delay: 1\n'


# ----------------------------------------------------------------- сервер
class MockShop:
    def __init__(self, day: int = 1):
        self.day = day
        self.fail_once: Dict[str, int] = {}     # путь с query -> сколько раз ответить 503 (для проверки повторных попыток)
        self.hits: List[str] = []
        self.agents: List[str] = []             # User-Agent каждого запроса
        self.port = 0
        self._srv: Optional[ThreadingHTTPServer] = None

    def start(self, port: int = 0) -> str:
        shop = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):          # тишина в консоли
                pass

            def do_GET(self):                       # noqa: N802
                shop._handle(self)

        self._srv = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        self.port = self._srv.server_address[1]
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()
        return f'http://127.0.0.1:{self.port}'

    def stop(self) -> None:
        if self._srv:
            self._srv.shutdown()
            self._srv.server_close()
            self._srv = None

    # --- внутреннее
    def _send(self, h, code: int, body: str, ctype: str = 'text/html; charset=utf-8', extra=None) -> None:
        data = body.encode('utf-8')
        h.send_response(code)
        h.send_header('Content-Type', ctype)
        h.send_header('Content-Length', str(len(data)))
        for k, v in (extra or {}).items():
            h.send_header(k, v)
        h.end_headers()
        h.wfile.write(data)

    def _handle(self, h) -> None:
        self.hits.append(h.path)
        self.agents.append(h.headers.get('User-Agent', ''))
        left = self.fail_once.get(h.path, 0)
        if left > 0:
            self.fail_once[h.path] = left - 1
            return self._send(h, 503, 'Временно недоступно', 'text/plain; charset=utf-8', {'Retry-After': '0'})
        u = urlsplit(h.path)
        parts = [x for x in u.path.split('/') if x]
        if u.path == '/robots.txt':
            return self._send(h, 200, ROBOTS, 'text/plain; charset=utf-8')
        if len(parts) == 2 and parts[0] == 'catalog' and parts[1] in CATEGORIES:
            try:
                page = int(parse_qs(u.query).get('page', ['1'])[0])
            except ValueError:
                page = 0
            body = render_listing(parts[1], page, self.day)
            return self._send(h, 200 if body else 404, body or 'Страница не найдена')
        if len(parts) == 2 and parts[0] == 'product' and parts[1].upper() in BY_SKU:
            return self._send(h, 200, render_product(BY_SKU[parts[1].upper()], self.day))
        if parts and parts[0] == 'admin':
            return self._send(h, 403, 'Доступ закрыт')
        return self._send(h, 404, 'Страница не найдена')


if __name__ == '__main__':                          # ручной запуск: python -m mock_shop.shop [день]
    import sys
    s = MockShop(day=int(sys.argv[1]) if len(sys.argv) > 1 else 1)
    print('Тестовый магазин:', s.start(8765))
    threading.Event().wait()
