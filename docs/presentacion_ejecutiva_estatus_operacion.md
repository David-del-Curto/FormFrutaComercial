# Presentacion Ejecutiva - Estatus Operacion

Version: 2026-04-16

## 1. Mensaje clave
El modulo `Estatus Operacion` evoluciono desde una vista de apoyo a una vista operacional proyectable, compacta y configurable por linea.

Hoy permite responder, en una sola pantalla:
- cuanto volumen horario se esta transformando en comercial
- que defectos dominan por hora
- cual es el impacto combinado en `% FBC`
- que linea necesita foco inmediato

## 2. Cambios ejecutivos mas relevantes
### UI y uso en sala
- Se elimino la imagen grande del dashboard para ganar altura util.
- Se retiro el titulo grande del cuerpo y se compactaron los bloques superiores.
- El semaforo ahora muestra el `% FBC Absoluto 1h` dentro del propio grafico, junto al rombo indicador.
- Se removieron textos auxiliares bajo el semaforo para priorizar la visualizacion de las dos primeras filas de graficos en pantallas grandes.
- El dashboard quedo ordenado para mostrar primero los 3 graficos de lectura principal.

### KPI y lectura
- `% FBC` duplicado fue eliminado de la grilla superior.
- La grilla de volumen/estado quedo en 5 columnas uniformes.
- La grilla de porcentajes quedo en 5 columnas, sin KPI redundantes.
- Se agregaron y consolidaron graficos para:
  - promedio `% FBC` por hora
  - tendencia `% defectos por hora (tipo)`
  - `Kg FBC/h`
  - `Kg exportable por hora`
  - `Top defectos` con porcentaje visible

### Operacion proyectada
- Se agrego modo `kiosk` por URL/config, pensado para mini PCs por linea.
- El refresh automatico se limita al modo kiosk; tablets y uso manual no se refrescan solas.

### Correos
- El estatus del dia puede salir por correo via un job independiente.
- El modelo contempla resumen general, resumen por linea y alertas por umbral de `% FBC Absoluto 1h`.

## 3. Orden actual de lectura en pantalla
Primera fila de graficos:
1. `Promedio % FBC por hora (simple)`
2. `Tendencia % defectos por hora (tipo)`
3. `Status de Operacion (Kg FBC/h)`

Segunda fila de graficos:
1. `Muestra por turno`
2. `Kg exportable por hora (vaciado)`
3. `Top defectos`

Esto deja visible, con menor scroll, la lectura principal que se quiere proyectar en sala.

## 4. KPI oficiales
Base de volumen:
- `Kg Exportable = max(Kg/Hr - Kg Comercial 1h, 0)`
- `% Comercial Kg = Kg Comercial 1h / Kg/Hr * 100`
- `% Exportable = Kg Exportable / Kg/Hr * 100`

Base de calidad:
- `% Sana FBC muestra = Sana / (Sana + Choice + Defectos) * 100`
- `% Choice = Choice / (Sana + Choice + Defectos) * 100`
- `% Descartable = Defectos / (Sana + Choice + Defectos) * 100`

Indicador combinado:
- `% FBC = (% Sana + % Choice) * % Comercial Kg / 100`

Complemento horario:
- `Kg FBC/h = Kg Comercial validado * ((Fruta Sana + Choice) / Base Calidad)`

## 5. Gobernanza y automatizacion
### Pantallas por linea
Se configura en:
- `config/operacion.toml`

Cada pantalla usa:
- `screen_id`
- `linea`
- `refresh_seconds`
- `lock_filters`
- `hide_sidebar`

### Correo
Configuracion funcional:
- `config/operacion.toml`

Configuracion SMTP:
- `.streamlit/secrets.toml`

Script de envio:
- `scripts/send_operacion_status_email.py`

## 6. Riesgos o decisiones abiertas
- Los destinatarios globales hoy tambien entran en los correos por linea.
- El refresh kiosk depende de que cada mini PC abra la URL correcta con `screen_id`.
- Si se quieren destinatarios estrictamente separados entre resumen general y linea, se requiere un ajuste menor en la logica del job.

## 7. Recomendacion de uso
Para operacion:
- usar `screen_id` por linea en pantallas fijas
- dejar tablets en modo interactivo normal

Para jefatura/calidad:
- revisar primero la fila superior de KPI y el semaforo
- luego la primera fila de graficos
- terminar con `Top defectos` y `Pendientes`

## 8. Siguiente paso natural
- completar destinatarios reales y SMTP
- calendarizar el job de correo en Linux
- validar una prueba controlada con 1 linea y 1 mini PC antes de desplegar al resto
