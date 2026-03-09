from engine import cargar_productores, cargar_especies


def warm_cache():
    try:
        cargar_productores()
    except Exception:
        pass

    try:
        cargar_especies()
    except Exception:
        pass