from datetime import datetime

import pandas as pd
import streamlit as st

from engine import (
    cargar_centros,
    cargar_especies,
    cargar_productores,
    cargar_variedades,
)
from core.business_rules import obtener_reglas_centro
from core.catalogos import DEFECTOS, LINEAS, LUGAR_SELECCION, obtener_lineas_por_centro
from core.dashboard import render_como_vamos
from core.form_state import load_record_into_session, reset_form_state
from core.forms import (
    calcular_indicadores_operaciones,
    render_bloque_defectos,
    render_bloque_resultado,
    render_bloque_terceros,
)
from core.ui import mostrar_resumen_dialog, render_header
from core.validators import validar_formulario
from services.cache_sqlite import init_cache
from services.cache_warmup import warm_cache
from services.local_store import (
    evaluar_estado_formulario,
    format_registro_option,
    get_current_operational_date,
    get_defectos_df,
    get_registro,
    get_registro_defectos,
    get_registros_df,
    init_local_store,
    list_recent_registros,
)
from services.save_form import guardar_formulario_staging


def _ensure_default_state(key, value):
    if key not in st.session_state:
        st.session_state[key] = value


def _ensure_option_state(key, options):
    if not options:
        st.session_state.pop(key, None)
        return None

    if key not in st.session_state or st.session_state[key] not in options:
        st.session_state[key] = options[0]

    return st.session_state[key]


def _ensure_nullable_option_state(key, options):
    if key not in st.session_state or st.session_state[key] not in options:
        st.session_state[key] = None

    return st.session_state[key]


def _validar_formulario_compat(
    nro_lote,
    centro,
    cant_muestra,
    suma_defectos,
    fruta_comercial,
    fruta_sana,
    choice,
    verificador,
    velocidad_kgh,
    kg_ultima_hora,
):
    try:
        return validar_formulario(
            nro_lote,
            centro,
            cant_muestra,
            suma_defectos,
            fruta_comercial,
            fruta_sana,
            choice,
            verificador,
            velocidad_kgh,
            kg_ultima_hora,
        )
    except TypeError as exc:
        # Compatibilidad con instancia caliente de Streamlit que mantiene
        # una version anterior de core.validators (firma de 8 parametros).
        if "takes 8 positional arguments but 10 were given" not in str(exc):
            raise

        errores = validar_formulario(
            nro_lote,
            centro,
            cant_muestra,
            suma_defectos,
            fruta_comercial,
            fruta_sana,
            choice,
            verificador,
        )

        velocidad_val = float(velocidad_kgh or 0)
        kg_val = int(kg_ultima_hora or 0)
        if kg_val > 0 and velocidad_val <= 0:
            errores.append(
                "Para informar Kilos Fruta Comercial (ultima hora), Velocidad Kg/h debe ser mayor a 0."
            )
        elif velocidad_val > 0 and kg_val > velocidad_val:
            velocidad_txt = int(velocidad_val) if velocidad_val.is_integer() else round(velocidad_val, 2)
            errores.append(
                f"Kilos Fruta Comercial (ultima hora) ({kg_val}) no puede superar Velocidad Kg/h ({velocidad_txt})."
            )

        return errores


st.set_page_config(
    page_title="Planilla Fruta Comercial",
    layout="wide"
)

init_cache()
init_local_store()

if not st.session_state.get("_dimensions_warmed"):
    warm_cache()
    st.session_state["_dimensions_warmed"] = True


def _reset_after_save(saved):
    estado = saved["estado_formulario"].upper()
    pendientes = saved["campos_pendientes"] or "Sin pendientes"
    st.session_state["post_save_notice"] = (
        f"Registro #{saved['id_registro']} guardado. "
        f"Estado: {estado}. Pendientes: {pendientes}"
    )
    _queue_form_reset()


def _queue_form_reset():
    st.session_state["_pending_form_reset"] = True
    st.session_state.pop("_pending_form_load_id", None)


def _queue_form_load(record_id):
    _queue_form_reset()
    st.session_state["_pending_form_load_id"] = record_id

render_header("images/Imagen2.jpg", "Planilla Fruta Comercial")

tab_formulario, tab_bi = st.tabs(["Formulario", "Estatus Operación"])

