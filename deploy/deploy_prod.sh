#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-/home/soporte/FormFrutaComercial}"
DEPLOY_BRANCH="${2:-feature/mvp-streamlit}"
DATA_VOLUME="${FORMFRUTA_DATA_VOLUME:-formfruta_data}"
LEGACY_DATA_DIR="${FORMFRUTA_LEGACY_DATA_DIR:-$APP_DIR/data}"

cd "$APP_DIR"

legacy_data_exists() {
    [ -d "$LEGACY_DATA_DIR" ] && find "$LEGACY_DATA_DIR" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null | grep -q .
}

volume_has_data() {
    docker run --rm -v "$DATA_VOLUME:/dest" busybox sh -c 'find /dest -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null' | grep -q .
}

migrate_legacy_data() {
    docker volume create "$DATA_VOLUME" >/dev/null

    if ! legacy_data_exists; then
        return 0
    fi

    if volume_has_data; then
        return 0
    fi

    echo "Migrando datos legacy desde $LEGACY_DATA_DIR al volumen Docker $DATA_VOLUME"
    docker run --rm \
        -v "$DATA_VOLUME:/dest" \
        -v "$LEGACY_DATA_DIR:/src:ro" \
        busybox sh -c 'cp -a /src/. /dest/'
}

wait_for_app_health() {
    local health_url="http://127.0.0.1:8502/_stcore/health"
    local attempts="${FORMFRUTA_HEALTH_ATTEMPTS:-30}"
    local delay_seconds="${FORMFRUTA_HEALTH_DELAY_SECONDS:-2}"

    for attempt in $(seq 1 "$attempts"); do
        if curl -fsS "$health_url" >/dev/null; then
            return 0
        fi

        echo "Esperando healthcheck Streamlit ($attempt/$attempts)"
        sleep "$delay_seconds"
    done

    echo "La app no respondio healthcheck despues de $attempts intentos"
    docker compose -f compose.prod.yml ps || true
    docker compose -f compose.prod.yml logs --tail=120 app || true
    return 1
}

# Preservar secrets locales antes del pull (no están en git desde chore/destrackear)
_secrets_backup=""
_legacy_data_backup=""
cleanup_backups() {
    if [ -n "$_secrets_backup" ] && [ -f "$_secrets_backup" ]; then
        rm -f "$_secrets_backup"
    fi
    if [ -n "$_legacy_data_backup" ] && [ -d "$_legacy_data_backup" ]; then
        rm -rf "$_legacy_data_backup"
    fi
}
trap cleanup_backups EXIT

if [ -f ".streamlit/secrets.toml" ]; then
    _secrets_backup=$(mktemp)
    cp ".streamlit/secrets.toml" "$_secrets_backup"
fi
if [ -d "$LEGACY_DATA_DIR" ]; then
    _legacy_data_backup=$(mktemp -d)
    cp -a "$LEGACY_DATA_DIR/." "$_legacy_data_backup/"
fi

# Limpiar flags skip-worktree y resetear archivos que el pull necesita tocar
git update-index --no-skip-worktree .streamlit/secrets.toml data/cache.db 2>/dev/null || true
git checkout HEAD -- .streamlit/secrets.toml data/cache.db 2>/dev/null || true

git fetch --all --prune
git checkout "$DEPLOY_BRANCH"
git pull --ff-only origin "$DEPLOY_BRANCH"

# Restaurar secrets (git pull los borró del working tree al aplicar el commit de remoción)
if [ -n "$_secrets_backup" ] && [ -f "$_secrets_backup" ]; then
    mkdir -p .streamlit
    cp "$_secrets_backup" ".streamlit/secrets.toml"
    rm -f "$_secrets_backup"
fi
if [ -n "$_legacy_data_backup" ] && [ -d "$_legacy_data_backup" ]; then
    mkdir -p "$LEGACY_DATA_DIR"
    cp -a "$_legacy_data_backup/." "$LEGACY_DATA_DIR/"
    rm -rf "$_legacy_data_backup"
fi
migrate_legacy_data
docker compose -f compose.prod.yml build app
docker compose -f compose.prod.yml up -d app

wait_for_app_health

if command -v nginx >/dev/null 2>&1 && systemctl is-enabled nginx >/dev/null 2>&1; then
    sudo nginx -t
    sudo systemctl reload nginx
fi

if systemctl list-unit-files | grep -q '^formfruta-email.timer'; then
    sudo systemctl restart formfruta-email.timer
fi
