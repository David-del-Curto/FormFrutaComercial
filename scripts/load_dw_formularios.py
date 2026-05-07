import argparse
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pyodbc

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.extract_dw_staging_payload import build_defect_df, build_header_df
from services.local_store import get_source_system


try:
    import tomllib
except ImportError:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib


DEV_DATABASE = "DEV_ddc_datawarehouse"
PROD_DATABASE = "ddc_datawarehouse"
PROD_SOURCE_SYSTEM = "form_fruta_comercial_prod_ol9"
PROD_CONTAINER_ROOT = Path("/app")
PROD_SQLITE_PATH = PROD_CONTAINER_ROOT / "data" / "cache.db"
REFRACTORED_DDL = ROOT / "sql" / "azure_dw_form_fruta_comercial_refactored.sql"
PHASE1_DDL = ROOT / "sql" / "azure_dw_form_fruta_comercial_phase1_hardening.sql"
SECRETS_PATH = ROOT / ".streamlit" / "secrets.toml"

HEADER_STAGE_COLUMNS = [
    "source_system",
    "source_business_key",
    "source_record_id",
    "fecha",
    "fecha_operacional",
    "turno_codigo",
    "turno_nombre",
    "rango_turno",
    "linea_codigo",
    "linea_nombre",
    "especie",
    "especie_principal_linea",
    "variedad",
    "lote",
    "centro_codigo",
    "centro_nombre",
    "centro_display",
    "productor_codigo",
    "productor_nombre",
    "productor_display",
    "lugar_codigo",
    "lugar_nombre",
    "verificador",
    "observaciones",
    "cant_muestra",
    "suma_defectos",
    "fruta_comercial",
    "fruta_sana",
    "choice",
    "porc_exportable",
    "porc_embalable",
    "porc_choice",
    "porc_descartable",
    "porc_export_manual",
    "velocidad_kgh",
    "velocidad_manual",
    "centro_sin_definir",
    "estado_formulario",
    "es_completo",
    "campos_pendientes",
    "created_at",
    "updated_at",
    "batch_id",
    "source_run_id",
]

DEFECT_STAGE_COLUMNS = [
    "source_system",
    "source_business_key",
    "codigo_defecto",
    "nombre_defecto",
    "cantidad",
    "updated_at",
    "batch_id",
    "source_run_id",
]

REQUIRED_OBJECTS = [
    "stg.FormularioHeader",
    "stg.FormularioDefecto",
    "dbo.DimLinea",
    "dbo.DimLugarSeleccion",
    "dbo.DimTurno",
    "dbo.DimDefecto",
    "dbo.FactFormulario",
    "dbo.FactFormularioDefecto",
    "etl.BatchControl",
    "etl.RechazoFormularioHeader",
    "etl.RechazoFormularioDefecto",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Carga formularios completos desde SQLite a DEV_ddc_datawarehouse."
    )
    parser.add_argument(
        "--target-database",
        default=DEV_DATABASE,
        help=f"Base Azure SQL destino. Default seguro: {DEV_DATABASE}.",
    )
    parser.add_argument(
        "--fecha-operacional",
        help="Filtra por fecha operacional YYYY-MM-DD.",
    )
    parser.add_argument(
        "--prepare-dw",
        action="store_true",
        help="Ejecuta DDL idempotente y seed estatico antes de cargar. En dry-run solo reporta.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida y reporta sin ejecutar DDL, inserts ni stored procedures de proceso.",
    )
    parser.add_argument(
        "--source-run-id",
        help="Identificador de corrida. Default: formfruta_prod_<UTC timestamp>.",
    )
    parser.add_argument(
        "--confirm-dev-load",
        action="store_true",
        help="Confirmacion requerida para escritura real en DEV.",
    )
    return parser.parse_args()


