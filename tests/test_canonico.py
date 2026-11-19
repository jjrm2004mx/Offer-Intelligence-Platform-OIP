"""Pruebas de T04 4.1: casos límite del JSON canónico (CTR-06) y de la verificación estricta
de tipos (DEC-238) en ``oip.evaluacion._canonico`` y ``oip.evaluacion._tipos``."""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
from collections.abc import Mapping
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

import pytest

from oip.catalogos import Canal
from oip.evaluacion._canonico import ErrorSerializacion, a_json, desde_json
from oip.evaluacion._tipos import verificar_tipo


@dataclasses.dataclass(frozen=True)
class _Muestra:
    modo: Literal["a", "b"]
    canal: Canal | None
    tabla: Mapping[Canal, Decimal]
    libre: Any
    fecha: dt.date
    id: UUID | int


def _muestra(**cambios) -> _Muestra:
    base = {
        "modo": "a",
        "canal": Canal.AMAZON,
        "tabla": {Canal.LOCAL: Decimal("1.10")},
        "libre": {"x": [Decimal("2.50"), 1, None, False, "t"]},
        "fecha": dt.date(2026, 11, 18),
        "id": UUID(int=5),
    }
    base.update(cambios)
    return _Muestra(**base)


def test_ida_y_vuelta_de_literal_mapa_any_y_union():
    for muestra in (_muestra(), _muestra(modo="b", canal=None, id=7, libre=None)):
        texto = a_json(muestra, _Muestra)
        leido = desde_json(texto, _Muestra)
        assert leido == muestra
        assert a_json(leido, _Muestra) == texto
    assert '"tabla":{"local":"1.10"}' in a_json(_muestra(), _Muestra)
    assert '{"$decimal":"2.50"}' in a_json(_muestra(), _Muestra)


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("modo", "c"),
        ("modo", 1),
        ("canal", "amazon_mx"),
        ("tabla", []),
        ("tabla", {"local": 1}),
        ("tabla", {"otro": "1.10"}),
        ("libre", {"$decimal": 2}),
        ("libre", {"$decimal": "2.5e0"}),
        ("fecha", "2026-11-18Z"),
        ("fecha", 20261118),
        ("id", "no-es-uuid"),
        ("id", True),
    ],
)
def test_lectura_estricta_de_cada_tipo(campo, valor):
    datos = json.loads(a_json(_muestra(), _Muestra))
    datos[campo] = valor
    with pytest.raises(ErrorSerializacion):
        desde_json(json.dumps(datos), _Muestra)


def test_lectura_rechaza_null_donde_no_hay_none_y_lo_que_no_es_objeto():
    datos = json.loads(a_json(_muestra(), _Muestra))
    datos["fecha"] = None
    with pytest.raises(ErrorSerializacion):
        desde_json(json.dumps(datos), _Muestra)
    with pytest.raises(ErrorSerializacion):
        desde_json("[]", _Muestra)
    with pytest.raises(ErrorSerializacion):
        desde_json('{"a": NaN}', _Muestra)
    with pytest.raises(ErrorSerializacion):
        desde_json('"texto"', tuple[int, ...])
    with pytest.raises(TypeError):
        desde_json(123, _Muestra)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "libre",
    [
        1.5,
        {"x": 1.5},
        {1: "clave no texto"},
        {"$decimal": "1"},  # clave reservada
        Decimal("Infinity"),
        dt.date(2026, 1, 1),
        object(),
    ],
)
def test_any_solo_admite_valores_de_json_y_decimal(libre):
    with pytest.raises(TypeError):
        a_json(_muestra(libre=libre), _Muestra)


@pytest.mark.parametrize(
    ("valor", "tipo"),
    [
        ([1], tuple[int, ...]),
        ((1, "x"), tuple[int, ...]),
        ({"a": 1}, Mapping[str, str]),
        ([], Mapping[str, str]),
        ("c", Literal["a", "b"]),
        (1, None),
        (dt.datetime(2026, 1, 1), dt.datetime),  # noqa: DTZ001
        (dt.datetime(2026, 1, 1, tzinfo=dt.UTC), dt.date),  # datetime no es date
        (1.0, Canal | None),
    ],
)
def test_verificar_tipo_sin_conversiones(valor, tipo):
    with pytest.raises(TypeError):
        verificar_tipo(valor, tipo, "campo")
    with pytest.raises(TypeError):
        a_json(valor, tipo)


def test_tuplas_de_largo_fijo_no_se_admiten():
    with pytest.raises(TypeError):
        verificar_tipo((1, 2), tuple[int, int], "campo")


def test_tipos_no_admitidos():
    with pytest.raises(TypeError):
        verificar_tipo([1], list[int], "campo")
    with pytest.raises(TypeError):
        a_json(b"x", bytes)
    with pytest.raises(TypeError):
        a_json({"a": 1}, _Muestra)
    with pytest.raises(ErrorSerializacion):
        desde_json('"x"', bytes)


def test_el_error_cita_la_ruta_sin_el_valor():
    datos = json.loads(a_json(_muestra(), _Muestra))
    datos["tabla"] = {"local": "valor-privado"}
    with pytest.raises(ErrorSerializacion) as error:
        desde_json(json.dumps(datos), _Muestra)
    assert "valor-privado" not in str(error.value)
    assert "tabla.local" in str(error.value)
