"""Pruebas unitarias de oip.entradas.contrato (CMP-05, CTR-01; design.md §6 y §12; T03 3.1).

Fixtures sintéticos: las URL son texto de example.com y ninguna prueba las abre.
"""

import copy
import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from oip.catalogos import (
    Categoria,
    Condicion,
    EstadoDisponibilidad,
    ModoCompra,
    Vendedor,
    motivo_campo_faltante,
)
from oip.entradas.contrato import (
    CAMPOS_PARTICULAR,
    OBLIGATORIOS_CONTRATO,
    OBLIGATORIOS_PARTICULAR,
    VERSIONES_ACEPTADAS,
    Observacion,
    RegistroInvalido,
    es_publicacion_de_particular,
    gtin_valido,
    leer_observacion,
)

# --- Datos sintéticos -----------------------------------------------------------------

COMERCIO = {
    "schemaVersion": "3.1",
    "crawlJobId": "8a1c6c1e-0000-4000-8000-000000000001",
    "idempotencyKey": "tienda|https://tienda.example.com/p/123|t-0123|2026-11-16T18:00",
    "retailerCode": "tienda",
    "storeCode": "t-0123",
    "sourceType": "clearance",
    "productUrl": "https://tienda.example.com/p/123",
    "title": "Atornillador de impacto",
    "brand": "MarcaX",
    "model": "MX-100",
    "gtin": "036000291452",
    "content": "tool only",
    "category": "tools",
    "weightKg": Decimal("4.0"),
    "dimsCm": None,
    "price": {"current": "29.00", "was": "129.00", "currency": "USD"},
    "seller": "comercio",
    "condition": "new",
    "availability": {
        "state": "in_stock",
        "text": "3 disponibles",
        "quantity": 3,
        "scope": "store",
        "addToCart": None,
    },
    "isClearance": True,
    "purchaseMode": "tienda",
    "taxLocation": "chula_vista",
    "shipping": {"toMeCost": "0.00", "days": None, "mode": "pickup"},
    "msrp": {"value": "149.00", "source": "fabricante", "date": "2026-11-10"},
    "amazonListing": None,
    "extractedAt": "2026-11-16T18:00:00Z",
    "extractionMethod": "playwright_jsonld",
    "blocked": False,
    "evidence": {"jsonld": True, "priceSelector": "..."},
}

PARTICULAR = {
    "schemaVersion": "3.1",
    "retailerCode": "particular",
    "productUrl": "https://mercado.example.com/item/abc",
    "brand": "DEWALT",
    "model": "DCF840",
    "category": "tools",
    "price": {"current": "70.00", "currency": "USD"},
    "seller": "particular",
    "condition": "used",
    "availability": {"state": "listed"},
    "purchaseMode": "particular",
    "pickupLocation": "san_diego",
    "extractedAt": "2026-11-18T17:00:00Z",
    "blocked": False,
}


def _sin(datos: dict, ruta: str) -> dict:
    """Copia de ``datos`` sin el campo ``ruta`` (con punto en los anidados)."""
    copia = copy.deepcopy(datos)
    *padres, hoja = ruta.split(".")
    actual = copia
    for parte in padres:
        actual = actual[parte]
    del actual[hoja]
    return copia


def _con(datos: dict, ruta: str, valor: object) -> dict:
    copia = copy.deepcopy(datos)
    *padres, hoja = ruta.split(".")
    actual = copia
    for parte in padres:
        actual = actual[parte]
    actual[hoja] = valor
    return copia


def _motivo(datos: dict) -> str:
    with pytest.raises(RegistroInvalido) as error:
        leer_observacion(datos)
    return error.value.motivo


# --- Observación válida ---------------------------------------------------------------


def test_observacion_de_comercio_valida_con_tipos_del_contrato():
    obs = leer_observacion(COMERCIO)
    assert isinstance(obs, Observacion)
    assert obs.schema_version == "3.1"
    assert obs.retailer_code == "tienda"
    assert obs.category is Categoria.TOOLS
    assert obs.seller is Vendedor.COMERCIO
    assert obs.condition is Condicion.NEW
    assert obs.purchase_mode is ModoCompra.TIENDA
    assert obs.availability.state is EstadoDisponibilidad.IN_STOCK
    assert obs.availability.quantity == 3
    assert obs.price.current == Decimal("29.00")
    assert obs.price.was == Decimal("129.00")
    assert obs.shipping.to_me_cost == Decimal("0.00")
    assert obs.msrp.value == Decimal("149.00")
    assert obs.weight_kg == Decimal("4.0")
    assert obs.extracted_at.utcoffset().total_seconds() == 0
    assert obs.title == "Atornillador de impacto"
    assert not obs.es_particular
    assert not obs.es_ficha_amazon
    assert not obs.precio_invalido
    assert obs.gtin_valido