def enforce_database_guard(target_database: str, dry_run: bool, confirm_dev_load: bool):
    database = (target_database or "").strip()
    if database.lower() == PROD_DATABASE.lower():
        raise SystemExit(
            f"ABORTADO: este loader no puede escribir en {PROD_DATABASE}. "
            f"Usa {DEV_DATABASE} para esta primera carga."
        )
    if database != DEV_DATABASE:
        raise SystemExit(
            f"ABORTADO: destino no permitido '{database}'. "
            f"El unico destino habilitado ahora es {DEV_DATABASE}."
        )
    if not dry_run and not confirm_dev_load:
        raise SystemExit(
            "ABORTADO: para carga real en DEV agrega --confirm-dev-load. "
            "Ejecuta primero --dry-run y revisa los conteos."
        )


def enforce_source_guard(dry_run: bool):
    if dry_run:
        return

    source_system = get_source_system()
    root_is_prod_container = ROOT == PROD_CONTAINER_ROOT
    prod_sqlite_exists = PROD_SQLITE_PATH.exists()

    if source_system != PROD_SOURCE_SYSTEM or not root_is_prod_container or not prod_sqlite_exists:
        raise SystemExit(
            "ABORTADO: la carga real solo puede ejecutarse desde el contenedor productivo OL9. "
            f"Esperado source_system={PROD_SOURCE_SYSTEM}, root={PROD_CONTAINER_ROOT}, "
            f"sqlite={PROD_SQLITE_PATH}. "
            f"Actual source_system={source_system}, root={ROOT}."
        )


def load_azure_sql_config(target_database: str):
    if not SECRETS_PATH.exists():
        raise FileNotFoundError(f"No existe {SECRETS_PATH}")

    secrets = tomllib.loads(SECRETS_PATH.read_text(encoding="utf-8"))
    cfg = dict(secrets.get("connections", {}).get("azure_sql", {}))
    cfg["database"] = target_database

    missing = [key for key in ("server", "database", "username", "password", "driver") if not cfg.get(key)]
    if missing:
        raise ValueError(f"Faltan claves Azure SQL en secrets.toml: {', '.join(missing)}")

    return cfg


