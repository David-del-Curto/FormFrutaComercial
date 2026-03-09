from engine import get_engine


def guardar_formulario_staging(payload, defectos):

    engine = get_engine()

    with engine.begin() as conn:

        result = conn.exec_driver_sql("""
        INSERT INTO registro (
            fecha,
            linea,
            especie,
            variedad,
            lote,
            productor,
            cant_muestra,
            fruta_sana,
            choice,
            porc_exportable,
            porc_embalable,
            observaciones,
            verificador,
            lugar_codigo,
            velocidad_kgh,
            porc_export_manual,
            velocidad_manual,
            created_at,
            etl_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 0)
        """,
        (
            payload["fecha"],
            payload["linea"],
            payload["especie"],
            payload["variedad"],
            payload["lote"],
            payload["productor"],
            payload["cant_muestra"],
            payload["fruta_sana"],
            payload["choice"],
            payload["porc_exportable"],
            payload["porc_embalable"],
            payload["observaciones"],
            payload["verificador"],
            payload["lugar_codigo"],
            payload["velocidad_kgh"],
            payload["porc_export_manual"],
            payload["velocidad_manual"]
        ))

        id_registro = result.lastrowid

        for codigo, cantidad in defectos.items():

            if cantidad > 0:

                conn.exec_driver_sql("""
                INSERT INTO registro_defectos
                (id_registro, codigo_defecto, cantidad)
                VALUES (?, ?, ?)
                """, (id_registro, codigo, cantidad))