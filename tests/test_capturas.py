"""Pruebas unitarias de oip.entradas.capturas (CMP-06, CTR-04; design.md §6 y §12; T03 3.2).

Fixtures sintéticos. Enteros y booleanos estrictos (DEC-238): el texto de un CSV lo convierte
el cargador (T08), no los esquemas.
"""

import copy
import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from oip.catalogos import Canal, Categoria, Condicion, DemandaLocal, TipoRegistro
from oip.entradas.capturas import (
    CONDICIONES_POR_DEFECTO,
    ESQUEMAS_CAPTURA,
    CapturaMsrp,
    ComparableLocal,
    DemandaLocalCapturada,
    EstimadoLocal,
    Modalidad,
    Moneda,
    RegistroInvalido,
    ResultadoReal,
    ResultadoVisita,
    SolicitudCliente,
    VisitaTienda,
    leer_captura,
    motivo_de_rechazo,
)

ALIAS = "Cliente-Zeta-7781"
UUID_EVAL = "4f1a7f7e-2b1c-4c5d-9e8f-0a1b2c3d4e5f"

VALIDAS = {
    "local_comparable": {
        "brand": "DEWALT",
        "model": "DCF840",
        "condition": "used",
        "askingPrice": "120.00",
        "currency": "USD",
        "city": "san_diego",
        "date": "2026-11-15",
        "sold": False,
    },
    "local_estimate": {"gtin": "036000291452", "price": "95.00", "date": "2026-11-15"},
    "msrp": {
        "brand": "DEWALT",
        "model": "DCF840",
        "value": "149.00",
        "source": "fabricante",
        "date": "2026-11-10",
    },
    "local_demand": {"category": "beauty", "level": "medium", "date": "2026-11-15"},
    "store_visit": {
        "storeCode": "t-0123",
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
        "clientAlias": ALIAS,
        "items": ["DCF840", "036000291452"],
        "quantity": 1,
        "acceptedConditions": ["new"],
        "modality": "link_only",
        "postalCode": "22000",
        "date": "2026-11-18",
    },
}

#: Obligatorios de CTR-04 que siempre deben venir, en su orden (sin el producto).
OBLIGATORIOS = {
    "local_comparable": ("condition", "askingPrice", "currency", "city", "date", "sold"),
    "local_estimate": ("price", "date"),
    "msrp": ("value", "source", "date"),
    "local_demand": ("category", "level", "date"),
    "store_visit": ("storeCode", "result", "visitedAt"),
    "actual_result": (
        "evaluationId",
        "channel",
        "units",
        "purchasePrice",
        "salePrice",
        "actualCosts",
        "purchasedOn",
        "soldOn",
    ),
    "client_request": ("clientAlias", "items", "quantity", "modality", "date"),
}

CON_PRODUCTO = ("local_comparable", "local_estimate", "msrp")


def _sin(datos: dict, *campos: str) -> dict:
    copia = copy.deepcopy(datos)
    for campo in campos:
        copia.pop(campo, None)
    return copia


def _motivo(tipo: str, datos: dict) -> str:
    with pytest.raises(RegistroInvalido) as error:
        leer_captura(tipo, datos)
    return error.value.motivo


# --- Catálogo de esquemas -------------------------------------------------------------


def test_hay_un_esquema_por_cada_captura_que_no_es_observacion():
    assert set(ESQUEMAS_CAPTURA) == set(TipoRegistro) - {TipoRegistro.OBSERVATION}
    assert len(ESQUEMAS_CAPTURA) == 7


@pytest.mark.parametrize("tipo", ["coupon", "observation", "", None, "LOCAL_COMPARABLE"])
def test_tipo_desconocido(tipo):
    assert _motivo(tipo, {}) == "TIPO DE REGISTRO DESCONOCIDO"


@pytest.mark.parametrize("tipo", sorted(VALIDAS))
def test_cada_captura_valida_carga(tipo):
    captura = leer_captura(tipo, VALIDAS[tipo])
    assert isinstance(captura, ESQUEMAS_CAPTURA[tipo])


