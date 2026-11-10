"""
playwright_browser.py — управление Chrome через Playwright (headless).
Использует настоящий Chromium, обходит антибот-защиты маркетплейсов.
"""
from __future__ import annotations

import json
import os
import time
from typing import Optional, List, Dict, Any

# Playwright imports
try:
    from playwright.sync_api import sync_playwright, Page, Browser
except ImportError:
    sync_playwright = None
    Page = None
    Browser = None

EXTRACT_JS = r"""
(function (cfg) {
  var out = [];
  var limit = cfg.limit || 40;

  function clean(s) { return (s || '').replace(/\s+/g, ' ').trim(); }

  function digits(el) {
    if (!el) return null;
    var t = (el.textContent || '').replace(/[\s   ]/g, '');
    var m = t.match(/(\d{2,9})/);
    return m ? parseInt(m[1], 10) : null;
  }

  function priceFromElement(el) {
    if (!el) return null;
    var nodes = el.querySelectorAll('[class*="price" i], [data-price], [itemprop="price"]');
    for (var i = 0; i < nodes.length; i++) {
      var p = digits(nodes[i]);
      if (p) return p;
    }
    var t = clean(el.textContent);
    if (t.length < 160 && /[₽€$]|руб/i.test(t)) {
      return digits(el);
    }
    return null;
  }

  function findPrice(start) {
    var node = start;
    for (var d = 0; d < 7 && node; d++, node = node.parentElement) {
      var p = priceFromElement(node);
      if (p) return p;
      if ((node.textContent || '').length > 4000) break;
    }
    return null;
  }

  function pickTitle(root) {
    var best = '', bestScore = -1;
    var nodes = root.querySelectorAll('img[alt], [title], span, div, a, p');
    var limitNodes = Math.min(nodes.length, 250);
    for (var k = 0; k < limitNodes; k++) {
      var e = nodes[k];
      var t = '';
      if (e.tagName === 'IMG') t = e.getAttribute('alt') || '';
      else if (e.hasAttribute && e.hasAttribute('title')) t = e.getAttribute('title');
      if (!t) t = clean(e.textContent);
      if (!t) continue;
      if (/\d+\s*[₽€$]|руб\.?$/i.test(t)) continue;
      if (!/[A-Za-zА-я]{2}/.test(t)) continue;
      if (t.length < 12 || t.length > 150) continue;
      if (e.children && e.children.length > 6) continue;
      var score = t.length + (e.tagName === 'IMG' ? 30 : 0);
      if (score > bestScore) { bestScore = score; best = t; }
    }
    return best;
  }

  function titleOf(card, a) {
    var t = '';
    if (cfg.title_sel) { var e = card.querySelector(cfg.title_sel); if (e) t = clean(e.textContent); }
    if (!t && cfg.title_sel_attr) {
      var e2 = card.querySelector(cfg.title_sel_attr.sel);
      if (e2) t = clean(e2.getAttribute(cfg.title_sel_attr.attr) || e2.textContent);
    }
    if (!t && a) t = clean(a.getAttribute('title') || a.getAttribute('aria-label') || '');
    if (!t && a) t = pickTitle(a);
    if (!t) { var img = card.querySelector('img[alt]'); if (img) t = clean(img.getAttribute('alt')); }
    return t;
  }

  function idOf(card, url) {
    if (cfg.id_attr) {
      var v = card.getAttribute(cfg.id_attr);
      if (v) return v;
    }
    var m = (url || '').match(cfg.id_re || /(\d{5,})/);
    return m ? m[1] : url;
  }

  function push(url, title, price, id) {
    if (!url || !price || price < (cfg.min_price || 0)) return;
    if (out.some(function (o) { return o.url === url; })) return;
    out.push({ url: url, title: title, price: price, id: String(id) });
  }

  if (cfg.mode === 'cards') {
    var cards = document.querySelectorAll(cfg.selector);
    for (var i = 0; i < cards.length && out.length < limit; i++) {
      var card = cards[i];
      var a = cfg.link_sel ? card.querySelector(cfg.link_sel) : card.querySelector('a[href]');
      var price = null;
      if (cfg.price_sel_attr) {
        var pe = card.querySelector(cfg.price_sel_attr.sel);
        if (pe) price = parseInt(String(pe.getAttribute(cfg.price_sel_attr.attr)).replace(/\D/g, ''), 10);
      }
      if (!price) price = digits(cfg.price_sel ? card.querySelector(cfg.price_sel) : null);
      if (!price) price = findPrice(card);
      if (!price) continue;
      var url = a ? a.href : '';
      push(url, titleOf(card, a), price, idOf(card, url));
    }
  } else {
    var links = document.querySelectorAll(cfg.selector);
    var seen = {};
    for (var j = 0; j < links.length && out.length < limit; j++) {
      var link = links[j];
      var href = link.href;
      if (!href || seen[href]) continue;
      seen[href] = 1;
      var p = findPrice(link);
      if (!p) continue;
      push(href, titleOf(link, link), p, idOf(link, href));
    }
  }
  return JSON.stringify(out);
})(__CFG__)
"""


class PlaywrightBrowserError(Exception):
    """Ошибка браузера Playwright."""
    pass


