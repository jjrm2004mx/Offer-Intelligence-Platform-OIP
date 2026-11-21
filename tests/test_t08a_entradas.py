"""T08a: decimales, rangos de las capturas y ``pickupLocation`` de un comercio (DEC-257).

Una prueba por regla (tasks.md T08a, comportamientos esperados):

- cada monto de la observación con más de 2 decimales: ``price.current`` → ``PRECIO
  INVÁLIDO``; ``price.was``, ``shipping.toMeCost``, ``msrp.value`` y
  ``amazonListing.buyBoxPrice`` → ``CAMPO OBLIGATORIO FALTANTE (<campo>)`` (DEC-257, DEC-244);
- cada rango de CTR-04 con su motivo: los cinco precios de las capturas ≤ 0 o con más de 2
  decimales → ``PRECIO INVÁLIDO``; ``actualCosts`` < 0 o con más de 2 decimales, ``units``
  < 1, ``soldOn`` < ``purchasedOn`` y cada fecha posterior al día de la carga →
  ``CAMPO OBLIGATORIO FALTANTE (<campo>)``;
- un comercio con una ciudad que no existe se acepta sin ``pickup_location`` (decisión 37).

El día de la carga llega como dato (``dia_de_carga``), nunca del reloj. Los motivos llevan
solo el código y el campo, nunca el valor (R-20). Fixtures sintéticos: el comercio
``tienda-prueba`` con dominio example.com; ninguna URL se abre.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from config_tienda_prueba import TIENDA_PRUEBA, configuracion_con_tienda_prueba
from oip.entradas._comun import RegistroInvalido, mas_de_2_decimales
from oip.entradas.capturas import leer_captura, motivo_de_rechazo
from oip.entradas.contrato import leer_observacion
from oip.entradas.validacion import validar

CONFIG = configuracion_con_tienda_prueba().contenido
PRECIO_INVALIDO = "PRECIO INVÁLIDO"
ZONA = "America/Tijuana"
DIA = dt.date(2026, 11, 21)
FIXTURES = Path(__file__).parent / "fixtures"


def _faltante(campo: str) -> str:
    return f"CAMPO OBLIGATORIO FALTANTE ({campo})"


COMERCIO: dict[str, Any] = {
    "schemaVersion": "3.1",
    "retailerCode": TIENDA_PRUEBA,
    "storeCode": "tp-01",
    "productUrl": "https://tienda.example.com/p/100",
    "title": "Taladro sintético",
    "brand": "MarcaP",
    "model": "MP-1",
    "category": "tools",
    "price": {"current": "29.00", "was": "129.00", "currency": "USD"},
    "seller": "comercio",
    "condition": "new",
    "availability": {"state": "in_stock", "quantity": 3, "scope": "store"},
    "purchaseMode": "tienda",
    "shipping": {"toMeCost": "0.00"},
    "msrp": {"value": "149.00", "source": "fabricante"},
    "extractedAt": "2026-11-16T10:00:00-08:00",
    "blocked": False,
}


def _con(base: dict[str, Any], ruta: str, valor: Any) -> dict[str, Any]:
    datos = copy.deepcopy(base)
    actual = datos
    *padres, hoja = ruta.split(".")
    for parte in padres:
        actual = actual.setdefault(parte, {})
    if valor is None:
        actual.pop(hoja, None)
    else:
        actual[hoja] = valor
    return datos


def _motivo_observacion(datos: dict[str, Any]) -> str | None:
    return validar(datos, CONFIG).motivo_rechazo


# --- mas_de_2_decimales ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("29", False),
        ("29.5", False),
        ("29.50", False),
        ("29.000", False),  # se compara el valor, no los ceros finales
        ("0.01", False),
        ("-1.25", False),
        ("29.001", True),
        ("0.005", True),
        ("-1.255", True),
        ("1E-3", True),
    ],
)
def test_mas_de_2_decimales_compara_el_valor(valor, esperado):
    assert mas_de_2_decimales(Decimal(valor)) is esperado


@pytest.mark.parametrize("valor", [29.5, 29, "29.5", Decimal("NaN"), Decimal("Infinity")])
def test_mas_de_2_decimales_solo_acepta_decimal_finito(valor):
    with pytest.raises(TypeError):
        mas_de_2_decimales(valor)


# --- Montos de la observación (DEC-257) ----------------------------------------------------


def test_la_observacion_base_es_valida():
    assert _motivo_observacion(COMERCIO) is None


@pytest.mark.parametrize("precio", ["29.001", "0.005", "1E-3"])
def test_price_current_con_mas_de_2_decimales_es_precio_invalido(precio):
    assert _motivo_observacion(_con(COMERCIO, "price.current", precio)) == PRECIO_INVALIDO


@pytest.mark.parametrize("precio", ["29.000", "29.5"])
def test_price_current_con_ceros_finales_no_es_precio_invalido(precio):
    assert _motivo_observacion(_con(COMERCIO, "price.current", precio)) is None


@pytest.mark.parametrize(
    ("ruta", "base"),
    [
        ("price.was", COMERCIO),
        ("shipping.toMeCost", COMERCIO),
        ("msrp.value", COMERCIO),
        (
            "amazonListing.buyBoxPrice",
            {**COMERCIO, "amazonListing": {"buyBoxPrice": "105.00", "sellersNew": 4}},
        ),
    ],
)
@pytest.mark.parametrize("valor", ["129.001", "0.005"])
def test_otro_monto_de_la_observacion_con_mas_de_2_decimales_es_campo_faltante(ruta, base, valor):
    datos = _con(base, ruta, valor)
    with pytest.raises(RegistroInvalido) as error:
        leer_observacion(datos)
    assert error.value.motivo == _faltante(ruta)
    assert error.value.campo == ruta
    assert valor not in str(error.value)
    assert _motivo_observacion(datos) == _faltante(ruta)


@pytest.mark.parametrize(
    "ruta", ["price.was", "shipping.toMeCost", "msrp.value", "amazonListing.buyBoxPrice"]
)
def test_otro_monto_con_2_decimales_o_ceros_finales_se_acepta(ruta):
    base = {**COMERCIO, "amazonListing": {"buyBoxPrice": "105.00"}}
    for valor in ("12.34", "12.340", "12"):
        observacion = leer_observacion(_con(base, ruta, valor))
        assert observacion is not None


def test_el_monto_con_mas_decimales_va_antes_que_el_precio_invalido():
    """Orden de design.md §6: el campo no válido (obligatorios y forma) antes del precio."""
    datos = _con(_con(COMERCIO, "price.current", "0"), "shipping.toMeCost", "1.005")
    assert _motivo_observacion(datos) == _faltante("shipping.toMeCost")


def test_buy_box_price_nulo_sigue_siendo_sin_oferta_hoy():
    datos = {**COMERCIO, "amazonListing": {"buyBoxPrice": None, "sellersNew": 4}}
    assert leer_observacion(datos).amazon_listing.buy_box_price is None


# --- pickupLocation en la observación de un comercio (decisión 37) --------------------------


@pytest.mark.parametrize("ciudad", ["ciudad_que_no_existe", "san_diego", 123, {"x": 1}, "  "])
def test_un_comercio_con_pickup_location_se_acepta_sin_guardarla(ciudad):
    datos = {**COMERCIO, "pickupLocation": ciudad}
    validacion = validar(datos, CONFIG)
    assert validacion.motivo_rechazo is None
    assert validacion.observacion.pickup_location is None


def test_en_un_comercio_3_0_pickup_location_tambien_se_descarta():
    datos = {**COMERCIO, "schemaVersion": "3.0", "pickupLocation": "ciudad_que_no_existe"}
    assert validar(datos, CONFIG).observacion.pickup_location is None


def _particular() -> dict[str, Any]:
    texto = (FIXTURES / "observaciones" / "b18_particular.json").read_text(encoding="utf-8")
    datos = json.loads(texto, parse_float=Decimal)
    datos.pop("_nota")
    return datos


def test_el_particular_conserva_y_valida_su_pickup_location():
    assert validar(_particular(), CONFIG).observacion.pickup_location == "san_diego"
    otra = {**_particular(), "pickupLocation": "ciudad_que_no_existe"}
    assert validar(otra, CONFIG).motivo_rechazo == "CIUDAD NO CONFIGURADA"
    sin = {k: v for k, v in _particular().items() if k != "pickupLocation"}
    assert validar(sin, CONFIG).motivo_rechazo == _faltante("pickupLocation")


# --- Capturas: fixtures sintéticos ----------------------------------------------------------

UUID_EVAL = str(UUID(int=7))

CAPTURAS: dict[str, dict[str, Any]] = {
    "local_comparable": {
        "brand": "MarcaP",
        "model": "MP-1",
        "condition": "used",
        "askingPrice": "120.00",
        "currency": "USD",
        "city": "san_diego",
        "date": "2026-11-15",
        "sold": False,
    },
    "local_estimate": {"gtin": "036000291452", "price": "95.00", "date": "2026-11-15"},
    "msrp": {
        "brand": "MarcaP",
        "model": "MP-1",
        "value": "149.00",
        "source": "fabricante",
        "date": "2026-11-10",
    },
    "local_demand": {"category": "beauty", "level": "medium", "date": "2026-11-15"},
    "store_visit": {
        "storeCode": "tp-01",
        "gtin": "036000291452",
        "result": "found",
        "visitedAt": "2026-11-16T19:30:00Z",
    },
    "actual_result": {
        "evaluationId": UUID_EVAL,
        "channel": "local",
        "units": 2,
        "purchasePrice": "29.00",
        "salePrice": "75.00",
        "actualCosts": "9.50",
        "purchasedOn": "2026-11-16",
        "soldOn": "2026-11-20",
    },
    "client_request": {
        "clientAlias": "cliente-sintetico-7",
        "items": ["MP-1"],
        "quantity": 1,
        "modality": "link_only",
        "date": "2026-11-18",
    },
}


def _captura(tipo: str, **cambios: Any) -> dict[str, Any]:
    datos = copy.deepcopy(CAPTURAS[tipo])
    datos.update(cambios)
    return datos


def _motivo_captura(tipo: str, datos: dict[str, Any], dia: dt.date | None = DIA) -> str | None:
    """El primer motivo de la captura: el de la lectura o, si se lee, el del precio."""
    try:
        captura = leer_captura(tipo, datos, zona=ZONA, dia_de_carga=dia)
    except RegistroInvalido as error:
        return error.motivo
    return motivo_de_rechazo(captura)


@pytest.mark.parametrize("tipo", sorted(CAPTURAS))
def test_cada_captura_base_es_valida_con_el_dia_de_la_carga(tipo):
    assert _motivo_captura(tipo, _captura(tipo)) is None
    captura = leer_captura(tipo, _captura(tipo), zona=ZONA, dia_de_carga=DIA)
    assert captura.precio_invalido is False


# --- Precios de las capturas → PRECIO INVÁLIDO -------------------------------------------

PRECIOS = [
    ("local_comparable", "askingPrice"),
    ("local_estimate", "price"),
    ("msrp", "value"),
    ("actual_result", "purchasePrice"),
    ("actual_result", "salePrice"),
]


@pytest.mark.parametrize(("tipo", "campo"), PRECIOS)
@pytest.mark.parametrize("precio", ["0", "0.00", "-5.00"])
def test_precio_de_captura_no_positivo_es_precio_invalido(tipo, campo, precio):
    datos = _captura(tipo, **{campo: precio})
    captura = leer_captura(tipo, datos, zona=ZONA, dia_de_carga=DIA)
    assert captura.precio_invalido is True
    assert motivo_de_rechazo(captura) == PRECIO_INVALIDO


@pytest.mark.parametrize(("tipo", "campo"), PRECIOS)
@pytest.mark.parametrize("precio", ["29.001", "0.005"])
def test_precio_de_captura_con_mas_de_2_decimales_es_precio_invalido(tipo, campo, precio):
    datos = _captura(tipo, **{campo: precio})
    assert _motivo_captura(tipo, datos) == PRECIO_INVALIDO


@pytest.mark.parametrize(("tipo", "campo"), PRECIOS)
@pytest.mark.parametrize("precio", ["29.000", "29.5", "0.01"])
def test_precio_de_captura_con_2_decimales_o_ceros_finales_es_valido(tipo, campo, precio):
    assert _motivo_captura(tipo, _captura(tipo, **{campo: precio})) is None


def test_un_comparable_con_precio_invalido_no_tiene_price_usd():
    datos = _captura(
        "local_comparable", askingPrice="1500.001", currency="MXN", exchangeRate="17.3"
    )
    comparable = leer_captura("local_comparable", datos, zona=ZONA, dia_de_carga=DIA)
    assert comparable.precio_invalido is True
    assert comparable.price_usd is None


@pytest.mark.parametrize("tipo", ["local_demand", "store_visit", "client_request"])
def test_una_captura_sin_precio_nunca_es_precio_invalido(tipo):
    captura = leer_captura(tipo, _captura(tipo), zona=ZONA, dia_de_carga=DIA)
    assert captura.precio_invalido is False
    assert motivo_de_rechazo(captura) is None


def test_el_campo_faltante_va_antes_que_el_precio_invalido():
    """Orden de design.md §6: obligatorios (y valores no válidos) antes del precio."""
    datos = _captura("actual_result", purchasePrice="0", actualCosts="-1")
    assert _motivo_captura("actual_result", datos) == _faltante("actualCosts")
    datos = _captura("local_comparable", askingPrice="0")
    datos.pop("city")
    assert _motivo_captura("local_comparable", datos) == _faltante("city")
    datos = _captura("local_estimate", price="0", date="2026-11-22")
    assert _motivo_captura("local_estimate", datos) == _faltante("date")


def test_motivo_de_rechazo_exige_una_captura_ya_leida():
    with pytest.raises(TypeError):
        motivo_de_rechazo(CAPTURAS["local_estimate"])  # type: ignore[arg-type]


# --- Rangos de actual_result → CAMPO OBLIGATORIO FALTANTE ---------------------------------


@pytest.mark.parametrize("costos", ["-0.01", "-9.50"])
def test_actual_costs_negativo_es_campo_faltante(costos):
    datos = _captura("actual_result", actualCosts=costos)
    assert _motivo_captura("actual_result", datos) == _faltante("actualCosts")


@pytest.mark.parametrize("costos", ["9.501", "0.001"])
def test_actual_costs_con_mas_de_2_decimales_es_campo_faltante(costos):
    datos = _captura("actual_result", actualCosts=costos)
    assert _motivo_captura("actual_result", datos) == _faltante("actualCosts")


@pytest.mark.parametrize("costos", ["0", "0.00", "9.50", "9.500"])
def test_actual_costs_cero_o_con_2_decimales_es_valido(costos):
    assert _motivo_captura("actual_result", _captura("actual_result", actualCosts=costos)) is None


@pytest.mark.parametrize("unidades", [0, -1])
def test_units_menor_que_1_es_campo_faltante(unidades):
    datos = _captura("actual_result", units=unidades)
    assert _motivo_captura("actual_result", datos) == _faltante("units")


def test_units_1_es_valido():
    assert _motivo_captura("actual_result", _captura("actual_result", units=1)) is None


def test_sold_on_antes_de_purchased_on_es_campo_faltante():
    datos = _captura("actual_result", purchasedOn="2026-11-16", soldOn="2026-11-15")
    assert _motivo_captura("actual_result", datos) == _faltante("soldOn")
    # Sin el día de la carga también se comprueba: no depende de él.
    assert _motivo_captura("actual_result", datos, dia=None) == _faltante("soldOn")


def test_sold_on_el_mismo_dia_que_purchased_on_es_valido():
    datos = _captura("actual_result", purchasedOn="2026-11-16", soldOn="2026-11-16")
    assert _motivo_captura("actual_result", datos) is None


def test_purchased_on_no_valido_se_cita_y_no_soldon():
    datos = _captura("actual_result", purchasedOn="no-es-fecha", soldOn="2026-11-15")
    assert _motivo_captura("actual_result", datos) == _faltante("purchasedOn")


# --- Fechas posteriores al día de la carga ------------------------------------------------

FECHAS = [
    ("local_comparable", "date"),
    ("local_estimate", "date"),
    ("msrp", "date"),
    ("local_demand", "date"),
    ("client_request", "date"),
    ("actual_result", "purchasedOn"),
    ("actual_result", "soldOn"),
]


@pytest.mark.parametrize(("tipo", "campo"), FECHAS)
def test_una_fecha_posterior_al_dia_de_la_carga_es_campo_faltante(tipo, campo):
    cambios = {campo: "2026-11-22"}
    if campo == "purchasedOn":
        cambios["soldOn"] = "2026-11-22"
    datos = _captura(tipo, **cambios)
    assert _motivo_captura(tipo, datos) == _faltante(campo)


@pytest.mark.parametrize(("tipo", "campo"), FECHAS)
def test_una_fecha_igual_al_dia_de_la_carga_es_valida(tipo, campo):
    cambios = {campo: "2026-11-21"}
    if campo == "purchasedOn":
        cambios["soldOn"] = "2026-11-21"
    assert _motivo_captura(tipo, _captura(tipo, **cambios)) is None


@pytest.mark.parametrize(("tipo", "campo"), FECHAS)
def test_sin_dia_de_la_carga_no_se_comprueba_la_fecha(tipo, campo):
    cambios = {campo: "2030-01-01"}
    if campo == "purchasedOn":
        cambios["soldOn"] = "2030-01-01"
    assert _motivo_captura(tipo, _captura(tipo, **cambios), dia=None) is None


@pytest.mark.parametrize(
    ("visitado", "esperado"),
    [
        # Sin desfase: en la zona de general.timezone (DEC-240).
        ("2026-11-21T23:59:00", None),
        ("2026-11-22T00:00:00", _faltante("visitedAt")),
        # Con desfase: el día se toma en la zona (05:00Z del 22 es el 21 en Tijuana).
        ("2026-11-22T05:00:00Z", None),
        ("2026-11-22T08:00:00Z", _faltante("visitedAt")),
        ("2026-11-21T23:30:00-08:00", None),
    ],
)
def test_visited_at_se_compara_con_el_dia_de_la_carga_en_la_zona(visitado, esperado):
    datos = _captura("store_visit", visitedAt=visitado)
    assert _motivo_captura("store_visit", datos) == esperado


def test_visited_at_con_desfase_y_sin_zona_usa_su_propio_desfase():
    datos = _captura("store_visit", visitedAt="2026-11-22T05:00:00Z")
    with pytest.raises(RegistroInvalido) as error:
        leer_captura("store_visit", datos, dia_de_carga=DIA)
    assert error.value.motivo == _faltante("visitedAt")


@pytest.mark.parametrize("dia", ["2026-11-21", dt.datetime(2026, 11, 21, tzinfo=dt.UTC), 20261121])
def test_el_dia_de_la_carga_debe_ser_una_fecha(dia):
    with pytest.raises(TypeError):
        leer_captura("local_demand", _captura("local_demand"), zona=ZONA, dia_de_carga=dia)


def test_el_resultado_depende_solo_del_dia_que_llega_como_dato():
    """Sin reloj: la misma captura vale o no según el día de la carga que se pasa."""
    datos = _captura("local_demand", date="2026-11-22")
    assert _motivo_captura("local_demand", datos, dia=DIA) == _faltante("date")
    assert _motivo_captura("local_demand", datos, dia=dt.date(2026, 11, 22)) is None
    assert _motivo_captura("local_demand", datos, dia=dt.date(2099, 1, 1)) is None


# --- Los motivos no llevan valores (R-20) -------------------------------------------------


def test_el_motivo_no_lleva_el_valor_ni_el_alias():
    alias = "cliente-sintetico-7"
    datos = _captura("client_request", date="2026-11-30")
    with pytest.raises(RegistroInvalido) as error:
        leer_captura("client_request", datos, zona=ZONA, dia_de_carga=DIA)
    assert error.value.motivo == _faltante("date")
    texto = f"{error.value} {error.value!r} {error.value.args}"
    assert alias not in texto
    assert "2026-11-30" not in texto
    datos = _captura("actual_result", actualCosts="-12.345")
    with pytest.raises(RegistroInvalido) as error:
        leer_captura("actual_result", datos, zona=ZONA, dia_de_carga=DIA)
    assert "12.345" not in f"{error.value} {error.value!r}"
