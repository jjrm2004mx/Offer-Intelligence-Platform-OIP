"""Pruebas de oip-tester para T03 de req-2026-0001-b-evaluacion (contrato 3.1 y capturas).

T03 no tiene escenarios propios (tasks.md §3; B20 se ejercita en T07 y B34 en T08 y T21).
Estas pruebas cubren sus comportamientos esperados de forma independiente de las del
developer, con los datos copiados de las fuentes y no del código:

- la observación de base es el ejemplo de la arquitectura v2.2 §8, leída como JSON con
  ``parse_float=Decimal`` (CTR-02), con los dominios cambiados a example.com;
- los obligatorios y su orden son los de la arquitectura §8 y de CTR-04 (design.md §6),
  escritos aquí a mano;
- los motivos de B20 (c, f, h) y B34 (a.2, b) en la capa del esquema, con el nombre del
  campo en el archivo (DEC-234);
- GTIN con ejemplos públicos de GS1 (no calculados con el código bajo prueba);
- MXN → USD sin redondear (S-23): se comprueba que el resultado no se cuantiza;
- el alias del cliente no sale en ``repr``, ``str``, el motivo, la traza ni los logs.

Sin marcador de escenario: T03 no tiene escenarios propios. Fixtures sintéticos; ninguna
prueba abre una URL.
"""

import copy
import json
import logging
import traceback
from decimal import Decimal

import pytest
from pydantic import ValidationError

from oip.entradas._comun import RegistroInvalido
from oip.entradas.capturas import ESQUEMAS_CAPTURA, leer_captura
from oip.entradas.contrato import gtin_valido, leer_observacion

# --- Datos de las fuentes ---------------------------------------------------------------

# Ejemplo de la arquitectura v2.2 §8, con example.com en lugar del comercio.
_EJEMPLO_ARQ_8 = """{
  "schemaVersion": "3.1",
  "crawlJobId": "8a1c6c1e-0000-4000-8000-0000000000aa",
  "idempotencyKey": "tienda|https://tienda.example.com/p/123|t-0123|2026-11-16T18:00",
  "retailerCode": "tienda",
  "storeCode": "t-0123",
  "sourceType": "clearance",
  "productUrl": "https://tienda.example.com/p/123",
  "title": "Taladro de prueba",
  "brand": "MarcaP",
  "model": "MP-1",
  "gtin": "0123456789012",
  "content": "tool only",
  "category": "tools",
  "weightKg": 4.0,
  "dimsCm": null,
  "price": { "current": "29.00", "was": "129.00", "currency": "USD" },
  "seller": "comercio",
  "condition": "new",
  "availability": { "state": "in_stock", "text": "3 disponibles", "quantity": 3,
                    "scope": "store", "addToCart": null },
  "isClearance": true,
  "purchaseMode": "tienda",
  "taxLocation": "chula_vista",
  "shipping": { "toMeCost": "0.00", "days": null, "mode": "pickup" },
  "msrp": { "value": "149.00", "source": "fabricante", "date": "2026-11-10" },
  "amazonListing": null,
  "extractedAt": "2026-11-16T18:00:00Z",
  "extractionMethod": "playwright_jsonld",
  "blocked": false,
  "evidence": { "jsonld": true, "priceSelector": "..." }
}"""

#: Obligatorios del contrato, en el orden de la arquitectura v2.2 §8 (copiado a mano).
_OBLIGATORIOS_ARQ_8 = [
    "retailerCode",
    "productUrl",
    "title",
    "category",
    "price.current",
    "seller",
    "availability",
    "purchaseMode",
    "extractedAt",
    "blocked",
]


def _comercio() -> dict:
    return json.loads(_EJEMPLO_ARQ_8, parse_float=Decimal)


def _particular() -> dict:
    """Publicación de un particular de REQ §6 (familia 1), sintética."""
    return {
        "schemaVersion": "3.1",
        "retailerCode": "particular",
        "seller": "particular",
        "purchaseMode": "particular",
        "productUrl": "https://plataforma.example.com/item/1",
        "title": "VENDO YA llamar al 555 000 0000",
        "brand": "MarcaP",
        "model": "MP-1",
        "category": "electronics",
        "condition": "used",
        "price": {"current": "80.00", "currency": "USD"},
        "availability": {"state": "listed"},
        "pickupLocation": "san_diego",
        "extractedAt": "2026-11-17T10:00:00Z",
        "blocked": False,
    }


