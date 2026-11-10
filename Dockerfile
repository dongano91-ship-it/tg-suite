FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    chromium \
    chromium-sandbox \
    fonts-liberation \
    fonts-noto-cjk \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    libxshmfence1 wget curl xdg-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY Procfile .

# Create Chrome profile dir with proper permissions
RUN mkdir -p /app/.chrome-profile && chmod 777 /app/.chrome-profile

ENV CHROME_BIN=/usr/bin/chromium
ENV DEALWATCH_CHROME=/usr/bin/chromium
ENV DISPLAY=:99
ENV PYTHONUNBUFFERED=1

CMD ["python", "app/bot.py"]
