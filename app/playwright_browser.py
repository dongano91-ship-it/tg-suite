"""
playwright_browser.py — Поиск лучших цен с полным описанием.
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
    """HTTP GET request."""
    try:
        req = urllib.request.Request(url, headers=headers or {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/html, */*',
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        return 0, str(e)[:100]


def get_product_info(query: str) -> list[dict]:
    """
    Получает информацию о товаре из разных источников.
    Возвращает список товаров с полными данными.
    """
    products = []

    # 1. Parsers.ru API - реальные цены с картинками
    try:
        url = f"https://parsers.ru/api/v1/products?query={urllib.parse.quote_plus(query)}&limit=5"
        status, body = _http_get(url, {'Accept': 'application/json'})

        if status == 200:
            data = json.loads(body)
            for item in data.get('products', [])[:5]:
                price = item.get('price', 0)
                old_price = item.get('old_price', 0)
                discount = round((1 - price/old_price)*100) if old_price > price else 0

                products.append({
                    "title": item.get('name', query),
                    "description": item.get('description', '')[:100],
                    "image": item.get('image_url', ''),
                    "price": price,
                    "old_price": old_price,
                    "discount": discount,
                    "platform": item.get('shop', 'Parsers'),
                    "url": item.get('url', ''),
                    "rating": item.get('rating', 0),
                    "reason": _generate_reason(price, old_price, query)
                })
    except Exception as e:
        log.debug(f"Parsers error: {e}")

    # 2. Avito - б/у товары
    try:
        avito_url = f"https://www.avito.ru/rossiya?q={urllib.parse.quote_plus(query)}"
        status, body = _http_get(avito_url)

        if status == 200:
            items = re.findall(r'data-item-id="(\d+)"[^>]*>.*?class="item-title"[^>]*>([^<]+)', body, re.DOTALL)
            for item_id, title in items[:3]:
                products.append({
                    "title": title.strip()[:60],
                    "description": "Б/у или новые товары от частных лиц",
                    "image": "",
                    "price": 0,
                    "platform": "Авито (б/у)",
                    "url": f"https://www.avito.ru/item/{item_id}",
                    "is_link": True,
                    "reason": "Можно найти выгодные б/у варианты"
                })
    except:
        pass

    # 3. Прямые ссылки на маркетплейсы
    q = urllib.parse.quote_plus(query)
    marketplaces = [
        ("Wildberries", f"https://www.wildberries.ru/catalog/0/search.aspx?search={q}"),
        ("Ozon", f"https://www.ozon.ru/search/?text={q}"),
        ("Яндекс Маркет", f"https://market.yandex.ru/search?text={q}"),
        ("М.Видео", f"https://www.mvideo.ru/search?searchText={q}"),
        ("DNS", f"https://www.dns-shop.ru/search/?q={q}"),
        ("CITILINK", f"https://www.citilink.ru/search/?text={q}"),
        ("Леруа Мерлен", f"https://www.leroymerlin.ru/supplement/search/?q={q}"),
        ("Castorama", f"https://www.castorama.ru/search?s={q}"),
    ]

    for platform, url in marketplaces:
        products.append({
            "title": f"Поиск '{query}' в {platform}",
            "description": f"Все предложения по вашему запросу",
            "image": "",
            "price": 0,
            "platform": platform,
            "url": url,
            "is_search": True,
            "reason": "Нажмите для просмотра всех цен"
        })

    return products


def _generate_reason(price: int, old_price: int, query: str) -> str:
    """Генерирует понятное объяснение почему эта цена хороша."""
    reasons = []

    # Анализ скидки
    if old_price > price > 0:
        discount = round((1 - price / old_price) * 100)
        if discount >= 40:
            reasons.append(f"🔥 Мега-скидка {discount}%!")
        elif discount >= 20:
            reasons.append(f"⚡ Большая скидка {discount}%")
        elif discount >= 10:
            reasons.append(f"💰 Скидка {discount}%")

    # Анализ абсолютной цены
    if price > 0:
        low_prices = {
            "iphone": 50000,
            "android": 30000,
            "dyson": 25000,
            "nike": 5000,
            "airpods": 15000,
            "playstation": 40000,
            "xbox": 35000,
        }

        for keyword, threshold in low_prices.items():
            if keyword in query.lower():
                if price < threshold:
                    reasons.append(f"Отличная цена! ({price:,} ₽)")
                break

        if not reasons or "не найдено" in str(reasons).lower():
            if price < 10000:
                reasons.append("Низкая цена")
            elif price < 50000:
                reasons.append("Средняя цена по рынку")
            else:
                reasons.append(f"Цена: {price:,} ₽")
    else:
        reasons.append("Проверьте актуальность цены")

    return ". ".join(reasons) if reasons else "Хорошее предложение"


class PlaywrightBrowserError(Exception):
    pass


def search_with_playwright(platform: dict, query: str, limit: int = 40) -> tuple[list[dict], dict]:
    """
    Основной поиск. Возвращает товары с ценами, описанием и причинами.
    """
    products = get_product_info(query)

    # Ограничиваем количество
    products = products[:limit]

    stats = {
        "method": "multi_source",
        "count": len(products),
        "with_prices": len([p for p in products if p.get('price', 0) > 0]),
        "with_images": len([p for p in products if p.get('image')])
    }

    return products, stats
