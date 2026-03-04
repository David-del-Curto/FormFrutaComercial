import streamlit as st
import pandas as pd
from datetime import datetime, time

st.set_page_config(page_title="Planilla Fruta Comercial", layout="wide")

st.title("📋 Planilla Fruta Comercial")

# ------------------------
# Glosario
# ------------------------
tipo_proceso = {
    "MS": "Mesa Selección",
    "BC": "Bins Comercial",
    "TP": "Trypack"
}

defectos = [
    "Herida Abierta (Oxidada)",
    "Herida Abierta (Fresca)",
    "Machucón",
    "Partidura",
    "Golpe Sol Sev",
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

# ------------------------
# Formulario
# ------------------------
with st.form("form_planilla"):
    st.subheader("Encabezado")

    col1, col2 = st.columns(2)
    with col1:
        fecha = st.date_input("Fecha", datetime.today())
        linea = st.text_input("Línea")
    with col2:
        proceso = st.selectbox(
            "Tipo Proceso",
            options=list(tipo_proceso.keys()),
            format_func=lambda x: f"{x} - {tipo_proceso[x]}"
        )

    st.subheader("Datos Generales")

    productor = st.text_input("Productor")
    variedad = st.text_input("Variedad")
    nro_lote = st.text_input("N° Lote")
    hora_eval = st.time_input("Hora Evaluación", time(8, 0))
    cant_muestra = st.number_input("Cant. Frutos Muestra", min_value=1, step=1)
    lugar_sel = st.text_input("Lugar Selección")

    st.subheader("Defectos")

    valores = {}
    for d in defectos:
        valores[d] = st.number_input(d, min_value=0.0, step=0.1, format="%.2f")

    st.subheader("Resultado")

    choice = st.number_input("Choice", min_value=0.0, step=0.1, format="%.2f")
    fruta_sana = st.number_input("Fruta Sana", min_value=0.0, step=0.1, format="%.2f")

    observaciones = st.text_area("Observaciones")
    verificador = st.text_input("Verificador")

    submit = st.form_submit_button("Guardar")

# ------------------------
# Validación
# ------------------------
if submit:
    total = round(sum(valores.values()) + choice + fruta_sana, 2)

    if total != round(cant_muestra, 2):
        st.error(
            f"❌ La suma total ({total}) no coincide con la muestra ({cant_muestra})"
        )
    else:
        registro = {
            "fecha": fecha.strftime("%Y%m%d"),
            "linea": linea,
            "tipo_proceso": proceso,
            "productor": productor,
            "variedad": variedad,
            "nro_lote": nro_lote,
            "hora_evaluacion": hora_eval.strftime("%H:%M"),
            "cant_muestra": cant_muestra,
            "lugar_seleccion": lugar_sel,
            **valores,
            "choice": choice,
            "fruta_sana": fruta_sana,
            "observaciones": observaciones,
            "verificador": verificador
        }

        df = pd.DataFrame([registro])
        st.success("✅ Registro guardado correctamente")
        st.dataframe(df)