def _motivo(campo: str) -> str:
    return f"CAMPO OBLIGATORIO FALTANTE ({campo})"


def _quitar(datos: dict, ruta: str) -> dict:
    copia = copy.deepcopy(datos)
    *padres, hoja = ruta.split(".")
    nodo = copia
    for p in padres:
        nodo = nodo[p]
    del nodo[hoja]
    return copia


def _rechazo(funcion, *args) -> RegistroInvalido:
    with pytest.raises(RegistroInvalido) as info:
        funcion(*args)
    return info.value


# --- Contrato 3.1: lectura del ejemplo ---------------------------------------------------


def test_el_ejemplo_de_la_arquitectura_se_lee_completo():
    obs = leer_observacion(_comercio())
    assert obs.schema_version == "3.1"
    assert obs.retailer_code == "tienda"
    assert obs.title == "Taladro de prueba"  # en un comercio el title se conserva
    assert obs.price.current == Decimal("29.00")
    assert obs.price.was == Decimal("129.00")
    assert obs.shipping.to_me_cost == Decimal("0.00")
    assert obs.msrp.value == Decimal("149.00")
    assert obs.weight_kg == Decimal("4.0")
    assert obs.precio_invalido is False
    for monto in (obs.price.current, obs.price.was, obs.shipping.to_me_cost, obs.weight_kg):
        assert type(monto) is Decimal


def test_la_observacion_es_inmutable():
    obs = leer_observacion(_comercio())
    with pytest.raises(ValidationError):
        obs.title = "otro"


# --- Obligatorios del contrato -----------------------------------------------------------


@pytest.mark.parametrize("campo", _OBLIGATORIOS_ARQ_8)
def test_cada_obligatorio_de_la_arquitectura_ausente(campo):
    assert _rechazo(leer_observacion, _quitar(_comercio(), campo)).motivo == _motivo(campo)


@pytest.mark.parametrize("campo", [c for c in _OBLIGATORIOS_ARQ_8 if c != "blocked"])
@pytest.mark.parametrize("vacio", [None, "", "   "], ids=["null", "vacio", "espacios"])
def test_cada_obligatorio_nulo_o_vacio_cuenta_como_ausente(campo, vacio):
    datos = _comercio()
    *padres, hoja = campo.split(".")
    nodo = datos
    for p in padres:
        nodo = nodo[p]
    nodo[hoja] = vacio
    assert _rechazo(leer_observacion, datos).motivo == _motivo(campo)


@pytest.mark.parametrize("i", range(len(_OBLIGATORIOS_ARQ_8)))
def test_con_todos_desde_i_ausentes_el_motivo_es_el_i(i):
    """Sin los obligatorios i..n, el motivo es el i (el primero del orden de §8)."""
    datos = _comercio()
    for campo in _OBLIGATORIOS_ARQ_8[i:]:
        datos = _quitar(datos, campo)
    assert _rechazo(leer_observacion, datos).motivo == _motivo(_OBLIGATORIOS_ARQ_8[i])


def test_el_mensaje_de_error_es_exactamente_el_motivo():
    error = _rechazo(leer_observacion, _quitar(_comercio(), "category"))
    assert str(error) == "CAMPO OBLIGATORIO FALTANTE (category)"  # B20 (c)
    assert error.campo == "category"


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("category", "herramientas"),  # etiqueta en español, no el código
        ("category", "Tools"),
        ("condition", "nuevo"),
        ("seller", "Particular"),
        ("purchaseMode", "pickup"),
        ("availability.state", "disponible"),
    ],
)
def test_codigo_fuera_de_la_tabla_cerrada_es_campo_faltante(campo, valor):
    """DEC-234 (2): un código fuera de las tablas cerradas → CAMPO OBLIGATORIO FALTANTE."""
    datos = _comercio()
    *padres, hoja = campo.split(".")
    nodo = datos
    for p in padres:
        nodo = nodo[p]
    nodo[hoja] = valor
    assert _rechazo(leer_observacion, datos).motivo == _motivo(campo)


