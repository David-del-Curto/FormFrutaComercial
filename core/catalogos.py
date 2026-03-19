def _normalizar_centro_codigo(centro) -> str:
    if isinstance(centro, dict):
        value = centro.get("CodCentro_SAP", "")
    else:
        value = centro or ""

    return str(value).strip().upper()


def _build_linea_label(linea: dict) -> str:
    codigo = str(linea["Linea_Codigo"]).strip()
    nombre = str(linea.get("Nombre_Linea") or "").strip()
    return f"{codigo} - {nombre}" if nombre else codigo


LUGAR_SELECCION = {
    "MS": "Mesa Selecci\u00f3n",
    "BC": "Bins Comercial",
    "TP": "Trypack",
}

LINEAS_BASE = {
    "1": "Linea 1",
    "2": "Linea 2",
    "3": "Linea 3",
}

LINEAS_DIM = (
    {"Centro": "DC05", "Linea_Codigo": "LIN_01", "Especie_Principal": "PERAS", "Nombre_Linea": ""},
    {"Centro": "DC05", "Linea_Codigo": "LIN_02", "Especie_Principal": "MANZANAS", "Nombre_Linea": ""},
    {"Centro": "DC05", "Linea_Codigo": "LIN_03", "Especie_Principal": "DAGEN", "Nombre_Linea": ""},
    {"Centro": "DC05", "Linea_Codigo": "LIN_04", "Especie_Principal": "CEREZAS", "Nombre_Linea": "MAF"},
    {"Centro": "DC05", "Linea_Codigo": "LIN_05", "Especie_Principal": "CEREZAS", "Nombre_Linea": "UNITEC"},
    {"Centro": "DC05", "Linea_Codigo": "LIN_06", "Especie_Principal": "DAGEN", "Nombre_Linea": ""},
    {"Centro": "DC05", "Linea_Codigo": "LIN_07", "Especie_Principal": "PERAS", "Nombre_Linea": ""},
    {"Centro": "DC10", "Linea_Codigo": "LIN_03", "Especie_Principal": "ARANDANOS", "Nombre_Linea": ""},
    {
        "Centro": "DC10",
        "Linea_Codigo": "LIN_04_G_CAMPO",
        "Especie_Principal": "ARANDANOS GRANEL DE CAMPO",
        "Nombre_Linea": "",
    },
    {"Centro": "DC10", "Linea_Codigo": "REEMBALAJE", "Especie_Principal": "ARANDANOS", "Nombre_Linea": ""},
)

LINEAS = dict(LINEAS_BASE)
LINEAS_POR_CENTRO = {}
LINEAS_METADATA = {}

for linea in LINEAS_DIM:
    centro_codigo = _normalizar_centro_codigo(linea["Centro"])
    linea_codigo = linea["Linea_Codigo"]

    LINEAS[linea_codigo] = _build_linea_label(linea)
    LINEAS_METADATA[linea_codigo] = dict(linea)
    LINEAS_POR_CENTRO.setdefault(centro_codigo, []).append(linea_codigo)


def obtener_lineas_por_centro(centro):
    centro_codigo = _normalizar_centro_codigo(centro)
    lineas = LINEAS_POR_CENTRO.get(centro_codigo)

    if lineas:
        return list(lineas)

    return list(LINEAS_BASE.keys())


DEFECTOS = {
    "HAO": "Herida Abierta (Oxidada)",
    "HAF": "Herida Abierta (Fresca)",
    "MAC": "Machuc\u00f3n",
    "PAR": "Partidura",
    "GSS": "Golpe Sol Severo",
    "CRA": "Cracking",
    "DES": "Deshidrataci\u00f3n",
    "DP": "Desgarro Pedicelar",
    "LEN": "Lenticelosis",
    "BP": "Bitter Pit",
    "MR": "Manchas - Roce",
    "RLP": "Roce (L\u00ednea Proceso)",
    "FC": "Falta Color",
    "HC": "Herida Cicatrizada",
    "DI": "Da\u00f1o Insecto",
    "DEF": "Deforme",
    "RAM": "Ramaleo",
    "RG": "Roce Grave",
    "RUS": "Russet Grave",
}
