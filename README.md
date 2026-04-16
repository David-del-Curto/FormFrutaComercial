# Form Fruta Comercial

Aplicacion Streamlit para captura de formularios de fruta comercial y seguimiento operativo diario en `Estatus Operacion`.

## Documentacion principal
- [Manual de uso](docs/manual_usuario_estatus_operacion.md)
- [Presentacion ejecutiva](docs/presentacion_ejecutiva_estatus_operacion.md)
- [Historial tecnico de ajustes](docs/historial_tecnico_ajustes_estatus_operacion.md)
- [Directrices DW Azure SQL](docs/dw_directrices_azure_sql.md)
- [Solicitud de mejora base](docs/Solicitud%20de%20mejora.txt)

## Componentes relevantes
- `streamlit_app.py`: entrada principal de la aplicacion.
- `core/dashboard.py`: dashboard `Estatus Operacion`.
- `config/operacion.toml`: configuracion de pantallas `kiosk` y destinatarios.
- `.streamlit/secrets.toml`: secretos de conexion y SMTP.
- `scripts/send_operacion_status_email.py`: job de correo/alertas.
- `sql/README.md`: guia de ejecucion SQL y script vigente.

## Ejecucion local
```powershell
cd c:\DEV\FormFrutaComercial
python -m streamlit run streamlit_app.py
```

## Verificacion tecnica rapida
```powershell
python -m compileall streamlit_app.py core services scripts engine.py
python scripts/send_operacion_status_email.py --dry-run --force-digest --skip-alerts
```

## Operacion proyectada
- Las pantallas de linea usan `screen_id` por URL.
- El comportamiento de `kiosk` se configura en `config/operacion.toml`.
- Los correos de estatus se configuran con destinatarios en `config/operacion.toml` y SMTP en `.streamlit/secrets.toml`.
