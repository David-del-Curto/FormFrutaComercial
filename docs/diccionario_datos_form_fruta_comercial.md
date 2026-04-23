# Diccionario de Datos y Formulas - Form Fruta Comercial

Version: 2026-04-22

## 1. Proposito y fuentes de verdad

Este documento deja una referencia oficial, unica y reutilizable para:

- arquitectura y datos, que necesitan la semantica y el mapeo fisico del formulario;
- QA y operacion, que necesitan entender que significa cada campo y KPI;
- futuras integraciones DW/BI, que necesitan distinguir entre etiqueta funcional y nombre tecnico.

Alcance cubierto:

- campos capturados en `Formulario`;
- KPI y formulas visibles en `Estatus Operacion`;
- estructura de `stg.FormularioHeader`, `stg.FormularioDefecto`, `dbo.FactFormulario` y `dbo.FactFormularioDefecto`;
- catalogo base de defectos sembrado en `dbo.DimDefecto`;
- reglas de validacion y equivalencias documentales.

Prioridad de fuentes:

1. Verdad funcional: `docs/manual_usuario_estatus_operacion.md`, `docs/presentacion_ejecutiva_estatus_operacion.md`, `docs/historial_tecnico_ajustes_estatus_operacion.md`.
2. Verdad tecnica: `docs/dw_fase0_contrato_staging.md` y `sql/azure_dw_form_fruta_comercial_refactored.sql`.
3. Si existe diferencia entre etiqueta UI y nombre fisico SQL, se documentan ambos y se declara la equivalencia.

## 2. Glosario funcional

| Termino | Definicion funcional | Observaciones |
|---|---|---|
| Formulario | Registro unitario de calidad capturado para una combinacion de fecha, linea, lote y contexto operacional. | En DW el grano oficial es 1 fila por formulario completo. |
| Borrador | Formulario con datos obligatorios pendientes. | Permanece en `stg` y no se promueve a core mientras `es_completo = 0`. |
| Completo | Formulario listo para KPI y procesos posteriores. | Solo los completos pasan al DW core. |
| Dia operacional | Dia usado para el seguimiento de la operacion y filtrado del dashboard. | Se almacena como `fecha_operacional`. |
| Muestra | Cantidad de frutos inspeccionados en un formulario. | Corresponde a `cant_muestra`. |
| Defectos | Conteo total de frutos defectuosos observados en la muestra. | En el modelo vigente coincide con `suma_defectos`. |
| Choice | Conteo de frutos clasificados como choice. | Forma parte de la base de calidad. |
| Fruta sana | Conteo de frutos sanos dentro de la muestra. | Forma parte de la base de calidad. |
| Base calidad | Total usado para calcular porcentajes de calidad. | `Base calidad = fruta_sana + choice + suma_defectos`. |
| Fruta comercial | Campo fisico del formulario/DW. | En el modelo vigente cumple la regla `fruta_comercial = suma_defectos`; no debe confundirse con `Kg Comercial 1h` del dashboard. |
| Exportable | Volumen estimado que queda luego de descontar fruta comercial de la ultima hora. | KPI horario del dashboard, no columna fisica del formulario base. |
| FBC | Indicador combinado de calidad y volumen comercial. | Se documenta como porcentaje compuesto. |
| FBC Absoluto 1h | KPI principal del semaforo en `Estatus Operacion`. | Se interpreta como `% FBC` calculado sobre una ventana movil de 1 hora. |
| Ventana movil 1h | Periodo de analisis relativo al ultimo `updated_at` con actividad. | No necesariamente coincide con una hora reloj cerrada. |
| Screen ID | Identificador de configuracion de una pantalla fija por linea. | Se usa en modo `kiosk`; no forma parte del modelo DW. |

## 3. Formulas oficiales y KPI

### 3.1 Base de volumen

| KPI | Formula oficial | Unidad | Ventana | Observaciones |
|---|---|---|---|---|
| Kg Exportable | `max(Kg/Hr - Kg Comercial 1h, 0)` | kg/h | Ultima hora | KPI operacional; no existe como columna fisica en `stg` ni en `FactFormulario`. |
| % Comercial Kg | `Kg Comercial 1h / Kg/Hr * 100` | % | Ultima hora | Mide relacion entre kilos comerciales y velocidad de linea. |
| % Exportable | `Kg Exportable / Kg/Hr * 100` | % | Ultima hora | Depende del KPI `Kg Exportable`. |