def test_los_montos_son_decimal_y_nunca_float():
    obs = leer_observacion(COMERCIO)
    for valor in (obs.price.current, obs.price.was, obs.shipping.to_me_cost, obs.msrp.value):
        assert type(valor) is Decimal


def test_renglon_json_leido_con_parse_float_decimal():
    renglon = json.dumps(
        {**COMERCIO, "weightKg": None, "price": {"current": 29.5, "currency": "USD"}}
    )
    obs = leer_observacion(json.loads(renglon, parse_float=Decimal))
    assert obs.price.current == Decimal("29.5")
    assert not obs.precio_invalido


def test_ficha_de_amazon_sin_oferta_hoy():
    ficha = {
        **COMERCIO,
        "amazonListing": {
            "buyBoxPrice": None,
            "sellersNew": 4,
            "rankMain": 12000,
            "rankSub": 30,
            "reviews": 250,
            "boughtLastMonth": 100,
        },
    }
    obs = leer_observacion(ficha)
    assert obs.es_ficha_amazon
    assert obs.amazon_listing.buy_box_price is None
    assert obs.amazon_listing.rank_main == 12000


def test_ficha_de_amazon_con_precio_del_boton_de_compra():
    obs = leer_observacion({**COMERCIO, "amazonListing": {"buyBoxPrice": "99.00"}})
    assert obs.amazon_listing.buy_box_price == Decimal("99.00")


def test_la_observacion_es_inmutable():
    obs = leer_observacion(COMERCIO)
    with pytest.raises(ValidationError):
        obs.title = "otro"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        obs.price.current = Decimal("1.00")  # type: ignore[misc]


# --- Obligatorios del contrato --------------------------------------------------------


def test_obligatorios_en_el_orden_de_la_arquitectura():
    assert OBLIGATORIOS_CONTRATO == (
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
    )
    assert OBLIGATORIOS_PARTICULAR == ("pickupLocation", "brand", "model")


@pytest.mark.parametrize("campo", OBLIGATORIOS_CONTRATO)
def test_cada_obligatorio_faltante_da_su_motivo(campo):
    with pytest.raises(RegistroInvalido) as error:
        leer_observacion(_sin(COMERCIO, campo))
    assert error.value.motivo == f"CAMPO OBLIGATORIO FALTANTE ({campo})"
    assert error.value.campo == campo
    assert str(error.value) == error.value.motivo


@pytest.mark.parametrize("campo", OBLIGATORIOS_CONTRATO)
@pytest.mark.parametrize("vacio", [None, "", "   "])
def test_obligatorio_nulo_o_vacio_cuenta_como_faltante(campo, vacio):
    assert _motivo(_con(COMERCIO, campo, vacio)) == motivo_campo_faltante(campo)


def test_sin_category_da_el_motivo_de_b20_c():
    assert _motivo(_sin(COMERCIO, "category")) == "CAMPO OBLIGATORIO FALTANTE (category)"


def test_sin_el_objeto_price_se_cita_price_current():
    assert _motivo(_sin(COMERCIO, "price")) == "CAMPO OBLIGATORIO FALTANTE (price.current)"
    assert _motivo(_con(COMERCIO, "price", "29.00")) == (
        "CAMPO OBLIGATORIO FALTANTE (price.current)"
    )


@pytest.mark.parametrize(
    ("faltan", "esperado"),
    [
        (("blocked", "category"), "category"),
        (("price.current", "retailerCode"), "retailerCode"),
        (("extractedAt", "availability", "seller"), "seller"),
        (("purchaseMode", "title"), "title"),
        (tuple(reversed(OBLIGATORIOS_CONTRATO)), "retailerCode"),
    ],
)
def test_con_varios_faltantes_el_motivo_es_el_primero_del_orden(faltan, esperado):
    datos = COMERCIO
    for campo in faltan:
        datos = _sin(datos, campo)
    assert _motivo(datos) == motivo_campo_faltante(esperado)


