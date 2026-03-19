from services.local_store import save_formulario_local


def guardar_formulario_staging(payload, defectos, record_id=None):
    return save_formulario_local(payload, defectos, record_id=record_id)
