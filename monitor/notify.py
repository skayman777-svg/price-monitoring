"""Короткая сводка для мессенджера. Отправка в Telegram: отдельная функция, в тестовом прогоне не вызывается."""
from __future__ import annotations

from typing import List, Optional

import requests

from .diff import summarize
from .models import Change, fmt_rub


def _pct(p: float) -> str:
    return f'{p:+.1f}%'.replace('.', ',').replace('-', '−')


def _short(title: str, n: int = 46) -> str:
    if len(title) <= n:
        return title
    cut = title[: n - 1]
    return (cut.rsplit(' ', 1)[0] if ' ' in cut else cut).rstrip(' ,(') + '…'


def format_digest(changes: List[Change], shop: str, total_now: int, total_prev: int,
                  min_pct: float = 5.0, limit: int = 8) -> str:
    """Сводка: крупные изменения цен (от min_pct %) списком, остальное — счётчиками."""
    cnt = summarize(changes)
    lines = [f'Мониторинг цен: {shop}', f'Товаров в каталоге: {total_now} (было {total_prev})', '']
    for kind, arrow, head in (('price_down', '↓', 'Подешевело'), ('price_up', '↑', 'Подорожало')):
        big = [c for c in changes if c.kind == kind and abs(c.pct or 0) >= min_pct]
        rest = cnt[kind] - len(big)
        if not cnt[kind]:
            continue
        lines.append(f'{head} ({cnt[kind]}), показаны изменения от {min_pct:g}%:')
        for c in big[:limit]:
            lines.append(f' {arrow} {_short(c.title)}: {fmt_rub(c.old_kop)} → {fmt_rub(c.new_kop)} ({_pct(c.pct)})')
        if len(big) > limit:
            lines.append(f'   …и ещё {len(big) - limit}')
        if rest:
            lines.append(f'   (мелких изменений ниже порога: {rest})')
        lines.append('')
    lines.append(f'Новых: {cnt["new"]} · Пропало: {cnt["removed"]} · '
                 f'Снова в наличии: {cnt["back_in_stock"]} · Нет в наличии: {cnt["out_of_stock"]}')
    return '\n'.join(lines)[:4000]                   # лимит Telegram — 4096 символов


def send_telegram(text: str, token: str, chat_id: str, timeout: float = 10.0) -> Optional[str]:
    """Отправляет текст ботом. Возвращает текст ошибки или None. В тестовом прогоне не использовалась."""
    try:
        r = requests.post(f'https://api.telegram.org/bot{token}/sendMessage',
                          json={'chat_id': chat_id, 'text': text}, timeout=timeout)
        return None if r.ok else f'HTTP {r.status_code}'
    except requests.RequestException as e:
        return e.__class__.__name__
