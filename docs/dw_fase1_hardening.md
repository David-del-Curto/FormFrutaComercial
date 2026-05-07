# DW Fase 1 Hardening

## Objetivo

Agregar control operativo al staging del DW:

- trazabilidad por lote;
- metadata de ingesta;
- tablas de rechazo;
- manejo de excepciones conocidas;
- control basico de calidad antes de promover a hechos.

## Script

- [azure_dw_form_fruta_comercial_phase1_hardening.sql](C:/DEV/FormFrutaComercial/sql/azure_dw_form_fruta_comercial_phase1_hardening.sql)

Este script es incremental y se ejecuta despues de:

- [azure_dw_form_fruta_comercial_refactored.sql](C:/DEV/FormFrutaComercial/sql/azure_dw_form_fruta_comercial_refactored.sql)

## Objetos nuevos

### Esquema `etl`

- `etl.BatchControl`
- `etl.FormularioExcepcion`
- `etl.RechazoFormularioHeader`
- `etl.RechazoFormularioDefecto`
- `etl.sp_start_formulario_batch`

### Nuevas columnas en `stg.FormularioHeader`

- `batch_id`
- `source_run_id`
- `row_hash`
- `ingested_at`
- `rejected_at`
- `reject_reason`

### Nuevas columnas en `stg.FormularioDefecto`

- `batch_id`
- `source_run_id`
- `row_hash`
- `ingested_at`
- `rejected_at`
- `reject_reason`

## Flujo recomendado

1. Abrir batch:

```sql
DECLARE @batch_id UNIQUEIDENTIFIER;

EXEC etl.sp_start_formulario_batch
    @source_run_id = 'manual_2026-04-22_01',
    @source_system = 'streamlit_form_fruta_comercial',
    @notes = 'Carga manual desde export local',
    @batch_id = @batch_id OUTPUT;

SELECT @batch_id AS batch_id;
```

2. Cargar `stg.FormularioHeader` y `stg.FormularioDefecto` usando ese `@batch_id`.
3. Ejecutar:

```sql
EXEC dbo.sp_process_formulario_stage;
```

4. Revisar:

- `etl.BatchControl`
- `etl.RechazoFormularioHeader`
- `etl.RechazoFormularioDefecto`

## Exportador con metadata ETL

El exportador soporta agregar `batch_id` y `source_run_id` al CSV sin alterar el contrato funcional por defecto:

```powershell
python scripts/extract_dw_staging_payload.py `
  --fecha-operacional 2026-04-21 `
  --batch-id 11111111-1111-1111-1111-111111111111 `
  --source-run-id manual_2026-04-22_01 `
  --include-etl-metadata `
  --output-dir .\out
```

Con `--include-etl-metadata`, las columnas `batch_id` y `source_run_id` se agregan al final del export.

## Reglas nuevas aplicadas por `sp_process_formulario_stage`

### Header

Se rechaza cuando:

- existe excepcion activa en `etl.FormularioExcepcion`;
- `cant_muestra <= 0`;
- `suma_defectos < 0`;
- `fruta_comercial <> suma_defectos`;
- `fruta_sana < 0`;
- `choice < 0`;
- `fruta_sana + choice + suma_defectos <> cant_muestra`;
- `centro_codigo` es nulo o vacio.

### Defecto

Se rechaza cuando:

- existe excepcion activa en `etl.FormularioExcepcion`;
- no existe header asociado en `stg.FormularioHeader`;
- el header asociado ya fue rechazado;
- `codigo_defecto` es nulo o vacio;
- `cantidad < 0`.

## Manejo de excepciones

Cuando un registro es conocido como dato de prueba o anomalia no corregible, puede marcarse como excepcion para que quede fuera del core analitico sin perder trazabilidad:

```sql
MERGE etl.FormularioExcepcion AS tgt
USING (
    SELECT
        'streamlit_form_fruta_comercial' AS source_system,
        'a600237f-34b0-4463-90aa-5aaf31f988ef' AS source_business_key,
        'Dato de prueba local' AS reason
) AS src
    ON tgt.source_system = src.source_system
   AND tgt.source_business_key = src.source_business_key
WHEN MATCHED THEN
    UPDATE SET
        tgt.reason = src.reason,
        tgt.is_active = 1,
        tgt.updated_at = SYSUTCDATETIME()
WHEN NOT MATCHED THEN
    INSERT (source_system, source_business_key, reason)
    VALUES (src.source_system, src.source_business_key, src.reason);
```

Ese registro no se elimina del staging. Queda trazado como rechazado por excepcion activa.

## Resultado esperado

- solo pasan al core filas completas y validadas;
- las filas rechazadas no se pierden;
- cada lote queda con conteos de recibidos, cargados y rechazados;
- el backfill puede ejecutarse con mas seguridad, aun si existen datos de prueba o inconsistentes.
