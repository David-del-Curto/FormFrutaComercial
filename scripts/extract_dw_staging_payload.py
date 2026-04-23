import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.local_store import get_defectos_para_dw_df, get_registros_para_dw_df


# Contrato oficial Fase 0 para stg.FormularioHeader.
# `kg_ultima_hora` se mantiene en la captura operacional pero queda fuera del
# contrato DW vigente hasta definir un hecho o mart especifico de productividad.
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
]

DEFECT_COLUMNS = [
    "source_system",
    "source_business_key",
    "codigo_defecto",
    "nombre_defecto",
    "cantidad",
    "updated_at",
]

ETL_METADATA_COLUMNS = [
    "batch_id",
    "source_run_id",
]


def summarize_header_contract_issues(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return []

    issues: list[str] = []

    fruta_comercial_mismatch = df["fruta_comercial"] != df["suma_defectos"]
    if fruta_comercial_mismatch.any():
        issues.append(
            "fruta_comercial != suma_defectos en "
            f"{int(fruta_comercial_mismatch.sum())} formulario(s)"
        )

    total_resultado = df["fruta_sana"] + df["choice"] + df["suma_defectos"]
    muestra_mismatch = total_resultado != df["cant_muestra"]
    if muestra_mismatch.any():
        issues.append(
            "fruta_sana + choice + suma_defectos != cant_muestra en "
            f"{int(muestra_mismatch.sum())} formulario(s)"
        )

    return issues


def build_header_df(
    fecha_operacional: str | None,
    solo_completos: bool,
    batch_id: str | None = None,
    source_run_id: str | None = None,
    include_etl_metadata: bool = False,
):
    df = get_registros_para_dw_df(
        fecha_operacional=fecha_operacional,
        solo_completos=solo_completos,
    ).copy()
    if df.empty:
        columns = HEADER_COLUMNS + (ETL_METADATA_COLUMNS if include_etl_metadata else [])
        return pd.DataFrame(columns=columns)

    df["source_record_id"] = df["id_registro"]
    df["linea_codigo"] = df["linea"]
    df["linea_nombre"] = df["linea"]
    df["especie_principal_linea"] = pd.NA
    df["batch_id"] = batch_id
    df["source_run_id"] = source_run_id

    selected_columns = HEADER_COLUMNS + (ETL_METADATA_COLUMNS if include_etl_metadata else [])
    return df[selected_columns]


def build_defect_df(
    fecha_operacional: str | None,
    solo_completos: bool,
    batch_id: str | None = None,
    source_run_id: str | None = None,
    include_etl_metadata: bool = False,
):
    df = get_defectos_para_dw_df(
        fecha_operacional=fecha_operacional,
        solo_completos=solo_completos,
    ).copy()
    if df.empty:
        columns = DEFECT_COLUMNS + (ETL_METADATA_COLUMNS if include_etl_metadata else [])
        return pd.DataFrame(columns=columns)

    df["batch_id"] = batch_id
    df["source_run_id"] = source_run_id

    selected_columns = DEFECT_COLUMNS + (ETL_METADATA_COLUMNS if include_etl_metadata else [])
    return df[selected_columns]


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
    parser.add_argument(
        "--batch-id",
        help="Batch id opcional para agregar al CSV exportado.",
    )
    parser.add_argument(
        "--source-run-id",
        help="Identificador opcional de corrida para agregar al CSV exportado.",
    )
    parser.add_argument(
        "--include-etl-metadata",
        action="store_true",
        help="Agrega batch_id y source_run_id al export para carga endurecida de Fase 1.",
    )
    args = parser.parse_args()

    solo_completos = not args.include_borradores
    header_df = build_header_df(
        args.fecha_operacional,
        solo_completos=solo_completos,
        batch_id=args.batch_id,
        source_run_id=args.source_run_id,
        include_etl_metadata=args.include_etl_metadata,
    )
    defect_df = build_defect_df(
        args.fecha_operacional,
        solo_completos=solo_completos,
        batch_id=args.batch_id,
        source_run_id=args.source_run_id,
        include_etl_metadata=args.include_etl_metadata,
    )

    print(f"solo_completos: {solo_completos}")
    print(f"headers: {len(header_df)}")
    print(f"defectos: {len(defect_df)}")
    print(f"include_etl_metadata: {args.include_etl_metadata}")

    header_issues = summarize_header_contract_issues(header_df)
    if header_issues:
        print("\nAdvertencias de contrato Header:")
        for issue in header_issues:
            print(f"- {issue}")

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