# --- schemaVersion -----------------------------------------------------------------------


@pytest.mark.parametrize("version", ["3.1", "3.0"])
def test_schema_version_aceptada(version):
    datos = _comercio()
    datos["schemaVersion"] = version
    assert leer_observacion(datos).schema_version == version


def test_schema_version_ausente_se_toma_31():
    datos = _comercio()
    del datos["schemaVersion"]
    assert leer_observacion(datos).schema_version == "3.1"


def test_schema_version_null_se_toma_31():
    datos = _comercio()
    datos["schemaVersion"] = None
    assert leer_observacion(datos).schema_version == "3.1"


# D-1 (defecto del tester): CTR-01 dice "ausente (se toma 3.1)" y CTR-03 "celda vacía =
# campo ausente"; el propio módulo trata el texto vacío como ausente en todos los demás
# campos (``_comun.ausente``). Un schemaVersion vacío se rechaza en lugar de tomarse 3.1.
@pytest.mark.parametrize("vacio", ["", "  "], ids=["vacio", "espacios"])
def test_d1_schema_version_vacia_es_ausente_y_se_toma_31(vacio):
    datos = _comercio()
    datos["schemaVersion"] = vacio
    assert leer_observacion(datos).schema_version == "3.1"


@pytest.mark.parametrize("version", ["2.0", "3.2", "4.0", "3", "3.10"])
def test_schema_version_no_aceptada_se_rechaza(version):
    datos = _comercio()
    datos["schemaVersion"] = version
    error = _rechazo(leer_observacion, datos)
    assert error.motivo == _motivo("schemaVersion")


def test_en_30_listed_no_existe():
    datos = _particular()
    datos["schemaVersion"] = "3.0"
    assert _rechazo(leer_observacion, datos).motivo == _motivo("availability.state")


def test_en_30_pickup_location_se_descarta_en_un_comercio():
    datos = _comercio()
    datos["schemaVersion"] = "3.0"
    datos["pickupLocation"] = "san_diego"
    assert leer_observacion(datos).pickup_location is None


def test_en_31_pickup_location_se_conserva():
    obs = leer_observacion(_particular())
    assert obs.pickup_location == "san_diego"
    assert obs.availability.state == "listed"


# --- Publicación de un particular (DEC-227 b, DEC-212) ----------------------------------


def test_title_del_particular_es_marca_mas_modelo():
    obs = leer_observacion(_particular())
    assert obs.title == "MarcaP MP-1"
    assert "555" not in obs.model_dump_json()


def test_title_del_particular_no_es_obligatorio_si_hay_marca_y_modelo():
    datos = _particular()
    del datos["title"]
    assert leer_observacion(datos).title == "MarcaP MP-1"


@pytest.mark.parametrize(
    ("campo", "letra"),
    [("pickupLocation", "f"), ("model", "h"), ("brand", None)],
)
def test_obligatorios_del_particular(campo, letra):
    """B20 (f) y (h) en la capa del esquema; ``brand`` por DEC-227 b."""
    assert _rechazo(leer_observacion, _quitar(_particular(), campo)).motivo == _motivo(campo)


def test_sin_marca_ni_modelo_cita_brand_y_no_title():
    datos = _quitar(_quitar(_particular(), "brand"), "model")
    assert _rechazo(leer_observacion, datos).motivo == _motivo("brand")


def test_orden_del_particular_pickup_location_brand_model():
    datos = _quitar(_quitar(_quitar(_particular(), "model"), "brand"), "pickupLocation")
    assert _rechazo(leer_observacion, datos).motivo == _motivo("pickupLocation")
    datos = _quitar(_quitar(_particular(), "model"), "brand")
    assert _rechazo(leer_observacion, datos).motivo == _motivo("brand")


