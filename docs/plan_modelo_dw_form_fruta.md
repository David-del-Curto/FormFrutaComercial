# Plan Modelo DW Form Fruta Comercial

## 1. Resumen ejecutivo

El proyecto ya tiene una base razonable para un DW:

- captura operacional en SQLite local;
- extraccion a payload tabular;
- staging en `stg`;
- dimensiones de dominio;
- hechos con grano claro para formulario y defecto.

Sin embargo, el modelo actual todavia esta a medio camino entre un modelo operacional persistido y un modelo analitico de DW. La recomendacion es **no desechar lo existente**, sino evolucionarlo a un modelo objetivo en 3 capas:

1. `raw/stg`: recepcion exacta del formulario.
2. `core`: dimensiones conformadas y hechos limpios.
3. `mart`: vistas o tablas orientadas a Power BI/KPI.

## 2. Lo que existe hoy

### Flujo actual

1. La app captura formularios y defectos en SQLite local.
2. La identidad de negocio del formulario se guarda con `source_system + source_business_key`.
3. Un script exporta datos para poblar `stg.FormularioHeader` y `stg.FormularioDefecto`.
4. `dbo.sp_process_formulario_stage` inserta/actualiza dimensiones y hechos.

### Modelo actual ya util

- `stg.FormularioHeader`: un registro por formulario.
- `stg.FormularioDefecto`: un registro por formulario y defecto.
- `dbo.FactFormulario`: un registro por formulario.
- `dbo.FactFormularioDefecto`: un registro por formulario y defecto.

### Validacion del grano

El grano definido en el SQL vigente es correcto para un primer DW:

- `FactFormulario`: 1 fila por formulario capturado.
- `FactFormularioDefecto`: 1 fila por formulario y codigo de defecto.

Eso permite construir KPI de calidad, productividad y mix de defectos sin romper agregaciones.

## 3. Brechas detectadas

### 3.1 Brecha tecnica inmediata: contrato de staging inconsistente

El contrato de `stg.FormularioHeader` no coincide completamente con el exportador actual:

- `stg.FormularioHeader` espera `especie_principal_linea`, `observaciones`, `campos_pendientes` y `created_at`.
- El exportador `scripts/extract_dw_staging_payload.py` no las incluye.
- El exportador incluye `kg_ultima_hora`, pero esa columna no existe en `stg.FormularioHeader`.

Impacto:

- hoy el proceso de exportacion/carga no tiene un contrato estable;
- cualquier carga automatizada puede fallar o requerir transformaciones manuales.

## 3.2 Falta integrar formalmente la dimension de tiempo existente

`FactFormulario` guarda `fecha` y `fecha_operacional` como `DATE`, pero el modelo vigente todavia no resuelve esas fechas contra la dimension de tiempo del DW.

Impacto:

- limita analisis calendario/fiscal/semana/mes/temporada;
- obliga a recalcular atributos temporales en cada consumo;
- dificulta estandarizar reporting en Power BI.

Recomendacion:

- integrar la `dbo.Dim_Date` existente;
- agregar `fecha_key` y `fecha_operacional_key` a `FactFormulario`.

## 3.3 Mezcla de atributos operacionales dentro del hecho analitico

`FactFormulario` contiene columnas de captura/estado como:

- `estado_formulario`
- `es_completo`
- `campos_pendientes`
- `observaciones`

Si el DW solo carga formularios completos, parte de esos atributos deja de ser medida analitica y pasa a ser:

- metadata de linaje;
- auditoria de calidad;
- o atributos degenerados de documento.

Recomendacion:

- mantener `observaciones` como atributo degenerado solo si tiene valor analitico real;
- sacar `campos_pendientes` del hecho core y moverlo a auditoria/rechazos;
- mantener `estado_formulario` solo en staging o auditoria si el core carga solo completos.

## 3.4 Dimensiones maestras reutilizadas, pero no gobernadas como DW

El modelo refactorizado reutiliza:

- `dbo.Dim_CentrosLogisticos`
- `dbo.Dim_Especies`
- `dbo.Dim_Productores`
- `dbo.Dim_Variedades`

Esto es bueno para no duplicar catalogos, pero hoy esas tablas se comportan mas como maestros operacionales que como dimensiones DW:

- no muestran estrategia SCD explicita;
- no tienen columnas tipicas de vigencia DW (`valid_from`, `valid_to`, `is_current`);
- no se observa manejo de miembro `Unknown/No definido`;
- no se ve una politica unica de claves naturales y calidad.

Recomendacion:

- corto plazo: usarlas como dimensiones conformadas tipo 1;
- mediano plazo: definir si `Productor`, `Centro` y eventualmente `Linea` requieren historia tipo 2.

## 3.5 Calidad de datos insuficientemente formalizada

