# Git y Referencias Rapidas

## Documentacion vigente
- `README.md`: punto de entrada del proyecto.
- `docs/manual_usuario_estatus_operacion.md`: manual operativo actual.
- `docs/presentacion_ejecutiva_estatus_operacion.md`: resumen ejecutivo para comite/jefaturas.
- `docs/historial_tecnico_ajustes_estatus_operacion.md`: trazabilidad tecnica de ajustes recientes.

## Flujo local sugerido
```powershell
cd c:\DEV\FormFrutaComercial
git status
python -m compileall streamlit_app.py core services scripts engine.py
git add .
git commit -m "mensaje"
git push
```

## Flujo Linux sugerido
```bash
cd /home/soporte/FormFrutaComercial
git pull
source .venv/bin/activate
python -m compileall streamlit_app.py core services scripts engine.py
```

## Notas
- Revisar `config/operacion.toml` antes de probar pantallas `kiosk` o correos.
- Revisar `.streamlit/secrets.toml` antes de probar SMTP.
