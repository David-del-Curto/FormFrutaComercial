# Deploy Oracle Linux 9

## Objetivo

Esta guia deja el proyecto listo para despliegue en Oracle Linux 9 / RHEL usando el runtime real del repositorio:

- Docker Engine + Docker Compose plugin
- `compose.prod.yml` para produccion
- `compose.local.yml` solo para pruebas locales
- Streamlit publicado en `0.0.0.0:8502`
- acceso operativo directo por `http://192.168.200.74:8502/`
- `systemd` para arranque y redeploy
- smoke tests del runtime, Azure SQL y consultas operativas

## Estado validado antes del server

La aplicacion ya quedo validada en Docker local con:

- build de la imagen OK
- contenedor `healthy`
- `python scripts/smoke_test_runtime.py --skip-db` OK
- `python scripts/smoke_test_runtime.py` OK
- `python scripts/smoke_test_runtime.py --sp-checks` OK
- `python scripts/send_operacion_status_email.py --dry-run --force-digest --skip-alerts` OK

Evidencia minima esperada:

```text
sql_ping: 1
centros_rows: 4
especies_rows: 12
SMOKE TEST OK
```

## Valores operativos que debes congelar

Antes de tocar el servidor, deja definidos estos valores:

```text
APP_DIR=/opt/form-fruta-comercial
APP_USER=formfruta
APP_GROUP=formfruta
PUBLIC_HOST=192.168.200.74
PUBLIC_URL=http://192.168.200.74:8502/
STREAMLIT_BIND=0.0.0.0:8502
LOCAL_URL=http://localhost:8502/
TIMEZONE=America/Santiago
```

Notas:

- `compose.local.yml` no se copia ni se usa en el servidor.
- El servidor debe usar `.streamlit/secrets.toml` del ambiente productivo, no el de DEV.
- Si en produccion cambia Azure SQL, SMTP o `FORM_FRUTA_SOURCE_SYSTEM`, debes dejarlo resuelto antes del primer build remoto.
- El despliegue automatico por GitHub Actions debe operar sobre la misma branch que esta publicada en el servidor.

## 1. Preparar el host Oracle Linux 9 / RHEL

Actualiza el sistema e instala dependencias base:

```bash
sudo dnf update -y
sudo dnf install -y git nginx curl dnf-plugins-core
```

Instala Docker Engine y Compose plugin:

