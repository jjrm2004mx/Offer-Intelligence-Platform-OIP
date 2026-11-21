"""Pruebas de T10: descuento anunciado y sus marcas, precio de mercado hoy, precio típico de la
tienda y calidad del precio (CMP-11, CMP-12, PAR-10; RN-002 v2, RN-003 v2, RN-012 v1; S-03,
S-22, S-28), con los escenarios B6 y B7, y los ajustes de T25 (DEC-261: orden del filtro
del mercado hoy; decisión 10 del #34: precio antes inflado sin datos).

Fixtures sintéticos: comercios ficticios con dominios reservados (example.com, example.net,
example.org); ninguna prueba abre una URL. Instante explícito, sin reloj ni zona de la
máquina, sin aleatoriedad.
"""

from __future__ import annotations

import builtins
import dataclasses
import datetime as dt
import socket
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from config_tienda_prueba import BASE, TIENDA_PRUEBA, con_tienda_prueba
from oip.catalogos import CalidadPrecio, Marca, Motivo, Resultado
from oip.configuracion import cargar_configuracion_texto
from oip.dinero import formatear_porcentaje
from oip.entradas.capturas import leer_captura
from oip.entradas.contrato import leer_observacion
from oip.evaluacion import canales, motor, referencias
from oip.evaluacion.contexto import ContextoEvaluacion, ObservacionRegistrada
from oip.evaluacion.descuento import (
    DatosCalidad,
    calidad_del_precio,
    descuento_anunciado,
    descuento_real,
    franja,
    marcas_del_anunciado,
)

# --- Configuración: tienda-prueba (cadena de la oferta), otra tienda de la misma cadena y
# tres cadenas más. Todo sintético.
_EXTRA = (
    "  tienda-prueba-linea: {chain: tienda-prueba, domains: [linea.example.com], "
    "amazon_listing: false}\n"
    "  tienda-b: {chain: cadena-b, domains: [example.net], amazon_listing: false}\n"
    "  tienda-c: {chain: cadena-c, domains: [example.org], amazon_listing: false}\n"
    "  tienda-d: {chain: cadena-d, domains: [d.example.org], amazon_listing: false}\n"
)


def _texto_config(**reemplazos: tuple[str, str]) -> str:
    texto = con_tienda_prueba(BASE.read_text(encoding="utf-8"))
    texto = texto.replace("\nretailers:\n", "\nretailers:\n" + _EXTRA, 1)
    for viejo, nuevo in reemplazos.values():
        assert texto.count(viejo) == 1, viejo
        texto = texto.replace(viejo, nuevo)
    return texto


def _config(**reemplazos: tuple[str, str]):
    return cargar_configuracion_texto(_texto_config(**reemplazos), origen="t10")


CONFIG = _config()
PARAMETROS = CONFIG.contenido.discount_quality
ZONA = ZoneInfo("America/Tijuana")
HOY = dt.date(2026, 11, 18)
INSTANTE = dt.datetime(2026, 11, 18, 13, 0, tzinfo=ZONA)
PRODUCTO = UUID(int=700)
PUB_OFERTA = UUID(int=701)

_contador = iter(range(10_000, 10_000_000))
_URL = {
    TIENDA_PRUEBA: "https://tienda.example.com/p/1",
    "tienda-prueba-linea": "https://linea.example.com/p/1",
    "tienda-b": "https://example.net/p/1",
    "tienda-c": "https://example.org/p/1",
    "tienda-d": "https://d.example.org/p/1",
    "amazon": "https://amazon.example.com/dp/X",
}


def _momento(dias: int = 0, horas_antes: int = 0, minutos_antes: int = 0) -> dt.datetime:
    base = dt.datetime(HOY.year, HOY.month, HOY.day, 13, 0, tzinfo=ZONA)
    return base + dt.timedelta(days=dias) - dt.timedelta(hours=horas_antes, minutes=minutos_antes)


def _obs(
    precio: str,
    *,
    comercio: str = "tienda-b",
    publicacion: UUID | None = None,
    momento: dt.datetime | None = None,
    ident: UUID | None = None,
    **cambios,
) -> ObservacionRegistrada:
    datos = {
        "retailerCode": comercio,
        "productUrl": _URL[comercio],
        "title": "Producto de prueba",
        "brand": "MarcaP",
        "model": "MP-1",
        "category": "tools",
        "price": {"current": precio, "currency": "USD"},
        "seller": "comercio",
        "condition": "new",
        "availability": {"state": "in_stock_confirmed"},
        "purchaseMode": "envio",
        "extractedAt": (momento or _momento(horas_antes=2)).isoformat(),
        "blocked": False,
    }
    datos.update(cambios)
    publicacion = UUID(int=next(_contador)) if publicacion is None else publicacion
    ident = UUID(int=next(_contador)) if ident is None else ident
    return ObservacionRegistrada(leer_observacion(datos), ident, publicacion, PRODUCTO)


def _oferta(precio: str = "169.00", was: str | None = None, **cambios) -> ObservacionRegistrada:
    precio_dict = {"current": precio, "currency": "USD"}
    if was is not None:
        precio_dict["was"] = was
    return _obs(
        precio,
        comercio=TIENDA_PRUEBA,
        publicacion=PUB_OFERTA,
        momento=_momento(horas_antes=1),
        price=precio_dict,
        **cambios,
    )


def _ficha(buy_box: str | None, horas_antes: int = 2, publicacion=None):
    return _obs(
        "999.00",
        comercio="amazon",
        publicacion=publicacion,
        momento=_momento(horas_antes=horas_antes),
        amazonListing={"buyBoxPrice": buy_box, "sellersNew": 3},
    )