### 3.2 Base de calidad

Base calidad oficial:

`Base calidad = Fruta Sana + Choice + Defectos`

| KPI | Formula oficial | Unidad | Ventana | Observaciones |
|---|---|---|---|---|
| % Sana FBC muestra | `Sana / (Sana + Choice + Defectos) * 100` | % | Segun formularios incluidos | Alias funcional del campo fisico `porc_embalable`. |
| % Choice | `Choice / (Sana + Choice + Defectos) * 100` | % | Segun formularios incluidos | Corresponde a `porc_choice`. |
| % Descartable | `Defectos / (Sana + Choice + Defectos) * 100` | % | Segun formularios incluidos | Corresponde a `porc_descartable`. |

### 3.3 Indicadores combinados

| KPI | Formula oficial | Unidad | Ventana | Observaciones |
|---|---|---|---|---|
| % FBC | `(% Sana + % Choice) * % Comercial Kg / 100` | % | Segun agregado visible | En la documentacion funcional `% Sana` corresponde a `% Sana FBC muestra`. |
| Kg FBC/h | `Kg Comercial validado * ((Fruta Sana + Choice) / Base calidad)` | kg/h | Ultima hora | Indicador horario para status operacional. |
| % FBC Absoluto 1h | `% FBC` calculado sobre la ventana movil de la ultima hora | % | Ventana movil 1h | Esta equivalencia se infiere de manual, presentacion e historial tecnico; no existe una columna DW con ese nombre. |

### 3.4 Semaforo operacional

El semaforo de `Estatus Operacion` usa `% FBC Absoluto 1h` con esta interpretacion:

| Banda | Regla |
|---|---|
| Verde | `< 1,0` |
| Amarillo | `>= 1,0` y `< 1,5` |
| Rojo | `>= 1,5` |

## 4. Diccionario de datos del formulario

Plantilla aplicada por campo:

- nombre funcional;
- nombre fisico;
- capa/origen;
- definicion de negocio;
- formula o derivacion;
- tipo de dato;
- unidad;
- obligatoriedad/nullabilidad;
- regla de validacion;
- consumidor principal;
- observaciones.

### 4.1 Identificacion y trazabilidad

| Nombre funcional | Nombre fisico | Capa/origen | Definicion de negocio | Formula o derivacion | Tipo | Unidad | Nullabilidad | Regla de validacion | Consumidor principal | Observaciones |
|---|---|---|---|---|---|---|---|---|---|---|
| Sistema origen | `source_system` | `stg`, `FactFormulario`, `stg.FormularioDefecto` | Identifica la aplicacion o fuente que genero el formulario. | Valor emitido por exportador. | `NVARCHAR(50)` | N/A | No nulo | Forma parte de la business key. | ETL, auditoria, integracion DW | Junto con `source_business_key` identifica univocamente el formulario. |
| Llave de negocio formulario | `source_business_key` | `stg`, `FactFormulario`, `stg.FormularioDefecto` | Identificador estable del formulario en la fuente. | Valor emitido por exportador. | `NVARCHAR(100)` | N/A | No nulo | Unico por `source_system`. | ETL, DW, trazabilidad | Llave oficial del formulario: `source_system + source_business_key`. |
| Id tecnico origen | `source_record_id` | `stg`, `FactFormulario` | Id interno del registro local exportado. | `registro.id_registro`. | `BIGINT` | N/A | Nulo permitido | Sin regla funcional propia. | Soporte, trazabilidad | Es identificador tecnico, no business key. |
| Fecha creacion local | `created_at` | `stg`, `FactFormulario` | Momento en que se creo el registro local. | `registro.created_at`. | `DATETIME2(0)` | fecha-hora | Nulo permitido en SQL | Si existe, debe ser menor o igual a `updated_at`. | Auditoria | Puede venir nulo en staging. |
| Fecha actualizacion local | `updated_at` | `stg`, `FactFormulario`, `stg.FormularioDefecto`, `FactFormularioDefecto` | Momento de ultima actualizacion del registro. | `registro.updated_at` o equivalente del detalle. | `DATETIME2(0)` | fecha-hora | No nulo | Base para ventana movil operacional. | Dashboard, auditoria, ETL incremental | Es la referencia temporal mas importante para actividad reciente. |
| Fecha carga DW staging | `dw_loaded_at` | `stg`, `stg.FormularioDefecto` | Marca de carga hacia capas posteriores. | Gestionada por proceso DW. | `DATETIME2(0)` | fecha-hora | Nulo permitido | Nulo mientras no ha sido promovido. | ETL | No forma parte del payload funcional Fase 0. |
| Fecha insercion DW | `dw_inserted_at` | `FactFormulario` | Momento en que el hecho se inserto en core. | `SYSUTCDATETIME()`. | `DATETIME2(0)` | fecha-hora | No nulo | Gestionado por SQL. | Auditoria DW | Campo tecnico, no visible en UI. |
| Fecha actualizacion DW | `dw_updated_at` | `FactFormulario`, `FactFormularioDefecto` | Momento de ultima actualizacion del hecho en core. | `SYSUTCDATETIME()`. | `DATETIME2(0)` | fecha-hora | No nulo | Gestionado por SQL. | Auditoria DW | Campo tecnico. |
| Llave surrogate formulario | `formulario_key` | `FactFormulario`, `FactFormularioDefecto` | Identificador surrogate del hecho principal. | `IDENTITY(1,1)` en `FactFormulario`. | `BIGINT` | N/A | No nulo | PK de core. | DW, modelo estrella | No existe en captura operacional. |