@pytest.mark.parametrize("tipo", sorted(VALIDAS))
def test_las_capturas_son_inmutables(tipo):
    captura = leer_captura(tipo, VALIDAS[tipo])
    campo = next(iter(type(captura).model_fields))
    with pytest.raises(ValidationError):
        setattr(captura, campo, None)


# --- Obligatorios ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tipo", "campo"), [(t, c) for t, campos in OBLIGATORIOS.items() for c in campos]
)
def test_cada_obligatorio_faltante_da_su_motivo_con_el_nombre_del_archivo(tipo, campo):
    assert _motivo(tipo, _sin(VALIDAS[tipo], campo)) == f"CAMPO OBLIGATORIO FALTANTE ({campo})"
    vacio = {**VALIDAS[tipo], campo: ""}
    assert _motivo(tipo, vacio) == f"CAMPO OBLIGATORIO FALTANTE ({campo})"
    nulo = {**VALIDAS[tipo], campo: None}
    assert _motivo(tipo, nulo) == f"CAMPO OBLIGATORIO FALTANTE ({campo})"


@pytest.mark.parametrize("tipo", sorted(OBLIGATORIOS))
def test_con_todos_los_obligatorios_faltantes_el_motivo_es_el_primero(tipo):
    datos = _sin(VALIDAS[tipo], *OBLIGATORIOS[tipo])
    esperado = "gtin" if tipo in CON_PRODUCTO else OBLIGATORIOS[tipo][0]
    if tipo in CON_PRODUCTO:
        datos = _sin(datos, "gtin", "brand", "model")
    assert _motivo(tipo, datos) == f"CAMPO OBLIGATORIO FALTANTE ({esperado})"


@pytest.mark.parametrize("tipo", sorted(OBLIGATORIOS))
def test_dos_faltantes_dan_el_primero_del_orden_de_ctr04(tipo):
    primero, *resto = OBLIGATORIOS[tipo]
    datos = _sin(VALIDAS[tipo], resto[-1], primero)
    assert _motivo(tipo, datos) == f"CAMPO OBLIGATORIO FALTANTE ({primero})"


def test_b34_b_comparable_sin_estado():
    assert _motivo("local_comparable", _sin(VALIDAS["local_comparable"], "condition")) == (
        "CAMPO OBLIGATORIO FALTANTE (condition)"
    )


# --- Producto: gtin, o brand y model --------------------------------------------------


@pytest.mark.parametrize("tipo", CON_PRODUCTO)
@pytest.mark.parametrize(
    ("producto", "esperado"),
    [
        ({}, "gtin"),
        ({"brand": "DEWALT"}, "model"),
        ({"model": "DCF840"}, "brand"),
        ({"gtin": "", "brand": " ", "model": None}, "gtin"),
    ],
)
def test_producto_faltante(tipo, producto, esperado):
    datos = {**_sin(VALIDAS[tipo], "gtin", "brand", "model"), **producto}
    assert _motivo(tipo, datos) == f"CAMPO OBLIGATORIO FALTANTE ({esperado})"


@pytest.mark.parametrize("tipo", CON_PRODUCTO)
@pytest.mark.parametrize(
    "producto",
    [{"gtin": "036000291452"}, {"brand": "DEWALT", "model": "DCF840"}, {"gtin": "1", "brand": "X"}],
)
def test_producto_completo(tipo, producto):
    datos = {**_sin(VALIDAS[tipo], "gtin", "brand", "model"), **producto}
    assert leer_captura(tipo, datos) is not None


@pytest.mark.parametrize("tipo", CON_PRODUCTO)
def test_el_producto_va_antes_que_los_demas_obligatorios(tipo):
    datos = _sin(VALIDAS[tipo], "gtin", "brand", "model", *OBLIGATORIOS[tipo][1:])
    datos["brand"] = "DEWALT"
    assert _motivo(tipo, datos) == "CAMPO OBLIGATORIO FALTANTE (model)"


def test_store_visit_con_oportunidad_y_sin_producto():
    datos = {**_sin(VALIDAS["store_visit"], "gtin"), "evaluationId": UUID_EVAL}
    visita = leer_captura("store_visit", datos)
    assert visita.evaluation_id == UUID(UUID_EVAL)
    assert visita.result is ResultadoVisita.FOUND


