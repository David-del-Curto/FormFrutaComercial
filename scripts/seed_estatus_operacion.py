import argparse
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.business_rules import usa_velocidad_tercero
from core.catalogos import DEFECTOS, LUGAR_SELECCION
from core.forms import calcular_indicadores_operaciones
from services.cache_sqlite import get_conn
from services.local_store import (
    calcular_contexto_operacional,
    get_current_operational_date,
    init_local_store,
    save_formulario_local,
)


TIMEZONE = ZoneInfo("America/Santiago")
SEED_TAG = "[SEED-ESTATUS-OPERACION]"
LEGACY_SEED_TAG = "[SEED-ESTATUS-20260325]"
SEED_TAG_PREFIXES = (SEED_TAG, LEGACY_SEED_TAG)


@dataclass
class Scenario:
    timestamp: str
    lote: str
    muestra: int
    defectos_total: int
    choice: int
    velocidad_kgh: int
    kg_comercial: int
    especie: str
    variedad: str
    linea: str
    centro_codigo: str
    centro_nombre: str
    lugar_codigo: str
    verificador: str
    defect_pool: list[str]
    pending: bool = False


def parse_date(value: str) -> str:
    return datetime.strptime(value, "%Y-%m-%d").date().isoformat()


def make_timestamp(date_str: str, hour_minute: str) -> str:
    dt = datetime.strptime(f"{date_str} {hour_minute}", "%Y-%m-%d %H:%M").replace(tzinfo=TIMEZONE)
    return dt.isoformat(timespec="seconds")


def distribute(total: int, codes: list[str]) -> dict[str, int]:
    if total <= 0:
        return {}
    base, rem = divmod(total, len(codes))
    result: dict[str, int] = {}
    for idx, code in enumerate(codes):
        value = base + (1 if idx < rem else 0)
        if value > 0:
            result[code] = value
    return result


def build_seed_filter() -> tuple[str, tuple[str, ...]]:
    where = " OR ".join("observaciones LIKE ?" for _ in SEED_TAG_PREFIXES)
    params = tuple(f"{prefix}%" for prefix in SEED_TAG_PREFIXES)
    return where, params


def build_scenarios(date_str: str) -> list[Scenario]:
    rows = [
        ("08:10", "D25-001", 100, 26, 22, 2000, 800, "KIWIS", "SUMMER", "LIN_03", "DC10", "C.F.Retiro", "MS", "QA-01", ["MR", "DEF", "CRA", "LEN", "FC", "RAM"], False),
        ("09:05", "D25-002", 50, 13, 9, 1200, 480, "PERAS", "PACKHAM", "LIN_01", "DC05", "Centro Fruta", "BC", "QA-02", ["MR", "HAO", "PAR", "DES", "BP"], False),
        ("10:20", "D25-003", 100, 35, 15, 2800, 980, "CEREZAS", "SANTINA", "LIN_04", "DC05", "Centro Fruta", "TP", "QA-03", ["CRA", "PAR", "MR", "DI", "RG", "RUS"], False),
        ("11:35", "D25-004", 50, 18, 6, 1600, 640, "ARANDANOS", "DUKE", "LIN_03", "DC10", "C.F.Retiro", "MS", "QA-04", ["DEF", "MR", "LEN", "FC", "HAF", "RAM"], False),
        ("12:40", "D25-005", 100, 42, 10, 3000, 1500, "MANZANAS", "GALA", "LIN_02", "DC05", "Centro Fruta", "BC", "QA-05", ["BP", "MR", "HC", "DI", "DES", "DEF"], False),
        ("14:10", "D25-006", 50, 10, 15, 1800, 540, "PERAS", "FORELLE", "LIN_07", "DC05", "Centro Fruta", "TP", "QA-06", ["MR", "RLP", "FC", "LEN", "CRA"], False),
        ("15:55", "D25-007", 100, 30, 20, 2500, 1000, "KIWIS", "HAYWARD", "LIN_03", "DC10", "C.F.Retiro", "MS", "QA-01", ["DEF", "MR", "CRA", "BP", "DI", "DES"], False),
        ("17:20", "D25-008", 50, 14, 8, 1900, 760, "CEREZAS", "REGINA", "LIN_04", "DC05", "Centro Fruta", "BC", "QA-02", ["PAR", "CRA", "MR", "RG", "HAF"], False),
        ("18:45", "D25-009", 100, 28, 18, 2600, 1300, "ARANDANOS", "EMERALD", "LIN_03", "DC10", "C.F.Retiro", "TP", "QA-03", ["MR", "DEF", "LEN", "FC", "RAM", "RLP"], False),
        ("20:05", "D25-010", 50, 16, 10, 1700, 850, "MANZANAS", "FUJI", "LIN_02", "DC05", "Centro Fruta", "MS", "QA-04", ["BP", "MR", "HC", "DI", "DES", "DEF"], False),
        ("22:05", "D25-011", 100, 33, 12, 2400, 960, "KIWIS", "SUMMER", "LIN_03", "DC10", "C.F.Retiro", "BC", "QA-05", ["MR", "DEF", "CRA", "LEN", "FC", "RAM", "DI"], False),
        ("22:35", "D25-012", 50, 11, 14, 1500, 525, "PERAS", "ABATE", "LIN_01", "DC05", "Centro Fruta", "TP", "QA-06", ["MR", "HAO", "PAR", "DES", "BP", "RUS"], False),
        # Pendientes intencionales para poblar la tabla de pendientes.
        ("21:15", "D25-013", 100, 24, 20, 0, 0, "CEREZAS", "LAPINS", "LIN_04", "DC05", "Centro Fruta", "MS", "QA-07", ["MR", "CRA", "PAR", "DI", "DEF"], True),
        ("23:05", "D25-014", 50, 12, 8, 0, 0, "ARANDANOS", "LEGACY", "LIN_03", "DC10", "C.F.Retiro", "BC", "QA-08", ["MR", "DEF", "LEN", "FC", "DES"], True),
    ]

    scenarios: list[Scenario] = []
    for row in rows:
        hour_min, *rest = row
        scenarios.append(
            Scenario(
                timestamp=make_timestamp(date_str, hour_min),
                lote=rest[0],
                muestra=rest[1],
                defectos_total=rest[2],
                choice=rest[3],
                velocidad_kgh=rest[4],
                kg_comercial=rest[5],
                especie=rest[6],
                variedad=rest[7],
                linea=rest[8],
                centro_codigo=rest[9],
                centro_nombre=rest[10],
                lugar_codigo=rest[11],
                verificador=rest[12],
                defect_pool=rest[13],
                pending=rest[14],
            )
        )
    return scenarios


