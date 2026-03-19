def validar_formulario(
    nro_lote: str,
    centro: str,
    cant_muestra: int,
    suma_defectos: int,
    fruta_comercial: int,
    fruta_sana: int,
    choice: int,
    verificador: str
):
    errores = []

    if not nro_lote.strip():
        errores.append("Debe ingresar N° Lote")

    #if not centro.strip():
    #    errores.append("Debe ingresar Centro")

    if not verificador.strip():
        errores.append("Debe ingresar Verificador")

    choice_maximo = max(cant_muestra - suma_defectos, 0)
    total_resultado = fruta_comercial + fruta_sana

    if suma_defectos > cant_muestra:
        errores.append(
            f"Defectos acumulados ({suma_defectos}) no pueden superar la muestra ({cant_muestra})"
        )

    if choice > choice_maximo:
        errores.append(
            f"Choice ({choice}) no puede superar la disponibilidad restante ({choice_maximo})"
        )

    if fruta_comercial != suma_defectos + choice:
        errores.append(
            "Fruta Comercial debe ser igual a Defectos + Choice"
        )

    if total_resultado > cant_muestra:
        errores.append(
            f"Resultado acumulado ({total_resultado}) supera la muestra ({cant_muestra})"
        )
    elif total_resultado < cant_muestra:
        errores.append(
            f"Resultado acumulado ({total_resultado}) aun no completa la muestra ({cant_muestra})"
        )

    return errores