def _historial(precio: str, dias: range, comercio: str = "tienda-b", publicacion=None):
    publicacion = UUID(int=next(_contador)) if publicacion is None else publicacion
    return [
        _obs(precio, comercio=comercio, publicacion=publicacion, momento=_momento(n)) for n in dias
    ]


def _contexto(oferta, historial=(), fichas=(), msrp=(), configuracion=CONFIG):
    return ContextoEvaluacion(
        id_evaluacion=UUID(int=1),
        instante=INSTANTE,
        configuracion=configuracion,
        id_version_configuracion=1,
        oferta=oferta,
        historial=tuple(historial),
        fichas_amazon=tuple(fichas),
        msrp=tuple(msrp),
    )


def _msrp(valor: str, fecha: str):
    datos = {"brand": "MarcaP", "model": "MP-1", "value": valor, "source": "fab", "date": fecha}
    return leer_captura("msrp", datos, zona=ZONA)


def _datos(**cambios) -> DatosCalidad:
    base = {
        "precio": Decimal("29.00"),
        "precio_habitual": Decimal("119"),
        "descuento_real": descuento_real(Decimal("119"), Decimal("29.00")),
        "precio_mercado_hoy": Decimal("119.00"),
        "otros_comercios": 2,
        "minimo_registrado": Decimal("109.00"),
        "dias_historial": 60,
        "descuento_anunciado": None,
        "precio_antes_inflado": False,
    }
    base.update(cambios)
    if ("precio_habitual" in cambios or "precio" in cambios) and "descuento_real" not in cambios:
        habitual = base["precio_habitual"]
        base["descuento_real"] = (
            None if habitual is None else descuento_real(habitual, base["precio"])
        )
    return DatosCalidad(**base)


# --- Descuento anunciado (RN-003 §4) -----------------------------------------------------


def test_descuento_anunciado_sin_redondear_y_mostrado_a_un_decimal():
    anunciado = descuento_anunciado(Decimal("129.00"), Decimal("29.00"))
    assert anunciado == (Decimal("129.00") - Decimal("29.00")) / Decimal("129.00") * 100
    assert anunciado != Decimal("77.5")  # no se redondea
    assert formatear_porcentaje(anunciado) == "77.5 %"
    assert formatear_porcentaje(descuento_anunciado(Decimal("200"), Decimal("20"))) == "90.0 %"
    assert formatear_porcentaje(descuento_anunciado(Decimal("199"), Decimal("79"))) == "60.3 %"


def test_sin_precio_tachado_no_hay_descuento_anunciado():
    assert descuento_anunciado(None, Decimal("29.00")) is None
    assert descuento_anunciado(Decimal("0"), Decimal("29.00")) is None


def test_descuento_anunciado_rechaza_float():
    with pytest.raises(TypeError):
        descuento_anunciado(129.0, Decimal("29.00"))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        descuento_anunciado(Decimal("129"), 29.0)  # type: ignore[arg-type]


# --- Franja (B7 y bordes) ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("habitual", "precio", "motivo"),
    [
        ("100", "80", Motivo.SOLO_REFERENCIA),  # 20.0% exacto: desde el corte
        ("100", "80.01", Motivo.MERCADO_YA_BARATO),  # 19.99%
        ("100", "75.01", Motivo.SOLO_REFERENCIA),  # 24.99%
        ("100", "75", None),  # 25%: sigue
        ("22", "20", Motivo.MERCADO_YA_BARATO),  # RN-003 ejemplo A: 9.1%
        ("100", "120", Motivo.MERCADO_YA_BARATO),  # negativo
    ],
)
def test_franjas_sin_redondear(habitual, precio, motivo):
    real = descuento_real(Decimal(habitual), Decimal(precio))
    assert franja(real, PARAMETROS) is motivo


# --- Marcas del descuento anunciado ------------------------------------------------------


def test_precio_antes_inflado_ejemplo_lampara():
    # RN-003 ejemplo A / B3: 200 > 1.5 × 25 = 37.50.
    marcas = marcas_del_anunciado(Decimal("200.00"), Decimal("25"), PARAMETROS)
    assert marcas == (Marca.PRECIO_ANTES_INFLADO,)


def test_no_inflado_ejemplo_taladro():
    # B2: 199 ≤ 1.5 × 149 = 223.50.
    assert marcas_del_anunciado(Decimal("199.00"), Decimal("149"), PARAMETROS) == ()


def test_inflado_es_estrictamente_mayor():
    assert marcas_del_anunciado(Decimal("37.50"), Decimal("25"), PARAMETROS) == ()
    assert marcas_del_anunciado(Decimal("37.51"), Decimal("25"), PARAMETROS) == (
        Marca.PRECIO_ANTES_INFLADO,
    )


def test_tachado_sin_historial_de_la_tienda_no_comprobado():
    assert marcas_del_anunciado(Decimal("129.00"), None, PARAMETROS) == (
        Marca.DESCUENTO_ANUNCIADO_NO_COMPROBADO,
    )


def test_sin_tachado_no_hay_marcas():
    assert marcas_del_anunciado(None, None, PARAMETROS) == ()
    assert marcas_del_anunciado(None, Decimal("25"), PARAMETROS) == ()


def test_el_factor_de_inflado_sale_de_la_configuracion():
    otra = _config(factor=("inflated_factor: 1.5", "inflated_factor: 2"))
    parametros = otra.contenido.discount_quality
    assert marcas_del_anunciado(Decimal("40"), Decimal("25"), PARAMETROS) == (
        Marca.PRECIO_ANTES_INFLADO,
    )
    assert marcas_del_anunciado(Decimal("40"), Decimal("25"), parametros) == ()


