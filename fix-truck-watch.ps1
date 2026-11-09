# Перейдите в папку и обновите Railway
cd "C:\Users\donga\OneDrive\Documents\deepseek-harness\default-workspace"

# Обновите railway.json
@"
{
  "build": {
    "builder": "nixpacks"
  },
  "deploy": {
    "startCommand": "python watcher.py"
  }
}
"@ | Out-File -Encoding utf8 railway.json

# Отправьте на GitHub
git add railway.json requirements.txt
git commit -m "fix: force nixpacks build for railway"
git push origin main