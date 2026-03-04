import streamlit as st
from sqlalchemy import create_engine
import urllib
import pandas as pd

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


def _read_sql(query, params=None):
    engine = get_engine()
    with engine.connect() as conn:
        try:
            return pd.read_sql(query, conn, params=params)
        except Exception:
            # Ensure failed/invalid transactions do not poison pooled connections.
            conn.rollback()
            raise

@st.cache_data
def cargar_productores():
    query = "EXEC sp_GetProductores"
    return _read_sql(query)

@st.cache_data
def cargar_especies():
    query = "EXEC sp_GetEspecies"
    return _read_sql(query)

@st.cache_data
def cargar_variedades(id_especie):
    query = "EXEC sp_GetVariedadesByEspecie @idEspecie = ?"
    return _read_sql(query, params=(id_especie,))