def test_store_visit_sin_producto_ni_oportunidad():
    datos = _sin(VALIDAS["store_visit"], "gtin")
    assert _motivo("store_visit", datos) == "CAMPO OBLIGATORIO FALTANTE (gtin)"
    datos["brand"] = "DEWALT"
    assert _motivo("store_visit", datos) == "CAMPO OBLIGATORIO FALTANTE (model)"
    assert _motivo("store_visit", _sin(datos, "storeCode")) == (
        "CAMPO OBLIGATORIO FALTANTE (storeCode)"
    )


@pytest.mark.parametrize(
    ("tipo", "campo", "valor"),
    [
        ("store_visit", "evaluationId", "no-es-uuid"),
        ("store_visit", "result", "encontrado"),
        ("store_visit", "visitedAt", "2026-11-16T19:30:00"),  # sin zona horaria
        ("local_demand", "category", "perfumes"),
        ("local_demand", "level", "media"),
        ("local_comparable", "condition", "usado"),
        ("local_comparable", "currency", "EUR"),
        ("local_comparable", "date", "15/11/2026"),
        ("local_comparable", "sold", "tal vez"),
        ("local_comparable", "sold", "true"),  # DEC-238: el texto lo convierte T08
        ("local_comparable", "sold", 0),
        ("local_comparable", "sold", 1),
        ("local_estimate", "condition", "nuevo"),
        ("actual_result", "channel", "ebay"),
        ("actual_result", "units", "dos"),
        ("actual_result", "units", "2"),  # DEC-238
        ("actual_result", "units", True),
        ("actual_result", "units", Decimal("2")),
        ("client_request", "modality", "delivery"),
        ("client_request", "quantity", 0),
        ("client_request", "quantity", True),  # DEC-238: true no es 1
        ("client_request", "quantity", "3"),
        ("client_request", "items", []),
        ("client_request", "items", ["a", "b", "c", "d"]),
        ("client_request", "items", ["a", " "]),
        ("client_request", "acceptedConditions", ["new", "nuevo"]),
        ("client_request", "acceptedConditions", "new"),
    ],
)
def test_valor_no_valido_o_fuera_de_la_tabla_cuenta_como_faltante(tipo, campo, valor):
    datos = {**VALIDAS[tipo], campo: valor}
    assert _motivo(tipo, datos) == f"CAMPO OBLIGATORIO FALTANTE ({campo})"


@pytest.mark.parametrize(
    ("tipo", "campo", "valor"),
    [
        ("local_estimate", "price", 95.0),  # float: nunca se acepta
        ("msrp", "value", "ciento"),
        ("actual_result", "salePrice", 75.0),
    ],
)
def test_precio_que_no_es_un_numero_da_precio_invalido(tipo, campo, valor):
    # DEC-276: los cinco precios de las capturas dan PRECIO INVÁLIDO, no campo faltante.
    captura = leer_captura(tipo, {**VALIDAS[tipo], campo: valor})
    assert captura.precio_invalido is True
    assert motivo_de_rechazo(captura) == "PRECIO INVÁLIDO"


# --- local_comparable: moneda, tipo de cambio y precio --------------------------------


def test_comparable_en_usd():
    comparable = leer_captura("local_comparable", VALIDAS["local_comparable"])
    assert isinstance(comparable, ComparableLocal)
    assert comparable.currency is Moneda.USD
    assert comparable.condition is Condicion.USED
    assert comparable.price_usd == Decimal("120.00")
    assert comparable.sold is False
    assert comparable.date == date(2026, 11, 15)
    assert not comparable.precio_invalido


def test_comparable_en_mxn_se_convierte_sin_redondear():
    datos = {
        **VALIDAS["local_comparable"],
        "askingPrice": "2000",
        "currency": "MXN",
        "exchangeRate": "17.3",
    }
    comparable = leer_captura("local_comparable", datos)
    esperado = Decimal("2000") / Decimal("17.3")
    assert comparable.price_usd == esperado
    assert comparable.price_usd != Decimal("115.61")
    assert len(str(comparable.price_usd).split(".")[1]) > 2
    assert type(comparable.price_usd) is Decimal