def test_obligatorios_del_contrato_van_antes_que_los_del_particular():
    datos = _quitar(_quitar(_particular(), "pickupLocation"), "category")
    assert _rechazo(leer_observacion, datos).motivo == _motivo("category")  # B20 (c)
    datos = _quitar(_quitar(_particular(), "model"), "blocked")
    assert _rechazo(leer_observacion, datos).motivo == _motivo("blocked")


@pytest.mark.parametrize("campo", ["seller", "retailerCode", "purchaseMode"])
def test_basta_un_campo_particular_para_armar_el_title(campo):
    # Ajustada por DEC-239 (decisión de Jesús, 2026-11-18): si uno de los tres vale
    # particular, los tres deben valerlo; con uno solo, la observación se rechaza con el
    # primero de retailerCode, seller, purchaseMode (orden de REQ §6) que no lo vale.
    datos = _comercio()
    datos[campo] = "particular"
    datos["pickupLocation"] = "san_diego"
    primero = next(c for c in ("retailerCode", "seller", "purchaseMode") if c != campo)
    assert _rechazo(leer_observacion, datos).motivo == _motivo(primero)
    for otro in ("retailerCode", "seller", "purchaseMode"):
        datos[otro] = "particular"
    obs = leer_observacion(datos)
    assert obs.es_particular
    assert obs.title == "MarcaP MP-1"


def test_un_comercio_no_exige_pickup_location_ni_marca_ni_modelo():
    datos = _quitar(_quitar(_comercio(), "brand"), "model")
    assert leer_observacion(datos).pickup_location is None


def test_campos_desconocidos_se_descartan_del_particular():
    datos = _particular()
    datos["description"] = "texto libre del vendedor"
    datos["sellerPhone"] = "555 000 0000"
    datos["sellerName"] = "Nombre Persona"
    datos["recordType"] = "observation"
    datos["availability"]["contacto"] = "555"
    volcado = leer_observacion(datos).model_dump_json()
    for texto in ("texto libre", "555", "Nombre Persona", "recordType", "observation"):
        assert texto not in volcado


# --- GTIN (RN-013) -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "gtin",
    [
        "96385074",  # GTIN-8 (EAN-8), ejemplo público de GS1
        "036000291452",  # GTIN-12 (UPC-A)
        "4006381333931",  # GTIN-13 (EAN-13)
        "10012345678902",  # GTIN-14 con indicador 1
        "00000000000000",
        "0123456789012",  # el GTIN del ejemplo de la arquitectura §8
    ],
)
def test_gtin_valido(gtin):
    assert gtin_valido(gtin) is True


@pytest.mark.parametrize(
    "gtin",
    [
        "96385075",
        "036000291453",
        "4006381333932",
        "10012345678903",
        "0123456789013",  # el GTIN de ejemplo de la arquitectura con otro dígito
        "400638133393",  # 12 dígitos sin el último del EAN-13
        "123456789",  # 9
        "1234567890",  # 10
        "12345678901",  # 11
        "400638133393100",  # 15
        "40063813339A1",
        "４００６３８１３３３９３１",  # dígitos de ancho completo
        "4006381-333931",
        "",
        None,
        4006381333931,
    ],
)
def test_gtin_no_valido(gtin):
    assert gtin_valido(gtin) is False


def test_gtin_invalido_no_rechaza_la_observacion_pero_no_confirma():
    datos = _comercio()
    datos["gtin"] = "0123456789013"  # dígito verificador incorrecto (el correcto es 2)
    obs = leer_observacion(datos)
    assert obs.gtin == "0123456789013"
    assert obs.gtin_valido is False
    datos = _comercio()
    datos["gtin"] = "4006381333931"
    assert leer_observacion(datos).gtin_valido is True


def test_sin_gtin_no_confirma():
    assert leer_observacion(_quitar(_comercio(), "gtin")).gtin_valido is False


# --- price.current para PRECIO INVÁLIDO --------------------------------------------------


@pytest.mark.parametrize("precio", ["29.00", "0.01", "29", "29.1", "29.010", "1000000.00"])
def test_precio_valido_no_se_marca(precio):
    datos = _comercio()
    datos["price"]["current"] = precio
    assert leer_observacion(datos).precio_invalido is False


