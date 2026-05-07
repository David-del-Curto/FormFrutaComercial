import json
import os
from datetime import datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pandas as pd

from core.business_rules import obtener_reglas_centro
from services.cache_sqlite import get_conn


TIMEZONE = ZoneInfo("America/Santiago")
DEFAULT_SOURCE_SYSTEM = "streamlit_form_fruta_comercial"
SOURCE_SYSTEM_ENV_VAR = "FORM_FRUTA_SOURCE_SYSTEM"
TURNO_1_INICIO = time(7, 0)
TURNO_1_FIN = time(17, 0)
TURNO_2_FIN = time(2, 0)
RANGO_TURNO_1 = "07:00-17:00"
RANGO_TURNO_2 = "17:00-02:00"


def get_source_system() -> str:
    source_system = str(os.getenv(SOURCE_SYSTEM_ENV_VAR, DEFAULT_SOURCE_SYSTEM) or "").strip()
    return source_system or DEFAULT_SOURCE_SYSTEM


def generate_source_business_key() -> str:
    return str(uuid4())


def _resolve_source_identity(payload, existing=None) -> tuple[str, str]:
    existing = existing or {}

    source_system = str(
        existing.get("source_system")
        or payload.get("source_system")
        or get_source_system()
    ).strip()

    source_business_key = str(
        existing.get("source_business_key")
        or payload.get("source_business_key")
        or generate_source_business_key()
    ).strip()

    if not source_system:
        source_system = get_source_system()

    if not source_business_key:
        source_business_key = generate_source_business_key()

    return source_system, source_business_key


REGISTRO_COLUMN_DEFS = {
    "id_registro": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "source_system": f"TEXT NOT NULL DEFAULT '{DEFAULT_SOURCE_SYSTEM}'",
    "source_business_key": "TEXT",
    "fecha": "TEXT NOT NULL",
    "linea": "TEXT NOT NULL",
    "especie": "TEXT NOT NULL",
    "variedad": "TEXT NOT NULL",
    "lote": "TEXT NOT NULL",
    "centro_codigo": "TEXT",
    "centro_nombre": "TEXT",
    "centro_display": "TEXT",
    "productor_codigo": "TEXT",
    "productor_nombre": "TEXT",
    "productor_display": "TEXT",
    "cant_muestra": "INTEGER NOT NULL DEFAULT 0",
    "suma_defectos": "INTEGER NOT NULL DEFAULT 0",
    "fruta_comercial": "INTEGER NOT NULL DEFAULT 0",
    "fruta_sana": "INTEGER NOT NULL DEFAULT 0",
    "choice": "INTEGER NOT NULL DEFAULT 0",
    "porc_exportable": "REAL NOT NULL DEFAULT 0",
    "porc_embalable": "REAL NOT NULL DEFAULT 0",
    "porc_choice": "REAL NOT NULL DEFAULT 0",
    "porc_descartable": "REAL NOT NULL DEFAULT 0",
    "porc_export_manual": "INTEGER",
    "velocidad_kgh": "REAL",
    "kg_ultima_hora": "INTEGER",
    "velocidad_manual": "REAL",
    "lugar_codigo": "TEXT",
    "lugar_nombre": "TEXT",
    "observaciones": "TEXT",
    "verificador": "TEXT",
    "centro_sin_definir": "INTEGER NOT NULL DEFAULT 0",
    "estado_formulario": "TEXT NOT NULL DEFAULT 'borrador'",
    "es_completo": "INTEGER NOT NULL DEFAULT 0",
    "campos_pendientes": "TEXT",
    "fecha_operacional": "TEXT NOT NULL",
    "turno_codigo": "TEXT NOT NULL",
    "turno_nombre": "TEXT NOT NULL",
    "rango_turno": "TEXT NOT NULL",
    "created_at": "TEXT NOT NULL",
    "updated_at": "TEXT NOT NULL"
}


REGISTRO_DEFECTOS_COLUMN_DEFS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "id_registro": "INTEGER NOT NULL",
    "codigo_defecto": "TEXT NOT NULL",
    "nombre_defecto": "TEXT",
    "cantidad": "INTEGER NOT NULL DEFAULT 0",
    "created_at": "TEXT NOT NULL",
    "updated_at": "TEXT NOT NULL"
}


