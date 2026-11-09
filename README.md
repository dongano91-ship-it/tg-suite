# TG Suite - Telegram Bot Collection

一组轻量级 Telegram 机器人集合，包含：

1. **Reminders Bot** (`app/bot.py`) - 提醒服务机器人
   - `/start` - 帮助信息
   - `/whoami` - 查看 chat_id
   - `/remind HH:MM 文本` - 创建提醒
   - `/list` - 查看待处理提醒

2. **FreeLLM Bot** (`free-llm-bot/app.py`) - AI 助手机器人
   - 连接到本地 FreeLLM API
   - 支持对话历史
   - `/start`, `/clear`, `/status`, `/help`

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 BOT_TOKEN

# 运行
python app/bot.py
```

## Railway 部署

参见 [DEPLOY_GUIDE.md](DEPLOY_GUIDE.md) 和 [STEP_BY_STEP_DEPLOY.md](STEP_BY_STEP_DEPLOY.md)

## 环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `BOT_TOKEN` | Telegram Bot Token | `123456789:AAH...` |
| `FLASK_PORT` | Flask 端口 (预留) | `20129` |
| `FREE_LLM_API_URL` | FreeLLM API 地址 | `http://localhost:8080` |
| `ADMIN_CHAT_IDS` | 管理员 chat_id (逗号分隔) | `123456789,987654321` |

## 目录结构

```
tg-suite/
├── app/                    # 提醒机器人
│   ├── bot.py             # 主程序
│   └── reminders.db       # SQLite 数据库 (不提交)
├── free-llm-bot/          # FreeLLM 机器人
│   ├── app.py             # 主程序
│   ├── requirements.txt   # 依赖
│   └── .env.example       # 环境变量模板
├── dealwatch/             # DealWatch 集成 (来自 deepseek-harness)
├── railway.json           # Railway 配置
├── Procfile               # Railway 启动命令
├── requirements.txt       # Python 依赖
└── *.md                   # 文档
```