# --- Calidad del precio (RN-012 §4 y §5, S-22, S-28) ------------------------------------


def test_rn012_ejemplo_a_igualar_el_minimo_no_es_excepcional():
    datos = _datos(
        precio=Decimal("79.99"),
        precio_habitual=Decimal("100.39"),
        precio_mercado_hoy=Decimal("79.99"),
        otros_comercios=3,
        minimo_registrado=Decimal("79.99"),
        dias_historial=400,
    )
    assert calidad_del_precio(datos, PARAMETROS) is CalidadPrecio.BUENA_OFERTA


def test_rn012_ejemplo_b_sin_90_dias_es_buena_oferta():
    datos = _datos(minimo_registrado=Decimal("50"), dias_historial=60)
    assert calidad_del_precio(datos, PARAMETROS) is CalidadPrecio.BUENA_OFERTA


def test_oferta_excepcional_con_90_dias_y_menor_que_el_minimo():
    datos = _datos(minimo_registrado=Decimal("29.01"), dias_historial=90)
    assert calidad_del_precio(datos, PARAMETROS) is CalidadPrecio.OFERTA_EXCEPCIONAL
    assert (
        calidad_del_precio(dataclasses.replace(datos, dias_historial=89), PARAMETROS)
        is CalidadPrecio.BUENA_OFERTA
    )


def test_rn012_ejemplo_d_sin_historial_no_pasa_de_precio_competitivo():
    datos = _datos(
        precio=Decimal("169.00"),
        precio_habitual=None,
        precio_mercado_hoy=Decimal("179.00"),
        otros_comercios=3,
    )
    assert calidad_del_precio(datos, PARAMETROS) is CalidadPrecio.PRECIO_COMPETITIVO


def test_rn012_ejemplo_e_fuera_de_los_mas_baratos_es_precio_normal():
    datos = _datos(
        precio=Decimal("105"), precio_habitual=Decimal("110"), precio_mercado_hoy=Decimal("95")
    )
    assert calidad_del_precio(datos, PARAMETROS) is CalidadPrecio.PRECIO_NORMAL


def test_s22_sin_historial_y_fuera_de_los_mas_baratos_es_precio_normal():
    datos = _datos(precio=Decimal("190"), precio_habitual=None, precio_mercado_hoy=Decimal("179"))
    assert calidad_del_precio(datos, PARAMETROS) is CalidadPrecio.PRECIO_NORMAL


def test_s22_arriba_del_habitual_es_precio_normal_aunque_sea_el_mas_barato():
    datos = _datos(
        precio=Decimal("120"), precio_habitual=Decimal("119"), precio_mercado_hoy=Decimal("130")
    )
    assert calidad_del_precio(datos, PARAMETROS) is CalidadPrecio.PRECIO_NORMAL


def test_entre_los_mas_baratos_en_el_borde_sin_redondear():
    # 179 × 1.02 = 182.58 (B6): igual cuenta; un centavo arriba, no.
    borde = _datos(
        precio=Decimal("182.58"), precio_habitual=None, precio_mercado_hoy=Decimal("179")
    )
    assert calidad_del_precio(borde, PARAMETROS) is CalidadPrecio.PRECIO_COMPETITIVO
    fuera = dataclasses.replace(borde, precio=Decimal("182.59"))
    assert calidad_del_precio(fuera, PARAMETROS) is CalidadPrecio.PRECIO_NORMAL


def test_menos_de_2_comercios_no_pasa_de_precio_competitivo():
    # B14: mercado hoy $124 (1 comercio) con precio habitual → Precio competitivo (S-28).
    datos = _datos(
        precio_mercado_hoy=Decimal("124"), otros_comercios=1, descuento_anunciado=Decimal(77)
    )
    assert calidad_del_precio(datos, PARAMETROS) is CalidadPrecio.PRECIO_COMPETITIVO


def test_descuento_menor_que_15_entre_los_mas_baratos_es_precio_competitivo():
    datos = _datos(precio=Decimal("102"), precio_habitual=Decimal("119"))  # 14.3%
    assert calidad_del_precio(datos, PARAMETROS) is CalidadPrecio.PRECIO_COMPETITIVO
    datos = _datos(precio=Decimal("101.15"), precio_habitual=Decimal("119"))  # 15% exacto
    assert calidad_del_precio(datos, PARAMETROS) is CalidadPrecio.BUENA_OFERTA


def test_precio_antes_inflado_es_descuento_cuestionable_primero():
    datos = _datos(precio_antes_inflado=True, minimo_registrado=Decimal("50"), dias_historial=99)
    assert calidad_del_precio(datos, PARAMETROS) is CalidadPrecio.DESCUENTO_CUESTIONABLE


def test_s28_sin_historial_anunciado_contra_un_solo_comercio_es_cuestionable():
    datos = _datos(
        precio=Decimal("120"),
        precio_habitual=None,
        precio_mercado_hoy=Decimal("150"),
        otros_comercios=1,
        descuento_anunciado=Decimal("40"),
    )
    assert calidad_del_precio(datos, PARAMETROS) is CalidadPrecio.DESCUENTO_CUESTIONABLE
    # Con dos comercios ya no; sin precio tachado tampoco.
    dos = dataclasses.replace(datos, otros_comercios=2)
    assert calidad_del_precio(dos, PARAMETROS) is CalidadPrecio.PRECIO_COMPETITIVO
    sin_tachado = dataclasses.replace(datos, descuento_anunciado=None)
    assert calidad_del_precio(sin_tachado, PARAMETROS) is CalidadPrecio.PRECIO_COMPETITIVO


