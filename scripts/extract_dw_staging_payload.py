import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.local_store import get_defectos_para_dw_df, get_registros_para_dw_df


HEADER_COLUMNS = [
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
    "kg_ultima_hora",
    "velocidad_manual",
    "centro_sin_definir",
    "estado_formulario",
    "es_completo",
    "updated_at",
]

DEFECT_COLUMNS = [
    "source_system",
    "source_business_key",
    "codigo_defecto",
    "nombre_defecto",
    "cantidad",
    "updated_at",
]


def build_header_df(fecha_operacional: str | None, solo_completos: bool):
    df = get_registros_para_dw_df(
        fecha_operacional=fecha_operacional,
        solo_completos=solo_completos,
    ).copy()
    if df.empty:
        return df

    df["source_record_id"] = df["id_registro"]
    df["linea_codigo"] = df["linea"]
    df["linea_nombre"] = df["linea"]

    return df[HEADER_COLUMNS]


def build_defect_df(fecha_operacional: str | None, solo_completos: bool):
    df = get_defectos_para_dw_df(
        fecha_operacional=fecha_operacional,
        solo_completos=solo_completos,
    ).copy()
    if df.empty:
        return df
    return df[DEFECT_COLUMNS]


def main():
    parser = argparse.ArgumentParser(
        description="Extrae payload para stg.FormularioHeader y stg.FormularioDefecto."
    )
    parser.add_argument(
        "--fecha-operacional",
        help="Filtra por fecha operacional YYYY-MM-DD.",
    )
    parser.add_argument(
        "--include-borradores",
        action="store_true",
        help="Incluye registros en borrador. Por defecto extrae solo completos.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directorio de salida para CSV (opcional).",
    )
    parser.add_argument(
        "--preview",
        type=int,
        default=5,
        help="Cantidad de filas a mostrar por consola.",
    )
    args = parser.parse_args()

    solo_completos = not args.include_borradores
    header_df = build_header_df(args.fecha_operacional, solo_completos=solo_completos)
    defect_df = build_defect_df(args.fecha_operacional, solo_completos=solo_completos)

    print(f"solo_completos: {solo_completos}")
    print(f"headers: {len(header_df)}")
    print(f"defectos: {len(defect_df)}")

    if not header_df.empty:
        print("\nHeader preview:")
        print(header_df.head(args.preview).to_string(index=False))
    if not defect_df.empty:
        print("\nDefect preview:")
        print(defect_df.head(args.preview).to_string(index=False))

    if args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        header_path = out_dir / "FormularioHeader.csv"
        defect_path = out_dir / "FormularioDefecto.csv"
        header_df.to_csv(header_path, index=False, encoding="utf-8")
        defect_df.to_csv(defect_path, index=False, encoding="utf-8")
        print(f"\nCSV generado: {header_path}")
        print(f"CSV generado: {defect_path}")


if __name__ == "__main__":
    main()
