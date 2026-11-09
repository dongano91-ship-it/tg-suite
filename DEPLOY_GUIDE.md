# Telegram Bots Suite - Деплой в облако

## Описание ботов

| Бот | Папка | Функционал | Сложность деплоя |
|-----|-------|-----------|------------------|
| **Truck Watch** | `OneDrive/.../default-workspace/` | Мониторинг логистики из Google Таблицы | ✅ Низкая (Python скрипт) |
| **DealWatch** | `OneDrive/.../dealwatch/` | Поиск выгодных цен на маркетплейсах | ⚠️ Средняя (нужен Chrome) |
| **FreeLLM Bot** | `tg-suite/free-llm-bot/` | Интерфейс к FreeLLM API через Telegram | ✅ Низкая (Python скрипт) |

---

## Подготовка к деплою

### Шаг 1: Получите токены ботов от @BotFather

Для каждого бота создайте нового бота:

```
1. Откройте @BotFather в Telegram
2. Напишите /newbot
3. Придумайте имя и username (оканчивается на bot)
4. Скопируйте токен вида: 123456789:AAH...
```

### Шаг 2: Получите chat_id для получателей

**Только для Truck Watch:**
```powershell
cd "C:\Users\donga\OneDrive\Documents\deepseek-harness\default-workspace"
python get_chat_id.py <ТОКЕН>
```
Напишите любому из 4 получателей своему боту сообщение — появится chat_id.

**Для FreeLLM Bot (админы):**
Тоже используйте `get_chat_id.py` для получения chat_id администраторов.

---

## Деплой на Railway

### Бот 1: Truck Watch

**Вариант A: GitHub Actions (рекомендуется)**
Проект уже настроен! Проверьте `.github/workflows/watch.yml`.

**Что нужно сделать:**
1. Создайте репозиторий на GitHub
2. Загрузите файлы проекта (`watcher.py`, `config.json`, `.github/`)
3. В Railway создайте проект → подключите репозиторий
4. Добавьте переменные окружения:
   - `TGW_TELEGRAM_TOKEN` — токен бота
   - `TGW_TELEGRAM_CHAT_IDS` — ID 4 получателей через запятую
   - `TGW_SHEET_URL` — ссылка на таблицу
   - `TGW_PLATES` — номера машин (если нужен фильтр)
   - `TGW_CITIES` — города (если нужен фильтр)

**Запуск:**
```bash
# Локально перед деплоем
cd "C:\Users\donga\OneDrive\Documents\deepseek-harness\default-workspace"
python watcher.py --test-notify
```

---

### Бот 2: DealWatch

**⚠️ Важное примечание:**
Этот проект использует Chrome браузер для скрапинга. Для облачного деплоя нужен сервис с поддержкой браузеров.

**Рекомендации по деплою:**

1. **Render (бесплатный tier)** — поддерживает Docker с браузерами
2. **Local deployment** — запускайте локально с автозапуском
   
**Локальный запуск:**
```powershell
cd "C:\Users\donga\OneDrive\Documents\deepseek-harness\default-workspace\dealwatch"

# Тест уведомлений
python dealwatch.py --test-notify

# Один проход проверки
python dealwatch.py --once

# Постоянный мониторинг
python dealwatch.py
```

**Автозапуск при старте Windows:**
```powershell
schtasks /create /tn "DealWatch" /tr "pythonw.exe \"C:\Users\donga\OneDrive\Documents\deepseek-harness\default-workspace\dealwatch\dealwatch.py\"" /sc onlogon /rl highest
```

---

### Бот 3: FreeLLM Bot

**Вариант A: Локальный запуск (рекомендуется)**

Так как FreeLLM Desktop работает локально, проще запускать бота рядом с ним:

```powershell
# Установите зависимости
cd C:\Users\donga\tg-suite\free-llm-bot
pip install -r requirements.txt

# Запустите бота
python app.py
```

**Конфигурация:**
Скопируйте `.env.example` в `.env` и заполните:
```env
FREE_LLM_BOT_TOKEN=<токен от BotFather>
FREE_LLM_API_URL=http://localhost:8080
FREE_LLM_ADMINS=<ваш chat_id>
```

**Переменные окружения в Windows:**
```powershell
$env:FREE_LLM_BOT_TOKEN = "<токен>"
$env:FREE_LLM_API_URL = "http://localhost:8080"
$env:FREE_LLM_ADMINS = "123456789"
python app.py
```

**Вариант B: Релиз в облако (ngrok туннель)**
Если нужно запускать бота удалённо:
1. Установите ngrok: https://ngrok.com/download
2. Запустите туннель: `ngrok http 8080`
3. Обновите `FREE_LLM_API_URL` на https://xxxx.ngrok.io/v1
4. Разверните бота на Railway

---

## Быстрый старт

```powershell
# 1. Откройте PowerShell от имени администратора

# 2. Для бота 1 (Truck Watch) - тест
cd "C:\Users\donga\OneDrive\Documents\deepseek-harness\default-workspace"
python watcher.py --test-notify

# 3. Для бота 2 (DealWatch) - тест
cd dealwatch
python dealwatch.py --test-notify

# 4. Для бота 3 (FreeLLM) - настройка
cd "C:\Users\donga\tg-suite\free-llm-bot"
copy .env.example .env
# Отредактируйте .env
python app.py
```

---

##Troubleshooting

### Ошибки при деплое

| Ошибка | Решение |
|--------|---------|
| `Telegram ответил 401` | Неверный токен бота. Пересоздайте через @BotFather |
| `chat not found` | Напишите боту первое сообщение в Telegram |
| `CERTIFICATE_VERIFY_FAILED` | Добавьте сертификаты в конфиг |
| `Connection refused` | Проверьте что FreeLLM Desktop запущен |

### Проверка работы

**Truck Watch:**
```powershell
python watcher.py --list    # показать текущие строки
python watcher.py --once    # один цикл проверки
```

**DealWatch:**
```powershell
python dealwatch.py --test-notify  # тест уведомлений
python dealwatch.py --once         # один проход
```

**FreeLLM Bot:**
```
Напишите /status боту — должна появиться проверка API
```

---

## Поддержка

Все проекты находятся под контролем:
- Truck Watch + DealWatch: `C:\Users\donga\OneDrive\Documents\deepseek-harness\default-workspace\`
- FreeLLM Bot: `C:\Users\donga\tg-suite\free-llm-bot\`
- TG Suite: `C:\Users\donga\tg-suite\`
