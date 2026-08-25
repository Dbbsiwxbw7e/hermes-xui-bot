"""
TCP Proxy engine — list/create/delete/rotate proxies on Railway services.
Adapted from the TCP rotator concept, integrated with Hermes X-UI style.
"""
import json
import socket
import time
import urllib.request

RAILWAY_URL = "https://api.railway.app/graphql/v2"

DEFAULT_GOOD_DOMAINS = (
    "monorail,nozomi,turntable,trolley,reseau,autorack,metro,hopper,"
    "kodama,interchange,switchyard,junction"
)


def normalize_domains(raw: str) -> set:
    out = set()
    for d in (raw or "").split(","):
        d = d.strip().rstrip(".")
        if not d:
            continue
        if not d.endswith(".proxy.rlwy.net"):
            d = d + ".proxy.rlwy.net"
        out.add(d)
    return out


class TCPProxyAPI:
    """GraphQL client scoped to TCP proxy operations."""

    def __init__(self, token: str):
        self.token = token

    # ── low-level ──────────────────────────────────────────────
    def _gql(self, query: str, variables: dict | None = None) -> dict:
        body = json.dumps({"query": query, "variables": variables or {}}).encode()
        req = urllib.request.Request(RAILWAY_URL, data=body, headers={
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json",
            "User-Agent": "railway-cli/5.30.4",
            "Accept": "*/*",
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read().decode())
        if "data" not in resp:
            raise RuntimeError("Railway API error: " + json.dumps(resp)[:300])
        return resp["data"]

    # ── CRUD ───────────────────────────────────────────────────
    def list_proxies(self, service_id: str, env_id: str) -> list[dict]:
        q = ('query($e: String!, $s: String!) { tcpProxies(environmentId: $e, serviceId: $s) '
             '{ id domain proxyPort applicationPort syncStatus } }')
        return self._gql(q, {"e": env_id, "s": service_id}).get("tcpProxies") or []

    def create_proxy(self, service_id: str, env_id: str, app_port: int) -> dict:
        r = self._gql(
            'mutation($input: TCPProxyCreateInput!) { tcpProxyCreate(input: $input) '
            '{ id domain proxyPort applicationPort syncStatus } }',
            {"input": {"applicationPort": app_port,
                       "environmentId": env_id, "serviceId": service_id}})
        return r.get("tcpProxyCreate") or {}

    def delete_proxy(self, proxy_id: str) -> bool:
        return bool(self._gql(
            'mutation($id: String!) { tcpProxyDelete(id: $id) }',
            {"id": proxy_id}).get("tcpProxyDelete"))

    def find_env(self, project_id: str) -> str | None:
        edges = self._gql(
            'query($pid: String!){ environments(projectId: $pid) '
            '{ edges { node { id name } } } }', {"pid": project_id})
        envs = [e["node"] for e in edges.get("environments", {}).get("edges", [])]
        for e in envs:
            if (e.get("name") or "").lower() == "production":
                return e.get("id")
        return envs[0].get("id") if envs else None

    def list_services(self, service_id_or_project: str) -> list[dict]:
        """Accepts a PROJECT id. (Passing a service id returns null → error.)"""
        d = self._gql(
            'query($id: String!){ project(id: $id) '
            '{ services(first: 20) { edges { node { id name } } } } }',
            {"id": service_id_or_project})
        edges = ((d.get("project") or {}).get("services") or {}).get("edges", [])
        return [e["node"] for e in edges]

    # ── helpers ────────────────────────────────────────────────
    def wait_active(self, service_id: str, env_id: str, timeout: int = 240) -> dict | None:
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            live = [p for p in self.list_proxies(service_id, env_id)
                    if p.get("syncStatus") == "ACTIVE"]
            if live:
                last = live[0]
                if len(live) == 1:
                    return live[0]
            time.sleep(5)
        return last

    @staticmethod
    def test_domain(domain: str, port: int, timeout: int = 5) -> bool:
        try:
            s = socket.create_connection((domain, port), timeout=timeout)
            s.close()
            return True
        except Exception:
            return False

    # ── rotation (blocking; run via asyncio.to_thread) ────────
    def rotate(self, service_id: str, env_id: str, app_port: int,
               targets: set | None = None, max_tries: int = 30,
               cooldown: float = 8, on_progress=None, cancel_check=None):
        """Rotate until a target domain is hit (or any connectable one).

        Returns (domain, port) or None.
        """
        targets = targets or set()
        api_port = app_port

        def log(msg):
            if on_progress:
                on_progress(msg)

        for attempt in range(1, max_tries + 1):
            if cancel_check and cancel_check():
                log("⏹ توسط کاربر متوقف شد")
                return None

            # 1) delete non-target proxies
            for p in self.list_proxies(service_id, env_id):
                if (p.get("domain") not in targets
                        and p.get("syncStatus") not in ("DELETED", "DELETING")):
                    log(f"[{attempt}] 🗑 حذف {p['domain']}:{p.get('proxyPort')}")
                    try:
                        self.delete_proxy(p["id"])
                    except Exception as e:
                        log(f"[{attempt}] حذف ناموفق: {e}")
            time.sleep(max(cooldown - 2, 3))

            # 2) create new
            try:
                created = self.create_proxy(service_id, env_id, api_port)
            except Exception as e:
                log(f"[{attempt}] ساخت ناموفق: {e}")
                time.sleep(cooldown)
                continue
            if not created:
                log(f"[{attempt}] ساخت ناموفق، تکرار...")
                time.sleep(cooldown)
                continue

            domain = (created.get("domain") or "?").rstrip(".")
            log(f"[{attempt}] ✨ ساخته شد → {domain}")

            # 3) wait ACTIVE (final domain may differ!)
            proxy = self.wait_active(service_id, env_id)
            if proxy:
                final = (proxy.get("domain") or "").rstrip(".")
                if final and final != domain:
                    domain = final
                    log(f"[{attempt}] دامنه نهایی → {domain}")
            port = (proxy or created).get("proxyPort") or api_port

            hit = False
            if targets:
                if domain in targets:
                    hit = True
            else:
                ok = self.test_domain(domain, port)
                log(f"[{attempt}] تست {domain}:{port} → {'✓' if ok else '✗'}")
                if ok:
                    hit = True

            if hit:
                log(f"🎯 HIT → {domain}:{port}")
                return (domain, port)
            time.sleep(cooldown)

        log(f"❌ بعد از {max_tries} تلاش به هدف نرسید")
        return None
