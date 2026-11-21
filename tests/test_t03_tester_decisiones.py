"""Pruebas de oip-tester (tercera pasada) para T03: decisiones DEC-236 a DEC-241.

Independientes de las del developer. Los datos salen de las fuentes (arquitectura v2.2 §8,
REQ §6, RN-011, DEC-236 a DEC-241), no del código. Los valores en UTC de los cambios de
horario de America/Tijuana se escribieron a mano (PST −8, PDT −7; cambio el 2026-03-08 a las
2:00 y el 2026-11-01 a las 2:00). Sin marcador de escenario: T03 no tiene escenarios propios.
Fixtures sintéticos (example.com); ninguna prueba abre una URL.
"""

import copy
import datetime as dt
import json
import logging
import traceback
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from oip.catalogos import MotivoRechazo
from oip.entradas._comun import RegistroInvalido
from oip.entradas.capturas import leer_captura
from oip.entradas.contrato import leer_observacion

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

_UTC = dt.UTC


def _comercio() -> dict:
    return json.loads(_EJEMPLO_ARQ_8, parse_float=Decimal)


def _particular() -> dict:
    """Publicación de un particular (REQ §6 familia 1) con texto libre del vendedor."""
    return {
        "schemaVersion": "3.1",
        "retailerCode": "particular",
        "seller": "particular",
        "purchaseMode": "particular",
        "sourceType": "manual",
        "productUrl": "https://plataforma.example.com/item/1",
        "title": "texto del vendedor",
        "brand": "MarcaP",
        "model": "MP-1",
        "content": "tool only",
        "category": "tools",
        "condition": "used",
        "price": {"current": "70.00", "currency": "USD"},
        "availability": {"state": "listed", "text": "llamar al 555 000 0000"},
        "pickupLocation": "san_diego",
        "extractedAt": "2026-11-17T10:00:00Z",
        "extractionMethod": "manual_capture",
        "blocked": False,
        "evidence": {"nota": "vendedor Juan 555 000 0000"},
    }


def _motivo(campo: str) -> str:
    return f"CAMPO OBLIGATORIO FALTANTE ({campo})"


def _rechazo(funcion, *args, **kwargs) -> RegistroInvalido:
    with pytest.raises(RegistroInvalido) as info:
        funcion(*args, **kwargs)
    return info.value


def _poner(datos: dict, ruta: str, valor) -> dict:
    copia = copy.deepcopy(datos)
    *padres, hoja = ruta.split(".")
    nodo = copia
    for p in padres:
        if nodo.get(p) is None:
            nodo[p] = {}
        nodo = nodo[p]
    nodo[hoja] = valor
    return copia


# --- DEC-236: el particular sin availability.text ni evidence ------------------------


def test_dec236_particular_descarta_text_y_evidence_y_conserva_source_y_method():
    obs = leer_observacion(_particular())
    volcado = json.dumps(obs.model_dump(mode="json", by_alias=True))
    assert obs.availability.text is None
    assert obs.evidence is None
    assert "555 000 0000" not in volcado
    assert "Juan" not in volcado
    assert obs.source_type == "manual"
    assert obs.extraction_method == "manual_capture"
    assert str(obs.availability.state) == "listed"


def test_dec236_particular_con_evidence_mal_formada_no_se_rechaza():
    """``evidence`` se descarta antes de validar: su forma no importa en el particular."""
    datos = {**_particular(), "evidence": "texto libre"}
    datos["availability"] = {"state": "listed", "text": ["no", "es", "texto"]}
    obs = leer_observacion(datos)
    assert obs.evidence is None
    assert obs.availability.text is None


def test_dec236_comercio_sin_cambios():
    obs = leer_observacion(_comercio())
    assert obs.availability.text == "3 disponibles"
    assert obs.evidence == {"jsonld": True, "priceSelector": "..."}
    assert obs.content == "tool only"
    assert obs.source_type == "clearance"
    assert obs.extraction_method == "playwright_jsonld"


def test_dec236_comercio_con_evidence_no_valida_se_rechaza():
    """En el comercio, ``evidence`` sigue validándose (DEC-244: opcional no válido)."""
    datos = {**_comercio(), "evidence": "texto libre"}
    assert _rechazo(leer_observacion, datos).motivo == _motivo("evidence")


def test_dec245_content_del_particular_se_conserva():
    """DEC-245 (resuelve el pendiente de DEC-236): ``content`` del particular se conserva."""
    assert leer_observacion(_particular()).content == "tool only"