class PlaywrightChrome:
    """Обертка над Playwright для headless Chrome."""

    def __init__(self, headless: bool = True, wait_until: str = "networkidle"):
        self.playwright = None
        self.browser = None
        self.page = None
        self.headless = headless
        self.wait_until = wait_until
        self._context = None

    def start(self) -> bool:
        """Запуск браузера."""
        try:
            from playwright.sync_api import sync_playwright

            self.playwright = sync_playwright().start()

            # Ищем Chrome/Chromium executable path
            chrome_paths = [
                os.environ.get("CHROME_BIN", "/usr/bin/chromium"),
                os.environ.get("DEALWATCH_CHROME", "/usr/bin/chromium"),
                "/usr/bin/chromium-browser",
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable",
                os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux/chrome"),
            ]
            executable_path = None
            for p in chrome_paths:
                if os.path.exists(p):
                    executable_path = p
                    break

            log.info(f"Chrome path: {executable_path}")

            # Запускаем Chrome в headless режиме
            launch_kwargs = dict(
                headless=self.headless,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-software-rasterizer',
                    '--disable-accelerated-2d-canvas',
                    '--disable-webrtc',
                    '--window-size=1440,900',
                    '--lang=ru-RU',
                    '--disable-extensions',
                    '--disable-background-networking',
                ]
            )
            if executable_path and os.path.exists(executable_path):
                launch_kwargs['executable_path'] = executable_path
                log.info(f"Using custom Chrome at {executable_path}")
            else:
                # Fallback: используем встроенный Playwright chromium
                log.info("Using Playwright's bundled Chromium")

            self.browser = self.playwright.chromium.launch(**launch_kwargs)

            # Создаем контекст с прокси anti-detect
            self._context = self.browser.new_context(
                viewport={'width': 1440, 'height': 900},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                locale='ru-RU',
                timezone_id='Europe/Moscow',
            )

            # Добавляем заголовки для имитации реального браузера
            self._context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                window.chrome = { runtime: {} };
            """)

            # Создаем страницу
            self.page = self._context.new_page()

            return True

        except Exception as e:
            raise PlaywrightBrowserError(f"Не удалось запустить браузер: {e}")

    def goto(self, url: str, timeout: int = 60000) -> bool:
        """Переход по URL."""
        try:
            response = self.page.goto(url, wait_until=self.wait_until, timeout=timeout)
            if response is None:
                return False
            return response.status == 200
        except Exception as e:
            raise PlaywrightBrowserError(f"Ошибка перехода: {e}")

    def scroll(self, steps: int = 3, pause: float = 0.5) -> None:
        """Скроллинг страницы."""
        for _ in range(steps):
            try:
                self.page.evaluate("window.scrollBy(0, 800)")
            except Exception:
                pass
            time.sleep(pause)

    def evaluate(self, js_code: str) -> Any:
        """Выполнение JavaScript."""
        try:
            return self.page.evaluate(js_code)
        except Exception as e:
            raise PlaywrightBrowserError(f"Ошибка выполнения JS: {e}")

    def screenshot(self, path: str = None) -> Optional[str]:
        """Снимок экрана."""
        if not path:
            path = f"screenshot_{int(time.time())}.png"
        self.page.screenshot(path=path, full_page=True)
        return path

    def close(self) -> None:
        """Закрытие браузера."""
        try:
            if self.page:
                self.page.close()
            if self._context:
                self._context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass
        finally:
            self.page = None
            self._context = None
            self.browser = None
            self.playwright = None


def search_with_playwright(platform: dict, query: str, limit: int = 40) -> tuple[list[dict], dict]:
    """
    Поиск товаров на конкретной площадке через Playwright.
    Возвращает (offers, diag_info).
    """
    offers = []
    error_info = {}

    browser = None
    try:
        browser = PlaywrightChrome(headless=True)
        browser.start()

        plat_name = platform.get("name", "Unknown")
        plat_key = platform.get("key", "?")
        url_template = platform.get("url", "")

        if not url_template or "{q}" not in url_template:
            error_info[f"{plat_key}"] = "Нет шаблона URL"
            return [], error_info

        # Формируем URL поиска
        import urllib.parse
        url = url_template.replace("{q}", urllib.parse.quote_plus(query))

        # Прогрев если нужен
        warmup = platform.get("warmup")
        if warmup:
            try:
                browser.goto(warmup, timeout=30000)
            except Exception:
                pass

        # Переход на поиск
        browser.goto(url, timeout=platform.get("timeout", 60) * 1000)

        # Скроллим
        for _ in range(platform.get("scroll_steps", 3)):
            try:
                browser.page.evaluate("window.scrollBy(0, 900)")
            except Exception:
                break
            time.sleep(0.5)

        # Извлечение данных через JS
        cfg = {k: v for k, v in platform.items()
               if k in ("mode", "selector", "link_sel", "title_sel", "title_sel_attr",
                        "price_sel", "price_sel_attr", "id_attr", "id_re", "min_price")}
        cfg["limit"] = limit

        js = EXTRACT_JS.replace("__CFG__", json.dumps(cfg, ensure_ascii=False))
        raw = browser.evaluate(js)

        if raw:
            offers = json.loads(raw)
            for o in offers:
                o.setdefault("title", "")
                o["price"] = int(o.get("price", 0))

        # Диагностика
        try:
            diag = browser.evaluate("""
                JSON.stringify({
                    title: document.title,
                    url: location.href,
                    body_len: (document.body && document.body.innerText || '').length
                })
            """)
            if diag:
                d = json.loads(diag)
                if d.get("body_len", 0) < 300 and not offers:
                    error_info[f"{plat_key}"] = f"пустая страница: {d.get('title', '?')[:50]}"
        except Exception:
            pass

    except Exception as e:
        error_info[f"{plat_key}"] = str(e)[:100]
    finally:
        if browser:
            browser.close()

    return offers, error_info