def clear_seed_records() -> int:
    conn = get_conn()
    seed_where, seed_params = build_seed_filter()
    seed_ids = [
        int(row["id_registro"])
        for row in conn.execute(
            f"SELECT id_registro FROM registro WHERE {seed_where}",
            seed_params,
        ).fetchall()
    ]

    if seed_ids:
        marks = ",".join("?" for _ in seed_ids)
        conn.execute(f"DELETE FROM registro_defectos WHERE id_registro IN ({marks})", seed_ids)
        conn.execute(f"DELETE FROM registro WHERE id_registro IN ({marks})", seed_ids)
        conn.commit()

    conn.close()
    return len(seed_ids)


def make_payload(s: Scenario) -> tuple[dict, dict[str, int]]:
    defectos = distribute(s.defectos_total, s.defect_pool)
    suma_defectos = sum(defectos.values())
    fruta_sana = s.muestra - suma_defectos - s.choice
    if fruta_sana < 0:
        raise ValueError(f"fruta_sana negativa para lote {s.lote}")

    indicadores = calcular_indicadores_operaciones(
        s.muestra,
        suma_defectos,
        s.choice,
        s.velocidad_kgh,
        s.kg_comercial,
    )

    if s.pending:
        velocidad_manual = 0.0
    elif usa_velocidad_tercero(s.centro_codigo):
        velocidad_manual = max(round(s.velocidad_kgh * 0.65, 1), 1.0)
    else:
        velocidad_manual = 0.0

    payload = {
        "fecha": s.timestamp[:10],
        "linea": s.linea,
        "especie": s.especie,
        "variedad": s.variedad,
        "lote": s.lote,
        "centro_codigo": s.centro_codigo,
        "centro_nombre": s.centro_nombre,
        "centro_display": f"{s.centro_codigo} - {s.centro_nombre}",
        "productor_codigo": "P0001",
        "productor_nombre": "Productor Demo",
        "productor_display": "P0001 - Productor Demo",
        "cant_muestra": s.muestra,
        "suma_defectos": suma_defectos,
        "fruta_comercial": suma_defectos,
        "fruta_sana": fruta_sana,
        "choice": s.choice,
        "porc_exportable": indicadores["porc_exportable"],
        "porc_embalable": indicadores["porc_embalable"],
        "porc_choice": indicadores["porc_choice"],
        "porc_descartable": indicadores["porc_descartable"],
        "observaciones": f"{SEED_TAG} {s.lote}",
        "verificador": s.verificador,
        "lugar_codigo": s.lugar_codigo,
        "lugar_nombre": LUGAR_SELECCION[s.lugar_codigo],
        "velocidad_kgh": s.velocidad_kgh,
        "kg_ultima_hora": s.kg_comercial,
        "porc_export_manual": 0,
        "velocidad_manual": velocidad_manual,
        "centro_sin_definir": 0,
        "defectos_nombres": DEFECTOS,
    }
    return payload, defectos


