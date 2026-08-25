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
    [InlineKeyboardButton("👤 اکانت‌ها", callback_data="sec_account"),
     InlineKeyboardButton("🚀 دپلوی", callback_data="sec_deploy")],
    [InlineKeyboardButton("🛰 TCP Proxy", callback_data="go_tcp"),
     InlineKeyboardButton("🕸 Proxy", callback_data="sec_proxy")],
    [InlineKeyboardButton("📥 اینباندها", callback_data="sec_inbound"),
     InlineKeyboardButton("📊 وضعیت", callback_data="go_status")],
    [InlineKeyboardButton("ℹ️ راهنما", callback_data="go_help")],
])

WELCOME_BODY = (
    "👤 <b>اکانت‌ها</b> — چند اکانت Railway، سوییچ آنی\n"
    "🚀 <b>دپلوی</b> — ساخت پنل + اتصال خودکار نودها\n"
    "🛰 <b>TCP Proxy</b> — چرخش با پورت و تعداد دلخواه\n"
    "🕸 <b>Proxy</b> — بخش ویژه (به‌زودی)\n"
    "📥 <b>اینباندها</b> — VLESS+TLS و لینک آماده\n\n"
)

BACK_MAIN = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔙 منوی اصلی", callback_data="refresh_menu")],
])

def welcome_msg(name: str = "", account_label: str = "") -> str:
    who = f", <b>{name}</b>" if name else ""
    badge = f"👤 اکانت فعال: <b>{account_label}</b>\n" if account_label else "⚪️ هنوز اکانتی ثبت نشده\n"
    return (
        f"{header(f'سلام{who} 👋')}\n\n"
        f"{badge}"
        "🛰 کنترل‌پنل کامل 3x-ui روی Railway:\n\n"
        "👤 <b>اکانت‌ها</b> — چند اکانت، سوییچ آنی\n"
        "🚀 <b>دپلوی</b> — ساخت پنل + اتصال خودکار نودها\n"
        "🛰 <b>TCP Proxy</b> — چرخش با پورت و تعداد دلخواه\n"
        "🕸 <b>Proxy</b> — بخش ویژه (به‌زودی)\n"
        "📥 <b>اینباندها</b> — VLESS+TLS و لینک آماده\n\n"
        f"{SEP}\n👇 یک بخش رو انتخاب کن:"
    )

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
    "اول از بخش 👤 <b>اکانت‌ها</b> یه اکانت Railway اضافه کن.\n\n"
    f"{BOT}\n💡 توکن از dashboard.railway.com → Tokens گرفته میشه."
)

CANCELLED = f"{header('انصراف')}\n\n❌ عملیات لغو شد."

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

# ── TCP Proxy section ──────────────────────────────────────────
def tcp_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛰 چرخش TCP Proxy", callback_data="tcp_start")],
        [InlineKeyboardButton("📋 لیست پیشنهادی", callback_data="tcp_domains"),
         InlineKeyboardButton("⚙️ تنظیمات من", callback_data="tcp_settings")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="refresh_menu")],
    ])


TCP_WELCOME = (
    f"{header('TCP Proxy Manager 🛰')}\n\n"
    "برای هر پنل می‌تونی چند TCP Proxy بچرخونی:\n\n"
    "🎯 <b>هدف:</b> رسیدن به دامنه‌های خوش‌اسم (monorail, nozomi...)\n"
    "🔢 <b>تعداد:</b> هر پنل چند پروکسی همزمان\n"
    "🔌 <b>پورت:</b> پورت اپلیکیشن هر پروکسی\n"
    "📋 <b>لیست پیشنهادی:</b> قابل ویرایش از داخل ربات\n\n"
    f"{SEP}\n👇 انتخاب کن:"
)


def settings_text(uid_settings: dict) -> str:
    count = uid_settings.get("count", 2)
    port = uid_settings.get("port", 443)
    mode = "🔀 دامنه‌های تأیید" if uid_settings.get("mode", "good") == "good" else "🎲 رندم"
    return (
        f"{header('تنظیمات TCP Proxy ⚙️')}\n\n"
        f"🔢 تعداد پروکسی برای هر پنل: <b>{count}</b>\n"
        f"🔌 پورت شروع: <b>{port}</b> (هر پروکسی بعدی +۱)\n"
        "     └ ⚠️ هر TCP باید پورت یکتا داشته باشه — خودکار مدیریت میشه\n"
        f"🎯 حالت چرخش: {mode}\n\n"
        f"{SEP}\n👇 تغییر بده:"
    )


def settings_keyboard(s: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1️⃣", callback_data="tcpset_count:1"),
         InlineKeyboardButton("2️⃣", callback_data="tcpset_count:2"),
         InlineKeyboardButton("3️⃣", callback_data="tcpset_count:3"),
         InlineKeyboardButton("4️⃣", callback_data="tcpset_count:4")],
        [InlineKeyboardButton("🔌 پورت: 443", callback_data="tcpset_port:443"),
         InlineKeyboardButton("8080", callback_data="tcpset_port:8080"),
         InlineKeyboardButton("2053", callback_data="tcpset_port:2053")],
        [InlineKeyboardButton(("✅" if s.get("mode", "good") == "good" else "") + " 🔀 تأیید",
                              callback_data="tcpset_mode:good"),
         InlineKeyboardButton(("✅" if s.get("mode") == "rnd" else "") + " 🎲 رندم",
                              callback_data="tcpset_mode:rnd")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="tcp_back")],
    ])


def domains_text(domains: list[str]) -> str:
    body = "\n".join(f"  {i}. <code>{d}</code>" for i, d in enumerate(domains, 1))
    return (
        f"{header('لیست دامنه‌های پیشنهادی 📋')}\n\n"
        f"{body or '  (خالی)'}\n\n{SEP}\n"
        f"📊 مجموعه: <b>{len(domains)}</b> دامنه"
    )