# --- DEC-237: availability sin state --------------------------------------------------


@pytest.mark.parametrize(
    "disponibilidad",
    [{}, {"state": None}, {"state": ""}, {"state": "   "}, {"text": "3 disponibles"}],
    ids=["vacio", "null", "texto-vacio", "espacios", "solo-texto"],
)
def test_dec237_availability_sin_state(disponibilidad):
    datos = {**_comercio(), "availability": disponibilidad}
    assert _rechazo(leer_observacion, datos).motivo == _motivo("availability.state")


def test_dec237_availability_ausente_sigue_citando_availability():
    datos = _comercio()
    del datos["availability"]
    assert _rechazo(leer_observacion, datos).motivo == _motivo("availability")


def test_dec237_posicion_despues_de_seller_y_antes_de_purchase_mode():
    """Orden de la arquitectura §8: ... seller, availability, purchaseMode, extractedAt."""
    datos = {**_comercio(), "availability": {}}
    del datos["purchaseMode"]
    del datos["extractedAt"]
    assert _rechazo(leer_observacion, datos).motivo == _motivo("availability.state")
    del datos["seller"]
    assert _rechazo(leer_observacion, datos).motivo == _motivo("seller")


# --- DEC-238: enteros y booleanos estrictos -------------------------------------------


@pytest.mark.parametrize(
    ("ruta", "valor"),
    [
        ("availability.quantity", True),
        ("availability.quantity", "3"),
        ("availability.quantity", Decimal("3.0")),
        ("availability.addToCart", 0),
        ("availability.addToCart", "false"),
        ("blocked", "false"),
        ("blocked", 0),
        ("blocked", "0"),
        ("isClearance", 1),
        ("shipping.days", True),
        ("amazonListing.reviews", True),
        ("amazonListing.boughtLastMonth", "100"),
        ("amazonListing.rankSub", Decimal("5")),
    ],
)
def test_dec238_observacion_estricta(ruta, valor):
    datos = _poner(_comercio(), ruta, valor)
    assert _rechazo(leer_observacion, datos).motivo == _motivo(ruta)


def test_dec238_observacion_acepta_int_y_bool_de_json():
    datos = _poner(_comercio(), "availability.addToCart", True)
    datos = _poner(datos, "amazonListing.reviews", 12)
    obs = leer_observacion(datos)
    assert obs.availability.quantity == 3
    assert obs.availability.add_to_cart is True
    assert obs.blocked is False
    assert obs.is_clearance is True


_CAPTURAS = {
    "local_comparable": {
        "brand": "MarcaP",
        "model": "MP-1",
        "condition": "used",
        "askingPrice": "120.00",
        "currency": "USD",
        "city": "san_diego",
        "date": "2026-11-18",
        "sold": False,
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
        "clientAlias": "alias-sintetico-z9",
        "items": ["MP-1"],
        "quantity": 1,
        "acceptedConditions": ["new"],
        "modality": "link_only",
        "date": "2026-11-18",
    },
    "store_visit": {
        "storeCode": "t-0123",
        "gtin": "4006381333931",
        "result": "found",
        "visitedAt": "2026-11-18T10:00:00-08:00",
    },
}


def _captura(tipo: str) -> dict:
    return copy.deepcopy(_CAPTURAS[tipo])


@pytest.mark.parametrize(
    ("tipo", "campo", "valor"),
    [
        ("local_comparable", "sold", "true"),
        ("local_comparable", "sold", "false"),
        ("local_comparable", "sold", 1),
        ("local_comparable", "sold", 0),
        ("actual_result", "units", True),
        ("actual_result", "units", "2"),
        ("actual_result", "units", Decimal("2")),
        ("client_request", "quantity", True),
        ("client_request", "quantity", "1"),
    ],
)
def test_dec238_capturas_estrictas(tipo, campo, valor):
    datos = {**_captura(tipo), campo: valor}
    assert _rechazo(leer_captura, tipo, datos).motivo == _motivo(campo)


def test_dec238_capturas_aceptan_int_y_bool():
    assert leer_captura("local_comparable", _captura("local_comparable")).sold is False
    assert leer_captura("actual_result", _captura("actual_result")).units == 1
    assert leer_captura("client_request", _captura("client_request")).quantity == 1


# --- DEC-239: coherencia del particular -----------------------------------------------

_TRES = ("retailerCode", "seller", "purchaseMode")


