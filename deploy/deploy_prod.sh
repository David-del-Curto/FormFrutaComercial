#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-/home/soporte/FormFrutaComecial}"
DEPLOY_BRANCH="${2:-main}"
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

git fetch --all --prune
git checkout "$DEPLOY_BRANCH"
git pull --ff-only origin "$DEPLOY_BRANCH"
migrate_legacy_data
docker compose -f compose.prod.yml build app
docker compose -f compose.prod.yml up -d app

curl -fsS http://127.0.0.1:8502/_stcore/health >/dev/null

if command -v nginx >/dev/null 2>&1 && systemctl is-enabled nginx >/dev/null 2>&1; then
    sudo nginx -t
    sudo systemctl reload nginx
fi

if systemctl list-unit-files | grep -q '^formfruta-email.timer'; then
    sudo systemctl restart formfruta-email.timer
fi
