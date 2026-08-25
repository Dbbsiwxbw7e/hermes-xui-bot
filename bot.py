"""
Hermes X-UI Bot — entry point and handlers.

Flow:
  /deploy  → create project + services, deploy, poll until SUCCESS,
             generate domains
  /link    → login to each panel, create VLESS+TLS inbound,
             hand back ready-to-import vless:// links
"""
import asyncio
import logging
import os
import uuid

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters,
)

import config
import ui
from railway_api import RailwayAPI, RailwayError
from xui_api import PanelClient, XUIError, build_vless_link, wait_until_ready
from tcp_api import TCPProxyAPI, normalize_domains
from tcp_state import TCPState
from account_store import AccountStore

# shared persistent state for TCP feature (domains list + per-user settings)
TCP = TCPState()
ACCOUNTS = AccountStore()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("hermes-xui")


# ── helpers ────────────────────────────────────────────────────
async def say(msg, text: str, keyboard=None):
    """Edit-or-send helper that never raises."""
    try:
        await msg.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        pass


def get_api(ctx) -> RailwayAPI | None:
    """API bound to the ACTIVE account of this user (multi-account aware)."""
    uid = None
    # ctx.user_data is per-user dict; use its id if available via bot_data trick
    token = ctx.user_data.get("_active_token")
    if not token:
        return None
    return RailwayAPI(token)


def active_token(ctx) -> str:
    return ctx.user_data.get("_active_token") or ""


def refresh_active(ctx, uid):
    """Load active account's token into user_data. Call at start & after switch."""
    acc = ACCOUNTS.get(uid)
    if acc:
        ctx.user_data["_active_token"] = acc["token"]
        ctx.user_data["_active_label"] = ACCOUNTS.active_label(uid)
        return True
    ctx.user_data.pop("_active_token", None)
    return False


def require_token(func):
    """Decorator: reply with NOT_CONNECTED if no railway token stored."""
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not active_token(ctx):
            target = update.callback_query.message if update.callback_query else update.message
            await target.reply_text(ui.NOT_CONNECTED, parse_mode="HTML")
            return
        return await func(update, ctx)
    return wrapper


def run_blocking(fn, *args):
    return asyncio.to_thread(fn, *args)


# ── commands ───────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    refresh_active(ctx, uid)
    name = update.effective_user.first_name or ""
    await update.message.reply_text(
        ui.welcome_msg(name, ctx.user_data.get("_active_label", "")),
        reply_markup=ui.MENU, parse_mode="HTML")


