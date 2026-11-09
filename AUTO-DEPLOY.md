# 🚀 Автономный деплой ботов — Инструкция

## Автоматизация выполнена!

Все три бота готовы к деплою. Вот что было сделано:

### ✅ Исправлено и подготовлено:

1. **truck-watch** 
   - `requirements.txt` без BOM
   - `railway.json` без BOM  
   - Правильная структура для Railway
   
2. **dealwatch**
   - Добавлен `Dockerfile` с Chromium
   - Исправлены права доступа
   - Добавлен флаг `--no-sandbox`
   
3. **tg-suite**
   - Добавлен `apscheduler` в `requirements.txt`
   - Обновлён `railway.json`
   - Созданы скрипты автоматизации

---

## 🔧 Одним командой (автоматизация):

### Вариант 1: Через PowerShell (рекомендуется)
```powershell
cd C:\Users\donga\tg-suite
.\deploy-all.bat
```

### Вариант 2: Пошаговая команда
```powershell
# 1. Запустить скрипт проверки и деплоя
cd C:\Users\donga
.\tg-suite\check-status.ps1

# 2. Открыть Railway
Start-Process "https://railway.app"
```

---

## 📋 Ручной деплой (если автоматизация не сработала):

### Шаг 1: Коммитим и пушим всё на GitHub
```powershell
# Truck Watch
cd "C:\Users\donga\OneDrive\Documents\deepseek-harness\default-workspace"
git add -A && git commit -m "prepare railway deploy" && git push origin main

# DealWatch  
cd "C:\Users\donga\dealwatch"
git add -A && git commit -m "prepare railway deploy" && git push origin main

# TG Suite
cd "C:\Users\donga\tg-suite"
git add -A && git commit -m "prepare railway deploy" && git push origin main
```

### Шаг 2: Деплой на Railway
1. Откройте https://railway.app
2. Нажмите **+ New Project** → **Deploy from GitHub repo**
3. Выберите каждый репозиторий по очереди:
   - `truck-watch`
   - `dealwatch`
   - `tg-suite`
4. Для каждого проекта добавьте переменные окружения:

#### Переменные для truck-watch:
| Имя | Значение |
|-----|----------|
| `TGW_TELEGRAM_TOKEN` | Токен от @BotFather |
| `TGW_SHEET_URL` | `https://docs.google.com/spreadsheets/d/1GLkYhAZ094VIat3n2owKhvzykTAyPqqDDAeT5hdl1Fs/edit` |
| `TGW_PLATES` | `629,718,715,058,124` |

#### Переменные для dealwatch:
| Имя | Значение |
|-----|----------|
| `BOT_TOKEN` | Токен от @BotFather |
| `BOT_CHAT_IDS` | Ваш chat_id |

#### Переменные для tg-suite:
| Имя | Значение |
|-----|----------|
| `BOT_TOKEN` | Токен от @BotFather |
| `FREE_LLM_API_URL` | `http://localhost:8080` |

5. Нажмите **Deploy**!

---

## 🎯 Что делать если ошибка?

| Ошибка | Решение |
|--------|---------|
| `InvalidToken` | Проверьте переменную BOT_TOKEN в Railway |
| `ModuleNotFoundError` | Убедитесь что requirements.txt в корне репо |
| `Chrome not found` | DealWatch требует Docker (уже настроено) |

---

## ✨ Результат

После успешного деплоя у вас будут работать:
- 🚛 **Truck Watch** — уведомления о машинах из Google Таблицы
- 🛒 **DealWatch** — мониторинг цен на маркетплейсах
- 🤖 **FreeLLM Bot** — AI-ассистент через Telegram

