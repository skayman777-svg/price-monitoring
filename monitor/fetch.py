"""Загрузка страниц: честный User-Agent, robots.txt, пауза между запросами, повторные попытки."""
from __future__ import annotations

import logging
import time
from typing import Optional
from urllib import robotparser

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger('monitor.fetch')


class FetchError(Exception):
    pass


class LoggedRetry(Retry):
    """Обычные повторные попытки urllib3, но каждая попытка попадает в лог."""

    def increment(self, method=None, url=None, response=None, error=None, _pool=None, _stacktrace=None):
        new = super().increment(method, url, response, error, _pool, _stacktrace)
        why = f'ответ {response.status}' if response is not None else (error.__class__.__name__ if error else 'сбой')
        log.warning('повтор запроса %s: %s (осталось попыток: %s)', url, why, new.total)
        return new


def _why(e: Exception) -> str:
    if isinstance(e, requests.exceptions.RetryError):
        return 'сервер отвечает ошибкой, повторные попытки исчерпаны'
    if isinstance(e, requests.exceptions.Timeout):
        return 'таймаут'
    if isinstance(e, requests.exceptions.ConnectionError):
        return 'нет соединения'
    return e.__class__.__name__


class Fetcher:
    def __init__(self, base_url: str, user_agent: str = 'PriceMonitor/1.0', timeout: float = 10.0,
                 retries: int = 3, backoff: float = 0.5, delay: float = 1.0,
                 respect_robots: bool = True, honor_crawl_delay: bool = True):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.delay = delay
        self.requests_made = 0
        self._last = 0.0
        self._robots: Optional[robotparser.RobotFileParser] = None
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': user_agent, 'Accept-Language': 'ru-RU,ru;q=0.9'})
        retry = LoggedRetry(total=retries, backoff_factor=backoff, status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=('GET', 'HEAD'), respect_retry_after_header=True)
        for scheme in ('http://', 'https://'):
            self.session.mount(scheme, HTTPAdapter(max_retries=retry))
        if respect_robots:
            self._load_robots(honor_crawl_delay)

    # --- robots.txt
    def _load_robots(self, honor_crawl_delay: bool) -> None:
        rp = robotparser.RobotFileParser()
        try:
            resp = self.session.get(self.base_url + '/robots.txt', timeout=self.timeout)
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
            elif resp.status_code in (401, 403):
                rp.disallow_all = True
            else:
                rp.allow_all = True
        except requests.RequestException as e:
            log.warning('robots.txt не получен (%s), продолжаем с обычной паузой между запросами', e)
            rp.allow_all = True
        self._robots = rp
        wanted = rp.crawl_delay(self.session.headers['User-Agent'])
        if wanted and honor_crawl_delay:
            self.delay = max(self.delay, float(wanted))
            log.info('robots.txt просит паузу %s с между запросами, соблюдаем', wanted)

    def allowed(self, url: str) -> bool:
        return self._robots is None or self._robots.can_fetch(self.session.headers['User-Agent'], url)

    # --- загрузка
    def get(self, url: str) -> str:
        if not self.allowed(url):
            raise FetchError(f'{url}: запрещено в robots.txt')
        wait = self.delay - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        try:
            resp = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as e:
            raise FetchError(f'{url}: {_why(e)}') from e
        finally:
            self._last = time.monotonic()
            self.requests_made += 1
        if resp.status_code != 200:
            raise FetchError(f'{url}: HTTP {resp.status_code}')
        if not resp.encoding or resp.encoding.lower() == 'iso-8859-1':
            resp.encoding = resp.apparent_encoding
        return resp.text