### 4.2 Contexto operacional del encabezado

| Nombre funcional | Nombre fisico | Capa/origen | Definicion de negocio | Formula o derivacion | Tipo | Unidad | Nullabilidad | Regla de validacion | Consumidor principal | Observaciones |
|---|---|---|---|---|---|---|---|---|---|---|
| Fecha formulario | `fecha` | `stg`, `FactFormulario` | Fecha calendario del registro. | Capturada en formulario. | `DATE` | fecha | No nulo | Debe poder resolverse en `Dim_Date` en fases siguientes. | Operacion, DW | Distinta de `fecha_operacional`. |
| Dia operacional | `fecha_operacional` | `stg`, `FactFormulario` | Fecha usada para seguimiento y filtros operacionales. | Capturada/derivada por la app. | `DATE` | fecha | No nulo | Debe poder resolverse en `Dim_Date`. | Dashboard, BI, operacion | Filtro principal del dashboard. |
| Codigo turno | `turno_codigo` | `stg` | Codigo del turno del formulario. | Capturado o derivado por app. | `VARCHAR(10)` | N/A | No nulo | Natural key oficial de turno. | ETL, DW | Resuelve a `turno_key`. |
| Nombre turno | `turno_nombre` | `stg` | Nombre legible del turno. | Capturado o derivado por app. | `NVARCHAR(50)` | N/A | No nulo | Debe ser consistente con `turno_codigo`. | UI, DW | Se conserva como descriptivo. |
| Rango turno | `rango_turno` | `stg` | Franja horaria del turno. | Capturado o derivado por app. | `NVARCHAR(50)` | N/A | No nulo | Debe ser consistente con `turno_codigo`. | UI, DW | Se usa para interpretacion operacional. |
| Llave turno | `turno_key` | `FactFormulario` | Llave surrogate hacia `dbo.DimTurno`. | Resolve por ETL desde `turno_codigo`. | `INT` | N/A | No nulo | FK valida a `dbo.DimTurno`. | DW, BI | Sustituye a columnas descriptivas en core. |
| Codigo linea | `linea_codigo` | `stg` | Identificador de la linea operativa. | En Fase 0: `registro.linea`. | `NVARCHAR(50)` | N/A | No nulo | Natural key de linea junto con centro. | Operacion, ETL | Visible en filtros y kiosko. |
| Nombre linea | `linea_nombre` | `stg` | Nombre visible de la linea. | En Fase 0: `registro.linea`. | `NVARCHAR(120)` | N/A | Nulo permitido | Debe describir `linea_codigo`. | UI, DW | Puede coincidir con el codigo. |
| Llave linea | `linea_key` | `FactFormulario` | Llave surrogate hacia `dbo.DimLinea`. | Resolve por ETL. | `INT` | N/A | No nulo | FK valida a `dbo.DimLinea`. | DW, BI | La natural key oficial es `CodCentro_SAP + linea_codigo`. |
| Especie | `especie` | `stg` | Especie del lote/formulario. | Capturada en formulario. | `NVARCHAR(120)` | N/A | No nulo | Natural key oficial de especie. | Operacion, DW | Tambien se usa como filtro del dashboard. |
| Especie principal linea | `especie_principal_linea` | `stg` | Especie sugerida o dominante de la linea. | En Fase 0 puede venir `NULL`. | `NVARCHAR(120)` | N/A | Nulo permitido | Sin obligatoriedad en contrato Fase 0. | UI, apoyo operativo | Se mantiene por trazabilidad aunque el filtro siga siendo editable. |
| Llave especie | `idEspecie` | `FactFormulario` | Referencia a `dbo.Dim_Especies`. | Resolve por ETL desde `especie`. | `INT` | N/A | No nulo | FK valida a dimension. | DW, BI | Sustituye al nombre libre en core. |
| Variedad | `variedad` | `stg` | Variedad de la fruta muestreada. | Capturada en formulario. | `NVARCHAR(120)` | N/A | No nulo | Natural key oficial: `Especie + Variedad`. | Operacion, DW | Debe analizarse siempre junto a especie. |
| Llave variedad | `idVariedad` | `FactFormulario` | Referencia a `dbo.Dim_Variedades`. | Resolve por ETL desde especie/variedad. | `INT` | N/A | No nulo | FK valida a dimension. | DW, BI | En core se usa llave, no texto libre. |
| Lote | `lote` | `stg`, `FactFormulario` | Identificador del lote observado. | Capturado en formulario. | `NVARCHAR(50)` | N/A | No nulo | Debe existir para formularios completos. | Operacion, trazabilidad | Campo degenerado de negocio. |
| Codigo centro logistico | `centro_codigo` | `stg` | Codigo del centro logistico. | Capturado/exportado. | `NVARCHAR(20)` | N/A | Nulo permitido | Natural key oficial: `CodCentro_SAP`. | ETL, DW | Debe priorizarse sobre nombre para matching. |
| Nombre centro logistico | `centro_nombre` | `stg` | Nombre del centro logistico. | Capturado/exportado. | `NVARCHAR(200)` | N/A | Nulo permitido | Usar como descriptivo, no como llave primaria de negocio. | UI, apoyo operativo | Puede generar ambiguedad si se usa para matching. |
| Centro display | `centro_display` | `stg` | Etiqueta visible combinada para desplegar centro. | Derivada por app/exportador. | `NVARCHAR(250)` | N/A | Nulo permitido | Sin regla critica. | UI | Campo de presentacion. |
| Llave centro logistico | `idCentroLogistico` | `FactFormulario` | Referencia a `dbo.Dim_CentrosLogisticos`. | Resolve por ETL desde `centro_codigo`. | `INT` | N/A | Nulo permitido | FK valida si existe match. | DW, BI | Puede venir nulo si no se define centro. |
| Centro sin definir | `centro_sin_definir` | `stg`, `FactFormulario` | Bandera que indica si el centro no pudo quedar definido formalmente. | Derivada por captura/ETL. | `BIT` | booleano | No nulo | Debe reflejar casos sin mapeo confiable. | QA datos, ETL | Ayuda a separar registros incompletos o ambiguos. |
| Codigo productor | `productor_codigo` | `stg` | Codigo SAP u oficial del productor. | Capturado/exportado. | `NVARCHAR(50)` | N/A | Nulo permitido | Natural key oficial: `CodProductor_SAP`. | ETL, DW | Priorizar sobre nombre para matching. |
| Nombre productor | `productor_nombre` | `stg` | Nombre del productor. | Capturado/exportado. | `NVARCHAR(200)` | N/A | Nulo permitido | Debe usarse como descriptivo. | UI, trazabilidad | |
| Productor display | `productor_display` | `stg` | Etiqueta visible combinada para productor. | Derivada por app/exportador. | `NVARCHAR(250)` | N/A | Nulo permitido | Sin regla critica. | UI | Campo de presentacion. |
| Llave productor | `idProductor` | `FactFormulario` | Referencia a `dbo.Dim_Productores`. | Resolve por ETL desde `productor_codigo`. | `INT` | N/A | Nulo permitido | FK valida si existe match. | DW, BI | Puede quedar nula si el productor no mapea. |
| Codigo lugar de seleccion | `lugar_codigo` | `stg` | Codigo del lugar de seleccion. | Capturado en formulario. | `VARCHAR(10)` | N/A | Nulo permitido | Natural key oficial de lugar. | ETL, DW | |
| Nombre lugar de seleccion | `lugar_nombre` | `stg` | Nombre legible del lugar de seleccion. | Capturado en formulario. | `NVARCHAR(100)` | N/A | Nulo permitido | Debe ser consistente con `lugar_codigo`. | UI, DW | |
| Llave lugar de seleccion | `lugar_key` | `FactFormulario` | Referencia a `dbo.DimLugarSeleccion`. | Resolve por ETL. | `INT` | N/A | Nulo permitido | FK valida si existe match. | DW, BI | |
| Verificador | `verificador` | `stg`, `FactFormulario` | Persona que valida o registra el formulario. | Capturado en formulario. | `NVARCHAR(100)` | N/A | Nulo permitido | Recomendado para trazabilidad operativa. | Operacion, QA | No es dimension separada en el DW actual. |
| Observaciones | `observaciones` | `stg`, `FactFormulario` | Comentarios libres asociados al formulario. | `registro.observaciones`. | `NVARCHAR(1000)` | texto | Nulo permitido | Sin regla numerica; conservar trazabilidad textual. | Operacion, auditoria | El contrato Fase 0 mantiene este campo en staging. |