@pytest.mark.parametrize(
    "precio",
    ["0.00", "0", "-1.00", "-0.01", "29.001", "0.001", "abc", "NaN", "Infinity", "-Infinity"],
)
def test_precio_invalido_se_marca_sin_rechazar(precio):
    """B20 (a): $0.00 es PRECIO INVÁLIDO; la observación se lee y queda marcada (T07)."""
    datos = _comercio()
    datos["price"]["current"] = precio
    obs = leer_observacion(datos)
    assert obs.precio_invalido is True


def test_precio_invalido_no_tapa_un_obligatorio_anterior():
    datos = _quitar(_comercio(), "category")
    datos["price"]["current"] = "0.00"
    assert _rechazo(leer_observacion, datos).motivo == _motivo("category")


# --- Capturas (CTR-04) ------------------------------------------------------------------

_CAPTURAS = {
    "local_comparable": {
        "brand": "MarcaP",
        "model": "MP-1",
        "condition": "used",
        "askingPrice": "1500.00",
        "currency": "USD",
        "city": "tijuana",
        "date": "2026-11-18",
        "sold": False,
    },
    "local_estimate": {"gtin": "4006381333931", "price": "70.00", "date": "2026-11-18"},
    "msrp": {
        "gtin": "4006381333931",
        "value": "149.00",
        "source": "fabricante",
        "date": "2026-11-10",
    },
    "local_demand": {"category": "beauty", "level": "medium", "date": "2026-11-18"},
    "store_visit": {
        "storeCode": "t-0123",
        "gtin": "4006381333931",
        "result": "found",
        "visitedAt": "2026-11-18T10:00:00-08:00",
    },
    "actual_result": {
        "evaluationId": "8a1c6c1e-0000-4000-8000-0000000000bb",
        "channel": "local",
        "units": 1,
        "purchasePrice": "29.00",
        "salePrice": "80.00",
        "actualCosts": "5.50",
        "purchasedOn": "2026-11-10",
        "soldOn": "2026-11-15",
    },
    "client_request": {
        "clientAlias": "alias-sintetico-q7",
        "items": ["MP-1"],
        "quantity": 1,
        "acceptedConditions": ["new"],
        "modality": "link_only",
        "date": "2026-11-18",
    },
}

#: Obligatorios de CTR-04 (design.md §6) que siempre deben venir, en su orden.
_OBLIGATORIOS_CTR04 = {
    "local_comparable": ["condition", "askingPrice", "currency", "city", "date", "sold"],
    "local_estimate": ["price", "date"],
    "msrp": ["value", "source", "date"],
    "local_demand": ["category", "level", "date"],
    "store_visit": ["storeCode", "result", "visitedAt"],
    "actual_result": [
        "evaluationId",
        "channel",
        "units",
        "purchasePrice",
        "salePrice",
        "actualCosts",
        "purchasedOn",
        "soldOn",
    ],
    # acceptedConditions ya no es obligatorio: ausente o vacío vale [new] (DEC-241,
    # decisión de Jesús, 2026-11-18; RN-011 punto 2).
    "client_request": [
        "clientAlias",
        "items",
        "quantity",
        "modality",
        "date",
    ],
}


def _captura(tipo: str) -> dict:
    return copy.deepcopy(_CAPTURAS[tipo])


def test_son_exactamente_los_7_tipos_de_req_6():
    assert {str(t) for t in ESQUEMAS_CAPTURA} == set(_CAPTURAS)


@pytest.mark.parametrize("tipo", sorted(_CAPTURAS))
def test_cada_captura_completa_se_lee(tipo):
    assert leer_captura(tipo, _captura(tipo)) is not None


@pytest.mark.parametrize(
    ("tipo", "campo"),
    [(t, c) for t, campos in _OBLIGATORIOS_CTR04.items() for c in campos],
)
def test_cada_obligatorio_de_ctr04_ausente(tipo, campo):
    error = _rechazo(leer_captura, tipo, _quitar(_captura(tipo), campo))
    assert error.motivo == _motivo(campo)


