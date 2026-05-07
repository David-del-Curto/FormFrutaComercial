from __future__ import annotations

import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from html import escape
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import toml as tomllib

from core.catalogos import LINEAS
from services.operacion_status import (
    format_number_latam,
    format_percent_latam,
    format_quantity_latam,
    format_timestamp_label,
)


SECRETS_PATH = Path(__file__).resolve().parents[1] / ".streamlit" / "secrets.toml"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "si", "on"}


def _normalize_recipients(recipients) -> list[str]:
    if recipients is None:
        return []
    if isinstance(recipients, str):
        recipients = [recipients]

    normalized: list[str] = []
    seen: set[str] = set()
    for value in recipients:
        email = str(value or "").strip().lower()
        if not email or email in seen or not EMAIL_RE.match(email):
            continue
        normalized.append(email)
        seen.add(email)
    return normalized


def _load_secrets_file() -> dict:
    if not SECRETS_PATH.exists():
        return {}

    if getattr(tomllib, "__name__", "") == "toml":
        return tomllib.load(str(SECRETS_PATH))

    with SECRETS_PATH.open("rb") as fh:
        return tomllib.load(fh)


def load_mail_settings() -> dict:
    secrets = _load_secrets_file()
    mail_section = secrets.get("mail", {}) if isinstance(secrets.get("mail", {}), dict) else {}
    smtp_section = mail_section.get("smtp", {}) if isinstance(mail_section.get("smtp", {}), dict) else {}

    settings = {
        "host": os.getenv("FORM_FRUTA_MAIL_HOST") or smtp_section.get("host") or mail_section.get("host"),
        "port": int(os.getenv("FORM_FRUTA_MAIL_PORT") or smtp_section.get("port") or mail_section.get("port") or 587),
        "username": os.getenv("FORM_FRUTA_MAIL_USERNAME") or smtp_section.get("username") or mail_section.get("username"),
        "password": os.getenv("FORM_FRUTA_MAIL_PASSWORD") or smtp_section.get("password") or mail_section.get("password"),
        "from_email": os.getenv("FORM_FRUTA_MAIL_FROM") or smtp_section.get("from_email") or mail_section.get("from_email"),
        "from_name": os.getenv("FORM_FRUTA_MAIL_FROM_NAME") or smtp_section.get("from_name") or mail_section.get("from_name") or "Planilla Fruta Comercial",
        "use_tls": _normalize_bool(os.getenv("FORM_FRUTA_MAIL_USE_TLS"), _normalize_bool(smtp_section.get("use_tls"), True)),
        "use_ssl": _normalize_bool(os.getenv("FORM_FRUTA_MAIL_USE_SSL"), _normalize_bool(smtp_section.get("use_ssl"), False)),
    }
    return settings


def send_email(subject: str, html_body: str, recipients, text_body: str | None = None) -> bool:
    recipient_list = _normalize_recipients(recipients)
    if not recipient_list:
        return False

    settings = load_mail_settings()
    required_keys = ["host", "port", "from_email"]
    missing = [key for key in required_keys if not settings.get(key)]
    if missing:
        raise ValueError(f"Configuración SMTP incompleta: faltan {', '.join(missing)}")

    message = EmailMessage()
    from_name = str(settings.get("from_name") or "").strip()
    from_email = str(settings["from_email"]).strip()
    message["Subject"] = subject
    message["From"] = f"{from_name} <{from_email}>" if from_name else from_email
    message["To"] = ", ".join(recipient_list)
    message.set_content(
        text_body or "Este correo requiere un cliente compatible con HTML.",
        charset="utf-8",
    )
    message.add_alternative(html_body, subtype="html", charset="utf-8")

    use_ssl = bool(settings.get("use_ssl"))
    use_tls = bool(settings.get("use_tls")) and not use_ssl
    host = str(settings["host"])
    port = int(settings["port"])
    username = settings.get("username")
    password = settings.get("password")

    if use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as server:
            if username:
                server.login(str(username), str(password or ""))
            server.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.ehlo()
            if use_tls:
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
            if username:
                server.login(str(username), str(password or ""))
            server.send_message(message)

    return True


def _wrap_email_html(title: str, body: str) -> str:
    return f"""
    <html>
      <body style=\"font-family:Segoe UI,Arial,sans-serif;background:#0f1117;color:#e5e7eb;padding:24px;\">
        <div style=\"max-width:1100px;margin:0 auto;background:#171923;border:1px solid #2d3748;border-radius:12px;padding:24px;\">
          <h2 style=\"margin:0 0 16px 0;color:#f8fafc;\">{escape(title)}</h2>
          {body}
        </div>
      </body>
    </html>
    """


def _kpi_cards(snapshot: dict) -> str:
    kpis = snapshot["kpis"]
    summary = snapshot["summary"]
    cards = [
        ("Formularios", format_number_latam(summary["formularios"], 0)),
        ("Completos", format_number_latam(summary["completos"], 0)),
        ("Borradores", format_number_latam(summary["borradores"], 0)),
        ("Muestra", format_number_latam(summary["muestra_total"], 0)),
        ("Kg Exportable 1h", format_quantity_latam(kpis["kg_exportable_total"])),
        ("% FBC Absoluto 1h", format_percent_latam(kpis["porc_fbc"], 1)),
    ]
    pieces = []
    for label, value in cards:
        pieces.append(
            f"<div style='flex:1 1 160px;padding:12px 14px;background:#111827;border:1px solid #374151;border-radius:10px;'>"
            f"<div style='font-size:12px;color:#9ca3af;margin-bottom:6px;'>{escape(label)}</div>"
            f"<div style='font-size:24px;font-weight:700;color:#f8fafc;'>{escape(value)}</div>"
            "</div>"
        )
    return "<div style='display:flex;flex-wrap:wrap;gap:12px;margin:16px 0 20px 0;'>" + "".join(pieces) + "</div>"