```bash
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Activa Docker:

```bash
sudo systemctl enable --now docker
sudo systemctl status docker --no-pager
docker compose version
```

Crea usuario y carpeta operativa:

```bash
sudo useradd --system --create-home --home-dir /opt/form-fruta-comercial --shell /bin/bash formfruta || true
sudo mkdir -p /opt/form-fruta-comercial
sudo chown -R formfruta:formfruta /opt/form-fruta-comercial
```

Si SELinux esta activo:

- valida los contextos despues de copiar archivos
- no lo deshabilites como primer recurso

## 2. Copiar proyecto y secretos

Clona el repo con el usuario de servicio:

```bash
sudo -u formfruta git clone <URL_DEL_REPO> /opt/form-fruta-comercial
```

Si el repo ya existe:

```bash
sudo -u formfruta git -C /opt/form-fruta-comercial fetch --all
sudo -u formfruta git -C /opt/form-fruta-comercial checkout feature/mvp-streamlit
sudo -u formfruta git -C /opt/form-fruta-comercial pull --ff-only origin feature/mvp-streamlit
```

Crea las carpetas que usa el contenedor:

```bash
sudo -u formfruta mkdir -p /opt/form-fruta-comercial/.streamlit
sudo -u formfruta mkdir -p /opt/form-fruta-comercial/data
```

Importante:

- `data/` queda solo como ruta legacy para una migracion inicial.
- la persistencia productiva real pasa al volumen Docker `formfruta_data`
- el contenido actual de `/opt/form-fruta-comercial/data` se migra automaticamente la primera vez que ejecutes `deploy/deploy_prod.sh`

Copia los secretos reales del ambiente a:

```text
/opt/form-fruta-comercial/.streamlit/secrets.toml
```

Usa [`../.streamlit/secrets.example.toml`](../.streamlit/secrets.example.toml) como referencia de estructura.

Verifica permisos:

```bash
sudo chown -R formfruta:formfruta /opt/form-fruta-comercial
sudo chmod 700 /opt/form-fruta-comercial/.streamlit
sudo chmod 600 /opt/form-fruta-comercial/.streamlit/secrets.toml
```

Antes del primer arranque, revisa tambien `config/operacion.toml` con los destinatarios y pantallas reales de produccion.

## 3. Validar prerequisitos de red

Antes del primer `docker compose up`, confirma:

- salida HTTPS a `packages.microsoft.com`
- salida a Azure SQL productivo
- salida al SMTP productivo, si ya existe
- allowlist de la IP o NAT del host Linux en Azure SQL

Si SMTP todavia no esta disponible:

- continua con el despliegue de la app
- no habilites `formfruta-email.service` ni `formfruta-email.timer`

## 4. Primer arranque manual en el servidor

El despliegue productivo usa [../compose.prod.yml](../compose.prod.yml), que:

- construye desde [../Dockerfile](../Dockerfile)
- monta `config/operacion.toml`, `.streamlit/secrets.toml` y el volumen persistente `formfruta_data`
- publica `8502`, porque `8501` y `8503` ya estan ocupados en el servidor
- define `FORM_FRUTA_SOURCE_SYSTEM=form_fruta_comercial_prod_ol9`
- evita que un `git pull` toque la data persistente de la app

Build inicial:

```bash
cd /opt/form-fruta-comercial
sudo -u formfruta docker compose -f compose.prod.yml build app
```

Levanta el contenedor:

```bash
sudo -u formfruta docker compose -f compose.prod.yml up -d app
```

Revisa estado y logs:

```bash
sudo -u formfruta docker compose -f compose.prod.yml ps
sudo -u formfruta docker compose -f compose.prod.yml logs --tail=200 app
```

Valida el health endpoint:

```bash
curl -fsS http://127.0.0.1:8502/_stcore/health
```

Ejecuta los smoke tests dentro del contenedor:

```bash
sudo -u formfruta docker compose -f compose.prod.yml exec -T app python scripts/smoke_test_runtime.py --skip-db
sudo -u formfruta docker compose -f compose.prod.yml exec -T app python scripts/smoke_test_runtime.py
sudo -u formfruta docker compose -f compose.prod.yml exec -T app python scripts/smoke_test_runtime.py --sp-checks
```

Criterio de salida:

- los tres comandos deben terminar en `SMOKE TEST OK`

## 5. Publicacion de la app

La publicacion base del proyecto queda directa en `8502`, sin `nginx`, porque:

- `8501` ya esta ocupado por `monitorproduccion`
- `8503` ya esta ocupado por `formfrutaprocesada`
- la URL actual de esta app es `http://192.168.200.74:8502/`

Pruebas desde el host:

```bash
curl -I http://127.0.0.1:8502/
curl -I http://192.168.200.74:8502/
```

Pruebas desde cliente:

```text
http://192.168.200.74:8502/
```

`nginx` queda opcional. Si mas adelante decides volver a poner reverse proxy, el ejemplo base esta en [../deploy/nginx-formfruta.conf.example](../deploy/nginx-formfruta.conf.example) y debe apuntar a `127.0.0.1:8502`.

## 6. Configurar systemd

```bash
sudo cp /opt/form-fruta-comercial/deploy/formfruta.service.example /etc/systemd/system/formfruta.service
sudo systemctl daemon-reload
sudo systemctl enable --now formfruta.service
sudo systemctl status formfruta.service --no-pager
```

Revisa logs:

```bash
journalctl -u formfruta.service -n 100 --no-pager
```

El servicio debe quedar alineado con [../deploy/formfruta.service.example](../deploy/formfruta.service.example), que ejecuta:

- `docker compose up -d --build app`
- `docker compose stop app`

## 7. Validacion funcional post-despliegue

Desde el host:

```bash
curl -fsS http://127.0.0.1:8502/_stcore/health
curl -I http://127.0.0.1:8502/
```

Desde una estacion cliente dentro de la red:

```text
http://192.168.200.74:8502/
```

Valida:

- carga de la app
- acceso a `Formulario`
- acceso a `Estatus Operacion`
- acceso a `Manual de Usuario`
- apertura de una pantalla con `?screen_id=<id>`