@pytest.mark.parametrize(
    ("tipo", "i"),
    [(t, i) for t, campos in _OBLIGATORIOS_CTR04.items() for i in range(len(campos))],
)
def test_captura_con_los_obligatorios_desde_i_ausentes_cita_el_i(tipo, i):
    datos = _captura(tipo)
    for campo in _OBLIGATORIOS_CTR04[tipo][i:]:
        datos = _quitar(datos, campo)
    error = _rechazo(leer_captura, tipo, datos)
    assert error.motivo == _motivo(_OBLIGATORIOS_CTR04[tipo][i])


@pytest.mark.parametrize("tipo", ["local_comparable", "local_estimate", "msrp"])
def test_producto_faltante_cita_gtin_o_el_que_falte(tipo):
    datos = _captura(tipo)
    datos.pop("gtin", None)
    datos.pop("brand", None)
    datos.pop("model", None)
    assert _rechazo(leer_captura, tipo, datos).motivo == _motivo("gtin")
    con_marca = dict(datos, brand="MarcaP")
    assert _rechazo(leer_captura, tipo, con_marca).motivo == _motivo("model")
    con_modelo = dict(datos, model="MP-1")
    assert _rechazo(leer_captura, tipo, con_modelo).motivo == _motivo("brand")
    assert leer_captura(tipo, dict(datos, gtin="4006381333931")) is not None
    assert leer_captura(tipo, dict(datos, brand="MarcaP", model="MP-1")) is not None


def test_producto_faltante_va_antes_que_los_demas_obligatorios():
    datos = {"askingPrice": "10.00"}  # local_comparable casi vacío
    assert _rechazo(leer_captura, "local_comparable", datos).motivo == _motivo("gtin")


def test_store_visit_con_evaluation_id_no_necesita_producto():
    datos = _captura("store_visit")
    del datos["gtin"]
    datos["evaluationId"] = "8a1c6c1e-0000-4000-8000-0000000000bb"
    assert leer_captura("store_visit", datos) is not None
    del datos["evaluationId"]
    assert _rechazo(leer_captura, "store_visit", datos).motivo == _motivo("gtin")


@pytest.mark.parametrize(
    ("tipo", "campo", "valor"),
    [
        ("local_comparable", "condition", "usado"),
        ("local_comparable", "currency", "mxn"),
        ("local_comparable", "currency", "EUR"),
        ("local_demand", "level", "media"),
        ("local_demand", "category", "perfumes"),
        ("store_visit", "result", "encontrado"),
        ("actual_result", "channel", "facebook"),
        ("client_request", "modality", "solo_enlace"),
        ("client_request", "acceptedConditions", ["nuevo"]),
    ],
)
def test_captura_con_codigo_fuera_de_la_tabla_es_campo_faltante(tipo, campo, valor):
    datos = _captura(tipo)
    datos[campo] = valor
    assert _rechazo(leer_captura, tipo, datos).motivo == _motivo(campo)


# --- B34 en la capa del esquema ---------------------------------------------------------


def test_b34_a2_comparable_en_mxn_sin_tipo_de_cambio():
    datos = _captura("local_comparable")
    datos["currency"] = "MXN"
    assert _rechazo(leer_captura, "local_comparable", datos).motivo == _motivo("exchangeRate")


def test_b34_b_comparable_en_usd_sin_estado():
    datos = _quitar(_captura("local_comparable"), "condition")
    assert _rechazo(leer_captura, "local_comparable", datos).motivo == _motivo("condition")


def test_b34_a3_demanda_local_de_beauty_media():
    demanda = leer_captura("local_demand", _captura("local_demand"))
    assert demanda.category == "beauty"
    assert demanda.level == "medium"


@pytest.mark.parametrize("tipo", ["coupon", "observation", "", None, "LOCAL_COMPARABLE"])
def test_tipo_que_no_es_captura_es_tipo_desconocido(tipo):
    error = _rechazo(leer_captura, tipo, {})
    assert error.motivo == "TIPO DE REGISTRO DESCONOCIDO"


# --- MXN → USD sin redondear (S-23) -----------------------------------------------------


def test_comparable_en_mxn_exacto():
    datos = _captura("local_comparable")
    datos.update(currency="MXN", askingPrice="1720.00", exchangeRate="17.20")
    assert leer_captura("local_comparable", datos).price_usd == Decimal("100")


