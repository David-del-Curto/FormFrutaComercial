import hashlib
import json
import logging
import os
import urllib
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

from services.cache_sqlite import get_cache_entry, set_cache

try:
    import streamlit as _streamlit
except ImportError:  # pragma: no cover - usado en smoke tests sin Streamlit
    _streamlit = None

try:
    import tomllib
except ImportError:  # pragma: no cover - compatibilidad Python < 3.11
    import toml as tomllib


LOGGER = logging.getLogger(__name__)
SECRETS_PATH = Path(__file__).resolve().parent / ".streamlit" / "secrets.toml"
DEFAULT_DRIVER = "ODBC Driver 18 for SQL Server"
_CONNECTION_RUNTIME_EVENTS = []


class DatabaseConnectionError(RuntimeError):
    def __init__(self, message: str, diagnostic: dict, *, cache_available: bool = False):
        super().__init__(message)
        self.diagnostic = diagnostic
        self.cache_available = cache_available


def _cache_resource(func):
    if _streamlit is None:
        return func
    return _streamlit.cache_resource(func)


def _cache_data(func):
    if _streamlit is None:
        return func
    return _streamlit.cache_data(func)


def clear_connection_runtime_events():
    _CONNECTION_RUNTIME_EVENTS.clear()


def get_connection_runtime_events():
    return list(_CONNECTION_RUNTIME_EVENTS)


def _push_connection_runtime_event(event: dict):
    _CONNECTION_RUNTIME_EVENTS.append(event)


def _load_toml_secrets() -> dict:
    if not SECRETS_PATH.exists():
        return {}
    if hasattr(tomllib, "loads"):
        return tomllib.loads(SECRETS_PATH.read_text(encoding="utf-8"))
    with SECRETS_PATH.open("rb") as fh:
        return tomllib.load(fh)


def get_connection_settings() -> dict:
    settings = {}

    if _streamlit is not None:
        try:
            azure_sql = _streamlit.secrets["connections"]["azure_sql"]
            settings = {
                "server": str(azure_sql.get("server", "")),
                "database": str(azure_sql.get("database", "")),
                "username": str(azure_sql.get("username", "")),
                "password": str(azure_sql.get("password", "")),
                "driver": str(azure_sql.get("driver", DEFAULT_DRIVER)),
            }
        except Exception:
            settings = {}

    if not settings:
        secrets = _load_toml_secrets()
        azure_sql = secrets.get("connections", {}).get("azure_sql", {})
        settings = {
            "server": str(azure_sql.get("server", "")),
            "database": str(azure_sql.get("database", "")),
            "username": str(azure_sql.get("username", "")),
            "password": str(azure_sql.get("password", "")),
            "driver": str(azure_sql.get("driver", DEFAULT_DRIVER)),
        }

    return {
        "server": os.getenv("FORM_FRUTA_AZURE_SQL_SERVER") or settings.get("server", ""),
        "database": os.getenv("FORM_FRUTA_AZURE_SQL_DATABASE") or settings.get("database", ""),
        "username": os.getenv("FORM_FRUTA_AZURE_SQL_USERNAME") or settings.get("username", ""),
        "password": os.getenv("FORM_FRUTA_AZURE_SQL_PASSWORD") or settings.get("password", ""),
        "driver": os.getenv("FORM_FRUTA_AZURE_SQL_DRIVER") or settings.get("driver", DEFAULT_DRIVER) or DEFAULT_DRIVER,
    }


