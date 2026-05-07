@C:\DEV\FormFrutaComercial\docs\Plan 26-04 C.md /engineering:deploy-checklist Como Software & Data Arquitect debes seguir un plan para desplegar en ol9 una app Python/Streamlit, conservando la cache de registros en SQLite. Te adjunto el plan Plan 26-04 C.md. solo no consideres el Fix del KeyError porque ya esta OK

Leyó un archivo, usado una herramienta

Let me explore the repo structure to generate a precise, context-aware checklist.

Ejecutado 2 agentes

Good findings. Now let me write the deploy checklist plan.

Usó ToolSearch

Now I have everything I need. Writing the deploy checklist plan.

Creadoc-dev-formfrutacomercial-docs-plan-26-0-drifting-sonnet.md+171-0

Plan propuesto

El repo está listo para el deploy. Resumen del estado actual:

**Ya confirmado (repo limpio):**

- `.github/workflows/deploy.yml` — ambos jobs (`validate` + `deploy` en `formfruta-ol9`) ya configurados
- `deploy/deploy_prod.sh` — migración SQLite→`formfruta_data` incluida
- `compose.prod.yml` — volumen nombrado `formfruta_data` para persistencia
- `secrets.toml` y `cache.db` correctamente **no tracked** en git
- Rama activa: `feature/mvp-streamlit`

**Orden de ejecución:**

|Fase|Dónde|Estado|
|---|---|---|
|1. Preflight servidor|SSH → `192.168.200.74`|Pendiente tú|
|2. Self-hosted runner|GitHub UI + SSH|Pendiente tú|
|3. Variable `PROD_APP_DIR`|GitHub Settings|Opcional|
|4. `workflow_dispatch`|GitHub Actions UI|Pendiente tú|
|5. Validar post-deploy|SSH → servidor|Pendiente tú|
|6. systemd/nginx|SSH → servidor|**Diferido** (2a fase)|

El checklist completo está en el plan. ¿Empezamos por la Fase 1 (preflight SSH) o necesitas que te ayude con algún archivo antes del deploy?

@C:\DEV\FormFrutaComercial\.streamlit\secrets.toml Antes de ir con la fase 1, hice unos cambios en .secrets que son la configuración del SMTP para el envió de correos. Analízalo y haz los ajustes necesarios para desplegar todo el código actualizado hacia ol9

Voy a analizar cómo el código consume el `secrets.toml` para verificar que la estructura SMTP sea compatible.

Ejecutado un agente, leyó un archivo

La estructura del `secrets.toml` es **compatible con el código**. `services/operacion_email.py::load_mail_settings()` lee exactamente `[mail.smtp]` con esas claves. No hay cambios de código necesarios.

**Un punto a confirmar antes de continuar:**

SolicitadoDB producción

El secrets.toml tiene database = "DEV_ddc_datawarehouse". Para el deploy en OL9 producción, ¿cuál DB debe usar?

en produccion es ddc_datawarehouse

Entendido. Hay que cambiar `database` de `DEV_ddc_datawarehouse` a `ddc_datawarehouse` en el `secrets.toml` local, y luego sincronizarlo al servidor (no va por git).

Editadosecrets.toml+1-1

`secrets.toml` actualizado. Ahora hay que copiarlo al servidor — **esto no lo hace el CI/CD** porque el archivo está en `.gitignore`.

Ejecuta desde tu máquina (ajusta usuario/IP si difieren):

```
# Copiar secrets al servidor OL9scp C:/DEV/FormFrutaComercial/.streamlit/secrets.toml \    soporte@192.168.200.74:/home/soporte/FormFrutaComercial/.streamlit/secrets.toml
```

Si el directorio `.streamlit/` no existe aún en el servidor:

```
ssh soporte@192.168.200.74 "mkdir -p /home/soporte/FormFrutaComercial/.streamlit"# luego el scp de arriba
```

**Verificar en el servidor después del SCP:**

```
ssh soporte@192.168.200.74 \  "grep 'database\|host\|username' /home/soporte/FormFrutaComercial/.streamlit/secrets.toml"# Debe mostrar ddc_datawarehouse (sin DEV_) y smtp.office365.com
```

Una vez confirmado, procedes con **Fase 1 del preflight** (git status, docker group, etc.) y luego `workflow_dispatch`. ¿Tienes acceso SSH al servidor listo?

Tengo acceso al servidor SSH . completé las pruebas después del SCP *procedamos con la fase 1

Perfecto. Ejecuta estos bloques en orden vía SSH en `192.168.200.74`:

---

**1.1 — Directorio y rama**

```
cd /home/soporte/FormFrutaComercial && \git status && \git branch && \git log --oneline -3
```

**1.2 — Archivos de configuración locales**

```
ls -la .streamlit/secrets.toml && \ls -la config/operacion.toml
```

**1.3 — Docker y permisos**

```
docker ps && \docker volume ls | grep formfruta && \groups soporte && \systemctl is-active docker
```

**1.4 — Datos SQLite existentes**

```
ls -lh data/cache.db 2>/dev/null || echo "no legacy data" && \docker volume inspect formfruta_data 2>/dev/null || echo "volume not created yet"
```

---

Pega el output de cada bloque y vemos si hay algo que corregir antes de avanzar a la Fase 2 (runner).