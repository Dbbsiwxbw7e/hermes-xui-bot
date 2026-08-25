"""
All user-facing text and keyboards in one place — premium dark-console style.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

APP_NAME = "⚡️ HERMES X-UI ⚡️"

# ── decorative building blocks ─────────────────────────────────
TOP = "╔═══════════════════════╗"
BOT = "╚═══════════════════════╝"
SEP = "╠═══════════════════════╣"
SIDE = "║"

def box_line(left: str, body: str = "") -> str:
    return f"{left} {body}" if body else left

def header(subtitle: str = "") -> str:
    h = f"{TOP}\n{SIDE}   <b>{APP_NAME}</b>   {SIDE}\n"
    if subtitle:
        h += f"{SIDE}   <i>{subtitle}</i>   {SIDE}\n"
    return h + BOT

STATUS_ICONS = {
    "SUCCESS": "🟢", "FAILED": "🔴", "CRASHED": "💥",
    "DEPLOYING": "🟡", "BUILDING": "🟡", "WAITING": "⚪️", "REMOVED": "⚫️",
}

# ── main menu ──────────────────────────────────────────────────
WELCOME = (
    f"{header('دستیار هوشمند دپلوی 3x-ui')}\n\n"
    "🛰 <b>دپلوی خودکار</b> روی Railway\n"
    "     └ چند پنل، همزمان، با poll واقعی\n\n"
    "📡 <b>وضعیت زنده</b>\n"
    "     └ تا SUCCESS واقعی منتظر می‌مونه\n\n"
    "🔗 <b>لینک آماده</b>\n"
    "     └ VLESS + TLS + WS قابل ایمپورت فوری\n\n"
    f"{SEP}\n"
    "👇 <b>از منو شروع کن یا دستور بزن</b>"
)

MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("🚀 دپلوی جدید", callback_data="go_deploy"),
     InlineKeyboardButton("🔗 لینک اتصال", callback_data="go_link")],
    [InlineKeyboardButton("📊 وضعیت", callback_data="go_status"),
     InlineKeyboardButton("ℹ️ راهنما", callback_data="go_help")],
    [InlineKeyboardButton("🗑 حذف پروژه", callback_data="go_delete")],
])

HELP_TEXT = (
    f"{header('راهنمای کامل')}\n\n"
    "🔐 <b>۱. اتصال</b>\n"
    "<code>/connect TOKEN</code>\n"
    "     └ توکن از dashboard.railway.com → Tokens\n\n"
    "🚀 <b>۲. دپلوی</b>\n"
    "<code>/deploy</code>\n"
    "     └ ساخت همه پنل‌ها + انتظار برای SUCCESS\n\n"
    "🔗 <b>۳. لینک اتصال</b>\n"
    "<code>/link</code>\n"
    "     └ اینباند VLESS+TLS و خروجی vless://\n\n"
    "📊 <b>۴. وضعیت</b>\n"
    "<code>/status</code>\n\n"
    "🗑 <b>۵. حذف</b>\n"
    "<code>/delete</code>\n\n"
    f"{SEP}\n"
    "⚠️ بعد از /connect پیام توکن رو پاک کن 🗑\n"
    "🔑 پیش‌فرض پنل: admin / admin — فوراً عوضش کن!"
)

NOT_CONNECTED = (
    f"{header('قفل شد! 🔒')}\n\n"
    "برای ادامه اول به Railway وصل شو:\n\n"
    "<code>/connect TOKEN</code>\n\n"
    f"{BOT}\n💡 توکن از داشبورد Railway بخش Tokens گرفته میشه."
)

CANCELLED = f"{header}عملیات لغو شد ❌".replace("{header}", header('انصراف')) if False else (
    f"{header('انصراف')}\n\n❌ عملیات لغو شد."
)

CONNECTED_OK = "{email}"
def connected_msg(email: str) -> str:
    return (
        f"{header('اتصال برقرار شد ✅')}\n\n"
        f"👤 کاربر: <code>{email}</code>\n"
        f"🆔 Workspace متصل شد\n\n"
        f"{SEP}\n"
        "🎉 آماده‌ای! حالا بزن: 🚀 <code>/deploy</code>"
    )

TOKEN_INVALID = (
    f"{header('خطا ⛔️')}\n\n"
    "❌ توکن قبول نشد. دوباره چکش کن:\n"
    "<code>/connect TOKEN_درست</code>"
)


# ── progress / deploy views ────────────────────────────────────
def progress_bar(step: int, total: int, width: int = 14) -> str:
    filled = round(step * width / max(total, 1))
    return "▓" * filled + "░" * (width - filled)


def deploy_step(step: int, total: int, title: str, detail: str = "") -> str:
    pct = round(step * 100 / max(total, 1))
    txt = (
        f"{header('در حال اجرا...')}\n\n"
        f"{progress_bar(step, total)}  <b>{pct}%</b>\n"
        f"📍 مرحله {step}/{total}\n\n"
        f"{SEP}\n{title}"
    )
    if detail:
        txt += f"\n{detail}"
    return txt


def panel_summary(panels: list[dict]) -> str:
    s = ""
    for p in panels:
        icon = STATUS_ICONS.get(p.get("status", ""), "⏳")
        s += f"\n{icon} <b>{p['name']}</b>  ·  {p.get('region', '')}"
        if p.get("url"):
            s += f"\n     🌐 {p['url'].replace('https://','')}/managepanel/"
    return s


DEPLOY_DONE_ALL = "🎉 <b>همه پنل‌ها آماده‌ان!</b>"
DEPLOY_DONE_PARTIAL = "⚠️ بعضی پنل‌ها هنوز کامل نیستن"


def deploy_report(lines: list[str], all_ok: bool, n_ok: int, n_total: int) -> str:
    verdict = DEPLOY_DONE_ALL if all_ok else DEPLOY_DONE_PARTIAL
    txt = (
        f"{header('گزارش نهایی دپلوی')}\n\n"
        f"{'🟢' if all_ok else '🟡'} نتیجه: <b>{n_ok}/{n_total}</b> موفق\n\n"
        f"{SEP}{lines and '' or ''}"
    )
    for l in lines:
        txt += l
    txt += f"\n{SEP}\n{verdict}\n\n👉 قدم بعد: 🔗 <code>/link</code>"
    return txt


def status_row(icon: str, name: str, detail: str = "") -> str:
    row = f"\n{icon} <b>{name}</b>"
    if detail:
        row += f"\n     └ {detail}"
    return row


# ── links view ─────────────────────────────────────────────────
def links_summary(links: list[tuple[str, str]]) -> str:
    """links: list of (panel_name, vless_url_or_error)"""
    s = f"{header('لینک‌های اتصال 🔗')}\n"
    ok = sum(1 for _, u in links if u.startswith("vless://"))
    s += f"\n{'🟢' if ok == len(links) else '🟡'} آماده: <b>{ok}/{len(links)}</b>\n{SEP}\n"
    for name, url in links:
        s += f"\n📡 <b>{name}</b>\n<code>{url}</code>\n"
    s += (f"\n{SEP}\n"
          "📲 <b>نصب:</b> کپی کن → v2rayNG → Import from clipboard\n"
          "🔐 TLS از Railway · مسیر WS داخل لینک هست")
    return s

LINKS_EMPTY = (
    f"{header('چیزی برای نشون دادن نیست 📭')}\n\n"
    "هنوز پنلی دپلوی نشده.\nاول بزن: 🚀 <code>/deploy</code>"
)