def test_comparable_en_mxn_no_se_redondea():
    datos = _captura("local_comparable")
    datos.update(currency="MXN", askingPrice="1000.00", exchangeRate="17.30")
    usd = leer_captura("local_comparable", datos).price_usd
    assert type(usd) is Decimal
    # 1000 / 17.30 = 57.8034682080924855491329479768... : sin cuantizar a centavos.
    assert usd != usd.quantize(Decimal("0.01"))
    assert usd != usd.quantize(Decimal("0.0001"))
    assert str(usd).startswith("57.80346820809248554913")
    assert abs(usd * Decimal("17.30") - Decimal("1000.00")) < Decimal("1E-20")


def test_comparable_en_usd_conserva_el_precio_y_no_usa_el_tipo_de_cambio():
    datos = _captura("local_comparable")
    datos["exchangeRate"] = "17.30"
    assert leer_captura("local_comparable", datos).price_usd == Decimal("1500.00")


@pytest.mark.parametrize("tasa", ["0", "-17.30", "abc", 17.3])
def test_tipo_de_cambio_no_valido_en_mxn(tasa):
    datos = _captura("local_comparable")
    datos.update(currency="MXN", exchangeRate=tasa)
    assert _rechazo(leer_captura, "local_comparable", datos).motivo == _motivo("exchangeRate")


@pytest.mark.parametrize("precio", ["0", "0.00", "-5.00"])
def test_asking_price_no_positivo_se_marca_para_precio_invalido(precio):
    datos = _captura("local_comparable")
    datos["askingPrice"] = precio
    comparable = leer_captura("local_comparable", datos)
    assert comparable.precio_invalido is True
    assert comparable.price_usd is None


# --- Sin float, campos desconocidos, inmutables -----------------------------------------


@pytest.mark.parametrize(
    ("tipo", "campo"),
    [
        ("local_comparable", "askingPrice"),
        ("local_estimate", "price"),
        ("msrp", "value"),
        ("actual_result", "purchasePrice"),
        ("actual_result", "salePrice"),
        ("actual_result", "actualCosts"),
    ],
)
def test_un_monto_float_no_se_acepta(tipo, campo):
    datos = _captura(tipo)
    datos[campo] = 29.5
    if campo != "actualCosts":
        # Los cinco precios no válidos se marcan para PRECIO INVÁLIDO (no pasan por float;
        # DEC-276).
        captura = leer_captura(tipo, datos)
        assert captura.precio_invalido is True
        assert all(not isinstance(v, float) for v in captura.model_dump().values())
    else:
        assert _rechazo(leer_captura, tipo, datos).motivo == _motivo(campo)


@pytest.mark.parametrize("tipo", sorted(_CAPTURAS))
def test_montos_de_captura_son_decimal_desde_json(tipo):
    renglon = json.dumps(_captura(tipo)).replace('"29.00"', "29.00")
    captura = leer_captura(tipo, json.loads(renglon, parse_float=Decimal))
    for valor in captura.model_dump().values():
        assert not isinstance(valor, float)


@pytest.mark.parametrize("tipo", sorted(_CAPTURAS))
def test_campos_desconocidos_y_record_type_se_descartan(tipo):
    datos = _captura(tipo)
    datos["recordType"] = tipo
    datos["notes"] = "llamar al 555 000 0000"
    datos["telefono"] = "555 000 0000"
    captura = leer_captura(tipo, datos)
    volcado = captura.model_dump_json()
    assert "555" not in volcado
    assert "recordType" not in volcado and "record_type" not in volcado


@pytest.mark.parametrize("tipo", sorted(_CAPTURAS))
def test_capturas_inmutables(tipo):
    captura = leer_captura(tipo, _captura(tipo))
    campo = next(iter(type(captura).model_fields))
    with pytest.raises(ValidationError):
        setattr(captura, campo, None)


# --- client_request (RNF-11) ------------------------------------------------------------

_ALIAS = "alias-sintetico-q7"


