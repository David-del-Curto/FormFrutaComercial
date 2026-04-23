# Manual de Usuario - Form Fruta Comercial

Version: 2026-04-16

## 1. Para que sirve esta app
`Form Fruta Comercial` tiene tres secciones en el menu lateral:

- `Formulario`: para ingresar y completar registros de calidad.
- `Estatus Operacion`: para revisar el estado del dia por linea.
- `Manual de Usuario`: esta misma guia operativa.

La app esta pensada para dos usos principales:

- captura diaria de formularios por parte del equipo de calidad u operacion
- seguimiento visual del proceso en tablets, mini PCs o pantallas de linea

## 2. Flujo para quien ingresa formularios
### 2.1 Antes de comenzar
Revise que esta en la seccion `Formulario` y que tiene a mano:

- verificador
- centro logistico
- productor
- lote
- especie y variedad
- cantidad de muestra
- conteo de defectos, choice y fruta sana
- datos de velocidad o kilos de la ultima hora, si corresponden

### 2.2 Si va a continuar un registro pendiente
En `Gestion Formularios`:

- use `Registros para editar` para elegir un borrador
- presione `Cargar`
- complete lo que falta
- guarde nuevamente

Si quiere partir un registro nuevo:

- presione `Nuevo`

## 2.3 Orden recomendado de captura
1. Complete el encabezado: fecha, centro, linea, especie, variedad, lote, productor, lugar de seleccion y verificador.
2. Ingrese `Cantidad Muestra Frutos`.
3. Registre los defectos observados.
4. Revise el bloque de resultado y complete `Choice` y `Fruta Sana`.
5. Ingrese `Velocidad Kg/h` y `Kg/h Fruta Comercial` cuando aplique.
6. Agregue observaciones si corresponde.
7. Presione `Guardar Formulario` o `Completar y Guardar`.

### 2.4 Que significa cada estado
- `Borrador`: faltan datos obligatorios para que el registro quede completo.
- `Completo`: el registro ya puede ser usado en los KPI y en los procesos posteriores.

### 2.5 Recomendaciones operativas
- Si va a corregir un formulario pendiente, cargue el borrador y no cree uno nuevo.
- Si un formulario ya esta completo, no se vuelve a editar.
- Si falta `Velocidad Kg/h`, algunos indicadores quedaran pendientes.
- Revise el resumen de confirmacion antes de guardar.

## 3. Como leer Estatus Operacion
### 3.1 Filtros
En la parte superior encontrara:

- `Dia operacional`
- `Linea`
- `Especie`

Uso recomendado:

- elija la linea que quiere revisar
- confirme la especie sugerida
- ajuste la especie solo si la operacion real del momento es distinta

En modo pantalla o `kiosk`, estos filtros pueden quedar fijos y bloqueados.

### 3.2 KPI principales
Primera fila:

- `Formularios`
- `Completos`
- `Borradores`
- `Muestra acumulada`
- `Kg Exportable 1h`

Segunda fila:

- `% Exportable`
- `% Comercial Kg`
- `% Sana FBC muestra`
- `% Choice`
- `% Descartable`

Lectura rapida:

- mas `Borradores` significa mas formularios pendientes de cerrar
- `Kg Exportable 1h` ayuda a seguir el rendimiento reciente
- `% Sana FBC muestra` muestra la proporcion sana dentro de la base usada para calidad

### 3.3 Semaforo de ultima hora
El semaforo muestra el KPI `% FBC Absoluto (ultima hora)`.

Interpretacion:

- verde: menor a `1,0`
- amarillo: entre `1,0` y `1,49`
- rojo: `1,5` o mayor

El rombo marca el valor actual y el numero se muestra dentro del mismo grafico.

### 3.4 Graficos del dashboard
Primera fila:

1. `Promedio % FBC por hora (simple)`
2. `Tendencia % defectos por hora (tipo)`
3. `Status de Operacion (Kg FBC/h)`

Segunda fila:

1. `Muestra por turno`
2. `Kg exportable por hora (vaciado)`
3. `Top defectos`

Debajo encontrara:

- `Pendientes de completar`
- `Detalle del dia`

## 4. Uso en pantallas de linea
La app puede abrirse en modo fijo para proyeccion con una URL configurada por pantalla.

Ejemplo:

- `...?screen_id=dc05_lin_01`

Cuando una pantalla esta configurada:

- entra directo a `Estatus Operacion`
- fija la linea definida
- usa refresco automatico
- puede ocultar el menu lateral

Esto permite mostrar una linea especifica sin intervencion del usuario.

## 5. Correos de estatus
La operacion puede enviar correos de resumen y alerta.

Tipos de correo:

- resumen general del dia
- resumen por linea
- alerta por linea cuando `% FBC Absoluto 1h` supera el umbral configurado

Los destinatarios y horarios se administran en la configuracion operativa de la app.

## 6. Conceptos utiles para operar
- `% Exportable`: parte estimada que queda disponible despues de descontar fruta comercial de la ultima hora.
- `% Comercial Kg`: relacion entre kilos comerciales informados y velocidad de la linea.
- `% Sana FBC muestra`: proporcion sana dentro de la base de calidad usada para el calculo.
- `% Choice`: proporcion de fruta clasificada como choice.
- `% Descartable`: proporcion de defectos dentro de la base de calidad.
- `% FBC Absoluto (ultima hora)`: indicador principal mostrado en el semaforo de seguimiento inmediato.

## 7. Buenas practicas
- Capture primero y complete velocidades apenas esten disponibles.
- Mantenga controlados los borradores para que el dashboard use la mayor cantidad posible de registros completos.
- Use el filtro de linea antes de interpretar los KPI.
- Si una pantalla de linea queda fija por URL, no cambie manualmente la configuracion del equipo sin validar el `screen_id`.

## 8. Soporte operativo
Si la app no carga bien o una pantalla no muestra la linea esperada, revise primero:

- que la URL sea la correcta
- que el `screen_id` corresponda a la pantalla
- que exista conectividad al servidor
- que los datos del formulario hayan sido guardados

Si el problema persiste, escale al equipo que administra la configuracion y el despliegue de la app.