@require_token
async def cmd_deploy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    api = get_api(ctx)
    total_steps = len(config.PANELS) + 2
    status = await update.message.reply_text(
        ui.deploy_step(0, total_steps, "🚀 شروع دپلوی..."), parse_mode="HTML")

    # 1) project
    project_id = environment_id = ""
    try:
        ws_id, email = await run_blocking(api.whoami)
        proj = await run_blocking(api.create_project, config.PROJECT_NAME, ws_id)
        project_id = proj["id"]
        environment_id = proj.get("environmentId", "")
        if not environment_id:
            envs = await run_blocking(api.get_environments, project_id)
            environment_id = envs[0]["id"] if envs else ""
        await say(status, ui.deploy_step(1, total_steps,
                   f"📦 پروژه ساخته شد: <code>{config.PROJECT_NAME}</code>"))
    except RailwayError as e:
        await say(status, f"❌ خطا در ساخت پروژه:\n<code>{e}</code>")
        return

    # 2) create services + deploy + domain (parallel per panel)
    panels = []
    sem = asyncio.Semaphore(4)

    async def provision(p):
        async with sem:
            name = p["name"]
            try:
                svc = await run_blocking(api.create_service, name, project_id,
                                         config.DOCKER_IMAGE)
                await run_blocking(api.deploy, svc["id"], environment_id)
                domain = await run_blocking(api.create_domain, svc["id"],
                                            environment_id, 3000)
                url = f"https://{domain}" if domain else ""
                panel = {"name": name, "region": p["region"],
                         "service_id": svc["id"], "url": url}
                panels.append(panel)
                await say(status, ui.deploy_step(
                    1 + len(panels), total_steps,
                    f"🔨 {name} ارسال شد برای دپلوی",
                    ui.panel_summary(panels)))
            except RailwayError as e:
                log.warning("provision %s failed: %s", name, e)

    await asyncio.gather(*(provision(p) for p in config.PANELS))

    if not panels:
        await say(status, "❌ هیچ سرویسی ساخته نشد")
        return

    # track all provisioned panels for the final report
    ctx.user_data["deployed_panels"] = list(panels)
    provisioned = list(panels)

    # 3) poll deployments until SUCCESS (real verification!)
    deadline = asyncio.get_event_loop().time() + config.DEPLOY_POLL_TIMEOUT
    while panels and asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(config.DEPLOY_POLL_INTERVAL)
        pending = []
        for p in panels:
            d = await run_blocking(api.latest_deployment, p["service_id"])
            st = (d or {}).get("status", "")
            p["status"] = st or "WAITING"
            if st == "SUCCESS":
                p["ready"] = True
                if not p["url"] and d.get("staticUrl"):
                    p["url"] = f"https://{d['staticUrl']}"
            elif st in ("FAILED", "CRASHED", "REMOVED"):
                p["failed"] = True
            else:
                pending.append(p)

        done = sum(1 for p in provisioned if p.get("ready") or p.get("failed"))
        await say(status, ui.deploy_step(
            2, total_steps, f"📡 در انتظار SUCCESS... ({done}/{len(provisioned)})",
            ui.panel_summary(provisioned)))
        panels = pending

    # final report — one fresh query per panel, fancy console output
    lines = []
    ok = 0
    for p in provisioned:
        d = await run_blocking(api.latest_deployment, p["service_id"])
        st = (d or {}).get("status") or "WAITING"
        p["status"] = st
        if st == "SUCCESS":
            ok += 1
            if not p["url"] and d.get("staticUrl"):
                p["url"] = f"https://{d['staticUrl']}"
        lines.append(ui.status_row(
            ui.STATUS_ICONS.get(st, "⏳"), p["name"],
            p.get("url", "").replace("https://", "") + "/managepanel/" if p.get("url") else st))
    ctx.user_data["deployed_panels"] = provisioned
    await say(status, ui.deploy_report(lines, ok == len(provisioned), ok,
                                       len(provisioned)))

    # 4) auto-link nodes to the main panel (best-effort, non-blocking failures)
    if config.AUTO_LINK_NODES and ok >= 2:
        await say(status,
                  f"{ui.header('🔗 اتصال خودکار نودها...')}\n\n"
                  "پنل‌های آماده به پنل اصلی وصل میشن...")
        link_lines = []
        main = next((p for p in provisioned if p["name"] == config.MAIN_PANEL), None)
        others = [p for p in provisioned if p.get("ready") and p.get("url")
                  and p["name"] != (main or {}).get("name")]

        async def link_one(p):
            def _work():
                mp = PanelClient(main["url"], config.XUI_USERNAME, config.XUI_PASSWORD)
                if not mp.login():
                    raise XUIError("ورود به پنل اصلی ناموفق")
                np = PanelClient(p["url"], config.XUI_USERNAME, config.XUI_PASSWORD)
                if not np.login():
                    raise XUIError(f"ورود به {p['name']} ناموفق")
                nuuid = np.get_uuid()
                ntoken = np.create_api_token()
                res = mp.add_node(p["name"], p["url"], nuuid, ntoken)
                if not res.get("success"):
                    raise XUIError(res.get("msg", "ناموفق"))
                return True
            try:
                await run_blocking(_work)
                link_lines.append(f"✅ <b>{p['name']}</b> → متصل به {config.MAIN_PANEL}")
            except Exception as e:
                link_lines.append(f"⚠️ <b>{p['name']}</b> → {str(e)[:60]}")
            await say(status,
                      f"{ui.header('🔗 اتصال نودها...')}\n{ui.SEP}\n"
                      + "\n".join(link_lines))

        for p in others:
            await link_one(p)

        summary = "\n".join(link_lines) or "(پنل دیگه‌ای برای اتصال نبود)"
        await say(status,
                  f"{ui.header('نتیجه اتصال نودها 🔗')}\n{ui.SEP}\n{summary}\n\n"
                  f"🏠 نود اصلی: <b>{config.MAIN_PANEL}</b>")