# --- Códigos cerrados y valores no válidos (DEC-234 punto 2) --------------------------


@pytest.mark.parametrize(
    ("ruta", "valor"),
    [
        ("category", "foo"),
        ("category", "Tools"),
        ("seller", "vendedor"),
        ("purchaseMode", "domicilio"),
        ("condition", "nuevo"),
        ("availability.state", "disponible"),
    ],
)
def test_codigo_fuera_de_la_tabla_cerrada_cuenta_como_faltante(ruta, valor):
    assert _motivo(_con(COMERCIO, ruta, valor)) == motivo_campo_faltante(ruta)


def test_codigo_invalido_de_un_obligatorio_respeta_el_orden():
    datos = _con(_sin(COMERCIO, "blocked"), "category", "foo")
    assert _motivo(datos) == motivo_campo_faltante("category")


def test_un_opcional_no_valido_va_despues_de_los_obligatorios():
    datos = _con(_sin(COMERCIO, "blocked"), "condition", "nuevo")
    assert _motivo(datos) == motivo_campo_faltante("blocked")


@pytest.mark.parametrize(
    ("ruta", "valor"),
    [
        ("extractedAt", "2026-11-16T18:00:00"),  # sin zona horaria
        ("extractedAt", "ayer"),
        ("blocked", "quizá"),
        ("weightKg", 4.0),  # float: nunca se acepta
        ("price.was", 129.0),
        ("shipping.toMeCost", "gratis"),
        ("msrp.date", "10/11/2026"),
        ("availability.quantity", "tres"),
        ("amazonListing.buyBoxPrice", "NaN"),
    ],
)
def test_valor_no_valido_cita_el_campo_del_archivo(ruta, valor):
    base = {**COMERCIO, "amazonListing": {"buyBoxPrice": "99.00"}}
    assert _motivo(_con(base, ruta, valor)) == motivo_campo_faltante(ruta)


def test_el_motivo_no_trae_claves_ni_valores_del_registro():
    datos = _con(COMERCIO, "dimsCm", {"Llamar-al-555-0100": "mucho"})
    with pytest.raises(RegistroInvalido) as error:
        leer_observacion(datos)
    assert error.value.motivo == "CAMPO OBLIGATORIO FALTANTE (dimsCm)"
    assert "555" not in str(error.value)
    assert "mucho" not in str(error.value)


def test_el_registro_debe_ser_un_mapa():
    with pytest.raises(TypeError):
        leer_observacion(["no", "es", "un", "mapa"])  # type: ignore[arg-type]


# --- schemaVersion --------------------------------------------------------------------


def test_versiones_aceptadas():
    assert VERSIONES_ACEPTADAS == ("3.1", "3.0")


def test_schema_version_ausente_se_toma_31():
    assert leer_observacion(_sin(COMERCIO, "schemaVersion")).schema_version == "3.1"
    assert leer_observacion(_con(COMERCIO, "schemaVersion", None)).schema_version == "3.1"
    # CTR-03: celda vacía = campo ausente (D-1).
    assert leer_observacion(_con(COMERCIO, "schemaVersion", "")).schema_version == "3.1"
    assert leer_observacion(_con(COMERCIO, "schemaVersion", "  ")).schema_version == "3.1"


@pytest.mark.parametrize("version", ["3.1", "3.0"])
def test_schema_version_31_y_30_se_aceptan(version):
    assert leer_observacion(_con(COMERCIO, "schemaVersion", version)).schema_version == version


@pytest.mark.parametrize("version", ["2.0", "4.0", "3.2", "3", Decimal("3.1"), 3])
def test_otra_schema_version_se_rechaza(version):
    assert _motivo(_con(COMERCIO, "schemaVersion", version)) == (
        "CAMPO OBLIGATORIO FALTANTE (schemaVersion)"
    )


def test_schema_version_no_aceptada_va_antes_que_los_obligatorios():
    datos = _con(_sin(COMERCIO, "retailerCode"), "schemaVersion", "2.0")
    assert _motivo(datos) == "CAMPO OBLIGATORIO FALTANTE (schemaVersion)"


def test_en_30_listed_no_es_un_codigo_valido():
    datos = _con(COMERCIO, "schemaVersion", "3.0")
    datos = _con(datos, "availability.state", "listed")
    assert _motivo(datos) == "CAMPO OBLIGATORIO FALTANTE (availability.state)"
    datos31 = _con(COMERCIO, "availability.state", "listed")
    assert leer_observacion(datos31).availability.state is EstadoDisponibilidad.LISTED


