import math

import streamlit as st


def render_header(image_path: str, title: str):
    st.sidebar.image(image_path, width=120)
    st.sidebar.markdown(f"### {title}")
    st.sidebar.caption("Control operacional diario")


def render_operacion_layout(hide_sidebar: bool = False):
    sidebar_css = ""
    if hide_sidebar:
        sidebar_css = """
        [data-testid="stSidebar"] { display: none; }
        [data-testid="collapsedControl"] { display: none; }
        """

    st.markdown(
        f"""
        <style>
        [data-testid="stHeader"] {{
            display: none;
        }}
        [data-testid="stMainBlockContainer"] {{
            padding-top: 0.8rem;
            padding-bottom: 1.5rem;
        }}
        {sidebar_css}
        </style>
        """,
        unsafe_allow_html=True,
    )


def mostrar_resumen_dialog(
    registro,
    df_defectos,
    metricas,
    on_confirm,
):
    def _rerun_app():
        st.rerun(scope="app")

    @st.dialog("Confirmacion de Registro", width="large")
    def dialog():
        st.success("Registro valido")
        st.markdown("Indicadores de Calidad")

        cols = st.columns(len(metricas))
        for col, (label, valor) in zip(cols, metricas):
            if isinstance(valor, (int, float)) and not isinstance(valor, bool):
                display_value = f"{round(float(valor), 2)} %"
                if not math.isfinite(float(valor)):
                    display_value = "Pendiente"
            else:
                display_value = str(valor)

            col.metric(label, display_value, delta=None)

        st.divider()
        col_resumen, col_defectos = st.columns([1, 1])

        with col_resumen:
            st.markdown("Resumen Registro")
            for k, v in registro.items():
                c1, c2 = st.columns([1, 2])
                c1.markdown(f"**{k}**")
                c2.write(v)

        with col_defectos:
            st.markdown("Defectos")
            if not df_defectos.empty:
                st.dataframe(df_defectos, hide_index=True, width="content")
            else:
                st.info("No se registraron defectos")

            if not df_defectos.empty:
                defecto_top = df_defectos.iloc[0]["Defecto"]
                cant_top = df_defectos.iloc[0]["Cantidad"]
                st.info(f"Defecto principal: **{defecto_top} ({cant_top})**")

        st.divider()
        col_btn1, col_btn2 = st.columns(2)

        with col_btn1:
            if st.button("Cancelar"):
                _rerun_app()

        with col_btn2:
            if st.button("Confirmar y Guardar", type="primary"):
                try:
                    on_confirm()
                except Exception as exc:
                    st.error(f"No se pudo guardar el registro: {exc}")
                else:
                    # Avoid extra UI writes in the dialog right before full app rerun.
                    _rerun_app()

    dialog()
