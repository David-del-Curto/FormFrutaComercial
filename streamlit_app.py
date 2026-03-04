import streamlit as st
import pandas as pd
from datetime import datetime, time
from engine import get_engine, cargar_productores, cargar_especies, cargar_variedades


st.set_page_config(page_title="Planilla Fruta Comercial", layout="wide", initial_sidebar_state="auto")

lugar_seleccion = {
    "MS": "Mesa Selección",
    "BC": "Bins Comercial",
    "TP": "Trypack"
}

defectos = [
    "Herida Abierta (Oxidada)",
    "Herida Abierta (Fresca)",
    "Machucón",
    "Partidura",
    "Golpe Sol Severo",
    "Cracking",
    "Deshidratación",
    "Desgarro Pedicelar",
    "Lenticelosis",
    "Bitter Pit",
    "Manchas – Roce",
    "Roce (Línea Proceso)",
    "Falta Color",
    "Herida Cicatrizada",
    "Daño Insecto",
    "Deforme",
    "Ramaleo",
    "Roce Grave",
    "Russet Grave"
]

linea = {
    "1": "Linea 1",
    "2": "Linea 2",
    "3": "Linea 3"
}

with st.container():    

    st.image("images/Imagen2.jpg")

    st.title("Planilla Fruta Comercial")

    st.subheader("Encabezado")

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
            options=list(linea.keys())
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
            "Lugar de Selección",
            options=list(lugar_seleccion.keys()),
            format_func=lambda x: f"{x} - {lugar_seleccion[x]}"
        )

        df_variedades = cargar_variedades(id_especie)
        variedad = st.selectbox(
            "Variedad",
            df_variedades.to_dict("records"),
            format_func=lambda x: f"{x['Variedad']}",
            key=f"variedad_{id_especie}"
        )

        hora_eval = st.time_input("Hora Evaluación", time(8, 0))

    st.divider()

    col_t1, col_t2 = st.columns([4,1])

    with col_t1:
        st.subheader("Defectos (Unidades)")

    valores = {}

    cols = st.columns(3)

    for i, d in enumerate(defectos):
        with cols[i % 3]:
            valores[d] = st.number_input(
                d,
                min_value=0.0,
                step=0.1,
                format="%.2f"
            )

    suma_defectos = round(sum(valores.values()), 2)

    with col_t2:
        st.markdown(
            f"<h3 style='text-align:right;'>Σ {suma_defectos:.2f}</h3>",
            unsafe_allow_html=True
        )
    
    st.divider()

    col_r1, col_r2 = st.columns([4,1])

    with col_r1:
        st.subheader("Resultado (Unidades)")

    col1, col2 = st.columns(2)

    with col1:

        fruta_sana = st.number_input("Fruta Sana (exportación)", min_value=0.0, step=0.1, format="%.2f")

    with col2:

        choice = st.number_input("Choice (aprovechable)", min_value=0.0, step=0.1, format="%.2f")

    total_resultado = round(choice + fruta_sana + suma_defectos, 2)

    with col_r2:

        color = "green" if suma_defectos <= cant_muestra else "red"

        st.markdown(
            f"<h3 style='text-align:right; color:{color};'>Σ {total_resultado:.2f}</h3>",
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

        velocidad = st.number_input("Velocidad (manual)", min_value=0.0, step=0.1)

    st.divider()

    col1, col2 = st.columns(2)

    with col1:

        observaciones = st.text_area("Observaciones")

    with col2:

        verificador = st.text_input("Verificador")

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
                "Hora Evaluacion": hora_eval.strftime("%H:%M"),
                "Productor": f"{productor["CodProductor_SAP"]} - {productor["Productor"]}",
                "Cant Muestra": cant_muestra,
                "Lugar Seleccion": lugar_seleccion[lugar],
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