def test_s28_con_historial_el_anunciado_se_considera_comparado():
    datos = _datos(otros_comercios=1, descuento_anunciado=Decimal("77"))
    assert calidad_del_precio(datos, PARAMETROS) is CalidadPrecio.PRECIO_COMPETITIVO


def test_sin_habitual_ni_mercado_hoy_no_hay_calidad():
    datos = _datos(precio_habitual=None, precio_mercado_hoy=None, otros_comercios=0)
    assert calidad_del_precio(datos, PARAMETROS) is None


def test_con_habitual_sin_mercado_hoy_no_esta_entre_los_mas_baratos():
    datos = _datos(precio_mercado_hoy=None, otros_comercios=0)
    assert calidad_del_precio(datos, PARAMETROS) is CalidadPrecio.PRECIO_NORMAL


def test_los_umbrales_de_calidad_salen_de_la_configuracion():
    otra = _config(
        buena=("good_offer_min_discount_pct: 15", "good_offer_min_discount_pct: 80"),
        minimo=("min_other_retailers: 2", "min_other_retailers: 1"),
    )
    parametros = otra.contenido.discount_quality
    datos = _datos()  # 75.6%: ya no llega a 80
    assert calidad_del_precio(datos, parametros) is CalidadPrecio.PRECIO_COMPETITIVO
    uno = _datos(precio=Decimal("20"), otros_comercios=1)  # 83.2% y 1 comercio basta
    assert calidad_del_precio(uno, parametros) is CalidadPrecio.BUENA_OFERTA


def test_datos_calidad_son_estrictos():
    with pytest.raises(TypeError):
        _datos(precio=29.0)
    with pytest.raises(TypeError):
        _datos(otros_comercios=True)
    with pytest.raises(TypeError):
        _datos(precio_antes_inflado=1)
    with pytest.raises(ValueError):
        _datos(descuento_real=None)


# --- Precio de mercado hoy (RN-002 §4.1, S-03; design.md §10.4) ------------------------


def _hoy(*historial, fichas=(), oferta=None):
    return referencias.mercado_hoy(_contexto(oferta or _oferta(), historial, fichas))


def test_mercado_hoy_es_el_mas_bajo_y_no_cuenta_la_oferta_evaluada():
    propia_anterior = _obs("100.00", comercio=TIENDA_PRUEBA, publicacion=PUB_OFERTA)
    hoy = _hoy(_obs("185.00"), _obs("179.00", comercio="tienda-c"), propia_anterior)
    assert hoy.precio == Decimal("179.00")
    assert hoy.otras_cadenas == frozenset({"cadena-b", "cadena-c"})


def test_mercado_hoy_48_horas_o_menos():
    justo = _obs("150.00", momento=_momento(horas_antes=48))
    viejo = _obs("90.00", momento=_momento(horas_antes=48, minutos_antes=1), comercio="tienda-c")
    assert _hoy(justo, viejo).precio == Decimal("150.00")
    assert _hoy(viejo) is None  # RN-002 ejemplo C: dato viejo no cuenta


def test_mercado_hoy_la_antiguedad_sale_de_la_configuracion():
    otra = _config(edad=("market_today_max_age_hours: 48", "market_today_max_age_hours: 72"))
    viejo = _obs("90.00", momento=_momento(horas_antes=60))
    contexto = _contexto(_oferta(), [viejo], configuracion=otra)
    assert referencias.mercado_hoy(contexto).precio == Decimal("90.00")


def test_mercado_hoy_solo_nuevo_y_vendido_por_el_comercio():
    externo = _obs("100.00", seller="externo")
    usado = _obs("101.00", condition="used", comercio="tienda-c")
    bueno = _obs("150.00", comercio="tienda-d")
    assert _hoy(externo, usado, bueno).precio == Decimal("150.00")


def test_mercado_hoy_en_linea_solo_disponible_confirmada():
    no_confirmada = _obs("100.00", availability={"state": "in_stock"})
    limitada = _obs("101.00", availability={"state": "limited_stock"}, comercio="tienda-c")
    agotado = _obs("102.00", availability={"state": "out_of_stock"}, comercio="tienda-d")
    assert _hoy(no_confirmada, limitada, agotado) is None
    recoger = _obs("103.00", purchaseMode="recoleccion")
    assert _hoy(recoger).precio == Decimal("103.00")


@pytest.mark.parametrize(
    ("disponibilidad", "liquidacion", "horas", "cuenta"),
    [
        ({"state": "in_stock", "quantity": 4}, False, (24, 0), True),  # Media
        ({"state": "in_stock", "quantity": 4}, False, (24, 1), False),  # Baja
        ({"state": "in_stock", "quantity": 4}, True, (12, 0), True),
        ({"state": "in_stock", "quantity": 4}, True, (12, 1), False),
        ({"state": "in_stock"}, False, (12, 0), True),  # sin número: Media
        ({"state": "in_stock"}, False, (12, 1), False),
        ({"state": "in_stock"}, True, (6, 0), True),
        ({"state": "in_stock"}, True, (6, 1), False),
        ({"state": "limited_stock"}, False, (2, 0), True),
        ({"state": "limited_stock"}, False, (2, 1), False),
        ({"state": "out_of_stock"}, False, (1, 0), False),
        ({"state": "unconfirmed"}, False, (1, 0), False),
    ],
)
def test_mercado_hoy_en_tienda_confianza_alta_o_media(disponibilidad, liquidacion, horas, cuenta):
    obs = _obs(
        "100.00",
        purchaseMode="tienda",
        availability=disponibilidad,
        isClearance=liquidacion,
        momento=_momento(horas_antes=horas[0], minutos_antes=horas[1]),
    )
    assert (_hoy(obs) is not None) is cuenta


