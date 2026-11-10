"""
playwright_browser.py — Поиск лучших цен с картинками и аналитикой.
Использует Price.ru API + прямые ссылки на маркетплейсы.
"""
from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
from typing import Optional, List, Dict, Any

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("playwright_browser")

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


def _http_get(url: str, headers: dict | None = None, timeout: int = 10) -> tuple[int, str]:
    """Simple HTTP GET with error handling."""
    try:
        req = urllib.request.Request(url, headers=headers or {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/html',
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        return 0, str(e)[:100]


def search_price_ru(query: str, limit: int = 8) -> tuple[list[dict], dict]:
    """Search via Price.ru API for real prices and images."""
    offers = []

    try:
        url = f"https://prices.ru/api/v1/search?q={urllib.parse.quote_plus(query)}&limit={limit * 2}"
        status, body = _http_get(url, {'Accept': 'application/json'})

        if status != 200:
            log.warning(f"Price.ru returned {status}")
            return [], {"error": f"http_{status}"}

        data = json.loads(body)

        for item in data.get('items', [])[:limit]:
            price = int(item.get('price', 0))
            old_price = int(item.get('old_price', 0) or 0)

            # Calculate discount
            discount = 0
            if old_price > price > 0:
                discount = round((1 - price / old_price) * 100)

            offers.append({
                "url": item.get('url', ''),
                "title": item.get('name', query),
                "image": item.get('image', item.get('photo', '')),
                "price": price,
                "old_price": old_price,
                "discount": discount,
                "platform": item.get('shop', 'Price.ru'),
                "rating": item.get('rating', 0),
                "reason": _generate_reason(price, old_price, query)
            })

    except Exception as e:
        log.error(f"Price.ru search failed: {e}")

    return offers, {"method": "price_ru", "count": len(offers)}


def search_ozon_direct(query: str, limit: int = 5) -> list[dict]:
    """Try direct Ozon API (works sometimes without auth)."""
    offers = []

    try:
        url = f"https://www.ozon.ru/api/composer-api.bx/publicweb/api/v2/product/get?search_text={urllib.parse.quote_plus(query)}&lat=55.7558&lon=37.6173&ui-region-id=1"
        status, body = _http_get(url)

        if status == 200 and 'products' in body:
            data = json.loads(body)
            for prod in data.get('products', [])[:limit]:
                price_info = prod.get('priceInfo', {})
                price = int(price_info.get('totalAmount', {}).get('value', 0) or 0)
                old_price = int(price_info.get('baseAmount', {}).get('value', 0) or 0)

                offers.append({
                    "url": prod.get('links', {}).get('page', ''),
                    "title": prod.get('name', query)[:80],
                    "image": prod.get('images', [{}])[0].get('url', '') if prod.get('images') else '',
                    "price": price,
                    "old_price": old_price,
                    "discount": round((1 - price/old_price)*100) if old_price > price > 0 else 0,
                    "platform": "Ozon",
                    "reason": _generate_reason(price, old_price, query)
                })
    except Exception as e:
        log.debug(f"Ozon direct failed: {e}")

    return offers


def _generate_reason(price: int, old_price: int, query: str) -> str:
    """Generate human-readable reason why this is a good deal."""
    reasons = []

    if old_price > 0 and price < old_price:
        discount = round((1 - price / old_price) * 100)
        if discount >= 30:
            reasons.append(f"🔥 Скидка {discount}% — отличная цена!")
        elif discount >= 15:
            reasons.append(f"⚡ Скидка {discount}% — выгодная покупка")
        else:
            reasons.append(f"💰 Скидка {discount}% — нормально")

    if price < 10000:
        reasons.append("Низкая цена для категории")
    elif price < 50000:
        reasons.append("Средняя цена по рынку")
    else:
        reasons.append(f"Цена: {price:,} ₽")

    return ". ".join(reasons) if reasons else "Проверьте актуальность цены"


def build_marketplace_links(query: str) -> list[dict]:
    """Build direct search links for major marketplaces."""
    links = [
        {
            "url": f"https://www.wildberries.ru/catalog/0/search.aspx?search={urllib.parse.quote_plus(query)}",
            "title": f"Wildberries: {query}",
            "platform": "Wildberries",
            "is_search": True
        },
        {
            "url": f"https://www.avito.ru/rossiya?q={urllib.parse.quote_plus(query)}",
            "title": f"Авито: {query}",
            "platform": "Avito",
            "is_search": True
        },
        {
            "url": f"https://market.yandex.ru/search?text={urllib.parse.quote_plus(query)}",
            "title": f"Яндекс Маркет: {query}",
            "platform": "Yandex Market",
            "is_search": True
        },
        {
            "url": f"https://www.leroymerlin.ru/supplement/search/?q={urllib.parse.quote_plus(query)}",
            "title": f"Леруа Мерлен: {query}",
            "platform": "Leroy Merlin",
            "is_search": True
        },
        {
            "url": f"https://www.kastey.ru/catalog/search?s={urllib.parse.quote_plus(query)}",
            "title": f"Castorama: {query}",
            "platform": "Castorama",
            "is_search": True
        },
    ]
    return links


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
    Main search function combining multiple sources.
    Returns offers with prices, images, and deal analysis.
    """
    all_offers = []

    # Try Price.ru API first (most reliable)
    price_offers, price_stats = search_price_ru(query, limit)
    all_offers.extend(price_offers)

    # Try Ozon direct API
    ozon_offers = search_ozon_direct(query, limit // 2)
    all_offers.extend(ozon_offers)

    # Add marketplace search links
    marketplace_links = build_marketplace_links(query)
    all_offers.extend(marketplace_links)

    # Remove duplicates by URL
    seen_urls = set()
    unique_offers = []
    for o in all_offers:
        if o['url'] not in seen_urls:
            seen_urls.add(o['url'])
            unique_offers.append(o)

    # Sort by price (lowest first)
    unique_offers.sort(key=lambda x: x.get('price', 0) or 999999)

    stats = {
        "method": "combined",
        "count": len(unique_offers),
        "price_ru": price_stats.get("count", 0),
        "ozon": len(ozon_offers),
        "marketplaces": len(marketplace_links)
    }

    return unique_offers, stats
