def validar_formulario(
    nro_lote: str,
    centro: str,
    cant_muestra: int,
    suma_defectos: int,
    fruta_comercial: int,
    fruta_sana: int,
    choice: int,
    verificador: str,
    velocidad_kgh: float,
    kg_ultima_hora: int,
):
    errores = []

    if not nro_lote.strip():
        errores.append("Debe ingresar N° Lote")

    # if not centro.strip():
    #     errores.append("Debe ingresar Centro")

    if not verificador.strip():
        errores.append("Debe ingresar Verificador")

    choice_maximo = max(cant_muestra - suma_defectos, 0)
    total_resultado = fruta_comercial + fruta_sana + choice

    if suma_defectos > cant_muestra:
        errores.append(
            f"Defectos acumulados ({suma_defectos}) no pueden superar la muestra ({cant_muestra})"
        )

    if choice > choice_maximo:
        errores.append(
            f"Choice ({choice}) no puede superar la disponibilidad restante ({choice_maximo})"
        )

    if fruta_comercial != suma_defectos:
        errores.append(
            "Fruta Comercial debe ser igual a Defectos"
        )

    velocidad_kgh = float(velocidad_kgh or 0)
    kg_ultima_hora = int(kg_ultima_hora or 0)

    if kg_ultima_hora > 0 and velocidad_kgh <= 0:
        errores.append(
            "Para informar Kilos Fruta Comercial (última hora), Velocidad Kg/h debe ser mayor a 0."
        )
    elif velocidad_kgh > 0 and kg_ultima_hora > velocidad_kgh:
        velocidad_txt = int(velocidad_kgh) if velocidad_kgh.is_integer() else round(velocidad_kgh, 2)
        errores.append(
            f"Kilos Fruta Comercial (última hora) ({kg_ultima_hora}) no puede superar Velocidad Kg/h ({velocidad_txt})."
        )

    if total_resultado > cant_muestra:
        errores.append(
            f"Resultado acumulado ({total_resultado}) supera la muestra ({cant_muestra})"
        )
    elif total_resultado < cant_muestra:
        errores.append(
            f"Resultado acumulado ({total_resultado}) aún no completa la muestra ({cant_muestra})"
        )

    return errores