def test_mercado_hoy_la_observacion_mas_reciente_de_cada_publicacion_y_despues_el_filtro():
    pub = UUID(int=9_001)
    antes = _obs("100.00", publicacion=pub, momento=_momento(horas_antes=10))
    despues = _obs("120.00", publicacion=pub, momento=_momento(horas_antes=3))
    agotada = _obs(
        "90.00",
        publicacion=pub,
        momento=_momento(horas_antes=1),
        availability={"state": "out_of_stock"},
    )
    # DEC-261: primero la más reciente (la agotada) y después el filtro → la publicación sale.
    assert _hoy(antes, despues, agotada) is None
    # Sin la agotada, la más reciente es la de $120, no la anterior de $100.
    assert _hoy(antes, despues).precio == Decimal("120.00")


def test_mercado_hoy_con_la_ficha_de_amazon():
    assert _hoy(fichas=[_ficha("119.00")]).precio == Decimal("119.00")
    assert _hoy(fichas=[_ficha(None)]) is None  # sin botón de compra: sin oferta hoy
    hoy = _hoy(_obs("124.00", comercio="tienda-b"), fichas=[_ficha("119.00")])
    assert hoy.precio == Decimal("119.00")
    assert hoy.otras_cadenas == frozenset({"amazon", "cadena-b"})


def test_las_cadenas_no_cuentan_la_de_la_oferta():
    misma_cadena = _obs("150.00", comercio="tienda-prueba-linea")
    otra_pub_misma_tienda = _obs("151.00", comercio=TIENDA_PRUEBA)
    hoy = _hoy(misma_cadena, otra_pub_misma_tienda, _obs("160.00"))
    # El precio aún las incluye (comercio = cadena en el mercado hoy es de T16).
    assert hoy.precio == Decimal("150.00")
    assert hoy.otras_cadenas == frozenset({"cadena-b"})


def test_dos_tiendas_de_la_misma_cadena_son_un_comercio():
    hoy = _hoy(_obs("150.00"), _obs("151.00"))  # dos publicaciones de cadena-b
    assert hoy.otras_cadenas == frozenset({"cadena-b"})


def test_sin_datos_de_hoy_no_hay_mercado_hoy():
    assert _hoy() is None
    bloqueada = _obs("100.00", blocked=True)
    assert _hoy(bloqueada) is None


# --- Precio típico de la tienda, mínimo registrado, días de historial y MSRP ------------


def test_precio_tipico_solo_con_la_cadena_de_la_oferta_y_sin_el_dia_evaluado():
    propia = _historial("25.00", range(-10, -5), comercio=TIENDA_PRUEBA)
    misma_cadena = _historial("27.00", range(-10, -6), comercio="tienda-prueba-linea")
    otra = _historial("22.00", range(-10, 0), comercio="tienda-b")
    hoy_propio = _obs("1.00", comercio=TIENDA_PRUEBA, momento=_momento(horas_antes=3))
    contexto = _contexto(_oferta(was="200.00"), [*propia, *misma_cadena, *otra, hoy_propio])
    # 5 a $25 y 4 a $27 → mediana 25 (sin las de la otra cadena ni la de hoy).
    assert referencias.precio_tipico_de_la_tienda(contexto) == Decimal("25.00")


def test_precio_tipico_sin_historial_suficiente_de_la_tienda():
    propia = _historial("25.00", range(-4, 0), comercio=TIENDA_PRUEBA)  # 4 observaciones
    otra = _historial("22.00", range(-10, 0))
    contexto = _contexto(_oferta(was="200.00"), [*propia, *otra])
    assert referencias.precio_tipico_de_la_tienda(contexto) is None


def test_minimo_registrado_y_dias_de_historial_sin_la_oferta():
    oferta = _oferta("10.00")
    historial = [
        *_historial("119.00", range(-60, -55)),
        _obs("109.00", comercio="tienda-c", momento=_momento(-30)),
        _obs("5.00", seller="externo", momento=_momento(-20)),  # no cuenta
        oferta,  # la propia oferta no cuenta
    ]
    contexto = _contexto(oferta, historial)
    assert referencias.minimo_registrado(contexto) == Decimal("109.00")
    assert referencias.dias_de_historial(contexto) == 60
    vacio = _contexto(_oferta())
    assert referencias.minimo_registrado(vacio) is None
    assert referencias.dias_de_historial(vacio) == 0


def test_msrp_la_captura_mas_reciente_o_la_de_la_oferta():
    capturas = [_msrp("199.00", "2026-11-10"), _msrp("189.00", "2026-11-12")]
    assert referencias.msrp(_contexto(_oferta(), msrp=capturas)) == Decimal("189.00")
    con_msrp = _oferta(msrp={"value": "209.00", "source": "fab", "date": "2026-11-01"})
    assert referencias.msrp(_contexto(con_msrp)) == Decimal("209.00")
    assert referencias.msrp(_contexto(_oferta())) is None


# --- Motor: pasos 3, 4 y 5 ---------------------------------------------------------------


def test_motor_marca_no_comprobado_y_guarda_el_anunciado():
    # B1: tachado $129, oferta $29, la tienda sin historial suficiente propio.
    historial = _historial("119.00", range(-8, 0))
    registro = motor.evaluar(_contexto(_oferta("29.00", was="129.00"), historial))
    assert formatear_porcentaje(registro.descuento_anunciado) == "77.5 %"
    assert formatear_porcentaje(registro.descuento_real) == "75.6 %"
    assert registro.marcas == (Marca.DESCUENTO_ANUNCIADO_NO_COMPROBADO.value,)
    assert registro.motivos == ()


