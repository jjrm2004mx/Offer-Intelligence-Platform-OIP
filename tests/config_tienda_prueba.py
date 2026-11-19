"""Configuración de pruebas con un comercio sintético (``tienda-prueba``, dominio example.com).

Desde T07 el paso 1 del motor valida el dominio de la oferta contra PAR-02 (DEC-212,
design.md §6). Las pruebas del motor que no son de validación usan ofertas sintéticas con
URL de example.com (CLAUDE.md §2.1: ninguna prueba abre una URL ni nombra un comercio fuera
de ``config/`` y ``tests/fixtures/``), así que necesitan un comercio cuyo dominio
autorizado sea example.com. Se agrega a la configuración base sin cambiar nada más.
"""

from __future__ import annotations

from pathlib import Path

from oip.configuracion import ConfiguracionVersionada, cargar_configuracion_texto

BASE = Path(__file__).parent / "fixtures" / "config" / "base.yaml"

#: Código del comercio sintético y su dominio autorizado.
TIENDA_PRUEBA = "tienda-prueba"
DOMINIO_PRUEBA = "example.com"

_RENGLON = (
    f"  {TIENDA_PRUEBA}: {{chain: {TIENDA_PRUEBA}, domains: [{DOMINIO_PRUEBA}], "
    "amazon_listing: false}\n"
)


def configuracion_con_tienda_prueba() -> ConfiguracionVersionada:
    """La configuración base de los escenarios más el comercio ``tienda-prueba``."""
    texto = BASE.read_text(encoding="utf-8")
    if texto.count("\nretailers:\n") != 1:
        raise AssertionError("base.yaml: se esperaba una sola sección retailers")
    texto = texto.replace("\nretailers:\n", "\nretailers:\n" + _RENGLON, 1)
    return cargar_configuracion_texto(texto, origen="base.yaml + tienda-prueba")