def classify_db_exception(exc: Exception) -> dict:
    raw_message = " ".join(str(exc).split())
    lower_message = raw_message.lower()

    if (
        "40615" in raw_message
        or "not allowed to access the server" in lower_message
        or "sp_set_firewall_rule" in lower_message
    ):
        return {
            "category": "firewall_blocked",
            "title": "Azure SQL rechazo la IP de origen",
            "detail": "La IP publica actual del host no esta autorizada en el firewall del logical server de Azure SQL.",
            "action": "Validar allowlist de la IP/NAT de salida del host y esperar la propagacion de la regla.",
            "raw_message": raw_message,
        }

    if (
        "can't open lib" in lower_message
        or "data source name not found" in lower_message
        or ("driver manager" in lower_message and "odbc driver" in lower_message)
    ):
        return {
            "category": "odbc_driver_missing",
            "title": "Driver ODBC no disponible o incorrecto",
            "detail": "El runtime no encontro el driver configurado para SQL Server.",
            "action": f"Instalar o configurar {DEFAULT_DRIVER} y alinear secrets.toml y el contenedor.",
            "raw_message": raw_message,
        }

    if "login failed" in lower_message or "authentication failed" in lower_message:
        return {
            "category": "authentication_failed",
            "title": "Azure SQL rechazo las credenciales",
            "detail": "La autenticacion contra Azure SQL fallo antes de abrir la sesion.",
            "action": "Validar usuario, password y permisos del login configurado en secrets.toml.",
            "raw_message": raw_message,
        }

    return {
        "category": "connection_error",
        "title": "No fue posible conectar con Azure SQL",
        "detail": "La aplicacion no pudo completar la conexion al origen de datos remoto.",
        "action": "Revisar red, DNS, firewall, credenciales y estado del servidor Azure SQL.",
        "raw_message": raw_message,
    }


def _raise_connection_error(exc: Exception, *, cache_available: bool = False):
    diagnostic = classify_db_exception(exc)
    _push_connection_runtime_event(
        {
            "severity": "error",
            "used_cache": False,
            "cache_available": cache_available,
            "diagnostic": diagnostic,
        }
    )
    raise DatabaseConnectionError(
        f"{diagnostic['title']}. {diagnostic['detail']}",
        diagnostic,
        cache_available=cache_available,
    ) from exc


def _build_connection_string(settings: dict) -> str:
    return urllib.parse.quote_plus(
        f"DRIVER={{{settings['driver']}}};"
        f"SERVER={settings['server']};"
        f"DATABASE={settings['database']};"
        f"UID={settings['username']};"
        f"PWD={settings['password']};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )


@_cache_resource
def get_engine():
    params = _build_connection_string(get_connection_settings())
    return create_engine(
        f"mssql+pyodbc:///?odbc_connect={params}",
        pool_pre_ping=True,
        pool_reset_on_return="rollback",
    )


def _build_cache_key(query, params=None):
    payload = {
        "q": query,
        "p": list(params) if isinstance(params, tuple) else params,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.md5(raw).hexdigest()


def _read_sql(query, params=None, ttl=3600):
    cache_key = _build_cache_key(query, params)
    cache_entry = get_cache_entry(cache_key, allow_expired=True)

    if cache_entry is not None and not cache_entry["is_expired"]:
        return pd.DataFrame(cache_entry["value"])

    engine = get_engine()

    try:
        with engine.connect() as conn:
            try:
                df = pd.read_sql(query, conn, params=params)
            except Exception:
                conn.rollback()
                raise
    except Exception as exc:
        diagnostic = classify_db_exception(exc)
        if cache_entry is not None:
            _push_connection_runtime_event(
                {
                    "severity": "warning",
                    "used_cache": True,
                    "cache_available": True,
                    "cache_expired": cache_entry["is_expired"],
                    "cache_age_seconds": cache_entry["age_seconds"],
                    "diagnostic": diagnostic,
                }
            )
            LOGGER.warning(
                "Usando cache SQLite para consulta remota fallida",
                extra={
                    "category": diagnostic["category"],
                    "cache_expired": cache_entry["is_expired"],
                    "cache_age_seconds": cache_entry["age_seconds"],
                },
            )
            return pd.DataFrame(cache_entry["value"])
        _raise_connection_error(exc, cache_available=False)

    set_cache(cache_key, df.to_dict("records"), ttl)
    return df


def execute_non_query(query, params=None):
    engine = get_engine()

    try:
        with engine.begin() as conn:
            conn.execute(text(query), params or {})
    except Exception as exc:
        _raise_connection_error(exc, cache_available=False)


@_cache_data
def cargar_productores():
    query = "EXEC sp_GetProductores"
    return _read_sql(query, ttl=21600)


@_cache_data
def cargar_centros():
    query = "EXEC sp_GetCentrosLogisticos"
    return _read_sql(query, ttl=21600)


@_cache_data
def cargar_especies():
    query = "EXEC sp_GetEspecies"
    return _read_sql(query, ttl=86400)


@_cache_data
def cargar_variedades(id_especie):
    query = "EXEC sp_GetVariedadesByEspecie @idEspecie = ?"
    return _read_sql(query, params=(id_especie,), ttl=21600)
