"""
playwright_browser.py — Поиск лучших цен через агрегаторы.
Использует публичные API/ссылки без антибота.
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Optional, List, Dict, Any

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("playwright_browser")

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


def search_price_aggregator(query: str, limit: int = 10) -> tuple[list[dict], dict]:
    """
    Ищет товары через агрегаторы цен (Price.ru, Яндекс.Маркет, E-Katalog).
    Возвращает список лучших предложений со ссылками.
    """
    offers = []

    # Price.ru API (публичный)
    try:
        url = f"https://prices.ru/api/v1/search?q={urllib.parse.quote_plus(query)}&limit=5"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        for item in data.get('items', [])[:limit//2]:
            offers.append({
                "url": item.get('url', ''),
                "title": item.get('name', query),
                "price": int(item.get('price', 0)),
                "platform": item.get('shop', 'Price.ru'),
                "rating": item.get('rating', 0)
            })
    except Exception as e:
        log.debug(f"Price.ru error: {e}")

    # Dns-shop (прямой поиск)
    try:
        dns_url = f"https://www.dns-shop.ru/search/?q={urllib.parse.quote_plus(query)}"
        offers.append({
            "url": dns_url,
            "title": f"🔍 Поиск '{query}' в DNS",
            "price": 0,
            "platform": "DNS",
            "is_link": True
        })
    except:
        pass

    # M.Video
    try:
        mvideo_url = f"https://www.mvideo.ru/search?searchText={urllib.parse.quote_plus(query)}"
        offers.append({
            "url": mvideo_url,
            "title": f"🔍 Поиск '{query}' в М.Видео",
            "price": 0,
            "platform": "M.Video",
            "is_link": True
        })
    except:
        pass

    # Citilink
    try:
        citi_url = f"https://www.citilink.ru/search/?text={urllib.parse.quote_plus(query)}"
        offers.append({
            "url": citi_url,
            "title": f"🔍 Поиск '{query}' в Цитилинк",
            "price": 0,
            "platform": "Citilink",
            "is_link": True
        })
    except:
        pass

    return offers, {"method": "aggregator", "count": len(offers)}


def search_marketplaces(query: str, limit: int = 10) -> tuple[list[dict], dict]:
    """
    Генерирует прямые ссылки на поиск по маркетплейсам.
    """
    links = [
        {"url": f"https://www.wildberries.ru/catalog/0/search.aspx?search={urllib.parse.quote_plus(query)}",
         "title": f"🛒 Wildberries: {query}",
         "platform": "Wildberries"},
        {"url": f"https://www.ozon.ru/search/?text={urllib.parse.quote_plus(query)}",
         "title": f"📦 Ozon: {query}",
         "platform": "Ozon"},
        {"url": f"https://market.yandex.ru/search?text={urllib.parse.quote_plus(query)}",
         "title": f"🏪 Яндекс.Маркет: {query}",
         "platform": "Яндекс Маркет"},
        {"url": f"https://www.avito.ru/rossiya?q={urllib.parse.quote_plus(query)}",
         "title": f"📋 Авито: {query}",
         "platform": "Авито"},
    ]
    return links, {"method": "direct_links", "count": len(links)}


class PlaywrightBrowserError(Exception):
    pass


class PlaywrightChrome:
    """Headless Chrome wrapper."""

    def __init__(self, headless: bool = True):
        self.playwright = None
        self.browser = None
        self.page = None
        self.headless = headless
        self._context = None

    def start(self) -> bool:
        if not sync_playwright:
            raise PlaywrightBrowserError("Playwright not installed")

        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            self._context = self.browser.new_context(
                viewport={'width': 1440, 'height': 900},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            self.page = self._context.new_page()
            return True
        except Exception as e:
            raise PlaywrightBrowserError(f"Launch error: {e}")

    def goto(self, url: str, timeout: int = 30000) -> bool:
        try:
            resp = self.page.goto(url, timeout=timeout)
            return resp is not None and resp.status == 200
        except Exception as e:
            raise PlaywrightBrowserError(f"Navigate error: {e}")

    def evaluate(self, js: str) -> Any:
        try:
            return self.page.evaluate(js)
        except Exception as e:
            raise PlaywrightBrowserError(f"JS error: {e}")

    def close(self) -> None:
        try:
            if self.page: self.page.close()
            if self._context: self._context.close()
            if self.browser: self.browser.close()
            if self.playwright: self.playwright.stop()
        except:
            pass
        finally:
            self.page = None
            self._context = None
            self.browser = None
            self.playwright = None


def search_with_playwright(platform: dict, query: str, limit: int = 40) -> tuple[list[dict], dict]:
    """
    Unified search function - returns offers + direct marketplace links.
    """
    plat_key = platform.get("key", "?")

    # Для всех платформ возвращаем агрегированные результаты
    offers, stats = search_price_aggregator(query, limit)

    # Добавляем прямые ссылки на маркетплейсы
    marketplace_links, _ = search_marketplaces(query, limit)
    offers.extend(marketplace_links)

    return offers, stats