@pytest.mark.parametrize(
    ("particulares", "esperado"),
    [
        (("retailerCode",), "seller"),
        (("seller",), "retailerCode"),
        (("purchaseMode",), "retailerCode"),
        (("retailerCode", "seller"), "purchaseMode"),
        (("retailerCode", "purchaseMode"), "seller"),
        (("seller", "purchaseMode"), "retailerCode"),
    ],
)
def test_dec239_primero_que_no_vale_particular_en_orden_de_req_6(particulares, esperado):
    datos = {**_comercio(), "pickupLocation": "san_diego"}
    for campo in particulares:
        datos[campo] = "particular"
    error = _rechazo(leer_observacion, datos)
    assert error.motivo == _motivo(esperado)
    assert error.motivo.startswith(MotivoRechazo.CAMPO_OBLIGATORIO_FALTANTE.value)


def test_dec239_los_tres_particular_se_leen():
    obs = leer_observacion(_particular())
    assert obs.es_particular
    assert obs.title == "MarcaP MP-1"


def test_dec239_sin_ninguno_particular_es_un_comercio():
    obs = leer_observacion(_comercio())
    assert not obs.es_particular


def test_dec239_un_obligatorio_anterior_del_contrato_gana():
    """productUrl y category van antes que seller en la arquitectura §8."""
    datos = {**_particular(), "seller": "comercio"}
    del datos["category"]
    assert _rechazo(leer_observacion, datos).motivo == _motivo("category")


def test_dec239_la_incoherencia_va_antes_que_un_obligatorio_posterior():
    datos = {**_particular(), "seller": "comercio"}
    del datos["extractedAt"]
    del datos["pickupLocation"]
    assert _rechazo(leer_observacion, datos).motivo == _motivo("seller")


def test_dec239_sin_literal_nuevo():
    """El catálogo de motivos sigue siendo el de REQ §3.2 y design.md §6 (copiado a mano)."""
    assert {m.value for m in MotivoRechazo} == {
        "TIPO DE REGISTRO DESCONOCIDO",
        "CAMPO OBLIGATORIO FALTANTE",
        "PRECIO INVÁLIDO",
        "DOMINIO NO AUTORIZADO",
        "CIUDAD NO CONFIGURADA",
    }


# --- DEC-240: zona horaria ------------------------------------------------------------


def _visita(visitado):
    return {**_captura("store_visit"), "visitedAt": visitado}


@pytest.mark.parametrize(
    ("texto", "utc"),
    [
        ("2026-11-18T10:00:00", dt.datetime(2026, 11, 18, 18, 0, tzinfo=_UTC)),  # PST −8
        ("2026-11-18 10:00", dt.datetime(2026, 11, 18, 18, 0, tzinfo=_UTC)),
        ("2026-07-01T10:00:00", dt.datetime(2026, 7, 1, 17, 0, tzinfo=_UTC)),  # PDT −7
        ("2026-03-08T01:59:00", dt.datetime(2026, 3, 8, 9, 59, tzinfo=_UTC)),  # antes, −8
        ("2026-03-08T03:00:00", dt.datetime(2026, 3, 8, 10, 0, tzinfo=_UTC)),  # después, −7
        ("2026-11-01T00:59:00", dt.datetime(2026, 11, 1, 7, 59, tzinfo=_UTC)),  # −7
        ("2026-11-01T02:00:00", dt.datetime(2026, 11, 1, 10, 0, tzinfo=_UTC)),  # −8
    ],
)
def test_dec240_visited_at_sin_desfase_en_tijuana(texto, utc):
    visita = leer_captura("store_visit", _visita(texto), zona="America/Tijuana")
    assert visita.visited_at.astimezone(_UTC) == utc


def test_dec240_hora_ambigua_toma_la_primera():
    """2026-11-01 01:30 ocurre dos veces; la primera es PDT (−7) = 08:30 UTC."""
    visita = leer_captura("store_visit", _visita("2026-11-01T01:30:00"), zona="America/Tijuana")
    assert visita.visited_at.astimezone(_UTC) == dt.datetime(2026, 11, 1, 8, 30, tzinfo=_UTC)


def test_dec240_hora_inexistente_toma_el_desfase_anterior():
    """2026-03-08 02:30 no existe en Tijuana; con el desfase anterior (−8) = 10:30 UTC."""
    visita = leer_captura("store_visit", _visita("2026-03-08T02:30:00"), zona="America/Tijuana")
    assert visita.visited_at.astimezone(_UTC) == dt.datetime(2026, 3, 8, 10, 30, tzinfo=_UTC)