def test_en_30_pickup_location_no_existe():
    obs = leer_observacion(_con(_con(COMERCIO, "schemaVersion", "3.0"), "pickupLocation", "x"))
    assert obs.pickup_location is None
    datos = _con(PARTICULAR, "schemaVersion", "3.0")
    assert _motivo(datos) == "CAMPO OBLIGATORIO FALTANTE (availability.state)"
    datos = _con(datos, "availability.state", "unconfirmed")
    assert _motivo(datos) == "CAMPO OBLIGATORIO FALTANTE (pickupLocation)"


# --- Publicación de un particular (DEC-227 b, DEC-212) --------------------------------


def test_publicacion_de_particular_valida():
    obs = leer_observacion(PARTICULAR)
    assert obs.es_particular
    assert obs.pickup_location == "san_diego"
    assert obs.availability.state is EstadoDisponibilidad.LISTED
    assert obs.condition is Condicion.USED


def test_title_del_particular_es_marca_mas_modelo_e_ignora_el_que_venga():
    obs = leer_observacion({**PARTICULAR, "title": "Lo vendo barato, pregunta por Ana"})
    assert obs.title == "DEWALT DCF840"
    sin_title = leer_observacion(PARTICULAR)
    assert sin_title.title == "DEWALT DCF840"
    con_espacios = leer_observacion({**PARTICULAR, "brand": "  DEWALT ", "model": " DCF840  "})
    assert con_espacios.title == "DEWALT DCF840"


@pytest.mark.parametrize("campo", OBLIGATORIOS_PARTICULAR)
def test_cada_obligatorio_del_particular_faltante_da_su_motivo(campo):
    assert _motivo(_sin(PARTICULAR, campo)) == f"CAMPO OBLIGATORIO FALTANTE ({campo})"
    assert _motivo(_con(PARTICULAR, campo, "")) == f"CAMPO OBLIGATORIO FALTANTE ({campo})"


def test_sin_model_da_el_motivo_de_b20_h_y_no_title():
    assert _motivo(_sin(PARTICULAR, "model")) == "CAMPO OBLIGATORIO FALTANTE (model)"


def test_sin_pickup_location_da_el_motivo_de_b20_f():
    assert _motivo(_sin(PARTICULAR, "pickupLocation")) == (
        "CAMPO OBLIGATORIO FALTANTE (pickupLocation)"
    )


def test_orden_obligatorios_del_particular():
    datos = _sin(_sin(PARTICULAR, "model"), "pickupLocation")
    assert _motivo(datos) == "CAMPO OBLIGATORIO FALTANTE (pickupLocation)"
    datos = _sin(_sin(PARTICULAR, "model"), "brand")
    assert _motivo(datos) == "CAMPO OBLIGATORIO FALTANTE (brand)"


def test_los_obligatorios_del_contrato_van_antes_que_los_del_particular():
    datos = _sin(_sin(PARTICULAR, "pickupLocation"), "extractedAt")
    assert _motivo(datos) == "CAMPO OBLIGATORIO FALTANTE (extractedAt)"
    datos = _con(_sin(PARTICULAR, "brand"), "category", "foo")
    assert _motivo(datos) == "CAMPO OBLIGATORIO FALTANTE (category)"


def test_una_observacion_de_comercio_no_exige_los_obligatorios_del_particular():
    datos = _sin(_sin(COMERCIO, "brand"), "model")
    obs = leer_observacion(datos)
    assert obs.pickup_location is None and obs.brand is None


@pytest.mark.parametrize("campo", ["seller", "retailerCode", "purchaseMode"])
def test_basta_un_campo_particular_para_aplicar_sus_reglas(campo):
    datos = {**COMERCIO, campo: "particular"}
    assert es_publicacion_de_particular(datos)


# --- Coherencia del particular (DEC-239) ----------------------------------------------


def test_campos_particular_en_el_orden_de_req_6():
    assert CAMPOS_PARTICULAR == ("retailerCode", "seller", "purchaseMode")


