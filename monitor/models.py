from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Деньги храним в копейках (целые числа): сравнение точное, без ошибок float.


@dataclass
class Item:
    sku: str
    title: str
    url: str
    category: str
    price_kop: Optional[int]                 # None: цена не указана («по запросу», нет блока цены)
    old_price_kop: Optional[int] = None      # зачёркнутая цена, если есть
    in_stock: bool = True
    note: str = ''                           # «цена от», «цена по запросу», «цена не найдена»


KIND_RU = {
    'price_down': 'Цена снизилась',
    'price_up': 'Цена выросла',
    'new': 'Новый товар',
    'removed': 'Товар пропал',
    'back_in_stock': 'Снова в наличии',
    'out_of_stock': 'Нет в наличии',
    'price_set': 'Появилась цена',
    'price_unset': 'Цена скрыта',
}
KIND_ORDER = list(KIND_RU)


@dataclass
class Change:
    kind: str
    sku: str
    title: str
    category: str
    url: str
    old_kop: Optional[int] = None
    new_kop: Optional[int] = None

    @property
    def delta_kop(self) -> Optional[int]:
        if self.old_kop is None or self.new_kop is None:
            return None
        return self.new_kop - self.old_kop

    @property
    def pct(self) -> Optional[float]:
        d = self.delta_kop
        return None if d is None or not self.old_kop else d / self.old_kop * 100


def fmt_rub(kop: Optional[int]) -> str:
    """6499000 → '64 990 ₽', None → '—'."""
    if kop is None:
        return '—'
    rub, k = divmod(kop, 100)
    s = f'{rub:,}'.replace(',', ' ')
    return f'{s},{k:02d} ₽' if k else f'{s} ₽'
