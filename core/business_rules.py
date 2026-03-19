CENTROS_SIN_VELOCIDAD_TERCERO = {"DC02", "DC10"}


def normalizar_centro_codigo(centro) -> str:
    if isinstance(centro, dict):
        value = centro.get("CodCentro_SAP", "")
    else:
        value = centro or ""
    return str(value).strip().upper()


def normalizar_centro_nombre(centro) -> str:
    if isinstance(centro, dict):
        value = centro.get("Centro_Logistico", "")
    else:
        value = ""
    return str(value).strip().lower()


def es_centro_sin_definir(centro) -> bool:
    return (
        normalizar_centro_codigo(centro) == "0001"
        and normalizar_centro_nombre(centro) == "[sin definir]"
    )


def usa_velocidad_tercero(centro) -> bool:
    return normalizar_centro_codigo(centro) not in CENTROS_SIN_VELOCIDAD_TERCERO


def obtener_reglas_centro(centro) -> dict:
    centro_sin_definir = es_centro_sin_definir(centro)
    velocidad_tercero_habilitada = usa_velocidad_tercero(centro)

    return {
        "centro_codigo": normalizar_centro_codigo(centro),
        "centro_sin_definir": centro_sin_definir,
        "usa_velocidad_tercero": velocidad_tercero_habilitada,
        "requiere_velocidad_kgh": True,
        "requiere_velocidad_tercero": velocidad_tercero_habilitada,
        "requiere_export_manual": centro_sin_definir,
    }
