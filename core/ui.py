import base64
from pathlib import Path
import streamlit as st


def img_to_base64(path: str) -> str:
    data = Path(path).read_bytes()
    return base64.b64encode(data).decode()


def render_header(image_path: str, title: str):

    b64 = img_to_base64(image_path)

    st.markdown(
        f"""
        <div style="text-align:center; margin-top:10px;">
            <img src="data:image/jpg;base64,{b64}"
                 style="width:220px; display:block; margin:0 auto;" />
            <h1 style="margin: 16px 0 0 0;">{title}</h1>
        </div>
        """,
        unsafe_allow_html=True
    )


def mostrar_resumen_dialog(
    registro,
    df_defectos,
    porc_exportacion,
    porc_choice,
    porc_comercial,
    porc_descartable,
    on_confirm
):

    @st.dialog("Confirmación de Registro", width="large")
    def dialog():

        st.success("Registro válido")

        st.markdown("Indicadores de Calidad")

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "% Exportacion",
            f"{porc_exportacion} %",
        )

        col2.metric(
            "% Choice",
            f"{porc_choice} %",
        )

        col3.metric(
            "% Comercial",
            f"{porc_comercial} %",
        )

        col4.metric(
            "% Descartable",
            f"{porc_descartable} %",
            delta=None
        )

        st.divider()

        col_resumen, col_defectos = st.columns([1,1])

        with col_resumen:

            st.markdown("Resumen Registro")

            for k, v in registro.items():

                c1, c2 = st.columns([1,2])
                c1.markdown(f"**{k}**")
                c2.write(v)

        with col_defectos:

            st.markdown("Defectos")

            if not df_defectos.empty:

                st.dataframe(
                    df_defectos,
                    hide_index=True,
                    width='content'
                )

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
                st.rerun()

        with col_btn2:
            if st.button("Confirmar y Guardar", type="primary"):
                on_confirm()
                st.success("Registro guardado correctamente")
                st.rerun()

    dialog()
