# Deploy Oracle Linux 9

## Objetivo

Esta guia deja el package listo para despliegue en Oracle Linux 9 / RHEL con:

- Python en `.venv` Linux
- `pyodbc` operativo
- Microsoft ODBC Driver 18
- Streamlit detras de `nginx`
- servicio `systemd`
- smoke tests de runtime y Azure SQL

## 1. Prerrequisitos del host

Instala paquetes base:

```bash
sudo dnf install -y git gcc gcc-c++ make python3.11 python3.11-devel openssl openssl-devel unixODBC unixODBC-devel nginx
```

Verifica Python:

```bash
python3.11 --version
```

## 2. Instalar Microsoft ODBC Driver 18

Segun Microsoft Learn, para RHEL y Oracle Linux debes registrar el repo de Microsoft e instalar `msodbcsql18`. Referencia oficial:

- https://learn.microsoft.com/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server

Comandos:

```bash
cd /tmp
curl -sSL -O https://packages.microsoft.com/config/rhel/9/packages-microsoft-prod.rpm
sudo yum install -y packages-microsoft-prod.rpm
rm -f packages-microsoft-prod.rpm
sudo yum remove -y unixODBC-utf16 unixODBC-utf16-devel
sudo ACCEPT_EULA=Y yum install -y msodbcsql18 mssql-tools18
```

Verifica el driver:

```bash
odbcinst -q -d
```

Debes ver:

```text
[ODBC Driver 18 for SQL Server]
```

## 3. Usuario de servicio y carpeta de despliegue

```bash
sudo useradd --system --create-home --shell /sbin/nologin formfruta
sudo mkdir -p /opt/form-fruta-comercial
sudo chown -R formfruta:formfruta /opt/form-fruta-comercial
```

Clona el proyecto:

```bash
sudo -u formfruta git clone <URL_GIT> /opt/form-fruta-comercial
cd /opt/form-fruta-comercial
```

## 4. Crear `.venv` Linux e instalar dependencias

```bash
sudo -u formfruta python3.11 -m venv /opt/form-fruta-comercial/.venv
sudo -u formfruta /opt/form-fruta-comercial/.venv/bin/pip install --upgrade pip wheel
sudo -u formfruta /opt/form-fruta-comercial/.venv/bin/pip install -r /opt/form-fruta-comercial/requirements.txt
```

Nota:

- `requirements.txt` ya incluye solo dependencias runtime del proyecto.
- `SQLAlchemy` y `pyodbc` son obligatorios para este package.

## 5. Configurar secretos

Coloca las credenciales solo del lado servidor en:

```text
/opt/form-fruta-comercial/.streamlit/secrets.toml
```

Permisos recomendados:

```bash
sudo chown formfruta:formfruta /opt/form-fruta-comercial/.streamlit/secrets.toml
sudo chmod 600 /opt/form-fruta-comercial/.streamlit/secrets.toml
sudo chmod 700 /opt/form-fruta-comercial/.streamlit
```

## 6. Smoke test antes de publicar

Prueba runtime local:

```bash
cd /opt/form-fruta-comercial
sudo -u formfruta /opt/form-fruta-comercial/.venv/bin/python scripts/smoke_test_runtime.py --sp-checks
```

Que valida:

- Python del `.venv`
- `pyodbc`
- presencia de `ODBC Driver 18 for SQL Server`
- conexion `SELECT 1` a Azure SQL
- lectura de catalogos via stored procedures
- inicializacion del store local

## 7. Publicacion recomendada

Recomendacion:

- Streamlit escuchando en `127.0.0.1:8501`
- `nginx` publicando la URL interna corporativa por HTTPS

Archivos de ejemplo incluidos:

- [formfruta.service.example](C:/DEV/FormFrutaComercial/deploy/formfruta.service.example)
- [nginx-formfruta.conf.example](C:/DEV/FormFrutaComercial/deploy/nginx-formfruta.conf.example)

## 8. Activar systemd

```bash
sudo cp /opt/form-fruta-comercial/deploy/formfruta.service.example /etc/systemd/system/formfruta.service
sudo systemctl daemon-reload
sudo systemctl enable --now formfruta.service
sudo systemctl status formfruta.service
```

Logs:

```bash
sudo journalctl -u formfruta.service -f
```

## 9. Activar nginx

```bash
sudo cp /opt/form-fruta-comercial/deploy/nginx-formfruta.conf.example /etc/nginx/conf.d/formfruta.conf
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```

## 10. Hardening minimo

- No exponer Streamlit directo a internet.
- Mantener `server.address=127.0.0.1` si usas `nginx`.
- Publicar solo via URL corporativa interna.
- Restringir `nginx` por subred.
- Ejecutar el servicio con usuario no root.
- Mantener permisos cerrados en `data/` y `.streamlit/secrets.toml`.

## 11. Smoke test de aplicacion

Valida el arranque del package:

```bash
cd /opt/form-fruta-comercial
sudo -u formfruta /opt/form-fruta-comercial/.venv/bin/python -m streamlit run streamlit_app.py --server.headless=true --server.address=127.0.0.1 --server.port=8501
```

Luego abre la URL interna publicada por `nginx`.

## 12. Troubleshooting rapido

Si `pip install -r requirements.txt` falla:

- Asegura que el repo del server tenga la ultima version del archivo. Una copia antigua podia incluir paquetes del entorno local y fijaciones invalidas como `cachetools==7.0.5`.
- Recomendacion: recrea el `.venv` Linux y vuelve a instalar con el `requirements.txt` actual.

Si ves `streamlit: command not found`:

- Normalmente significa que la instalacion de dependencias aborto antes de completar.
- Usa siempre el arranque mas robusto:

```bash
/opt/form-fruta-comercial/.venv/bin/python -m streamlit run streamlit_app.py --server.headless=true --server.address=127.0.0.1 --server.port=8501
```

## 13. Referencias oficiales

- Microsoft Learn, instalacion de ODBC Driver 18 para RHEL/Oracle Linux:
  https://learn.microsoft.com/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server
- Streamlit config.toml:
  https://docs.streamlit.io/develop/api-reference/configuration/config.toml
