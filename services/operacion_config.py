from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import toml as tomllib


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "operacion.toml"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DEFAULT_CONFIG = {
    "screens": {},
    "mail": {
        "global_recipients": [],
        "line_recipients": {},
        "digest_times": [],
        "alert_threshold_fbc": 1.5,
    },
}


def _load_toml_file(path: Path) -> dict:
    if getattr(tomllib, "__name__", "") == "toml":
        return tomllib.load(str(path))

    with path.open("rb") as fh:
        return tomllib.load(fh)


def _normalize_email_list(values) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        email = str(value or "").strip().lower()
        if not email or email in seen or not EMAIL_RE.match(email):
            continue
        normalized.append(email)
        seen.add(email)
    return normalized


def _normalize_digest_times(values) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        candidate = str(value or "").strip()
        if len(candidate) != 5 or candidate[2] != ":":
            continue
        hh, mm = candidate.split(":", 1)
        if not (hh.isdigit() and mm.isdigit()):
            continue
        hour = int(hh)
        minute = int(mm)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            continue
        label = f"{hour:02d}:{minute:02d}"
        if label in seen:
            continue
        normalized.append(label)
        seen.add(label)
    return normalized


def load_operacion_config() -> dict:
    config = deepcopy(DEFAULT_CONFIG)

    if CONFIG_PATH.exists():
        raw_config = _load_toml_file(CONFIG_PATH)
    else:
        raw_config = {}

    screens = raw_config.get("screens", {})
    normalized_screens: dict[str, dict] = {}
    for screen_id, raw_screen in screens.items():
        screen_key = str(screen_id or "").strip()
        if not screen_key:
            continue

        screen = dict(raw_screen or {})
        linea = str(screen.get("linea") or "").strip()
        if not linea:
            continue

        refresh_seconds = int(screen.get("refresh_seconds") or 600)
        normalized_screens[screen_key] = {
            "screen_id": screen_key,
            "label": str(screen.get("label") or screen_key).strip(),
            "linea": linea,
            "especie": str(screen.get("especie") or "").strip(),
            "variedad": str(screen.get("variedad") or "").strip(),
            "view": str(screen.get("view") or "estatus").strip().lower() or "estatus",
            "refresh_seconds": max(refresh_seconds, 60),
            "lock_filters": bool(screen.get("lock_filters", True)),
            "hide_sidebar": bool(screen.get("hide_sidebar", False)),
        }

    mail = raw_config.get("mail", {})
    line_recipients_raw = mail.get("line_recipients", {})
    normalized_line_recipients = {
        str(linea or "").strip(): _normalize_email_list(recipients)
        for linea, recipients in line_recipients_raw.items()
        if str(linea or "").strip()
    }

    config["screens"] = normalized_screens
    config["mail"] = {
        "global_recipients": _normalize_email_list(mail.get("global_recipients")),
        "line_recipients": normalized_line_recipients,
        "digest_times": _normalize_digest_times(mail.get("digest_times")),
        "alert_threshold_fbc": float(mail.get("alert_threshold_fbc") or 1.5),
    }
    return config


def get_screen_config(screen_id: str | None, config: dict | None = None) -> dict | None:
    if not screen_id:
        return None

    config = config or load_operacion_config()
    return config.get("screens", {}).get(str(screen_id).strip())


def get_line_recipients(linea: str, config: dict | None = None) -> list[str]:
    config = config or load_operacion_config()
    return list(config.get("mail", {}).get("line_recipients", {}).get(str(linea or "").strip(), []))
