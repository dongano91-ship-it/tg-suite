# Проверка готовности ботов к деплою
Write-Host "=== СТАТУС ГОТОВНОСТИ БОТОВ ===" -ForegroundColor Cyan
Write-Host ""

$projects = @(
    @{Name="Truck Watch"; Path="C:\Users\donga\OneDrive\Documents\deepseek-harness\default-workspace"; Reqs=@("requirements.txt","watcher.py")},
    @{Name="DealWatch"; Path="C:\Users\donga\dealwatch"; Reqs=@("requirements.txt","dealwatch.py","Dockerfile")},
    @{Name="TG Suite"; Path="C:\Users\donga\tg-suite"; Reqs=@("requirements.txt","app/bot.py","free-llm-bot/app.py")}
)

foreach ($proj in $projects) {
    Write-Host "--- $($proj.Name) ---" -ForegroundColor Yellow

    # Проверка наличия файлов
    foreach ($req in $proj.Reqs) {
        $fullPath = Join-Path $proj.Path $req
        if (Test-Path $fullPath) {
            Write-Host "  ✓ $req" -ForegroundColor Green
        } else {
            Write-Host "  ✗ $req NOT FOUND" -ForegroundColor Red
        }
    }

    # Проверка Git
    $gitPath = Join-Path $proj.Path ".git"
    if (Test-Path $gitPath) {
        Set-Location $proj.Path
        $status = git status --porcelain 2>$null
        if (-not $status) {
            Write-Host "  ✓ Git: всё готово к деплою" -ForegroundColor Green
        } else {
            Write-Host "  ⚠ Git: есть неизменённые файлы" -ForegroundColor Yellow
        }
    }
    Write-Host ""
}

Write-Host "=== Готово к деплою! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Для запуска деплоя выполните:" -ForegroundColor White
Write-Host ""
Write-Host "# Обновить все репозитории на GitHub:" -ForegroundColor Cyan
Write-Host 'cd "C:\Users\donga\OneDrive\Documents\deepseek-harness\default-workspace" && git add -A && git commit -m "deploy" && git push'
Write-Host 'cd "C:\Users\donga\dealwatch" && git add -A && git commit -m "deploy" && git push'
Write-Host 'cd "C:\Users\donga\tg-suite" && git add -A && git commit -m "deploy" && git push'
Write-Host ""
Write-Host "# Затем зайдите на https://railway.app и создайте проекты" -ForegroundColor White