def test_motor_precio_antes_inflado_y_cuestionable():
    # B3 sin canales: tachado $200, típico de la tienda $25, habitual $22 → 9.1%.
    propia = _historial("25.00", range(-10, -5), comercio=TIENDA_PRUEBA)
    otra = _historial("20.00", range(-10, -5))
    historial = [*propia, *otra, _obs("22.00", comercio="tienda-c", momento=_momento(-4))]
    registro = motor.evaluar(_contexto(_oferta("20.00", was="200.00"), historial))
    assert registro.referencias.precio_habitual == Decimal("22.00")
    assert formatear_porcentaje(registro.descuento_anunciado) == "90.0 %"
    assert registro.marcas == (Marca.PRECIO_ANTES_INFLADO.value,)
    assert registro.calidad_precio is CalidadPrecio.DESCUENTO_CUESTIONABLE
    assert registro.resultado is Resultado.DESCARTADA
    assert registro.motivo_principal is Motivo.MERCADO_YA_BARATO


def test_motor_buena_oferta_con_dos_comercios():
    historial = [
        *_historial("119.00", range(-8, 0), comercio="tienda-c"),
        _obs("124.00", momento=_momento(horas_antes=8)),
    ]
    registro = motor.evaluar(_contexto(_oferta("29.00"), historial, [_ficha("119.00")]))
    assert registro.referencias.precio_mercado_hoy == Decimal("119.00")
    assert registro.calidad_precio is CalidadPrecio.BUENA_OFERTA


def test_motor_usado_calidad_no_aplica_y_sin_motivo_de_historial():
    registro = motor.evaluar(_contexto(_oferta("50.00", was="80.00", condition="used")))
    assert registro.calidad_precio is CalidadPrecio.NO_APLICA
    assert registro.descuento_real is None
    assert registro.descuento_anunciado is None
    assert Motivo.SIN_HISTORIAL_SUFICIENTE not in registro.motivos


def test_motor_sin_datos_no_hay_calidad_ni_referencias():
    registro = motor.evaluar(_contexto(_oferta()))
    assert registro.calidad_precio is None
    assert registro.referencias.precio_habitual is None
    assert registro.referencias.precio_mercado_hoy is None
    assert registro.referencias.msrp is None
    assert registro.motivos == (Motivo.SIN_HISTORIAL_SUFICIENTE,)


def test_el_msrp_no_cambia_la_calidad_ni_el_resultado():
    otros = [_obs("179.00"), _obs("185.00", comercio="tienda-c")]
    sin = motor.evaluar(_contexto(_oferta(), otros))
    con = motor.evaluar(_contexto(_oferta(), otros, msrp=[_msrp("199.00", "2026-11-10")]))
    assert con.referencias.msrp == Decimal("199.00")
    assert (con.calidad_precio, con.resultado, con.motivos, con.marcas) == (
        sin.calidad_precio,
        sin.resultado,
        sin.motivos,
        sin.marcas,
    )


def test_motor_puro_y_reproducible(monkeypatch):
    contexto = _contexto(_oferta("29.00", was="129.00"), [_obs("179.00")], [_ficha("119.00")])

    def prohibido(*a, **k):
        raise AssertionError("el motor no usa red ni archivos")

    monkeypatch.setattr(socket, "socket", prohibido)
    monkeypatch.setattr(builtins, "open", prohibido)
    r1 = motor.evaluar(contexto)
    r2 = motor.evaluar(ContextoEvaluacion.desde_json(contexto.a_json()))
    assert r1 == r2
    assert r1.a_json() == r2.a_json()


# --- Escenarios ------------------------------------------------------------------------


@pytest.mark.scenario("B6")
def test_b6_sin_historial_suficiente():
    # Dado: 3 observaciones en 2 días, MSRP $199, oferta $169 y hoy otros 3 comercios a
    # $179, $185 y $189. El resto, neutro: sin precio tachado.
    historial = [
        _obs("175.00", momento=_momento(-4)),
        _obs("176.00", comercio="tienda-c", momento=_momento(-4, horas_antes=1)),
        _obs("177.00", comercio="tienda-d", momento=_momento(-3)),
        _obs("179.00", momento=_momento(horas_antes=3)),
        _obs("185.00", comercio="tienda-c", momento=_momento(horas_antes=4)),
        _obs("189.00", comercio="tienda-d", momento=_momento(horas_antes=5)),
    ]
    contexto = _contexto(_oferta("169.00"), historial, msrp=[_msrp("199.00", "2026-11-10")])
    registro = motor.evaluar(contexto)
    # No hay descuento real ni nivel (nivel_calculado no disponible).
    assert registro.referencias.precio_habitual is None
    assert registro.descuento_real is None
    assert all(c.nivel is None and c.nivel_calculado is None for c in registro.canales)
    assert registro.nivel_aviso is None
    # Los 3 comercios de hoy son 3 cadenas distintas de la evaluada.
    assert referencias.mercado_hoy(contexto).otras_cadenas == frozenset(
        {"cadena-b", "cadena-c", "cadena-d"}
    )
    # Calidad Precio competitivo (169 ≤ 179 × 1.02 = 182.58).
    assert registro.referencias.precio_mercado_hoy == Decimal("179.00")
    assert Decimal("169.00") <= Decimal("179.00") * Decimal("1.02") == Decimal("182.58")
    assert registro.calidad_precio is CalidadPrecio.PRECIO_COMPETITIVO
    # El MSRP solo se muestra.
    assert registro.referencias.msrp == Decimal("199.00")
    # Resultado REVISION_MANUAL, motivo SIN HISTORIAL SUFICIENTE.
    assert registro.resultado is Resultado.REVISION_MANUAL
    assert registro.motivo_principal is Motivo.SIN_HISTORIAL_SUFICIENTE


