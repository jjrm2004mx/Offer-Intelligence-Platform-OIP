"""Pruebas de T13: restricción en Amazon (S-09, S-10), ``MATERIAL PELIGROSO`` (S-07),
``COMPETENCIA MÁS BARATA`` (RN-002 §4.3, solo Amazon), confianza Baja con ``nivel_calculado``
(RN-007, RN-009 §4.2; DEC-224 a) y ``SIN ROTACIÓN`` (S-08), con los escenarios B4, B9 (base),
B21 y B25 y el empate del nivel del aviso (design.md §10 punto 6; S-33).

Fixtures sintéticos: comercios ficticios con dominios de example.com y las sucursales de
``config_tienda_prueba`` (T24); ninguna prueba abre una URL. Instante explícito, sin reloj ni
zona de la máquina. "Amazon" es el código de la ficha de Amazon de la configuración base, con
una URL de example.com que solo se lee como texto.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from config_tienda_prueba import (
    BASE,
    SUCURSAL_PRUEBA,
    TIENDA_PRUEBA,
    TIENDA_PRUEBA_2,
    con_sucursales_prueba,
)
from oip.catalogos import (
    CalidadPrecio,
    Canal,
    CausaCanalCerrado,
    Confianza,
    EstadoCanal,
    Marca,
    Nivel,
    Resultado,
)
from oip.configuracion import cargar_configuracion_texto
from oip.dinero import formatear_porcentaje
from oip.entradas.capturas import leer_captura
from oip.entradas.contrato import leer_observacion
from oip.evaluacion import canales, eleccion, motor, rentabilidad
from oip.evaluacion.contexto import ContextoEvaluacion, EvaluacionCanal, ObservacionRegistrada

D = Decimal

# --- Configuración ------------------------------------------------------------------------

_LISTAS_VACIAS = (
    "  amazon_restricted_brands: []\n"
    "  amazon_restricted_products: []\n"
    "  avoid_always: []\n"
    "  luxury_brands: []\n"
    "  hazmat_brands: []\n"
    "  hazmat_products: []\n"
)


def _config(*reemplazos: tuple[str, str]):
    texto = con_sucursales_prueba(BASE.read_text(encoding="utf-8"))
    for viejo, nuevo in reemplazos:
        assert texto.count(viejo) == 1, viejo
        texto = texto.replace(viejo, nuevo)
    return cargar_configuracion_texto(texto, origen="t13")


def _listas(
    *,
    marcas_restringidas: str = "[]",
    productos_restringidos: str = "[]",
    marcas_peligrosas: str = "[]",
    productos_peligrosos: str = "[]",
) -> tuple[str, str]:
    """Reemplazo de las listas de PAR-05 de base.yaml (las demás quedan vacías)."""
    return (
        _LISTAS_VACIAS,
        f"  amazon_restricted_brands: {marcas_restringidas}\n"
        f"  amazon_restricted_products: {productos_restringidos}\n"
        "  avoid_always: []\n"
        "  luxury_brands: []\n"
        f"  hazmat_brands: {marcas_peligrosas}\n"
        f"  hazmat_products: {productos_peligrosos}\n",
    )


#: Perfume de B4: material peligroso por producto (design.md, Open Questions punto 7: los
#: perfumes no son un código de ``category``; se configuran por producto o marca en PAR-05).
CONFIG_B4 = _config(_listas(productos_peligrosos="[{brand: MarcaPerfume, model: PF-1}]"))
CONFIG = _config()
C = CONFIG.contenido

ZONA = ZoneInfo("America/Tijuana")
INSTANTE = dt.datetime(2026, 10, 14, 13, 0, tzinfo=ZONA)  # fuera de la temporada de juguetes
PRODUCTO = UUID(int=1300)
PUB_OFERTA = UUID(int=1301)
PUB_AMAZON = UUID(int=1302)
PUB_OTRA = UUID(int=1303)  # tienda-prueba-2 (Walmart en B1 y B2; Target en B4)
PUB_TERCERA = UUID(int=1304)  # tienda-b (Target en B9)

_EXTRA = "  tienda-b: {chain: cadena-b, domains: [example.net], amazon_listing: false}\n"
CONFIG_B9 = cargar_configuracion_texto(
    con_sucursales_prueba(BASE.read_text(encoding="utf-8")).replace(
        "\nretailers:\n", "\nretailers:\n" + _EXTRA, 1
    ),
    origen="t13 b9",
)

_contador = iter(range(130_000, 130_000_000))
_URL = {
    TIENDA_PRUEBA: "https://tienda.example.com/p/13",
    TIENDA_PRUEBA_2: "https://otra.example.com/p/13",
    "tienda-b": "https://example.net/p/13",
    "amazon": "https://amazon.example.com/dp/T13",
}


def _momento(dias: int = 0, horas_antes: int = 0) -> dt.datetime:
    return INSTANTE + dt.timedelta(days=dias) - dt.timedelta(hours=horas_antes)


def _obs(
    precio: str,
    *,
    comercio: str,
    publicacion: UUID,
    momento: dt.datetime,
    producto: dict[str, str],
    **cambios,
) -> ObservacionRegistrada:
    datos = {
        "retailerCode": comercio,
        "productUrl": _URL[comercio],
        "category": "tools",
        "price": {"current": precio, "currency": "USD"},
        "seller": "comercio",
        "condition": "new",
        "availability": {"state": "in_stock_confirmed"},
        "purchaseMode": "envio",
        "extractedAt": momento.isoformat(),
        "blocked": False,
        **producto,
    }
    datos.update(cambios)
    return ObservacionRegistrada(
        leer_observacion(datos), UUID(int=next(_contador)), publicacion, PRODUCTO
    )


def _ficha(producto, buy_box: str | None, momento: dt.datetime, categoria: str, **listing):
    return _obs(
        "999.00",
        comercio="amazon",
        publicacion=PUB_AMAZON,
        momento=momento,
        producto=producto,
        category=categoria,
        amazonListing={"buyBoxPrice": buy_box, **listing},
    )


def _fichas(
    producto,
    *,
    hoy: str,
    minimo: str,
    rank: int | None,
    rank_antes: int | None,
    vendedores: int,
    vendidos: int | None,
    categoria: str = "tools",
):
    """Botón de compra ``hoy`` hoy (hace 2 h) y los 6 días anteriores; ranking ``rank`` los 7
    días que terminan hoy y ``rank_antes`` los 7 que terminan hace 30 días; mínimo de 60 días
    ``minimo`` (hace 20 días)."""
    hoy_listing = {"rankMain": rank, "sellersNew": vendedores}
    if vendidos is not None:
        hoy_listing["boughtLastMonth"] = vendidos
    fichas = [_ficha(producto, hoy, _momento(horas_antes=2), categoria, **hoy_listing)]
    fichas += [
        _ficha(producto, hoy, _momento(-d), categoria, rankMain=rank, sellersNew=vendedores)
        for d in range(1, 7)
    ]
    fichas += [
        _ficha(producto, None, _momento(-d), categoria, rankMain=rank_antes, sellersNew=vendedores)
        for d in range(30, 37)
    ]
    fichas.append(_ficha(producto, minimo, _momento(-20), categoria, sellersNew=vendedores))
    return fichas


def _contexto(oferta, historial, fichas, configuracion=CONFIG, **otros) -> ContextoEvaluacion:
    return ContextoEvaluacion(
        id_evaluacion=UUID(int=13),
        instante=INSTANTE,
        configuracion=configuracion,
        id_version_configuracion=1,
        oferta=oferta,
        historial=tuple(historial),
        fichas_amazon=tuple(fichas),
        **otros,
    )


def _canal(registro, canal: Canal) -> EvaluacionCanal:
    return next(c for c in registro.canales if c.canal is canal)


# --- B1 (base de B9 y B25) ----------------------------------------------------------------

_SIERRA = {"title": "Sierra circular de prueba", "brand": "MarcaP", "model": "SC-1"}


def _oferta_b1(**cambios) -> ObservacionRegistrada:
    """B1: tienda física en liquidación, herramientas, 4 kg, $29.00 con tachado $129.00,
    "3 disponibles" hace 2 h, tienda a 7.75%."""
    datos = {
        "storeCode": SUCURSAL_PRUEBA,
        "gtin": "036000291452",
        "weightKg": "4",
        "price": {"current": "29.00", "was": "129.00", "currency": "USD"},
        "availability": {"state": "in_stock", "quantity": 3},
        "isClearance": True,
        "purchaseMode": "tienda",
        "taxLocation": "tienda_prueba",
        **cambios,
    }
    return _obs(
        "29.00",
        comercio=TIENDA_PRUEBA,
        publicacion=PUB_OFERTA,
        momento=_momento(horas_antes=2),
        producto=_SIERRA,
        **datos,
    )


def _historial_b1(*extra: ObservacionRegistrada):
    """La segunda cadena: $124 hoy (hace 8 h) y hace 60 días (60 días de historial)."""
    return [
        _obs("124.00", comercio=TIENDA_PRUEBA_2, publicacion=PUB_OTRA, momento=_momento(-60),
             producto=_SIERRA),
        _obs("124.00", comercio=TIENDA_PRUEBA_2, publicacion=PUB_OTRA,
             momento=_momento(horas_antes=8), producto=_SIERRA),
        *extra,
    ]  # fmt: skip


def _fichas_b1(*, vendedores: int = 5, vendidos: int | None = 200):
    return _fichas(
        _SIERRA,
        hoy="119.00",
        minimo="109.00",
        rank=6000,
        rank_antes=6000,
        vendedores=vendedores,
        vendidos=vendidos,
    )


def _contexto_b1(historial=None, fichas=None, configuracion=CONFIG, **otros):
    return _contexto(
        _oferta_b1(),
        _historial_b1() if historial is None else historial,
        _fichas_b1() if fichas is None else fichas,
        configuracion,
        **otros,
    )


# --- B2 (base de B21) ---------------------------------------------------------------------

_TALADRO = {"title": "Taladro de prueba", "brand": "MarcaT", "model": "TD-2"}


def _oferta_b2(**cambios) -> ObservacionRegistrada:
    """B2: tienda física (no liquidación), herramientas, 2 kg, $79.00 con tachado $199.00,
    "4 disponibles" hace 2 h."""
    momento = cambios.pop("momento", _momento(horas_antes=2))
    datos = {
        "storeCode": SUCURSAL_PRUEBA,
        "gtin": "036000291469",
        "weightKg": "2",
        "price": {"current": "79.00", "was": "199.00", "currency": "USD"},
        "availability": {"state": "in_stock", "quantity": 4},
        "isClearance": False,
        "purchaseMode": "tienda",
        "taxLocation": "tienda_prueba",
        **cambios,
    }
    return _obs(
        "79.00",
        comercio=TIENDA_PRUEBA,
        publicacion=PUB_OFERTA,
        momento=momento,
        producto=_TALADRO,
        **datos,
    )


def _historial_b2():
    """Precio típico de la tienda $149 (la misma publicación, 8 observaciones en 6 días y 60
    días de historial); la segunda cadena a $152 hoy (hace 6 h)."""
    propia = [
        _obs("149.00", comercio=TIENDA_PRUEBA, publicacion=PUB_OFERTA, momento=_momento(-d),
             producto=_TALADRO, storeCode=SUCURSAL_PRUEBA, purchaseMode="tienda")
        for d in (1, 2, 3, 4, 5, 6, 6, 60)
    ]  # fmt: skip
    otra = _obs("152.00", comercio=TIENDA_PRUEBA_2, publicacion=PUB_OTRA,
                momento=_momento(horas_antes=6), producto=_TALADRO)  # fmt: skip
    return [*propia, otra]


def _comparable(producto, precio: str, ciudad: str = "san_diego"):
    datos = {
        "brand": producto["brand"],
        "model": producto["model"],
        "condition": "new",
        "askingPrice": precio,
        "currency": "USD",
        "city": ciudad,
        "date": "2026-10-10",
        "sold": False,
    }
    return leer_captura("local_comparable", datos, zona=ZONA)


def _estimado(producto, precio: str):
    datos = {
        "brand": producto["brand"],
        "model": producto["model"],
        "price": precio,
        "date": "2026-10-10",
    }
    return leer_captura("local_estimate", datos, zona=ZONA)


def _contexto_b2(oferta=None):
    return _contexto(
        _oferta_b2() if oferta is None else oferta,
        _historial_b2(),
        _fichas(
            _TALADRO,
            hoy="149.00",
            minimo="139.00",
            rank=8500,
            rank_antes=8000,
            vendedores=9,
            vendidos=300,
        ),
        comparables=tuple(_comparable(_TALADRO, p) for p in ("135", "139", "150")),
        estimados=(_estimado(_TALADRO, "129"),),
    )


# --- B4 -----------------------------------------------------------------------------------

_PERFUME = {"title": "Perfume de prueba", "brand": "MarcaPerfume", "model": "PF-1"}


def _oferta_b4(**cambios) -> ObservacionRegistrada:
    """B4: en línea (envío al PO Box, tasa de respaldo), belleza, 0.3 kg, vendido por el
    comercio, $27.00, "disponible confirmada"."""
    datos = {
        "gtin": "036000291476",
        "weightKg": "0.3",
        "category": "beauty",
        "price": {"current": "27.00", "currency": "USD"},
        **cambios,
    }
    return _obs(
        "27.00",
        comercio=TIENDA_PRUEBA,
        publicacion=PUB_OFERTA,
        momento=_momento(horas_antes=1),
        producto=_PERFUME,
        **datos,
    )


def _contexto_b4(oferta=None, configuracion=CONFIG_B4):
    """Precio habitual $90 (la segunda cadena, 8 observaciones en 6 días y 60 días de
    historial); hoy Amazon $88 y la segunda cadena $92; mínimo de 60 días en Amazon $80;
    estimado local $55; comparables locales $59 y $65."""
    historial = [
        _obs("90.00", comercio=TIENDA_PRUEBA_2, publicacion=PUB_OTRA, momento=_momento(-d),
             producto=_PERFUME, category="beauty")
        for d in (1, 2, 3, 4, 5, 6, 6, 60)
    ]  # fmt: skip
    historial.append(
        _obs("92.00", comercio=TIENDA_PRUEBA_2, publicacion=PUB_OTRA,
             momento=_momento(horas_antes=3), producto=_PERFUME, category="beauty")
    )  # fmt: skip
    # Ficha de Amazon: botón de compra $88 hoy; mínimo de 60 días $80 (hace 20 días).
    fichas = [
        _ficha(_PERFUME, "88.00", _momento(horas_antes=2), "beauty", rankMain=5000,
               sellersNew=4, boughtLastMonth=100),
        _ficha(_PERFUME, "80.00", _momento(-20), "beauty", sellersNew=4),
    ]  # fmt: skip
    return _contexto(
        _oferta_b4() if oferta is None else oferta,
        historial,
        fichas,
        configuracion,
        comparables=tuple(_comparable(_PERFUME, p) for p in ("59", "65")),
        estimados=(_estimado(_PERFUME, "55"),),
    )


@pytest.mark.scenario("B4")
def test_b4_perfume_restringido_venta_local_recomendable():
    registro = motor.evaluar(_contexto_b4())

    assert formatear_porcentaje(registro.descuento_real) == "70.0 %"
    assert registro.referencias.precio_habitual == D("90.00")
    assert registro.referencias.precio_mercado_hoy == D("88.00")
    assert registro.calidad_precio is CalidadPrecio.BUENA_OFERTA  # 27 ≤ 89.76
    assert registro.costo_compra == D("29.09")  # impuesto 27 × 7.75% = 2.0925 → 2.09

    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.CERRADO
    assert amazon.causas_cerrado == (CausaCanalCerrado.NO_VENDIBLE_EN_AMAZON,)
    assert CausaCanalCerrado.NO_VENDIBLE_EN_AMAZON.value in amazon.marcas
    assert Marca.MATERIAL_PELIGROSO.value in amazon.marcas
    # DEC-224 a: un canal cerrado no tiene nivel_calculado; solo el neto informativo.
    assert amazon.nivel_calculado is None and amazon.nivel is None
    assert amazon.margen_ajustado is None and amazon.unidades is None

    local = _canal(registro, Canal.LOCAL)
    assert local.estado is EstadoCanal.DISPONIBLE
    assert local.precio_venta == D("49.50")  # pedido $55 (techo $59) × 0.90
    assert local.margen_neto == D("10.91")
    assert formatear_porcentaje(local.margen_neto_pct) == "37.5 %"
    assert local.castigo == D("0.00")  # 49.50 < 80
    assert local.unidades == 2
    assert formatear_porcentaje(local.rendimiento_mensual_pct) == "37.5 %"
    assert local.nivel is Nivel.RECOMENDABLE  # Muy recomendable exige 40%

    assert registro.resultado is Resultado.NIVEL_ASIGNADO
    assert registro.canal_elegido is Canal.LOCAL
    assert (registro.nivel_aviso, registro.canal_aviso) == (Nivel.RECOMENDABLE, Canal.LOCAL)
    # DEC-267: las marcas de canal van solo en el canal.
    assert Marca.MATERIAL_PELIGROSO.value not in registro.marcas


def test_s07_material_peligroso_solo_marca_no_cierra_amazon():
    """S-07: sin la restricción de la categoría, el material peligroso no cierra Amazon."""
    config = _config(
        _listas(productos_peligrosos="[{brand: MarcaPerfume, model: PF-1}]"),
        (
            "    amazon_restricted: true          # RN-006 §4.3 (B4)\n",
            "    amazon_restricted: false\n",
        ),
    )
    amazon = _canal(motor.evaluar(_contexto_b4(configuracion=config)), Canal.AMAZON)
    assert CausaCanalCerrado.NO_VENDIBLE_EN_AMAZON not in amazon.causas_cerrado
    assert Marca.MATERIAL_PELIGROSO.value in amazon.marcas


def test_s07_material_peligroso_por_marca():
    listas = _config(_listas(marcas_peligrosas="[marcaperfume]")).contenido.lists
    assert canales.material_peligroso(_oferta_b4().observacion, listas)
    assert not canales.material_peligroso(_oferta_b4().observacion, C.lists)


_FUERA = dt.date(2026, 10, 14)
_DENTRO = dt.date(2026, 11, 1)


@pytest.mark.parametrize(
    ("reemplazo", "categoria", "dia", "esperado"),
    [
        (None, "tools", _FUERA, False),
        (None, "beauty", _FUERA, True),  # categoría restringida (B4)
        (_listas(marcas_restringidas="[MARCAP]"), "tools", _FUERA, True),  # marca
        (_listas(productos_restringidos="[{gtin: '036000291452'}]"), "tools", _FUERA, True),
        (_listas(productos_restringidos="[{brand: MarcaP, model: sc-1}]"), "tools", _FUERA, True),
        (_listas(productos_restringidos="[{brand: MarcaP, model: SC-2}]"), "tools", _FUERA, False),
        (None, "toys", _FUERA, False),
        (None, "toys", _DENTRO, True),  # S-10: del 1-nov
        (None, "toys", dt.date(2026, 12, 31), True),  # al 31-dic
        (None, "toys", dt.date(2027, 1, 1), False),
        (None, "tools", _DENTRO, False),  # la temporada es solo de juguetes
    ],
)
def test_s09_s10_restriccion_por_categoria_marca_producto_y_temporada(
    reemplazo, categoria, dia, esperado
):
    config = CONFIG if reemplazo is None else _config(reemplazo)
    oferta = _oferta_b1(category=categoria).observacion
    assert canales.restringido_en_amazon(oferta, config.contenido, dia) is esperado


def test_s10_temporada_de_juguetes_cierra_amazon_en_el_motor():
    contexto = _contexto(
        _oferta_b1(category="toys"),
        _historial_b1(),
        _fichas_b1(),
    )
    navidad = ContextoEvaluacion(
        id_evaluacion=UUID(int=14),
        instante=dt.datetime(2026, 11, 14, 13, 0, tzinfo=ZONA),
        configuracion=CONFIG,
        id_version_configuracion=1,
        oferta=contexto.oferta,
        historial=contexto.historial,
        fichas_amazon=contexto.fichas_amazon,
    )
    fuera = _canal(motor.evaluar(contexto), Canal.AMAZON)
    dentro = _canal(motor.evaluar(navidad), Canal.AMAZON)
    assert CausaCanalCerrado.NO_VENDIBLE_EN_AMAZON not in fuera.causas_cerrado
    assert CausaCanalCerrado.NO_VENDIBLE_EN_AMAZON in dentro.causas_cerrado
    assert dentro.estado is EstadoCanal.CERRADO


# --- B9 (base) ----------------------------------------------------------------------------


def _contexto_b9():
    """B1 con la tercera cadena a $99 hoy (hace 10 h)."""
    target = _obs(
        "99.00",
        comercio="tienda-b",
        publicacion=PUB_TERCERA,
        momento=_momento(horas_antes=10),
        producto=_SIERRA,
    )
    return _contexto_b1(historial=_historial_b1(target), configuracion=CONFIG_B9)


@pytest.mark.scenario("B9 (base)")
def test_b9_base_competencia_mas_barata_y_nivel_del_aviso():
    registro = motor.evaluar(_contexto_b9())

    assert registro.referencias.precio_mercado_hoy == D("99.00")
    assert registro.referencias.precio_habitual == D("119.00")
    assert registro.calidad_precio is CalidadPrecio.BUENA_OFERTA  # 29 ≤ 100.98

    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.DISPONIBLE
    assert Marca.COMPETENCIA_MAS_BARATA.value in amazon.marcas  # 99 < 101.15
    assert amazon.margen_ajustado == D("44.73")  # las cuentas por unidad de B1
    assert amazon.nivel_calculado is Nivel.RECOMENDABLE  # baja de Muy recomendable
    assert amazon.nivel is Nivel.RECOMENDABLE
    assert amazon.unidades == 3  # tope 3: Recomendable no sube el tope
    assert amazon.ganancia_total == D("134.19")

    local = _canal(registro, Canal.LOCAL)
    assert local.precio_venta == D("75.74")  # 99 × 85% × 90% = 75.735
    assert local.margen_neto == D("34.99")
    assert formatear_porcentaje(local.margen_neto_pct) == "112.0 %"
    assert local.nivel is Nivel.MUY_RECOMENDABLE  # la baja por competencia es solo de Amazon
    assert Marca.COMPETENCIA_MAS_BARATA.value not in local.marcas
    assert local.unidades == 2
    assert local.ganancia_total == D("69.98")

    diferencia = (amazon.ganancia_total - local.ganancia_total) / amazon.ganancia_total * 100
    assert formatear_porcentaje(diferencia) == "47.9 %"
    assert registro.resultado is Resultado.NIVEL_ASIGNADO
    assert registro.canal_elegido is Canal.AMAZON
    # S-33: el aviso va con el nivel más alto entre los canales (venta local).
    assert (registro.nivel_aviso, registro.canal_aviso) == (Nivel.MUY_RECOMENDABLE, Canal.LOCAL)
    # DEC-267: la marca de competencia va en el canal, no en el registro.
    assert Marca.COMPETENCIA_MAS_BARATA.value not in registro.marcas


def test_la_competencia_baja_vigilar_a_sin_nivel():
    """RN-009 §4.3: Vigilar con competencia más barata baja a sin nivel."""
    margenes = rentabilidad.Margenes(D("20"), D("40"), D(0), D(0), D("13"), D("26"))
    assert rentabilidad.nivel_calculado(D("30"), margenes, D("50"), C, False) is Nivel.VIGILAR
    assert rentabilidad.nivel_calculado(D("30"), margenes, D("50"), C, True) is None


def test_competencia_mas_barata_en_el_borde():
    """RN-002 §4.3: mercado hoy < venta × (1 − 15%); igual al umbral no cuenta."""
    umbral = C.levels.cheaper_competition_pct
    assert not canales.competencia_mas_barata(D("101.15"), D("119.00"), umbral)
    assert canales.competencia_mas_barata(D("101.14"), D("119.00"), umbral)
    assert not canales.competencia_mas_barata(D("99"), None, umbral)


# --- B21 ----------------------------------------------------------------------------------


def test_b2_sin_cambios_es_vigilar_en_venta_local():
    """La base de B21: B2 da Vigilar, venta local."""
    registro = motor.evaluar(_contexto_b2())
    assert registro.confianza is Confianza.ALTA  # "4 disponibles": cantidad exacta, 2 h ≤ 6 h
    local = _canal(registro, Canal.LOCAL)
    assert local.precio_venta == D("116.10")
    assert local.margen_ajustado == D("21.48")
    assert local.nivel is Nivel.VIGILAR
    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.margen_ajustado == D("17.31")
    assert amazon.nivel_calculado is None
    assert registro.resultado is Resultado.NIVEL_ASIGNADO
    assert (registro.nivel_aviso, registro.canal_aviso) == (Nivel.VIGILAR, Canal.LOCAL)


@pytest.mark.scenario("B21")
def test_b21_confianza_baja_en_tienda_sin_nivel_con_nivel_calculado():
    oferta = _oferta_b2(availability={"state": "limited_stock"}, momento=_momento(horas_antes=3))
    registro = motor.evaluar(_contexto_b2(oferta))

    assert registro.confianza is Confianza.BAJA  # "pocas unidades" > 2 h
    assert Marca.CONFIANZA_BAJA.value in registro.marcas
    assert formatear_porcentaje(registro.descuento_real) == "47.0 %"

    local = _canal(registro, Canal.LOCAL)
    assert local.estado is EstadoCanal.DISPONIBLE
    assert local.nivel_calculado is Nivel.VIGILAR
    assert local.nivel is None
    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.nivel_calculado is None and amazon.nivel is None

    assert registro.resultado is Resultado.SIN_NIVEL
    assert registro.motivos == ()
    assert registro.canal_elegido is None
    assert (registro.nivel_aviso, registro.canal_aviso) == (None, None)


# --- B25 ----------------------------------------------------------------------------------


@pytest.mark.scenario("B25")
def test_b25_sin_rotacion_cierra_amazon_y_gana_la_venta_local():
    contexto = _contexto_b1(fichas=_fichas_b1(vendedores=15, vendidos=10))
    registro = motor.evaluar(contexto)
    # 10 ÷ (15 + 1) = 0.625 → 0
    assert canales.ventas_al_mes_amazon(canales.ficha_vigente(contexto)) == 0

    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.CERRADO
    assert amazon.causas_cerrado == (CausaCanalCerrado.SIN_ROTACION,)
    assert CausaCanalCerrado.SIN_ROTACION.value in amazon.marcas
    assert amazon.nivel_calculado is None and amazon.nivel is None
    assert amazon.unidades is None and amazon.ganancia_total is None

    local = _canal(registro, Canal.LOCAL)
    assert local.ganancia_total == D("100.58")
    assert local.nivel is Nivel.MUY_RECOMENDABLE

    assert registro.resultado is Resultado.NIVEL_ASIGNADO
    assert registro.canal_elegido is Canal.LOCAL
    assert (registro.nivel_aviso, registro.canal_aviso) == (Nivel.MUY_RECOMENDABLE, Canal.LOCAL)


@pytest.mark.parametrize(("vendedores", "vendidos", "cierra"), [(15, 16, False), (15, 15, True)])
def test_s08_borde_de_una_venta_al_mes(vendedores, vendidos, cierra):
    amazon = _canal(
        motor.evaluar(_contexto_b1(fichas=_fichas_b1(vendedores=vendedores, vendidos=vendidos))),
        Canal.AMAZON,
    )
    assert (CausaCanalCerrado.SIN_ROTACION in amazon.causas_cerrado) is cierra


# --- Empate del nivel del aviso (design.md §10 punto 6) -----------------------------------


def _con_nivel(canal: Canal, nivel: Nivel | None, total: str, rendimiento: str):
    return EvaluacionCanal(
        canal=canal,
        estado=EstadoCanal.DISPONIBLE,
        nivel=nivel,
        nivel_calculado=nivel,
        ganancia_total=D(total),
        rendimiento_mensual_pct=D(rendimiento),
    )


@pytest.mark.parametrize(
    ("amazon_total", "local_total", "elegido"),
    [
        ("134.19", "100.58", Canal.AMAZON),  # gana Amazon por ganancia (25.0%)
        ("100.58", "134.19", Canal.LOCAL),  # gana la venta local por ganancia
        ("110.19", "100.58", Canal.LOCAL),  # 8.7% < 10%: desempata el rendimiento (local)
    ],
)
def test_empate_de_nivel_el_aviso_va_con_el_canal_elegido(amazon_total, local_total, elegido):
    amazon = _con_nivel(Canal.AMAZON, Nivel.MUY_RECOMENDABLE, amazon_total, "95.3")
    local = _con_nivel(Canal.LOCAL, Nivel.MUY_RECOMENDABLE, local_total, "160.9")
    resultado = eleccion.elegir((amazon, local), C.levels.channel_tiebreak_pct)
    assert resultado == eleccion.Eleccion(elegido, Nivel.MUY_RECOMENDABLE, elegido)


def test_sin_empate_el_aviso_va_con_el_nivel_mas_alto_aunque_no_sea_el_elegido():
    amazon = _con_nivel(Canal.AMAZON, Nivel.VIGILAR, "200.00", "50")
    local = _con_nivel(Canal.LOCAL, Nivel.RECOMENDABLE, "20.00", "40")
    resultado = eleccion.elegir((amazon, local), C.levels.channel_tiebreak_pct)
    assert resultado == eleccion.Eleccion(Canal.AMAZON, Nivel.RECOMENDABLE, Canal.LOCAL)