with tab_formulario:
    st.caption(
        f"Dia operacional actual: {get_current_operational_date()} | "
        "Turnos: 07:00-17:00, 17:00-02:00"
    )

    post_save_notice = st.session_state.pop("post_save_notice", None)
    if post_save_notice:
        st.success(post_save_notice)

    df_productores = cargar_productores()
    productores = df_productores.to_dict("records")

    df_centros = cargar_centros()
    centros = df_centros.to_dict("records")

    df_especies = cargar_especies()
    especies = df_especies.to_dict("records")

    if st.session_state.pop("_pending_form_reset", False):
        reset_form_state()
        st.session_state["editing_record_id"] = None
        st.session_state["registro_local_selector"] = None

    pending_form_load_id = st.session_state.pop("_pending_form_load_id", None)
    if pending_form_load_id is not None:
        registro_local = get_registro(pending_form_load_id)
        if registro_local is not None:
            defectos_local = get_registro_defectos(pending_form_load_id)
            especie_registro = next(
                (item for item in especies if item["Especie"] == registro_local["especie"]),
                especies[0] if especies else None
            )
            variedades_carga = (
                cargar_variedades(int(especie_registro["idEspecie"])).to_dict("records")
                if especie_registro is not None
                else []
            )

            load_record_into_session(
                registro_local,
                defectos_local,
                productores,
                centros,
                especies,
                variedades_carga,
            )
            st.session_state["registro_local_selector"] = pending_form_load_id
        else:
            st.session_state["editing_record_id"] = None
            st.session_state["registro_local_selector"] = None
            st.session_state["post_save_notice"] = (
                f"El registro #{pending_form_load_id} ya no esta disponible."
            )

    registros_recientes = list_recent_registros(limit=150)
    registros_editables = [
        registro
        for registro in registros_recientes
        if int(registro.get("es_completo") or 0) == 0
    ]
    registros_editables_map = {
        registro["id_registro"]: registro
        for registro in registros_editables
    }
    opciones_registro = list(registros_editables_map.keys())
    _ensure_nullable_option_state("registro_local_selector", opciones_registro)

    st.subheader("Gestion Formularios")

    col_sel, col_load, col_new = st.columns([4, 1, 1])

    with col_sel:
        registro_seleccionado = st.selectbox(
            "Registros para editar",
            options=opciones_registro,
            index=None,
            format_func=lambda x: format_registro_option(registros_editables_map[x]),
            key="registro_local_selector",
            placeholder="Seleccione un registro para editar",
            disabled=not bool(opciones_registro),
        )

    with col_load:
        cargar_pressed = st.button(
            "Cargar",
            width='content',
            disabled=registro_seleccionado is None
        )

    with col_new:
        nuevo_pressed = st.button("Nuevo", width='content')

    if not registros_editables:
        st.caption("No hay borradores pendientes por editar en este momento.")

    if nuevo_pressed:
        _queue_form_reset()
        st.rerun()

    if cargar_pressed and registro_seleccionado is not None:
        _queue_form_load(registro_seleccionado)
        st.rerun()

    editing_record_id = st.session_state.get("editing_record_id")
    registro_editando = get_registro(editing_record_id) if editing_record_id else None
    if editing_record_id and registro_editando is None:
        st.session_state["post_save_notice"] = (
            f"El registro local #{editing_record_id} ya no esta disponible."
        )
        _queue_form_reset()
        st.rerun()

    editando_borrador = registro_editando is not None and int(registro_editando.get("es_completo") or 0) == 0
    editando_completo = registro_editando is not None and int(registro_editando.get("es_completo") or 0) == 1
    captura_bloqueada = registro_editando is not None
    velocidades_bloqueadas = not editando_borrador
    puede_guardar = not editando_completo

    if registro_editando is not None:
        estado = registro_editando.get("estado_formulario", "borrador").upper()
        pendientes = registro_editando.get("campos_pendientes") or "Sin pendientes"
        if editando_borrador:
            st.info(
                f"Editando registro #{editing_record_id} | Estado: {estado} | "
                f"Pendientes: {pendientes}. En esta etapa solo se completan los campos pendientes."
            )
        else:
            st.success(
                f"Registro #{editing_record_id} | Estado: {estado}. "
                "Este formulario ya esta completo y no puede volver a editarse."
            )
    else:
        st.caption(
            "Primer paso: captura del formulario. Los indicadores de velocidad se completan en una segunda etapa."
        )

    _ensure_default_state("form_verificador", "")
    _ensure_default_state("form_fecha", datetime.today())
    _ensure_default_state("form_nro_lote", "")
    _ensure_default_state("form_cant_muestra", 0)
    _ensure_default_state("form_lugar_codigo", next(iter(LUGAR_SELECCION)))
    _ensure_default_state("velocidad_kgh", 0.0)
    _ensure_default_state("kg_ultima_hora", 0)
    _ensure_default_state("form_observaciones", "")
    _ensure_default_state("editing_record_id", None)

    _ensure_option_state("form_productor", productores)
    centro_default = _ensure_option_state("form_centro", centros)
    _ensure_option_state("form_linea", obtener_lineas_por_centro(centro_default))
    especie_default = _ensure_option_state("form_especie", especies)

    variedades = (
        cargar_variedades(int(especie_default["idEspecie"])).to_dict("records")
        if especie_default is not None
        else []
    )
    _ensure_option_state("form_variedad", variedades)

    st.divider()
    st.subheader("Encabezado")

    col1, col2 = st.columns(2)

    with col1:
        verificador = st.text_input(
            "Verificador",
            key="form_verificador",
            placeholder="Ingrese verificador",
            disabled=captura_bloqueada
        )

    with col2:
        centro = st.selectbox(
            "Centro Logistico",
            centros,
            format_func=lambda x: f"{x['CodCentro_SAP']} - {x['Centro_Logistico']}",
            key="form_centro",
            disabled=captura_bloqueada
        )

    reglas_centro = obtener_reglas_centro(centro)
    centro_sin_definir = reglas_centro["centro_sin_definir"]
    aplica_velocidad_tercero = reglas_centro["usa_velocidad_tercero"]

    col1, col2, col3 = st.columns(3)

    with col1:
        fecha = st.date_input("Fecha", key="form_fecha", disabled=captura_bloqueada)

        productor = st.selectbox(
            "Productor",
            productores,
            format_func=lambda x: f"{x['CodProductor_SAP']} - {x['Productor']}",
            key="form_productor",
            disabled=captura_bloqueada
        )

        nro_lote = st.text_input(
            "Nro Lote",
            key="form_nro_lote",
            placeholder="Ej: 1505475-01",
            disabled=captura_bloqueada
        )

    with col2:
        lineas_centro = obtener_lineas_por_centro(centro)
        _ensure_option_state("form_linea", lineas_centro)

        linea = st.selectbox(
            "Linea",
            options=lineas_centro,
            format_func=lambda x: LINEAS.get(x, x),
            key="form_linea",
            disabled=captura_bloqueada
        )

        especie = st.selectbox(
            "Especie",
            especies,
            format_func=lambda x: x["Especie"],
            key="form_especie",
            disabled=captura_bloqueada
        )

        variedades = cargar_variedades(int(especie["idEspecie"])).to_dict("records")
        _ensure_option_state("form_variedad", variedades)

        cant_muestra = st.number_input(
            "Cantidad Muestra Frutos",
            min_value=0,
            step=1,
            key="form_cant_muestra",
            disabled=captura_bloqueada
        )

    with col3:
        lugar_codigo = st.selectbox(
            "Lugar de seleccion",
            options=list(LUGAR_SELECCION.keys()),
            format_func=lambda x: LUGAR_SELECCION[x],
            key="form_lugar_codigo",
            disabled=captura_bloqueada
        )

        variedad = st.selectbox(
            "Variedad",
            variedades,
            format_func=lambda x: x["Variedad"],
            key="form_variedad",
            disabled=captura_bloqueada
        )

        col_velocidad, col_kg_ultima_hora = st.columns(2)

        with col_velocidad:
            velocidad_kgh = st.number_input(
                "Velocidad Kg/h",
                min_value=0.0,
                step=0.1,
                key="velocidad_kgh",
                disabled=velocidades_bloqueadas
            )

        with col_kg_ultima_hora:
            kg_ultima_hora = st.number_input(
                "Kilos Fruta Comercial (ultima hora)",
                min_value=0,
                step=1,
                key="kg_ultima_hora",
                disabled=velocidades_bloqueadas
            )

    st.divider()

    defectos, suma_defectos = render_bloque_defectos(disabled=captura_bloqueada)

    st.divider()

    resultado = render_bloque_resultado(
        cant_muestra,
        suma_defectos,
        choice_disabled=captura_bloqueada
    )

    st.divider()

    terceros = render_bloque_terceros(
        centro,
        porc_export_disabled=editando_completo,
        velocidad_disabled=velocidades_bloqueadas
    )

    st.divider()

    observaciones = st.text_area(
        "Observaciones",
        key="form_observaciones",
        disabled=captura_bloqueada
    )

    if editando_borrador:
        submit_label = "Completar y Guardar"
    else:
        submit_label = "Guardar Formulario"

    submit = st.button(
        submit_label,
        type="primary",
        width="stretch",
        disabled=not puede_guardar
    )

    if submit:
        centro_display = f"{centro['CodCentro_SAP']} - {centro['Centro_Logistico']}"
        productor_display = f"{productor['CodProductor_SAP']} - {productor['Productor']}"
        indicadores_operaciones = calcular_indicadores_operaciones(
            cant_muestra,
            suma_defectos,
            resultado["choice"],
            velocidad_kgh,
            kg_ultima_hora,
        )

        errores = _validar_formulario_compat(
            nro_lote,
            centro,
            cant_muestra,
            suma_defectos,
            resultado["fruta_comercial"],
            resultado["fruta_sana"],
            resultado["choice"],
            verificador,
            velocidad_kgh,
            kg_ultima_hora,
        )

        porc_embalable = indicadores_operaciones["porc_embalable"]

        if centro_sin_definir:
            porc_exportacion = terceros["porc_export_manual"]
            label_exportacion = "% Exportable (manual)"
        else:
            porc_exportacion = indicadores_operaciones["porc_exportable"]
            label_exportacion = "% Exportable"

        if errores:
            for error in errores:
                st.error(error)
            st.stop()

        porc_choice = indicadores_operaciones["porc_choice"]
        porc_descartable = indicadores_operaciones["porc_descartable"]
        porc_comercial_kilos = indicadores_operaciones["porc_comercial_kilos"]
        porc_fbc = indicadores_operaciones["porc_fbc"]
        kilos_exportables = indicadores_operaciones["kilos_exportables"]
        base_kilos_disponible = float(velocidad_kgh or 0) > 0

        exportable_modal = porc_exportacion
        comercial_modal = porc_comercial_kilos if base_kilos_disponible else "Pendiente"
        fbc_modal = porc_fbc if base_kilos_disponible else "Pendiente"
        if not centro_sin_definir and not base_kilos_disponible:
            exportable_modal = "Pendiente"

        defectos_guardar = {
            codigo: int(valor)
            for codigo, valor in defectos.items()
            if valor > 0
        }
        defectos_resumen = {
            DEFECTOS[codigo]: valor
            for codigo, valor in defectos_guardar.items()
        }

        df_defectos = pd.DataFrame(
            list(defectos_resumen.items()),
            columns=["Defecto", "Cantidad"]
        )

        if not df_defectos.empty:
            df_defectos = df_defectos.sort_values("Cantidad", ascending=False)
            df_defectos["% Muestra"] = (
                df_defectos["Cantidad"] / cant_muestra * 100
            ).round(1).astype(str) + " %"

        payload = {
            "fecha": fecha.strftime("%Y-%m-%d"),
            "linea": linea,
            "especie": especie["Especie"],
            "variedad": variedad["Variedad"],
            "lote": nro_lote,
            "centro_codigo": centro["CodCentro_SAP"],
            "centro_nombre": centro["Centro_Logistico"],
            "centro_display": centro_display,
            "productor_codigo": productor["CodProductor_SAP"],
            "productor_nombre": productor["Productor"],
            "productor_display": productor_display,
            "cant_muestra": cant_muestra,
            "suma_defectos": suma_defectos,
            "fruta_comercial": resultado["fruta_comercial"],
            "fruta_sana": resultado["fruta_sana"],
            "choice": resultado["choice"],
            "porc_exportable": porc_exportacion,
            "porc_embalable": porc_embalable,
            "porc_choice": porc_choice,
            "porc_descartable": porc_descartable,
            "observaciones": observaciones,
            "verificador": verificador,
            "lugar_codigo": lugar_codigo,
            "lugar_nombre": LUGAR_SELECCION[lugar_codigo],
            "velocidad_kgh": velocidad_kgh,
            "kg_ultima_hora": kg_ultima_hora,
            "porc_export_manual": terceros["porc_export_manual"],
            "velocidad_manual": terceros["velocidad_manual"],
            "centro_sin_definir": centro_sin_definir,
            "defectos_nombres": DEFECTOS,
        }

        estado_estimado = evaluar_estado_formulario(payload)
        resumen = {
            "Registro Local": st.session_state.get("editing_record_id") or "Nuevo",
            "Estado estimado": estado_estimado["estado_formulario"].upper(),
            "Pendientes": estado_estimado["campos_pendientes"] or "Sin pendientes",
            "Verificador": verificador,
            "Fecha": fecha.strftime("%Y-%m-%d"),
            "Linea": LINEAS.get(linea, linea),
            "Especie": especie["Especie"],
            "Variedad": variedad["Variedad"],
            "Nro Lote": nro_lote,
            "Centro": centro_display,
            "Productor": productor_display,
            "Cant Muestra": cant_muestra,
            "Lugar": LUGAR_SELECCION[lugar_codigo],
            "Fruta Comercial (captura)": resultado["fruta_comercial"],
            "Fruta Buena (Sana + Choice)": resultado["fruta_buena"],
            "Fruta Sana (captura)": resultado["fruta_sana"],
            "Choice (captura)": resultado["choice"],
            "Velocidad Kg/h": velocidad_kgh,
            "Kilos Fruta Comercial (ultima hora)": kg_ultima_hora,
            "Kg Exportable (Velocidad - Comercial)": kilos_exportables,
            "Velocidad Tercero Kg/h": (
                terceros["velocidad_manual"]
                if aplica_velocidad_tercero
                else "No aplica"
            ),
            label_exportacion: exportable_modal,
            "% Embalable": porc_embalable,
            "% Comercial Kg": comercial_modal,
            "% FBC": fbc_modal,
            "% Choice": porc_choice,
            "% Descartable": porc_descartable,
        }
        if not base_kilos_disponible:
            resumen["Nota KPI kilos"] = (
                "Complete Velocidad Kg/h para calcular % Exportable, % Comercial Kg y % FBC."
            )

        def confirmar():
            saved = guardar_formulario_staging(
                payload,
                defectos_guardar,
                record_id=st.session_state.get("editing_record_id")
            )
            _reset_after_save(saved)

        metricas = [
            (label_exportacion, exportable_modal),
            ("% Embalable", porc_embalable),
            ("% Comercial Kg", comercial_modal),
            ("% FBC", fbc_modal),
            ("% Descartable", porc_descartable),
        ]

        mostrar_resumen_dialog(
            resumen,
            df_defectos,
            metricas,
            confirmar
        )

    st.divider()
    st.subheader("Registros Locales Recientes")

    registros_tabla = list_recent_registros(limit=25)
    if registros_tabla:
        df_registros_tabla = pd.DataFrame(registros_tabla)[[
            "id_registro",
            "updated_at",
            "fecha_operacional",
            "turno_nombre",
            "lote",
            "especie",
            "cant_muestra",
            "estado_formulario",
            "campos_pendientes",
        ]].rename(columns={
            "id_registro": "ID",
            "updated_at": "Actualizado",
            "fecha_operacional": "Dia Operacional",
            "turno_nombre": "Turno",
            "lote": "Lote",
            "especie": "Especie",
            "cant_muestra": "Muestra",
            "estado_formulario": "Estado",
            "campos_pendientes": "Pendientes",
        })
        st.dataframe(df_registros_tabla, hide_index=True, width='stretch')
    else:
        st.info("Aun no hay registros guardados localmente.")

with tab_bi:
    fecha_operacional_bi = st.date_input(
        "Dia operacional",
        value=datetime.fromisoformat(get_current_operational_date()).date(),
        key="bi_fecha_operacional"
    )

    fecha_operacional_str = fecha_operacional_bi.strftime("%Y-%m-%d")
    registros_df = get_registros_df(fecha_operacional_str)
    defectos_df = get_defectos_df(fecha_operacional_str)

    render_como_vamos(registros_df, defectos_df, fecha_operacional_str)
