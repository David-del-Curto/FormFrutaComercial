# Historial Tecnico de Ajustes - Estatus Operacion

Version: 2026-04-16

## 1. Alcance
Este documento resume los ajustes implementados desde el hito registrado en las notas como **"Nuevos requerimientos y ajustes"**, donde se solicito remover la imagen del tab de `Estatus Operacion`.

El objetivo es dejar trazabilidad tecnica y funcional de los cambios realmente integrados en la aplicacion.

## 2. Estado anterior de referencia
En ese punto, el dashboard presentaba varias limitaciones:
- uso de una imagen grande y mayor consumo de altura visual
- encabezado/padding que generaba scroll temprano
- menor foco en pantallas de operacion proyectadas
- sin modo `kiosk`
- sin motor de correo independiente
- sin consolidacion final de orden de graficos y compactacion KPI

## 3. Ajustes implementados por bloque
### 3.1 Navegacion y shell visual
- Se abandono la idea de `sticky header` custom porque ocupaba demasiado espacio y generaba mala experiencia visual.
- La app quedo con menu lateral de Streamlit como navegacion principal.
- En `Estatus Operacion` se oculta el header shell de Streamlit y se reduce el padding superior para ganar altura util.
- Se elimino el titulo grande del cuerpo (`Planilla Fruta Comercial`) en el dashboard de operacion.
- Se elimino la imagen grande del tab de estatus.

Impacto:
- mejor uso de pantalla en mini PCs y proyeccion continua
- menor scroll inicial

### 3.2 Filtros del dashboard
- El dashboard quedo con filtros alineados de `Dia operacional`, `Linea` y `Especie`.
- `Especie` conserva autocompletado por linea, pero permanece editable en modo normal.
- El texto `Filtros de analisis` fue eliminado para ahorrar altura visual.

Impacto:
- se reduce ruido visual sin perder control funcional

### 3.3 KPI superiores
- La grilla de volumen/estado se consolido en 5 columnas:
  - `Formularios`
  - `Completos`
  - `Borradores`
  - `Muestra acumulada`
  - `Kg Exportable 1h`
- La grilla de porcentajes se consolido en 5 columnas:
  - `% Exportable`
  - `% Comercial Kg`
  - `% Sana`
  - `% Choice`
  - `% Descartable`
- Se elimino `% FBC` de la grilla porque duplicaba el mismo valor que `% FBC 1h`.

Impacto:
- menor redundancia
- mejor simetria visual

### 3.4 Semaforo FBC
Evolucion del bloque:
1. Se agrego semaforo con bandas verde/amarillo/rojo.
2. Se elimino el titulo `Semaforo FBC 1h`.
3. Se removieron captions apilados para evitar ocupar altura.
4. El valor principal `% FBC 1h` se incorporo dentro del propio grafico, a continuacion del rombo indicador.
5. Finalmente, se eliminaron los textos informativos bajo el semaforo para dejar visible la segunda fila de graficos en pantallas kiosk.

Estado actual:
- barra de semaforo
- rombo indicador
- porcentaje renderizado dentro del chart
- sin labels auxiliares bajo el chart

### 3.5 Claridad de ventana movil
Se confirmo y document� la logica operativa:
- la ventana KPI es de 1 hora movil respecto al ultimo `updated_at`
- no corresponde necesariamente a una hora reloj cerrada
- si dentro de esa hora solo existen registros en una fraccion menor, la actividad visible se concentra en ese tramo

Ejemplo:
- `21:35 - 22:35` puede ser la ventana logica
- `22:05 - 22:35` puede ser el tramo donde si hubo registros

### 3.6 Graficos incorporados y reordenados
Se consolidaron los siguientes graficos del dashboard:
- `Promedio % FBC por hora (simple)`
- `Tendencia % defectos por hora (tipo)`
- `Status de Operacion (Kg FBC/h)`
- `Muestra por turno`
- `Kg exportable por hora (vaciado)`
- `Top defectos`