### 4.3 Captura de calidad

| Nombre funcional | Nombre fisico | Capa/origen | Definicion de negocio | Formula o derivacion | Tipo | Unidad | Nullabilidad | Regla de validacion | Consumidor principal | Observaciones |
|---|---|---|---|---|---|---|---|---|---|---|
| Cantidad muestra frutos | `cant_muestra` | `stg`, `FactFormulario` | Cantidad total de frutos observados en el formulario. | Captura directa. | `INT` | frutos | No nulo | `cant_muestra > 0`. | Formulario, KPI, BI | Base numerica principal del formulario. |
| Suma defectos | `suma_defectos` | `stg`, `FactFormulario` | Total agregado de defectos observados en la muestra. | `SUM(cantidad)` del detalle por defecto. | `INT` | frutos | No nulo | `suma_defectos >= 0`. | KPI calidad, DW | Debe cuadrar con detalle de defectos. |
| Fruta comercial | `fruta_comercial` | `stg`, `FactFormulario` | Campo fisico heredado por el modelo vigente. | Captura/exportacion actual. | `INT` | frutos | No nulo | `fruta_comercial = suma_defectos`. | ETL, consistencia tecnica | No equivale a `Kg Comercial 1h` del dashboard. |
| Fruta sana | `fruta_sana` | `stg`, `FactFormulario` | Conteo de frutos sanos en la muestra. | Captura directa. | `INT` | frutos | No nulo | `fruta_sana + choice + suma_defectos = cant_muestra`. | KPI calidad, BI | Componente de la base calidad. |
| Choice | `choice` | `stg`, `FactFormulario` | Conteo de frutos clasificados como choice. | Captura directa. | `INT` | frutos | No nulo | `choice >= 0` y participa en cierre de muestra. | KPI calidad, BI | Componente de la base calidad. |
| % Exportable | `porc_exportable` | `stg`, `FactFormulario` | Porcentaje exportable registrado para el formulario. | Valor calculado/exportado por app. | `DECIMAL(9,2)` | % | No nulo | Debe ser coherente con formula oficial del KPI. | Dashboard, BI | Mantiene igual nombre fisico y funcional visible. |
| % Sana FBC muestra | `porc_embalable` | `stg`, `FactFormulario` | Proporcion sana dentro de la base de calidad. | `fruta_sana / (fruta_sana + choice + suma_defectos) * 100`. | `DECIMAL(9,2)` | % | No nulo | Debe ser coherente con la base calidad. | Dashboard, BI | Alias funcional oficial: `% Sana FBC muestra`. |
| % Choice | `porc_choice` | `stg`, `FactFormulario` | Proporcion de choice dentro de la base de calidad. | `choice / (fruta_sana + choice + suma_defectos) * 100`. | `DECIMAL(9,2)` | % | No nulo | Debe ser coherente con la base calidad. | Dashboard, BI | |
| % Descartable | `porc_descartable` | `stg`, `FactFormulario` | Proporcion de defectos dentro de la base de calidad. | `suma_defectos / (fruta_sana + choice + suma_defectos) * 100`. | `DECIMAL(9,2)` | % | No nulo | Debe ser coherente con la base calidad. | Dashboard, BI | |
| % Export manual | `porc_export_manual` | `stg`, `FactFormulario` | Ajuste o valor manual de porcentaje exportable, si aplica. | Ingreso manual opcional. | `INT` | % | Nulo permitido | Debe distinguirse de `porc_exportable` calculado. | Operacion, analisis puntual | Campo auxiliar; no todos los procesos lo requieren. |