def domains_keyboard(domains: list[str]) -> InlineKeyboardMarkup:
    rows = []
    # one remove button per domain (max 12)
    for i, d in enumerate(domains[:12]):
        short = d.replace(".proxy.rlwy.net", "")
        rows.append([InlineKeyboardButton(f"🗑 {short}", callback_data=f"tcpdel:{d}"),
                     InlineKeyboardButton(f"↩️ بازگردانی", callback_data="tcpreset")])
    rows.append([InlineKeyboardButton("➕ افزودن دامنه", callback_data="tcpadd_hint")])
    rows.append([InlineKeyboardButton("🔄 بازنشانی به پیش‌فرض", callback_data="tcpreset_all")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="tcp_back")])
    return InlineKeyboardMarkup(rows)


# ── Section: accounts ──────────────────────────────────────────
def accounts_text(accounts: list[dict], active: str) -> str:
    if not accounts:
        body = "  (هیچ اکانتی ثبت نشده)"
    else:
        lines = []
        for a in accounts:
            mark = "🟢" if a["active"] else "⚪️"
            email = f' · <code>{a["email"]}</code>' if a.get("email") else ""
            lines.append(f'{mark} <b>{a["label"]}</b>{email}')
        body = "\n".join(lines)
    return (
        f"{header('مدیریت اکانت‌ها 👤')}\n\n{body}\n\n{SEP}\n"
        f"🟢 اکانت فعال: <b>{active or '—'}</b>"
    )


def accounts_keyboard(accounts: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for a in accounts:
        lbl = a["label"]
        if a["active"]:
            rows.append([InlineKeyboardButton(f"🟢 {lbl} (فعال)", callback_data="noop")])
        else:
            rows.append([InlineKeyboardButton(f"⚪️ سوییچ به {lbl}", callback_data=f"accsw:{lbl}"),
                         InlineKeyboardButton("🗑", callback_data=f"accdel:{lbl}")])
    rows.append([InlineKeyboardButton("➕ افزودن اکانت", callback_data="accadd_hint")])
    rows.append([InlineKeyboardButton("🔙 منوی اصلی", callback_data="refresh_menu")])
    return InlineKeyboardMarkup(rows)

ADD_ACCOUNT_HINT = (
    "{hdr}\n\n"
    "1️⃣ اول یه <b>اسم</b> براش بفرست (مثلاً: <code>اکانت اصلی</code>)\n"
    "2️⃣ بعد توکن Railway رو بفرست\n\n"
    "لغو: /cancel"
)
DOMAIN_SET_HINT = (
    "{hdr}\n\n"
    "دامنه کامل رو بفرست، مثلاً:\n"
    "<code>sg-production-84cd.up.railway.app</code>\n\n"
    "لغو: /cancel"
)

# ── Section: deploy ────────────────────────────────────────────
def deploy_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 دپلوی جدید (همه پنل‌ها)", callback_data="go_deploy")],
        [InlineKeyboardButton("🌐 ست کردن دامنه", callback_data="dep_domain_hint")],
        [InlineKeyboardButton("🔗 اتصال نودها", callback_data="dep_nodes")],
        [InlineKeyboardButton("🗑 حذف پنل/پروژه", callback_data="go_delete")],
        [InlineKeyboardButton("📊 وضعیت", callback_data="go_status")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="refresh_menu")],
    ])

DEPLOY_WELCOME = (
    f"{header('بخش دپلوی 🚀')}\n\n"
    "🚀 <b>دپلوی جدید</b> — ساخت همه پنل‌ها + اتصال خودکار نودها\n"
    "🌐 <b>ست کردن دامنه</b> — دامنه دلخواهت رو به پنل وصل کن\n"
    "🔗 <b>اتصال نودها</b> — وصل کردن دستی پنل‌ها به پنل اصلی\n"
    "🗑 <b>حذف</b> — پنل یا کل پروژه رو پاک کن\n"
    "📊 <b>وضعیت</b> — لیست زنده پروژه‌ها\n\n"
    f"{SEP}\n👇 انتخاب کن:"
)

# ── Section: inbounds ──────────────────────────────────────────
def inbound_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ ساخت اینباند VLESS+TLS", callback_data="inb_create_pick")],
        [InlineKeyboardButton("📋 لیست اینباندها", callback_data="inb_list_pick")],
        [InlineKeyboardButton("🗑 حذف اینباند", callback_data="inb_delete_pick")],
        [InlineKeyboardButton("🔗 لینک‌های اتصال", callback_data="go_link")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="refresh_menu")],
    ])

INBOUND_WELCOME = (
    f"{header('مدیریت اینباندها 📥')}\n\n"
    "➕ <b>ساخت:</b> اینباند VLESS+WS+TLS روی هر پنل\n"
    "📋 <b>لیست:</b> همه اینباندهای یک پنل\n"
    "🗑 <b>حذف:</b> پاک کردن اینباند اضافی\n"
    "🔗 <b>لینک‌ها:</b> خروجی vless:// آماده ایمپورت\n\n"
    f"{SEP}\n👇 انتخاب کن:"
)



# ── Section: proxy (placeholder — content coming later) ───────
def proxy_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚧 به‌زودی...", callback_data="px_soon")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="refresh_menu")],
    ])

PROXY_WELCOME = (
    f"{header('بخش Proxy 🕸')}\n\n"
    "این بخش در حال ساخت است 🚧\n"
    "محتواش رو بعداً مشخص می‌کنیم.\n\n"
    f"{SEP}\n👇 فعلاً از بقیه بخش‌ها استفاده کن:"
)