OPERACION_DISPATCH_LOG_COLUMN_DEFS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "dispatch_kind": "TEXT NOT NULL",
    "fecha_operacional": "TEXT NOT NULL",
    "target_key": "TEXT NOT NULL DEFAULT ''",
    "schedule_key": "TEXT NOT NULL DEFAULT ''",
    "recipients": "TEXT",
    "metadata_json": "TEXT",
    "sent_at": "TEXT NOT NULL",
}


OPERACION_ALERT_STATE_COLUMN_DEFS = {
    "alert_code": "TEXT NOT NULL",
    "fecha_operacional": "TEXT NOT NULL",
    "target_key": "TEXT NOT NULL",
    "is_active": "INTEGER NOT NULL DEFAULT 0",
    "last_value": "REAL NOT NULL DEFAULT 0",
    "activated_at": "TEXT",
    "recovered_at": "TEXT",
    "updated_at": "TEXT NOT NULL",
}


def get_local_now() -> datetime:
    return datetime.now(TIMEZONE)


def get_current_operational_date() -> str:
    return calcular_contexto_operacional()["fecha_operacional"]


def calcular_contexto_operacional(reference_dt: datetime | None = None):
    dt = reference_dt or get_local_now()

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TIMEZONE)
    else:
        dt = dt.astimezone(TIMEZONE)

    hora_actual = dt.time()
    fecha_operacional = dt.date()
    if hora_actual <= TURNO_2_FIN:
        fecha_operacional = fecha_operacional - timedelta(days=1)

    if TURNO_1_INICIO <= hora_actual < TURNO_1_FIN:
        turno_codigo = "T1"
        turno_nombre = "Turno 1"
        rango_turno = RANGO_TURNO_1
    elif hora_actual >= TURNO_1_FIN or hora_actual <= TURNO_2_FIN:
        turno_codigo = "T2"
        turno_nombre = "Turno 2"
        rango_turno = RANGO_TURNO_2
    else:
        # 02:01-06:59 queda etiquetado como Turno 1 para mantener solo dos turnos.
        turno_codigo = "T1"
        turno_nombre = "Turno 1"
        rango_turno = RANGO_TURNO_1

    return {
        "fecha_operacional": fecha_operacional.isoformat(),
        "turno_codigo": turno_codigo,
        "turno_nombre": turno_nombre,
        "rango_turno": rango_turno,
        "timestamp": dt.isoformat(timespec="seconds"),
        "hora_bucket": dt.strftime("%H:00"),
    }


def evaluar_estado_formulario(payload):
    campos_pendientes = []
    reglas_centro = obtener_reglas_centro(
        {
            "CodCentro_SAP": payload.get("centro_codigo"),
            "Centro_Logistico": "[sin definir]" if payload.get("centro_sin_definir") else "",
        }
    )

    if reglas_centro["requiere_velocidad_kgh"] and float(payload.get("velocidad_kgh") or 0) <= 0:
        campos_pendientes.append("Velocidad Kg/h")

    if reglas_centro["requiere_velocidad_tercero"] and float(payload.get("velocidad_manual") or 0) <= 0:
        campos_pendientes.append("Velocidad Tercero Kg/h")

    if reglas_centro["requiere_export_manual"] and int(payload.get("porc_export_manual") or 0) <= 0:
        campos_pendientes.append("% Exportable manual")

    es_completo = int(len(campos_pendientes) == 0)
    estado_formulario = "completo" if es_completo else "borrador"

    return {
        "estado_formulario": estado_formulario,
        "es_completo": es_completo,
        "campos_pendientes": ", ".join(campos_pendientes),
    }


def _ensure_columns(conn, table_name: str, column_defs: dict[str, str]):
    existing = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }

    for column_name, column_def in column_defs.items():
        if column_name in existing:
            continue

        conn.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"
        )


