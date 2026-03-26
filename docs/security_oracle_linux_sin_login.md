# Seguridad y Despliegue en Oracle Linux 9 / RHEL

## Resumen ejecutivo

Este sistema puede defenderse sin login integrado solo si se presenta como lo que realmente es:

- una aplicacion operativa interna;
- de acceso restringido a red corporativa;
- con secretos y acceso a datos solo del lado servidor;
- y con controles compensatorios en red, host y despliegue.

No debe presentarse como equivalente a una aplicacion con autenticacion de usuario, perfilamiento o RBAC.

## Que ya queda cubierto en la app

1. Las credenciales de Azure SQL quedan del lado servidor mediante `st.secrets`; no se exponen al navegador.
2. El formulario ahora puede persistir una clave de negocio estable por registro (`source_business_key`) y un `source_system`, lo que mejora trazabilidad tecnica entre borrador, completo y futuras cargas DW.
3. La configuracion de Streamlit del proyecto endurece algunos puntos base:
   - `enableCORS = true`
   - `enableXsrfProtection = true`
   - `enableStaticServing = false`
   - `toolbarMode = "viewer"`
   - `showErrorDetails = "type"`
   - `gatherUsageStats = false`

Archivo relacionado:

- [config.toml](C:/DEV/FormFrutaComercial/.streamlit/config.toml)

## Argumento correcto para justificar ausencia de login

La justificacion solida no es "no hace falta seguridad", sino esta:

"La aplicacion no fue disenada como portal abierto ni como sistema transaccional orientado a usuarios finales. Se opera como herramienta interna de captura en una zona de red controlada, con acceso restringido por red corporativa, endurecimiento del host, secretos solo del lado servidor y trazabilidad tecnica por registro. Por diseno, la seguridad se resuelve con controles compensatorios de infraestructura y operacion, no con identidad individual embebida en la aplicacion."

Eso es defendible si, y solo si, cumples los controles de abajo.

## Controles obligatorios para pasar a validacion / produccion

### 1. Aislamiento de red

- No exponer la app a internet.
- Publicar solo dentro de la red corporativa o una VLAN operacional definida.
- Restringir acceso por firewall, ACL o reverse proxy a subredes autorizadas.
- Idealmente no abrir el puerto de Streamlit a toda la red; exponerlo a traves de reverse proxy interno.

### 2. Cifrado y publicacion

- Terminar TLS en Nginx, Apache o balanceador corporativo.
- No usar `sslCertFile` / `sslKeyFile` nativos de Streamlit para produccion.
- Definir una URL interna corporativa controlada y estable.

### 3. Endurecimiento del host

- Ejecutar el servicio con un usuario dedicado no root.
- Permisos restringidos en:
  - carpeta del proyecto;
  - `data/`;
  - `.streamlit/secrets.toml`.
- Mantener parches del sistema operativo y paquetes al dia.
- Deshabilitar acceso shell innecesario para operadores funcionales.
- Habilitar reinicio controlado via `systemd`.

### 4. Endurecimiento de aplicacion

- Mantener `enableCORS = true` y `enableXsrfProtection = true`.
- No habilitar servicio de archivos estaticos.
- No mostrar trazas completas ni errores sensibles al navegador.
- No almacenar secretos dentro del codigo fuente ni en repositorio.

### 5. Base de datos y secretos

- Usar un usuario SQL dedicado con privilegios minimos.
- Separar credenciales por ambiente.
- Guardar secretos fuera del repo y con permisos de lectura solo para la cuenta del servicio.
- Si es posible, limitar acceso del SQL solo desde la IP o segmento del servidor de aplicacion.

## Riesgos residuales que debes declarar con honestidad

Sin login, estos riesgos siguen existiendo:

- no hay autenticacion individual;
- no hay autorizacion por rol;
- no hay no-repudio por usuario;
- cualquier usuario con acceso a la URL interna puede operar la app;
- el campo `Verificador` aporta trazabilidad operativa, pero no reemplaza identidad fuerte.

En otras palabras:

- sirve para una app interna operada en entorno controlado;
- no sirve como argumento de identidad personal fuerte ni de segregacion de funciones.

## Cuando deja de ser aceptable no tener login

Debes agregar autenticacion si ocurre cualquiera de estas condiciones:

- acceso desde fuera de la red corporativa;
- acceso desde usuarios no controlados o muchos sitios abiertos;
- necesidad de auditoria por persona con valor legal o normativo;
- necesidad de perfiles, aprobaciones o segregacion de funciones;
- datos sensibles con exigencia formal de acceso nominal.

## Checklist minimo para despliegue

- usuario de sistema dedicado, por ejemplo `formfruta`
- permisos cerrados sobre proyecto y secretos
- reverse proxy interno con TLS
- allowlist de red corporativa
- `systemd` con reinicio automatico
- credenciales SQL separadas por ambiente
- respaldo del archivo SQLite local si sigue existiendo en produccion
- monitoreo de logs y rotacion

## Posicion recomendada para comite o validacion

Puedes defenderlo asi:

"Esta solucion se valida como aplicacion interna de captura operacional, no como sistema de acceso nominal por usuario. La ausencia de login se compensa con segmentacion de red, endurecimiento del host Oracle Linux, secretos solo del lado servidor, protecciones XSRF/CORS, minimizacion de exposicion de errores y trazabilidad tecnica por formulario. Si el alcance evoluciona a control por persona, segregacion de funciones o acceso fuera de la red controlada, el siguiente paso obligatorio es incorporar autenticacion corporativa."
