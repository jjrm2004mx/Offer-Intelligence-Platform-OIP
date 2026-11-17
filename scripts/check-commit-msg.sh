#!/usr/bin/env bash
# Verifica los trailers de trazabilidad de un mensaje de commit (DEC-071, DEC-174, DEC-193).
#
#   Change: <id>   siempre (minúsculas, números y guiones).
#   Refs: #N       obligatorio, salvo con "Change: docs".
#                  En el Worker se acepta "Refs: jjrm2004mx/<repo>#N" (DEC-174).
#
# Uso: check-commit-msg.sh <archivo-del-mensaje>
# Lo usan el hook .githooks/commit-msg y el gate de trazabilidad en GitHub Actions.
set -euo pipefail

msg_file="${1:?falta el archivo del mensaje}"
# Sin comentarios de git (#) y sin retornos de carro de Windows.
msg="$(grep -v '^#' "$msg_file" | tr -d '\r')"
subject="$(printf '%s\n' "$msg" | head -n 1)"

# Commits que git genera solo: no se exigen trailers.
case "$subject" in
  "Merge "*|"Revert \""*|"fixup! "*|"squash! "*|"amend! "*) exit 0 ;;
esac

change="$(printf '%s\n' "$msg" | sed -n 's/^Change: *\([a-z0-9][a-z0-9-]*\) *$/\1/p' | tail -n 1)"
if [ -z "$change" ]; then
  echo "ERROR: falta el trailer 'Change: <id>' (por ejemplo 'Change: req-2026-0001-b-evaluacion' o 'Change: docs')." >&2
  echo "       Asunto: $subject" >&2
  exit 1
fi

if [ "$change" = "docs" ]; then
  exit 0
fi

if ! printf '%s\n' "$msg" | grep -Eq '^Refs: *(#[0-9]+|[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[0-9]+)'; then
  echo "ERROR: falta el trailer 'Refs: #N' (obligatorio salvo con 'Change: docs')." >&2
  echo "       Asunto: $subject" >&2
  exit 1
fi
