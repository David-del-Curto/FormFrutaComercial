import streamlit as st
from core.catalogos import DEFECTOS


def render_bloque_defectos(columnas: int = 3):

    col_t1, col_t2 = st.columns([4,1])

    with col_t1:
        st.subheader("Defectos (Unidades)")

    valores = {}

    cols = st.columns(columnas)

    for i, (codigo, nombre) in enumerate(DEFECTOS.items()):
        with cols[i % columnas]:

            valores[codigo] = st.number_input(
                nombre,
                min_value=0,
                step=1,
                format="%d",
                key=f"def_{codigo}"
            )

    suma_defectos = int(sum(valores.values()))

    with col_t2:
        st.markdown(
            f"<h3 style='text-align:right;'>Σ {suma_defectos}</h3>",
            unsafe_allow_html=True
        )

    return valores, suma_defectos


def render_bloque_resultado(cant_muestra, suma_defectos):

    col_r1, col_r2 = st.columns([4,1])

    with col_r1:
        st.subheader("Resultado (Unidades)")

    col1, col2 = st.columns(2)

    with col1:
        fruta_sana = st.number_input(
            "Fruta Sana (exportación)",
            min_value=0,
            step=1,
            format="%d",
            key="fruta_sana"
        )

    with col2:
        choice = st.number_input(
            "Choice (aprovechable)",
            min_value=0,
            step=1,
            format="%d",
            key="choice"
        )

    total = int(choice + fruta_sana + suma_defectos)

    color = "green" if total == cant_muestra else "red"

    with col_r2:
        st.markdown(
            f"<h3 style='text-align:right; color:{color};'>Σ {total}</h3>",
            unsafe_allow_html=True
        )

    return {
        "fruta_sana": fruta_sana,
        "choice": choice,
        "total": total
    }


def render_bloque_terceros():

    st.subheader("Terceros")

    col1, col2 = st.columns(2)

    with col1:
        porc_export_manual = st.number_input(
            "% Exportable (manual)",
            min_value=0.0,
            max_value=100.0,
            step=0.1
        )

    with col2:
        velocidad_manual = st.number_input(
            "Velocidad (manual)",
            min_value=0.0,
            step=0.1
        )

    return {
        "porc_export_manual": porc_export_manual,
        "velocidad_manual": velocidad_manual
    }