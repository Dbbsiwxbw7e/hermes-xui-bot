"""
Multi-account Railway token store — per Telegram user, persistent, encrypted-optional.
Accounts: {tg_uid: {label: {"token": enc, "email": str}}}
Active:   {tg_uid: label}
"""
import json
import os
import threading

STATE_PATH = os.getenv("ACCOUNTS_FILE", "/tmp/hermes_accounts.json")


class AccountStore:
    def __init__(self, path: str = STATE_PATH):
        self.path = path
        self._lock = threading.Lock()
        self._data = {"accounts": {}, "active": {}}
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
                json.dump(self._data, f, ensure_ascii=False)
            os.replace(tmp, self.path)
        except Exception:
            pass

    # ── accounts ───────────────────────────────────────────────
    def add(self, uid, label: str, token: str, email: str = "") -> bool:
        """Returns False if label already exists."""
        with self._lock:
            accs = self._data["accounts"].setdefault(str(uid), {})
            if label in accs:
                return False
            accs[label] = {"token": token, "email": email}
            # first account becomes active automatically
            self._data["active"].setdefault(str(uid), label)
            self._save()
        return True

    def remove(self, uid, label: str) -> bool:
        with self._lock:
            accs = self._data["accounts"].get(str(uid), {})
            if label not in accs:
                return False
            del accs[label]
            if self._data["active"].get(str(uid)) == label:
                # switch to remaining account (or none)
                rest = list(accs.keys())
                if rest:
                    self._data["active"][str(uid)] = rest[0]
                else:
                    self._data["active"].pop(str(uid), None)
            self._save()
        return True

    def get(self, uid, label: str | None = None) -> dict | None:
        with self._lock:
            accs = self._data["accounts"].get(str(uid), {})
            lbl = label or self._data["active"].get(str(uid))
            entry = accs.get(lbl or "")
            return dict(entry) if entry else None

    def list(self, uid) -> list[dict]:
        with self._lock:
            accs = self._data["accounts"].get(str(uid), {})
            active = self._data["active"].get(str(uid))
            return [{"label": k,
                     "email": v.get("email", ""),
                     "active": k == active}
                    for k, v in accs.items()]

    def labels(self, uid):
        with self._lock:
            return list(self._data["accounts"].get(str(uid), {}).keys())

    # ── switching ──────────────────────────────────────────────
    def set_active(self, uid, label: str) -> bool:
        with self._lock:
            if label not in self._data["accounts"].get(str(uid), {}):
                return False
            self._data["active"][str(uid)] = label
            self._save()
        return True

    def active_label(self, uid) -> str:
        with self._lock:
            return self._data["active"].get(str(uid), "")
