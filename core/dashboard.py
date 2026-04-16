from datetime import date, datetime

import altair as alt
import pandas as pd
import streamlit as st

from core.catalogos import LINEAS, LINEAS_METADATA
from services.operacion_status import (
    apply_record_filters,
    build_operacion_snapshot,
    filter_defectos_by_records,
    format_number_latam,
    format_percent_latam,
    format_quantity_latam,
    group_hourly,
)


MOVING_WINDOW_HOURS = 1
TODAS_LINEAS_OPTION = "Todas las lineas"
TODAS_ESPECIES_OPTION = "Todas las especies"
PRIMARY_CHART_HEIGHT = 340
SECONDARY_CHART_HEIGHT = 320
SEMAFORO_CHART_HEIGHT = 110
CHART_LOCALE = {
    "number": {
        "decimal": ",",
        "thousands": ".",
        "grouping": [3],
        "currency": ["", ""],
    }
}


def _safe_percentage(valor: float, base: float) -> float:
    if base <= 0:
        return 0.0
    return round((valor / base) * 100, 2)


def _linea_label(linea_codigo: str) -> str:
    return f"{LINEAS.get(linea_codigo, linea_codigo)} ({linea_codigo})"


def _especie_principal_linea(linea_codigo: str) -> str:
    metadata = LINEAS_METADATA.get(linea_codigo, {})
    return str(metadata.get("Especie_Principal") or "").strip()


def _match_option_case_insensitive(options: list[str], target: str) -> str | None:
    target = str(target or "").strip().upper()
    if not target:
        return None

    for option in options:
        if str(option).strip().upper() == target:
            return option

    return None


def _ensure_select_state(key: str, options: list[str], default: str):
    if not options:
        st.session_state.pop(key, None)
        return

    if key not in st.session_state or st.session_state[key] not in options:
        st.session_state[key] = default if default in options else options[0]


def _resolve_operational_date(fecha_operacional: str, fecha_operacional_value=None) -> date:
    if isinstance(fecha_operacional_value, datetime):
        resolved = fecha_operacional_value.date()
    elif isinstance(fecha_operacional_value, date):
        resolved = fecha_operacional_value
    else:
        state_value = st.session_state.get("bi_fecha_operacional")
        if isinstance(state_value, datetime):
            resolved = state_value.date()
        elif isinstance(state_value, date):
            resolved = state_value
        else:
            resolved = datetime.fromisoformat(str(fecha_operacional)).date()

    st.session_state["bi_fecha_operacional"] = resolved
    return resolved


def _is_whole_number(value) -> bool:
    try:
        return float(value).is_integer()
    except (TypeError, ValueError):
        return False


def _format_number_latam(value, decimals: int = 0) -> str:
    return format_number_latam(value, decimals)


def _format_quantity_latam(value) -> str:
    return format_quantity_latam(value)


def _format_percent_latam(value, decimals: int = 1) -> str:
    return format_percent_latam(value, decimals)


def _configure_chart(chart):
    return chart.configure(locale=CHART_LOCALE)


def _prepare_records_for_kpi(records_df: pd.DataFrame) -> pd.DataFrame:
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