def _ensure_registro_source_identity(conn):
    conn.execute(
        """
        UPDATE registro
        SET source_system = ?
        WHERE COALESCE(NULLIF(TRIM(source_system), ''), '') = ''
        """,
        (get_source_system(),)
    )

    rows = conn.execute(
        """
        SELECT id_registro
        FROM registro
        WHERE COALESCE(NULLIF(TRIM(source_business_key), ''), '') = ''
        """
    ).fetchall()

    for row in rows:
        conn.execute(
            """
            UPDATE registro
            SET source_business_key = ?
            WHERE id_registro = ?
            """,
            (generate_source_business_key(), int(row["id_registro"]))
        )

    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_registro_source_identity
        ON registro(source_system, source_business_key)
        """
    )


def init_local_store():
    conn = get_conn()

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS registro (
            id_registro INTEGER PRIMARY KEY AUTOINCREMENT,
            source_system TEXT NOT NULL DEFAULT 'streamlit_form_fruta_comercial',
            source_business_key TEXT NOT NULL,
            fecha TEXT NOT NULL,
            linea TEXT NOT NULL,
            especie TEXT NOT NULL,
            variedad TEXT NOT NULL,
            lote TEXT NOT NULL,
            centro_codigo TEXT,
            centro_nombre TEXT,
            centro_display TEXT,
            productor_codigo TEXT,
            productor_nombre TEXT,
            productor_display TEXT,
            cant_muestra INTEGER NOT NULL DEFAULT 0,
            suma_defectos INTEGER NOT NULL DEFAULT 0,
            fruta_comercial INTEGER NOT NULL DEFAULT 0,
            fruta_sana INTEGER NOT NULL DEFAULT 0,
            choice INTEGER NOT NULL DEFAULT 0,
            porc_exportable REAL NOT NULL DEFAULT 0,
            porc_embalable REAL NOT NULL DEFAULT 0,
            porc_choice REAL NOT NULL DEFAULT 0,
            porc_descartable REAL NOT NULL DEFAULT 0,
            porc_export_manual INTEGER,
            velocidad_kgh REAL,
            kg_ultima_hora INTEGER,
            velocidad_manual REAL,
            lugar_codigo TEXT,
            lugar_nombre TEXT,
            observaciones TEXT,
            verificador TEXT,
            centro_sin_definir INTEGER NOT NULL DEFAULT 0,
            estado_formulario TEXT NOT NULL DEFAULT 'borrador',
            es_completo INTEGER NOT NULL DEFAULT 0,
            campos_pendientes TEXT,
            fecha_operacional TEXT NOT NULL,
            turno_codigo TEXT NOT NULL,
            turno_nombre TEXT NOT NULL,
            rango_turno TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS registro_defectos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_registro INTEGER NOT NULL,
            codigo_defecto TEXT NOT NULL,
            nombre_defecto TEXT,
            cantidad INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS operacion_dispatch_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dispatch_kind TEXT NOT NULL,
            fecha_operacional TEXT NOT NULL,
            target_key TEXT NOT NULL DEFAULT '',
            schedule_key TEXT NOT NULL DEFAULT '',
            recipients TEXT,
            metadata_json TEXT,
            sent_at TEXT NOT NULL,
            UNIQUE (dispatch_kind, fecha_operacional, target_key, schedule_key)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS operacion_alert_state (
            alert_code TEXT NOT NULL,
            fecha_operacional TEXT NOT NULL,
            target_key TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 0,
            last_value REAL NOT NULL DEFAULT 0,
            activated_at TEXT,
            recovered_at TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (alert_code, fecha_operacional, target_key)
        )
        """
    )

    _ensure_columns(conn, "registro", REGISTRO_COLUMN_DEFS)
    _ensure_columns(conn, "registro_defectos", REGISTRO_DEFECTOS_COLUMN_DEFS)
    _ensure_columns(conn, "operacion_dispatch_log", OPERACION_DISPATCH_LOG_COLUMN_DEFS)
    _ensure_columns(conn, "operacion_alert_state", OPERACION_ALERT_STATE_COLUMN_DEFS)
    _ensure_registro_source_identity(conn)

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_registro_fecha_operacional ON registro(fecha_operacional)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_registro_estado ON registro(estado_formulario)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_registro_updated_at ON registro(updated_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_registro_defectos_registro ON registro_defectos(id_registro)"
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_operacion_dispatch_lookup
        ON operacion_dispatch_log(dispatch_kind, fecha_operacional, target_key, schedule_key)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_operacion_alert_state_lookup
        ON operacion_alert_state(alert_code, fecha_operacional, target_key)
        """
    )

    conn.commit()
    conn.close()


def _fetch_record(conn, record_id: int):
    row = conn.execute(
        "SELECT * FROM registro WHERE id_registro = ?",
        (record_id,)
    ).fetchone()

    return dict(row) if row is not None else None


def save_formulario_local(payload, defectos, record_id: int | None = None):
    init_local_store()

    contexto = calcular_contexto_operacional()
    payload = dict(payload)
    reglas_centro = obtener_reglas_centro(
        {
            "CodCentro_SAP": payload.get("centro_codigo"),
            "Centro_Logistico": payload.get("centro_nombre")
            or ("[sin definir]" if payload.get("centro_sin_definir") else ""),
        }
    )

    if not reglas_centro["usa_velocidad_tercero"]:
        payload["velocidad_manual"] = 0.0

    if not reglas_centro["requiere_export_manual"]:
        payload["porc_export_manual"] = 0

    payload["centro_sin_definir"] = int(reglas_centro["centro_sin_definir"])

    estado = evaluar_estado_formulario(payload)
    timestamp = contexto["timestamp"]
    conn = get_conn()
    existing = None

    if record_id is not None:
        existing = _fetch_record(conn, record_id)
        if existing is None:
            conn.close()
            raise ValueError(f"No existe el registro local con id {record_id}.")

        if int(existing.get("es_completo") or 0) == 1:
            conn.close()
            raise ValueError(f"El registro local #{record_id} ya está completo y no puede editarse.")

    source_system, source_business_key = _resolve_source_identity(payload, existing)

    registro = {
        "source_system": source_system,
        "source_business_key": source_business_key,
        "fecha": payload["fecha"],
        "linea": payload["linea"],
        "especie": payload["especie"],
        "variedad": payload["variedad"],
        "lote": payload["lote"],
        "centro_codigo": payload.get("centro_codigo"),
        "centro_nombre": payload.get("centro_nombre"),
        "centro_display": payload.get("centro_display"),
        "productor_codigo": payload.get("productor_codigo"),
        "productor_nombre": payload.get("productor_nombre"),
        "productor_display": payload.get("productor_display"),
        "cant_muestra": int(payload["cant_muestra"]),
        "suma_defectos": int(payload["suma_defectos"]),
        "fruta_comercial": int(payload["fruta_comercial"]),
        "fruta_sana": int(payload["fruta_sana"]),
        "choice": int(payload["choice"]),
        "porc_exportable": float(payload["porc_exportable"]),
        "porc_embalable": float(payload["porc_embalable"]),
        "porc_choice": float(payload["porc_choice"]),
        "porc_descartable": float(payload["porc_descartable"]),
        "porc_export_manual": int(payload["porc_export_manual"]),
        "velocidad_kgh": float(payload["velocidad_kgh"]),
        "kg_ultima_hora": int(payload.get("kg_ultima_hora")),
        "velocidad_manual": float(payload["velocidad_manual"]),
        "lugar_codigo": payload["lugar_codigo"],
        "lugar_nombre": payload["lugar_nombre"],
        "observaciones": payload["observaciones"],
        "verificador": payload["verificador"],
        "centro_sin_definir": int(payload["centro_sin_definir"]),
        "estado_formulario": estado["estado_formulario"],
        "es_completo": estado["es_completo"],
        "campos_pendientes": estado["campos_pendientes"],
        "fecha_operacional": contexto["fecha_operacional"],
        "turno_codigo": contexto["turno_codigo"],
        "turno_nombre": contexto["turno_nombre"],
        "rango_turno": contexto["rango_turno"],
        "updated_at": timestamp,
    }

    if record_id is None:
        registro["created_at"] = timestamp
        cursor = conn.execute(
            """
            INSERT INTO registro (
                source_system,
                source_business_key,
                fecha,
                linea,
                especie,
                variedad,
                lote,
                centro_codigo,
                centro_nombre,
                centro_display,
                productor_codigo,
                productor_nombre,
                productor_display,
                cant_muestra,
                suma_defectos,
                fruta_comercial,
                fruta_sana,
                choice,
                porc_exportable,
                porc_embalable,
                porc_choice,
                porc_descartable,
                porc_export_manual,
                velocidad_kgh,
                kg_ultima_hora,
                velocidad_manual,
                lugar_codigo,
                lugar_nombre,
                observaciones,
                verificador,
                centro_sin_definir,
                estado_formulario,
                es_completo,
                campos_pendientes,
                fecha_operacional,
                turno_codigo,
                turno_nombre,
                rango_turno,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                registro["source_system"],
                registro["source_business_key"],
                registro["fecha"],
                registro["linea"],
                registro["especie"],
                registro["variedad"],
                registro["lote"],
                registro["centro_codigo"],
                registro["centro_nombre"],
                registro["centro_display"],
                registro["productor_codigo"],
                registro["productor_nombre"],
                registro["productor_display"],
                registro["cant_muestra"],
                registro["suma_defectos"],
                registro["fruta_comercial"],
                registro["fruta_sana"],
                registro["choice"],
                registro["porc_exportable"],
                registro["porc_embalable"],
                registro["porc_choice"],
                registro["porc_descartable"],
                registro["porc_export_manual"],
                registro["velocidad_kgh"],
                registro["kg_ultima_hora"],
                registro["velocidad_manual"],
                registro["lugar_codigo"],
                registro["lugar_nombre"],
                registro["observaciones"],
                registro["verificador"],
                registro["centro_sin_definir"],
                registro["estado_formulario"],
                registro["es_completo"],
                registro["campos_pendientes"],
                registro["fecha_operacional"],
                registro["turno_codigo"],
                registro["turno_nombre"],
                registro["rango_turno"],
                registro["created_at"],
                registro["updated_at"],
            )
        )
        record_id = int(cursor.lastrowid)
    else:
        registro["fecha_operacional"] = existing["fecha_operacional"]
        registro["turno_codigo"] = existing["turno_codigo"]
        registro["turno_nombre"] = existing["turno_nombre"]
        registro["rango_turno"] = existing["rango_turno"]

        conn.execute(
            """
            UPDATE registro
            SET source_system = ?,
                source_business_key = ?,
                fecha = ?,
                linea = ?,
                especie = ?,
                variedad = ?,
                lote = ?,
                centro_codigo = ?,
                centro_nombre = ?,
                centro_display = ?,
                productor_codigo = ?,
                productor_nombre = ?,
                productor_display = ?,
                cant_muestra = ?,
                suma_defectos = ?,
                fruta_comercial = ?,
                fruta_sana = ?,
                choice = ?,
                porc_exportable = ?,
                porc_embalable = ?,
                porc_choice = ?,
                porc_descartable = ?,
                porc_export_manual = ?,
                velocidad_kgh = ?,
                kg_ultima_hora = ?,
                velocidad_manual = ?,
                lugar_codigo = ?,
                lugar_nombre = ?,
                observaciones = ?,
                verificador = ?,
                centro_sin_definir = ?,
                estado_formulario = ?,
                es_completo = ?,
                campos_pendientes = ?,
                fecha_operacional = ?,
                turno_codigo = ?,
                turno_nombre = ?,
                rango_turno = ?,
                updated_at = ?
            WHERE id_registro = ?
            """,
            (
                registro["source_system"],
                registro["source_business_key"],
                registro["fecha"],
                registro["linea"],
                registro["especie"],
                registro["variedad"],
                registro["lote"],
                registro["centro_codigo"],
                registro["centro_nombre"],
                registro["centro_display"],
                registro["productor_codigo"],
                registro["productor_nombre"],
                registro["productor_display"],
                registro["cant_muestra"],
                registro["suma_defectos"],
                registro["fruta_comercial"],
                registro["fruta_sana"],
                registro["choice"],
                registro["porc_exportable"],
                registro["porc_embalable"],
                registro["porc_choice"],
                registro["porc_descartable"],
                registro["porc_export_manual"],
                registro["velocidad_kgh"],
                registro["kg_ultima_hora"],
                registro["velocidad_manual"],
                registro["lugar_codigo"],
                registro["lugar_nombre"],
                registro["observaciones"],
                registro["verificador"],
                registro["centro_sin_definir"],
                registro["estado_formulario"],
                registro["es_completo"],
                registro["campos_pendientes"],
                registro["fecha_operacional"],
                registro["turno_codigo"],
                registro["turno_nombre"],
                registro["rango_turno"],
                registro["updated_at"],
                record_id,
            )
        )
        conn.execute(
            "DELETE FROM registro_defectos WHERE id_registro = ?",
            (record_id,)
        )

    for codigo_defecto, cantidad in defectos.items():
        if int(cantidad) <= 0:
            continue

        conn.execute(
            """
            INSERT INTO registro_defectos (
                id_registro,
                codigo_defecto,
                nombre_defecto,
                cantidad,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                codigo_defecto,
                payload["defectos_nombres"].get(codigo_defecto, codigo_defecto),
                int(cantidad),
                timestamp,
                timestamp,
            )
        )

    conn.commit()
    conn.close()

    return {
        "id_registro": record_id,
        "source_system": registro["source_system"],
        "source_business_key": registro["source_business_key"],
        "estado_formulario": estado["estado_formulario"],
        "es_completo": estado["es_completo"],
        "campos_pendientes": estado["campos_pendientes"],
    }


def get_registro(record_id: int):
    init_local_store()
    conn = get_conn()
    row = _fetch_record(conn, record_id)
    conn.close()
    return row


def get_registro_defectos(record_id: int):
    init_local_store()
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT codigo_defecto, nombre_defecto, cantidad
        FROM registro_defectos
        WHERE id_registro = ?
        ORDER BY codigo_defecto
        """,
        (record_id,)
    ).fetchall()
    conn.close()

    return [dict(row) for row in rows]