Las validaciones funcionales existen en la app, pero en el DW faltan controles duros y trazables:

- no hay tablas de rechazo;
- no hay `batch_id` ni auditoria de corrida;
- no hay reglas `CHECK` para relaciones numericas clave;
- no hay watermarks ni control incremental explicito.

Recomendacion:

- agregar auditoria ETL;
- registrar rechazos por fila;
- formalizar reglas de calidad en stored procedures o capa ETL.

## 3.6 Riesgo de mapeo ambiguo en centros logisticos

El SQL hace match de centro por codigo o por nombre:

- `CAST(c.CodCentro_SAP AS NVARCHAR) = ...`
- `OR c.Centro_Logistico = ...`

Impacto:

- si existen equivalencias no unicas, una fila puede mapear distinto segun catalogo;
- esto es especialmente sensible en `DimLinea`, porque la linea depende del centro.

Recomendacion:

- estandarizar un solo natural key de centro para DW;
- priorizar `CodCentro_SAP`;
- dejar nombre solo como atributo descriptivo.

## 4. Validacion arquitectonica

### Lo que SI validaria como base del DW

- staging separado de hechos;
- uso de una business key estable por formulario;
- carga incremental por `dw_loaded_at`;
- tabla de detalle de defectos separada del encabezado;
- reutilizacion de dimensiones maestras para no duplicar catalogos.

### Lo que NO validaria aun como modelo final de DW

- ausencia de `DimFecha`;
- contrato inestable entre exportacion y staging;
- mezcla de atributos operacionales dentro del hecho core;
- falta de auditoria de lotes y rechazos;
- falta de estrategia SCD y de miembros desconocidos;
- dependencia de joins ambiguos para centro/linea.

## 5. Modelo objetivo recomendado

## 5.1 Capas

### Capa 1: Raw/Staging

Tablas:

- `stg.FormularioHeaderRaw`
- `stg.FormularioDefectoRaw`

Objetivo:

- recibir el payload tal como sale de la app;
- guardar `batch_id`, `ingested_at`, `source_file` o `source_run_id`;
- no mezclar reglas analiticas complejas en esta capa.

Nota:

Si se quiere minimizar cambio, se puede reutilizar `stg.FormularioHeader` y `stg.FormularioDefecto`, pero agregando metadata ETL y estabilizando columnas.

### Capa 2: Core DW

Dimensiones recomendadas:

- `dbo.Dim_Date`
- `dbo.DimTurno`
- `dbo.DimCentroLogistico`
- `dbo.DimProductor`
- `dbo.DimEspecie`
- `dbo.DimVariedad`
- `dbo.DimLinea`
- `dbo.DimLugarSeleccion`
- `dbo.DimDefecto`

Hechos recomendados:

- `dbo.FactFormulario`
- `dbo.FactFormularioDefecto`

Auditoria:

- `etl.BatchControl`
- `etl.RechazoFormularioHeader`
- `etl.RechazoFormularioDefecto`

### Capa 3: Mart / Consumo

Objetos recomendados:

- vista `mart.vw_calidad_operacional_diaria`
- vista `mart.vw_calidad_por_linea`
- vista `mart.vw_mix_defectos`
- vista `mart.vw_productividad_turno`

## 5.2 Grano objetivo

### FactFormulario

Una fila por formulario completo.

Claves:

- `formulario_key` surrogate
- `source_system`
- `source_business_key`
- `fecha_key`
- `fecha_operacional_key`
- `turno_key`
- `centro_key`
- `productor_key`
- `especie_key`
- `variedad_key`
- `linea_key`
- `lugar_key`

Medidas:

- `cant_muestra`
- `suma_defectos`
- `fruta_comercial`
- `fruta_sana`
- `choice`
- `porc_exportable`
- `porc_embalable`
- `porc_choice`
- `porc_descartable`
- `porc_export_manual`
- `velocidad_kgh`
- `velocidad_manual`

Degenerados opcionales:

- `lote`
- `verificador`

### FactFormularioDefecto

Una fila por formulario completo y defecto.

Claves:

- `formulario_key`
- `defecto_key`

Medidas:

- `cantidad`

## 5.3 Politica SCD recomendada

- `Dim_Date`: estatica.
- `DimTurno`: tipo 1.
- `DimLugarSeleccion`: tipo 1.
- `DimDefecto`: tipo 1.
- `DimEspecie`: tipo 1.
- `DimVariedad`: tipo 1.
- `DimCentroLogistico`: tipo 1 al inicio; evaluar tipo 2 si cambian atributos usados en analitica.
- `DimProductor`: evaluar tipo 2 para atributos geograficos/comerciales si se analizara historia por vigencia.
- `DimLinea`: tipo 2 solo si la especie principal o asociacion a centro puede cambiar y se requiere trazabilidad historica; si no, tipo 1.