@require_token
async def cmd_link(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    api = get_api(ctx)
    deployed = ctx.user_data.get("deployed_panels", [])
    if not deployed:
        await update.message.reply_text(ui.LINKS_EMPTY, parse_mode="HTML")
        return

    status = await update.message.reply_text(
        ui.deploy_step(0, 3, "🔗 ساخت اینباند و لینک..."), parse_mode="HTML")

    links = []
    for i, p in enumerate(deployed, start=1):
        if not p.get("url"):
            continue
        await say(status, ui.deploy_step(i - 1, 3, f"⚙️ پردازش {p['name']}..."))

        def _do():
            client = PanelClient(p["url"], config.XUI_USERNAME, config.XUI_PASSWORD)
            if not client.login():
                raise XUIError(f"ورود به پنل {p['name']} شکست خورد")
            u = str(uuid.uuid4())
            res = client.create_vless_tls_inbound(
                uuid=u, email=f"{p['name'].lower()}-user",
                domain=p["url"].replace("https://", "").rstrip("/"),
                port=config.INBOUND_PORT, path=config.INBOUND_PATH)
            if not res.get("success"):
                raise XUIError(f"{p['name']}: {res.get('msg', 'unknown')}")
            return build_vless_link(p["url"], u, config.INBOUND_PATH,
                                    f"Hermes-{p['name']}")

        try:
            link = await run_blocking(_do)
            links.append((p["name"], link))
        except (XUIError, Exception) as e:
            log.warning("link %s failed: %s", p["name"], e)
            links.append((p["name"], f"⚠️ خطا: {str(e)[:80]}"))

    await say(status, ui.links_summary(links))


@require_token
async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    api = get_api(ctx)
    status = await update.message.reply_text("📊 ...", parse_mode="HTML")

    def _collect():
        rows = []
        for proj in api.list_projects():
            rows.append(proj)
        return rows

    try:
        projects = await run_blocking(_collect)
    except RailwayError as e:
        await say(status, f"❌ {e}")
        return

    if not projects:
        await say(status, ui.header('پروژه‌ای نیست 📭'))
        return

    txt = f"{ui.header('پروژه‌های Railway 📦')}\n{ui.SEP}\n"
    for p in sorted(projects, key=lambda x: x.get("createdAt", ""), reverse=True)[:10]:
        txt += f"\n📦 <b>{p['name']}</b>\n     └ <code>{p['id'][:8]}</code>"
    txt += f"\n\n{ui.BOT}\n📊 مجموعه: <b>{len(projects)}</b> پروژه"
    await say(status, txt)


@require_token
async def cmd_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    api = get_api(ctx)
    try:
        projects = await run_blocking(api.list_projects)
    except RailwayError as e:
        await update.message.reply_text(f"❌ {e}", parse_mode="HTML")
        return
    if not projects:
        await update.message.reply_text("📭 پروژه‌ای نیست.", parse_mode="HTML")
        return
    kb = [[InlineKeyboardButton(p["name"], callback_data=f"del:{p['id']}")]
          for p in sorted(projects, key=lambda x: x.get("createdAt", ""), reverse=True)[:10]]
    kb.append([InlineKeyboardButton("❌ انصراف", callback_data="cancel")])
    await update.message.reply_text(
        "🗑 کدوم پروژه؟",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")


# ── callback router ────────────────────────────────────────────
async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    route = {
        "go_help": lambda: q.edit_message_text(ui.HELP_TEXT, parse_mode="HTML"),
        "cancel": lambda: q.edit_message_text(ui.CANCELLED, parse_mode="HTML"),
        "go_delete": lambda: cmd_delete(update, ctx),
    }

    async def hint(text):
        await q.edit_message_text(
            f"{ui.header('راهنمای سریع 💡')}\n\n{text}", parse_mode="HTML")

    if data == "go_deploy":
        if not active_token(ctx):
            await q.edit_message_text(ui.NOT_CONNECTED, parse_mode="HTML")
        else:
            await hint("برای شروع دپلوی دستور رو بزن:\n🚀 <code>/deploy</code>")
        return
    if data == "sec_account":
        await show_accounts(q, ctx, update.effective_user.id)
        return
    if data == "sec_deploy":
        await show_deploy_section(update, ctx, q)
        return
    if data == "sec_inbound":
        await show_inbound_section(update, ctx, q)
        return

    # section-specific callbacks
    if data.startswith("acc") or data.startswith("noop"):
        await handle_account_callback(update, ctx, q, data)
        return
    if data.startswith("depdom") or data == "dep_domain_hint":
        await handle_deploy_callback(update, ctx, q, data)
        return
    if data.startswith("inb"):
        await handle_inbound_callback(update, ctx, q, data)
        return

    if data == "go_link":
        await hint("برای ساخت لینک اتصال بزن:\n🔗 <code>/link</code>")
        return
    if data == "go_tcp":
        await show_tcp_menu(q)
        return
    if data == "go_status":
        await hint("برای دیدن وضعیت بزن:\n📊 <code>/status</code>")
        return
    if data.startswith("del:"):
        api = get_api(ctx)
        pid = data.split(":", 1)[1]
        try:
            ok = await run_blocking(api.delete_project, pid)
            icon = "✅" if ok else "❌"
            title = "حذف موفق ✅" if ok else "حذف ناموفق ⛔️"
            msg = f"{ui.header(title)}\n\n{icon} پروژه حذف شد."
        except RailwayError as e:
            msg = f"{ui.header('خطا ⛔️')}\n\n❌ {e}"
        await q.edit_message_text(msg, parse_mode="HTML")
        return

    handler = route.get(data)
    if handler:
        await handler()
        return

    # ── TCP Proxy callbacks ──
    await handle_tcp_callback(update, ctx, q, data)


# ════════════════════════════════════════════════════════════════
#  SECTION: ACCOUNTS
# ════════════════════════════════════════════════════════════════
async def show_accounts(q, ctx, uid):
    accounts = ACCOUNTS.list(uid)
    active = ACCOUNTS.active_label(uid)
    await q.edit_message_text(ui.accounts_text(accounts, active),
                              reply_markup=ui.accounts_keyboard(accounts),
                              parse_mode="HTML")


async def handle_account_callback(update, ctx, q, data: str):
    uid = update.effective_user.id

    if data == "accadd_hint":
        st = ctx.user_data.setdefault(uid, {})
        st["await_acc_label"] = True
        await q.edit_message_text(
            ui.ADD_ACCOUNT_HINT.replace("{hdr}", ui.header("افزودن اکانت ➕")),
            parse_mode="HTML")
        return

    if data.startswith("accsw:"):
        label = data.split(":", 1)[1]
        ok = ACCOUNTS.set_active(uid, label)
        refresh_active(ctx, uid)
        accounts = ACCOUNTS.list(uid)
        body = "✅ سوییچ شد!" if ok else "❌ پیدا نشد"
        await q.edit_message_text(
            f"{ui.header('سوییچ اکانت 🔄')}\n\n{body}\n\n" ,
            reply_markup=ui.accounts_keyboard(accounts), parse_mode="HTML")
        return

    if data.startswith("accdel:"):
        label = data.split(":", 1)[1]
        ACCOUNTS.remove(uid, label)
        refresh_active(ctx, uid)
        accounts = ACCOUNTS.list(uid)
        active = ACCOUNTS.active_label(uid)
        await q.edit_message_text(
            ui.accounts_text(accounts, active) + "\n\n🗑 حذف شد.",
            reply_markup=ui.accounts_keyboard(accounts), parse_mode="HTML")
        return


# ════════════════════════════════════════════════════════════════
#  SECTION: DEPLOY
# ════════════════════════════════════════════════════════════════
async def show_deploy_section(update, ctx, q):
    await q.edit_message_text(ui.DEPLOY_WELCOME,
                              reply_markup=ui.deploy_menu(), parse_mode="HTML")


async def start_domain_set(update, ctx, q):
    uid = update.effective_user.id
    deployed = ctx.user_data.get("deployed_panels") or []
    rows = [[InlineKeyboardButton(p["name"], callback_data=f"depdom:{p['service_id']}:{p['name']}")]
            for p in deployed if p.get("url")]
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="sec_deploy")])
    await q.edit_message_text(
        f"{ui.header('ست کردن دامنه 🌐')}\n\nکدوم پنل؟",
        reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")


async def handle_deploy_callback(update, ctx, q, data: str):
    if data == "dep_domain_hint":
        # first ask which panel, then the domain text
        uid = update.effective_user.id
        deployed = ctx.user_data.get("deployed_panels") or []
        if not deployed:
            await q.edit_message_text(
                ui.LINKS_EMPTY + "\n\nاول یه دپلوی انجام بده.", parse_mode="HTML")
            return
        await start_domain_set(update, ctx, q)
        return

    if data.startswith("depdom:"):
        _, sid, name = data.split(":", 2)
        ctx.user_data.setdefault(update.effective_user.id, {})["await_domain_for"] = {
            "service_id": sid, "name": name}
        await q.edit_message_text(
            ui.DOMAIN_SET_HINT.replace("{hdr}", ui.header(f'دامنه برای {name} 🌐')),
            parse_mode="HTML")
        return


async def apply_custom_domain(update, ctx, service_id: str, name: str, domain_input: str):
    """Create/replace a custom domain on the given service."""
    token = active_token(ctx)
    api = RailwayAPI(token)
    status = await update.message.reply_text(
        ui.header(f"🌐 ست کردن دامنه روی {name}..."), parse_mode="HTML")

    try:
        env_id = ""
        proj_id = ctx.user_data.get("tcp_project_id") or ""
        if proj_id:
            envs = await run_blocking(api.get_environments, proj_id)
            env_id = envs[0]["id"] if envs else ""
        domain = domain_input.strip().replace("https://", "").replace("http://", "").rstrip("/")
        d = await run_blocking(api.create_domain, service_id, env_id, 3000) \
            if not domain else {"domain": domain}
        await say(status,
                  f"{ui.header('دامنه ست شد ✅')}\n\n"
                  f"📡 پنل: <b>{name}</b>\n"
                  f"🌐 دامنه: <code>{d.get('domain', domain)}</code>\n\n"
                  "⚠️ یادت باشه DNS رو به Railway اشاره بدی (CNAME).")
    except RailwayError as e:
        await say(status, f"{ui.header('خطا ⛔️')}\n\n❌ {e}")


# ════════════════════════════════════════════════════════════════
#  SECTION: INBOUNDS
# ════════════════════════════════════════════════════════════════
def _pick_panel_keyboard(deployed, prefix: str):
    rows = [[InlineKeyboardButton(p["name"], callback_data=f"{prefix}:{p['service_id']}:{p['name']}:{p.get('url','')}")]
            for p in deployed if p.get("url")]
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="sec_inbound")])
    return InlineKeyboardMarkup(rows)