def test_dec240_la_zona_no_esta_fija_en_el_codigo():
    visita = leer_captura("store_visit", _visita("2026-11-18T10:00:00"), zona="Asia/Tokyo")
    assert visita.visited_at.astimezone(_UTC) == dt.datetime(2026, 11, 18, 1, 0, tzinfo=_UTC)
    con_tzinfo = leer_captura(
        "store_visit", _visita("2026-11-18T10:00:00"), zona=ZoneInfo("America/Tijuana")
    )
    assert con_tzinfo.visited_at.utcoffset() == dt.timedelta(hours=-8)


def test_dec240_con_desfase_conserva_el_suyo_aunque_haya_zona():
    visita = leer_captura(
        "store_visit", _visita("2026-11-18T10:00:00+02:00"), zona="America/Tijuana"
    )
    assert visita.visited_at.utcoffset() == dt.timedelta(hours=2)


@pytest.mark.parametrize("texto", ["2026-11-18T10:00:00", "2026-11-18 10:00"])
def test_dec240_sin_zona_se_rechaza(texto):
    error = _rechazo(leer_captura, "store_visit", _visita(texto))
    assert error.motivo == _motivo("visitedAt")


@pytest.mark.parametrize("texto", ["2026-11-18", "18/11/2026 10:00", "ayer"])
def test_dec240_no_es_fecha_y_hora_se_rechaza_con_zona(texto):
    error = _rechazo(leer_captura, "store_visit", _visita(texto), zona="America/Tijuana")
    assert error.motivo == _motivo("visitedAt")


def test_dec240_observacion_sin_desfase_se_rechaza():
    datos = {**_comercio(), "extractedAt": "2026-11-16T18:00:00"}
    assert _rechazo(leer_observacion, datos).motivo == _motivo("extractedAt")


def test_dec240_la_zona_no_toca_las_fechas_sin_hora():
    comparable = leer_captura("local_comparable", _captura("local_comparable"), zona="Asia/Tokyo")
    assert comparable.date == dt.date(2026, 11, 18)


# --- DEC-241: acceptedConditions opcional ---------------------------------------------


@pytest.mark.parametrize(
    "valor", ["ausente", None, [], "", ()], ids=["ausente", "null", "lista", "texto", "tupla"]
)
def test_dec241_sin_accepted_conditions_vale_new(valor):
    datos = _captura("client_request")
    if valor == "ausente":
        del datos["acceptedConditions"]
    else:
        datos["acceptedConditions"] = valor
    solicitud = leer_captura("client_request", datos)
    assert [str(c) for c in solicitud.accepted_conditions] == ["new"]


def test_dec241_otros_estados_se_conservan():
    datos = {**_captura("client_request"), "acceptedConditions": ["open_box", "used"]}
    solicitud = leer_captura("client_request", datos)
    assert [str(c) for c in solicitud.accepted_conditions] == ["open_box", "used"]


@pytest.mark.parametrize("valor", [["nuevo"], ["new", "otro"], "new"])
def test_dec241_codigo_no_valido_cuenta_como_faltante(valor):
    datos = {**_captura("client_request"), "acceptedConditions": valor}
    error = _rechazo(leer_captura, "client_request", datos)
    assert error.motivo == _motivo("acceptedConditions")


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("quantity", True), ("quantity", "x"), ("acceptedConditions", ["alias-sintetico-z9"])],
)
def test_alias_fuera_de_los_nuevos_caminos_de_rechazo(campo, valor, caplog):
    datos = {**_captura("client_request"), campo: valor}
    with caplog.at_level(logging.DEBUG):
        error = _rechazo(leer_captura, "client_request", datos, zona="America/Tijuana")
    traza = "".join(traceback.format_exception(error))
    for texto in (str(error), repr(error), error.motivo, traza, caplog.text):
        assert "alias-sintetico-z9" not in texto


def test_texto_del_particular_fuera_de_los_errores_de_coherencia(caplog):
    datos = {**_particular(), "seller": "comercio"}
    with caplog.at_level(logging.DEBUG):
        error = _rechazo(leer_observacion, datos)
    traza = "".join(traceback.format_exception(error))
    for texto in (str(error), traza, caplog.text):
        assert "555 000 0000" not in texto
        assert "texto del vendedor" not in texto
