import altair as alt
import pandas as pd
import streamlit as st


def _weighted_percentage(df: pd.DataFrame, column: str) -> float:
    if df.empty:
        return 0.0

    total_muestra = df["cant_muestra"].sum()
    if total_muestra == 0:
        return 0.0

    return round(float((df[column] * df["cant_muestra"]).sum() / total_muestra), 2)


def render_como_vamos(records_df: pd.DataFrame, defectos_df: pd.DataFrame, fecha_operacional: str):
    st.subheader(f"Estatus Dia Operacional {fecha_operacional}")

    if records_df.empty:
        st.info("Aun no hay formularios guardados para este dia operacional.")
        return

    total_forms = len(records_df)
    completos = int(records_df["es_completo"].sum())
    borradores = int(total_forms - completos)
    muestra_total = int(records_df["cant_muestra"].sum())
    porc_exportable = _weighted_percentage(records_df, "porc_exportable")
    porc_embalable = _weighted_percentage(records_df, "porc_embalable")
    porc_choice = _weighted_percentage(records_df, "porc_choice")
    porc_descartable = _weighted_percentage(records_df, "porc_descartable")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Formularios", total_forms)
    col2.metric("Completos", completos)
    col3.metric("Borradores", borradores)
    col4.metric("Muestra acumulada", muestra_total)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("% Exportable", f"{porc_exportable} %")
    col2.metric("% Embalable", f"{porc_embalable} %")
    col3.metric("% Choice", f"{porc_choice} %")
    col4.metric("% Descartable", f"{porc_descartable} %")

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

        tendencia_df = records_df.copy()
        tendencia_df["updated_at"] = pd.to_datetime(tendencia_df["updated_at"], errors="coerce")
        tendencia_df["hora"] = tendencia_df["updated_at"].dt.strftime("%H:00")
        tendencia_df = (
            tendencia_df.groupby("hora", dropna=False)
            .agg(
                formularios=("id_registro", "count"),
                muestra=("cant_muestra", "sum")
            )
            .reset_index()
            .dropna(subset=["hora"])
            .sort_values("hora")
        )

        if not tendencia_df.empty:
            chart = (
                alt.Chart(tendencia_df)
                .transform_fold(
                    ["formularios", "muestra"],
                    as_=["serie", "valor"]
                )
                .mark_line(point=True)
                .encode(
                    x=alt.X("hora:N", title="Hora"),
                    y=alt.Y("valor:Q", title="Valor"),
                    color=alt.Color("serie:N", title="Serie"),
                    tooltip=["hora:N", "serie:N", "valor:Q"]
                )
                .properties(height=280)
            )
            st.altair_chart(chart, width='content')
        else:
            st.info("Aun no hay suficientes registros para construir la tendencia por hora.")

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
        "estado_formulario",
        "campos_pendientes",
        "porc_exportable",
        "porc_embalable",
        "porc_choice",
        "porc_descartable",
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
        "estado_formulario": "Estado",
        "campos_pendientes": "Pendientes",
        "porc_exportable": "% Exportable",
        "porc_embalable": "% Embalable",
        "porc_choice": "% Choice",
        "porc_descartable": "% Descartable",
    })
    st.dataframe(detalle_df, hide_index=True, width='content')
