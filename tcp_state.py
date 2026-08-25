"""
TCP Proxy feature: per-user settings + suggested-domains store (persistent).
"""
import json
import os
import threading

STATE_PATH = os.getenv("TCP_STATE_FILE", "/tmp/hermes_tcp_state.json")
DEFAULT_GOOD_DOMAINS = (
    "monorail,nozomi,turntable,trolley,reseau,autorack,metro,hopper,"
    "kodama,interchange,switchyard,junction"
)


class TCPState:
    """Thread-safe persistent state:
       - good_domains: shared suggested-domain list
       - user_settings[uid]: {"count": int, "port": int, "mode": "rnd"|"good"}
    """

    def __init__(self, path: str = STATE_PATH):
        self.path = path
        self._lock = threading.Lock()
        self._data = {"good_domains": DEFAULT_GOOD_DOMAINS.split(","), "user_settings": {}}
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    self._data.update(raw)
        except Exception:
            pass

    def _save(self):
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except Exception:
            pass

    # ── suggested domains ──────────────────────────────────────
    def get_domains(self) -> list[str]:
        with self._lock:
            return list(self._data.get("good_domains", []))

    def set_domains(self, domains: list[str]):
        clean = [d.strip().rstrip(".") for d in domains if d.strip()]
        with self._lock:
            self._data["good_domains"] = clean
            self._save()

    def add_domain(self, domain: str) -> bool:
        d = domain.strip().rstrip(".")
        if not d:
            return False
        if not d.endswith(".proxy.rlwy.net"):
            d += ".proxy.rlwy.net"
        with self._lock:
            lst = self._data.setdefault("good_domains", [])
            if d in lst:
                return False
            lst.append(d)
            self._save()
        return True

    def remove_domain(self, domain: str) -> bool:
        d = domain.strip().rstrip(".")
        if not d.endswith(".proxy.rlwy.net"):
            d += ".proxy.rlwy.net"
        with self._lock:
            lst = self._data.get("good_domains", [])
            if d not in lst:
                return False
            lst.remove(d)
            self._save()
        return True

    def reset_domains(self):
        with self._lock:
            self._data["good_domains"] = DEFAULT_GOOD_DOMAINS.split(",")
            self._save()

    # ── per-user settings ──────────────────────────────────────
    def get_user(self, uid) -> dict:
        with self._lock:
            return dict(self._data.get("user_settings", {}).get(str(uid), {}))

    def set_user(self, uid, **kv):
        with self._lock:
            users = self._data.setdefault("user_settings", {})
            u = users.setdefault(str(uid), {"count": 2, "port": 443, "mode": "good"})
            u.update(kv)
            self._save()

    def target_set(self) -> set:
        """Domains as full .proxy.rlwy.net targets."""
        from tcp_api import normalize_domains
        return normalize_domains(",".join(self.get_domains()))
