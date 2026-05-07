from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.local_store import (
    get_current_operational_date,
    get_defectos_df,
    get_local_now,
    get_operacion_alert_state,
    get_registros_df,
    init_local_store,
    log_operacion_dispatch,
    set_operacion_alert_state,
    was_operacion_dispatch_sent,
)
from services.operacion_config import load_operacion_config
from services.operacion_email import (
    build_alert_email,
    build_general_digest_email,
    build_line_digest_email,
    send_email,
)
from services.operacion_status import apply_record_filters, build_operacion_snapshot


ALERT_CODE_FBC = "fbc_1h_threshold"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Envío de correos de Status Operación")
    parser.add_argument("--fecha", help="Fecha operacional YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="No envía correos ni registra despachos")
    parser.add_argument("--force-digest", action="store_true", help="Fuerza el envío del digest aunque no coincida con una hora programada")
    parser.add_argument("--force-alerts", action="store_true", help="Evalúa alertas aunque no existan destinatarios por línea configurados")
    parser.add_argument("--schedule-slot", help="Etiqueta HH:MM para el digest programado")
    parser.add_argument("--skip-digest", action="store_true", help="Omite el envío de digest")
    parser.add_argument("--skip-alerts", action="store_true", help="Omite el envío de alertas")
    return parser.parse_args()


def _dedupe_recipients(*recipient_groups) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for group in recipient_groups:
        for value in group or []:
            email = str(value or "").strip().lower()
            if not email or email in seen:
                continue
            normalized.append(email)
            seen.add(email)
    return normalized


def _registered_recipients(config: dict) -> set[str]:
    recipients = set(config["mail"].get("global_recipients", []))
    for group in config["mail"].get("line_recipients", {}).values():
        recipients.update(group or [])
    return recipients


def _filter_registered_recipients(recipients: list[str], registered: set[str]) -> list[str]:
    return [email for email in recipients if email in registered]


def _resolve_digest_slot(config: dict, now_local: datetime, args: argparse.Namespace) -> str | None:
    if args.skip_digest:
        return None

    if args.schedule_slot:
        return args.schedule_slot.strip()

    if args.force_digest:
        return now_local.strftime("%H:%M")

    current_slot = now_local.strftime("%H:%M")
    if current_slot in config["mail"]["digest_times"]:
        return current_slot
    return None


def _send_or_log(subject: str, html_body: str, recipients: list[str], dry_run: bool):
    if not recipients:
        print(f"[skip] {subject} sin destinatarios registrados válidos")
        return False

    if dry_run:
        print(f"[dry-run] {subject} -> {', '.join(recipients) if recipients else '(sin destinatarios)'}")
        return False

    if not send_email(subject=subject, html_body=html_body, recipients=recipients):
        print(f"[skip] {subject} sin destinatarios registrados válidos")
        return False

    print(f"[sent] {subject} -> {', '.join(recipients)}")
    return True


def _build_line_snapshots(records_df, defectos_df, lineas: list[str]) -> dict[str, dict]:
    snapshots: dict[str, dict] = {}
    for linea in sorted({str(linea or "").strip() for linea in lineas if str(linea or "").strip()}):
        line_records_df = apply_record_filters(records_df, linea=linea)
        snapshots[linea] = build_operacion_snapshot(line_records_df, defectos_df)
    return snapshots


def main():
    args = _parse_args()
    init_local_store()

    now_local = get_local_now()
    fecha_operacional = args.fecha or get_current_operational_date()
    config = load_operacion_config()

    registros_df = get_registros_df(fecha_operacional)
    defectos_df = get_defectos_df(fecha_operacional)
    general_snapshot = build_operacion_snapshot(registros_df, defectos_df)

    config_lineas = set(config["mail"]["line_recipients"].keys())
    data_lineas = set(registros_df.get("linea", []).tolist()) if not registros_df.empty else set()
    screen_lineas = {screen["linea"] for screen in config.get("screens", {}).values()}
    lineas_objetivo = sorted({str(linea).strip() for linea in (config_lineas | data_lineas | screen_lineas) if str(linea).strip()})
    line_snapshots = _build_line_snapshots(registros_df, defectos_df, lineas_objetivo)

    digest_slot = _resolve_digest_slot(config, now_local, args)
    global_recipients = config["mail"]["global_recipients"]
    registered_recipients = _registered_recipients(config)

    if digest_slot is not None:
        digest_schedule_key = digest_slot if not args.force_digest else f"{digest_slot}-manual-{now_local.strftime('%H%M%S')}"

        global_recipients = _filter_registered_recipients(global_recipients, registered_recipients)

        if global_recipients:
            already_sent = was_operacion_dispatch_sent(
                "digest_general",
                fecha_operacional,
                "general",
                digest_slot,
            )
            if args.force_digest or not already_sent:
                subject, html_body = build_general_digest_email(fecha_operacional, general_snapshot, line_snapshots)
                if _send_or_log(subject, html_body, global_recipients, args.dry_run):
                    log_operacion_dispatch(
                        dispatch_kind="digest_general",
                        fecha_operacional=fecha_operacional,
                        target_key="general",
                        schedule_key=digest_schedule_key,
                        recipients=global_recipients,
                        metadata={"schedule_slot": digest_slot},
                    )
        else:
            print("[skip] digest_general sin destinatarios globales registrados")

        for linea, snapshot in line_snapshots.items():
            recipients = _filter_registered_recipients(
                _dedupe_recipients(global_recipients, config["mail"]["line_recipients"].get(linea, [])),
                registered_recipients,
            )
            if not recipients:
                continue

            already_sent = was_operacion_dispatch_sent(
                "digest_linea",
                fecha_operacional,
                linea,
                digest_slot,
            )
            if args.force_digest or not already_sent:
                subject, html_body = build_line_digest_email(fecha_operacional, linea, snapshot)
                if _send_or_log(subject, html_body, recipients, args.dry_run):
                    log_operacion_dispatch(
                        dispatch_kind="digest_linea",
                        fecha_operacional=fecha_operacional,
                        target_key=linea,
                        schedule_key=digest_schedule_key,
                        recipients=recipients,
                        metadata={"schedule_slot": digest_slot},
                    )
    else:
        print("[skip] no corresponde digest en esta ejecución")

    if not args.skip_alerts:
        threshold = float(config["mail"]["alert_threshold_fbc"])
        for linea, snapshot in line_snapshots.items():
            recipients = _filter_registered_recipients(
                _dedupe_recipients(global_recipients, config["mail"]["line_recipients"].get(linea, [])),
                registered_recipients,
            )
            if not recipients and not args.force_alerts:
                continue

            current_value = float(snapshot["kpis"]["porc_fbc"])
            state = get_operacion_alert_state(ALERT_CODE_FBC, fecha_operacional, linea) or {}
            is_active = int(state.get("is_active") or 0) == 1
            timestamp = now_local.isoformat(timespec="seconds")

            if current_value >= threshold and not is_active:
                subject, html_body = build_alert_email(fecha_operacional, linea, snapshot, threshold)
                if _send_or_log(subject, html_body, recipients, args.dry_run):
                    log_operacion_dispatch(
                        dispatch_kind="alert_fbc_linea",
                        fecha_operacional=fecha_operacional,
                        target_key=linea,
                        schedule_key=now_local.strftime("%H:%M:%S"),
                        recipients=recipients,
                        metadata={"threshold": threshold, "porc_fbc": current_value},
                    )
                    set_operacion_alert_state(
                        alert_code=ALERT_CODE_FBC,
                        fecha_operacional=fecha_operacional,
                        target_key=linea,
                        is_active=True,
                        last_value=current_value,
                        activated_at=timestamp,
                        recovered_at=None,
                    )
            elif current_value < threshold and is_active:
                set_operacion_alert_state(
                    alert_code=ALERT_CODE_FBC,
                    fecha_operacional=fecha_operacional,
                    target_key=linea,
                    is_active=False,
                    last_value=current_value,
                    activated_at=state.get("activated_at"),
                    recovered_at=timestamp,
                )
                print(f"[rearm] alerta {linea} vuelve bajo umbral ({current_value:.2f})")
            elif state:
                set_operacion_alert_state(
                    alert_code=ALERT_CODE_FBC,
                    fecha_operacional=fecha_operacional,
                    target_key=linea,
                    is_active=is_active,
                    last_value=current_value,
                    activated_at=state.get("activated_at"),
                    recovered_at=state.get("recovered_at"),
                )
    else:
        print("[skip] alertas deshabilitadas para esta ejecución")


if __name__ == "__main__":
    main()