def backfill_timestamps(inserted_records: list[tuple[int, str]]):
    conn = get_conn()
    for record_id, timestamp in inserted_records:
        dt = datetime.fromisoformat(timestamp)
        contexto = calcular_contexto_operacional(dt)

        conn.execute(
            """
            UPDATE registro
            SET fecha_operacional = ?,
                turno_codigo = ?,
                turno_nombre = ?,
                rango_turno = ?,
                created_at = ?,
                updated_at = ?
            WHERE id_registro = ?
            """,
            (
                contexto["fecha_operacional"],
                contexto["turno_codigo"],
                contexto["turno_nombre"],
                contexto["rango_turno"],
                contexto["timestamp"],
                contexto["timestamp"],
                record_id,
            ),
        )
        conn.execute(
            """
            UPDATE registro_defectos
            SET created_at = ?, updated_at = ?
            WHERE id_registro = ?
            """,
            (contexto["timestamp"], contexto["timestamp"], record_id),
        )

    conn.commit()
    conn.close()


def print_status(date_operacional: str):
    conn = get_conn()
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS formularios,
            COALESCE(SUM(cant_muestra), 0) AS muestra,
            COALESCE(SUM(es_completo), 0) AS completos,
            COALESCE(SUM(CASE WHEN es_completo = 0 THEN 1 ELSE 0 END), 0) AS borradores,
            MIN(updated_at) AS min_upd,
            MAX(updated_at) AS max_upd
        FROM registro
        WHERE fecha_operacional = ?
        """,
        (date_operacional,),
    ).fetchone()

    turnos = conn.execute(
        """
        SELECT turno_nombre, COUNT(*) AS formularios, COALESCE(SUM(cant_muestra), 0) AS muestra
        FROM registro
        WHERE fecha_operacional = ?
        GROUP BY turno_nombre
        ORDER BY turno_nombre
        """,
        (date_operacional,),
    ).fetchall()

    seed_where, seed_params = build_seed_filter()
    seed_count = conn.execute(
        f"SELECT COUNT(*) AS n FROM registro WHERE {seed_where}",
        seed_params,
    ).fetchone()["n"]
    conn.close()

    print(f"Fecha operacional: {date_operacional}")
    print(f"Formularios: {row['formularios']}")
    print(f"Completos: {row['completos']}")
    print(f"Borradores: {row['borradores']}")
    print(f"Muestra total: {row['muestra']}")
    print(f"Rango update: {row['min_upd']} -> {row['max_upd']}")
    print(f"Registros seed activos ({SEED_TAG}): {seed_count}")
    print("Muestra por turno:")
    for t in turnos:
        print(f"  - {t['turno_nombre']}: formularios={t['formularios']}, muestra={t['muestra']}")


def run_seed(date_operacional: str):
    init_local_store()
    deleted = clear_seed_records()
    scenarios = build_scenarios(date_operacional)

    inserted: list[tuple[int, str]] = []
    for scenario in scenarios:
        payload, defectos = make_payload(scenario)
        saved = save_formulario_local(payload, defectos)
        inserted.append((int(saved["id_registro"]), scenario.timestamp))

    backfill_timestamps(inserted)
    print(f"Seed completado. Eliminados previos: {deleted}. Insertados: {len(inserted)}.")
    print_status(date_operacional)


def main():
    parser = argparse.ArgumentParser(
        description="Seeder para Estatus Operacion (re-seed / clear) en Form Fruta Comercial."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    default_date = get_current_operational_date()

    seed_parser = subparsers.add_parser("seed", help="Limpia seeds previos y vuelve a insertar datos demo.")
    seed_parser.add_argument(
        "--date",
        default=default_date,
        type=parse_date,
        help=f"Dia operacional objetivo YYYY-MM-DD (default: {default_date}).",
    )

    clear_parser = subparsers.add_parser("clear", help="Elimina solo los registros seed.")
    clear_parser.add_argument(
        "--date",
        default=default_date,
        type=parse_date,
        help=f"Dia operacional para mostrar status final YYYY-MM-DD (default: {default_date}).",
    )

    status_parser = subparsers.add_parser("status", help="Muestra resumen del dia operacional.")
    status_parser.add_argument(
        "--date",
        default=default_date,
        type=parse_date,
        help=f"Dia operacional YYYY-MM-DD (default: {default_date}).",
    )

    args = parser.parse_args()

    if args.command == "seed":
        run_seed(args.date)
        return

    if args.command == "clear":
        init_local_store()
        deleted = clear_seed_records()
        print(f"Seeds eliminados: {deleted}")
        print_status(args.date)
        return

    if args.command == "status":
        init_local_store()
        print_status(args.date)
        return


if __name__ == "__main__":
    main()