def test_client_request_no_tiene_notas_ni_texto_libre():
    campos = set(ESQUEMAS_CAPTURA["client_request"].model_fields)
    assert campos == {
        "client_alias",
        "items",
        "quantity",
        "accepted_conditions",
        "modality",
        "postal_code",
        "date",
    }
    for prohibido in ("notes", "notas", "note", "comments"):
        assert prohibido not in campos


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("items", []),
        ("items", ["a", "b", "c", "d"]),
        ("items", [""]),
        ("quantity", 0),
        ("quantity", -1),
        # ("acceptedConditions", []) sale de aquí: vacío vale [new] (DEC-241); lo cubre
        # test_client_request_sin_accepted_conditions_vale_solo_nuevo.
        ("modality", "otra"),
        ("date", "18/11/2026"),
    ],
)
def test_client_request_valores_no_validos(campo, valor):
    datos = _captura("client_request")
    datos[campo] = valor
    assert _rechazo(leer_captura, "client_request", datos).motivo == _motivo(campo)


@pytest.mark.parametrize("n", [1, 2, 3])
def test_client_request_de_1_a_3_articulos(n):
    datos = _captura("client_request")
    datos["items"] = [f"MP-{i}" for i in range(n)]
    assert len(leer_captura("client_request", datos).items) == n


@pytest.mark.parametrize("vacio", ["ausente", None, []], ids=["ausente", "null", "vacio"])
def test_client_request_sin_accepted_conditions_vale_solo_nuevo(vacio):
    """Antes ``test_client_request_sin_accepted_conditions_se_rechaza``: fijaba el rechazo
    mientras Jesús resolvía la contradicción entre REQ §6 (obligatorio) y "por defecto
    [new]" (REQ §3.4 punto 1, RN-011 punto 2, columna de tipos de CTR-04). Jesús la resolvió
    el 2026-11-18 (DEC-241): mandan las RN, ausente o vacío vale [new]."""
    datos = _quitar(_captura("client_request"), "acceptedConditions")
    if vacio != "ausente":
        datos["acceptedConditions"] = vacio
    solicitud = leer_captura("client_request", datos)
    assert [str(c) for c in solicitud.accepted_conditions] == ["new"]


def test_el_alias_no_sale_en_repr_ni_str():
    solicitud = leer_captura("client_request", _captura("client_request"))
    assert solicitud.client_alias == _ALIAS
    assert _ALIAS not in repr(solicitud)
    assert _ALIAS not in str(solicitud)


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("quantity", 0),
        ("items", []),
        ("modality", _ALIAS),  # el alias como valor no válido de otro campo
        ("date", _ALIAS),
        ("acceptedConditions", [_ALIAS]),
        ("items", [_ALIAS, "b", "c", "d"]),
    ],
)
def test_el_alias_no_sale_en_el_error_la_traza_ni_los_logs(campo, valor, caplog):
    datos = _captura("client_request")
    datos[campo] = valor
    with caplog.at_level(logging.DEBUG):
        error = _rechazo(leer_captura, "client_request", datos)
    traza = "".join(traceback.format_exception(error))
    for texto in (str(error), repr(error), error.motivo, str(error.campo), traza, caplog.text):
        assert _ALIAS not in texto
    for argumento in error.args:
        assert _ALIAS not in str(argumento)


@pytest.mark.parametrize("valor", [12345, ["lista"], {"a": 1}])
def test_alias_mal_formado_no_sale_en_el_error(valor, caplog):
    datos = _captura("client_request")
    datos["clientAlias"] = valor
    with caplog.at_level(logging.DEBUG):
        error = _rechazo(leer_captura, "client_request", datos)
    assert error.motivo == _motivo("clientAlias")
    traza = "".join(traceback.format_exception(error))
    assert str(valor) not in traza
    assert str(valor) not in caplog.text


def test_el_error_no_encadena_la_validacion_de_pydantic():
    """Una excepción encadenada (``__context__``) llevaría el valor recibido a la traza."""
    datos = _captura("client_request")
    datos["quantity"] = 0
    error = _rechazo(leer_captura, "client_request", datos)
    assert error.__cause__ is None
    assert error.__context__ is None
