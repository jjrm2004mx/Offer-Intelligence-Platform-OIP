"""Prueba mínima del arranque técnico: el paquete importa y el marcador de escenario existe."""

import pytest

import oip


def test_el_paquete_importa():
    assert oip.__version__ == "0.0.0"


@pytest.mark.scenario("ARRANQUE")
def test_marcador_scenario_registrado():
    # Con --strict-markers, un marcador no registrado haría fallar la colección.
    assert True
