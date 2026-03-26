# Directrices DW Azure SQL

## 1. Criterio funcional para `Especie_Principal`

No conviene usar `Especie_Principal` como una restriccion dura de seleccion de linea.
Si la conviertes en regla obligatoria, en una contingencia operacional como mantencion,
desviacion de flujo o reconfiguracion temporal de linea vas a bloquear una captura valida.

La recomendacion es:

- `Centro` define el conjunto permitido de lineas.
- `Especie_Principal` solo sugiere, prioriza o marca lineas recomendadas.
- La validacion dura debe seguir siendo por `centro + linea`.

Eso te deja dos beneficios:

- Flujo guiado para la operacion normal.
- Flexibilidad real para operar con lineas alternativas cuando haga falta.

## 2. Modelo recomendado

El script [azure_dw_form_fruta_comercial.sql](C:/DEV/FormFrutaComercial/sql/azure_dw_form_fruta_comercial.sql) crea:

- `stg.FormularioHeader`
- `stg.FormularioDefecto`
- `dw.DimCentro`
- `dw.DimProductor`
- `dw.DimEspecie`
- `dw.DimVariedad`
- `dw.DimLinea`
- `dw.DimLugarSeleccion`
- `dw.DimTurno`
- `dw.DimDefecto`
- `dw.FactFormulario`
- `dw.FactFormularioDefecto`

Grano propuesto:

- `FactFormulario`: un registro por formulario guardado en la app.
- `FactFormularioDefecto`: un registro por formulario y codigo de defecto.

## 3. Regla mas importante: clave de negocio

Para poblar el DW correctamente necesitas una clave estable por formulario:

- `source_business_key`

Debe ser:

- Globalmente unica.
- Inmutable entre borrador y completo.
- Compartida entre encabezado y defectos.

Lo ideal es un GUID generado en la app.

Implementacion actual del MVP:

- la app ya persiste `source_business_key` en SQLite y lo conserva entre borrador y completo;
- la app ya persiste `source_system`;
- `source_system` puede fijarse por ambiente con la variable `FORM_FRUTA_SOURCE_SYSTEM`.

No recomiendo usar solo `id_registro` local como llave DW si la captura ocurre desde mas de un equipo, porque vas a tener colisiones entre dispositivos.

## 4. Secuencia de carga

1. Ejecuta una vez el script base en Azure SQL.
2. Ejecuta `EXEC dw.sp_seed_static_catalogs;`
3. Inserta el lote crudo en `stg.FormularioHeader`.
4. Inserta los defectos del mismo lote en `stg.FormularioDefecto`.
5. Ejecuta `EXEC dw.sp_process_formulario_stage;`
6. Valida conteos y formularios sin defecto.

## 5. Contrato minimo de datos

Encabezado:

- `source_system`
- `source_business_key`
- `fecha`
- `fecha_operacional`
- `turno_codigo`
- `linea_codigo`
- `especie`
- `variedad`
- `lote`
- `cant_muestra`
- `suma_defectos`
- `fruta_comercial`
- `fruta_sana`
- `choice`
- `%` y velocidades
- `estado_formulario`
- `es_completo`
- `updated_at`

Defectos:

- `source_system`
- `source_business_key`
- `codigo_defecto`
- `cantidad`
- `updated_at`

## 6. Recomendacion operativa

Si vas a poblar el DW desde la app:

- genera `source_business_key` al crear el formulario, no al guardarlo como completo;
- conserva esa misma clave cuando el registro pase de borrador a completo;
- envia siempre header y defectos del mismo formulario dentro del mismo batch;
- reutiliza `source_system` para distinguir origenes, por ejemplo `streamlit_form_fruta_comercial`.

## 7. Validaciones que conviene dejar en el ETL

- `cant_muestra >= fruta_comercial`
- `fruta_comercial = suma_defectos + choice`
- `porc_exportable <= porc_embalable` cuando aplique
- `centro_codigo` no nulo en carga productiva
- no cargar duplicados del mismo `source_business_key`

## 8. Ejemplo minimo de uso

```sql
EXEC dw.sp_seed_static_catalogs;

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

EXEC dw.sp_process_formulario_stage;
```
