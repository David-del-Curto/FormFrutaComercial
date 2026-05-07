# Directrices DW Azure SQL

## 1. Criterio funcional para `Especie_Principal`

No conviene usar `Especie_Principal` como una restriccion dura de seleccion de linea.
Si se convierte en regla obligatoria, una contingencia operacional valida puede bloquear la captura.

La recomendacion vigente es:

- `Centro` define el conjunto permitido de lineas.
- `Especie_Principal` solo sugiere o prioriza lineas recomendadas.
- La validacion dura sigue siendo por `centro + linea`.

## 2. Modelo recomendado

El script vigente es [azure_dw_form_fruta_comercial_refactored.sql](C:/DEV/FormFrutaComercial/sql/azure_dw_form_fruta_comercial_refactored.sql).

Ese script:

- reutiliza dimensiones maestras existentes:
  - `dbo.Dim_CentrosLogisticos`
  - `dbo.Dim_Especies`
  - `dbo.Dim_Productores`
  - `dbo.Dim_Variedades`
- crea staging:
  - `stg.FormularioHeader`
  - `stg.FormularioDefecto`
- crea dimensiones nuevas del dominio:
  - `dbo.DimLinea`
  - `dbo.DimLugarSeleccion`
  - `dbo.DimTurno`
  - `dbo.DimDefecto`
- crea los hechos:
  - `dbo.FactFormulario`
  - `dbo.FactFormularioDefecto`

Adicionalmente, el DW destino ya cuenta con una dimension de fechas existente:

- `dbo.Dim_Date`
  - PK: `idFecha` `INT`
  - fecha natural: `FechaCompleta` `DATE`

La integracion futura del hecho debe resolver ambas fechas del formulario contra esa dimension:

- `fecha`
- `fecha_operacional`

El archivo [azure_dw_form_fruta_comercial.sql](C:/DEV/FormFrutaComercial/sql/azure_dw_form_fruta_comercial.sql) queda solo como referencia historica del modelo legacy en esquema `dw`.

## 3. Grano recomendado

- `dbo.FactFormulario`: un registro por formulario capturado en la app.
- `dbo.FactFormularioDefecto`: un registro por formulario y codigo de defecto.

## 4. Regla mas importante: clave de negocio

Para poblar el DW correctamente se necesita una clave estable por formulario:

- `source_business_key`

Debe ser:

- globalmente unica;
- inmutable entre borrador y completo;
- compartida entre encabezado y defectos.

La app ya persiste `source_business_key` en SQLite y lo conserva entre borrador y completo.
La app tambien persiste `source_system`, configurable por ambiente con `FORM_FRUTA_SOURCE_SYSTEM`.

No conviene usar solo `id_registro` local como llave DW si la captura puede ocurrir desde mas de un equipo.

## 5. Secuencia de carga

1. Ejecutar una vez las dimensiones base `dbo.Dim_*` si la base destino todavia no las tiene.
2. Ejecutar [azure_dw_form_fruta_comercial_refactored.sql](C:/DEV/FormFrutaComercial/sql/azure_dw_form_fruta_comercial_refactored.sql).
3. Ejecutar `EXEC dbo.sp_seed_static_catalogs;`.
4. Insertar el lote crudo en `stg.FormularioHeader`.
5. Insertar los defectos del mismo lote en `stg.FormularioDefecto`.
6. Ejecutar `EXEC dbo.sp_process_formulario_stage;`.
7. Validar conteos y formularios sin defecto.

## 6. Regla vigente de carga

- `dbo.sp_process_formulario_stage` carga al DW solo formularios con `es_completo = 1`.
- Los formularios en borrador permanecen en staging con `dw_loaded_at = NULL`.
- Cuando un formulario pasa de borrador a completo, el mismo `source_business_key` permite completar la carga sin duplicar hechos.

## 7. Contrato minimo de datos

Encabezado:

