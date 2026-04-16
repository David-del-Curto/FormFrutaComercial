import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.cache_sqlite import get_conn
from services.local_store import evaluar_estado_formulario, get_local_now, init_local_store


def _build_payload(row) -> dict:
    return {
        "centro_codigo": row["centro_codigo"],
        "centro_sin_definir": int(row["centro_sin_definir"] or 0),
        "velocidad_kgh": float(row["velocidad_kgh"] or 0.0),
        "velocidad_manual": float(row["velocidad_manual"] or 0.0),
        "porc_export_manual": int(row["porc_export_manual"] or 0),
    }


def _fetch_target_rows(conn, record_id: int | None, all_open: bool):
    if record_id is not None:
        return conn.execute(
            """
            SELECT *
            FROM registro
            WHERE id_registro = ?
            """,
            (record_id,),
        ).fetchall()

    if all_open:
        return conn.execute(
            """
            SELECT *
            FROM registro
            WHERE es_completo = 0
            ORDER BY id_registro ASC
            """
        ).fetchall()

    return []


def run(record_id: int | None, all_open: bool, dry_run: bool) -> int:
    init_local_store()
    conn = get_conn()

    rows = _fetch_target_rows(conn, record_id=record_id, all_open=all_open)
    if not rows:
        print("No se encontraron registros objetivo para backfill.")
        conn.close()
        return 0

    now_iso = get_local_now().isoformat(timespec="seconds")
    evaluados = 0
    actualizados = 0

    for row in rows:
        evaluados += 1
        payload = _build_payload(row)
        nuevo_estado = evaluar_estado_formulario(payload)

        estado_actual = (row["estado_formulario"] or "").strip().lower()
        pendientes_actual = (row["campos_pendientes"] or "").strip()
        es_completo_actual = int(row["es_completo"] or 0)

        estado_nuevo = nuevo_estado["estado_formulario"]
        pendientes_nuevo = nuevo_estado["campos_pendientes"]
        es_completo_nuevo = int(nuevo_estado["es_completo"])

        cambio = (
            estado_actual != estado_nuevo
            or pendientes_actual != pendientes_nuevo
            or es_completo_actual != es_completo_nuevo
        )
        if not cambio:
            continue

        actualizados += 1
        print(
            f"#{row['id_registro']}: "
            f"{estado_actual or '-'} -> {estado_nuevo} | "
            f"pendientes: '{pendientes_actual or '-'}' -> '{pendientes_nuevo or '-'}'"
        )

        if dry_run:
            continue

        conn.execute(
            """
            UPDATE registro
            SET estado_formulario = ?,
                es_completo = ?,
                campos_pendientes = ?,
                updated_at = ?
            WHERE id_registro = ?
            """,
            (
                estado_nuevo,
                es_completo_nuevo,
                pendientes_nuevo,
                now_iso,
                int(row["id_registro"]),
            ),
        )

    if dry_run:
        print(f"[DRY-RUN] Evaluados: {evaluados} | Cambios detectados: {actualizados}")
    else:
        conn.commit()
        print(f"Evaluados: {evaluados} | Registros actualizados: {actualizados}")

    conn.close()
    return 0


def parse_args():
    parser = argparse.ArgumentParser(
        description="Recalcula estado_formulario/es_completo/campos_pendientes para registros locales."
    )
    parser.add_argument("--id", dest="record_id", type=int, help="Id especifico a recalcular.")
    parser.add_argument(
        "--all-open",
        action="store_true",
        help="Recalcula todos los registros abiertos (es_completo = 0).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra cambios sin persistirlos.",
    )
    args = parser.parse_args()

    if args.record_id is None and not args.all_open:
        parser.error("Debes indicar --id <N> o --all-open.")

    return args


if __name__ == "__main__":
    cli_args = parse_args()
    raise SystemExit(
        run(
            record_id=cli_args.record_id,
            all_open=cli_args.all_open,
            dry_run=cli_args.dry_run,
        )
    )
