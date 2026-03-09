import streamlit as st
import pandas as pd
from datetime import datetime, time
from engine import get_engine, cargar_productores, cargar_especies, cargar_variedades
import base64
from pathlib import Path
from services.cache_sqlite import init_cache
from services.cache_warmup import warm_cache
from core.catalogos import LUGAR_SELECCION, LINEAS, DEFECTOS
from core.forms import input_defectos
from services.save_form import guardar_registro

warm_cache()

init_cache()

def img_to_base64(path: str) -> str:
    data = Path(path).read_bytes()
    return base64.b64encode(data).decode()

st.set_page_config(page_title="Planilla Fruta Comercial", layout="wide", initial_sidebar_state="auto")

with st.container():    

    b64 = img_to_base64("images/Imagen2.jpg")

    st.markdown(
        f"""
        <div style="text-align:center; margin-top:10px;">
            <img src="data:image/jpg;base64,{b64}"
                 style="width:220px; display:block; margin:0 auto;" />
            <h1 style="margin: 16px 0 0 0;">Planilla Fruta Comercial</h1>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.divider()
    st.subheader("Encabezado")

    col1, col2, col3 = st.columns([1,2,1])

    with col2:
        verificador = st.text_input("Verificador")

    col1, col2, col3 = st.columns(3)

    with col1:

        fecha = st.date_input("Fecha", datetime.today()) 

        df_productores = cargar_productores()
        productor = st.selectbox(
            "Productor",
            df_productores.to_dict("records"),
            format_func=lambda x: f"{x['CodProductor_SAP']}  -  {x['Productor']}"
        )

        nro_lote = st.text_input("N° Lote") 
        lote_limpio = nro_lote.strip()
        lote_valido = bool(lote_limpio)

        if not lote_valido and nro_lote != "":
            st.warning("Debe ingresar N° Lote")

    with col2:

        linea = st.selectbox(
            "Línea",
            options=list(LINEAS.keys()),
            format_func=lambda x: LINEAS[x]
        )

        df_especies = cargar_especies()
        especie = st.selectbox(
            "Especie",
            df_especies.to_dict("records"),
            format_func=lambda x: f"{x['Especie']}",
            key="especie_select"
        )
        id_especie = int(especie["idEspecie"])

        cant_muestra = st.number_input("Cant. Frutos Muestra", min_value=1, step=1)

    with col3:    

        lugar = st.selectbox(
            "Lugar de selección",
            options=list(LUGAR_SELECCION.keys()),
            format_func=lambda x: LUGAR_SELECCION[x]
        )

        df_variedades = cargar_variedades(id_especie)
        variedad = st.selectbox(
            "Variedad",
            df_variedades.to_dict("records"),
            format_func=lambda x: f"{x['Variedad']}",
            key=f"variedad_{id_especie}"
        )

        #hora_eval = st.time_input("Hora Evaluación", time(8, 0))
        velocidad = st.number_input("Velocidad Kg/h", min_value=0.0, step=0.1, key="velocidad_manual")

    st.divider()

    col_t1, col_t2 = st.columns([4,1])

    with col_t1:
        st.subheader("Defectos (Unidades)")

    valores, suma_defectos = input_defectos(DEFECTOS, columnas=3)

    with col_t2:
        st.markdown(
            f"<h3 style='text-align:right;'>Σ {suma_defectos:d}</h3>",
            unsafe_allow_html=True
        )
    
    st.divider()

    col_r1, col_r2 = st.columns([4,1])

    with col_r1:
        st.subheader("Resultado (Unidades)")

    col1, col2 = st.columns(2)

    with col1:

        fruta_sana = st.number_input("Fruta Sana (exportación)", min_value=0, step=1, format="%d")

    with col2:

        choice = st.number_input("Choice (aprovechable)", min_value=0, step=1, format="%d")

    total_resultado = round(choice + fruta_sana + suma_defectos, 2)

    with col_r2:

        color = "green" if suma_defectos <= cant_muestra else "red"

        st.markdown(
            f"<h3 style='text-align:right; color:{color};'>Σ {total_resultado:d}</h3>",
            unsafe_allow_html=True
        )

    st.divider()

    st.subheader("Terceros")

    col1, col2 = st.columns(2)

    with col1:

        porcentaje_exportable_manual = st.number_input(
            "% Exportable (manual)",
            min_value=0.0,
            max_value=100.0,
            step=0.1
        )

    with col2:

        velocidad = st.number_input("Velocidad (manual)", min_value=0.0, step=0.1,key="velocidad_auto")

    st.divider()

    observaciones = st.text_area("Observaciones")

    st.divider()

    submit = st.button("Enviar Formulario",type="primary",width="stretch", disabled=not lote_valido)

    st.info(
        "Más adelante reemplazaremos este input libre por informacion"
    )

    @st.dialog("Confirmación de Registro",width="medium")
    def mostrar_resumen(registro, porcentaje_exportable, porcentaje_embalable):

        st.success("Registro válido")

        st.markdown("Indicadores")

        col1, col2 = st.columns(2)
        col1.metric("% Exportable", f"{porcentaje_exportable}%")
        col2.metric("% Embalable", f"{porcentaje_embalable}%")

        st.divider()
        st.markdown("Resumen")

        for k, v in registro.items():
            col1, col2 = st.columns([1,2])
            col1.markdown(f"**{k}**")
            col2.write(v)

        st.divider()

        col_btn1, col_btn2 = st.columns(2)

        with col_btn1:
            if st.button("❌ Cancelar"):
                st.rerun()

        with col_btn2:
            if st.button("Confirmar y Guardar", type="primary"):

                # guardar_en_bd(registro)
                # guardar_registro(registro)

                st.success("Registro guardado correctamente")
                st.rerun()

    if submit:

        suma_defectos = round(sum(valores.values()), 2)
        total_con_choice = round(suma_defectos + choice + fruta_sana, 2)
        total_sin_choice = round(suma_defectos + fruta_sana, 2)

        errores = []

        if not nro_lote.strip():
            errores.append("Debe ingresar N° Lote")

        if total_sin_choice != round(cant_muestra, 2):
            errores.append(
                f"Defectos + Fruta Sana ({total_sin_choice}) debe ser igual a la muestra ({cant_muestra})"
            )

        if total_con_choice != round(cant_muestra, 2):
            errores.append(
                f"Defectos + Choice + Fruta Sana ({total_con_choice}) debe ser igual a la muestra ({cant_muestra})"
            )

        if errores:
            for e in errores:
                st.error(f"{e}")
            st.stop()
        else:
            # Cálculos automáticos
            porcentaje_exportable = round((fruta_sana / cant_muestra) * 100, 2)
            porcentaje_embalable = round(((fruta_sana + choice) / cant_muestra) * 100, 2)

            st.success("Registro válido")

            st.markdown("Indicadores Calculados")
            st.write(f"% Exportable (automático): {porcentaje_exportable}%")
            st.write(f"% Embalable: {porcentaje_embalable}%")

            registro = {
                "Fecha": fecha.strftime("%Y-%m-%d"),
                "Línea": linea,
                "Especie": especie["Especie"],
                "Variedad": variedad["Variedad"],
                "Nro Lote": nro_lote,
                #"Hora Evaluacion": hora_eval.strftime("%H:%M"),
                "Productor": f"{productor['CodProductor_SAP']} - {productor['Productor']}",
                "Cant Muestra": cant_muestra,
                "Lugar Seleccion": lugar[lugar],
                **valores,
                "Choice": choice,
                "Fruta Sana": fruta_sana,
                "% Exportable Auto": porcentaje_exportable,
                "% Embalable": porcentaje_embalable,
                "Velocidad Terceros": velocidad,
                "% Exportable Manual": porcentaje_exportable_manual,
                "Observaciones": observaciones,
                "Verificador": verificador
            }

            st.markdown("Resumen Registro")

            for k, v in registro.items():
                col1, col2 = st.columns([1,2])
                col1.markdown(f"**{k}**")
                col2.write(v)

            mostrar_resumen(registro, porcentaje_exportable, porcentaje_embalable)