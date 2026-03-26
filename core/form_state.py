from datetime import date

import streamlit as st

from core.catalogos import (
    DEFECTOS,
    LINEAS,
    LUGAR_SELECCION,
    obtener_lineas_por_centro,
)


FORM_STATE_KEYS = [
    "editing_record_id",
    "form_verificador",
    "form_fecha",
    "form_productor",
    "form_nro_lote",
    "form_centro",
    "form_linea",
    "form_especie",
    "form_cant_muestra",
    "form_lugar_codigo",
    "form_variedad",
    "velocidad_kgh",
    "kg_ultima_hora",
    "ingreso_manual_kg_ultima_hora",
    "form_observaciones",
    "choice_resultado",
    "porc_export_manual",
    "velocidad_manual",
]


def reset_form_state():
    for key in FORM_STATE_KEYS:
        st.session_state.pop(key, None)

    # Fuerza cero en defectos conocidos para evitar valores "pegados" de widgets.
    for codigo in DEFECTOS:
        st.session_state[f"def_{codigo}"] = 0

    # Limpia claves de defectos obsoletas/no catalogadas.
    claves_catalogo = {f"def_{codigo}" for codigo in DEFECTOS}
    for key in list(st.session_state.keys()):
        if key.startswith("def_") and key not in claves_catalogo:
            st.session_state.pop(key, None)


def _match_option(options, predicate):
    for option in options:
        if predicate(option):
            return option
    return options[0] if options else None


def load_record_into_session(
    registro,
    defectos_registro,
    productores,
    centros,
    especies,
    variedades,
):
    st.session_state["editing_record_id"] = registro["id_registro"]
    st.session_state["form_verificador"] = registro.get("verificador", "")
    st.session_state["form_fecha"] = date.fromisoformat(registro["fecha"])
    st.session_state["form_nro_lote"] = registro.get("lote", "")
    st.session_state["form_cant_muestra"] = int(registro.get("cant_muestra") or 1)
    st.session_state["form_lugar_codigo"] = (
        registro.get("lugar_codigo")
        if registro.get("lugar_codigo") in LUGAR_SELECCION
        else next(iter(LUGAR_SELECCION))
    )
    st.session_state["velocidad_kgh"] = float(registro.get("velocidad_kgh") or 0.0)
    st.session_state["kg_ultima_hora"] = int(registro.get("kg_ultima_hora") or 0)
    st.session_state.pop("ingreso_manual_kg_ultima_hora", None)
    st.session_state["form_observaciones"] = registro.get("observaciones", "")
    st.session_state["choice_resultado"] = int(registro.get("choice") or 0)
    st.session_state["porc_export_manual"] = int(registro.get("porc_export_manual") or 0)
    st.session_state["velocidad_manual"] = float(registro.get("velocidad_manual") or 0.0)

    st.session_state["form_productor"] = _match_option(
        productores,
        lambda x: (
            str(x.get("CodProductor_SAP", "")).strip() == str(registro.get("productor_codigo", "")).strip()
            or str(x.get("Productor", "")).strip() == str(registro.get("productor_nombre", "")).strip()
        )
    )
    st.session_state["form_centro"] = _match_option(
        centros,
        lambda x: (
            str(x.get("CodCentro_SAP", "")).strip() == str(registro.get("centro_codigo", "")).strip()
            or str(x.get("Centro_Logistico", "")).strip() == str(registro.get("centro_nombre", "")).strip()
        )
    )
    lineas_disponibles = obtener_lineas_por_centro(st.session_state["form_centro"])
    st.session_state["form_linea"] = (
        registro.get("linea")
        if registro.get("linea") in lineas_disponibles
        else (lineas_disponibles[0] if lineas_disponibles else next(iter(LINEAS)))
    )
    st.session_state["form_especie"] = _match_option(
        especies,
        lambda x: str(x.get("Especie", "")).strip() == str(registro.get("especie", "")).strip()
    )
    st.session_state["form_variedad"] = _match_option(
        variedades,
        lambda x: str(x.get("Variedad", "")).strip() == str(registro.get("variedad", "")).strip()
    )

    defectos_map = {
        row["codigo_defecto"]: int(row.get("cantidad") or 0)
        for row in defectos_registro
    }
    for codigo in DEFECTOS:
        st.session_state[f"def_{codigo}"] = defectos_map.get(codigo, 0)