def _render_dashboard_filters(
    records_df: pd.DataFrame,
    fecha_operacional_value,
    screen_context: dict | None = None,
) -> tuple[pd.DataFrame, str, str]:
    screen_context = screen_context or {}
    forced_linea = str(screen_context.get("linea") or "").strip()
    forced_especie = str(screen_context.get("especie") or "").strip()
    lock_filters = bool(screen_context.get("lock_filters"))

    lineas_disponibles = sorted(
        {
            str(linea).strip()
            for linea in records_df.get("linea", pd.Series(dtype="object")).dropna().tolist()
            if str(linea).strip()
        },
        key=lambda codigo: LINEAS.get(codigo, codigo),
    )
    if forced_linea and forced_linea not in lineas_disponibles:
        lineas_disponibles.append(forced_linea)
    lineas_options = [TODAS_LINEAS_OPTION, *lineas_disponibles]

    linea_key = "bi_linea_filtro"
    especie_key = "bi_especie_filtro"
    linea_prev_key = "bi_linea_filtro_prev"

    _ensure_select_state(linea_key, lineas_options, TODAS_LINEAS_OPTION)
    if forced_linea:
        st.session_state[linea_key] = forced_linea
    if linea_prev_key not in st.session_state:
        st.session_state[linea_prev_key] = st.session_state[linea_key]

    col_fecha, col_linea, col_especie = st.columns([1, 1, 1])
    with col_fecha:
        st.date_input(
            "Dia operacional",
            key="bi_fecha_operacional",
            disabled=lock_filters,
        )
    with col_linea:
        linea_seleccionada = st.selectbox(
            "Linea",
            options=lineas_options,
            key=linea_key,
            format_func=lambda x: x if x == TODAS_LINEAS_OPTION else _linea_label(x),
            disabled=lock_filters,
        )

    line_changed = st.session_state.get(linea_prev_key) != linea_seleccionada

    if linea_seleccionada == TODAS_LINEAS_OPTION:
        base_especies_df = records_df.copy()
    else:
        base_especies_df = records_df.loc[records_df["linea"].astype(str) == linea_seleccionada].copy()

    especies_disponibles = sorted(
        {
            str(especie).strip()
            for especie in base_especies_df.get("especie", pd.Series(dtype="object")).dropna().tolist()
            if str(especie).strip()
        },
        key=str.upper,
    )
    especies_options = [TODAS_ESPECIES_OPTION, *especies_disponibles]

    if forced_linea and lock_filters:
        st.session_state[especie_key] = forced_especie or TODAS_ESPECIES_OPTION
    elif line_changed:
        especie_sugerida = None
        if linea_seleccionada != TODAS_LINEAS_OPTION:
            especie_sugerida = _match_option_case_insensitive(
                especies_options,
                _especie_principal_linea(linea_seleccionada),
            )
        st.session_state[especie_key] = especie_sugerida or TODAS_ESPECIES_OPTION

    _ensure_select_state(especie_key, especies_options, TODAS_ESPECIES_OPTION)
    with col_especie:
        especie_seleccionada = st.selectbox(
            "Especie",
            options=especies_options,
            key=especie_key,
            disabled=lock_filters,
        )

    st.session_state[linea_prev_key] = linea_seleccionada

    filtered_df = apply_record_filters(
        records_df,
        linea=None if linea_seleccionada == TODAS_LINEAS_OPTION else linea_seleccionada,
        especie=None if especie_seleccionada == TODAS_ESPECIES_OPTION else especie_seleccionada,
    )

    especie_principal = _especie_principal_linea(linea_seleccionada)
    if linea_seleccionada != TODAS_LINEAS_OPTION and especie_principal and not lock_filters:
        st.caption(
            "Sugerencia operativa: "
            f"{_linea_label(linea_seleccionada)} -> {especie_principal}. "
            "Puede ajustar la especie manualmente si corresponde."
        )

    return filtered_df, linea_seleccionada, especie_seleccionada


def _last_moving_hour(records_df: pd.DataFrame) -> pd.DataFrame:
    if records_df.empty:
        return records_df

    df_with_timestamp = records_df.loc[records_df["updated_at_dt"].notna()].copy()
    if df_with_timestamp.empty:
        return records_df.copy()

    latest_timestamp = df_with_timestamp["updated_at_dt"].max()
    cutoff = latest_timestamp - pd.Timedelta(hours=MOVING_WINDOW_HOURS)
    return df_with_timestamp.loc[df_with_timestamp["updated_at_dt"] >= cutoff].copy()


