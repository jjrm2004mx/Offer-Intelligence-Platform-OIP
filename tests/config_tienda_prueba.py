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


def con_tienda_prueba(texto: str) -> str:
    """El texto YAML de una configuración con el comercio ``tienda-prueba`` agregado a
    ``retailers`` (para las pruebas que cambian un parámetro de base.yaml)."""
    if texto.count("\nretailers:\n") != 1:
        raise AssertionError("base.yaml: se esperaba una sola sección retailers")
    return texto.replace("\nretailers:\n", "\nretailers:\n" + _RENGLON, 1)


def configuracion_con_tienda_prueba() -> ConfiguracionVersionada:
    """La configuración base de los escenarios más el comercio ``tienda-prueba``."""
    texto = con_tienda_prueba(BASE.read_text(encoding="utf-8"))
    return cargar_configuracion_texto(texto, origen="base.yaml + tienda-prueba")


# --- Sucursales sintéticas por cadena (decisión 28 del #34; T24) ---------------------------
# Para los fixtures de T12 en adelante: una sucursal de ``tienda-prueba`` y otra de una segunda
# cadena sintética, para no mezclar un comercio sintético con una sucursal de otro comercio de
# PAR-03. Los fixtures anteriores (``con_tienda_prueba``) no cambian.

#: Sucursal sintética de ``tienda-prueba``.
SUCURSAL_PRUEBA = "tp-cv"
#: Segunda cadena sintética, su dominio (debajo de example.com) y su sucursal.
TIENDA_PRUEBA_2 = "tienda-prueba-2"
DOMINIO_PRUEBA_2 = "otra.example.com"
SUCURSAL_PRUEBA_2 = "tp2-cv"

_RENGLON_2 = (
    f"  {TIENDA_PRUEBA_2}: {{chain: {TIENDA_PRUEBA_2}, domains: [{DOMINIO_PRUEBA_2}], "
    "amazon_listing: false}\n"
)
_SUCURSALES = (
    f"  {SUCURSAL_PRUEBA}: {{retailer: {TIENDA_PRUEBA}}}\n"
    f"  {SUCURSAL_PRUEBA_2}: {{retailer: {TIENDA_PRUEBA_2}}}\n"
)


def con_sucursales_prueba(texto: str) -> str:
    """El texto YAML de una configuración con ``tienda-prueba`` y ``tienda-prueba-2`` en
    ``retailers`` y sus sucursales ``tp-cv`` y ``tp2-cv`` en ``stores``."""
    texto = con_tienda_prueba(texto)
    if texto.count("\nstores:\n") != 1:
        raise AssertionError("base.yaml: se esperaba una sola sección stores")
    texto = texto.replace("\nretailers:\n", "\nretailers:\n" + _RENGLON_2, 1)
    return texto.replace("\nstores:\n", "\nstores:\n" + _SUCURSALES, 1)


def configuracion_con_sucursales_prueba() -> ConfiguracionVersionada:
    """La configuración base más los dos comercios sintéticos y sus sucursales."""
    texto = con_sucursales_prueba(BASE.read_text(encoding="utf-8"))
    return cargar_configuracion_texto(texto, origen="base.yaml + sucursales de prueba")
