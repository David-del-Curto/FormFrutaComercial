# Contrato Staging DW Fase 0

## Objetivo

Dejar fijo el contrato entre:

- captura local en SQLite;
- exportador `scripts/extract_dw_staging_payload.py`;
- tablas `stg.FormularioHeader` y `stg.FormularioDefecto`.

Este documento define la version operativa vigente para la Fase 0.

La Fase 1 agrega metadata ETL sobre `stg`, pero no cambia el payload funcional del exportador.

## Decisiones cerradas

- El exportador debe emitir exactamente las columnas de `stg.FormularioHeader`.
- `kg_ultima_hora` queda fuera del contrato DW vigente.
- `observaciones` se mantiene en el contrato de staging.
- `campos_pendientes` se mantiene en staging para trazabilidad.
- `especie_principal_linea` forma parte del contrato y puede venir nulo.
- La business key oficial del formulario es `(source_system, source_business_key)`.
- La dimension de fechas del DW ya existe como `dbo.Dim_Date`.

## Llaves naturales oficiales

- formulario: `source_system + source_business_key`
- centro logistico: `CodCentro_SAP`
- productor: `CodProductor_SAP`
- especie: `Especie`
- variedad: `Especie + Variedad`
- linea: `CodCentro_SAP + linea_codigo`
- lugar seleccion: `lugar_codigo`
- turno: `turno_codigo`
- defecto: `codigo_defecto`
- fecha DW: `dbo.Dim_Date.idFecha` con base en la fecha calendario

## Contrato `stg.FormularioHeader`

Orden oficial de columnas:

1. `source_system`
2. `source_business_key`
3. `source_record_id`
4. `fecha`
5. `fecha_operacional`
6. `turno_codigo`
7. `turno_nombre`
8. `rango_turno`
9. `linea_codigo`
10. `linea_nombre`
11. `especie`
12. `especie_principal_linea`
13. `variedad`
14. `lote`
15. `centro_codigo`
16. `centro_nombre`
17. `centro_display`
18. `productor_codigo`
19. `productor_nombre`
20. `productor_display`
21. `lugar_codigo`
22. `lugar_nombre`
23. `verificador`
24. `observaciones`
25. `cant_muestra`
26. `suma_defectos`
27. `fruta_comercial`
28. `fruta_sana`
29. `choice`
30. `porc_exportable`
31. `porc_embalable`
32. `porc_choice`
33. `porc_descartable`
34. `porc_export_manual`
35. `velocidad_kgh`
36. `velocidad_manual`
37. `centro_sin_definir`
38. `estado_formulario`
39. `es_completo`
40. `campos_pendientes`
41. `created_at`
42. `updated_at`

## Mapping actual desde SQLite local

- `source_record_id` <- `registro.id_registro`
- `linea_codigo` <- `registro.linea`
- `linea_nombre` <- `registro.linea`
- `especie_principal_linea` <- `NULL` en Fase 0
- `observaciones` <- `registro.observaciones`
- `campos_pendientes` <- `registro.campos_pendientes`
- `created_at` <- `registro.created_at`
- `updated_at` <- `registro.updated_at`

Campos excluidos intencionalmente:

- `kg_ultima_hora`

Razon:

- existe en la captura operacional;
- no existe en `stg.FormularioHeader`;
- no tiene aun semantica DW cerrada en hechos o marts.

## Contrato `stg.FormularioDefecto`

Orden oficial de columnas:

1. `source_system`
2. `source_business_key`
3. `codigo_defecto`
4. `nombre_defecto`
5. `cantidad`
6. `updated_at`

## Reglas de validacion funcional minima

- `fruta_comercial = suma_defectos`
- `fruta_sana + choice + suma_defectos = cant_muestra`
- `cant_muestra > 0`
- `choice >= 0`
- `suma_defectos >= 0`
- solo promover a core registros con `es_completo = 1`

## Integracion con `dbo.Dim_Date`

El DW ya dispone de `dbo.Dim_Date` con los atributos observados en `date.csv`:

- `idFecha`
- `FechaCompleta`
- atributos de anio, mes, semana, dia y temporada

Uso recomendado para la siguiente fase:

- `fecha_key` = `YEAR(fecha) * 10000 + MONTH(fecha) * 100 + DAY(fecha)`
- `fecha_operacional_key` = `YEAR(fecha_operacional) * 10000 + MONTH(fecha_operacional) * 100 + DAY(fecha_operacional)`

Alternativamente, la resolucion puede hacerse por join sobre `FechaCompleta`.

## Salida esperada del exportador

Comando:

```powershell
python scripts/extract_dw_staging_payload.py --fecha-operacional 2026-04-21 --output-dir .\out
```

Archivos esperados:

- `FormularioHeader.csv`
- `FormularioDefecto.csv`

El archivo `FormularioHeader.csv` debe respetar exactamente el orden de columnas definido arriba.

El exportador ademas reporta advertencias si detecta desalineaciones contra el contrato vigente, por ejemplo:

- `fruta_comercial != suma_defectos`
- `fruta_sana + choice + suma_defectos != cant_muestra`
