import streamlit as st
from sqlalchemy import create_engine, text
import urllib
import pandas as pd
from services.cache_sqlite import get_cache, set_cache
import hashlib
import json


@st.cache_resource
def get_engine():
    params = urllib.parse.quote_plus(
        f"DRIVER={{{st.secrets.connections.azure_sql.driver}}};"
        f"SERVER={st.secrets.connections.azure_sql.server};"
        f"DATABASE={st.secrets.connections.azure_sql.database};"
        f"UID={st.secrets.connections.azure_sql.username};"
        f"PWD={st.secrets.connections.azure_sql.password};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )

    engine = create_engine(
        f"mssql+pyodbc:///?odbc_connect={params}",
        pool_pre_ping=True,
        pool_reset_on_return="rollback",
    )
    return engine


def _build_cache_key(query, params=None):
    payload = {
        "q": query,
        "p": list(params) if isinstance(params, tuple) else params
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.md5(raw).hexdigest()


def _read_sql(query, params=None, ttl=3600):
    cache_key = _build_cache_key(query, params)

    cached = get_cache(cache_key)
    if cached is not None:
        return pd.DataFrame(cached)

    engine = get_engine()

    with engine.connect() as conn:
        try:
            df = pd.read_sql(query, conn, params=params)
        except Exception:
            conn.rollback()
            raise

    set_cache(cache_key, df.to_dict("records"), ttl)
    return df


def execute_non_query(query, params=None):
    engine = get_engine()

    with engine.begin() as conn:
        conn.execute(text(query), params or {})


@st.cache_data
def cargar_productores():
    query = "EXEC sp_GetProductores"
    return _read_sql(query, ttl=21600)

@st.cache_data
def cargar_centros():
    query = "EXEC sp_GetCentrosLogisticos"
    return _read_sql(query, ttl=21600)

@st.cache_data
def cargar_especies():
    query = "EXEC sp_GetEspecies"
    return _read_sql(query, ttl=86400)


@st.cache_data
def cargar_variedades(id_especie):
    query = "EXEC sp_GetVariedadesByEspecie @idEspecie = ?"
    return _read_sql(query, params=(id_especie,), ttl=21600)