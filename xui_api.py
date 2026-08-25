"""
3x-ui panel REST client + VLESS link builder.
"""
import json
import re
import time
import urllib.parse

import requests


class XUIError(Exception):
    pass


class PanelClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.csrf = ""
        self.logged_in = False

    # ── internals ──────────────────────────────────────────────
    def _fetch_csrf(self) -> None:
        try:
            r = self.session.get(f"{self.base}/managepanel/", timeout=15)
            m = re.search(r'csrf-token.*?content="([^"]+)"', r.text)
            if m:
                self.csrf = m.group(1)
        except requests.RequestException:
            pass

    def _hdrs(self) -> dict:
        return {"X-CSRF-Token": self.csrf}

    def _req(self, method: str, path: str, payload: dict | None = None) -> dict:
        url = f"{self.base}/managepanel{path}"
        try:
            if method == "GET":
                r = self.session.get(url, headers=self._hdrs(), timeout=20)
            else:
                r = self.session.post(url, json=payload or {}, headers=self._hdrs(), timeout=30)
            return r.json()
        except (requests.RequestException, ValueError) as e:
            raise XUIError(f"{path}: {e}") from e

    # ── auth ───────────────────────────────────────────────────
    def login(self) -> bool:
        self._fetch_csrf()
        d = self._req("POST", "/login", {"username": self.username, "password": self.password})
        if d.get("success"):
            self.logged_in = True
            self._fetch_csrf()
            return True
        return False

    # ── inbounds ───────────────────────────────────────────────
    def create_vless_tls_inbound(
        self,
        uuid: str,
        email: str,
        domain: str,
        port: int,
        path: str,
    ) -> dict:
        """VLESS + WS inbound; TLS is terminated by the Railway edge."""
        stream = {
            "network": "ws",
            "security": "tls",
            "tlsSettings": {
                "serverName": domain,
                "alpn": ["http/1.1"],
                "certificates": [],
                # Empty certificate list + serverName keeps the panel UI
                # consistent (shows tls) while Railway edge does real TLS.
                "allowInsecure": False,
            },
            "wsSettings": {
                "path": path,
                "headers": {"Host": domain},
            },
        }
        data = {
            "up": 0, "down": 0, "total": 0,
            "remark": f"Hermes-{email}",
            "enable": True,
            "expiryTime": 0,
            "listen": "",
            "port": port,
            "protocol": "vless",
            "settings": json.dumps({
                "clients": [{
                    "id": uuid,
                    "flow": "",
                    "email": email,
                    "limitIp": 0,
                    "totalGB": 0,
                    "expiredTime": 0,
                    "enable": True,
                    "tgId": 0,
                    "subId": "",
                }],
                "decryption": "none",
                "fallbacks": [],
            }),
            "streamSettings": json.dumps(stream),
            "sniffing": json.dumps({"enabled": False, "destOverride": [], "routeOnly": False}),
            "tag": f"vless-ws-{email}",
            "listenning": "",
        }
        return self._req("POST", "/panel/api/inbounds/add", data)

    def list_inbounds(self) -> list[dict]:
        d = self._req("GET", "/panel/api/inbounds/list")
        return d.get("obj", []) or []

    def delete_inbound(self, inbound_id: int) -> dict:
        return self._req("POST", f"/panel/api/inbounds/del/{inbound_id}")

    # ── node management ────────────────────────────────────────
    def get_uuid(self) -> str:
        d = self._req("GET", "/panel/api/server/getNewUUID")
        return (d.get("obj") or {}).get("uuid", "")

    def create_api_token(self, name: str = "node-token") -> str:
        tokens = self._req("GET", "/panel/api/setting/apiTokens")
        for t in (tokens.get("obj") or []):
            try:
                self._req("POST", f"/panel/api/setting/apiTokens/delete/{t['id']}")
            except XUIError:
                pass
        d = self._req("POST", "/panel/api/setting/apiTokens/create", {"name": name})
        return (d.get("obj") or {}).get("token", "")

    def add_node(self, node_name: str, node_url: str, node_uuid: str,
                 node_token: str) -> dict:
        host = node_url.replace("https://", "").replace("http://", "").rstrip("/")
        data = {
            "name": node_name,
            "address": host,
            "port": 443,
            "scheme": "https",
            "serialNumber": node_uuid,
            "apiToken": node_token,
            "trafficLimit": 0,
            "weight": 100,
            "remark": f"{node_name} Node",
            "checkInterval": 60,
            "checkType": "http",
            "notify": True,
            "alertThreshold": 0,
            "enable": True,
            "allowPrivateAddress": False,
            "basePath": "/managepanel/",
            "inboundSyncMode": "all",
            "inboundTags": [],
            "outboundTag": "",
            "pinnedCertSha256": "",
            "tlsVerifyMode": "skip",
        }
        return self._req("POST", "/panel/api/nodes/add", data)


# ── helpers ────────────────────────────────────────────────────
def build_vless_link(domain: str, uuid: str, path: str = "/cdn", name: str = "config") -> str:
    host = domain.replace("https://", "").replace("http://", "").rstrip("/")
    q = urllib.parse.quote(path, safe="")
    n = urllib.parse.quote(name)
    return (
        f"vless://{uuid}@{host}:443"
        f"?encryption=none&security=tls&sni={host}&fp=chrome"
        f"&type=ws&host={host}&path={q}#{n}"
    )


def wait_until_ready(url: str, timeout: int, interval: int = 5) -> bool:
    deadline = time.time() + timeout
    probe = url.rstrip("/") + "/managepanel/"
    while time.time() < deadline:
        try:
            r = requests.get(probe, timeout=10, allow_redirects=True)
            if r.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(interval)
    return False
