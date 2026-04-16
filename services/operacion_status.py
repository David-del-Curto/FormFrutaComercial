from __future__ import annotations

from datetime import datetime

import pandas as pd


MOVING_WINDOW_HOURS = 1


def safe_percentage(valor: float, base: float) -> float:
    if base <= 0:
        return 0.0
    return round((valor / base) * 100, 2)


def is_whole_number(value) -> bool:
    try:
        return float(value).is_integer()
    except (TypeError, ValueError):
        return False


def format_number_latam(value, decimals: int = 0) -> str:
    if value is None or pd.isna(value):
        return "-"

    numeric_value = float(value)
    if abs(numeric_value) < 1e-9:
        numeric_value = 0.0

    formatted = f"{numeric_value:,.{decimals}f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def format_quantity_latam(value) -> str:
    decimals = 0 if is_whole_number(value) else 1
    return format_number_latam(value, decimals)


def format_percent_latam(value, decimals: int = 1) -> str:
    return f"{format_number_latam(value, decimals)} %"


def prepare_records_for_kpi(records_df: pd.DataFrame) -> pd.DataFrame:
    df = records_df.copy()
    numeric_columns = [
        "cant_muestra",
        "suma_defectos",
        "fruta_sana",
        "choice",
        "velocidad_kgh",
        "kg_ultima_hora",
    ]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)

    df["es_completo"] = pd.to_numeric(df.get("es_completo", 0), errors="coerce").fillna(0).astype(int)
    df["updated_at_dt"] = pd.to_datetime(df["updated_at"], errors="coerce")
    df["velocidad_kgh"] = df["velocidad_kgh"].clip(lower=0.0)
    df["kg_ultima_hora"] = df["kg_ultima_hora"].clip(lower=0.0)
    df["kg_comercial_validado"] = df[["kg_ultima_hora", "velocidad_kgh"]].min(axis=1)
    df["kg_exportable_calc"] = (df["velocidad_kgh"] - df["kg_comercial_validado"]).clip(lower=0.0).round(2)

    base_velocidad = df["velocidad_kgh"].where(df["velocidad_kgh"] > 0)
    df["porc_comercial_kilos"] = (
        (df["kg_comercial_validado"] / base_velocidad) * 100
    ).fillna(0.0).round(2)
    df["porc_exportable"] = (
        (df["kg_exportable_calc"] / base_velocidad) * 100
    ).fillna(0.0).round(2)

    calidad_base = (df["fruta_sana"] + df["choice"] + df["suma_defectos"]).astype(float)
    calidad_base = calidad_base.where(calidad_base > 0, df["cant_muestra"])
    calidad_base = calidad_base.where(calidad_base > 0)
    fraccion_calidad_aprovechable = (
        (df["fruta_sana"] + df["choice"]) / calidad_base
    ).fillna(0.0)

    df["porc_sana"] = ((df["fruta_sana"] / calidad_base) * 100).fillna(0.0).round(2)
    df["porc_choice"] = ((df["choice"] / calidad_base) * 100).fillna(0.0).round(2)
    df["porc_descartable"] = ((df["suma_defectos"] / calidad_base) * 100).fillna(0.0).round(2)
    df["porc_fbc"] = (
        ((df["porc_sana"] + df["porc_choice"]) * df["porc_comercial_kilos"]) / 100
    ).round(2)
    df["kg_fbc_h"] = (df["kg_comercial_validado"] * fraccion_calidad_aprovechable).round(2)

    return df


def apply_record_filters(records_df: pd.DataFrame, linea: str | None = None, especie: str | None = None) -> pd.DataFrame:
    filtered_df = records_df.copy()

    if linea:
        filtered_df = filtered_df.loc[filtered_df["linea"].astype(str) == str(linea)].copy()
    if especie:
        filtered_df = filtered_df.loc[filtered_df["especie"].astype(str) == str(especie)].copy()

    return filtered_df


def filter_defectos_by_records(defectos_df: pd.DataFrame, records_df: pd.DataFrame) -> pd.DataFrame:
    if defectos_df.empty or records_df.empty or "id_registro" not in defectos_df.columns:
        return defectos_df.iloc[0:0].copy() if records_df.empty else defectos_df.copy()

    defectos = defectos_df.copy()
    defectos["id_registro_num"] = pd.to_numeric(defectos["id_registro"], errors="coerce")
    ids_validos = set(
        pd.to_numeric(records_df["id_registro"], errors="coerce")
        .dropna()
        .astype(int)
        .tolist()
    )
    defectos = defectos.loc[defectos["id_registro_num"].isin(ids_validos)].copy()
    return defectos.drop(columns=["id_registro_num"])


def last_moving_hour(records_df: pd.DataFrame) -> pd.DataFrame:
    if records_df.empty:
        return records_df

    df_with_timestamp = records_df.loc[records_df["updated_at_dt"].notna()].copy()
    if df_with_timestamp.empty:
        return records_df.copy()

    latest_timestamp = df_with_timestamp["updated_at_dt"].max()
    cutoff = latest_timestamp - pd.Timedelta(hours=MOVING_WINDOW_HOURS)
    return df_with_timestamp.loc[df_with_timestamp["updated_at_dt"] >= cutoff].copy()


