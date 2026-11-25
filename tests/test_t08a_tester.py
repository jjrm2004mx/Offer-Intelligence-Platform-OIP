"""Pruebas de oip-tester para T08a — validación y persistencia previas al cargador.

Escritas desde las fuentes, **sin ver la implementación** (DEC-252, fase 1), sobre el commit
de interfaz ``01c623b``. Cada prueba cita su regla:

- **DEC-257** (decisiones 2 y 2b del #34; design.md §6 y CTR-04): un monto con más de 2
  decimales se rechaza al leer; rangos de las capturas; motivos ``PRECIO INVÁLIDO`` o
  ``CAMPO OBLIGATORIO FALTANTE (<campo>)`` (DEC-244). El repositorio queda como última
  barrera.
- **DEC-258** (decisión 3): ``local_comparable.price_usd`` en ``numeric`` sin escala con la
  migración ``0004_price_usd_sin_escala``; sin la excepción ``_DERIVADAS``, memoria y
  PostgreSQL guardan el mismo valor.
- **Decisiones 16 y 17**: ``buscar_publicacion`` y las lecturas por id, en memoria y en
  PostgreSQL (la misma batería, design.md §5).
- **Decisión 18**: ``password`` y ``passfile`` en la query de la URL (RNF-8).
- **Decisión 19**: ``NotImplementedError`` al importar en ``_checks`` y ``_columnas``.
- **Decisión 37** (design.md §6): ``pickupLocation`` se descarta en la observación de un
  comercio; el particular lo sigue exigiendo (DEC-227 b).
- **R-20 / DEC-181**: ningún motivo ni mensaje lleva el valor.

Deterministas: el día de la carga y la zona se pasan como dato, sin reloj ni red. Las
pruebas ``integracion`` se saltan sin ``OIP_TEST_DATABASE_URL`` (DEC-233). Los
``NotImplementedError`` "al importar" se provocan en un **subproceso** que agrega una tabla
de prueba a ``tablas.metadata`` antes de importar los módulos, para no tocar la sesión de
pytest.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import os
import subprocess
import sys
import textwrap
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import Numeric, select, text

from config_tienda_prueba import TIENDA_PRUEBA, configuracion_con_tienda_prueba
from oip.catalogos import Identificacion
from oip.entradas._comun import RegistroInvalido, mas_de_2_decimales
from oip.entradas.capturas import leer_captura, motivo_de_rechazo
from oip.entradas.contrato import leer_observacion
from oip.entradas.validacion import validar
from oip.evaluacion.contexto import ObservacionRegistrada
from oip.persistencia import tablas
from oip.persistencia.repositorios import (
    CapturaNueva,
    Carga,
    ErrorDeConexion,
    ObservacionNueva,
    Producto,
    Publicacion,
    ReporteCarga,
    RepositorioMemoria,
    RepositorioPostgres,
    crear_motor,
    url_de_conexion,
)

RAIZ = Path(__file__).resolve().parent.parent
_VARIABLE = "OIP_TEST_DATABASE_URL"

CONFIG = configuracion_con_tienda_prueba()
CONTENIDO = CONFIG.contenido

_FIXTURE = json.loads(
    (RAIZ / "tests" / "fixtures" / "observaciones" / "t08a_tester.json").read_text("utf-8"),
    parse_float=Decimal,
)

# --- Oráculos copiados de las fuentes -------------------------------------------------------

PRECIO_INVALIDO = "PRECIO INVÁLIDO"  # REQ §3.2 paso 1, DEC-257 (3)
CIUDAD_NO_CONFIGURADA = "CIUDAD NO CONFIGURADA"  # REQ §6, DEC-227


def faltante(campo: str) -> str:
    """``CAMPO OBLIGATORIO FALTANTE (<campo>)`` con el nombre del campo en el archivo."""
    return f"CAMPO OBLIGATORIO FALTANTE ({campo})"


#: Zona de ``general.timezone`` (PAR-01) y día de la carga en esa zona (DEC-257, DEC-240).
ZONA = "America/Tijuana"
DIA_DE_CARGA = dt.date(2026, 11, 21)
T0 = dt.datetime(2026, 11, 21, 18, 0, tzinfo=dt.UTC)

_QUITAR = object()


def _con(base: dict[str, Any], **cambios: Any) -> dict[str, Any]:
    """Copia de ``base`` con ``cambios``; ``__`` separa un campo anidado; ``_QUITAR`` lo
    quita."""
    datos = copy.deepcopy(base)
    for clave, valor in cambios.items():
        ruta = clave.split("__")
        destino = datos
        for parte in ruta[:-1]:
            destino = destino.setdefault(parte, {})
        if valor is _QUITAR:
            destino.pop(ruta[-1], None)
        else:
            destino[ruta[-1]] = valor
    return datos


def comercio(**cambios: Any) -> dict[str, Any]:
    return _con(_FIXTURE["comercio"], **cambios)


def ficha(**cambios: Any) -> dict[str, Any]:
    return _con(_FIXTURE["ficha_amazon"], **cambios)


def particular(**cambios: Any) -> dict[str, Any]:
    return _con(_FIXTURE["particular"], **cambios)


def _motivo_obs(datos: dict[str, Any]) -> str | None:
    """Motivo del paso 1 (``validar``) o ``None`` si la observación es válida."""
    v = validar(datos, CONTENIDO)
    if v.rechazada:
        assert v.observacion is None
    return v.motivo_rechazo


def _sin_valor(texto: str, *valores: str) -> None:
    """R-20 / DEC-181: el motivo o mensaje no lleva el valor del registro."""
    for valor in valores:
        assert valor not in texto, f"el mensaje lleva el valor {valor!r}"


# --- Capturas sintéticas válidas (CTR-04) ---------------------------------------------------

CAPTURAS: dict[str, dict[str, Any]] = {
    "local_comparable": {
        "brand": "MarcaTester",
        "model": "MT-08A",
        "condition": "used",
        "askingPrice": "85.00",
        "currency": "USD",
        "city": "tijuana",
        "date": "2026-11-20",
        "sold": False,
    },
    "local_estimate": {"gtin": "0123456789012", "price": "90.50", "date": "2026-11-20"},
    "msrp": {
        "gtin": "0123456789012",
        "value": "149.00",
        "source": "fabricante",
        "date": "2026-11-01",
    },
    "local_demand": {"category": "tools", "level": "medium", "date": "2026-11-20"},
    "store_visit": {
        "storeCode": "tp-t08a",
        "gtin": "0123456789012",
        "result": "found",
        "visitedAt": "2026-11-20T09:30:00",
    },
    "actual_result": {
        "evaluationId": str(UUID(int=55)),
        "channel": "local",
        "units": 2,
        "purchasePrice": "29.00",
        "salePrice": "76.61",
        "actualCosts": "9.50",
        "purchasedOn": "2026-11-16",
        "soldOn": "2026-11-20",
    },
    "client_request": {
        "clientAlias": "cliente-sintetico-t08a",
        "items": ["MT-08A"],
        "quantity": 1,
        "modality": "link_only",
        "date": "2026-11-20",
    },
}


def _captura(tipo: str, dia: dt.date | None = DIA_DE_CARGA, **cambios: Any):
    return leer_captura(tipo, _con(CAPTURAS[tipo], **cambios), zona=ZONA, dia_de_carga=dia)


def _rechazo_al_leer(tipo: str, **cambios: Any) -> RegistroInvalido:
    with pytest.raises(RegistroInvalido) as error:
        _captura(tipo, **cambios)
    return error.value


#: Los cinco precios de las capturas (DEC-257 (2) y (3)): ≤ 0 o > 2 decimales → PRECIO INVÁLIDO.
PRECIOS_DE_CAPTURA = [
    ("local_comparable", "askingPrice"),
    ("local_estimate", "price"),
    ("msrp", "value"),
    ("actual_result", "purchasePrice"),
    ("actual_result", "salePrice"),
]


# =============================================================================================
# DEC-257 — mas_de_2_decimales
# =============================================================================================


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("29.001", True),
        ("0.001", True),
        ("-1.234", True),
        ("1E-3", True),
        ("29.000", False),  # se compara el valor, no los ceros finales (docstring, DEC-257)
        ("29.5", False),
        ("29.50", False),
        ("29", False),
        ("0", False),
        ("-29.01", False),
        ("2.90E+1", False),
    ],
)
def test_mas_de_2_decimales_compara_el_valor_no_los_ceros(valor, esperado):
    assert mas_de_2_decimales(Decimal(valor)) is esperado


# =============================================================================================
# DEC-257 — observación: price.current → PRECIO INVÁLIDO
# =============================================================================================


@pytest.mark.parametrize("precio", ["29.001", "0.001", "0", "0.00", "-29.00", "-0.001"])
def test_price_current_cero_negativo_o_con_mas_de_2_decimales_es_precio_invalido(precio):
    motivo = _motivo_obs(comercio(price__current=precio))
    assert motivo == PRECIO_INVALIDO
    _sin_valor(motivo, precio)


@pytest.mark.parametrize("precio", ["29.000", "29.5", "29.00", "29", "0.01"])
def test_price_current_valido_en_el_borde(precio):
    assert _motivo_obs(comercio(price__current=precio)) is None


def test_price_current_como_decimal_de_json_con_3_decimales_es_precio_invalido():
    # CTR-02: el JSON se lee con parse_float=Decimal; el número llega como Decimal.
    datos = comercio(price__current=Decimal("29.001"))
    assert _motivo_obs(datos) == PRECIO_INVALIDO
    assert _motivo_obs(comercio(price__current=Decimal("29.000"))) is None


# =============================================================================================
# DEC-257 (3) — los demás montos de la observación → CAMPO OBLIGATORIO FALTANTE (<campo>)
# =============================================================================================

_MONTOS_OBSERVACION = [
    (comercio, "price__was", "price.was", "129.001", "129.000"),
    (comercio, "shipping__toMeCost", "shipping.toMeCost", "0.001", "0.000"),
    (comercio, "msrp__value", "msrp.value", "149.001", "149.000"),
    (ficha, "amazonListing__buyBoxPrice", "amazonListing.buyBoxPrice", "105.001", "105.000"),
]


@pytest.mark.parametrize(
    ("base", "ruta", "campo", "malo", "bueno"),
    _MONTOS_OBSERVACION,
    ids=[m[2] for m in _MONTOS_OBSERVACION],
)
def test_otro_monto_de_la_observacion_con_mas_de_2_decimales_es_campo_faltante(
    base, ruta, campo, malo, bueno
):
    motivo = _motivo_obs(base(**{ruta: malo}))
    assert motivo == faltante(campo)
    _sin_valor(motivo, malo)
    # El mismo monto con ceros finales (2 decimales de valor) es válido.
    assert _motivo_obs(base(**{ruta: bueno})) is None


@pytest.mark.parametrize(
    ("base", "ruta", "campo", "malo", "bueno"),
    _MONTOS_OBSERVACION,
    ids=[m[2] for m in _MONTOS_OBSERVACION],
)
def test_otro_monto_con_mas_de_2_decimales_se_rechaza_al_leer_con_el_campo(
    base, ruta, campo, malo, bueno
):
    # "Se rechazan al leer" (design.md §6): leer_observacion levanta, sin el valor.
    with pytest.raises(RegistroInvalido) as error:
        leer_observacion(base(**{ruta: malo}))
    assert error.value.motivo == faltante(campo)
    assert error.value.campo == campo
    _sin_valor(str(error.value), malo)
    _sin_valor(repr(error.value), malo)
    leer_observacion(base(**{ruta: bueno}))


def test_un_monto_opcional_invalido_va_antes_que_el_precio_invalido():
    # design.md §6: los campos (DEC-244, opcional no válido = faltante) se comprueban al leer,
    # antes del paso "precio > 0 con 2 decimales como máximo".
    datos = comercio(price__current="29.001", price__was="129.001")
    assert _motivo_obs(datos) == faltante("price.was")


@pytest.mark.parametrize(
    ("ruta", "valor"),
    [("weightKg", "4.1255"), ("dimsCm", {"l": "30.125", "w": "20.0001"})],
)
def test_lo_que_no_es_monto_conserva_sus_decimales(ruta, valor):
    # DEC-257 nombra una lista cerrada de montos; el peso y las medidas no lo son.
    assert _motivo_obs(comercio(**{ruta: valor})) is None


# =============================================================================================
# DEC-257 — capturas: los cinco precios → PRECIO INVÁLIDO
# =============================================================================================


@pytest.mark.parametrize(("tipo", "campo"), PRECIOS_DE_CAPTURA, ids=lambda x: str(x))
@pytest.mark.parametrize("valor", ["0", "0.00", "-1.00", "29.001", "0.001"])
def test_precio_de_captura_cero_negativo_o_con_mas_de_2_decimales(tipo, campo, valor):
    captura = _captura(tipo, **{campo: valor})
    assert captura.precio_invalido is True
    motivo = motivo_de_rechazo(captura)
    assert motivo == PRECIO_INVALIDO
    _sin_valor(motivo, valor, campo)


@pytest.mark.parametrize(("tipo", "campo"), PRECIOS_DE_CAPTURA, ids=lambda x: str(x))
@pytest.mark.parametrize("valor", ["29.000", "29.5", "29", "0.01"])
def test_precio_de_captura_valido_en_el_borde(tipo, campo, valor):
    captura = _captura(tipo, **{campo: valor})
    assert captura.precio_invalido is False
    assert motivo_de_rechazo(captura) is None


@pytest.mark.parametrize(("tipo", "campo"), PRECIOS_DE_CAPTURA, ids=lambda x: str(x))
def test_precio_de_captura_como_decimal_de_json(tipo, campo):
    assert motivo_de_rechazo(_captura(tipo, **{campo: Decimal("29.001")})) == PRECIO_INVALIDO
    assert motivo_de_rechazo(_captura(tipo, **{campo: Decimal("29.000")})) is None


def test_comparable_en_mxn_con_precio_de_mas_de_2_decimales_es_precio_invalido():
    captura = _captura(
        "local_comparable", currency="MXN", askingPrice="1500.001", exchangeRate="17.3"
    )
    assert motivo_de_rechazo(captura) == PRECIO_INVALIDO


def test_el_tipo_de_cambio_no_es_monto_y_conserva_sus_decimales():
    # S-23: exchangeRate (MXN por USD) se guarda sin escala; no es un monto en USD.
    captura = _captura(
        "local_comparable", currency="MXN", askingPrice="1500.00", exchangeRate="17.3456"
    )
    assert motivo_de_rechazo(captura) is None
    assert captura.price_usd == Decimal("1500.00") / Decimal("17.3456")


@pytest.mark.parametrize("tipo", ["local_demand", "store_visit", "client_request"])
def test_las_capturas_sin_precio_nunca_tienen_precio_invalido(tipo):
    captura = _captura(tipo)
    assert captura.precio_invalido is False
    assert motivo_de_rechazo(captura) is None


@pytest.mark.parametrize("tipo", list(CAPTURAS))
def test_las_capturas_base_son_validas(tipo):
    assert motivo_de_rechazo(_captura(tipo)) is None


# =============================================================================================
# DEC-257 — actual_result: actualCosts ≥ 0, units ≥ 1, soldOn ≥ purchasedOn
# =============================================================================================


@pytest.mark.parametrize("valor", ["-0.01", "-9.50", "9.501", "0.001"])
def test_actual_costs_negativo_o_con_mas_de_2_decimales_es_campo_faltante(valor):
    error = _rechazo_al_leer("actual_result", actualCosts=valor)
    assert error.motivo == faltante("actualCosts")
    _sin_valor(str(error), valor)


@pytest.mark.parametrize("valor", ["0", "0.00", "0.000", "9.5", "9.50"])
def test_actual_costs_cero_o_con_2_decimales_es_valido(valor):
    assert motivo_de_rechazo(_captura("actual_result", actualCosts=valor)) is None


@pytest.mark.parametrize("unidades", [0, -1])
def test_units_menor_que_1_es_campo_faltante(unidades):
    error = _rechazo_al_leer("actual_result", units=unidades)
    assert error.motivo == faltante("units")


def test_units_igual_a_1_es_valido():
    assert _captura("actual_result", units=1).units == 1


def test_sold_on_antes_de_purchased_on_es_campo_faltante():
    error = _rechazo_al_leer("actual_result", purchasedOn="2026-11-16", soldOn="2026-11-15")
    assert error.motivo == faltante("soldOn")
    _sin_valor(str(error), "2026-11-15", "2026-11-16")


def test_sold_on_igual_a_purchased_on_es_valido():
    captura = _captura("actual_result", purchasedOn="2026-11-16", soldOn="2026-11-16")
    assert captura.sold_on == captura.purchased_on == dt.date(2026, 11, 16)


def test_un_rango_invalido_va_antes_que_el_precio_invalido():
    # capturas.leer_captura: el precio inválido no levanta y va después de los campos.
    error = _rechazo_al_leer("actual_result", units=0, purchasePrice="0")
    assert error.motivo == faltante("units")


def test_actual_costs_va_antes_que_las_fechas_en_el_orden_de_ctr04():
    error = _rechazo_al_leer(
        "actual_result", actualCosts="-1.00", purchasedOn="2026-11-16", soldOn="2026-11-15"
    )
    assert error.motivo == faltante("actualCosts")


# =============================================================================================
# DEC-257 — ninguna fecha de captura posterior al día de la carga (en la zona de PAR-01)
# =============================================================================================

_FECHAS = [
    ("local_comparable", "date"),
    ("local_estimate", "date"),
    ("msrp", "date"),
    ("local_demand", "date"),
    ("client_request", "date"),
    ("actual_result", "soldOn"),
]


@pytest.mark.parametrize(("tipo", "campo"), _FECHAS, ids=lambda x: str(x))
def test_fecha_igual_al_dia_de_la_carga_es_valida(tipo, campo):
    assert motivo_de_rechazo(_captura(tipo, **{campo: "2026-11-21"})) is None


@pytest.mark.parametrize(("tipo", "campo"), _FECHAS, ids=lambda x: str(x))
def test_fecha_del_dia_siguiente_a_la_carga_es_campo_faltante(tipo, campo):
    error = _rechazo_al_leer(tipo, **{campo: "2026-11-22"})
    assert error.motivo == faltante(campo)
    _sin_valor(str(error), "2026-11-22")


def test_purchased_on_posterior_a_la_carga_es_campo_faltante():
    error = _rechazo_al_leer("actual_result", purchasedOn="2026-11-22", soldOn="2026-11-22")
    assert error.motivo == faltante("purchasedOn")


def test_purchased_on_igual_al_dia_de_la_carga_es_valido():
    captura = _captura("actual_result", purchasedOn="2026-11-21", soldOn="2026-11-21")
    assert motivo_de_rechazo(captura) is None


@pytest.mark.parametrize(
    "visita",
    [
        "2026-11-21T00:00:00",  # sin desfase: en Tijuana (DEC-240)
        "2026-11-21T23:59:59",
        "2026-11-22T07:59:59+00:00",  # = 2026-11-21 23:59:59 en Tijuana (PST, −08:00)
        "2026-11-21T23:59:59-08:00",
    ],
)
def test_visited_at_del_dia_de_la_carga_en_la_zona_es_valido(visita):
    assert motivo_de_rechazo(_captura("store_visit", visitedAt=visita)) is None


@pytest.mark.parametrize(
    "visita",
    [
        "2026-11-22T00:00:00",  # sin desfase: ya es el día siguiente en Tijuana
        "2026-11-22T08:00:00+00:00",  # = 2026-11-22 00:00 en Tijuana
        "2026-11-22T00:00:00-08:00",
    ],
)
def test_visited_at_del_dia_siguiente_en_la_zona_es_campo_faltante(visita):
    error = _rechazo_al_leer("store_visit", visitedAt=visita)
    assert error.motivo == faltante("visitedAt")


def test_sin_dia_de_carga_no_se_comprueba_la_fecha():
    # leer_captura: "sin él, no se comprueba" (lo pasa el cargador, nunca el reloj).
    assert motivo_de_rechazo(_captura("local_estimate", dia=None, date="2030-01-01")) is None


def test_el_motivo_de_una_solicitud_rechazada_no_lleva_el_alias():
    # RNF-11 / R-20: el alias del cliente nunca va en un mensaje.
    alias = CAPTURAS["client_request"]["clientAlias"]
    error = _rechazo_al_leer("client_request", date="2026-11-22")
    _sin_valor(str(error), alias)
    _sin_valor(repr(error), alias)


# =============================================================================================
# Decisión 37 — pickupLocation se descarta en la observación de un comercio
# =============================================================================================


@pytest.mark.parametrize("ciudad", ["ciudad_que_no_existe", "san_diego", "  ", 123, {"x": 1}])
def test_comercio_con_pickup_location_se_acepta_sin_guardarlo(ciudad):
    v = validar(comercio(pickupLocation=ciudad), CONTENIDO)
    assert not v.rechazada, v.motivo_rechazo
    assert v.observacion.pickup_location is None


def test_comercio_con_ciudad_que_no_existe_al_leer_no_trae_pickup_location():
    observacion = leer_observacion(comercio(pickupLocation="ciudad_que_no_existe"))
    assert observacion.pickup_location is None
    assert "pickup_location" not in observacion.model_dump(exclude_none=True)


@pytest.mark.scenario("B20 (f)")
def test_el_particular_sigue_exigiendo_pickup_location():
    assert _motivo_obs(particular(pickupLocation=_QUITAR)) == faltante("pickupLocation")


@pytest.mark.scenario("B20 (g)")
def test_el_particular_con_ciudad_fuera_de_la_lista_sigue_rechazado():
    assert _motivo_obs(particular(pickupLocation="ensenada")) == CIUDAD_NO_CONFIGURADA


def test_el_particular_conserva_su_ciudad():
    v = validar(particular(), CONTENIDO)
    assert not v.rechazada, v.motivo_rechazo
    assert v.observacion.pickup_location == "san_diego"


# =============================================================================================
# Decisión 18 — password y passfile en la query de la URL
# =============================================================================================

_CLAVE_FALSA = "no-es-un-secreto-t08a"  # texto de prueba, no es una credencial


@pytest.mark.parametrize(
    "query",
    [
        f"password={_CLAVE_FALSA}",
        f"PASSWORD={_CLAVE_FALSA}",
        f"Password={_CLAVE_FALSA}",
        f"passfile=/tmp/{_CLAVE_FALSA}",
        f"PassFile=/tmp/{_CLAVE_FALSA}",
        f"sslmode=require&password={_CLAVE_FALSA}",
    ],
)
def test_url_con_password_o_passfile_en_la_query_se_rechaza_sin_la_url(query):
    url = f"postgresql://usuario-t08a@host-t08a/base_t08a?{query}"
    with pytest.raises(ErrorDeConexion) as error:
        url_de_conexion({"OIP_DATABASE_URL": url}, archivo_secreto=None)
    mensaje = f"{error.value} {error.value!r}"
    _sin_valor(mensaje, _CLAVE_FALSA, "host-t08a", "usuario-t08a", "base_t08a", url)


@pytest.mark.parametrize("query", ["sslmode=require", "application_name=password"])
def test_url_con_otra_query_se_acepta(query):
    url = url_de_conexion(
        {"OIP_DATABASE_URL": f"postgresql://usuario@host/base?{query}"}, archivo_secreto=None
    )
    assert url.password is None


def test_las_claves_prohibidas_son_password_y_passfile():
    from oip.persistencia.repositorios.conexion import CLAVES_PROHIBIDAS_EN_QUERY

    assert {c.lower() for c in CLAVES_PROHIBIDAS_EN_QUERY} == {"password", "passfile"}


# =============================================================================================
# Decisiones 16 y 17 — utilidades de _columnas
# =============================================================================================


def test_tienda_de_busqueda():
    from oip.persistencia.repositorios._columnas import tienda_de_busqueda

    assert tienda_de_busqueda(None) is None
    assert tienda_de_busqueda("tp-t08a") == "tp-t08a"
    for vacia in ("", " ", "   ", "\t"):
        with pytest.raises(ValueError):
            tienda_de_busqueda(vacia)
    for otro in (5, b"tp", ["tp"]):
        with pytest.raises(TypeError):
            tienda_de_busqueda(otro)


@pytest.mark.parametrize(
    ("valor", "tipo"),
    [(True, int), (False, int), ("1", int), (Decimal(1), int), (None, int),
     (str(UUID(int=1)), UUID), (1, UUID), (None, UUID),
     (1, str), (b"clave", str), (None, str)],
)  # fmt: skip
def test_exigir_tipo_rechaza_otro_tipo_sin_el_valor(valor, tipo):
    from oip.persistencia.repositorios._columnas import exigir_tipo

    with pytest.raises(TypeError) as error:
        exigir_tipo(valor, tipo, "id_t08a")
    assert "id_t08a" in str(error.value)
    if isinstance(valor, str):
        _sin_valor(str(error.value), valor)


@pytest.mark.parametrize(("valor", "tipo"), [(1, int), (UUID(int=1), UUID), ("clave", str)])
def test_exigir_tipo_acepta_el_tipo_exacto(valor, tipo):
    from oip.persistencia.repositorios._columnas import exigir_tipo

    assert exigir_tipo(valor, tipo, "id_t08a") is None


# =============================================================================================
# Batería de contrato: memoria y PostgreSQL (design.md §5)
# =============================================================================================


def _url():
    from sqlalchemy.engine import make_url

    valor = os.environ.get(_VARIABLE, "").strip()
    if not valor:
        pytest.skip(f"sin {_VARIABLE}: las pruebas de integración se saltan (DEC-233)")
    url = make_url(valor)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    return url


def _limpiar(motor) -> None:
    nombres = ", ".join([*tablas.metadata.tables, "alembic_version"])
    with motor.begin() as conexion:
        conexion.execute(text("DROP VIEW IF EXISTS open_opportunity"))
        conexion.execute(text(f"DROP TABLE IF EXISTS {nombres} CASCADE"))


def _alembic(motor, accion, revision: str) -> None:
    from alembic.config import Config

    with motor.begin() as conexion:
        config = Config(str(RAIZ / "alembic.ini"))
        config.attributes["connection"] = conexion
        accion(config, revision)


def _con_timescale(motor) -> None:
    with motor.connect() as conexion:
        hay = conexion.execute(
            text("SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb'")
        ).first()
    if hay is None:
        pytest.fail("la base de OIP_TEST_DATABASE_URL no tiene la extensión timescaledb")


@pytest.fixture(params=["memoria", pytest.param("postgres", marks=pytest.mark.integracion)])
def repo(request):
    if request.param == "memoria":
        yield RepositorioMemoria()
        return
    from alembic import command

    motor = crear_motor(_url())
    _limpiar(motor)
    try:
        _con_timescale(motor)
        _alembic(motor, command.upgrade, "head")
        repositorio = RepositorioPostgres(motor)
        repositorio._motor_t08a = motor  # para leer la fila cruda
        yield repositorio
    finally:
        _limpiar(motor)
        motor.dispose()


ID_PRODUCTO = UUID(int=8100)
ID_CARGA = UUID(int=8900)
URL_PUB = "https://tienda.example.com/p/tester-t08a/1"


def _h(n: int) -> str:
    return f"{n:064x}"


def _guardar_publicacion(repo, n: int, tienda: str | None, *, primera: bool) -> Publicacion:
    cambios: dict[str, Any] = {"storeCode": tienda if tienda is not None else _QUITAR}
    observacion = leer_observacion(comercio(**cambios))
    publicacion = Publicacion(UUID(int=8200 + n), ID_PRODUCTO, TIENDA_PRUEBA, URL_PUB, T0, tienda)
    nueva = ObservacionNueva(
        registrada=ObservacionRegistrada(
            observacion, UUID(int=8300 + n), publicacion.id, ID_PRODUCTO
        ),
        identificacion=Identificacion.CONFIRMED,
        clave_idempotencia=f"{TIENDA_PRUEBA}|t08a-{n}",
        origen="worker",
        recibida_en=T0,
        producto=Producto(ID_PRODUCTO, T0) if primera else None,
        publicacion=publicacion,
    )
    assert repo.guardar_observacion(nueva)
    return publicacion


def test_buscar_publicacion_sin_tienda_con_none_y_vacia_rechazada(repo):
    con_tienda = _guardar_publicacion(repo, 1, "tp-t08a", primera=True)
    sin_tienda = _guardar_publicacion(repo, 2, None, primera=False)
    assert repo.buscar_publicacion(TIENDA_PRUEBA, URL_PUB, "tp-t08a") == con_tienda
    assert repo.buscar_publicacion(TIENDA_PRUEBA, URL_PUB, None) == sin_tienda
    # Decisión 16: una tienda vacía o solo espacios es un error, en las dos implementaciones.
    for vacia in ("", " ", "   ", "\t"):
        with pytest.raises(ValueError):
            repo.buscar_publicacion(TIENDA_PRUEBA, URL_PUB, vacia)


def _reporte() -> ReporteCarga:
    return ReporteCarga(T0, 0, 0, 0, {})


_ID_TEXTO = "id-en-texto-t08a"

_LECTURAS_POR_ID = [
    ("version_configuracion", [True, False, "1", Decimal(1), None, _ID_TEXTO]),
    ("leer_producto", [str(UUID(int=1)), 1, None, _ID_TEXTO]),
    ("leer_observacion", [str(UUID(int=1)), 1, None, _ID_TEXTO]),
    ("leer_carga", [str(UUID(int=1)), 1, None, _ID_TEXTO]),
    ("leer_evaluacion", [str(UUID(int=1)), 1, None, _ID_TEXTO]),
    ("observacion_por_clave", [1, b"clave", None, UUID(int=1)]),
]


@pytest.mark.parametrize(
    ("metodo", "valor"),
    [(m, v) for m, vs in _LECTURAS_POR_ID for v in vs],
    ids=lambda x: repr(x)[:40],
)
def test_lectura_por_id_con_otro_tipo_da_type_error_sin_el_valor(repo, metodo, valor):
    with pytest.raises(TypeError) as error:
        getattr(repo, metodo)(valor)
    if isinstance(valor, str):
        _sin_valor(str(error.value), valor)


@pytest.mark.parametrize("valor", [str(UUID(int=1)), 1, None, _ID_TEXTO])
def test_terminar_carga_con_otro_tipo_de_id_da_type_error(repo, valor):
    with pytest.raises(TypeError) as error:
        repo.terminar_carga(valor, _reporte())
    if isinstance(valor, str):
        _sin_valor(str(error.value), valor)


@pytest.mark.parametrize(
    ("metodo", "valor"),
    [
        ("version_configuracion", 987654),
        ("leer_producto", UUID(int=987654)),
        ("leer_observacion", UUID(int=987654)),
        ("leer_carga", UUID(int=987654)),
        ("leer_evaluacion", UUID(int=987654)),
        ("observacion_por_clave", "clave-que-no-existe"),
    ],
)
def test_lectura_por_id_con_el_tipo_exacto_y_sin_dato_da_none(repo, metodo, valor):
    assert getattr(repo, metodo)(valor) is None


# --- DEC-258: price_usd igual en memoria y en PostgreSQL ------------------------------------


def _price_usd_crudo(repo, id_: UUID) -> Decimal:
    t = tablas.local_comparable
    if isinstance(repo, RepositorioMemoria):
        (fila,) = [f for f in repo._tablas[t.name].filas if f["id"] == id_]
        return fila["price_usd"]
    with repo._motor_t08a.connect() as c:
        return c.execute(select(t.c.price_usd).where(t.c.id == id_)).scalar_one()


def _preparar_carga(repo) -> None:
    version, _ = repo.guardar_version_configuracion(CONFIG, cargada_en=T0 - dt.timedelta(days=1))
    repo.iniciar_carga(Carga(ID_CARGA, "capturas.jsonl", _h(1), "jsonl", T0, version.id))
    repo.guardar_producto(Producto(ID_PRODUCTO, T0))


@pytest.mark.parametrize(
    ("precio", "cambio"),
    [("1500.00", "17.3"), ("100.00", "17"), ("999.99", "18.123456")],
)
def test_price_usd_se_guarda_sin_redondear_igual_en_memoria_y_postgres(repo, precio, cambio):
    _preparar_carga(repo)
    captura = _captura("local_comparable", currency="MXN", askingPrice=precio, exchangeRate=cambio)
    esperado = Decimal(precio) / Decimal(cambio)  # S-23: sin redondear
    assert captura.price_usd == esperado
    id_ = UUID(int=8401)
    repo.guardar_captura(CapturaNueva(id_, captura, _h(2), ID_CARGA, T0, ID_PRODUCTO))
    guardado = _price_usd_crudo(repo, id_)
    assert guardado == esperado
    # Más de 4 decimales: numeric(14,4) lo habría redondeado (T05-1).
    assert guardado.as_tuple().exponent < -4


def test_el_repositorio_sigue_siendo_la_ultima_barrera_de_los_decimales(repo):
    # DEC-257 (1): el esquema ya marca el precio; si llegara al repositorio, no lo redondea.
    _preparar_carga(repo)
    captura = _captura("local_comparable", askingPrice="29.001")
    assert motivo_de_rechazo(captura) == PRECIO_INVALIDO
    with pytest.raises((ValueError, TypeError)):
        repo.guardar_captura(
            CapturaNueva(UUID(int=8402), captura, _h(3), ID_CARGA, T0, ID_PRODUCTO)
        )


# --- DEC-258: el modelo y la migración 0004 -------------------------------------------------

_0004 = "0004_price_usd_sin_escala"
_0003 = "0003_registro_de_rechazo"


def test_el_modelo_tiene_price_usd_sin_escala():
    tipo = tablas.local_comparable.c.price_usd.type
    assert isinstance(tipo, Numeric)
    assert tipo.precision is None and tipo.scale is None
    assert tablas.CAMBIOS_0004 == {"local_comparable": ("price_usd",)}


def test_ya_no_hay_columnas_derivadas_exentas():
    from oip.persistencia.repositorios import _columnas

    assert not getattr(_columnas, "_DERIVADAS", frozenset())


def test_la_0004_va_despues_de_la_0003_y_es_la_cabeza():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    guion = ScriptDirectory.from_config(Config(str(RAIZ / "alembic.ini")))
    revision = guion.get_revision(_0004)
    assert revision is not None
    assert revision.down_revision == _0003
    assert guion.get_heads() == [_0004]


def _escala_price_usd(motor) -> tuple[Any, Any, str]:
    with motor.connect() as c:
        fila = c.execute(
            text(
                "SELECT numeric_precision, numeric_scale, data_type FROM information_schema.columns"
                " WHERE table_schema = current_schema() AND table_name = 'local_comparable'"
                " AND column_name = 'price_usd'"
            )
        ).one()
    return fila[0], fila[1], fila[2]


@pytest.fixture
def motor_vacio():
    from sqlalchemy import create_engine

    motor = create_engine(_url())
    _limpiar(motor)
    try:
        _con_timescale(motor)
        yield motor
    finally:
        _limpiar(motor)
        motor.dispose()


@pytest.mark.integracion
def test_la_0004_sube_y_baja(motor_vacio):
    from alembic import command
    from alembic.migration import MigrationContext

    def revision() -> str | None:
        with motor_vacio.connect() as c:
            return MigrationContext.configure(c).get_current_revision()

    _alembic(motor_vacio, command.upgrade, _0003)
    assert _escala_price_usd(motor_vacio) == (14, 4, "numeric")

    _alembic(motor_vacio, command.upgrade, _0004)
    assert revision() == _0004
    assert _escala_price_usd(motor_vacio) == (None, None, "numeric")

    _alembic(motor_vacio, command.downgrade, _0003)
    assert revision() == _0003
    assert _escala_price_usd(motor_vacio) == (14, 4, "numeric")

    _alembic(motor_vacio, command.upgrade, "head")
    assert revision() == _0004
    assert _escala_price_usd(motor_vacio) == (None, None, "numeric")


# =============================================================================================
# Decisión 19 — NotImplementedError al importar (_checks y _columnas)
# =============================================================================================

_GUION = textwrap.dedent(
    """
    import sys
    import sqlalchemy as sa
    from sqlalchemy.dialects.postgresql import ARRAY
    from oip.persistencia import tablas

    modo, expresion = sys.argv[1], sys.argv[2]
    columnas = [
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("code", sa.Text),
        sa.Column("n", sa.Integer),
        sa.Column("tags", ARRAY(sa.Text)),
    ]
    if modo == "check":
        columnas.append(sa.CheckConstraint(expresion, name="t08a_prueba"))
    else:
        columnas.append(sa.Column("s", sa.SmallInteger))
    tabla = sa.Table("t08a_prueba", tablas.metadata, *columnas)
    try:
        from oip.persistencia.repositorios import _checks, _columnas
    except NotImplementedError:
        print("NIE")
        sys.exit(0)
    if modo == "check":
        print("IMPORTA" if "t08a_prueba" in _checks.CHECKS else "SIN_TABLA")
        sys.exit(0)
    salida = []
    for valor in (32767, -32768, 32768, -32769):
        try:
            _columnas.normalizar(tabla, {"id": 1, "s": valor})
            salida.append("ok")
        except NotImplementedError:
            salida.append("NIE")
        except ValueError:
            salida.append("ValueError")
    print(",".join(salida))
    """
)


def _importar_con(modo: str, expresion: str = "") -> str:
    entorno = dict(os.environ)
    entorno["PYTHONPATH"] = os.pathsep.join(
        [str(RAIZ / "src"), *filter(None, [entorno.get("PYTHONPATH")])]
    )
    resultado = subprocess.run(  # noqa: S603 — el propio intérprete, sin red ni shell
        [sys.executable, "-c", _GUION, modo, expresion],
        capture_output=True,
        text=True,
        env=entorno,
        cwd=RAIZ,
        timeout=120,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stderr[-2000:]
    return resultado.stdout.strip()


@pytest.mark.parametrize(
    "expresion",
    [
        "code IN ('a', 'b')",
        "tags <@ ARRAY['a', 'b']::text[]",
        "n >= 1 AND btrim(code) <> ''",
        "code ~ '^[0-9a-f]{64}$'",
        "code ~ '^CAMPO \\(x\\)$'",  # escape no alfabético, como el del esquema
    ],
)
def test_control_un_check_admitido_importa(expresion):
    assert _importar_con("check", expresion) == "IMPORTA"


@pytest.mark.parametrize(
    "expresion",
    [
        "n::integer > 0",
        "code::text = 'a'",
        "code::varchar = 'a'",
        "tags <@ ARRAY['a']::integer[]",
        "ARRAY[code]::varchar[] <@ ARRAY['a']::text[]",
    ],
)
def test_un_cast_distinto_de_text_array_falla_al_importar(expresion):
    assert _importar_con("check", expresion) == "NIE"


@pytest.mark.parametrize(
    "expresion",
    [
        "columna_que_no_existe = 'a'",
        "code = otra_columna",
        "n IS NOT NULL AND inexistente > 0",
        "btrim(no_existe) <> ''",
        "code = TRUE",
        "code = FALSE",
        "code = true",
    ],
)
def test_un_identificador_que_no_es_columna_falla_al_importar(expresion):
    assert _importar_con("check", expresion) == "NIE"


_PATRONES_NO_ADMITIDOS = [
    "^[[:alpha:]]$",
    "[[.a.]]",
    "[[=a=]]",
    "(?i)abc",
    "(?:ab)c",
    "***:abc",
    "***=abc",
    "^\\d+$",
    "\\w",
    "\\s",
    "\\yabc\\y",
    "\\mabc\\M",
    "\\b",
    "\\Aabc",
    "abc\\Z",
    "\\n",
    "\\x41",
]


@pytest.mark.parametrize("patron", _PATRONES_NO_ADMITIDOS)
def test_un_patron_no_admitido_falla_al_importar(patron):
    assert _importar_con("check", f"code ~ '{patron}'") == "NIE"


@pytest.mark.parametrize("patron", _PATRONES_NO_ADMITIDOS)
def test_patron_are_rechaza_las_formas_no_admitidas(patron):
    from oip.persistencia.repositorios import _checks

    with pytest.raises(NotImplementedError):
        _checks._patron_are(patron)


@pytest.mark.parametrize(
    "patron", ["^[0-9a-f]{64}$", "^CAMPO \\(x\\)$", "^[A-Za-z][A-Za-z0-9_.]*$"]
)
def test_patron_are_admite_los_del_esquema(patron):
    from oip.persistencia.repositorios import _checks

    assert isinstance(_checks._patron_are(patron), str)


def test_smallint_de_16_bits_o_not_implemented_error():
    salida = _importar_con("smallint")
    assert salida in {"NIE", "NIE,NIE,NIE,NIE", "ok,ok,ValueError,ValueError"}, salida


def test_el_esquema_vigente_importa_sin_errores():
    # Control: las restricciones reales están todas en el subconjunto admitido.
    from oip.persistencia.repositorios import _checks

    assert set(_checks.CHECKS) == set(tablas.metadata.tables)


# =============================================================================================
# Fase 2 — números no finitos (DEC-257 con DEC-244): un motivo, nunca una excepción suelta
# =============================================================================================


@pytest.mark.parametrize("valor", ["NaN", "sNaN", "Infinity", "-Infinity"])
def test_un_monto_no_finito_da_su_motivo_y_no_una_excepcion(valor):
    assert _motivo_obs(comercio(price__current=valor)) == PRECIO_INVALIDO
    assert _motivo_obs(comercio(price__was=valor)) == faltante("price.was")
    assert motivo_de_rechazo(_captura("local_comparable", askingPrice=valor)) == PRECIO_INVALIDO
    assert _rechazo_al_leer("actual_result", actualCosts=valor).motivo == faltante("actualCosts")
