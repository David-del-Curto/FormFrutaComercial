def validar_formulario(
    nro_lote: str,
    centro: str,
    cant_muestra: int,
    suma_defectos: int,
    fruta_sana: int,
    choice: int,
    verificador: str
):
    errores = []

    if not nro_lote.strip():
        errores.append("Debe ingresar N° Lote")

    if not centro.strip():
        errores.append("Debe ingresar Centro")

    if not verificador.strip():
        errores.append("Debe ingresar Verificador")

    total_con_choice = suma_defectos + fruta_sana + choice

    if total_con_choice != cant_muestra:
        errores.append(
            f"Defectos + Choice + Fruta Sana ({total_con_choice}) debe ser igual a la muestra ({cant_muestra})"
        )

    return errores
