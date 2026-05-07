import argparse
import os
import platform
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def print_header(title: str):
    print(f"\n=== {title} ===")


def check_python_runtime():
    print_header("Python")
    print(f"version: {sys.version}")
    print(f"executable: {sys.executable}")
    print(f"platform: {platform.platform()}")


def check_pyodbc_driver(required_driver: str):
    import pyodbc

    print_header("pyodbc")
    print(f"pyodbc_version: {pyodbc.version}")
    drivers = pyodbc.drivers()
    print(f"odbc_drivers: {drivers}")

    if required_driver and required_driver not in drivers:
        raise RuntimeError(
            f"No se encontro el driver requerido '{required_driver}'. "
            f"Drivers detectados: {drivers}"
        )


def check_sql_connection(run_sp_checks: bool):
    from engine import cargar_centros, cargar_especies, classify_db_exception, get_engine

    print_header("Azure SQL")
    engine = get_engine()

    try:
        with engine.connect() as conn:
            value = conn.exec_driver_sql("SELECT 1 AS ok").scalar_one()
            print(f"sql_ping: {value}")
    except Exception as exc:
        diagnostic = classify_db_exception(exc)
        print(f"sql_ping: ERROR")
        print(f"sql_error_category: {diagnostic['category']}")
        print(f"sql_error_title: {diagnostic['title']}")
        print(f"sql_error_action: {diagnostic['action']}")
        print(f"sql_error_raw: {diagnostic['raw_message']}")
        raise

    if not run_sp_checks:
        return

    print_header("Stored Procedures")
    centros = cargar_centros()
    especies = cargar_especies()
    print(f"centros_rows: {len(centros)}")
    print(f"especies_rows: {len(especies)}")


def check_local_store():
    from services.local_store import get_source_system, init_local_store

    print_header("Local Store")
    init_local_store()
    print(f"db_path: {ROOT / 'data' / 'cache.db'}")
    print(f"source_system_default: {get_source_system()}")


def main():
    from engine import get_connection_settings

    parser = argparse.ArgumentParser(
        description="Smoke test del runtime para Form Fruta Comercial."
    )
    parser.add_argument(
        "--skip-db",
        action="store_true",
        help="Omite la prueba de conexion a Azure SQL."
    )
    parser.add_argument(
        "--sp-checks",
        action="store_true",
        help="Ejecuta un smoke test ligero sobre stored procedures de catalogos."
    )
    parser.add_argument(
        "--required-driver",
        default="ODBC Driver 18 for SQL Server",
        help="Nombre del driver ODBC que debe existir."
    )
    args = parser.parse_args()

    print_header("Environment")
    print(f"cwd: {os.getcwd()}")
    print(f"project_root: {ROOT}")

    settings = get_connection_settings()
    print_header("Azure SQL Config")
    print(f"server: {settings['server']}")
    print(f"database: {settings['database']}")
    print(f"configured_driver: {settings['driver']}")
    if settings["driver"] != args.required_driver:
        raise RuntimeError(
            f"El driver configurado es '{settings['driver']}' y debe ser '{args.required_driver}'."
        )

    check_python_runtime()
    check_pyodbc_driver(args.required_driver)
    check_local_store()

    if not args.skip_db:
        check_sql_connection(args.sp_checks)

    print_header("Result")
    print("SMOKE TEST OK")


if __name__ == "__main__":
    main()
