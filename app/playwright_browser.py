"""
playwright_browser.py — Поиск лучших цен с картинками и аналитикой.
Использует CDN-источники + прямые ссылки на маркетплейсы.
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
            'Accept': 'application/json, text/html, */*',
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        return 0, str(e)[:100]


def search_yandex_market(query: str, limit: int = 6) -> list[dict]:
    """Try Yandex Market public data."""
    offers = []

    try:
        # Try fetching from a known public endpoint
        url = f"https://market.yandex.ru/search?text={urllib.parse.quote_plus(query)}&msid=bot_search"
        status, body = _http_get(url)

        if status == 200 and len(body) > 500:
            # Extract product cards using regex
            patterns = {
                'title': r'class="ProductTitle[^"]*"[^>]*>([^<]+)<',
                'price': r'class="PriceValue-value[^"]*"[^>]*>([\d\s]+)<',
                'old_price': r'class="PriceOld-value[^"]*"[^>]*>([\d\s]+)<',
                'link': r'href="(https://market\.yandex\.ru/[^"]+)"',
                'image': r'img src="([^"]+\.jpg[^"]*)"',
            }

            for title in re.findall(patterns['title'], body):
                price = 0
                for p_match in re.findall(patterns['price'], body):
                    try:
                        price = int(p_match.replace(' ', ''))
                        break
                    except:
                        pass

                if title.strip() and query.lower() in title.lower():
                    offers.append({
                        "url": f"https://market.yandex.ru/search?text={urllib.parse.quote_plus(query)}",
                        "title": title.strip()[:70],
                        "image": "",
                        "price": price,
                        "platform": "Яндекс Маркет",
                        "is_link": True
                    })

                if len(offers) >= limit:
                    break

    except Exception as e:
        log.debug(f"Yandex Market parse failed: {e}")

    return offers[:limit]


def search_avito_simple(query: str, limit: int = 5) -> list[dict]:
    """Parse Avito search results (lightweight)."""
    offers = []

    try:
        url = f"https://www.avito.ru/rossiya?q={urllib.parse.quote_plus(query)}"
        status, body = _http_get(url)

        if status == 200:
            # Look for item listings
            items = re.findall(r'data-item-id="(\d+)"[^>]*>.*?class="item-title[^"]*">([^<]+)', body, re.DOTALL)

            for item_id, title in items[:limit]:
                offers.append({
                    "url": f"https://www.avito.ru/item/{item_id}",
                    "title": title.strip()[:70],
                    "image": "",
                    "price": 0,
                    "platform": "Авито",
                    "is_link": True
                })

    except Exception as e:
        log.debug(f"Avito parse failed: {e}")

    return offers[:limit]


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
        reasons.append(f"Цена от {price:,} руб")

    return ". ".join(reasons) if reasons else "Проверьте актуальность цены"


def build_marketplace_links(query: str) -> list[dict]:
    """Build direct search links for major Russian marketplaces."""
    q = urllib.parse.quote_plus(query)

    links = [
        {
            "url": f"https://www.wildberries.ru/catalog/0/search.aspx?search={q}",
            "title": f"Wildberries: {query}",
            "platform": "Wildberries",
            "is_search": True,
            "reason": "Крупнейший маркетплейс с широким ассортиментом"
        },
        {
            "url": f"https://www.ozon.ru/search/?text={q}",
            "title": f"Ozon: {query}",
            "platform": "Ozon",
            "is_search": True,
            "reason": "Огромный выбор товаров с быстрой доставкой"
        },
        {
            "url": f"https://market.yandex.ru/search?text={q}",
            "title": f"Яндекс Маркет: {query}",
            "platform": "Яндекс Маркет",
            "is_search": True,
            "reason": "Сравнение цен от разных продавцов"
        },
        {
            "url": f"https://www.avito.ru/rossiya?q={q}",
            "title": f"Авито: {query}",
            "platform": "Авито",
            "is_search": True,
            "reason": "Б/у и новые товары от частных лиц"
        },
        {
            "url": f"https://www.mvideo.ru/search?searchText={q}",
            "title": f"M.Video: {query}",
            "platform": "М.Видео",
            "is_search": True,
            "reason": "Электроника и бытовая техника"
        },
        {
            "url": f"https://www.dns-shop.ru/search/?q={q}",
            "title": f"DNS: {query}",
            "platform": "DNS",
            "is_search": True,
            "reason": "Техника и электроника"
        },
        {
            "url": f"https://www.citilink.ru/search/?text={q}",
            "title": f"Citilink: {query}",
            "platform": "CITILINK",
            "is_search": True,
            "reason": "Компьютеры и электроника"
        },
        {
            "url": f"https://www.leroymerlin.ru/supplement/search/?q={q}",
            "title": f"Leroy Merlin: {query}",
            "platform": "Леруа Мерлен",
            "is_search": True,
            "reason": "Стройка и ремонт"
        },
        {
            "url": f"https://www.oxi.ru/search?q={q}",
            "title": f"Oxi: {query}",
            "platform": "Oxi",
            "is_search": True,
            "reason": "Китайские товары"
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

    # Try Yandex Market first
    ym_offers = search_yandex_market(query, limit // 2)
    all_offers.extend(ym_offers)

    # Try Avito for used goods
    avito_offers = search_avito_simple(query, limit // 2)
    all_offers.extend(avito_offers)

    # Add all marketplace search links
    marketplace_links = build_marketplace_links(query)
    all_offers.extend(marketplace_links)

    # Remove duplicates by URL
    seen_urls = set()
    unique_offers = []
    for o in all_offers:
        if o['url'] not in seen_urls:
            seen_urls.add(o['url'])
            unique_offers.append(o)

    # Stats
    stats = {
        "method": "multi_source",
        "count": len(unique_offers),
        "ym": len(ym_offers),
        "avito": len(avito_offers),
        "marketplaces": len(marketplace_links)
    }

    return unique_offers, stats