### 4.4 Productividad y velocidad

| Nombre funcional | Nombre fisico | Capa/origen | Definicion de negocio | Formula o derivacion | Tipo | Unidad | Nullabilidad | Regla de validacion | Consumidor principal | Observaciones |
|---|---|---|---|---|---|---|---|---|---|---|
| Velocidad Kg/h | `velocidad_kgh` | `stg`, `FactFormulario` | Velocidad de procesamiento de la linea en kilos por hora. | Captura directa. | `DECIMAL(18,2)` | kg/h | Nulo permitido | Si falta, algunos KPI horarios quedan pendientes. | Dashboard, operacion | Insumo de `% Comercial Kg` y `% Exportable`. |
| Velocidad manual | `velocidad_manual` | `stg`, `FactFormulario` | Ajuste manual de velocidad, si aplica. | Ingreso manual opcional. | `DECIMAL(18,2)` | kg/h | Nulo permitido | Debe diferenciarse de `velocidad_kgh`. | Operacion | Campo auxiliar de captura. |
| Kg/Hr | Sin columna unica en `stg` | Dashboard/servicio operacional | Velocidad efectiva usada para KPI de volumen. | Usa velocidad validada del contexto operacional. | Derivado | kg/h | N/A | Debe basarse en velocidad disponible y validada. | Dashboard | La documentacion funcional usa esta etiqueta; en la persistencia base el campo disponible es `velocidad_kgh`. |
| Kg Comercial 1h | Sin columna unica en `stg` | Dashboard/servicio operacional | Kilos comerciales de la ultima hora usados para KPI de volumen. | Derivado de actividad reciente y validacion operacional. | Derivado | kg/h o kg en ventana | N/A | Debe distinguirse de `fruta_comercial`. | Dashboard | No existe como columna del contrato Fase 0. |
| Kg FBC/h | Sin columna fisica en `stg` | Dashboard/servicio operacional | Kilos FBC por hora del status operacional. | `Kg Comercial validado * ((Fruta Sana + Choice) / Base calidad)`. | Derivado | kg/h | N/A | Requiere velocidad y base calidad validas. | Dashboard, jefatura, operacion | Visible como grafico principal. |
| Kg Exportable 1h | Sin columna fisica en `stg` | Dashboard/servicio operacional | Kilos exportables estimados de la ultima hora. | `max(Kg/Hr - Kg Comercial 1h, 0)`. | Derivado | kg/h | N/A | No puede ser negativo. | Dashboard | Visible en KPI superior. |
| Kg ultima hora | `kg_ultima_hora` | Captura operacional local | Campo operacional historicamente mencionado fuera del DW vigente. | Captura local. | N/A en DW | kg | Fuera de contrato Fase 0 | Queda excluido del DW vigente. | Operacion local | Existe en captura, pero no en `stg.FormularioHeader`. |