def build_connection_string(cfg: dict) -> str:
    return (
        f"DRIVER={{{cfg['driver']}}};"
        f"SERVER={cfg['server']};"
        f"DATABASE={cfg['database']};"
        f"UID={cfg['username']};"
        f"PWD={cfg['password']};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )


def split_sql_batches(sql_text: str) -> list[str]:
    batches: list[str] = []
    current: list[str] = []
    for line in sql_text.splitlines():
        if re.match(r"^\s*GO\s*(?:--.*)?$", line, flags=re.IGNORECASE):
            batch = "\n".join(current).strip()
            if batch:
                batches.append(batch)
            current = []
            continue
        current.append(line)

    batch = "\n".join(current).strip()
    if batch:
        batches.append(batch)
    return batches


def execute_sql_script(conn, path: Path):
    batches = split_sql_batches(path.read_text(encoding="utf-8-sig"))
    cursor = conn.cursor()
    for index, batch in enumerate(batches, start=1):
        try:
            cursor.execute(batch)
            while cursor.nextset():
                pass
        except Exception as exc:
            raise RuntimeError(f"Fallo ejecutando {path.name} batch {index}/{len(batches)}: {exc}") from exc
    conn.commit()
    return len(batches)


def execute_prepare_dw(conn):
    ref_batches = execute_sql_script(conn, REFRACTORED_DDL)
    phase1_batches = execute_sql_script(conn, PHASE1_DDL)
    cursor = conn.cursor()
    cursor.execute("EXEC dbo.sp_seed_static_catalogs")
    while cursor.nextset():
        pass
    conn.commit()
    return ref_batches, phase1_batches


def object_exists(cursor, object_name: str) -> bool:
    return cursor.execute("SELECT OBJECT_ID(?)", object_name).fetchval() is not None


def table_count(cursor, object_name: str) -> int | None:
    if not object_exists(cursor, object_name):
        return None
    schema, table = object_name.split(".")
    return int(cursor.execute(f"SELECT COUNT(*) FROM {schema}.{table}").fetchval())


def fetch_metadata_counts(conn):
    cursor = conn.cursor()
    counts: dict[str, int | None] = {}
    for object_name in REQUIRED_OBJECTS:
        counts[object_name] = table_count(cursor, object_name)
    procedures = [
        row[0]
        for row in cursor.execute(
            """
            SELECT s.name + '.' + p.name
            FROM sys.procedures p
            INNER JOIN sys.schemas s ON s.schema_id = p.schema_id
            WHERE s.name IN ('dbo','etl')
              AND p.name IN ('sp_process_formulario_stage','sp_start_formulario_batch','sp_seed_static_catalogs')
            ORDER BY 1
            """
        ).fetchall()
    ]
    return counts, procedures


def validate_header_df(header_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if header_df.empty:
        return header_df.copy(), header_df.copy()

    validation = pd.Series(True, index=header_df.index)
    validation &= header_df["es_completo"].astype(int).eq(1)
    validation &= header_df["cant_muestra"].astype(int).gt(0)
    validation &= header_df["suma_defectos"].astype(int).ge(0)
    validation &= header_df["fruta_sana"].astype(int).ge(0)
    validation &= header_df["choice"].astype(int).ge(0)
    validation &= header_df["fruta_comercial"].astype(int).eq(header_df["suma_defectos"].astype(int))
    validation &= (
        header_df["fruta_sana"].astype(int)
        + header_df["choice"].astype(int)
        + header_df["suma_defectos"].astype(int)
    ).eq(header_df["cant_muestra"].astype(int))

    return header_df[validation].copy(), header_df[~validation].copy()


def build_payload(fecha_operacional: str | None, batch_id: str, source_run_id: str):
    raw_header_df = build_header_df(
        fecha_operacional,
        solo_completos=True,
        batch_id=batch_id,
        source_run_id=source_run_id,
        include_etl_metadata=True,
    )
    raw_defect_df = build_defect_df(
        fecha_operacional,
        solo_completos=True,
        batch_id=batch_id,
        source_run_id=source_run_id,
        include_etl_metadata=True,
    )

    valid_header_df, rejected_header_df = validate_header_df(raw_header_df)
    valid_keys = set(
        zip(
            valid_header_df.get("source_system", pd.Series(dtype=str)),
            valid_header_df.get("source_business_key", pd.Series(dtype=str)),
        )
    )
    if raw_defect_df.empty:
        valid_defect_df = raw_defect_df.copy()
    else:
        valid_defect_df = raw_defect_df[
            raw_defect_df.apply(
                lambda row: (row["source_system"], row["source_business_key"]) in valid_keys,
                axis=1,
            )
        ].copy()

    return raw_header_df, raw_defect_df, valid_header_df, valid_defect_df, rejected_header_df


def none_if_na(value):
    if value is pd.NA or value is pd.NaT:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    return value


def parse_date_value(value):
    value = none_if_na(value)
    if value is None or isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value)[:10])


def parse_datetime_value(value):
    value = none_if_na(value)
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    elif not isinstance(value, datetime):
        value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if value.tzinfo is not None:
        return value.replace(tzinfo=None)
    return value


def scalar_for_sql(column: str, value):
    value = none_if_na(value)
    if column in {"fecha", "fecha_operacional"}:
        return parse_date_value(value)
    if column in {"created_at", "updated_at"}:
        return parse_datetime_value(value)
    if column in {"centro_sin_definir", "es_completo"}:
        return int(value or 0)
    if column in {
        "source_record_id",
        "cant_muestra",
        "suma_defectos",
        "fruta_comercial",
        "fruta_sana",
        "choice",
        "porc_export_manual",
        "cantidad",
    }:
        return None if value is None else int(value)
    if column in {
        "porc_exportable",
        "porc_embalable",
        "porc_choice",
        "porc_descartable",
        "velocidad_kgh",
        "velocidad_manual",
    }:
        return None if value is None else float(value)
    return value