def _calcular_kpis_excel(records_df: pd.DataFrame) -> dict[str, float]:
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
    porc_comercial_kilos = _safe_percentage(kg_comercial_total, velocidad_total)
    porc_exportable = _safe_percentage(kg_exportable_total, velocidad_total)

    sana_total = float(records_df["fruta_sana"].sum())
    choice_total = float(records_df["choice"].sum())
    mala_total = float(records_df["suma_defectos"].sum())
    calidad_total = sana_total + choice_total + mala_total
    if calidad_total <= 0:
        calidad_total = float(records_df["cant_muestra"].sum())

    porc_sana = _safe_percentage(sana_total, calidad_total)
    porc_choice = _safe_percentage(choice_total, calidad_total)
    porc_descartable = _safe_percentage(mala_total, calidad_total)
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


def _estado_semaforo_fbc(porc_fbc: float) -> tuple[str, str]:
    if porc_fbc < 1.0:
        return "Verde", "#2ca02c"
    if porc_fbc < 1.5:
        return "Amarillo", "#f2b01e"
    return "Rojo", "#d62728"


def _build_semaforo_chart(porc_fbc: float):
    max_domain = max(2.0, round(max(porc_fbc, 1.5) * 1.25, 2))
    bandas_df = pd.DataFrame(
        [
            {"inicio": 0.0, "fin": 1.0, "estado": "Verde", "fila": "Semaforo"},
            {"inicio": 1.0, "fin": 1.5, "estado": "Amarillo", "fila": "Semaforo"},
            {"inicio": 1.5, "fin": max_domain, "estado": "Rojo", "fila": "Semaforo"},
        ]
    )
    valor_df = pd.DataFrame([{"valor": porc_fbc, "fila": "Semaforo"}])
    bandas_df["inicio_label"] = bandas_df["inicio"].apply(lambda x: _format_number_latam(x, 1))
    bandas_df["fin_label"] = bandas_df["fin"].apply(lambda x: _format_number_latam(x, 1))
    valor_df["valor_label"] = valor_df["valor"].apply(lambda x: _format_percent_latam(x, 1))

    base = (
        alt.Chart(bandas_df)
        .mark_bar(size=28)
        .encode(
            x=alt.X(
                "inicio:Q",
                title="% FBC (ultima hora)",
                scale=alt.Scale(domain=[0, max_domain]),
            ),
            x2="fin:Q",
            y=alt.Y("fila:N", axis=None),
            color=alt.Color(
                "estado:N",
                legend=None,
                scale=alt.Scale(
                    domain=["Verde", "Amarillo", "Rojo"],
                    range=["#2ca02c", "#f2b01e", "#d62728"],
                ),
            ),
            tooltip=[
                alt.Tooltip("estado:N", title="Estado"),
                alt.Tooltip("inicio_label:N", title="Desde"),
                alt.Tooltip("fin_label:N", title="Hasta"),
            ],
        )
    )

    marcador = (
        alt.Chart(valor_df)
        .mark_point(shape="diamond", color="black", size=140)
        .encode(
            x=alt.X("valor:Q", scale=alt.Scale(domain=[0, max_domain])),
            y=alt.Y("fila:N", axis=None),
            tooltip=[alt.Tooltip("valor_label:N", title="% FBC actual")],
        )
    )

    etiqueta_valor = (
        alt.Chart(valor_df)
        .mark_text(
            align="left",
            baseline="middle",
            dx=10,
            color="#f8fafc",
            fontSize=18,
            fontWeight="bold",
        )
        .encode(
            x=alt.X("valor:Q", scale=alt.Scale(domain=[0, max_domain])),
            y=alt.Y("fila:N", axis=None),
            text=alt.Text("valor_label:N"),
        )
    )

    return _configure_chart((base + marcador + etiqueta_valor).properties(height=SEMAFORO_CHART_HEIGHT))


def _filtrar_defectos_por_registros(defectos_df: pd.DataFrame, records_df: pd.DataFrame) -> pd.DataFrame:
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