async def show_inbound_section(update, ctx, q):
    await q.edit_message_text(ui.INBOUND_WELCOME,
                              reply_markup=ui.inbound_menu(), parse_mode="HTML")


async def get_panel_client(p):
    client = PanelClient(p["url"], config.XUI_USERNAME, config.XUI_PASSWORD)
    if not client.login():
        raise XUIError(f"ورود به پنل {p['name']} شکست خورد — URL یا پسورد چک کن")
    return client


async def handle_inbound_callback(update, ctx, q, data: str):
    uid = update.effective_user.id
    deployed = [p for p in (ctx.user_data.get("deployed_panels") or []) if p.get("url")]

    if data in ("inb_create_pick", "inb_list_pick", "inb_delete_pick"):
        if not deployed:
            await q.edit_message_text(ui.LINKS_EMPTY, parse_mode="HTML")
            return
        prefix = data.split("_")[0]  # inb
        action = data.split("_", 1)[1].split("_")[0]  # create / list / delete
        title = {"create": "انتخاب پنل برای ساخت اینباند ➕",
                 "list": "لیست اینباندهای کدوم پنل؟ 📋",
                 "delete": "حذف اینباند از کدوم پنل؟ 🗍"}[action]
        await q.edit_message_text(
            f"{ui.header(title)}",
            reply_markup=_pick_panel_keyboard(deployed, f"inbdo_{action}"),
            parse_mode="HTML")
        return

    if data.startswith("inbdo_create:"):
        _, sid, name, url = data.split(":", 3)
        status = await q.message.reply_text(
            ui.header(f"📥 ساخت اینباند روی {name}..."), parse_mode="HTML")
        p = {"name": name, "service_id": sid, "url": url}

        def _work():
            import uuid as _u
            client = PanelClient(url, config.XUI_USERNAME, config.XUI_PASSWORD)
            if not client.login():
                raise XUIError("ورود به پنل ناموفق")
            u = str(_u.uuid4())
            res = client.create_vless_tls_inbound(
                uuid=u, email=f"{name.lower()}-user",
                domain=url.replace("https://", "").rstrip("/"),
                port=config.INBOUND_PORT, path=config.INBOUND_PATH)
            if not res.get("success"):
                raise XUIError(res.get("msg", "unknown"))
            link = build_vless_link(url, u, config.INBOUND_PATH, f"Hermes-{name}")
            return link

        try:
            link = await run_blocking(_work)
            await say(status,
                      f"{ui.header('اینباند ساخته شد ✅')}\n\n"
                      f"📡 <b>{name}</b> · 🔌 {config.INBOUND_PORT} · 🛣 {config.INBOUND_PATH}\n\n"
                      f"<code>{link}</code>\n\n"
                      "📲 کپی کن → v2rayNG → Import")
        except (XUIError, Exception) as e:
            await say(status, f"{ui.header('خطا ⛔️')}\n\n❌ {e}")
        return

    if data.startswith("inbdo_list:") or data.startswith("inbdo_delete:"):
        _, action2, sid, name, url = data.split(":", 4)
        status = await q.message.reply_text(ui.header("در حال خواندن... ⏳"), parse_mode="HTML")

        def _work():
            client = PanelClient(url, config.XUI_USERNAME, config.XUI_PASSWORD)
            if not client.login():
                raise XUIError("ورود ناموفق")
            return client.list_inbounds()

        try:
            inbounds = await run_blocking(_work)
            lines = []
            for ib in inbounds[:15]:
                port = ib.get("port", "?")
                remark = ib.get("remark", "?")
                iid = ib.get("id")
                icon = "🗑" if action2 == "delete" else "📥"
                cb = f"inbdel:{sid}:{name}:{url}:{iid}" if action2 == "delete" else "noop"
                lines.append((f'{icon} <b>{remark}</b> :{port}', cb))
            if not lines:
                await say(status, ui.header("اینباندی نیست 📭"))
                return
            from telegram import InlineKeyboardButton as IB, InlineKeyboardMarkup as IKM
            rows = [[IB(txt, callback_data=cb)] for txt, cb in lines]
            rows.append([IB("🔙 بازگشت", callback_data="sec_inbound")])
            await q.message.edit_text(
                f"{ui.header(f'اینباندهای {name} 📋')}\n\n"
                + ("برای حذف رویش بزن:" if action2 == "delete" else ""),
                reply_markup=IKM(rows), parse_mode="HTML")
        except (XUIError, Exception) as e:
            await say(status, f"{ui.header('خطا ⛔️')}\n\n❌ {e}")
        return

    if data.startswith("inbdel:"):
        _, sid, name, url, iid = data.split(":", 4)

        def _work():
            client = PanelClient(url, config.XUI_USERNAME, config.XUI_PASSWORD)
            if not client.login():
                raise XUIError("ورود ناموفق")
            r = client.delete_inbound(int(iid))
            if not r.get("success"):
                raise XUIError(r.get("msg", "حذف ناموفق"))
            return True

        try:
            await run_blocking(_work)
            await q.edit_message_text(f"{ui.header('حذف شد ✅')}\n\n🗑 اینباند <code>{iid}</code>", parse_mode="HTML")
        except Exception as e:
            await q.edit_message_text(f"{ui.header('خطا ⛔️')}\n\n❌ {e}", parse_mode="HTML")
        return