@pytest.mark.scenario("B7")
def test_b7_solo_referencia():
    # Dado: oferta $80, precio habitual $100. El resto, neutro: sin tachado ni datos de hoy.
    historial = _historial("100.00", range(-10, -5))
    registro = motor.evaluar(_contexto(_oferta("80.00"), historial))
    assert registro.referencias.precio_habitual == Decimal("100.00")
    assert registro.descuento_real == Decimal(20)
    assert formatear_porcentaje(registro.descuento_real) == "20.0 %"
    assert registro.resultado is Resultado.SOLO_REFERENCIA
    assert registro.motivo_principal is Motivo.SOLO_REFERENCIA
    # No se calculan unidades, días, rendimiento ni nivel.
    for canal in registro.canales:
        assert canal.unidades is None
        assert canal.dias_para_recuperar is None
        assert canal.rendimiento_mensual_pct is None
        assert canal.nivel is None
    assert registro.nivel_aviso is None


# --- T25: orden del filtro del mercado hoy (DEC-261) y cuestionable sin datos ------------


def _agotado(precio: str, publicacion: UUID, horas_antes: int, **cambios):
    datos = {"availability": {"state": "out_of_stock"}, **cambios}
    return _obs(precio, publicacion=publicacion, momento=_momento(horas_antes=horas_antes), **datos)


def test_t25_un_agotado_reciente_saca_a_la_publicacion_y_no_a_las_demas():
    pub = UUID(int=9_101)
    disponible = _obs("90.00", publicacion=pub, momento=_momento(horas_antes=20))
    agotado = _agotado("95.00", pub, horas_antes=2)
    otra = _obs("130.00", comercio="tienda-c", momento=_momento(horas_antes=30))
    hoy = _hoy(disponible, agotado, otra)
    assert hoy.precio == Decimal("130.00")  # el $90 viejo de la publicación agotada no entra
    assert hoy.otras_cadenas == frozenset({"cadena-c"})  # cadena-b ya no da dato de hoy
    # El orden de las observaciones en el contexto no cambia el resultado.
    assert _hoy(otra, agotado, disponible) == hoy


@pytest.mark.parametrize(
    "cambios",
    [{"condition": "used"}, {"seller": "externo"}, {"availability": {"state": "in_stock"}}],
    ids=["usada", "vendedor-externo", "en-linea-no-confirmada"],
)
def test_t25_la_mas_reciente_que_no_cumple_saca_a_la_publicacion(cambios):
    pub = UUID(int=9_102)
    anterior = _obs("90.00", publicacion=pub, momento=_momento(horas_antes=20))
    reciente = _obs("95.00", publicacion=pub, momento=_momento(horas_antes=2), **cambios)
    assert _hoy(anterior, reciente) is None
    # Si la que no cumple es la anterior, la más reciente sí da precio.
    vieja = _obs("80.00", publicacion=pub, momento=_momento(horas_antes=30), **cambios)
    assert _hoy(vieja, anterior).precio == Decimal("90.00")


def test_t25_tienda_fisica_la_confianza_es_la_de_la_mas_reciente():
    pub = UUID(int=9_103)
    base = {"purchaseMode": "tienda", "comercio": "tienda-b", "publicacion": pub}
    media = _obs(
        "90.00", momento=_momento(horas_antes=10), availability={"state": "in_stock"}, **base
    )
    baja = _obs(
        "92.00", momento=_momento(horas_antes=3), availability={"state": "out_of_stock"}, **base
    )
    assert _hoy(media).precio == Decimal("90.00")  # sola, sin número y ≤ 12 h: Media
    assert _hoy(media, baja) is None  # la más reciente está agotada


def test_t25_ficha_de_amazon_reciente_sin_boton_de_compra_saca_a_amazon():
    pub = UUID(int=9_104)
    con_boton = _ficha("119.00", horas_antes=20, publicacion=pub)
    sin_boton = _ficha(None, horas_antes=2, publicacion=pub)
    assert _hoy(fichas=[con_boton]).precio == Decimal("119.00")
    assert _hoy(fichas=[con_boton, sin_boton]) is None


def test_t25_borde_de_las_48_horas_y_la_antiguedad_cuenta_contra_el_instante():
    pub = UUID(int=9_105)
    justo = _obs("150.00", publicacion=pub, momento=_momento(horas_antes=48))
    # Un agotado fuera de la ventana no es "la más reciente" (más vieja que la de 48 h).
    fuera = _agotado("140.00", pub, horas_antes=49)
    assert _hoy(fuera, justo).precio == Decimal("150.00")
    # Exactamente a 48 h y agotada: es la más reciente en la ventana y saca a la publicación.
    justo_agotada = _agotado("150.00", pub, horas_antes=48)
    vieja_disponible = _obs("100.00", publicacion=pub, momento=_momento(horas_antes=49))
    assert _hoy(vieja_disponible, justo_agotada) is None
    # Una observación posterior al instante no está en la ventana: no saca a la publicación.
    futura = _obs(
        "99.00",
        publicacion=pub,
        momento=_momento(horas_antes=-1),
        availability={"state": "out_of_stock"},
    )
    assert _hoy(justo, futura).precio == Decimal("150.00")


