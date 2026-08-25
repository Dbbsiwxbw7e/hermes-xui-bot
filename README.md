# ⚡️ Hermes X-UI Bot

ربات تلگرامی مدرن برای ساخت خودکار پنل‌های 3x-ui روی Railway — با معماری ماژولار تمیز.

## ✨ قابلیت‌ها

- 🔐 **اتصال امن به Railway** — توکن فقط در RAM (user_data تلگرام)، هر کاربر توکن خودش
- 🚀 **دپلوی N پنل** — تعداد و ریجن پنل‌ها از `config.py` یا env قابل تغییره
- 📡 **Poll وضعیت دیپلوی** — ربات منتظر SUCCESS میمونه، حدس نمی‌زنه
- 🔗 **ساخت اینباند VLESS+WS+TLS** — هماهنگ با TLS لبه Railway
- 📋 **لینک آماده اتصال** — خروجی `vless://` قابل ایمپورت مستقیم در v2rayNG
- 🧩 **معماری ماژولار:**

```
hermes_xui_bot/
├── bot.py            # نقطه ورود + هندلرها
├── config.py         # تنظیمات مرکزی (env-first)
├── ui.py             # متن‌ها و کیبوردها (تمام UI یکجا)
├── railway_api.py    # کلاینت GraphQL Railway
├── xui_api.py        # کلاینت REST پنل 3x-ui
└── requirements.txt
```

## 📱 دستورات

| دستور | توضیح |
|---|---|
| `/start` | منوی اصلی |
| `/connect TOKEN` | اتصال به Railway |
| `/deploy` | ساخت و دپلوی همه پنل‌ها |
| `/link` | ساخت اینباند + لینک VLESS برای پنل‌های موجود |
| `/status` | وضعیت زنده سرویس‌ها |
| `/delete` | حذف پروژه |

## 🚀 راه‌اندازی

```bash
pip install -r requirements.txt
export BOT_TOKEN="توکن ربات از @BotFather"
python bot.py
```

## 🔧 تنظیمات (config.py)

همه تنظیمات از متغیر محیطی خونده میشن، با مقدار پیش‌فرض منطقی:

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `BOT_TOKEN` | — (اجباری) | توکن ربات تلگرام |
| `DOCKER_IMAGE` | ghcr 3x-ui | ایمیج Docker پنل |
| `PROJECT_NAME` | hermes-xui | نام پروژه در Railway |
| `PANELS` | NL,US,SG,DE | لیست «اسم:ریجن» جدا شده با کاما |
| `INBOUND_PORT` | 8080 | پورت داخلی اینباند |
| `INBOUND_PATH` | /cdn | مسیر WebSocket |

## 📄 لایسنس

MIT