Orden actual:
Primera fila:
1. `Promedio % FBC por hora (simple)`
2. `Tendencia % defectos por hora (tipo)`
3. `Status de Operacion (Kg FBC/h)`

Segunda fila:
1. `Muestra por turno`
2. `Kg exportable por hora (vaciado)`
3. `Top defectos`

Adicionalmente:
- `Top defectos` muestra porcentaje al final de cada barra.
- Los graficos usan formato LATAM para miles y decimales.

### 3.7 Nuevas metricas y calculos analiticos
Se integraron capacidades analiticas que no estaban en la version inicial:
- `Kg FBC/h`
- tendencia `% defectos por hora (tipo)`
- `Kg exportable por hora`
- promedio simple `% FBC por hora`
- filtros de apertura por linea/especie

### 3.8 Reglas y estabilidad del dashboard
Se aplicaron ajustes de robustez para evitar errores de runtime:
- eliminacion de doble fuente de verdad en `bi_fecha_operacional`
- firma tolerante de `render_como_vamos(...)`
- correcciones para hot reload parcial de Streamlit

### 3.9 Modo kiosk para pantallas
Se implemento modo operativo por URL/configuracion:
- query param: `screen_id=<id>`
- config en `config/operacion.toml`
- soporte para:
  - linea fija
  - refresh automatico
  - bloqueo de filtros
  - ocultar sidebar si corresponde

Dise�o final adoptado:
- diferenciar pantallas y tablets por URL/config, no por `User-Agent`

### 3.10 Correos de estatus y alertas
Se implemento una base operativa completa para correo:
- configuracion funcional en `config/operacion.toml`
- configuracion SMTP en `.streamlit/secrets.toml`
- snapshot reutilizable de KPI/estado para UI y correo
- script independiente `scripts/send_operacion_status_email.py`
- persistencia local para deduplicar digests y alertas

Tipos de envio:
- resumen general
- resumen por linea
- alerta por linea cuando `% FBC 1h >= 1,5`

### 3.11 Configuracion de prueba actual
Configuracion funcional dejada para pruebas:
- `mail.global_recipients = ["bastian.barahona@ddc.cl"]`
- `mail.line_recipients.LIN_01 = ["bastian.barahona@ddc.cl"]`

Nota operativa vigente:
- los destinatarios globales tambien entran en correos por linea, porque el job combina ambas listas y deduplica usuarios repetidos.

### 3.12 Ajustes del formulario relacionados
Aunque el foco fue `Estatus Operacion`, tambien quedaron ajustes de UX en `Formulario`:
- alineacion de `Cargar` y `Nuevo` con el `selectbox`
- mantenimiento del flujo de borradores y nuevas capturas sin cambios funcionales

## 4. Archivos nuevos o consolidados en este tramo
Archivos de soporte agregados o consolidados:
- `services/operacion_config.py`
- `services/operacion_status.py`
- `services/operacion_email.py`
- `config/operacion.toml`
- `scripts/send_operacion_status_email.py`

Archivos principales ajustados:
- `streamlit_app.py`
- `core/dashboard.py`
- `core/ui.py`
- `services/local_store.py`
- `.streamlit/secrets.toml`

## 5. Limpieza documental y archivos obsoletos
Se consideran obsoletos y prescindibles los siguientes artefactos temporales del proceso de ajuste:
- notas sueltas (`Sin t�tulo.md`)
- planes temporales con encoding degradado (`PLAN.md`)
- respaldos locales de arranque (`streamlit_app copy.py`, `streamlit_app copy 2.py`)

Estos archivos no deben seguir siendo la referencia documental del proyecto.

## 6. Fuente de verdad recomendada desde ahora
Documentacion funcional:
- `docs/manual_usuario_estatus_operacion.md`
- `docs/presentacion_ejecutiva_estatus_operacion.md`

Trazabilidad tecnica de ajustes:
- `docs/historial_tecnico_ajustes_estatus_operacion.md`
