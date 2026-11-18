"""Pruebas de la estructura del paquete (CMP-01; tasks.md T01 1.1) y de la regla de que
solo oip.dinero redondea (design.md §8)."""

import importlib
from pathlib import Path

import pytest

import oip

RAIZ_OIP = Path(oip.__file__).parent


@pytest.mark.parametrize("subpaquete", ["oip.entradas", "oip.evaluacion", "oip.persistencia"])
def test_los_subpaquetes_importan(subpaquete):
    modulo = importlib.import_module(subpaquete)
    assert modulo.__doc__


def test_marcador_integracion_registrado(pytestconfig):
    nombres = [linea.split(":", 1)[0].strip() for linea in pytestconfig.getini("markers")]
    assert "integracion" in nombres
    assert "scenario(id)" in nombres


def test_solo_dinero_redondea():
    # Ningún otro módulo usa quantize (design.md §8; guía de implementación de T01).
    infractores = [
        archivo.relative_to(RAIZ_OIP).as_posix()
        for archivo in RAIZ_OIP.rglob("*.py")
        if archivo != RAIZ_OIP / "dinero.py" and "quantize" in archivo.read_text(encoding="utf-8")
    ]
    assert infractores == []