## 6. Reglas de calidad de datos recomendadas

Minimas para el core:

- `cant_muestra > 0`
- `suma_defectos >= 0`
- `choice >= 0`
- `fruta_sana >= 0`
- `fruta_comercial = suma_defectos`
- `fruta_sana + choice + suma_defectos = cant_muestra`
- `source_system + source_business_key` unico
- no insertar `FactFormularioDefecto` sin `FactFormulario`
- no cargar hechos sin correspondencia valida en dimensiones

Reglas de mapeo:

- `centro_codigo` debe mapear de forma univoca a una dimension
- `linea_codigo` debe ser unica dentro de un centro
- `variedad` debe pertenecer a una `especie`

Reglas de proceso:

- los rechazos no se pierden;
- cada lote debe dejar conteo de recibidos, cargados y rechazados.

## 7. Plan de implementacion recomendado

## Fase 0. Definiciones y cierre de contrato

Objetivo:

- dejar cerrado el contrato de datos entre app, exportacion y staging.

Tareas:

- alinear columnas de `scripts/extract_dw_staging_payload.py` con `stg.FormularioHeader`;
- decidir si `kg_ultima_hora` entra al DW o queda fuera del core;
- decidir si `observaciones` y `campos_pendientes` se mantienen en core o solo auditoria;
- definir natural keys oficiales para centro, productor, especie y variedad.

Entregable:

- diccionario de datos v1;
- contrato de staging versionado.

## Fase 1. Hardening del staging

Objetivo:

- convertir staging en una capa confiable y auditable.

Tareas:

- agregar `batch_id`, `ingested_at`, `source_run_id`, `row_hash`;
- crear tablas de rechazo;
- crear `etl.BatchControl`;
- agregar indices por `dw_loaded_at`, `updated_at`, `source_business_key`.

Entregable:

- staging listo para backfill e incremental.

## Fase 2. Ajuste del modelo core DW

Objetivo:

- llevar el modelo actual a un esquema analitico estable.

Tareas:

- integrar `Dim_Date`;
- agregar `fecha_key` y `fecha_operacional_key` a `FactFormulario`;
- introducir miembros `Unknown` en dimensiones necesarias;
- separar metadata operacional del hecho core cuando no sea analitica;
- revisar `DimLinea` y mapeo univoco con centro.

Entregable:

- DDL v2 del DW.

## Fase 3. ETL inicial y backfill historico

Objetivo:

- poblar el DW con historia disponible.

Tareas:

- extraer historico desde SQLite local;
- cargar `stg`;
- ejecutar procedimiento de transformacion;
- validar conteos por fecha operacional, centro, linea y turno;
- reconciliar defectos vs muestra.

Entregable:

- primera carga historica validada.

## Fase 4. Carga incremental operativa

Objetivo:

- automatizar la alimentacion del DW.

Tareas:

- definir frecuencia de extraccion;
- usar watermark por `updated_at` o lotes por `batch_id`;
- automatizar exportacion CSV o carga directa;
- generar monitoreo de fallos y rechazos.

Entregable:

- pipeline incremental operando.

## Fase 5. Capa mart y reporting

Objetivo:

- dejar el DW listo para consumo.

Tareas:

- construir vistas de KPI;
- documentar medidas certificadas;
- validar con usuarios de negocio.

Entregable:

- capa de consumo lista para BI.

## 8. Orden de prioridad real

Si lo hacemos de forma pragmatica, este seria el orden correcto:

1. Estabilizar el contrato `export -> stg`.
2. Incorporar auditoria y rechazo de lotes.
3. Integrar `Dim_Date`.
4. Ajustar `FactFormulario` a modelo analitico limpio.
5. Ejecutar backfill historico.
6. Automatizar incremental.
7. Exponer marts o vistas de consumo.

## 9. Decisiones que recomiendo tomar ahora

### Decision 1

Mantener el modelo base actual y evolucionarlo, no rehacerlo desde cero.

### Decision 2

Adoptar `source_system + source_business_key` como business key oficial del formulario.

### Decision 3

Usar `CodCentro_SAP` como llave natural principal de centro en DW.

### Decision 4

Integrar `Dim_Date` antes de poblar historia.

### Decision 5

Separar datos rechazados y metadata ETL del hecho analitico.

## 10. Siguiente iteracion recomendada

La siguiente iteracion tecnica deberia ejecutar estas 4 acciones:

1. Corregir el contrato del exportador `extract_dw_staging_payload.py`.
2. Diseñar el DDL v2 del DW con integracion a `Dim_Date`, auditoria ETL y rechazos.
3. Ajustar `sp_process_formulario_stage` para usar el nuevo contrato.
4. Hacer una carga piloto de una fecha operacional y validar reconciliacion.