Durante esa prueba, revisa logs del contenedor:

```bash
sudo -u formfruta docker compose -f /opt/form-fruta-comercial/compose.prod.yml logs --tail=200 app
```

## 8. Correo: dejar pendiente hasta tener SMTP

No habilites estos artefactos hasta tener credenciales reales:

- [../deploy/formfruta-email.service.example](../deploy/formfruta-email.service.example)
- [../deploy/formfruta-email.timer.example](../deploy/formfruta-email.timer.example)

Cuando el SMTP productivo exista, valida primero:

```bash
sudo -u formfruta docker compose -f /opt/form-fruta-comercial/compose.prod.yml exec -T app python scripts/send_operacion_status_email.py --dry-run --force-digest --skip-alerts
sudo -u formfruta docker compose -f /opt/form-fruta-comercial/compose.prod.yml exec -T app python scripts/send_operacion_status_email.py --force-digest --skip-alerts
```

Si ambas pruebas pasan, instala y habilita el timer:

```bash
sudo cp /opt/form-fruta-comercial/deploy/formfruta-email.service.example /etc/systemd/system/formfruta-email.service
sudo cp /opt/form-fruta-comercial/deploy/formfruta-email.timer.example /etc/systemd/system/formfruta-email.timer
sudo systemctl daemon-reload
sudo systemctl enable --now formfruta-email.timer
sudo systemctl status formfruta-email.timer --no-pager
```

## 9. Redeploy operativo

El flujo de redeploy queda encapsulado en [../deploy/deploy_prod.sh](../deploy/deploy_prod.sh):

```bash
cd /opt/form-fruta-comercial
bash deploy/deploy_prod.sh /opt/form-fruta-comercial
```

Ese script hace:

- `git fetch --all --prune`
- `git checkout <branch>`
- `git pull --ff-only origin <branch>`
- migracion unica de `/opt/form-fruta-comercial/data` hacia `formfruta_data` si el volumen aun esta vacio
- `docker compose -f compose.prod.yml build app`
- `docker compose -f compose.prod.yml up -d app`
- validacion del health endpoint local
- `nginx -t` y recarga
- reinicio del timer de correo si ya existe

Si vas a publicar `feature/mvp-streamlit`, el primer despliegue manual y el workflow deben usar esa misma branch.

## 10. Criterios de aceptacion

El despliegue queda aceptado cuando:

- `docker compose ps` muestra `app` en `healthy`
- `curl http://127.0.0.1:8502/_stcore/health` responde OK
- `smoke_test_runtime.py --skip-db` termina OK
- `smoke_test_runtime.py` termina OK
- `smoke_test_runtime.py --sp-checks` termina OK y devuelve catalogos
- la aplicacion responde por `http://192.168.200.74:8502/`
- `formfruta.service` queda habilitado y estable tras reinicio del host
- el correo queda deshabilitado hasta disponer de SMTP real

## Troubleshooting rapido

Si el build falla al instalar Docker o dependencias:

- verifica salida a internet y resolucion DNS del host
- confirma que `docker compose version` responda

Si el contenedor no llega a `healthy`:

- revisa `docker compose logs --tail=200 app`
- verifica que `.streamlit/secrets.toml` este presente y legible
- confirma que `config/operacion.toml` exista en el host

Si falla Azure SQL:

- valida el allowlist de la IP/NAT del host Linux
- reejecuta `python scripts/smoke_test_runtime.py --sp-checks`

Si falla el reverse proxy:

- valida `nginx -t`
- confirma que el contenedor responda en `127.0.0.1:8502`
- confirma que el proxy apunte a `127.0.0.1:8502`

## Referencias

- Docker Compose productivo: [../compose.prod.yml](../compose.prod.yml)
- Dockerfile del runtime: [../Dockerfile](../Dockerfile)
- Secretos por ambiente: [../.streamlit/secrets.example.toml](../.streamlit/secrets.example.toml)
- Servicio systemd: [../deploy/formfruta.service.example](../deploy/formfruta.service.example)
- Reverse proxy: [../deploy/nginx-formfruta.conf.example](../deploy/nginx-formfruta.conf.example)