def list_recent_registros(limit: int = 100, fecha_operacional: str | None = None):
    init_local_store()
    conn = get_conn()

    if fecha_operacional:
        rows = conn.execute(
            """
            SELECT *
            FROM registro
            WHERE fecha_operacional = ?
            ORDER BY updated_at DESC, id_registro DESC
            LIMIT ?
            """,
            (fecha_operacional, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT *
            FROM registro
            ORDER BY updated_at DESC, id_registro DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()

    conn.close()
    return [dict(row) for row in rows]


def get_registros_df(fecha_operacional: str):
    init_local_store()
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT *
        FROM registro
        WHERE fecha_operacional = ?
        ORDER BY created_at ASC, id_registro ASC
        """,
        conn,
        params=(fecha_operacional,)
    )
    conn.close()
    return df


def get_defectos_df(fecha_operacional: str):
    init_local_store()
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT
            d.id_registro,
            d.codigo_defecto,
            COALESCE(d.nombre_defecto, d.codigo_defecto) AS nombre_defecto,
            d.cantidad,
            r.fecha_operacional,
            r.turno_codigo,
            r.turno_nombre,
            r.created_at,
            r.estado_formulario,
            r.es_completo
        FROM registro_defectos d
        INNER JOIN registro r
            ON r.id_registro = d.id_registro
        WHERE r.fecha_operacional = ?
        ORDER BY d.cantidad DESC, d.nombre_defecto ASC
        """,
        conn,
        params=(fecha_operacional,)
    )
    conn.close()
    return df


def get_registros_para_dw_df(
    fecha_operacional: str | None = None,
    solo_completos: bool = True,
):
    init_local_store()
    conn = get_conn()

    filtros = []
    params: list = []
    if fecha_operacional is not None:
        filtros.append("fecha_operacional = ?")
        params.append(fecha_operacional)
    if solo_completos:
        filtros.append("es_completo = 1")

    where_clause = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    query = f"""
        SELECT *
        FROM registro
        {where_clause}
        ORDER BY updated_at ASC, id_registro ASC
    """

    df = pd.read_sql_query(query, conn, params=tuple(params))
    conn.close()
    return df


def was_operacion_dispatch_sent(
    dispatch_kind: str,
    fecha_operacional: str,
    target_key: str = "",
    schedule_key: str = "",
) -> bool:
    init_local_store()
    conn = get_conn()
    row = conn.execute(
        """
        SELECT 1
        FROM operacion_dispatch_log
        WHERE dispatch_kind = ?
          AND fecha_operacional = ?
          AND target_key = ?
          AND schedule_key = ?
        LIMIT 1
        """,
        (dispatch_kind, fecha_operacional, target_key, schedule_key),
    ).fetchone()
    conn.close()
    return row is not None


def log_operacion_dispatch(
    dispatch_kind: str,
    fecha_operacional: str,
    target_key: str = "",
    schedule_key: str = "",
    recipients: list[str] | None = None,
    metadata: dict | None = None,
) -> bool:
    init_local_store()
    conn = get_conn()
    before_changes = conn.total_changes
    conn.execute(
        """
        INSERT OR IGNORE INTO operacion_dispatch_log (
            dispatch_kind,
            fecha_operacional,
            target_key,
            schedule_key,
            recipients,
            metadata_json,
            sent_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            dispatch_kind,
            fecha_operacional,
            target_key,
            schedule_key,
            json.dumps(recipients or [], ensure_ascii=True),
            json.dumps(metadata or {}, ensure_ascii=True, default=str),
            get_local_now().isoformat(timespec="seconds"),
        ),
    )
    inserted = conn.total_changes > before_changes
    conn.commit()
    conn.close()
    return inserted


def get_operacion_alert_state(alert_code: str, fecha_operacional: str, target_key: str) -> dict | None:
    init_local_store()
    conn = get_conn()
    row = conn.execute(
        """
        SELECT *
        FROM operacion_alert_state
        WHERE alert_code = ?
          AND fecha_operacional = ?
          AND target_key = ?
        """,
        (alert_code, fecha_operacional, target_key),
    ).fetchone()
    conn.close()
    return dict(row) if row is not None else None


def set_operacion_alert_state(
    alert_code: str,
    fecha_operacional: str,
    target_key: str,
    is_active: bool,
    last_value: float,
    activated_at: str | None = None,
    recovered_at: str | None = None,
):
    init_local_store()
    conn = get_conn()
    existing = conn.execute(
        """
        SELECT activated_at, recovered_at
        FROM operacion_alert_state
        WHERE alert_code = ?
          AND fecha_operacional = ?
          AND target_key = ?
        """,
        (alert_code, fecha_operacional, target_key),
    ).fetchone()

    timestamp = get_local_now().isoformat(timespec="seconds")
    activated_value = activated_at
    recovered_value = recovered_at

    if existing is not None:
        if activated_value is None:
            activated_value = existing["activated_at"]
        if recovered_value is None:
            recovered_value = existing["recovered_at"]

    conn.execute(
        """
        INSERT INTO operacion_alert_state (
            alert_code,
            fecha_operacional,
            target_key,
            is_active,
            last_value,
            activated_at,
            recovered_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(alert_code, fecha_operacional, target_key)
        DO UPDATE SET
            is_active = excluded.is_active,
            last_value = excluded.last_value,
            activated_at = excluded.activated_at,
            recovered_at = excluded.recovered_at,
            updated_at = excluded.updated_at
        """,
        (
            alert_code,
            fecha_operacional,
            target_key,
            int(bool(is_active)),
            float(last_value or 0.0),
            activated_value,
            recovered_value,
            timestamp,
        ),
    )
    conn.commit()
    conn.close()


def get_defectos_para_dw_df(
    fecha_operacional: str | None = None,
    solo_completos: bool = True,
):
    init_local_store()
    conn = get_conn()

    filtros = []
    params: list = []
    if fecha_operacional is not None:
        filtros.append("r.fecha_operacional = ?")
        params.append(fecha_operacional)
    if solo_completos:
        filtros.append("r.es_completo = 1")

    where_clause = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    query = f"""
        SELECT
            r.id_registro,
            r.source_system,
            r.source_business_key,
            r.fecha_operacional,
            r.updated_at,
            d.codigo_defecto,
            COALESCE(d.nombre_defecto, d.codigo_defecto) AS nombre_defecto,
            d.cantidad
        FROM registro_defectos d
        INNER JOIN registro r
            ON r.id_registro = d.id_registro
        {where_clause}
        ORDER BY r.updated_at ASC, r.id_registro ASC, d.codigo_defecto ASC
    """

    df = pd.read_sql_query(query, conn, params=tuple(params))
    conn.close()
    return df


def format_registro_option(registro) -> str:
    estado = (registro.get("estado_formulario") or "borrador").upper()
    turno = registro.get("turno_codigo") or "-"
    updated_at = (registro.get("updated_at") or "")[11:16]
    lote = registro.get("lote") or "-"
    especie = registro.get("especie") or "-"
    return f"#{registro['id_registro']} | {estado} | {turno} | {updated_at} | {especie} | Lote {lote}"
