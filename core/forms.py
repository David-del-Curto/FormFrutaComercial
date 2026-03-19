import streamlit as st
from core.catalogos import DEFECTOS
from core.business_rules import (
    es_centro_sin_definir as _es_centro_sin_definir,
    usa_velocidad_tercero,
)


def es_centro_sin_definir(centro) -> bool:

    return _es_centro_sin_definir(centro)


def calcular_resultado(cant_muestra: int, suma_defectos: int, choice: int = 0):

    cant_muestra = int(cant_muestra or 0)
    suma_defectos = int(suma_defectos or 0)
    choice = max(int(choice or 0), 0)
    max_choice = max(cant_muestra - suma_defectos, 0)

    fruta_comercial = suma_defectos + choice
    fruta_sana = max(cant_muestra - fruta_comercial, 0)
    total = fruta_comercial + fruta_sana
    diferencia_muestra = cant_muestra - fruta_comercial

    return {
        "fruta_sana": fruta_sana,
        "choice": choice,
        "fruta_comercial": fruta_comercial,
        "total": total,
        "choice_disponible": max_choice,
        "diferencia_muestra": diferencia_muestra
    }


def calcular_indicadores_operaciones(cant_muestra: int, suma_defectos: int):

    cant_muestra = int(cant_muestra or 0)
    suma_defectos = int(suma_defectos or 0)
    fruta_embalable = max(cant_muestra - suma_defectos, 0)
    porc_embalable = round((fruta_embalable / cant_muestra) * 100, 2) if cant_muestra else 0.0
    porc_exportacion_ajustada = max(0.0, porc_embalable - 2.0)
    fruta_sana_estimada = int(round(cant_muestra * (porc_exportacion_ajustada / 100.0)))
    fruta_sana_estimada = min(fruta_sana_estimada, fruta_embalable)
    choice_estimado = max(fruta_embalable - fruta_sana_estimada, 0)
    porc_exportable = round((fruta_sana_estimada / cant_muestra) * 100, 2) if cant_muestra else 0.0

    return {
        "fruta_embalable": fruta_embalable,
        "fruta_sana_estimada": fruta_sana_estimada,
        "choice_estimado": choice_estimado,
        "porc_embalable": porc_embalable,
        "porc_exportable": porc_exportable,
        "porc_exportacion_ajustada": porc_exportacion_ajustada
    }


def render_bloque_defectos(columnas: int = 3, disabled: bool = False):

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
                key=f"def_{codigo}",
                disabled=disabled
            )

    suma_defectos = int(sum(valores.values()))

    with col_t2:
        st.markdown(
            f"<h3 style='text-align:right;'>Σ {suma_defectos}</h3>",
            unsafe_allow_html=True
        )

    return valores, suma_defectos


def render_bloque_resultado(cant_muestra, suma_defectos, choice_disabled: bool = False):

    col_r1, col_r2 = st.columns([4,1])

    with col_r1:
        st.subheader("Resultado (Unidades)")

    choice_key = "choice_resultado"
    resultado = calcular_resultado(
        cant_muestra,
        suma_defectos,
        st.session_state.get(choice_key, 0)
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Fruta Comercial (acumulado)", resultado["fruta_comercial"])

    with col2:
        st.metric("Fruta Sana (acumulado)", resultado["fruta_sana"])

    with col3:
        choice = st.number_input(
            "Choice (acumulado)",
            min_value=0,
            step=1,
            format="%d",
            key=choice_key,
            disabled=choice_disabled
        )
        st.caption(f"Disponible sugerido: {resultado['choice_disponible']}")

    resultado = calcular_resultado(cant_muestra, suma_defectos, choice)
    acumulado = resultado["fruta_comercial"]
    diferencia = resultado["diferencia_muestra"]

    if diferencia < 0:
        fondo = "#3f1d1d"
        borde = "#dc2626"
        texto = "#fecaca"
        estado = f"Excede la muestra por {abs(diferencia)} unidad(es)"
    elif diferencia == 0:
        fondo = "#17351f"
        borde = "#16a34a"
        texto = "#bbf7d0"
        estado = "Toda la muestra quedo asignada a fruta comercial"
    else:
        fondo = "#132b45"
        borde = "#2563eb"
        texto = "#bfdbfe"
        estado = f"Fruta sana calculada disponible: {resultado['fruta_sana']} unidad(es)"

    with col_r2:
        st.markdown(
            f"""
            <div style="
                border: 1px solid {borde};
                background: {fondo};
                color: {texto};
                border-radius: 12px;
                padding: 12px 14px;
                text-align: right;
            ">
                <div style="font-size: 0.85rem; opacity: 0.9;">Comercial acumulado</div>
                <div style="font-size: 1.8rem; font-weight: 700; line-height: 1.1;">{acumulado} / {cant_muestra}</div>
                <div style="font-size: 0.9rem; margin-top: 4px;">{estado}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    return resultado


def render_bloque_terceros(
    centro,
    porc_export_disabled: bool = False,
    velocidad_disabled: bool = False,
):

    st.subheader("Terceros")

    centro_sin_definir = es_centro_sin_definir(centro)
    aplica_velocidad_tercero = usa_velocidad_tercero(centro)
    porc_export_key = "porc_export_manual"
    velocidad_tercero_key = "velocidad_manual"

    if not centro_sin_definir and st.session_state.get(porc_export_key, 0) != 0:
        st.session_state[porc_export_key] = 0

    if not aplica_velocidad_tercero and st.session_state.get(velocidad_tercero_key, 0.0) != 0.0:
        st.session_state[velocidad_tercero_key] = 0.0

    col1, col2 = st.columns(2)

    with col1:
        porc_export_manual = st.number_input(
            "% Exportable acumulado (manual)",
            min_value=0,
            max_value=100,
            step=1,
            format="%d",
            key=porc_export_key,
            disabled=(not centro_sin_definir) or porc_export_disabled
        )

    with col2:
        velocidad_manual = st.number_input(
            "Velocidad Tercero Kg/h",
            min_value=0.0,
            step=0.1,
            key=velocidad_tercero_key,
            disabled=(not aplica_velocidad_tercero) or velocidad_disabled
        )

        if not aplica_velocidad_tercero:
            st.caption("No aplica para centros DC02 y DC10.")

    return {
        "porc_export_manual": porc_export_manual,
        "velocidad_manual": velocidad_manual,
        "aplica_velocidad_tercero": aplica_velocidad_tercero,
    }
