from engine import cargar_productores, cargar_especies, cargar_centros


def warm_cache():
    try:
        cargar_productores()
    except Exception:
        pass

    try:
        cargar_especies()
    except Exception:
        pass

    try:
        cargar_centros()
    except Exception:
        pass