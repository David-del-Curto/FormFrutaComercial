import altair as alt
import pandas as pd
import streamlit as st


MOVING_WINDOW_HOURS = 1


def _safe_percentage(valor: float, base: float) -> float:
    if base <= 0:
        return 0.0
    return round((valor / base) * 100, 2)


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
            "kg_exportable_total": 0.0,
            "porc_exportable": 0.0,
            "porc_comercial_kilos": 0.0,
            "porc_sana": 0.0,
            "porc_choice": 0.0,
            "porc_descartable": 0.0,
            "porc_fbc": 0.0,
        }

    velocidad_total = float(records_df["velocidad_kgh"].sum())
    kg_comercial_total = float(records_df["kg_comercial_validado"].sum())
    kg_exportable_total = round(max(velocidad_total - kg_comercial_total, 0.0), 2)
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


def render_como_vamos(records_df: pd.DataFrame, defectos_df: pd.DataFrame, fecha_operacional: str):
    st.subheader(f"Estatus Dia Operacional {fecha_operacional}")

    if records_df.empty:
        st.info("Aun no hay formularios guardados para este dia operacional.")
        return

    records_df = _prepare_records_for_kpi(records_df)
    records_completos_df = records_df.loc[records_df["es_completo"] == 1].copy()
    kpi_source_df = records_completos_df if not records_completos_df.empty else records_df
    kpi_window_df = _last_moving_hour(kpi_source_df)
    kpis = _calcular_kpis_excel(kpi_window_df)

    total_forms = len(records_df)
    completos = int(records_df["es_completo"].sum())
    borradores = int(total_forms - completos)
    muestra_total = int(records_df["cant_muestra"].sum())

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Formularios", total_forms)
    col2.metric("Completos", completos)
    col3.metric("Borradores", borradores)
    col4.metric("Muestra acumulada", muestra_total)
    col5.metric("Kg Exportable 1h", kpis["kg_exportable_total"])

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("% Exportable", f"{kpis['porc_exportable']} %")
    col2.metric("% Comercial Kg", f"{kpis['porc_comercial_kilos']} %")
    col3.metric("% Sana", f"{kpis['porc_sana']} %")
    col4.metric("% Choice", f"{kpis['porc_choice']} %")
    col5.metric("% Descartable", f"{kpis['porc_descartable']} %")
    col6.metric("% FBC", f"{kpis['porc_fbc']} %")

    if kpi_window_df.empty:
        st.caption("KPI sin registros validos en la ultima hora movil.")
    else:
        inicio = kpi_window_df["updated_at_dt"].min()
        fin = kpi_window_df["updated_at_dt"].max()
        st.caption(
            "Formula en ventana movil 1h: "
            f"{inicio.strftime('%H:%M')} - {fin.strftime('%H:%M')}"
        )

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

    col_left, col_right = st.columns([1.2, 1])

    with col_left:
        st.markdown("Tendencia por hora")

        tendencia_df = kpi_source_df.copy()
        tendencia_df["hora"] = tendencia_df["updated_at_dt"].dt.strftime("%H:00")
        tendencia_df = (
            tendencia_df.groupby("hora", dropna=False)
            .agg(
                kg_fbc_h=("kg_fbc_h", "sum"),
            )
            .reset_index()
            .dropna(subset=["hora"])
            .sort_values("hora")
        )
        tendencia_df["kg_fbc_h"] = tendencia_df["kg_fbc_h"].round(2)

        if not tendencia_df.empty:
            chart = (
                alt.Chart(tendencia_df)
                .mark_line(point=True)
                .encode(
                    x=alt.X("hora:N", title="Hora"),
                    y=alt.Y("kg_fbc_h:Q", title="Kg FBC/h"),
                    tooltip=[
                        alt.Tooltip("hora:N", title="Hora"),
                        alt.Tooltip("kg_fbc_h:Q", title="Kg FBC/h", format=".2f"),
                    ],
                )
                .properties(height=280)
            )
            st.altair_chart(chart, width='content')
        else:
            st.info("Aun no hay suficientes registros para construir la tendencia de Kg FBC/h por hora.")

    with col_right:
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
            .properties(height=280)
        )
        st.altair_chart(turno_chart, width='content')

    st.divider()

    col_left, col_right = st.columns([1.1, 1])

    with col_left:
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

            defect_chart = (
                alt.Chart(top_defectos)
                .mark_bar(cornerRadiusTopLeft=6, cornerRadiusBottomLeft=6)
                .encode(
                    x=alt.X("cantidad:Q", title="Cantidad"),
                    y=alt.Y("nombre_defecto:N", sort="-x", title="Defecto"),
                    tooltip=["nombre_defecto:N", "cantidad:Q"]
                )
                .properties(height=320)
            )
            st.altair_chart(defect_chart, width='content')

    with col_right:
        st.markdown("Pendientes de completar")

        pendientes_df = records_df.loc[records_df["es_completo"] == 0, [
            "id_registro",
            "lote",
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
                "especie": "Especie",
                "turno_nombre": "Turno",
                "campos_pendientes": "Pendiente",
                "updated_at": "Actualizado",
            })
            st.dataframe(pendientes_df, hide_index=True, width='content')

    st.divider()

    st.markdown("Detalle del dia")
    detalle_df = records_df[[
        "id_registro",
        "updated_at",
        "turno_nombre",
        "lote",
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
    st.dataframe(detalle_df, hide_index=True, width='content')