def test_comparable_en_mxn_exacto():
    datos = {
        **VALIDAS["local_comparable"],
        "askingPrice": "2175.00",
        "currency": "MXN",
        "exchangeRate": "17.40",
    }
    assert leer_captura("local_comparable", datos).price_usd == Decimal("125")


def test_b34_a_comparable_en_mxn_sin_tipo_de_cambio():
    datos = {**VALIDAS["local_comparable"], "currency": "MXN"}
    assert _motivo("local_comparable", datos) == "CAMPO OBLIGATORIO FALTANTE (exchangeRate)"
    datos["exchangeRate"] = ""
    assert _motivo("local_comparable", datos) == "CAMPO OBLIGATORIO FALTANTE (exchangeRate)"


def test_tipo_de_cambio_va_despues_de_currency_y_antes_de_city():
    datos = _sin({**VALIDAS["local_comparable"], "currency": "MXN"}, "city")
    assert _motivo("local_comparable", datos) == "CAMPO OBLIGATORIO FALTANTE (exchangeRate)"
    datos = _sin({**VALIDAS["local_comparable"], "currency": "MXN"}, "askingPrice")
    assert _motivo("local_comparable", datos) == "CAMPO OBLIGATORIO FALTANTE (askingPrice)"


@pytest.mark.parametrize("tasa", ["0", "-17.3", "abc"])
def test_tipo_de_cambio_no_valido(tasa):
    datos = {**VALIDAS["local_comparable"], "currency": "MXN", "exchangeRate": tasa}
    assert _motivo("local_comparable", datos) == "CAMPO OBLIGATORIO FALTANTE (exchangeRate)"


def test_en_usd_el_tipo_de_cambio_no_es_obligatorio():
    comparable = leer_captura("local_comparable", VALIDAS["local_comparable"])
    assert comparable.exchange_rate is None


@pytest.mark.parametrize("precio", ["0", "0.00", "-5", "abc"])
def test_precio_pedido_no_positivo_se_marca_para_precio_invalido(precio):
    comparable = leer_captura(
        "local_comparable", {**VALIDAS["local_comparable"], "askingPrice": precio}
    )
    assert comparable.precio_invalido
    assert comparable.price_usd is None


@pytest.mark.parametrize("vendido", [True, False])
def test_sold_es_un_booleano_estricto(vendido):
    datos = {**VALIDAS["local_comparable"], "sold": vendido}
    assert leer_captura("local_comparable", datos).sold is vendido


# --- Demás capturas -------------------------------------------------------------------


def test_estimado_local_sin_y_con_estado():
    sin_estado = leer_captura("local_estimate", VALIDAS["local_estimate"])
    assert isinstance(sin_estado, EstimadoLocal)
    assert sin_estado.condition is None
    assert sin_estado.price == Decimal("95.00")
    con_estado = leer_captura("local_estimate", {**VALIDAS["local_estimate"], "condition": "new"})
    assert con_estado.condition is Condicion.NEW


def test_msrp():
    msrp = leer_captura("msrp", VALIDAS["msrp"])
    assert isinstance(msrp, CapturaMsrp)
    assert msrp.value == Decimal("149.00")
    assert msrp.source == "fabricante"


def test_demanda_local_de_b34_a():
    demanda = leer_captura("local_demand", VALIDAS["local_demand"])
    assert isinstance(demanda, DemandaLocalCapturada)
    assert demanda.category is Categoria.BEAUTY
    assert demanda.level is DemandaLocal.MEDIUM


def test_visita_a_tienda():
    visita = leer_captura("store_visit", VALIDAS["store_visit"])
    assert isinstance(visita, VisitaTienda)
    assert visita.visited_at.utcoffset().total_seconds() == 0


# --- Fecha y hora sin desfase en las capturas (DEC-240) -------------------------------

TIJUANA = "America/Tijuana"  # general.timezone de tests/fixtures/config/base.yaml


