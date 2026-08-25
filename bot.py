"""
Hermes X-UI Bot — entry point and handlers.

Flow:
  /connect → store Railway token in RAM (user_data)
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
    ContextTypes,
)

import config
import ui
from railway_api import RailwayAPI, RailwayError
from xui_api import PanelClient, XUIError, build_vless_link, wait_until_ready

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
    token = ctx.user_data.get("railway_token")
    return RailwayAPI(token) if token else None


def require_token(func):
    """Decorator: reply with NOT_CONNECTED if no railway token stored."""
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not ctx.user_data.get("railway_token"):
            target = update.callback_query.message if update.callback_query else update.message
            await target.reply_text(ui.NOT_CONNECTED, parse_mode="HTML")
            return
        return await func(update, ctx)
    return wrapper


def run_blocking(fn, *args):
    return asyncio.to_thread(fn, *args)


# ── commands ───────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(ui.WELCOME, reply_markup=ui.MENU, parse_mode="HTML")


async def cmd_connect(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text(
            f"🔑 <b>اتصال به Railway</b>\n{ui.DIV}\n"
            "<code>/connect TOKEN</code>\n\n"
            "توکن از: dashboard.railway.com → Account → Tokens",
            parse_mode="HTML",
        )
        return

    token = ctx.args[0]
    api = RailwayAPI(token)
    status = await update.message.reply_text("🔍 در حال بررسی توکن...")
    try:
        ws_id, email = await run_blocking(api.whoami)
        ctx.user_data["railway_token"] = token
        ctx.user_data["workspace_id"] = ws_id
        await say(status, f"✅ متصل شدی!\n👤 <code>{email}</code>\n\nحالا بزن 🚀 /deploy")
    except RailwayError as e:
        await say(status, f"❌ توکن قبول نشد:\n<code>{e}</code>")


@require_token
async def cmd_deploy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    api = get_api(ctx)
    total_steps = len(config.PANELS) + 2
    status = await update.message.reply_text(
        ui.deploy_step(0, total_steps, "🚀 شروع دپلوی..."), parse_mode="HTML")

    # 1) project
    project_id = environment_id = ""
    try:
        proj = await run_blocking(api.create_project, config.PROJECT_NAME,
                                  ctx.user_data["workspace_id"])
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

    # 3) poll deployments until SUCCESS (real verification!)
    deadline = asyncio.get_event_loop().time() + config.DEPLOY_POLL_TIMEOUT
    while panels and asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(config.DEPLOY_POLL_INTERVAL)
        pending = []
        for p in panels:
            d = await run_blocking(api.latest_deployment, p["service_id"])
            st = (d or {}).get("status", "")
            if st == "SUCCESS":
                p["ready"] = True
                if not p["url"] and d.get("staticUrl"):
                    p["url"] = f"https://{d['staticUrl']}"
            elif st in ("FAILED", "CRASHED", "REMOVED"):
                p["failed"] = True
            else:
                pending.append(p)

        done = sum(1 for p in panels if p.get("ready") or p.get("failed"))
        await say(status, ui.deploy_step(
            2, total_steps, f"📡 در انتظار SUCCESS... ({done}/{len(panels)})",
            ui.panel_summary(panels)))
        panels = pending

    # final report — fetch fresh state of everything we created
    report = f"📊 <b>نتیجه دپلوی</b>\n{ui.DIV}\n"
    ok = 0
    for p in list({p['name']: p for p in panels}.values()) or []:
        pass  # panels now only holds still-pending ones; re-check all
    all_panels = []
    for p_cfg in config.PANELS:
        match = [p for p in ctx.user_data.setdefault("deployed_panels", [])
                 if p["name"] == p_cfg["name"]]
        if match:
            all_panels.append(match[0])
    ctx.user_data["deployed_panels"] = all_panels

    # merge: re-query latest deployment for each service once more
    for p in all_panels:
        d = await run_blocking(api.latest_deployment, p["service_id"])
        st = (d or {}).get("status")
        icon = {"SUCCESS": "✅", "FAILED": "❌", "CRASHED": "💥"}.get(st, "⏳")
        if st == "SUCCESS":
            ok += 1
            if not p["url"] and d.get("staticUrl"):
                p["url"] = f"https://{d['staticUrl']}"
        report += f"\n{icon} <b>{p['name']}</b>"
        if p.get("url"):
            report += f"\n     🌐 {p['url']}/managepanel/"

    report += (f"\n\n{ui.DIV}\n"
               f"{'🎉 همه آماده‌ان!' if ok == len(all_panels) else '⚠️ بعضی پنل‌ها هنوز آماده نیستن'}\n"
               "قدم بعدی: 🔗 /link")
    await say(status, report)


@require_token
async def cmd_link(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    api = get_api(ctx)
    deployed = ctx.user_data.get("deployed_panels", [])
    if not deployed:
        await update.message.reply_text(
            f"📭 پنلی توی این جلسه دپلوی نشده.\n{ui.DIV}\nاول بزن: /deploy",
            parse_mode="HTML")
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
        await say(status, "📭 پروژه‌ای وجود نداره.")
        return

    txt = f"📊 <b>پروژه‌های Railway</b>\n{ui.DIV}\n"
    for p in sorted(projects, key=lambda x: x.get("createdAt", ""), reverse=True)[:10]:
        txt += f"\n📦 <b>{p['name']}</b>\n     <code>{p['id']}</code>"
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
        "cancel": lambda: q.edit_message_text("❌ لغو شد."),
    }

    if data == "go_deploy":
        if not ctx.user_data.get("railway_token"):
            await q.edit_message_text(ui.NOT_CONNECTED, parse_mode="HTML")
        else:
            await q.edit_message_text("برای شروع دستور رو بزن: 🚀 /deploy",
                                      parse_mode="HTML")
        return
    if data == "go_link":
        await q.edit_message_text("برای ساخت لینک بزن: 🔗 /link", parse_mode="HTML")
        return
    if data == "go_status":
        await q.edit_message_text("برای وضعیت بزن: 📊 /status", parse_mode="HTML")
        return
    if data.startswith("del:"):
        api = get_api(ctx)
        pid = data.split(":", 1)[1]
        try:
            ok = await run_blocking(api.delete_project, pid)
            msg = "✅ پروژه حذف شد!" if ok else "❌ حذف ناموفق"
        except RailwayError as e:
            msg = f"❌ {e}"
        await q.edit_message_text(msg, parse_mode="HTML")
        return

    handler = route.get(data)
    if handler:
        await handler()


# ── main ───────────────────────────────────────────────────────
def main():
    if not config.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN env var is required!")
    app = ApplicationBuilder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("connect", cmd_connect))
    app.add_handler(CommandHandler("deploy", cmd_deploy))
    app.add_handler(CommandHandler("link", cmd_link))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("delete", cmd_delete))
    app.add_handler(CallbackQueryHandler(on_callback))

    log.info("Hermes X-UI bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
