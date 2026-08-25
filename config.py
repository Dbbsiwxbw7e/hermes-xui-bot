"""
Central configuration — everything env-first with sane defaults.
"""
import os

# ── Bot ────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ── Railway deployment ─────────────────────────────────────────
DOCKER_IMAGE = os.getenv("DOCKER_IMAGE", "ghcr.io/djsjsnsjcjx/3xui_amir:latest")
PROJECT_NAME = os.getenv("PROJECT_NAME", "hermes-xui")

# Panels: "NAME:REGION" pairs, comma separated.
#   e.g. PANELS="NL:NL,US:US-VA,SG:SG,DE:DE"
def _parse_panels(raw: str):
    panels = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        name, _, region = item.partition(":")
        panels.append({"name": name.strip(), "region": region.strip() or name.strip()})
    return panels

PANELS = _parse_panels(os.getenv("PANELS", "NL:NL,US_V:US-VA,SG:SG,NL_MT:NL-MT"))
MAIN_PANEL = os.getenv("MAIN_PANEL", PANELS[0]["name"] if PANELS else "NL")

# ── Panel default credentials (user should change immediately) ─
XUI_USERNAME = os.getenv("XUI_USERNAME", "admin")
XUI_PASSWORD = os.getenv("XUI_PASSWORD", "admin")

# ── Inbound (VLESS + WS + TLS via Railway edge) ────────────────
INBOUND_PORT = int(os.getenv("INBOUND_PORT", "8080"))
INBOUND_PATH = os.getenv("INBOUND_PATH", "/cdn")
PANEL_BASE_PATH = "/managepanel/"

# ── Timing ─────────────────────────────────────────────────────
DEPLOY_POLL_INTERVAL = 10   # seconds between deployment status checks
DEPLOY_POLL_TIMEOUT = 300   # max wait for a deployment to succeed
PANEL_READY_TIMEOUT = 90    # max wait for panel HTTP to come up