def _group_hourly(df: pd.DataFrame, value_field: str, agg: str = "sum") -> pd.DataFrame:
    return group_hourly(df, value_field, agg)


def render_como_vamos(
    records_df: pd.DataFrame,
    defectos_df: pd.DataFrame,
    fecha_operacional: str,
    fecha_operacional_value=None,
    screen_context: dict | None = None,
):
    st.subheader("Estatus Operacion")
    fecha_operacional_value = _resolve_operational_date(
        fecha_operacional,
        fecha_operacional_value,
    )
    records_df, _, _ = _render_dashboard_filters(records_df, fecha_operacional_value, screen_context)
    defectos_df = filter_defectos_by_records(defectos_df, records_df)

    if records_df.empty:
        st.info("No hay registros para el dia operacional o filtros seleccionados.")
        return

    snapshot = build_operacion_snapshot(records_df, defectos_df)
    records_df = snapshot["records_df"]
    defectos_df = snapshot["defectos_df"]
    kpi_source_df = snapshot["kpi_source_df"]
    kpi_window_df = snapshot["kpi_window_df"]
    kpis = snapshot["kpis"]
    summary = snapshot["summary"]

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Formularios", _format_number_latam(summary["formularios"], 0))
    col2.metric("Completos", _format_number_latam(summary["completos"], 0))
    col3.metric("Borradores", _format_number_latam(summary["borradores"], 0))
    col4.metric("Muestra acumulada", _format_number_latam(summary["muestra_total"], 0))
    col5.metric("Kg Exportable 1h", _format_quantity_latam(kpis["kg_exportable_total"]))

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("% Exportable", _format_percent_latam(kpis["porc_exportable"], 1))
    col2.metric("% Comercial Kg", _format_percent_latam(kpis["porc_comercial_kilos"], 1))
    col3.metric("% Sana", _format_percent_latam(kpis["porc_sana"], 1))
    col4.metric("% Choice", _format_percent_latam(kpis["porc_choice"], 1))
    col5.metric("% Descartable", _format_percent_latam(kpis["porc_descartable"], 1))

    st.altair_chart(_build_semaforo_chart(kpis["porc_fbc"]), width="stretch")

    st.divider()

    turnos_df = (
        records_df.groupby(["turno_codigo", "turno_nombre", "rango_turno"], dropna=False)
        .agg(
            formularios=("id_registro", "count"),
            muestra=("cant_muestra", "sum"),
            borradores=("es_completo", lambda s: int((1 - s).sum()))
        )
        .reset_index()
        .sort_values("turno_codigo")
    )

    turnos_df["etiqueta_turno"] = (
        turnos_df["turno_nombre"] + " (" + turnos_df["rango_turno"] + ")"
    )

    col_left, col_center, col_right = st.columns(3)

    with col_left:
        st.markdown("Promedio % FBC por hora (simple)")

        promedio_fbc_h_df = _group_hourly(kpi_source_df, "porc_fbc", agg="mean")
        if promedio_fbc_h_df.empty:
            st.info("Aun no hay suficientes registros para calcular el promedio de % FBC por hora.")
        else:
            promedio_fbc_h_df["porc_fbc"] = promedio_fbc_h_df["porc_fbc"].round(0).astype(int)
            hora_sort = promedio_fbc_h_df["hora"].tolist()
            promedio_fbc_h_df["porc_fbc_label"] = promedio_fbc_h_df["porc_fbc"].apply(
                lambda x: _format_percent_latam(x, 0)
            )
            promedio_chart = (
                alt.Chart(promedio_fbc_h_df)
                .mark_line(point=True)
                .encode(
                    x=alt.X("hora:N", title="Hora", sort=hora_sort),
                    y=alt.Y("porc_fbc:Q", title="Promedio % FBC/h", axis=alt.Axis(format=".0f")),
                    tooltip=[
                        alt.Tooltip("hora:N", title="Hora"),
                        alt.Tooltip("porc_fbc_label:N", title="Promedio % FBC/h"),
                    ],
                )
                .properties(height=PRIMARY_CHART_HEIGHT)
            )
            st.altair_chart(_configure_chart(promedio_chart), width="stretch")

    with col_center:
        st.markdown("Tendencia % defectos por hora (tipo)")

        if defectos_df.empty:
            st.info("No hay defectos para construir la tendencia por tipo.")
        else:
            defect_hour_df = defectos_df.merge(
                records_df[["id_registro", "updated_at_dt"]],
                on="id_registro",
                how="inner",
            )
            defect_hour_df = defect_hour_df.loc[defect_hour_df["updated_at_dt"].notna()].copy()

            if defect_hour_df.empty:
                st.info("No hay marcas horarias validas para calcular la tendencia de defectos.")
            else:
                defect_hour_df["hora_dt"] = defect_hour_df["updated_at_dt"].dt.floor("h")
                defect_hour_group = (
                    defect_hour_df.groupby(["hora_dt", "nombre_defecto"], dropna=False)["cantidad"]
                    .sum()
                    .reset_index()
                )
                total_por_hora = (
                    defect_hour_group.groupby("hora_dt", dropna=False)["cantidad"]
                    .sum()
                    .rename("total_hora")
                    .reset_index()
                )
                defect_hour_group = defect_hour_group.merge(total_por_hora, on="hora_dt", how="left")
                defect_hour_group["porc_defecto_tipo_h"] = (
                    (defect_hour_group["cantidad"] / defect_hour_group["total_hora"]) * 100
                ).fillna(0.0).round(0).astype(int)
                defect_hour_group = defect_hour_group.sort_values(["hora_dt", "nombre_defecto"])
                defect_hour_group["hora"] = defect_hour_group["hora_dt"].dt.strftime("%H:00")
                defect_hour_group["porc_defecto_tipo_h_label"] = defect_hour_group["porc_defecto_tipo_h"].apply(
                    lambda x: _format_percent_latam(x, 0)
                )

                hora_sort = defect_hour_group["hora"].drop_duplicates().tolist()
                defecto_chart = (
                    alt.Chart(defect_hour_group)
                    .mark_line(point=True)
                    .encode(
                        x=alt.X("hora:N", title="Hora", sort=hora_sort),
                        y=alt.Y("porc_defecto_tipo_h:Q", title="% Defecto por hora", axis=alt.Axis(format=".0f")),
                        color=alt.Color("nombre_defecto:N", title="Defecto"),
                        tooltip=[
                            alt.Tooltip("hora:N", title="Hora"),
                            alt.Tooltip("nombre_defecto:N", title="Defecto"),
                            alt.Tooltip("cantidad:Q", title="Cantidad"),
                            alt.Tooltip("total_hora:Q", title="Total hora"),
                            alt.Tooltip("porc_defecto_tipo_h_label:N", title="% Defecto"),
                        ],
                    )
                    .properties(height=SECONDARY_CHART_HEIGHT)
                )
                st.altair_chart(_configure_chart(defecto_chart), width="stretch")

    with col_right:
        st.markdown("Status de Operacion (Kg FBC/h)")

        tendencia_df = _group_hourly(kpi_source_df, "kg_fbc_h", agg="sum")
        if not tendencia_df.empty:
            hora_sort = tendencia_df["hora"].tolist()
            tendencia_df["kg_fbc_h_label"] = tendencia_df["kg_fbc_h"].apply(_format_quantity_latam)
            chart = (
                alt.Chart(tendencia_df)
                .mark_line(point=True)
                .encode(
                    x=alt.X("hora:N", title="Hora", sort=hora_sort),
                    y=alt.Y("kg_fbc_h:Q", title="Kg FBC/h"),
                    tooltip=[
                        alt.Tooltip("hora:N", title="Hora"),
                        alt.Tooltip("kg_fbc_h_label:N", title="Kg FBC/h"),
                    ],
                )
                .properties(height=PRIMARY_CHART_HEIGHT)
            )
            st.altair_chart(_configure_chart(chart), width="stretch")
        else:
            st.info("Aun no hay suficientes registros para construir la tendencia de Kg FBC/h por hora.")

    st.divider()

    col_left, col_center, col_right = st.columns(3)

    with col_left:
        st.markdown("Muestra por turno")

        turno_chart = (
            alt.Chart(turnos_df)
            .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
            .encode(
                x=alt.X("etiqueta_turno:N", title="Turno"),
                y=alt.Y("muestra:Q", title="Muestra"),
                color=alt.Color("turno_nombre:N", legend=None),
                tooltip=["turno_nombre:N", "rango_turno:N", "formularios:Q", "muestra:Q", "borradores:Q"]
            )
            .properties(height=SECONDARY_CHART_HEIGHT)
        )
        st.altair_chart(_configure_chart(turno_chart), width="stretch")

    with col_center:
        st.markdown("Kg exportable por hora (vaciado)")

        kg_exportable_h_df = _group_hourly(kpi_source_df, "kg_exportable_calc", agg="sum")
        if kg_exportable_h_df.empty:
            st.info("Aun no hay suficientes registros para construir Kg exportable por hora.")
        else:
            hora_sort = kg_exportable_h_df["hora"].tolist()
            kg_exportable_h_df["kg_exportable_calc_label"] = kg_exportable_h_df["kg_exportable_calc"].apply(
                _format_quantity_latam
            )
            exportable_chart = (
                alt.Chart(kg_exportable_h_df)
                .mark_line(point=True)
                .encode(
                    x=alt.X("hora:N", title="Hora", sort=hora_sort),
                    y=alt.Y("kg_exportable_calc:Q", title="Kg exportable/h"),
                    tooltip=[
                        alt.Tooltip("hora:N", title="Hora"),
                        alt.Tooltip("kg_exportable_calc_label:N", title="Kg exportable/h"),
                    ],
                )
                .properties(height=SECONDARY_CHART_HEIGHT)
            )
            st.altair_chart(_configure_chart(exportable_chart), width="stretch")

    with col_right:
        st.markdown("Top defectos")

        if defectos_df.empty:
            st.info("No hay defectos registrados para este dia operacional.")
        else:
            top_defectos = (
                defectos_df.groupby("nombre_defecto", dropna=False)["cantidad"]
                .sum()
                .reset_index()
                .sort_values(["cantidad", "nombre_defecto"], ascending=[False, True])
                .head(10)
            )
            total_defectos = float(defectos_df["cantidad"].sum())
            top_defectos["porc_defecto"] = (
                (top_defectos["cantidad"] / total_defectos) * 100 if total_defectos > 0 else 0.0
            )
            top_defectos["porc_defecto"] = top_defectos["porc_defecto"].round(0).astype(int)
            top_defectos["porc_label"] = top_defectos["porc_defecto"].astype(str) + " %"
            cantidad_max = float(top_defectos["cantidad"].max() or 0.0)
            x_domain_max = max(cantidad_max * 1.22, cantidad_max + 1.0)
            x_encoding = alt.X(
                "cantidad:Q",
                title="Cantidad",
                scale=alt.Scale(domain=[0, x_domain_max]),
            )

            defect_chart_base = (
                alt.Chart(top_defectos)
                .mark_bar(cornerRadiusTopLeft=6, cornerRadiusBottomLeft=6)
                .encode(
                    x=x_encoding,
                    y=alt.Y("nombre_defecto:N", sort="-x", title="Defecto"),
                    tooltip=[
                        alt.Tooltip("nombre_defecto:N", title="Defecto"),
                        alt.Tooltip("cantidad:Q", title="Cantidad"),
                        alt.Tooltip("porc_label:N", title="% del total"),
                    ],
                )
            )
            defect_chart_label = (
                alt.Chart(top_defectos)
                .mark_text(align="left", dx=8, baseline="middle", color="#f8fafc", fontWeight="bold")
                .encode(
                    x=x_encoding,
                    y=alt.Y("nombre_defecto:N", sort="-x"),
                    text=alt.Text("porc_label:N"),
                )
            )
            st.altair_chart(
                _configure_chart((defect_chart_base + defect_chart_label).properties(height=SECONDARY_CHART_HEIGHT)),
                width="stretch",
            )

    st.divider()

    st.markdown("Pendientes de completar")

    pendientes_df = records_df.loc[records_df["es_completo"] == 0, [
        "id_registro",
        "lote",
        "linea",
        "especie",
        "turno_nombre",
        "campos_pendientes",
        "updated_at",
    ]].copy()

    if pendientes_df.empty:
        st.success("No hay formularios pendientes.")
    else:
        pendientes_df = pendientes_df.rename(columns={
            "id_registro": "ID",
            "lote": "Lote",
            "linea": "Linea",
            "especie": "Especie",
            "turno_nombre": "Turno",
            "campos_pendientes": "Pendiente",
            "updated_at": "Actualizado",
        })
        pendientes_df["ID"] = pendientes_df["ID"].apply(lambda x: _format_number_latam(x, 0))
        st.dataframe(pendientes_df, hide_index=True, width='content')

    st.divider()

    st.markdown("Detalle del dia")
    detalle_df = records_df[[
        "id_registro",
        "updated_at",
        "turno_nombre",
        "lote",
        "linea",
        "especie",
        "variedad",
        "centro_display",
        "cant_muestra",
        "velocidad_kgh",
        "kg_comercial_validado",
        "kg_exportable_calc",
        "estado_formulario",
        "campos_pendientes",
        "porc_exportable",
        "porc_comercial_kilos",
        "porc_sana",
        "porc_choice",
        "porc_descartable",
        "porc_fbc",
    ]].copy()
    detalle_df = detalle_df.rename(columns={
        "id_registro": "ID",
        "updated_at": "Actualizado",
        "turno_nombre": "Turno",
        "lote": "Lote",
        "linea": "Linea",
        "especie": "Especie",
        "variedad": "Variedad",
        "centro_display": "Centro",
        "cant_muestra": "Muestra",
        "velocidad_kgh": "Kg/Hr",
        "kg_comercial_validado": "Kg Comercial 1h",
        "kg_exportable_calc": "Kg Exportable",
        "estado_formulario": "Estado",
        "campos_pendientes": "Pendientes",
        "porc_exportable": "% Exportable",
        "porc_comercial_kilos": "% Comercial Kg",
        "porc_sana": "% Sana",
        "porc_choice": "% Choice",
        "porc_descartable": "% Descartable",
        "porc_fbc": "% FBC",
    })
    detalle_df["ID"] = detalle_df["ID"].apply(lambda x: _format_number_latam(x, 0))
    detalle_df["Muestra"] = detalle_df["Muestra"].apply(lambda x: _format_number_latam(x, 0))
    detalle_df["Kg/Hr"] = detalle_df["Kg/Hr"].apply(_format_quantity_latam)
    detalle_df["Kg Comercial 1h"] = detalle_df["Kg Comercial 1h"].apply(_format_quantity_latam)
    detalle_df["Kg Exportable"] = detalle_df["Kg Exportable"].apply(_format_quantity_latam)
    for porcentaje_col in [
        "% Exportable",
        "% Comercial Kg",
        "% Sana",
        "% Choice",
        "% Descartable",
        "% FBC",
    ]:
        detalle_df[porcentaje_col] = detalle_df[porcentaje_col].apply(
            lambda x: _format_percent_latam(x, 1)
        )
    st.dataframe(detalle_df, hide_index=True, width='content')
