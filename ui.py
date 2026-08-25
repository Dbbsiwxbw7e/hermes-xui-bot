"""
All user-facing text and keyboards in one place.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

DIV = "━━━━━━━━━━━━━━━━━━"
APP_NAME = "⚡️ HERMES X-UI ⚡️"

WELCOME = (
    f"{APP_NAME}\n{DIV}\n\n"
    "🛰 دپلوی خودکار پنل‌های 3x-ui روی Railway\n"
    "📡 منتظر SUCCESS واقعی می‌مونه، حدس نمی‌زنه\n"
    "🔗 اینباند VLESS+TLS و لینک آماده اتصال\n\n"
    f"{DIV}\n👇 از منوی زیر شروع کن."
)

MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("🚀 دپلوی", callback_data="go_deploy"),
     InlineKeyboardButton("🔗 لینک اتصال", callback_data="go_link")],
    [InlineKeyboardButton("📊 وضعیت", callback_data="go_status"),
     InlineKeyboardButton("ℹ️ راهنما", callback_data="go_help")],
])

HELP_TEXT = (
    f"📖 <b>راهنما</b>\n{DIV}\n\n"
    "1️⃣ <code>/connect TOKEN</code> — اتصال Railway\n"
    "2️⃣ <code>/deploy</code> — ساخت پنل‌ها (با poll وضعیت)\n"
    "3️⃣ <code>/link</code> — اینباند + لینک VLESS\n"
    "4️⃣ <code>/status</code> — وضعیت زنده\n"
    "5️⃣ <code>/delete</code> — حذف پروژه\n\n"
    f"{DIV}\n"
    "⚠️ بعد از /connect پیام توکن رو پاک کن 🗑\n"
    "🔑 یوزر/پس پیش‌فرض پنل: admin / admin — سریع عوضش کن!"
)

NOT_CONNECTED = f"🔒 <b>متصل نیستی</b>\n{DIV}\nاول: <code>/connect TOKEN</code>"


def deploy_step(step: int, total: int, title: str, detail: str = "") -> str:
    bar = "▓" * step + "░" * (total - step)
    txt = f"{APP_NAME}\n{bar}  ({step}/{total})\n{DIV}\n{title}"
    if detail:
        txt += f"\n{detail}"
    return txt


def panel_summary(panels: list[dict]) -> str:
    s = ""
    for p in panels:
        icon = "✅" if p.get("url") else "⏳"
        s += f"\n{icon} <b>{p['name']}</b>  ({p['region']})"
        if p.get("url"):
            s += f"\n     🌐 {p['url']}/managepanel/"
    return s


def links_summary(links: list[tuple[str, str]]) -> str:
    """links: list of (panel_name, vless_url)"""
    s = f"🔗 <b>لینک‌های اتصال</b>\n{DIV}\n\n"
    for name, url in links:
        s += f"<b>{name}</b>\n<code>{url}</code>\n\n"
    return s