### 4.5 Estado y auditoria operacional

| Nombre funcional | Nombre fisico | Capa/origen | Definicion de negocio | Formula o derivacion | Tipo | Unidad | Nullabilidad | Regla de validacion | Consumidor principal | Observaciones |
|---|---|---|---|---|---|---|---|---|---|---|
| Estado formulario | `estado_formulario` | `stg`, `FactFormulario` | Estado operacional del registro. | Definido por app. | `NVARCHAR(20)` | N/A | No nulo | Valores funcionales esperados: `Borrador`, `Completo`. | Operacion, ETL | En core puede mantenerse como trazabilidad. |
| Es completo | `es_completo` | `stg`, `FactFormulario` | Indicador de completitud funcional del formulario. | Derivado por la app segun campos obligatorios. | `BIT` | booleano | No nulo | Solo se promueven a core registros con `es_completo = 1`. | ETL, dashboard | Regla critica del proceso DW. |
| Campos pendientes | `campos_pendientes` | `stg`, `FactFormulario` | Lista o resumen de datos faltantes al guardar. | `registro.campos_pendientes`. | `NVARCHAR(500)` | texto | Nulo permitido | Debe reflejar faltantes reales si `es_completo = 0`. | Operacion, QA datos | Se conserva por trazabilidad. |

## 5. Diccionario de detalle de defectos

### 5.1 Estructura de detalle

