"""
playwright_browser.py — Реальный парсинг товаров через Playwright.
Собирает цены, описания и картинки с маркетплейсов.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.parse
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("playwright_browser")

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


def search_with_playwright(platform: dict, query: str, limit: int = 40) -> tuple[list[dict], dict]:
    """
    Ищет товары через Playwright с реальными ценами и картинками.
    """
    if not sync_playwright:
        return [], {"error": "Playwright не установлен"}

    products = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
            )

            context = browser.new_context(
                viewport={'width': 1440, 'height': 900},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                locale='ru-RU'
            )
            page = context.new_page()

            # Wildberries
            wb_url = f"https://www.wildberries.ru/catalog/0/search.aspx?search={urllib.parse.quote_plus(query)}"
            _scrape_wb(page, wb_url, query, products, limit)

            # Если мало результатов — пробует другие площадки
            if len(products) < 2:
                ozon_url = f"https://www.ozon.ru/search/?text={urllib.parse.quote_plus(query)}"
                _scrape_ozon(page, ozon_url, query, products, limit)

            browser.close()

    except Exception as e:
        log.error(f"Browser error: {e}")
        products = []

    # Fallback: ссылки на поиск
    if not products:
        q = urllib.parse.quote_plus(query)
        products.extend([
            {"title": f"Wildberries: {query}", "price": 0, "platform": "Wildberries",
             "url": f"https://www.wildberries.ru/catalog/0/search.aspx?search={q}",
             "is_search": True, "reason": "Смотреть все товары"},
            {"title": f"Ozon: {query}", "price": 0, "platform": "Ozon",
             "url": f"https://www.ozon.ru/search/?text={q}",
             "is_search": True, "reason": "Смотреть все товары"},
            {"title": f"Авито: {query}", "price": 0, "platform": "Авито",
             "url": f"https://www.avito.ru/rossiya?q={q}",
             "is_search": True, "reason": "Б/у и новые товары"},
            {"title": f"Яндекс Маркет: {query}", "price": 0, "platform": "Яндекс Маркет",
             "url": f"https://market.yandex.ru/search?text={q}",
             "is_search": True, "reason": "Сравнение цен"},
        ])

    stats = {
        "count": len(products),
        "with_prices": len([p for p in products if p.get('price', 0) > 0]),
        "with_images": len([p for p in products if p.get('image')])
    }

    return products, stats


def _scrape_wb(page, url: str, query: str, products: list, limit: int):
    """Scrape Wildberries products."""
    try:
        page.goto(url, timeout=25000, wait_until="domcontentloaded")
        time.sleep(3)

        items = page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('.product-card, [data-badge]').forEach(card => {
                const titleEl = card.querySelector('h2, .product-card__title, [class*="Title"]');
                const priceEl = card.querySelector('.price__price, [class*="Price"]');
                const imgEl = card.querySelector('img');
                const linkEl = card.querySelector('a[href*="/detail"]');

                if (titleEl && priceEl) {
                    const title = titleEl.textContent.trim().substring(0, 60);
                    const priceText = priceEl.textContent.replace(/[^\\d]/g, '');
                    const price = parseInt(priceText);

                    if (title && !isNaN(price) && title.length > 5) {
                        results.push({
                            title: title,
                            price: price,
                            image: imgEl ? (imgEl.src || imgEl.getAttribute('data-src') || '') : '',
                            url: linkEl ? linkEl.href : ''
                        });
                    }
                }
            });
            return results;
        }""")

        if items:
            for item in items[:limit//2]:
                products.append({
                    "title": item["title"],
                    "description": f"Товар на Wildberries",
                    "image": item["image"],
                    "price": item["price"],
                    "old_price": 0,
                    "discount": 0,
                    "platform": "Wildberries",
                    "url": item["url"],
                    "rating": 0,
                    "reason": _gen_reason(item["price"], query)
                })
                log.info(f"WB found: {item['title'][:30]}... - {item['price']}₽")

    except Exception as e:
        log.debug(f"WB scrape failed: {e}")


def _scrape_ozon(page, url: str, query: str, products: list, limit: int):
    """Scrape Ozon products."""
    try:
        page.goto(url, timeout=25000, wait_until="domcontentloaded")
        time.sleep(3)

        items = page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('[data-kladr-id], .product-card, .offer-card').forEach(card => {
                const titleEl = card.querySelector('h2, .productName, [class*="Name"]');
                const priceEl = card.querySelector('.price-value, [class*="Price"]');
                const imgEl = card.querySelector('img');
                const linkEl = card.querySelector('a[href*="/product/"]');

                if (titleEl && priceEl) {
                    const title = titleEl.textContent.trim().substring(0, 60);
                    const priceText = priceEl.textContent.replace(/[^\\d]/g, '');
                    const price = parseInt(priceText);

                    if (title && !isNaN(price) && title.length > 5) {
                        results.push({
                            title: title,
                            price: price,
                            image: imgEl ? (imgEl.src || '') : '',
                            url: linkEl ? linkEl.href : ''
                        });
                    }
                }
            });
            return results;
        }""")

        if items:
            for item in items[:limit//2]:
                products.append({
                    "title": item["title"],
                    "description": f"Товар на Ozon",
                    "image": item["image"],
                    "price": item["price"],
                    "old_price": 0,
                    "discount": 0,
                    "platform": "Ozon",
                    "url": item["url"],
                    "rating": 0,
                    "reason": _gen_reason(item["price"], query)
                })

    except Exception as e:
        log.debug(f"Ozon scrape failed: {e}")


def _gen_reason(price: int, query: str) -> str:
    """Генерирует причину почему это хорошая цена."""
    thresholds = {
        "iphone": 80000,
        "android": 40000,
        "dyson": 30000,
        "nike": 8000,
        "airpods": 20000,
        "playstation": 50000,
        "xbox": 45000,
        "samsung": 50000,
    }

    for keyword, threshold in thresholds.items():
        if keyword in query.lower():
            if price < threshold * 0.7:
                return "🔥 Отличная цена! Ниже рынка"
            elif price < threshold:
                return "💰 Хорошая цена по рынку"
            else:
                return f"📊 Цена {price:,}₽ — проверьте актуальность"

    if price < 10000:
        return "✅ Низкая цена"
    elif price < 50000:
        return "📌 Средняя цена"
    else:
        return f"💵 {price:,}₽"


class PlaywrightBrowserError(Exception):
    pass
