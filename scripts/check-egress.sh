#!/usr/bin/env bash
# Gate estático de egress del Core (DEC-041, DEC-122, DEC-173).
# Falla si src/ contiene spiders, navegadores automatizados o dominios de comercios.
# Los dominios autorizados de cada comercio viven en la configuración versionada,
# fuera de src/; este gate solo mira el código.
#
# Es la parte estática del gate (EXT-016): la prueba del firewall de casa es una
# prueba de host, con el runbook, y no corre en GitHub Actions.
set -euo pipefail

src="${1:-src}"
fail=0

dominios='(homedepot|walmart|target|bestbuy|gamestop|nintendo|amazon)\.com'
if grep -rEniI --include='*.py' "$dominios" "$src"; then
  echo "ERROR: el Core menciona dominios de comercios (DEC-173)." >&2
  fail=1
fi

librerias='^[[:space:]]*(import|from)[[:space:]]+(scrapy|scrapy_playwright|playwright|selenium|undetected_chromedriver|pyppeteer)\b'
if grep -rEnI --include='*.py' "$librerias" "$src"; then
  echo "ERROR: el Core importa una librería de scraping o de navegador (DEC-173)." >&2
  fail=1
fi

if [ "$fail" -eq 0 ]; then
  echo "Egress estático: OK ($src sin spiders, navegadores ni dominios de comercios)."
fi
exit "$fail"