@pytest.mark.parametrize(
    ("cambios", "esperado"),
    [
        ({"retailerCode": "tienda"}, "retailerCode"),
        ({"seller": "comercio"}, "seller"),
        ({"purchaseMode": "envio"}, "purchaseMode"),
        ({"seller": "comercio", "purchaseMode": "envio"}, "seller"),
        ({"retailerCode": "tienda", "purchaseMode": "envio"}, "retailerCode"),
        ({"purchaseMode": "Particular"}, "purchaseMode"),
    ],
)
def test_si_uno_vale_particular_los_tres_deben_valerlo(cambios, esperado):
    assert _motivo({**PARTICULAR, **cambios}) == f"CAMPO OBLIGATORIO FALTANTE ({esperado})"


@pytest.mark.parametrize("campo", ["seller", "retailerCode", "purchaseMode"])
def test_un_comercio_con_un_solo_campo_particular_se_rechaza(campo):
    datos = {**COMERCIO, campo: "particular", "pickupLocation": "san_diego"}
    esperado = next(c for c in CAMPOS_PARTICULAR if c != campo)
    assert _motivo(datos) == f"CAMPO OBLIGATORIO FALTANTE ({esperado})"


def test_la_incoherencia_respeta_el_orden_del_contrato():
    # category va antes que seller en la arquitectura §8.
    datos = _sin({**PARTICULAR, "seller": "comercio"}, "category")
    assert _motivo(datos) == "CAMPO OBLIGATORIO FALTANTE (category)"
    # purchaseMode va antes que los obligatorios del particular.
    datos = _sin({**PARTICULAR, "purchaseMode": "envio"}, "pickupLocation")
    assert _motivo(datos) == "CAMPO OBLIGATORIO FALTANTE (purchaseMode)"


# --- Particular sin texto libre (DEC-236) ---------------------------------------------


def test_el_particular_descarta_availability_text_y_evidence():
    datos = {
        **PARTICULAR,
        "availability": {"state": "listed", "text": "Pregunta por Ana al 555-0100"},
        "evidence": {"nota": "Ana 555-0100"},
        "sourceType": "manual",
        "extractionMethod": "captura_jesus",
    }
    obs = leer_observacion(datos)
    assert obs.availability.text is None
    assert obs.evidence is None
    assert obs.source_type == "manual"
    assert obs.extraction_method == "captura_jesus"
    volcado = json.dumps(obs.model_dump(mode="json", by_alias=True))
    assert "555" not in volcado and "Ana" not in volcado


def test_el_particular_conserva_content_dec245():
    """``content`` no se descarta (DEC-245): RN-013 §4.1 confirma el producto con modelo +
    marca y el mismo contenido, y B18 lo da ("mismo contenido")."""
    obs = leer_observacion({**PARTICULAR, "content": "tool only"})
    assert obs.content == "tool only"


def test_un_comercio_conserva_availability_text_content_y_evidence():
    obs = leer_observacion(COMERCIO)
    assert obs.availability.text == "3 disponibles"
    assert obs.content == "tool only"
    assert obs.evidence == {"jsonld": True, "priceSelector": "..."}


# --- availability sin state (DEC-237) -------------------------------------------------


@pytest.mark.parametrize(
    "disponibilidad",
    [{}, {"text": "3 disponibles"}, {"state": ""}, {"state": None}, {"state": "  "}],
    ids=["vacio", "sin-state", "state-vacio", "state-null", "state-espacios"],
)
def test_availability_sin_state_cuenta_como_faltante(disponibilidad):
    datos = _con(COMERCIO, "availability", disponibilidad)
    assert _motivo(datos) == "CAMPO OBLIGATORIO FALTANTE (availability.state)"


def test_availability_state_va_en_el_lugar_de_availability():
    datos = _sin(_con(COMERCIO, "availability", {}), "purchaseMode")
    assert _motivo(datos) == "CAMPO OBLIGATORIO FALTANTE (availability.state)"
    datos = _sin(_con(COMERCIO, "availability", {}), "seller")
    assert _motivo(datos) == "CAMPO OBLIGATORIO FALTANTE (seller)"


def test_particular_con_availability_solo_con_texto_cuenta_como_faltante():
    datos = _con(PARTICULAR, "availability", {"text": "Llamar al 555-0100"})
    assert _motivo(datos) == "CAMPO OBLIGATORIO FALTANTE (availability.state)"


# --- Enteros y booleanos estrictos (DEC-238) ------------------------------------------


