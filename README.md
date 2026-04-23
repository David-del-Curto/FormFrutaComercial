# Form Fruta Comercial

Aplicacion Streamlit para captura de formularios de fruta comercial y seguimiento operativo diario en `Estatus Operacion`.

URL operativa actual en produccion: `http://192.168.200.74:8502/`.

## Documentacion principal
- [Manual de uso](docs/manual_usuario_estatus_operacion.md)
- [Presentacion ejecutiva](docs/presentacion_ejecutiva_estatus_operacion.md)
- [Historial tecnico de ajustes](docs/historial_tecnico_ajustes_estatus_operacion.md)
- [Deploy Oracle Linux 9](docs/deploy_oracle_linux_9.md)
- [Directrices DW Azure SQL](docs/dw_directrices_azure_sql.md)
- [Solicitud de mejora base](docs/Solicitud%20de%20mejora.txt)

## Componentes relevantes
- `streamlit_app.py`: entrada principal de la aplicacion.
- `core/dashboard.py`: dashboard `Estatus Operacion`.
- `config/operacion.toml`: configuracion de pantallas `kiosk` y destinatarios.
- `.streamlit/secrets.toml`: secretos locales de conexion y SMTP, no versionados.
- `.streamlit/secrets.example.toml`: template versionado para crear el archivo local por ambiente.
- `scripts/send_operacion_status_email.py`: job de correo/alertas.
- `Dockerfile`, `compose.prod.yml` y `compose.local.yml`: runtime en contenedor para produccion y validacion local.
- `.github/workflows/deploy.yml`: pipeline de validacion y despliegue por GitHub Actions.
- `sql/README.md`: guia de ejecucion SQL y script vigente.

## Ejecucion local
```powershell
cd c:\DEV\FormFrutaComercial
python -m streamlit run streamlit_app.py
```

## Verificacion tecnica rapida
```powershell
python -m compileall streamlit_app.py core services scripts engine.py
python scripts/smoke_test_runtime.py --skip-db
python scripts/smoke_test_runtime.py
python scripts/smoke_test_runtime.py --sp-checks
python scripts/send_operacion_status_email.py --dry-run --force-digest --skip-alerts
```

## Verificacion Docker local
```powershell
docker build -t form-fruta-comercial:local .
docker compose -f compose.prod.yml -f compose.local.yml up -d --build
docker compose -f compose.prod.yml -f compose.local.yml ps
docker compose -f compose.prod.yml -f compose.local.yml exec app python scripts/smoke_test_runtime.py --skip-db
docker compose -f compose.prod.yml -f compose.local.yml exec app python scripts/smoke_test_runtime.py
docker compose -f compose.prod.yml -f compose.local.yml exec app python scripts/smoke_test_runtime.py --sp-checks
docker compose -f compose.prod.yml -f compose.local.yml exec app python scripts/send_operacion_status_email.py --dry-run --force-digest --skip-alerts
```

## Operacion proyectada
- La navegacion principal expone `Formulario`, `Estatus Operacion` y `Manual de Usuario`.
- Las pantallas de linea usan `screen_id` por URL.
- El comportamiento de `kiosk` se configura en `config/operacion.toml`.
- Los correos de estatus se configuran con destinatarios en `config/operacion.toml` y SMTP en `.streamlit/secrets.toml`.
- `data/cache.db` se considera cache local de runtime y no forma parte de los artefactos versionados.
- En produccion, `/app/data` vive en el volumen Docker persistente `formfruta_data`, fuera del arbol versionado del repo.
- En produccion, la app publica Docker en `http://192.168.200.74:8502/`.
- En local, la validacion Docker queda en `http://localhost:8502/`.

## Despliegue productivo
- `Dockerfile` instala Python, dependencias de app y `ODBC Driver 18 for SQL Server`.
- `compose.prod.yml` publica la app en `8502`, que es el puerto disponible en el servidor.
- `compose.local.yml` solo se usa para validacion local con `localhost` y `FORM_FRUTA_SOURCE_SYSTEM` de desarrollo.
- `deploy/nginx-formfruta.conf.example` queda como ejemplo opcional si mas adelante decides poner reverse proxy delante de `8502`.
- `deploy/formfruta.service.example` muestra el servicio `systemd` para levantar el stack.
- `deploy/formfruta-email.service.example` y `deploy/formfruta-email.timer.example` muestran la ejecucion periodica del job de correo.
- `docs/deploy_oracle_linux_9.md` contiene el checklist detallado de despliegue en Oracle Linux 9 / RHEL.
- Si cambia la IP/NAT publica del host Linux, actualice el allowlist del logical server Azure SQL antes del redeploy y valide con `python scripts/smoke_test_runtime.py`.
- La app queda en `modo degradado` cuando Azure SQL no responde pero existe cache local reutilizable; si no hay cache suficiente, el formulario se bloquea sin botar la aplicacion.