@pytest.mark.parametrize(
    ("texto", "desfase"),
    [
        ("2026-11-16T19:30:00", -8),  # invierno (PST)
        ("2026-07-16T19:30:00", -7),  # verano (PDT)
        ("2026-11-16 19:30", -8),
    ],
)
def test_visited_at_sin_desfase_se_toma_en_la_zona_de_la_configuracion(texto, desfase):
    datos = {**VALIDAS["store_visit"], "visitedAt": texto}
    visita = leer_captura("store_visit", datos, zona=TIJUANA)
    assert visita.visited_at.utcoffset() == timedelta(hours=desfase)
    assert visita.visited_at.replace(tzinfo=None) == datetime.fromisoformat(texto)


def test_la_zona_tambien_se_acepta_como_tzinfo():
    datos = {**VALIDAS["store_visit"], "visitedAt": "2026-11-16T19:30:00"}
    visita = leer_captura("store_visit", datos, zona=ZoneInfo(TIJUANA))
    assert visita.visited_at.utcoffset() == timedelta(hours=-8)


def test_visited_at_como_datetime_sin_zona_tambien_se_localiza():
    datos = {**VALIDAS["store_visit"], "visitedAt": datetime.fromisoformat("2026-11-16T19:30")}
    visita = leer_captura("store_visit", datos, zona=TIJUANA)
    assert visita.visited_at.utcoffset() == timedelta(hours=-8)


def test_la_zona_sale_del_parametro_no_del_codigo():
    datos = {**VALIDAS["store_visit"], "visitedAt": "2026-11-16T19:30:00"}
    visita = leer_captura("store_visit", datos, zona="America/Mexico_City")
    assert visita.visited_at.utcoffset() == timedelta(hours=-6)


@pytest.mark.parametrize("texto", ["2026-11-16T19:30:00Z", "2026-11-16T19:30:00-05:00"])
def test_visited_at_con_desfase_conserva_el_suyo(texto):
    datos = {**VALIDAS["store_visit"], "visitedAt": texto}
    visita = leer_captura("store_visit", datos, zona=TIJUANA)
    assert visita.visited_at == datetime.fromisoformat(texto)


@pytest.mark.parametrize("texto", ["2026-11-16", "ayer", "16/11/2026 19:30"])
def test_visited_at_sin_hora_o_no_iso_se_rechaza_aun_con_zona(texto):
    datos = {**VALIDAS["store_visit"], "visitedAt": texto}
    with pytest.raises(RegistroInvalido) as error:
        leer_captura("store_visit", datos, zona=TIJUANA)
    assert error.value.motivo == "CAMPO OBLIGATORIO FALTANTE (visitedAt)"


def test_visited_at_sin_desfase_y_sin_zona_se_rechaza():
    datos = {**VALIDAS["store_visit"], "visitedAt": "2026-11-16T19:30:00"}
    assert _motivo("store_visit", datos) == "CAMPO OBLIGATORIO FALTANTE (visitedAt)"


def test_resultado_real():
    real = leer_captura("actual_result", VALIDAS["actual_result"])
    assert isinstance(real, ResultadoReal)
    assert real.channel is Canal.LOCAL
    assert real.units == 2
    assert (real.purchase_price, real.sale_price, real.actual_costs) == (
        Decimal("29.00"),
        Decimal("75.00"),
        Decimal("9.50"),
    )
    assert real.sold_on == date(2026, 11, 20)


def test_montos_de_las_capturas_son_decimal():
    real = leer_captura("actual_result", VALIDAS["actual_result"])
    for valor in (real.purchase_price, real.sale_price, real.actual_costs):
        assert type(valor) is Decimal


# --- client_request: alias sin notas (RNF-11) -----------------------------------------


def test_solicitud_de_cliente():
    solicitud = leer_captura("client_request", VALIDAS["client_request"])
    assert isinstance(solicitud, SolicitudCliente)
    assert solicitud.client_alias == ALIAS
    assert solicitud.items == ("DCF840", "036000291452")
    assert solicitud.accepted_conditions == (Condicion.NEW,)
    assert solicitud.modality is Modalidad.LINK_ONLY


@pytest.mark.parametrize(
    "cambio",
    [None, {"acceptedConditions": None}, {"acceptedConditions": []}, {"acceptedConditions": ""}],
    ids=["ausente", "null", "lista-vacia", "texto-vacio"],
)
def test_accepted_conditions_ausente_o_vacio_vale_solo_nuevo(cambio):
    """RN-011 punto 2 y REQ §3.4 punto 1: por defecto, solo nuevo (DEC-241)."""
    datos = _sin(VALIDAS["client_request"], "acceptedConditions")
    datos.update(cambio or {})
    solicitud = leer_captura("client_request", datos)
    assert solicitud.accepted_conditions == CONDICIONES_POR_DEFECTO == (Condicion.NEW,)


