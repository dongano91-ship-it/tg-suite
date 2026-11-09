# tg-suite

Легальный набор: Telegram-бот (напоминания) + анти-бомбер API + нагрузочный тест.

## Запуск

```powershell
cd C:\Users\donga\tg-suite
pip install -r requirements.txt

# в одном окне — API с защитой
python app\antibomb.py

# в другом — Telegram-бот (напоминания)
python app\bot.py
```

## Команды бота

- `/start` — справка
- `/whoami` — узнать chat_id
- `/remind 18:30 позвонить маме` — напоминание
- `/list` — активные напоминания

## Анти-бомбер API (эмулятор, ничего не отправляет)

- `POST /sms/request` — `{"phone": "79160000000"}`
- `POST /call/request` — то же
- `GET /stats` — сколько пропущено / отклонено

Защита: token bucket на номер, cooldown на IP, denylist, журнал в SQLite.

## Нагрузочный тест

```powershell
python app\loadtest.py --rate 20 --threads 4
```
Показывает, сколько запросов прошло (200), сколько отрезала защита (429).

## Важно

Токен бота был отправлен в чат — после проверки отзовите его в @BotFather
(/revoke) и выпустите новый, обновите `.env`.