| Nombre funcional | Nombre fisico | Capa/origen | Definicion de negocio | Formula o derivacion | Tipo | Unidad | Nullabilidad | Regla de validacion | Consumidor principal | Observaciones |
|---|---|---|---|---|---|---|---|---|---|---|
| Codigo defecto | `codigo_defecto` | `stg.FormularioDefecto`, `dbo.DimDefecto` | Codigo oficial del defecto observado. | Captura/exportacion o seed catalog. | `NVARCHAR(20)` | N/A | No nulo en staging y dimension | Natural key oficial del defecto. | ETL, DW, dashboard | Debe existir en `DimDefecto` para cargar detalle a core. |
| Nombre defecto | `nombre_defecto` | `stg.FormularioDefecto`, `dbo.DimDefecto` | Nombre legible del defecto. | Captura/exportacion o seed catalog. | `NVARCHAR(200)` | N/A | Nulo permitido en staging; no nulo en dimension | Si staging viene nulo, ETL puede usar codigo como fallback descriptivo. | UI, BI, top defectos | |
| Cantidad defecto | `cantidad` | `stg.FormularioDefecto`, `FactFormularioDefecto` | Cantidad observada para un defecto especifico dentro del formulario. | Captura directa del detalle. | `INT` | frutos | No nulo | Debe ser mayor o igual a 0 y sumar a `suma_defectos`. | DW, analisis de mix, top defectos | Grano oficial: 1 fila por formulario y defecto. |
| Llave defecto | `defecto_key` | `dbo.DimDefecto`, `FactFormularioDefecto` | Llave surrogate del defecto en el DW. | `IDENTITY(1,1)` en `dbo.DimDefecto`. | `INT` | N/A | No nulo | FK valida a dimension. | DW, BI | No existe en captura operacional. |

### 5.2 Catalogo base de defectos en `dbo.DimDefecto`

| Codigo | Nombre oficial |
|---|---|
| `HAO` | Herida Abierta (Oxidada) |
| `HAF` | Herida Abierta (Fresca) |
| `MAC` | Machucon |
| `PAR` | Partidura |
| `GSS` | Golpe Sol Severo |
| `CRA` | Cracking |
| `DES` | Deshidratacion |
| `DP` | Desgarro Pedicelar |
| `LEN` | Lenticelosis |
| `BP` | Bitter Pit |
| `MR` | Manchas - Roce |
| `RLP` | Roce (Linea Proceso) |
| `FC` | Falta Color |
| `HC` | Herida Cicatrizada |
| `DI` | Dano Insecto |
| `DEF` | Deforme |
| `RAM` | Ramaleo |
| `RG` | Roce Grave |
| `RUS` | Russet Grave |
| `VEN` | Venturia |
| `PEN` | Penacho |
| `QSOL` | Quemado de sol |
| `INF` | Infiltracion |
| `PARD` | Pardeamiento |
| `COR` | Corcho |
| `EUL` | Eulia |
| `DQU` | Dano quimico |

## 6. Mapeo de capas

### 6.1 Flujo principal

| Capa funcional | Persistencia tecnica | Destino core | Comentario |
|---|---|---|---|
| Captura `Formulario` | `stg.FormularioHeader` | `dbo.FactFormulario` | Solo se promueven formularios completos. |
| Captura detalle defectos | `stg.FormularioDefecto` | `dbo.FactFormularioDefecto` | Grano 1 formulario x 1 defecto. |
| Catalogo defectos | `dbo.DimDefecto` | `dbo.FactFormularioDefecto` | Se usa `codigo_defecto` como natural key. |
| Filtros operacionales | `fecha_operacional`, `linea`, `especie` | consultas operacionales y marts futuros | Son ejes principales del dashboard. |
| KPI de dashboard | derivaciones sobre formularios completos y actividad reciente | servicios operacionales / vistas futuras | No todos los KPI existen como columnas fisicas base. |

### 6.2 Mapeo de nombres UI -> `stg` -> core

