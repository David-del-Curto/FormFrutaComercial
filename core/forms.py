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

    # Comercial considera solo defectos; choice se suma a fruta buena.
    fruta_comercial = max(suma_defectos, 0)
    fruta_sana = max(cant_muestra - fruta_comercial - choice, 0)
    fruta_buena = fruta_sana + choice
    total = fruta_comercial + fruta_buena
    diferencia_muestra = cant_muestra - total

    return {
        "fruta_sana": fruta_sana,
        "fruta_buena": fruta_buena,
        "choice": choice,
        "fruta_comercial": fruta_comercial,
        "total": total,
        "choice_disponible": max_choice,
        "diferencia_muestra": diferencia_muestra
    }


def _porcentaje(valor: float, base: float) -> float:
    if base <= 0:
        return 0.0
    return round((valor / base) * 100, 2)


def calcular_indicadores_operaciones(
    cant_muestra: int,
    suma_defectos: int,
    choice: int,
    kilos_informados: float,
    kilos_comerciales: float,
):

    cant_muestra = int(cant_muestra or 0)
    suma_defectos = int(suma_defectos or 0)
    choice = max(int(choice or 0), 0)
    kilos_informados = max(float(kilos_informados or 0), 0.0)
    kilos_comerciales = max(float(kilos_comerciales or 0), 0.0)

    fruta_comercial = max(suma_defectos, 0)
    fruta_buena = max(cant_muestra - fruta_comercial, 0)
    fruta_sana = max(fruta_buena - choice, 0)

    porc_embalable = _porcentaje(fruta_buena, cant_muestra)
    porc_choice = _porcentaje(choice, cant_muestra)
    porc_descartable = _porcentaje(fruta_comercial, cant_muestra)
    porc_sana = _porcentaje(fruta_sana, cant_muestra)

    kilos_restantes = max(kilos_informados - kilos_comerciales, 0.0)
    kilos_exportables = round(kilos_restantes, 2)
    porc_comercial_kilos = _porcentaje(kilos_comerciales, kilos_informados)
    porc_exportable = _porcentaje(kilos_exportables, kilos_informados)
    porc_fbc = round(((porc_sana + porc_choice) * porc_comercial_kilos) / 100.0, 2)

    return {
        "fruta_comercial": fruta_comercial,
        "fruta_buena": fruta_buena,
        "fruta_sana": fruta_sana,
        "porc_embalable": porc_embalable,
        "porc_sana": porc_sana,
        "porc_choice": porc_choice,
        "porc_descartable": porc_descartable,
        "porc_comercial_kilos": porc_comercial_kilos,
        "porc_exportable": porc_exportable,
        "porc_fbc": porc_fbc,
        "kilos_restantes": kilos_restantes,
        "kilos_exportables": kilos_exportables,
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
        st.metric("Fruta Comercial (defectos)", resultado["fruta_comercial"])

    with col2:
        st.metric("Fruta Buena (Sana + Choice)", resultado["fruta_buena"])

    with col3:
        choice = st.number_input(
            "Choice (acumulado)",
            min_value=0,
            step=1,
            format="%d",
            key=choice_key,
            disabled=choice_disabled
        )
        st.caption(f"Disponible maximo sugerido: {resultado['choice_disponible']}")

    resultado = calcular_resultado(cant_muestra, suma_defectos, choice)
    acumulado = resultado["fruta_comercial"] + resultado["choice"]
    diferencia = cant_muestra - acumulado

    if diferencia < 0:
        fondo = "#3f1d1d"
        borde = "#dc2626"
        texto = "#fecaca"
        estado = f"Defectos + Choice exceden la muestra por {abs(diferencia)} unidad(es)"
    elif diferencia == 0:
        fondo = "#17351f"
        borde = "#16a34a"
        texto = "#bbf7d0"
        estado = "Defectos + Choice ya completan toda la muestra"
    else:
        fondo = "#132b45"
        borde = "#2563eb"
        texto = "#bfdbfe"
        estado = f"Pendiente por asignar: {diferencia} unidad(es)"

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
                <div style="font-size: 0.85rem; opacity: 0.9;">Defectos + Choice</div>
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
            st.caption("Solo aplica para centro 0001 - [sin definir].")

    return {
        "porc_export_manual": porc_export_manual,
        "velocidad_manual": velocidad_manual,
        "aplica_velocidad_tercero": aplica_velocidad_tercero,
    }