@pytest.mark.parametrize(
    ("ruta", "valor"),
    [
        ("availability.quantity", True),
        ("availability.quantity", "3"),
        ("availability.quantity", Decimal("3")),
        ("availability.addToCart", 1),
        ("availability.addToCart", "true"),
        ("blocked", "false"),
        ("blocked", 0),
        ("blocked", 1),
        ("isClearance", "true"),
        ("isClearance", 1),
        ("shipping.days", "2"),
        ("shipping.days", False),
        ("amazonListing.rankMain", True),
        ("amazonListing.sellersNew", "3"),
    ],
)
def test_enteros_y_booleanos_estrictos(ruta, valor):
    base = {**COMERCIO, "amazonListing": {"buyBoxPrice": "99.00"}}
    assert _motivo(_con(base, ruta, valor)) == motivo_campo_faltante(ruta)


def test_enteros_y_booleanos_del_json_se_aceptan():
    base = {**COMERCIO, "amazonListing": {"buyBoxPrice": "99.00", "rankMain": 1500}}
    datos = _con(_con(base, "availability.addToCart", True), "blocked", True)
    obs = leer_observacion(datos)
    assert obs.availability.quantity == 3 and obs.availability.add_to_cart is True
    assert obs.blocked is True and obs.amazon_listing.rank_main == 1500


def test_campos_desconocidos_se_descartan_tambien_en_el_particular():
    datos = {
        **PARTICULAR,
        "recordType": "observation",
        "description": "Llamar al 555-0100, pregunta por Ana",
        "sellerName": "Ana",
        "phone": "555-0100",
        "availability": {"state": "listed", "sellerNote": "solo efectivo"},
    }
    obs = leer_observacion(datos)
    volcado = json.dumps(obs.model_dump(mode="json", by_alias=True))
    for texto in ("recordType", "description", "sellerName", "phone", "555", "Ana", "sellerNote"):
        assert texto not in volcado
    assert not hasattr(obs, "description")


def test_record_type_no_es_parte_del_modelo():
    alias = {info.alias or nombre for nombre, info in Observacion.model_fields.items()}
    assert "recordType" not in alias
    assert "record_type" not in Observacion.model_fields
    assert leer_observacion({**COMERCIO, "recordType": "coupon"}) == leer_observacion(COMERCIO)


# --- GTIN con dígito verificador (RN-013) ---------------------------------------------


@pytest.mark.parametrize(
    "gtin",
    [
        "96385074",  # GTIN-8
        "036000291452",  # GTIN-12 (UPC-A)
        "4006381333931",  # GTIN-13
        "0123456789012",  # GTIN-13 del ejemplo de la arquitectura §8
        "10036000291459",  # GTIN-14
        " 036000291452 ",
    ],
)
def test_gtin_con_digito_verificador_valido(gtin):
    assert gtin_valido(gtin)


@pytest.mark.parametrize(
    "gtin",
    [
        "036000291453",  # dígito verificador incorrecto
        "4006381333932",
        "96385075",
        "12345",  # longitud
        "1234567890",
        "123456789012345",
        "03600029145A",
        "０３６０００２９１４５２",  # dígitos no ASCII
        "",
        None,
        36000291452,
    ],
)
def test_gtin_no_valido(gtin):
    assert not gtin_valido(gtin)


def test_gtin_invalido_no_rechaza_pero_no_confirma():
    obs = leer_observacion(_con(COMERCIO, "gtin", "036000291453"))
    assert obs.gtin == "036000291453"
    assert not obs.gtin_valido
    assert not leer_observacion(_sin(COMERCIO, "gtin")).gtin_valido


# --- price.current para PRECIO INVÁLIDO -----------------------------------------------


@pytest.mark.parametrize(
    "precio", ["29.00", "29.1", "29", "0.01", Decimal("29.00"), 29, "29.010", "1E+2"]
)
def test_precio_valido(precio):
    assert not leer_observacion(_con(COMERCIO, "price.current", precio)).precio_invalido


@pytest.mark.parametrize(
    "precio",
    ["0.00", "0", "-1.00", "29.001", "0.005", Decimal("29.999"), "abc", "NaN", "Infinity", 29.0],
)
def test_precio_invalido_se_marca_y_no_rechaza(precio):
    obs = leer_observacion(_con(COMERCIO, "price.current", precio))
    assert obs.precio_invalido


def test_precio_invalido_no_tapa_un_obligatorio_faltante():
    datos = _sin(_con(COMERCIO, "price.current", "0.00"), "category")
    assert _motivo(datos) == "CAMPO OBLIGATORIO FALTANTE (category)"
