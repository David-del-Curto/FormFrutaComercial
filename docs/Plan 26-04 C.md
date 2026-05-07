# Fix del `KeyError` y despliegue OL9 con CI/CD

## Resumen
- El error actual viene de `core/dashboard.py`: la tabla “Detalle del dia” renombra `porc_sana` como `"%FBC muestra"` sin espacio, pero luego intenta formatear `"% FBC muestra"` con espacio. Pandas no encuentra esa columna y lanza `KeyError`.
- El fix local mínimo es cambiar esa etiqueta a `"% FBC muestra"` y reconstruir Docker.
- Para OL9, el despliegue final usará self-hosted runner de GitHub en el servidor/LAN, no SSH desde `ubuntu-latest`, porque `192.168.200.74` es IP privada.

## Cambios Clave
- Corregir en `core/dashboard.py` el rename de `porc_sana`:
  `"%FBC muestra"` -> `"% FBC muestra"`.
- Validar localmente con:
  `docker compose -f compose.local.yml up -d --build --force-recreate`
  y revisar que `docker logs --tail 200 formfruta-app` no muestre `KeyError`.
- Antes de CI/CD, limpiar el repo:
  destrackear `.streamlit/secrets.toml`, `data/cache.db` y `__pycache__/*.pyc` con `git rm --cached`, manteniendo copias locales.
- Si `.streamlit/secrets.toml` tuvo credenciales reales en commits previos, rotar credenciales de Azure SQL/SMTP.

## OL9 + CI/CD
- Preflight en servidor:
  confirmar `/home/soporte/FormFrutaComercial`, permisos de `soporte`, existencia de `.streamlit/secrets.toml` y `config/operacion.toml`, y que `soporte` pueda ejecutar Docker.
- Si `soporte` no puede ejecutar Docker:
  agregarlo al grupo `docker`, cerrar sesión y entrar de nuevo antes del deploy.
- Instalar un GitHub self-hosted runner Linux x64 desde la UI del repo, con etiqueta `formfruta-ol9`, ejecutándose como usuario `soporte`.
- Ajustar `.github/workflows/deploy.yml`:
  mantener validación/build en `ubuntu-latest`, agregar job `deploy` en `[self-hosted, linux, x64, formfruta-ol9]`, y ejecutar localmente:
  `bash deploy/deploy_prod.sh /home/soporte/FormFrutaComercial feature/mvp-streamlit`.
- No usar secretos SSH para este flujo. Usar `PROD_APP_DIR=/home/soporte/FormFrutaComercial` como variable de GitHub o default del workflow.
- Dejar `systemd` para segunda fase después del primer deploy estable; instalar `formfruta.service` solo cuando Compose, health check, SQL y persistencia estén validados.

## Pruebas
- Local:
  compilar/importar, reconstruir contenedor, abrir `http://localhost:8502`, revisar “Detalle del dia”.
- Servidor OL9:
  `docker compose -f compose.prod.yml ps`
  `curl -fsS http://127.0.0.1:8502/_stcore/health`
  `docker compose -f compose.prod.yml exec -T app python scripts/smoke_test_runtime.py --skip-db`
  `docker compose -f compose.prod.yml exec -T app python scripts/smoke_test_runtime.py`
  `docker compose -f compose.prod.yml exec -T app python scripts/smoke_test_runtime.py --sp-checks`.
- CI/CD:
  ejecutar `workflow_dispatch`, confirmar que el job de deploy corre en el runner `formfruta-ol9` y que el contenedor queda `healthy`.

## Supuestos
- El fix del `KeyError` se aplica solo localmente por ahora.
- El deploy productivo seguirá usando branch `feature/mvp-streamlit`.
- La ruta correcta del servidor es `/home/soporte/FormFrutaComercial`.
- La app se publica directo en `8502`; nginx queda opcional.
