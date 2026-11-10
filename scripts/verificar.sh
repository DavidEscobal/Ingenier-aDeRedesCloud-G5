#!/usr/bin/env bash
# Verificación antes de subir o proponer un Pull Request hacia fase2.
# 1) tests del núcleo  2) tests de los microservicios  3) contratos OpenAPI al día  4) sin secretos en los cambios.
# Uso (desde la raíz del repo):  bash scripts/verificar.sh [rama_base]     (por defecto: origin/fase2)
set -u
BASE="${1:-origin/fase2}"
OK=1
SEP=":"; case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) SEP=";";; esac
PY="${PYTHON:-python}"
APP_PATH="services/gateway/src${SEP}services/iam-service/src${SEP}services/slice-manager/src${SEP}services/topology-manager/src${SEP}services/image-catalog/src${SEP}tests/app${SEP}."

echo "== 1/4 Tests del núcleo (g5)"
CORE_PATH=""; [ "$SEP" = ";" ] && CORE_PATH="tools/winshim"
if PYTHONPATH="$CORE_PATH" "$PY" -m unittest discover -s tests 2>&1 | tail -3 | tee /dev/stderr | grep -q "^OK"; then :; else OK=0; echo "   FALLA: tests del núcleo"; fi

echo "== 2/4 Tests de los microservicios (requiere las dependencias de services/*/requirements.lock)"
if PYTHONPATH="$APP_PATH" "$PY" -m unittest discover -s tests/app 2>&1 | tail -3 | tee /dev/stderr | grep -q "^OK"; then :; else OK=0; echo "   FALLA: tests de microservicios"; fi

echo "== 3/4 Contratos OpenAPI al día"
if PYTHONPATH="$APP_PATH" "$PY" scripts/export_app_contracts.py >/dev/null 2>&1; then
  if git diff --ignore-all-space --quiet -- contracts/; then echo "   OK"; else OK=0; echo "   FALLA: la API cambió; revisa y commitea contracts/http/*.json"; fi
else OK=0; echo "   FALLA: no se pudieron exportar los contratos"; fi

echo "== 4/4 Secretos en los cambios respecto de $BASE"
git fetch -q origin 2>/dev/null || true
FILES=$(git diff --name-only "$BASE"...HEAD 2>/dev/null; git diff --name-only; git diff --name-only --cached)
BAD_FILES=$(printf '%s\n' "$FILES" | sort -u | grep -Ei '\.token$|keys\.json$|cluster\.json$|openstack\.env|(^|/)\.env$|id_ed25519|known_hosts|platform-config/|\.pem$|\.key$|\.db$|\.qcow2$|\.img$' || true)
BAD_LINES=$( (git diff "$BASE"...HEAD 2>/dev/null; git diff; git diff --cached) | grep '^+' | grep -Ei 'BEGIN [A-Z ]*PRIVATE KEY|OS_PASSWORD *=|Bearer [A-Za-z0-9_-]{30,}|access_token" *: *"ey|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{12,}' || true)
if [ -n "$BAD_FILES$BAD_LINES" ]; then
  OK=0; echo "   FALLA: posibles secretos:"; printf '%s\n' "$BAD_FILES" "$BAD_LINES" | sed '/^$/d; s/^/     /'
else echo "   OK"; fi

echo
if [ "$OK" = 1 ]; then echo "TODO OK: puedes subir tu rama y abrir el Pull Request."; exit 0
else echo "HAY FALLAS: no subas a fase2 hasta corregirlas."; exit 1; fi
