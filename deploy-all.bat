@echo off
chcp 65001 >nul
title Автоматизация деплоя ботов

echo ========================================
echo   АВТОМАТИЗАЦИЯ ДЕПЛОЯ 3 БОТОВ
echo ========================================
echo.

REM Проверяем Git
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ОШИБКА: Git не установлен!
    pause
    exit /b 1
)

echo [1/4] Проверка репозиториев...
echo.

cd /d "C:\Users\donga\OneDrive\Documents\deepseek-harness\default-workspace"
echo Truck Watch:
git status --short 2>nul | findstr /v "^$" >nul
if %errorlevel% equ 0 (
    echo   - Есть изменения, коммитим...
    git add -A 2>nul
    git commit -m "fix: prepare railway deploy" 2>nul
    git push origin main 2>nul
) else (
    echo   - Всё готово!
)
echo.

cd /d "C:\Users\donga\dealwatch"
echo DealWatch:
git status --short 2>nul | findstr /v "^$" >nul
if %errorlevel% equ 0 (
    echo   - Есть изменения, коммитим...
    git add -A 2>nul
    git commit -m "fix: prepare railway deploy" 2>nul
    git push origin main 2>nul
) else (
    echo   - Всё готово!
)
echo.

cd /d "C:\Users\donga\tg-suite"
echo TG Suite:
git status --short 2>nul | findstr /v "^$" >nul
if %errorlevel% equ 0 (
    echo   - Есть изменения, коммитим...
    git add -A 2>nul
    git commit -m "fix: prepare railway deploy" 2>nul
    git push origin main 2>nul
) else (
    echo   - Всё готово!
)

echo.
echo [2/4] Открытие Railway...
start https://railway.app

echo.
echo [3/4] Создайте проекты на Railway:
echo   1. Нажмите + New Project -> Deploy from GitHub repo
echo   2. Выберите каждый из 3-х репозиториев:
echo      - truck-watch
echo      - dealwatch
echo      - tg-suite
echo.
echo [4/4] Добавьте переменные окружения:
echo.
echo === TRUCK-WATCH ===
echo TGW_TELEGRAM_TOKEN=ВАШ_ТОКЕН
echo TGW_SHEET_URL=https://docs.google.com/spreadsheets/d/1GLkYhAZ094VIat3n2owKhvzykTAyPqqDDAeT5hdl1Fs/edit
echo TGW_PLATES=629,718,715,058,124
echo.
echo === DEALWATCH ===
echo BOT_TOKEN=ВАШ_ТОКЕН
echo BOT_CHAT_IDS=ВАШ_CHAT_ID
echo.
echo === TG-SUITE ===
echo BOT_TOKEN=ВАШ_ТОКЕН
echo FREE_LLM_API_URL=http://localhost:8080
echo.
echo ========================================
echo   ГОТОВО! Нажмите любую клавишу...
echo ========================================
pause >nul