def test_accepted_conditions_con_otros_estados():
    datos = {**VALIDAS["client_request"], "acceptedConditions": ["new", "used"]}
    solicitud = leer_captura("client_request", datos)
    assert solicitud.accepted_conditions == (Condicion.NEW, Condicion.USED)


def test_accepted_conditions_no_valido_va_despues_de_los_obligatorios():
    datos = _sin({**VALIDAS["client_request"], "acceptedConditions": ["nuevo"]}, "date")
    assert _motivo("client_request", datos) == "CAMPO OBLIGATORIO FALTANTE (date)"


def test_client_request_no_tiene_campo_de_notas():
    campos = {info.alias or n for n, info in SolicitudCliente.model_fields.items()}
    assert campos == {
        "clientAlias",
        "items",
        "quantity",
        "acceptedConditions",
        "modality",
        "postalCode",
        "date",
    }
    datos = {
        **VALIDAS["client_request"],
        "notes": "Llamar al 555-0100",
        "notas": "Vive en Calle Falsa 123",
        "phone": "555-0100",
    }
    solicitud = leer_captura("client_request", datos)
    volcado = json.dumps(solicitud.model_dump(mode="json", by_alias=True))
    for texto in ("notes", "notas", "phone", "555", "Calle Falsa"):
        assert texto not in volcado


def test_el_alias_no_sale_en_el_repr_ni_en_el_texto():
    solicitud = leer_captura("client_request", VALIDAS["client_request"])
    assert ALIAS not in repr(solicitud)
    assert ALIAS not in str(solicitud)


@pytest.mark.parametrize(
    "cambio",
    [
        {"items": []},
        {"quantity": "mucho"},
        {"modality": None},
        {"acceptedConditions": ["nuevo"]},
        {"date": "ayer"},
    ],
)
def test_el_alias_no_sale_en_el_motivo_ni_en_los_logs(cambio, caplog):
    caplog.set_level(logging.DEBUG)
    datos = {**VALIDAS["client_request"], **cambio}
    with pytest.raises(RegistroInvalido) as error:
        leer_captura("client_request", datos)
    assert ALIAS not in str(error.value)
    assert ALIAS not in repr(error.value)
    assert ALIAS not in error.value.motivo
    assert error.value.__cause__ is None or ALIAS not in str(error.value.__cause__)
    assert ALIAS not in caplog.text


def test_el_alias_mal_formado_no_sale_en_el_motivo():
    datos = {**VALIDAS["client_request"], "clientAlias": ["Cliente-Zeta-7781"]}
    with pytest.raises(RegistroInvalido) as error:
        leer_captura("client_request", datos)
    assert error.value.motivo == "CAMPO OBLIGATORIO FALTANTE (clientAlias)"
    assert ALIAS not in str(error.value)


# --- Campos desconocidos y recordType -------------------------------------------------


@pytest.mark.parametrize("tipo", sorted(VALIDAS))
def test_campos_desconocidos_se_descartan(tipo):
    datos = {**VALIDAS[tipo], "recordType": tipo, "comentario": "texto libre", "telefono": "555"}
    captura = leer_captura(tipo, datos)
    assert captura == leer_captura(tipo, VALIDAS[tipo])
    volcado = json.dumps(captura.model_dump(mode="json", by_alias=True))
    assert "recordType" not in volcado
    assert "comentario" not in volcado and "telefono" not in volcado


@pytest.mark.parametrize("esquema", list(ESQUEMAS_CAPTURA.values()))
def test_record_type_no_es_parte_de_ningun_esquema(esquema):
    campos = {info.alias or n for n, info in esquema.model_fields.items()}
    assert "recordType" not in campos


def test_la_captura_debe_ser_un_mapa():
    with pytest.raises(TypeError):
        leer_captura("local_demand", ["beauty", "medium"])  # type: ignore[arg-type]