def test_t25_mismo_instante_desempata_el_id_antes_del_filtro():
    pub = UUID(int=9_106)
    momento = _momento(horas_antes=5)
    menor_disponible = _obs("90.00", publicacion=pub, momento=momento, ident=UUID(int=1_001))
    mayor_agotada = _obs(
        "91.00",
        publicacion=pub,
        momento=momento,
        ident=UUID(int=1_002),
        availability={"state": "out_of_stock"},
    )
    assert _hoy(menor_disponible, mayor_agotada) is None
    assert _hoy(mayor_agotada, menor_disponible) is None  # no depende del orden de llegada
    menor_agotada = dataclasses.replace(mayor_agotada, id=UUID(int=1_000))
    assert _hoy(menor_agotada, menor_disponible).precio == Decimal("90.00")


def test_t25_bloqueada_o_precio_invalido_no_es_la_mas_reciente():
    pub = UUID(int=9_107)
    disponible = _obs("90.00", publicacion=pub, momento=_momento(horas_antes=20))
    bloqueada = _obs("1.00", publicacion=pub, momento=_momento(horas_antes=2), blocked=True)
    invalida = _obs(
        "0.00",
        publicacion=pub,
        momento=_momento(horas_antes=1),
        price={"current": "0.00", "currency": "USD"},
    )
    assert invalida.observacion.precio_invalido
    assert _hoy(disponible, bloqueada, invalida).precio == Decimal("90.00")


def test_t25_la_competencia_mas_barata_usa_el_mismo_mercado_hoy():
    # Venta en Amazon $119 → umbral 119 × 85% = 101.15. La publicación de $90 está agotada
    # en su observación más reciente: no da precio de hoy y no hay competencia más barata.
    pub = UUID(int=9_108)
    disponible = _obs("90.00", publicacion=pub, momento=_momento(horas_antes=20))
    agotado = _agotado("90.00", pub, horas_antes=2)
    ficha = _ficha("119.00")

    def competencia(*historial):
        contexto = _contexto(_oferta("29.00"), historial, [ficha])
        refs = referencias.calcular_referencias(contexto)
        costo = canales.costo_compra(contexto.oferta.observacion, CONFIG.contenido)
        return refs.precio_mercado_hoy, canales.evaluar_amazon(contexto, refs, costo)

    hoy, amazon = competencia(disponible)
    assert hoy == Decimal("90.00")
    assert amazon.baja_por_competencia is True  # 90 < 101.15
    hoy, amazon = competencia(disponible, agotado)
    assert hoy == Decimal("119.00")  # solo la ficha de Amazon
    assert amazon.baja_por_competencia is False


def test_t25_el_motor_y_las_referencias_usan_el_mismo_mercado_hoy():
    # La reevaluación (T22) recalcula las referencias con calcular_referencias y el paso 5
    # con mercado_hoy: los dos dan el mismo valor con el orden de DEC-261.
    pub = UUID(int=9_109)
    historial = [
        _obs("90.00", publicacion=pub, momento=_momento(horas_antes=20)),
        _agotado("90.00", pub, horas_antes=2),
        _obs("130.00", comercio="tienda-c"),
    ]
    contexto = _contexto(_oferta(), historial)
    assert referencias.calcular_referencias(contexto).precio_mercado_hoy == Decimal("130.00")
    assert referencias.mercado_hoy(contexto).precio == Decimal("130.00")
    assert motor.evaluar(contexto).referencias.precio_mercado_hoy == Decimal("130.00")


def test_t25_precio_antes_inflado_sin_habitual_ni_mercado_hoy_es_cuestionable():
    datos = _datos(
        precio_habitual=None,
        precio_mercado_hoy=None,
        otros_comercios=0,
        descuento_anunciado=Decimal(90),
        precio_antes_inflado=True,
    )
    assert calidad_del_precio(datos, PARAMETROS) is CalidadPrecio.DESCUENTO_CUESTIONABLE
    # Sin la marca, sin datos sigue sin calidad.
    sin_marca = dataclasses.replace(datos, precio_antes_inflado=False)
    assert calidad_del_precio(sin_marca, PARAMETROS) is None


def test_t25_motor_precio_antes_inflado_sin_datos_es_cuestionable():
    # Solo pasa si la ventana del precio típico es mayor que la del habitual: la tienda tiene
    # historial de hace 61 a 90 días ($25) y el producto ninguno en los últimos 60 días.
    otra = _config(
        tipico=("store_typical_window_days: 60", "store_typical_window_days: 90"),
    )
    propia = _historial("25.00", range(-90, -85), comercio=TIENDA_PRUEBA)
    contexto = _contexto(_oferta("20.00", was="200.00"), propia, configuracion=otra)
    registro = motor.evaluar(contexto)
    assert registro.referencias.precio_habitual is None
    assert registro.referencias.precio_mercado_hoy is None
    assert registro.marcas == (Marca.PRECIO_ANTES_INFLADO.value,)  # 200 > 1.5 × 25
    assert registro.calidad_precio is CalidadPrecio.DESCUENTO_CUESTIONABLE
    assert Motivo.SIN_HISTORIAL_SUFICIENTE in registro.motivos
    # Con la configuración de producción, el mismo historial ya no da precio típico: sin
    # marca y sin datos, sin calidad.
    sin_ventana = motor.evaluar(_contexto(_oferta("20.00", was="200.00"), propia))
    assert sin_ventana.marcas == (Marca.DESCUENTO_ANUNCIADO_NO_COMPROBADO.value,)
    assert sin_ventana.calidad_precio is None