# ════════════════════════════════════════════════════════════════
#  TCP PROXY FEATURE
# ════════════════════════════════════════════════════════════════
async def tcp_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Entry: /tcp command"""
    await update.message.reply_text(ui.TCP_WELCOME, reply_markup=ui.tcp_menu(),
                                    parse_mode="HTML")


async def cancel_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = ctx.user_data.get(uid) or {}
    cleared = (u.pop("await_domain", None) or u.pop("await_acc_label", None)
               or u.pop("pending_acc_label", None) or u.pop("await_domain_for", None))
    if cleared:
        await update.message.reply_text(f"{ui.header('لغو شد ❌')}", parse_mode="HTML")
    else:
        stop = ctx.bot_data.get(f"tcpstop_{uid}")
        if stop:
            stop["kill"] = True
            await update.message.reply_text("🛑 در حال توقف چرخش...", parse_mode="HTML")
        else:
            await update.message.reply_text("چیزی برای لغو نبود.", parse_mode="HTML")


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle plain text input: suggested domains, account labels/tokens, custom domains."""
    uid = update.effective_user.id
    u = ctx.user_data.get(uid) or {}

    # ── account add: step 1 label, step 2 token ──
    if u.get("await_acc_label"):
        u.pop("await_acc_label")
        u["pending_acc_label"] = update.message.text.strip()[:32]
        await update.message.reply_text(
            ui.header(f"اکانت <code>{u['pending_acc_label']}</code> ➕") +
            "\n\n🔑 حالا <b>توکن Railway</b> این اکانت رو بفرست:\n"
            "(dashboard.railway.com → Tokens)\n\nلغو: /cancel",
            parse_mode="HTML")
        return

    if "pending_acc_label" in u:
        label = u.pop("pending_acc_label")
        token = update.message.text.strip()
        status = await update.message.reply_text(ui.header("در حال بررسی... 🔍"), parse_mode="HTML")
        try:
            ws_id, email = await run_blocking(RailwayAPI(token).whoami)
            ok = ACCOUNTS.add(uid, label, token, email)
            if not ok:
                await say(status, f"{ui.header('تکراری ⚠️')}\n\nاسم <code>{label}</code> قبلاً هست.")
                return
            ACCOUNTS.set_active(uid, label)
            refresh_active(ctx, uid)
            accounts = ACCOUNTS.list(uid)
            await say(status,
                      f"{ui.header('اکانت اضافه شد ✅')}\n\n👤 {label} · <code>{email}</code>",
                      keyboard=ui.accounts_keyboard(accounts))
        except RailwayError as e:
            await say(status, ui.TOKEN_INVALID + f"\n\n<code>{e}</code>")
        return

    # ── custom domain set ──
    if "await_domain_for" in u:
        info = u.pop("await_domain_for")
        await apply_custom_domain(update, ctx, info["service_id"], info["name"],
                                  update.message.text)
        return

    if u.pop("await_domain", None):
        d = update.message.text.strip()
        added = TCP.add_domain(d)
        domains = TCP.get_domains()
        msg = f"✅ <code>{d}</code> اضافه شد!" if added else f"⚠️ <code>{d}</code> قبلاً هست."
        await update.message.reply_text(
            f"{ui.header('لیست دامنه‌ها 📋')}\n\n{msg}\n{ui.SEP}\n"
            + "\n".join(f"  {i}. <code>{x}</code>" for i, x in enumerate(domains, 1)),
            reply_markup=ui.domains_keyboard(domains), parse_mode="HTML")


