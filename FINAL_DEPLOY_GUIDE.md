# 🚀 最终部署指南 - 三个 Telegram 机器人

## ✅ 已完成的工作

### 已推送到 GitHub 的三个仓库：

| 项目 | 仓库地址 | 状态 |
|------|----------|------|
| **Truck Watch** (物流监控) | `dongano91-ship-it/truck-watch` | ✅ 已推送 |
| **DealWatch** (市场机会监控) | `dongano91-ship-it/dealwatch` | ✅ 已推送 |
| **TG Suite** (FreeLLM + Reminders) | `dongano91-ship-it/tg-suite` | ✅ 已推送 |

---

## 📋 Railway 部署步骤（手动操作）

### 第 1 步：连接 GitHub 到 Railway

由于自动化工具被安全限制阻止，请**手动完成以下步骤**：

#### A. 访问 Railway
1. 打开 https://railway.app
2. 点击 **"Log in with GitHub"**
3. 授权 Railway 访问你的 GitHub 账户

#### B. 如果遇到"无项目"问题
1. 点击右上角头像 → **Account Settings**
2. 进入 **Integrations** → **GitHub**
3. 点击 **"Connect"** 或 **"Authorize"**
4. 选择你的账户 `dongano91-ship-it`
5. 选择 **"All repositories"** 或手动选择：
   - `truck-watch`
   - `dealwatch`
   - `tg-suite`
6. 点击 **"Install & Authorize"**

---

### 第 2 步：创建 Railway 项目

连接成功后，创建三个项目：

#### 项目 1: Truck Watch (物流监控)
```
New Project → Deploy from GitHub repo → 选择 truck-watch
```

添加环境变量：
| 变量名 | 值 |
|--------|-----|
| `TGW_TELEGRAM_TOKEN` | 从 @BotFather 获取的 bot token |
| `TGW_TELEGRAM_CHAT_IDS` | 4个接收者的 chat_id（逗号分隔） |
| `TGW_SHEET_URL` | https://docs.google.com/spreadsheets/d/1GLkYhAZ094VIat3n2owKhvzykTAyPqqDDAeT5hdl1Fs/edit |

#### 项目 2: DealWatch (市场机会监控)
```
New Project → Deploy from GitHub repo → 选择 dealwatch
```

添加环境变量：
| 变量名 | 值 |
|--------|-----|
| `BOT_TOKEN` | 第二个 bot 的 token |
| `BOT_CHAT_IDS` | 接收通知的 chat_id |

⚠️ **注意**：DealWatch 需要 Chrome 浏览器环境。Railway 不支持，建议使用本地部署或 Render。

#### 项目 3: TG Suite (FreeLLM Bot + Reminders)
```
New Project → Deploy from GitHub repo → 选择 tg-suite
```

添加环境变量：
| 变量名 | 值 |
|--------|-----|
| `FREE_LLM_BOT_TOKEN` | 第三个 bot 的 token |
| `FREE_LLM_API_URL` | http://localhost:8080（需 ngrok 隧道） |
| `ADMIN_CHAT_IDS` | 管理员 chat_id |

---

### 第 3 步：获取 Bot Token 和 Chat ID

#### 获取 Bot Token
1. 在 Telegram 搜索 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot`
3. 设置名称和 username（必须以 bot 结尾）
4. 复制生成的 token（格式：`123456789:AAH...`）

#### 获取 Chat ID
对于每个 bot：
1. 给 bot 发一条消息
2. 访问：`https://api.telegram.org/bot<TOKEN>/getUpdates`
3. 找到 `"chat":{"id":XXXXXXXXXX}` 中的数字

或者运行脚本：
```powershell
cd C:\Users\donga\OneDrive\Documents\deepseek-harness\default-workspace
python get_chat_id.py <TOKEN>
```

---

## 🔧 备选方案：本地部署

如果 Railway 配置困难，可以本地运行：

### Truck Watch (推荐 GitHub Actions)
已在 `.github/workflows/watch.yml` 中配置好，代码会每 5 分钟自动运行。

### DealWatch (本地运行)
```powershell
cd C:\Users\donga\dealwatch
python dealwatch.py --test-notify  # 测试
python dealwatch.py               # 运行
```

### FreeLLM Bot (需 ngrok)
```powershell
# 1. 启动 FreeLLM Desktop
# 2. 创建 ngrok 隧道
ngrok http 8080

# 3. 复制 ngrok URL，例如 https://xxxx.ngrok.io
# 4. 更新配置
# FREE_LLM_API_URL=https://xxxx.ngrok.io/v1

# 5. 运行 bot
cd C:\Users\donga\tg-suite\free-llm-bot
python app.py
```

---

## 📝 检查清单

- [ ] 在 Railway 连接了 GitHub
- [ ] 创建了 3 个 Projects
- [ ] 为每个 Project 添加了环境变量
- [ ] 获得了 3 个 Bot Token
- [ ] 获得了所有需要的 Chat IDs
- [ ] 点击 Deploy 并查看 Logs

---

## ❓ 常见问题

**Q: Railway 显示 "No projects found"**
- A: 重新授权 GitHub 连接，确保选择了正确的账户

**Q: 部署后报错 "token not found"**
- A: 检查环境变量名称是否正确，必须是 `BOT_TOKEN` 而不是其他名字

**Q: DealWatch 无法在 Railway 运行**
- A: 使用本地部署，或改用 Render（支持 Docker + 浏览器）

**Q: FreeLLM API 连接失败**
- A: 确保 FreeLLM Desktop 正在运行，且 ngrok 隧道正常

---

## 📞 需要帮助？

如果出现任何问题，请提供：
1. Railway 项目的错误日志截图
2. 当前设置的 env var 列表（隐藏敏感信息）
3. 具体的错误信息

祝部署顺利！🎉
