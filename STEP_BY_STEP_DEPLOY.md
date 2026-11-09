# Пошаговая инструкция по деплою на Railway

## Этап 1: Подготовка аккаунта

### 1.1 Создайте репозитории на GitHub

**Три репозитория:**
```bash
# 1. Truck Watch
mkdir ~/truck-watch && cd ~/truck-watch
git init
# Копируем файлы из default-workspace (кроме .env и state)
# Файлы для git: watcher.py, config.json, subscribers.json, get_chat_id.py, manage_plates.py
#          + .github/workflows/watch.yml

# 2. DealWatch  
mkdir ~/dealwatch && cd ~/dealwatch
git init
# Файлы для git: dealwatch.py, browser.py, sources.py, mailbox.py, notify.py
#          + config.json, state.json

# 3. FreeLLM Bot
mkdir ~/freellm-bot && cd ~/freellm-bot
git init
# Файлы: app.py, requirements.txt, .env.example
```

**Или вручную через GitHub.com** — создайте 3 публичных репозитория.

---

## Этап 2: Получение токенов и ID

### 2.1 Создайте 3 бота в @BotFather

```
@BotFather → /newbot
Название: Truck Watch Bot
Username: truck_watch_bot (оканчивается на bot)
→ Скопируйте токен

@BotFather → /newbot
Название: Deal Watch Bot  
Username: deal_watch_bot
→ Скопируйте токен

@BotFather → /newbot
Название: FreeLLM Assistant
Username: free_llm_assistant_bot
→ Скопируйте токен
```

### 2.2 Узнайте chat_id получателей

**Для Truck Watch (4 человека):**
```powershell
cd "C:\Users\donga\OneDrive\Documents\deepseek-harness\default-workspace"
python get_chat_id.py <ТОКЕН_ТРЮЧ_БОТА>
```
Каждый из 4-х человек должен написать боту любое сообщение. После этого скрипт покажет их ID. Запишите все 4 ID.

**Для DealWatch (1 человек - вы):**
Тоже используйте `get_chat_id.py` с токеном Deal Watch бота.

**Для FreeLLM Bot (админы):**
Аналогично — получите свои chat_id.

---

## Этап 3: Деплой на Railway

### 3.1 Зайдите на railway.app
- Перейдите на [railway.app](https://railway.app)
- Войдите через GitHub (кнопка "Login with GitHub")

### 3.2 Создайте проект Truck Watch

**Вариант A: Через GitHub (автоматически)**
```
1. Нажмите "New Project"
2. Выберите "Deploy from GitHub repo"
3. Найдите и выберите репозиторий truck-watch
4. Railway автоматически обнаружит workflow
5. Подождите завершения деплоя (~1-2 минуты)
```

**Вариант B: Вручную**
```
1. New Project → Blank
2. Выберите язык Python
3. Upload files или подключите Git
```

### 3.3 Настройте переменные окружения для каждого проекта

Для **Truck Watch**:
```
TGW_TELEGRAM_TOKEN=ваш_токен_бота
TGW_TELEGRAM_CHAT_IDS=id1,id2,id3,id4  # через запятую
TGW_SHEET_URL=https://docs.google.com/spreadsheets/d/1GLkYhAZ094VIat3n2owKhvzykTAyPqqDDAeT5hdl1Fs/edit
TGW_PLATES=629,718,715,058,124  # если нужен фильтр
TGW_CITIES=Набережные Челны,Москва  # если нужен фильтр
```

Для **DealWatch**:
```
DEALWATCH_TELEGRAM_TOKEN=ваш_токен_бота
DEALWATCH_TELEGRAM_CHAT_IDS=ваш_id
```
⚠️ *Примечание: DealWatch требует Chrome, Railway не поддерживает. Для него используйте Render или локальный запуск.*

Для **FreeLLM Bot**:
```
FREE_LLM_BOT_TOKEN=ваш_токен_бота
FREE_LLM_API_URL=http://localhost:8080
FREE_LLM_ADMINS=ваши_ids_через_запятую
```

---

## Этап 4: Активация ботов

### 4.1 Truck Watch — готов к работе!
После деплоя бот автоматически начнёт опрос таблицы каждые 5 минут (через GitHub Actions). Проверьте Telegram — должны приходить уведомления.

### 4.2 DealWatch — локальный запуск
Так как нужно веб-скрапинг с Chrome:

**Создайте задачу в планировщике Windows:**
```powershell
schtasks /create /tn "DealWatch" /tr "pythonw.exe \"C:\Users\donga\OneDrive\Documents\deepseek-harness\default-workspace\dealwatch\dealwatch.py\"" /sc onlogon /rl highest
```

**Проверка:**
```powershell
cd "C:\Users\donga\OneDrive\Documents\deepseek-harness\default-workspace\dealwatch"
python dealwatch.py --once
```

### 4.3 FreeLLM Bot — локальный запуск с ngrok

**Установите ngrok:**
```powershell
winget install ngrok.ngrok
```

**Запустите туннель:**
```powershell
ngrok http 8080
```
Скопируйте https://xxxx.ngrok.io адрес

**Обновите переменную FREE_LLM_API_URL:**
```
FREE_LLM_API_URL=https://xxxx.ngrok.io/v1
```

**Запустите бота:**
```powershell
cd C:\Users\donga\tg-suite\free-llm-bot
python app.py
```

---

## Этап 5: Проверка работы

| Бот | Команда проверки | Ожидаемый результат |
|-----|-----------------|---------------------|
| Truck Watch | Написать `/start` | Получить справку |
| DealWatch | `--test-notify` | Сообщение в Telegram о тестовом алерте |
| FreeLLM Bot | `/status` | Ответ "API Online" |

---

## Troubleshooting

| Проблема | Решение |
|----------|---------|
| Ошибка `401 Unauthorized` | Токен неверный, пересоздайте в @BotFather |
| Ошибка `chat not found` | Напишите боту первое сообщение |
| DealWatch не запускается | Убедитесь что Chrome установлен |
| FreeLLM Bot не видит API | Проверьте что FreeLLM Desktop запущен |
| Нет уведомлений в Telegram | Проверьте chat_id в конфиге |

---

## Что дальше?

1. **Truck Watch** — работает в облаке ✅
2. **DealWatch** — работает локально на вашем ПК ⚙️
3. **FreeLLM Bot** — работает локально с ngrok 🌐

Все три бота готовы к использованию!