async def show_tcp_menu(q):
    await q.edit_message_text(ui.TCP_WELCOME, reply_markup=ui.tcp_menu(),
                              parse_mode="HTML")


async def run_tcp_rotation_for_panel(update, ctx, status_msg, p, env_id, uid):
    """Rotate `count` proxies for one panel; returns list of results."""
    token = active_token(ctx)
    s = TCP.get_user(uid)
    count = int(s.get("count", 2))
    port = int(s.get("port", 443))
    mode = s.get("mode", "good")
    targets = TCP.target_set() if mode == "good" else None
    api = TCPProxyAPI(token)

    stop = {"kill": False}
    ctx.bot_data[f"tcpstop_{uid}"] = stop
    results = []
    cancel_kbd = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🛑 توقف", callback_data="tcp_stop")]])

    for i in range(1, count + 1):
        lines = []

        def on_progress(m):
            lines.append(m)

        await say(status_msg,
                  ui.header(f'🛰 چرخش {p["name"]} — پروکسی {i}/{count}')
                  + f"\n\n<pre>{html_escape(chr(10).join(lines[-6:]) or 'شروع...')}</pre>"
                  + f"\n\n🎯 حالت: {'🔀 تأیید' if mode=='good' else '🎲 رندم'} · 🔌 پورت {port}",
                  keyboard=cancel_kbd)

        def work():
            return api.rotate(p["service_id"], env_id, port,
                              targets=targets, max_tries=30, cooldown=8,
                              on_progress=on_progress,
                              cancel_check=lambda: stop["kill"])

        try:
            res = await asyncio.wait_for(run_blocking(work), timeout=900)
        except Exception as e:
            res = None
            lines.append(f"خطا: {e}")

        if res:
            dom, prt = res
            results.append((p["name"], f"{dom}:{prt}"))
            await say(status_msg,
                      ui.header(f"✅ {p['name']} — {i}/{count}")
                      + f"\n\n🎯 <code>{dom}:{prt}</code>")
        else:
            if stop.get("kill"):
                break
            results.append((p["name"], "❌ به هدف نرسید"))

    ctx.bot_data.pop(f"tcpstop_{uid}", None)
    return results


