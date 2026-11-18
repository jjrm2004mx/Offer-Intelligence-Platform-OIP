"""Pruebas de oip-tester para T01 de req-2026-0001-b-evaluacion (cimientos, sin escenarios).

Cubren lo que las pruebas del developer no cubren de los comportamientos de tasks.md §1 y de
su guía de implementación:

- un ``float`` levanta ``TypeError`` en cada ``TipoMonto`` (design.md §8), también un
  ``float`` no finito;
- los catálogos guardan el código exacto del REQ: en Unicode NFC (acentos precompuestos, como
  en el cuerpo del #2) y sin espacios de más (design.md §9);
- ninguna dependencia del paquete, directa o transitiva, es un cliente HTTP (RNF-6, DEC-173).

Sin marcador de escenario: T01 no tiene escenarios propios (tasks.md §1).
"""

import re
import tomllib
import unicodedata
from enum import StrEnum
from importlib import metadata
from pathlib import Path

import pytest

from oip import catalogos
from oip.dinero import TipoMonto, redondear

RAIZ_REPO = Path(__file__).resolve().parents[1]

# --- Sin float en cada TipoMonto (design.md §8) ---------------------------------------


@pytest.mark.parametrize("valor", [2.2475, -9.125, 0.0, float("nan"), float("inf")])
@pytest.mark.parametrize("tipo", list(TipoMonto))
def test_redondear_rechaza_float_en_cada_tipo(tipo, valor):
    with pytest.raises(TypeError):
        redondear(tipo, valor)


# --- Códigos exactos (design.md §9) ---------------------------------------------------

ENUMS_DE_CATALOGOS = [
    obj
    for obj in vars(catalogos).values()
    if isinstance(obj, type) and issubclass(obj, StrEnum) and obj is not StrEnum
]


def test_hay_catalogos_que_revisar():
    assert len(ENUMS_DE_CATALOGOS) >= 18


@pytest.mark.parametrize("enum", ENUMS_DE_CATALOGOS, ids=lambda e: e.__name__)
def test_codigos_en_nfc_y_sin_espacios_de_mas(enum):
    for miembro in enum:
        codigo = miembro.value
        assert unicodedata.is_normalized("NFC", codigo), codigo
        assert codigo == codigo.strip(), codigo
        assert "  " not in codigo, codigo
        assert re.fullmatch(r"[\w ().]+", codigo), codigo


@pytest.mark.parametrize(
    "codigo",
    [
        "PRECIO INVÁLIDO",
        "COMPETENCIA MÁS BARATA",
        "COMISIÓN DESCONOCIDA",
        "TASA DE DEVOLUCIÓN DESCONOCIDA",
        "ENVÍO POR COTIZAR",
        "SIN ROTACIÓN",
    ],
)
def test_codigos_con_acento_iguales_byte_a_byte_al_req(codigo):
    # Los literales de esta prueba se copiaron del cuerpo del #2 (NFC, UTF-8).
    todos = {m.value for enum in ENUMS_DE_CATALOGOS for m in enum}
    assert unicodedata.normalize("NFC", codigo) in todos
    assert codigo.encode("utf-8") in {v.encode("utf-8") for v in todos}


# --- Ninguna dependencia es un cliente HTTP (RNF-6, DEC-173) --------------------------

CLIENTES_HTTP = {
    "requests",
    "httpx",
    "urllib3",
    "aiohttp",
    "httplib2",
    "pycurl",
    "treq",
    "grequests",
    "niquests",
    "requests-html",
    "scrapy",
    "playwright",
    "selenium",
    "pyppeteer",
    "undetected-chromedriver",
    "mechanize",
    "curl-cffi",
}


def _nombre(requisito: str) -> str:
    return re.split(r"[\s\[<>=!~;]", requisito.strip(), maxsplit=1)[0].lower().replace("_", "-")


def _dependencias_declaradas() -> list[str]:
    datos = tomllib.loads((RAIZ_REPO / "pyproject.toml").read_text(encoding="utf-8"))
    return [_nombre(r) for r in datos["project"]["dependencies"]]


def test_dependencias_declaradas_son_las_de_design_5():
    assert sorted(_dependencias_declaradas()) == sorted(
        ["pydantic", "pyyaml", "sqlalchemy", "psycopg", "alembic", "tzdata"]
    )


def test_ninguna_dependencia_directa_es_cliente_http():
    assert set(_dependencias_declaradas()) & CLIENTES_HTTP == set()


def test_ninguna_dependencia_transitiva_instalada_es_cliente_http():
    # Cierre de las dependencias obligatorias (sin extras) tal como quedaron instaladas.
    pendientes, vistas = list(_dependencias_declaradas()), set()
    while pendientes:
        nombre = pendientes.pop()
        if nombre in vistas:
            continue
        vistas.add(nombre)
        try:
            requisitos = metadata.requires(nombre) or []
        except metadata.PackageNotFoundError:
            continue
        pendientes.extend(_nombre(r) for r in requisitos if "extra ==" not in r)
    assert vistas & CLIENTES_HTTP == set()