def _window_summary(snapshot: dict) -> str:
    window_info = snapshot["window_info"]
    semaforo_estado = snapshot["semaforo_estado"]
    logical_start = format_timestamp_label(window_info.get("logical_start"))
    logical_end = format_timestamp_label(window_info.get("logical_end"))
    observed_start = format_timestamp_label(window_info.get("observed_start"))
    observed_end = format_timestamp_label(window_info.get("observed_end"))
    return (
        "<div style='display:flex;gap:18px;flex-wrap:wrap;margin:12px 0 20px 0;'>"
        f"<div><strong>Estado actual:</strong> {escape(semaforo_estado)}</div>"
        "<div><strong>Bandas:</strong> Verde &lt; 1,0 | Amarillo 1,0-1,49 | Rojo &gt;= 1,5</div>"
        "</div>"
    )


def _line_table(line_snapshots: dict[str, dict]) -> str:
    if not line_snapshots:
        return "<p>No hay líneas configuradas para resumir.</p>"

    rows = []
    for linea, snapshot in sorted(line_snapshots.items()):
        label = LINEAS.get(linea, linea)
        rows.append(
            "<tr>"
            f"<td style='padding:8px 10px;border-bottom:1px solid #374151;'>{escape(label)} ({escape(linea)})</td>"
            f"<td style='padding:8px 10px;border-bottom:1px solid #374151;text-align:right;'>{escape(format_number_latam(snapshot['summary']['formularios'], 0))}</td>"
            f"<td style='padding:8px 10px;border-bottom:1px solid #374151;text-align:right;'>{escape(format_percent_latam(snapshot['kpis']['porc_fbc'], 1))}</td>"
            f"<td style='padding:8px 10px;border-bottom:1px solid #374151;text-align:right;'>{escape(format_quantity_latam(snapshot['kpis']['kg_exportable_total']))}</td>"
            f"<td style='padding:8px 10px;border-bottom:1px solid #374151;'>{escape(snapshot['semaforo_estado'])}</td>"
            "</tr>"
        )

    return (
        "<table style='width:100%;border-collapse:collapse;margin-top:12px;'>"
        "<thead><tr>"
        "<th style='text-align:left;padding:8px 10px;border-bottom:1px solid #4b5563;'>Línea</th>"
        "<th style='text-align:right;padding:8px 10px;border-bottom:1px solid #4b5563;'>Formularios</th>"
        "<th style='text-align:right;padding:8px 10px;border-bottom:1px solid #4b5563;'>% FBC Absoluto 1h</th>"
        "<th style='text-align:right;padding:8px 10px;border-bottom:1px solid #4b5563;'>Kg Exportable 1h</th>"
        "<th style='text-align:left;padding:8px 10px;border-bottom:1px solid #4b5563;'>Estado</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def build_general_digest_email(fecha_operacional: str, general_snapshot: dict, line_snapshots: dict[str, dict]) -> tuple[str, str]:
    title = f"Resumen Status Operación {fecha_operacional}"
    body = (
        f"<p>Resumen general del día operacional <strong>{escape(fecha_operacional)}</strong>.</p>"
        + _kpi_cards(general_snapshot)
        + _window_summary(general_snapshot)
        + "<h3 style='margin-top:24px;color:#f8fafc;'>Resumen por línea</h3>"
        + _line_table(line_snapshots)
    )
    return title, _wrap_email_html(title, body)


def build_line_digest_email(fecha_operacional: str, linea: str, snapshot: dict) -> tuple[str, str]:
    line_label = LINEAS.get(linea, linea)
    title = f"Status Operación {fecha_operacional} - {line_label}"
    body = (
        f"<p>Resumen de línea <strong>{escape(line_label)}</strong> ({escape(linea)}) para el día operacional <strong>{escape(fecha_operacional)}</strong>.</p>"
        + _kpi_cards(snapshot)
        + _window_summary(snapshot)
    )
    return title, _wrap_email_html(title, body)


def build_alert_email(fecha_operacional: str, linea: str, snapshot: dict, threshold: float) -> tuple[str, str]:
    line_label = LINEAS.get(linea, linea)
    current_value = format_percent_latam(snapshot["kpis"]["porc_fbc"], 1)
    threshold_label = format_number_latam(threshold, 1)
    title = f"ALERTA FBC {line_label} {fecha_operacional}"
    body = (
        f"<p>La línea <strong>{escape(line_label)}</strong> ({escape(linea)}) superó el umbral de <strong>{escape(threshold_label)} %</strong> en el KPI <strong>% FBC Absoluto 1h</strong>.</p>"
        f"<p>Valor actual: <strong>{escape(current_value)}</strong>.</p>"
        + _kpi_cards(snapshot)
        + _window_summary(snapshot)
    )
    return title, _wrap_email_html(title, body)