def rows_for_sql(df: pd.DataFrame, columns: list[str]) -> list[tuple]:
    rows = []
    for record in df[columns].to_dict("records"):
        rows.append(tuple(scalar_for_sql(column, record.get(column)) for column in columns))
    return rows


def merge_header_sql():
    source_cols = ", ".join(f"? AS {column}" for column in HEADER_STAGE_COLUMNS)
    update_cols = [column for column in HEADER_STAGE_COLUMNS if column not in {"source_system", "source_business_key"}]
    update_set = ",\n            ".join(f"tgt.{column} = src.{column}" for column in update_cols)
    insert_cols = ", ".join(HEADER_STAGE_COLUMNS)
    insert_values = ", ".join(f"src.{column}" for column in HEADER_STAGE_COLUMNS)
    return f"""
        MERGE stg.FormularioHeader AS tgt
        USING (SELECT {source_cols}) AS src
            ON tgt.source_system = src.source_system
           AND tgt.source_business_key = src.source_business_key
        WHEN MATCHED THEN
            UPDATE SET
            {update_set},
            tgt.dw_loaded_at = NULL,
            tgt.rejected_at = NULL,
            tgt.reject_reason = NULL
        WHEN NOT MATCHED THEN
            INSERT ({insert_cols})
            VALUES ({insert_values});
    """


def merge_defect_sql():
    source_cols = ", ".join(f"? AS {column}" for column in DEFECT_STAGE_COLUMNS)
    update_cols = [column for column in DEFECT_STAGE_COLUMNS if column not in {"source_system", "source_business_key", "codigo_defecto"}]
    update_set = ",\n            ".join(f"tgt.{column} = src.{column}" for column in update_cols)
    insert_cols = ", ".join(DEFECT_STAGE_COLUMNS)
    insert_values = ", ".join(f"src.{column}" for column in DEFECT_STAGE_COLUMNS)
    return f"""
        MERGE stg.FormularioDefecto AS tgt
        USING (SELECT {source_cols}) AS src
            ON tgt.source_system = src.source_system
           AND tgt.source_business_key = src.source_business_key
           AND tgt.codigo_defecto = src.codigo_defecto
        WHEN MATCHED THEN
            UPDATE SET
            {update_set},
            tgt.dw_loaded_at = NULL,
            tgt.rejected_at = NULL,
            tgt.reject_reason = NULL
        WHEN NOT MATCHED THEN
            INSERT ({insert_cols})
            VALUES ({insert_values});
    """


def execute_many_merges(cursor, sql: str, rows: list[tuple]):
    for row in rows:
        cursor.execute(sql, row)


def start_batch(conn, source_run_id: str, source_system: str, notes: str) -> str:
    cursor = conn.cursor()
    cursor.execute(
        """
        DECLARE @batch_id UNIQUEIDENTIFIER;
        EXEC etl.sp_start_formulario_batch
            @source_run_id = ?,
            @source_system = ?,
            @notes = ?,
            @batch_id = @batch_id OUTPUT;
        SELECT @batch_id AS batch_id;
        """,
        source_run_id,
        source_system,
        notes,
    )
    batch_id = None
    while True:
        if cursor.description:
            row = cursor.fetchone()
            if row and getattr(row, "batch_id", None):
                batch_id = str(row.batch_id)
        if not cursor.nextset():
            break
    conn.commit()
    if not batch_id:
        raise RuntimeError("No fue posible obtener batch_id desde etl.sp_start_formulario_batch.")
    return batch_id


def process_stage(conn):
    cursor = conn.cursor()
    cursor.execute("EXEC dbo.sp_process_formulario_stage")
    while cursor.nextset():
        pass
    conn.commit()


