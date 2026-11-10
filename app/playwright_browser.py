"""
playwright_browser.py — Поиск товаров через Playwright.
Собирает реальные цены, описания и картинки с маркетплейсов.
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
    """Основной поиск через Playwright."""
    if not sync_playwright:
        return [], {"error": "Playwright не установлен"}

    products = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--disable-setuid-sandbox']
            )

            context = browser.new_context(
                viewport={'width': 1440, 'height': 900},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                locale='ru-RU'
            )
            page = context.new_page()

            # Пробуем Wildberries
            wb_url = f"https://www.wildberries.ru/catalog/0/search.aspx?search={urllib.parse.quote_plus(query)}"
            _scrape_site(page, wb_url, "Wildberries", query, products, limit)

            # Если мало результатов, пробуем Ozon
            if len(products) < 2:
                ozon_url = f"https://www.ozon.ru/search/?text={urllib.parse.quote_plus(query)}"
                _scrape_site(page, ozon_url, "Ozon", query, products, limit)

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
             "is_search": True, "reason": "Открыть поиск на WB"},
            {"title": f"Ozon: {query}", "price": 0, "platform": "Ozon",
             "url": f"https://www.ozon.ru/search/?text={q}",
             "is_search": True, "reason": "Открыть поиск на Ozon"},
            {"title": f"Avito: {query}", "price": 0, "platform": "Avito",
             "url": f"https://www.avito.ru/rossiya?q={q}",
             "is_search": True, "reason": "Б/у и новые товары"},
            {"title": f"Yandex Market: {query}", "price": 0, "platform": "Яндекс Маркет",
             "url": f"https://market.yandex.ru/search?text={q}",
             "is_search": True, "reason": "Сравнение цен"},
        ])

    stats = {
        "count": len(products),
        "with_prices": len([p for p in products if p.get('price', 0) > 0]),
        "with_images": len([p for p in products if p.get('image')])
    }

    return products, stats


def _scrape_site(page, url: str, platform: str, query: str, products: list, limit: int):
    """Попробовать скрапить сайт с разными селекторами."""
    try:
        log.info(f"Scraping {platform}...")
        page.goto(url, timeout=30000, wait_until="networkidle")
        time.sleep(3)

        # Скроллим для загрузки ленивых изображений
        for _ in range(2):
            page.evaluate("window.scrollBy(0, 600)")
            time.sleep(0.3)

        # JavaScript для извлечения товаров
        js_code = f"""() => {{
            const results = [];
            // Try multiple selector patterns
            const selectors = [
                '[data-badge]',
                '.product-card',
                '.goods-item',
                'article',
                '[class*="ProductCard"]'
            ];

            for (const sel of selectors) {{
                const cards = document.querySelectorAll(sel);
                if (cards.length > 0) {{
                    cards.forEach(card => {{
                        const titleEl = card.querySelector('h1,h2,h3,[class*=Title],[class*=Name],a[href]');
                        const priceEl = card.querySelector('[class*=Price],[class*=price],span[itemprop="price"]');
                        const imgEl = card.querySelector('img[data-src],img[src*="photo"],img[class*=Image]');
                        const linkEl = card.querySelector('a[href*="/detail"],a[href*="/product"]');

                        if (titleEl && priceEl) {{
                            const title = (titleEl.textContent || '').trim().substring(0, 60);
                            const priceText = (priceEl.textContent || '').replace(/[^0-9]/g, '');
                            const price = parseInt(priceText);

                            if (title.length > 3 && !isNaN(price) && price > 50) {{
                                results.push({{
                                    title: title,
                                    price: price,
                                    image: imgEl ? (imgEl.getAttribute('data-src') || imgEl.src || '') : '',
                                    url: linkEl ? linkEl.href : ''
                                }});
                            }}
                        }}
                    }});
                    break;
                }}
            }}
            return results.slice(0, {limit});
        }}"""

        items = page.evaluate(js_code)

        if items:
            for item in items:
                # Избегаем дубликатов
                if not any(p.get('url') == item.get('url', '') for p in products):
                    products.append({
                        "title": item["title"],
                        "description": f"Товар на {platform}",
                        "image": item.get("image", ""),
                        "price": item.get("price", 0),
                        "old_price": 0,
                        "discount": 0,
                        "platform": platform,
                        "url": item.get("url", ""),
                        "rating": 0,
                        "reason": _gen_reason(item.get("price", 0), query)
                    })
            log.info(f"{platform}: found {len(items)} products")

    except Exception as e:
        log.debug(f"{platform} scrape failed: {e}")


def _gen_reason(price: int, query: str) -> str:
    """Генерирует объяснение почему цена хороша."""
    thresholds = {
        "iphone": 80000,
        "android": 40000,
        "dyson": 30000,
        "nike": 8000,
        "airpods": 20000,
        "playstation": 50000,
    }

    for keyword, threshold in thresholds.items():
        if keyword in query.lower():
            if price < threshold * 0.7:
                return "🔥 Отличная цена! Ниже рынка"
            elif price < threshold:
                return "💰 Хорошая цена по рынку"
            else:
                return f"📊 Проверьте актуальность цены"

    if price < 10000:
        return "✅ Низкая цена"
    elif price < 50000:
        return "📌 Средняя цена"
    else:
        return f"💵 Цена: {price:,} руб"


class PlaywrightBrowserError(Exception):
    pass
