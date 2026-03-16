from engine import get_engine

def init_db():

    engine = get_engine()

    with engine.begin() as conn:

        conn.exec_driver_sql("""
        CREATE TABLE IF NOT EXISTS registro (
            id_registro INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            linea TEXT,
            especie TEXT,
            variedad TEXT,
            lote TEXT,
            centro TEXT,
            productor TEXT,
            cant_muestra INTEGER,
            fruta_sana INTEGER,
            choice INTEGER,
            porc_exportable REAL,
            porc_embalable REAL,
            observaciones TEXT
        )
        """)

        conn.exec_driver_sql("""
        CREATE TABLE IF NOT EXISTS catalogo_defectos (
            codigo TEXT PRIMARY KEY,
            nombre TEXT
        )
        """)

        conn.exec_driver_sql("""
        CREATE TABLE IF NOT EXISTS registro_defectos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_registro INTEGER,
            codigo_defecto TEXT,
            cantidad INTEGER
        )
        """)
