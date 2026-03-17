import streamlit as st
from datetime import datetime
import pandas as pd

from services.cache_sqlite import init_cache
from services.cache_warmup import warm_cache

from engine import cargar_productores, cargar_especies, cargar_variedades, cargar_centros

from core.catalogos import LUGAR_SELECCION, LINEAS, DEFECTOS
from core.forms import (
    render_bloque_defectos,
    render_bloque_resultado,
    render_bloque_terceros
)
from core.validators import validar_formulario
from core.ui import render_header, mostrar_resumen_dialog
from services.save_form import guardar_formulario_staging


warm_cache()
init_cache()

st.set_page_config(
    page_title="Planilla Fruta Comercial",
    layout="wide"
)

render_header("images/Imagen2.jpg", "Planilla Fruta Comercial")

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
        format_func=lambda x: f"{x['CodProductor_SAP']} - {x['Productor']}"
    )

    nro_lote = st.text_input("N° Lote")

    df_centros = cargar_centros()
    centro = st.selectbox(
        "Centro Logístico",
        df_centros.to_dict("records"),
        format_func=lambda x: f"{x['CodCentro_SAP']} - {x['Centro_Logistico']}"
    )

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
        format_func=lambda x: x["Especie"]
    )

    cant_muestra = st.number_input(
        "Cant. Frutos Muestra",
        min_value=1,
        step=1
    )

with col3:

    lugar_codigo = st.selectbox(
        "Lugar de selección",
        options=list(LUGAR_SELECCION.keys()),
        format_func=lambda x: LUGAR_SELECCION[x]
    )

    df_variedades = cargar_variedades(int(especie["idEspecie"]))

    variedad = st.selectbox(
        "Variedad",
        df_variedades.to_dict("records"),
        format_func=lambda x: x["Variedad"]
    )

    velocidad_kgh = st.number_input(
        "Velocidad Kg/h",
        min_value=0.0,
        step=0.1
    )

st.divider()

defectos, suma_defectos = render_bloque_defectos()

st.divider()

resultado = render_bloque_resultado(cant_muestra, suma_defectos)

st.divider()

terceros = render_bloque_terceros()

st.divider()

observaciones = st.text_area("Observaciones")

submit = st.button("Enviar Formulario", type="primary", width="stretch")

if submit:

    errores = validar_formulario(
        nro_lote,
        centro,
        cant_muestra,
        suma_defectos,
        resultado["fruta_sana"],
        resultado["choice"],
        verificador
    )

    if errores:
        for e in errores:
            st.error(e)
        st.stop()

    # % Exportacion es estimado y se ajusta -2 pp sobre % Comercial.
    porc_comercial = round((resultado["fruta_comercial"] / cant_muestra) * 100, 2)
    porc_exportacion_estimado = porc_comercial
    porc_exportacion = round((resultado["fruta_sana"] / cant_muestra) * 100, 2)
    porc_choice = round((resultado["choice"] / cant_muestra) * 100, 2)
    porc_descartable = round((suma_defectos / cant_muestra) * 100, 2)

    defectos = {
        DEFECTOS[codigo]: valor
        for codigo, valor in defectos.items()
        if valor > 0
    }

    df_defectos = (
        pd.DataFrame(
            list(defectos.items()),
            columns=["Defecto", "Cantidad"]
        )
        .sort_values("Cantidad", ascending=False)
    )

    if not df_defectos.empty:
        df_defectos["% Muestra"] = (
            df_defectos["Cantidad"] / cant_muestra * 100
        ).round(1).astype(str) + " %"

    resumen = {
        "Verificador": verificador,
        "Fecha": fecha.strftime("%Y-%m-%d"),
        "Linea": LINEAS[linea],
        "Especie": especie["Especie"],
        "Variedad": variedad["Variedad"],
        "Nro Lote": nro_lote,
        "Centro": centro["Centro_Logistico"],
        "Productor": productor["Productor"],
        "Cant Muestra": cant_muestra,
        "Lugar": LUGAR_SELECCION[lugar_codigo],
        "Fruta Comercial (acumulado)": resultado["fruta_comercial"],
        "Fruta Sana (acumulado)": resultado["fruta_sana"],
        "Choice (acumulado)": resultado["choice"],
        "% Exportacion estimado": porc_exportacion_estimado,
        "% Exportacion ajustado (-2 pp)": porc_exportacion,
        "% Choice": porc_choice,
        "% Comercial": porc_comercial,
        "% Descartable": porc_descartable,
    }

    payload = {
        "fecha": fecha.strftime("%Y-%m-%d"),
        "linea": linea,
        "especie": especie["Especie"],
        "variedad": variedad["Variedad"],
        "lote": nro_lote,
        "centro": centro,
        "productor": productor["Productor"],
        "cant_muestra": cant_muestra,
        "fruta_sana": resultado["fruta_sana"],
        "choice": resultado["choice"],
        "porc_exportable": porc_exportacion,
        "porc_embalable": porc_comercial,
        "observaciones": observaciones,
        "verificador": verificador,
        "lugar_codigo": lugar_codigo,
        "velocidad_kgh": velocidad_kgh,
        "porc_export_manual": terceros["porc_export_manual"],
        "velocidad_manual": terceros["velocidad_manual"]
    }

    def confirmar():
        guardar_formulario_staging(payload, defectos)

    mostrar_resumen_dialog(
        resumen,
        df_defectos,
        porc_exportacion,
        porc_choice,
        porc_comercial,
        porc_descartable,
        confirmar
    )
