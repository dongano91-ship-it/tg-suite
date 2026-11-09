# === Бот 3: FreeLLM Telegram Bot ===
# Интерфейс к FreeLLM API через Telegram
# Работает с локальной версией FreeLLM Desktop

# Требования:
# 1. Установленный FreeLLM Desktop (FreeLLMAPI.exe)
# 2. Бот должен знать адрес API (по умолчанию http://localhost:8080)
# 3. Если бот запускается удалённо — нужен туннель к localhost (ngrok или аналог)

# Для деплоя на Railway:
# 1. Установите переменные окружения:
#    - FREE_LLM_BOT_TOKEN=<токен от BotFather>
#    - FREE_LLM_API_URL=http://localhost:8080 (или публичный URL)
#    - FREE_LLM_ADMINS=<chat_id админов, через запятую>
#
# 2. Если FreeLLM работает локально — настройте ngrok:
#    ngrok http 8080
#    Обновите FREE_LLM_API_URL на https://xxxx.ngrok.io/v1

# Локальный запуск:
cd tg-suite/free-llm-bot
python app.py