| Etiqueta funcional/UI | Nombre fisico staging | Nombre fisico core | Tipo de mapeo |
|---|---|---|---|
| Dia operacional | `fecha_operacional` | `fecha_operacional` | Directo |
| Linea | `linea_codigo`, `linea_nombre` | `linea_key` | Dimensionado |
| Especie | `especie` | `idEspecie` | Dimensionado |
| Variedad | `variedad` | `idVariedad` | Dimensionado |
| Centro logistico | `centro_codigo`, `centro_nombre` | `idCentroLogistico` | Dimensionado |
| Productor | `productor_codigo`, `productor_nombre` | `idProductor` | Dimensionado |
| Lugar de seleccion | `lugar_codigo`, `lugar_nombre` | `lugar_key` | Dimensionado |
| Cantidad Muestra Frutos | `cant_muestra` | `cant_muestra` | Directo |
| Defectos | `suma_defectos` y detalle `cantidad` | `suma_defectos` y `FactFormularioDefecto.cantidad` | Directo + agregado |
| Fruta Sana | `fruta_sana` | `fruta_sana` | Directo |
| Choice | `choice` | `choice` | Directo |
| % Exportable | `porc_exportable` | `porc_exportable` | Directo |
| % Sana FBC muestra | `porc_embalable` | `porc_embalable` | Alias funcional |
| % Choice | `porc_choice` | `porc_choice` | Directo |
| % Descartable | `porc_descartable` | `porc_descartable` | Directo |
| Velocidad Kg/h | `velocidad_kgh` | `velocidad_kgh` | Directo |
| Estado formulario | `estado_formulario` | `estado_formulario` | Directo |
| Borrador/Completo | `es_completo` | `es_completo` | Derivado conservado |

## 7. Reglas de validacion vigentes

### 7.1 Reglas funcionales minimas del contrato

| Regla | Interpretacion |
|---|---|
| `fruta_comercial = suma_defectos` | En el modelo vigente ambos campos deben coincidir. |
| `fruta_sana + choice + suma_defectos = cant_muestra` | La muestra debe cerrar completamente. |
| `cant_muestra > 0` | No existe formulario valido sin muestra. |
| `choice >= 0` | El conteo de choice no puede ser negativo. |
| `suma_defectos >= 0` | El total de defectos no puede ser negativo. |
| `es_completo = 1` para promover a core | Los borradores no deben entrar a `FactFormulario`. |

### 7.2 Reglas operacionales y de lectura

| Regla | Interpretacion |
|---|---|
| Si falta `velocidad_kgh`, algunos KPI horarios quedan pendientes | Impacta principalmente indicadores de volumen y status. |
| `% FBC Absoluto 1h` usa ventana movil de 1 hora respecto al ultimo `updated_at` | No equivale necesariamente a una hora cerrada de reloj. |
| `Kg Exportable` no puede ser negativo | Se fuerza por `max(..., 0)`. |
| `codigo_defecto` debe existir en `DimDefecto` para cargar detalle al core | Si no existe match, el detalle no deberia promoverse sin normalizacion. |

## 8. Ambiguedades y equivalencias documentales

| Caso | Decision documental |
|---|---|
| `% Sana FBC muestra` vs `porc_embalable` | Se declara que `% Sana FBC muestra` es el alias funcional oficial del campo fisico `porc_embalable`. |
| `% FBC` vs `% FBC Absoluto 1h` | `% FBC` es la formula compuesta base; `% FBC Absoluto 1h` es su expresion operacional sobre ventana movil de 1 hora. |
| `fruta_comercial` vs `Kg Comercial 1h` | `fruta_comercial` es un campo fisico entero del formulario/DW; `Kg Comercial 1h` es un KPI de volumen operacional distinto. No deben mezclarse. |
| `Kg/Hr` del dashboard vs `velocidad_kgh` del modelo | `Kg/Hr` es la etiqueta funcional; `velocidad_kgh` es el campo base persistido disponible en staging/core. |
| `kg_ultima_hora` | Se documenta como dato operacional fuera del contrato DW vigente. No existe en `stg.FormularioHeader`. |
| Borradores en dashboard vs DW core | El dashboard puede mostrar pendientes/borradores, pero el DW core solo carga completos. |
| `linea_codigo` y `linea_nombre` | En Fase 0 ambos pueden venir del mismo valor `registro.linea`; la semantica final de dimension depende del ETL. |

## 9. Cobertura de objetos revisados

Este documento cubre:

- todas las columnas vigentes de `stg.FormularioHeader`, incluyendo `dw_loaded_at`;
- todas las columnas vigentes de `stg.FormularioDefecto`, incluyendo `dw_loaded_at`;
- medidas y atributos relevantes de `dbo.FactFormulario`;
- estructura y grano de `dbo.FactFormularioDefecto`;
- catalogo base de `dbo.DimDefecto`;
- KPI visibles y formulas documentadas en manual, presentacion e historial tecnico.

Pendiente fuera de alcance de este documento:

- definicion fisica detallada de marts futuros;
- logica exacta de implementacion de servicios de dashboard no persistidos como columna DW;
- reglas ETL de Fase 1 mas alla de su impacto documental.