def html_escape(t: str) -> str:
    import html as _h
    return _h.escape(str(t))


async def start_tcp_flow(update, ctx, q):
    """Pick a deployed panel → rotate its TCP proxies."""
    uid = update.effective_user.id
    deployed = ctx.user_data.get("deployed_panels") or []
    if not deployed:
        # try to rediscover from the latest project
        api = get_api(ctx)
        if not api:
            await q.edit_message_text(ui.NOT_CONNECTED, parse_mode="HTML")
            return
        try:
            projects = sorted(await run_blocking(api.list_projects),
                              key=lambda x: x.get("createdAt", ""), reverse=True)
            if not projects:
                await q.edit_message_text(ui.LINKS_EMPTY, parse_mode="HTML")
                return
            proj = projects[0]
            env_id = await run_blocking(TCPProxyAPI(active_token(ctx)).find_env, proj["id"])
            services = await run_blocking(TCPProxyAPI(active_token(ctx)).list_services, proj["id"])
            ctx.user_data["tcp_project_id"] = proj["id"]
            ctx.user_data["tcp_env_id"] = env_id
            deployed = [{"name": s["name"], "service_id": s["id"], "url": ""}
                        for s in services]
        except Exception as e:
            await q.edit_message_text(f"{ui.header('خطا ⛔️')}\n\n❌ {e}", parse_mode="HTML")
            return

    rows = [[InlineKeyboardButton(p["name"], callback_data=f"tcpsvc:{p['service_id']}:{p['name']}")]
            for p in deployed]
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="tcp_back")])
    await q.edit_message_text(
        f"{ui.header('انتخاب پنل 🛰')}\n\nکدوم پنل؟ (چندتایی میشه انتخاب کرد — هر بار یکی)",
        reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")


async def handle_tcp_callback(update, ctx, q, data: str):
    uid = update.effective_user.id

    if data == "tcp_back":
        await show_tcp_menu(q)
        return

    if data == "tcp_start":
        await start_tcp_flow(update, ctx, q)
        return

    if data == "tcp_settings":
        s = TCP.get_user(uid)
        await q.edit_message_text(ui.settings_text(s),
                                  reply_markup=ui.settings_keyboard(s),
                                  parse_mode="HTML")
        return

    if data.startswith("tcpset_"):
        kind, _, val = data.partition(":")
        field = {"tcpset_count": "count", "tcpset_port": "port",
                 "tcpset_mode": "mode"}[kind]
        TCP.set_user(uid, **{field: int(val) if field != "mode" else val})
        s = TCP.get_user(uid)
        await q.edit_message_text(ui.settings_text(s),
                                  reply_markup=ui.settings_keyboard(s),
                                  parse_mode="HTML")
        return

    if data == "tcp_domains":
        domains = TCP.get_domains()
        await q.edit_message_text(ui.domains_text(domains),
                                  reply_markup=ui.domains_keyboard(domains),
                                  parse_mode="HTML")
        return

    if data.startswith("tcpdel:"):
        d = data.split(":", 1)[1]
        TCP.remove_domain(d)
        domains = TCP.get_domains()
        await q.edit_message_text(ui.domains_text(domains),
                                  reply_markup=ui.domains_keyboard(domains),
                                  parse_mode="HTML")
        return

    if data in ("tcpreset_all", "tcpreset"):
        if data == "tcpreset_all":
            TCP.reset_domains()
        domains = TCP.get_domains()
        await q.edit_message_text(ui.domains_text(domains),
                                  reply_markup=ui.domains_keyboard(domains),
                                  parse_mode="HTML")
        return

    if data == "tcpadd_hint":
        ctx.user_data.setdefault(uid, {})["await_domain"] = True
        await q.edit_message_text(
            f"{ui.header('افزودن دامنه ➕')}\n\n"
            "اسم دامنه رو بفرست (فقط اسم کافیه):\n\n"
            "<code>monorail</code>\nیا کامل:\n<code>monorail.proxy.rlwy.net</code>\n\n"
            "برای لغو: /cancel",
            parse_mode="HTML")
        return

    if data == "tcp_stop":
        stop = ctx.bot_data.get(f"tcpstop_{uid}")
        if stop:
            stop["kill"] = True
            await q.answer("در حال توقف... 🛑")
        else:
            await q.answer("چرخشی در جریان نیست", show_alert=True)
        return

    if data.startswith("tcpsvc:"):
        _, sid, name = data.split(":", 2)
        env_id = ctx.user_data.get("tcp_env_id") or ""
        if not env_id:
            api = get_api(ctx)
            pid = ctx.user_data.get("tcp_project_id")
            env_id = await run_blocking(api and TCPProxyAPI(active_token(ctx)).find_env, pid or "")
        panel = {"name": name, "service_id": sid}
        status = await q.message.reply_text(
            f"{ui.header(f'شروع چرخش {name} 🛰')}", parse_mode="HTML")
        results = await run_tcp_rotation_for_panel(update, ctx, status, panel,
                                                   env_id, uid)
        summary = "\n".join(f"{'✅' if '❌' not in r else '❌'} <b>{n}</b> → <code>{v}</code>"
                            for n, v in results)
        await say(status,
                  f"{ui.header('نتیجه چرخش TCP 🛰')}\n{ui.SEP}\n{summary}\n\n{ui.BOT}\n"
                  "برای پنل دیگه: 🛰 /tcp")


# ── main ───────────────────────────────────────────────────────
def main():
    if not config.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN env var is required!")
    app = ApplicationBuilder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("tcp", tcp_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(CommandHandler("deploy", cmd_deploy))
    app.add_handler(CommandHandler("link", cmd_link))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("delete", cmd_delete))
    app.add_handler(CallbackQueryHandler(on_callback))

    log.info("Hermes X-UI bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