- `source_system`
- `source_business_key`
- `fecha`
- `fecha_operacional`
- `turno_codigo`
- `linea_codigo`
- `linea_nombre`
- `especie`
- `especie_principal_linea`
- `variedad`
- `lote`
- `centro_codigo`
- `centro_nombre`
- `centro_display`
- `productor_codigo`
- `productor_nombre`
- `productor_display`
- `lugar_codigo`
- `lugar_nombre`
- `verificador`
- `observaciones`
- `cant_muestra`
- `suma_defectos`
- `fruta_comercial`
- `fruta_sana`
- `choice`
- porcentajes y velocidades
- `centro_sin_definir`
- `estado_formulario`
- `es_completo`
- `campos_pendientes`
- `created_at`
- `updated_at`

Decisiones Fase 0 vigentes:

- `kg_ultima_hora` no forma parte del contrato de `stg.FormularioHeader`.
- `kg_ultima_hora` permanece como dato operacional local hasta definir un uso analitico formal.
- `observaciones` viaja a staging y hecho como atributo de auditoria/consulta.
- `campos_pendientes` viaja a staging para trazabilidad de captura; su ubicacion final en el core se revisa en la siguiente fase.
- `especie_principal_linea` viaja en el contrato de staging y puede venir nulo mientras la app no lo persista.

Defectos:

- `source_system`
- `source_business_key`
- `codigo_defecto`
- `cantidad`
- `updated_at`

## 8. Validaciones recomendadas en ETL

- `cant_muestra >= fruta_comercial`
- `fruta_comercial = suma_defectos`
- `fruta_sana + choice + suma_defectos = cant_muestra`
- `centro_codigo` no nulo en carga productiva
- no cargar duplicados del mismo `source_business_key`
- no promover a hechos formularios con `es_completo = 0`

Llaves naturales oficiales Fase 0:

- centro logistico: `CodCentro_SAP`
- productor: `CodProductor_SAP`
- especie: `Especie`
- variedad: `(idEspecie, Variedad)` derivada desde `Especie + Variedad`
- formulario: `(source_system, source_business_key)`
- fecha DW: `idFecha` en `dbo.Dim_Date`, derivado desde la fecha calendario del formulario

## 9. Ejemplo minimo de uso

```sql
EXEC dbo.sp_seed_static_catalogs;

INSERT INTO stg.FormularioHeader (
    source_system,
    source_business_key,
    source_record_id,
    fecha,
    fecha_operacional,
    turno_codigo,
    turno_nombre,
    rango_turno,
    linea_codigo,
    linea_nombre,
    especie,
    variedad,
    lote,
    centro_codigo,
    centro_nombre,
    centro_display,
    productor_codigo,
    productor_nombre,
    productor_display,
    lugar_codigo,
    lugar_nombre,
    verificador,
    cant_muestra,
    suma_defectos,
    fruta_comercial,
    fruta_sana,
    choice,
    porc_exportable,
    porc_embalable,
    porc_choice,
    porc_descartable,
    centro_sin_definir,
    estado_formulario,
    es_completo,
    updated_at
)
VALUES (
    'streamlit_form_fruta_comercial',
    '6c3e3eb6-6f4f-4f16-bf2b-c230ecb28577',
    101,
    '2026-03-19',
    '2026-03-19',
    'T1',
    'Turno 1',
    '07:00-17:00',
    'LIN_03',
    'LIN_03',
    'KIWIS',
    'SUMMER',
    '1505475-01',
    'DC05',
    'C.F. Luis Cruz',
    'DC05 - C.F. Luis Cruz',
    'XA39',
    'A5 EXPORT SPA',
    'XA39 - A5 EXPORT SPA',
    'MS',
    'Mesa Seleccion',
    'Juan Perez',
    100,
    18,
    20,
    80,
    2,
    78.00,
    82.00,
    2.00,
    18.00,
    0,
    'completo',
    1,
    SYSUTCDATETIME()
);

INSERT INTO stg.FormularioDefecto (
    source_system,
    source_business_key,
    codigo_defecto,
    nombre_defecto,
    cantidad,
    updated_at
)
VALUES
('streamlit_form_fruta_comercial', '6c3e3eb6-6f4f-4f16-bf2b-c230ecb28577', 'HAO', 'Herida Abierta (Oxidada)', 8, SYSUTCDATETIME()),
('streamlit_form_fruta_comercial', '6c3e3eb6-6f4f-4f16-bf2b-c230ecb28577', 'MAC', 'Machucon', 10, SYSUTCDATETIME());

EXEC dbo.sp_process_formulario_stage;
```