def mark_batch_received(conn, batch_id: str, header_count: int, defect_count: int):
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE etl.BatchControl
        SET header_received_count = ?,
            defect_received_count = ?,
            last_updated_at = SYSUTCDATETIME()
        WHERE batch_id = ?
        """,
        header_count,
        defect_count,
        batch_id,
    )
    conn.commit()


def load_staging(conn, header_df: pd.DataFrame, defect_df: pd.DataFrame):
    cursor = conn.cursor()
    header_rows = rows_for_sql(header_df, HEADER_STAGE_COLUMNS)
    defect_rows = rows_for_sql(defect_df, DEFECT_STAGE_COLUMNS)

    execute_many_merges(cursor, merge_header_sql(), header_rows)
    for source_system, source_business_key in header_df[["source_system", "source_business_key"]].itertuples(index=False):
        cursor.execute(
            """
            DELETE FROM stg.FormularioDefecto
            WHERE source_system = ?
              AND source_business_key = ?
            """,
            source_system,
            source_business_key,
        )
    execute_many_merges(cursor, merge_defect_sql(), defect_rows)
    conn.commit()
    return len(header_rows), len(defect_rows)


def fetch_batch_summary(conn, batch_id: str, source_run_id: str):
    cursor = conn.cursor()
    summary = {}
    for object_name in [
        "stg.FormularioHeader",
        "stg.FormularioDefecto",
        "dbo.FactFormulario",
        "dbo.FactFormularioDefecto",
        "etl.RechazoFormularioHeader",
        "etl.RechazoFormularioDefecto",
    ]:
        if not object_exists(cursor, object_name):
            summary[object_name] = None
            continue
        schema, table = object_name.split(".")
        if object_name.startswith("dbo.Fact"):
            if table == "FactFormularioDefecto":
                summary[object_name] = int(
                    cursor.execute(
                        """
                        SELECT COUNT(*)
                        FROM dbo.FactFormularioDefecto fd
                        INNER JOIN dbo.FactFormulario f
                            ON f.formulario_key = fd.formulario_key
                        INNER JOIN stg.FormularioHeader h
                            ON h.source_system = f.source_system
                           AND h.source_business_key = f.source_business_key
                        WHERE h.batch_id = ? OR h.source_run_id = ?
                        """,
                        batch_id,
                        source_run_id,
                    ).fetchval()
                )
            else:
                summary[object_name] = int(
                    cursor.execute(
                        """
                        SELECT COUNT(*)
                        FROM dbo.FactFormulario f
                        INNER JOIN stg.FormularioHeader h
                            ON h.source_system = f.source_system
                           AND h.source_business_key = f.source_business_key
                        WHERE h.batch_id = ? OR h.source_run_id = ?
                        """,
                        batch_id,
                        source_run_id,
                    ).fetchval()
                )
        else:
            summary[object_name] = int(
                cursor.execute(
                    f"SELECT COUNT(*) FROM {schema}.{table} WHERE batch_id = ? OR source_run_id = ?",
                    batch_id,
                    source_run_id,
                ).fetchval()
            )
    batch = None
    if object_exists(cursor, "etl.BatchControl"):
        row = cursor.execute(
            """
            SELECT status, header_received_count, header_loaded_count, header_rejected_count,
                   defect_received_count, defect_loaded_count, defect_rejected_count,
                   started_at, completed_at
            FROM etl.BatchControl
            WHERE batch_id = ?
            """,
            batch_id,
        ).fetchone()
        if row:
            batch = {
                "status": row.status,
                "header_received_count": row.header_received_count,
                "header_loaded_count": row.header_loaded_count,
                "header_rejected_count": row.header_rejected_count,
                "defect_received_count": row.defect_received_count,
                "defect_loaded_count": row.defect_loaded_count,
                "defect_rejected_count": row.defect_rejected_count,
                "started_at": row.started_at,
                "completed_at": row.completed_at,
            }
    return summary, batch


def print_counts(title: str, counts: dict[str, int | None]):
    print(f"\n{title}")
    for name, count in counts.items():
        value = "MISSING" if count is None else str(count)
        print(f"- {name}: {value}")


def main():
    args = parse_args()
    enforce_database_guard(args.target_database, args.dry_run, args.confirm_dev_load)
    enforce_source_guard(args.dry_run)

    source_run_id = args.source_run_id or f"formfruta_prod_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    planned_batch_id = str(uuid4())
    cfg = load_azure_sql_config(args.target_database)

    print("Destino Azure SQL validado")
    print(f"- server: {cfg['server']}")
    print(f"- database: {cfg['database']}")
    print(f"- dry_run: {args.dry_run}")
    print(f"- prepare_dw: {args.prepare_dw}")
    print(f"- source_system: {get_source_system()}")
    print(f"- source_root: {ROOT}")
    print(f"- source_run_id: {source_run_id}")

    (
        raw_header_df,
        raw_defect_df,
        valid_header_df,
        valid_defect_df,
        rejected_header_df,
    ) = build_payload(args.fecha_operacional, planned_batch_id, source_run_id)

    print("\nPayload SQLite")
    print(f"- formularios completos leidos: {len(raw_header_df)}")
    print(f"- defectos leidos: {len(raw_defect_df)}")
    print(f"- formularios validos para staging: {len(valid_header_df)}")
    print(f"- defectos validos para staging: {len(valid_defect_df)}")
    print(f"- formularios excluidos por contrato local: {len(rejected_header_df)}")

    if not rejected_header_df.empty:
        print("\nFormularios excluidos localmente")
        for row in rejected_header_df[["source_record_id", "source_business_key", "lote"]].to_dict("records"):
            print(f"- id={row['source_record_id']} key={row['source_business_key']} lote={row['lote']}")

    conn_str = build_connection_string(cfg)
    with pyodbc.connect(conn_str) as conn:
        before_counts, procedures = fetch_metadata_counts(conn)
        print_counts("Conteos pre-carga", before_counts)
        print("\nProcedimientos existentes")
        print("- " + (", ".join(procedures) if procedures else "ninguno"))

        if args.dry_run:
            if args.prepare_dw:
                print("\nDry-run: se omitio preparacion DW; en carga real se ejecutarian los DDL idempotentes y seed estatico.")
            missing = [name for name, count in before_counts.items() if count is None]
            if missing:
                print("\nObjetos faltantes que --prepare-dw debe crear")
                for name in missing:
                    print(f"- {name}")
            print("\nDry-run completado sin escrituras en Azure SQL.")
            return

        if args.prepare_dw:
            ref_batches, phase1_batches = execute_prepare_dw(conn)
            print("\nDW preparado")
            print(f"- {REFRACTORED_DDL.name}: {ref_batches} batches")
            print(f"- {PHASE1_DDL.name}: {phase1_batches} batches")
            print("- dbo.sp_seed_static_catalogs: OK")

        after_prepare_counts, after_prepare_procedures = fetch_metadata_counts(conn)
        print_counts("Conteos despues de preparar DW", after_prepare_counts)
        print("\nProcedimientos despues de preparar DW")
        print("- " + (", ".join(after_prepare_procedures) if after_prepare_procedures else "ninguno"))

        missing_after_prepare = [name for name, count in after_prepare_counts.items() if count is None]
        if missing_after_prepare:
            raise RuntimeError("Faltan objetos requeridos despues de preparar DW: " + ", ".join(missing_after_prepare))

        if valid_header_df.empty:
            print("\nNo hay formularios validos para cargar. No se abrio batch ETL.")
            return

        batch_id = start_batch(
            conn,
            source_run_id=source_run_id,
            source_system=get_source_system(),
            notes="Carga controlada desde SQLite OL9 hacia DEV_ddc_datawarehouse",
        )
        valid_header_df["batch_id"] = batch_id
        valid_defect_df["batch_id"] = batch_id

        header_loaded, defect_loaded = load_staging(conn, valid_header_df, valid_defect_df)
        mark_batch_received(conn, batch_id, header_loaded, defect_loaded)
        process_stage(conn)

        final_counts, _ = fetch_metadata_counts(conn)
        print_counts("Conteos post-carga", final_counts)
        batch_summary, batch_control = fetch_batch_summary(conn, batch_id, source_run_id)
        print_counts("Conteos del batch/source_run", batch_summary)
        if batch_control:
            print("\nBatchControl")
            for key, value in batch_control.items():
                print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