def calculate_kpis(records_df: pd.DataFrame) -> dict[str, float]:
    if records_df.empty:
        return {
            "kg_exportable_total": 0,
            "porc_exportable": 0.0,
            "porc_comercial_kilos": 0.0,
            "porc_sana": 0.0,
            "porc_choice": 0.0,
            "porc_descartable": 0.0,
            "porc_fbc": 0.0,
        }

    velocidad_total = float(records_df["velocidad_kgh"].sum())
    kg_comercial_total = float(records_df["kg_comercial_validado"].sum())
    kg_exportable_total = round(max(velocidad_total - kg_comercial_total, 0))
    porc_comercial_kilos = safe_percentage(kg_comercial_total, velocidad_total)
    porc_exportable = safe_percentage(kg_exportable_total, velocidad_total)

    sana_total = float(records_df["fruta_sana"].sum())
    choice_total = float(records_df["choice"].sum())
    mala_total = float(records_df["suma_defectos"].sum())
    calidad_total = sana_total + choice_total + mala_total
    if calidad_total <= 0:
        calidad_total = float(records_df["cant_muestra"].sum())

    porc_sana = safe_percentage(sana_total, calidad_total)
    porc_choice = safe_percentage(choice_total, calidad_total)
    porc_descartable = safe_percentage(mala_total, calidad_total)
    porc_fbc = round(((porc_sana + porc_choice) * porc_comercial_kilos) / 100.0, 2)

    return {
        "kg_exportable_total": kg_exportable_total,
        "porc_exportable": porc_exportable,
        "porc_comercial_kilos": porc_comercial_kilos,
        "porc_sana": porc_sana,
        "porc_choice": porc_choice,
        "porc_descartable": porc_descartable,
        "porc_fbc": porc_fbc,
    }


def estado_semaforo_fbc(porc_fbc: float) -> tuple[str, str]:
    if porc_fbc < 1.0:
        return "Verde", "#2ca02c"
    if porc_fbc < 1.5:
        return "Amarillo", "#f2b01e"
    return "Rojo", "#d62728"


def group_hourly(df: pd.DataFrame, value_field: str, agg: str = "sum") -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["hora", value_field])

    hourly_df = df.loc[df["updated_at_dt"].notna(), ["updated_at_dt", value_field]].copy()
    if hourly_df.empty:
        return pd.DataFrame(columns=["hora", value_field])

    hourly_df["hora_dt"] = hourly_df["updated_at_dt"].dt.floor("h")
    if agg == "mean":
        grouped = hourly_df.groupby("hora_dt", dropna=False)[value_field].mean().reset_index()
    else:
        grouped = hourly_df.groupby("hora_dt", dropna=False)[value_field].sum().reset_index()
    grouped = grouped.sort_values("hora_dt")
    grouped["hora"] = grouped["hora_dt"].dt.strftime("%H:00")
    grouped[value_field] = grouped[value_field].round(2)
    return grouped


def build_window_info(kpi_source_df: pd.DataFrame, kpi_window_df: pd.DataFrame) -> dict:
    if kpi_source_df.empty or "updated_at_dt" not in kpi_source_df.columns:
        return {
            "logical_start": None,
            "logical_end": None,
            "observed_start": None,
            "observed_end": None,
            "has_valid_records": False,
        }

    valid_source_df = kpi_source_df.loc[kpi_source_df["updated_at_dt"].notna()].copy()
    if valid_source_df.empty:
        return {
            "logical_start": None,
            "logical_end": None,
            "observed_start": None,
            "observed_end": None,
            "has_valid_records": False,
        }

    logical_end = valid_source_df["updated_at_dt"].max()
    logical_start = logical_end - pd.Timedelta(hours=MOVING_WINDOW_HOURS)
    observed_start = None
    observed_end = None
    if not kpi_window_df.empty and kpi_window_df["updated_at_dt"].notna().any():
        observed_start = kpi_window_df["updated_at_dt"].min()
        observed_end = kpi_window_df["updated_at_dt"].max()

    return {
        "logical_start": logical_start,
        "logical_end": logical_end,
        "observed_start": observed_start,
        "observed_end": observed_end,
        "has_valid_records": observed_start is not None and observed_end is not None,
    }


def build_operacion_snapshot(records_df: pd.DataFrame, defectos_df: pd.DataFrame) -> dict:
    prepared_records_df = prepare_records_for_kpi(records_df)
    filtered_defectos_df = filter_defectos_by_records(defectos_df, prepared_records_df)

    records_completos_df = prepared_records_df.loc[prepared_records_df["es_completo"] == 1].copy()
    kpi_source_df = records_completos_df if not records_completos_df.empty else prepared_records_df
    kpi_window_df = last_moving_hour(kpi_source_df)
    kpis = calculate_kpis(kpi_window_df)
    semaforo_estado, semaforo_color = estado_semaforo_fbc(kpis["porc_fbc"])
    window_info = build_window_info(kpi_source_df, kpi_window_df)

    return {
        "records_df": prepared_records_df,
        "defectos_df": filtered_defectos_df,
        "records_completos_df": records_completos_df,
        "kpi_source_df": kpi_source_df,
        "kpi_window_df": kpi_window_df,
        "kpis": kpis,
        "semaforo_estado": semaforo_estado,
        "semaforo_color": semaforo_color,
        "window_info": window_info,
        "summary": {
            "formularios": int(len(prepared_records_df)),
            "completos": int(prepared_records_df["es_completo"].sum()) if not prepared_records_df.empty else 0,
            "borradores": int(len(prepared_records_df) - prepared_records_df["es_completo"].sum()) if not prepared_records_df.empty else 0,
            "muestra_total": int(prepared_records_df["cant_muestra"].sum()) if not prepared_records_df.empty else 0,
        },
    }


def format_timestamp_label(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "-"
    if isinstance(value, pd.Timestamp):
        return value.strftime("%H:%M")
    if isinstance(value, datetime):
        return value.strftime("%H:%M")
    return str(value)
