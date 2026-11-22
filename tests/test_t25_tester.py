"""Pruebas independientes de oip-tester para T25 (orden del filtro del mercado hoy y calidad
con ``PRECIO ANTES INFLADO`` sin datos).

Fuentes: REQ-2026-0001 §3.2 pasos 3 a 5, §5 (B1, B6, B7, B9, B14) y §13 S-03 y S-28;
RN-002 v2 §4.1 y §4.3; RN-007 v2 §4.1; RN-012 v1 §3, §4 y §11; design.md §3 (nada posterior
al instante entra al contexto), §10 puntos 3, 4, 10 y 13; DEC-261 (decisión 6 del #34) y la
decisión 10 del #34 (T10-3).

Escritas desde las fuentes antes de leer la implementación de T25. Los datos y resultados
esperados se copian del REQ y de las RN. Las variantes que agregan una observación reciente
(agotada, usada, de vendedor externo…) a un escenario no llevan el marcador del escenario:
solo lo llevan las que reproducen el escenario tal cual (B9).

Fixtures sintéticos (DEC-194): comercios ficticios con subdominios de example.com; ninguna
prueba abre una URL. Instante explícito en ``America/Tijuana`` (PAR-01), sin reloj, sin red,
sin aleatoriedad y sin depender de la zona de la máquina.
"""

from __future__ import annotations

import datetime as dt
import itertools
import socket
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from config_tienda_prueba import BASE, TIENDA_PRUEBA, con_tienda_prueba
from oip.catalogos import CalidadPrecio, Canal, Marca, Motivo, Nivel, Resultado
from oip.configuracion import cargar_configuracion_texto
from oip.entradas.contrato import leer_observacion
from oip.evaluacion import canales, motor, referencias
from oip.evaluacion.contexto import ContextoEvaluacion, EvaluacionCanal, ObservacionRegistrada
from oip.evaluacion.descuento import DatosCalidad, calidad_del_precio

D = Decimal

# --- Configuración: base de los escenarios + tienda-prueba + cadenas sintéticas -----------
# tienda-prueba hace de Home Depot (cadena de la oferta); tienda-b de Walmart; cx de Target;
# cy y cz son dos cadenas más. La ficha de Amazon es el comercio ``amazon`` de la base.
_EXTRA = (
    "  tienda-b: {chain: cadena-b, domains: [b.example.com], amazon_listing: false}\n"
    "  cx: {chain: cadena-x, domains: [x.example.com], amazon_listing: false}\n"
    "  cy: {chain: cadena-y, domains: [y.example.com], amazon_listing: false}\n"
    "  cz: {chain: cadena-z, domains: [z.example.com], amazon_listing: false}\n"
)
_DOMINIO = {
    TIENDA_PRUEBA: "tienda.example.com",
    "tienda-b": "b.example.com",
    "cx": "x.example.com",
    "cy": "y.example.com",
    "cz": "z.example.com",
    "amazon": "amazon.example.com",
}


def _config(*reemplazos: tuple[str, str]):
    texto = con_tienda_prueba(BASE.read_text(encoding="utf-8"))
    texto = texto.replace("\nretailers:\n", "\nretailers:\n" + _EXTRA, 1)
    for viejo, nuevo in reemplazos:
        assert texto.count(viejo) == 1, viejo
        texto = texto.replace(viejo, nuevo)
    return cargar_configuracion_texto(texto, origen="t25-tester")


CONFIG = _config()
TIJUANA = ZoneInfo("America/Tijuana")
INSTANTE = dt.datetime(2026, 10, 14, 13, 0, tzinfo=TIJUANA)  # fuera de temporada (S-10)
PRODUCTO = UUID(int=0x2500_0000)
PUB_OFERTA = UUID(int=0x2500_0001)
ID_OFERTA = UUID(int=0x2500_0002)
PUB_AMAZON = UUID(int=0x2500_0003)
PUB_WALMART = UUID(int=0x2500_0004)
PUB_TARGET = UUID(int=0x2500_0005)

_ids = itertools.count(0x2500_1000)


def _uuid() -> UUID:
    return UUID(int=next(_ids))


def _hace(horas: float = 0, dias: int = 0, segundos: int = 0) -> dt.datetime:
    return INSTANTE - dt.timedelta(days=dias, hours=horas, seconds=segundos)


def _obs(
    precio: str,
    comercio: str = "cx",
    *,
    momento: dt.datetime,
    publicacion: UUID | None = None,
    ident: UUID | None = None,
    **cambios,
) -> ObservacionRegistrada:
    datos = {
        "retailerCode": comercio,
        "productUrl": f"https://{_DOMINIO[comercio]}/p/t25",
        "title": "Sierra circular sintética T25",
        "brand": "MarcaP",
        "model": "SC-25",
        "category": "tools",
        "price": {"current": precio, "currency": "USD"},
        "seller": "comercio",
        "condition": "new",
        "availability": {"state": "in_stock_confirmed"},
        "purchaseMode": "envio",
        "isClearance": False,
        "extractedAt": momento.isoformat(),
        "blocked": False,
    }
    datos.update(cambios)
    return ObservacionRegistrada(
        leer_observacion(datos),
        _uuid() if ident is None else ident,
        _uuid() if publicacion is None else publicacion,
        PRODUCTO,
    )


def _agotada(precio: str, comercio: str, publicacion: UUID, momento: dt.datetime):
    return _obs(
        precio,
        comercio,
        momento=momento,
        publicacion=publicacion,
        availability={"state": "out_of_stock"},
    )


def _ficha(buy_box: str | None, momento: dt.datetime, **listing) -> ObservacionRegistrada:
    return _obs(
        "999.00",
        "amazon",
        momento=momento,
        publicacion=PUB_AMAZON,
        amazonListing={"buyBoxPrice": buy_box, **listing},
    )


def _oferta_simple(precio: str = "80.00", **cambios) -> ObservacionRegistrada:
    """Oferta en línea de la cadena evaluada (tienda-prueba), hace 1 h."""
    return _obs(
        precio,
        TIENDA_PRUEBA,
        momento=_hace(1),
        publicacion=PUB_OFERTA,
        ident=ID_OFERTA,
        **cambios,
    )


def _contexto(oferta=None, historial=(), fichas=(), configuracion=CONFIG, **otros):
    return ContextoEvaluacion(
        id_evaluacion=UUID(int=0x2500_00FF),
        instante=INSTANTE,
        configuracion=configuracion,
        id_version_configuracion=1,
        oferta=_oferta_simple() if oferta is None else oferta,
        historial=tuple(historial),
        fichas_amazon=tuple(fichas),
        **otros,
    )


def _hoy(*historial, fichas=(), oferta=None):
    return referencias.mercado_hoy(_contexto(oferta, historial, fichas))


def _precio_hoy(*historial, fichas=(), oferta=None) -> Decimal | None:
    hoy = _hoy(*historial, fichas=fichas, oferta=oferta)
    return None if hoy is None else hoy.precio


def _y_120() -> ObservacionRegistrada:
    """Otra cadena (cy) a $120 hace 3 h, disponible confirmada: siempre cuenta."""
    return _obs("120.00", "cy", momento=_hace(3))


# =========================================================================================
# 1. DEC-261: primero la más reciente (≤ 48 h) de cada publicación, después el filtro (S-03)
# =========================================================================================

_AFECTADAS = {
    "agotada": {"availability": {"state": "out_of_stock"}},
    "usada": {"condition": "used"},
    "vendedor_externo": {"seller": "externo"},
    "en_linea_no_confirmada": {"availability": {"state": "unconfirmed"}},
    "en_linea_in_stock_sin_confirmar": {"availability": {"state": "in_stock"}},
    "en_linea_pocas_unidades": {"availability": {"state": "limited_stock"}},
}


@pytest.mark.parametrize("cambios", list(_AFECTADAS.values()), ids=list(_AFECTADAS))
def test_la_mas_reciente_que_no_cumple_saca_a_la_publicacion(cambios):
    """DEC-261: la publicación X estaba disponible a $95 hace 10 h; hace 1 h su observación
    más reciente (a $90) no cumple S-03 → X sale del mercado hoy aunque la anterior cumpla."""
    pub_x = _uuid()
    anterior = _obs("95.00", "cx", momento=_hace(10), publicacion=pub_x)
    reciente = _obs("90.00", "cx", momento=_hace(1), publicacion=pub_x, **cambios)

    # Control: sin la reciente, X cuenta con $95.
    control = _hoy(anterior, _y_120())
    assert control.precio == D("95.00")
    assert control.otras_cadenas == frozenset({"cadena-x", "cadena-y"})

    hoy = _hoy(anterior, reciente, _y_120())
    assert hoy is not None
    assert hoy.precio == D("120.00")
    assert hoy.otras_cadenas == frozenset({"cadena-y"})


@pytest.mark.parametrize("cambios", list(_AFECTADAS.values()), ids=list(_AFECTADAS))
def test_sin_otra_publicacion_no_hay_mercado_hoy(cambios):
    """Si la única publicación de otra cadena queda fuera, no hay precio de mercado hoy."""
    pub_x = _uuid()
    anterior = _obs("95.00", "cx", momento=_hace(10), publicacion=pub_x)
    reciente = _obs("90.00", "cx", momento=_hace(1), publicacion=pub_x, **cambios)
    assert _hoy(anterior, reciente) is None


def test_la_reciente_que_cumple_manda_aunque_la_anterior_no():
    """Simétrico: la anterior agotada no importa si la más reciente cumple."""
    pub_x = _uuid()
    hoy = _hoy(
        _agotada("80.00", "cx", pub_x, _hace(10)),
        _obs("97.00", "cx", momento=_hace(2), publicacion=pub_x),
        _y_120(),
    )
    assert hoy.precio == D("97.00")
    assert hoy.otras_cadenas == frozenset({"cadena-x", "cadena-y"})


def test_varias_publicaciones_solo_sale_la_afectada():
    """Tres publicaciones de dos cadenas: solo sale la que tiene un agotado reciente; la otra
    publicación de la misma cadena (cadena-x) sigue contando."""
    p1, p2, p3 = _uuid(), _uuid(), _uuid()
    historial = (
        _obs("95.00", "cx", momento=_hace(10), publicacion=p1),
        _agotada("90.00", "cx", p1, _hace(1)),
        _obs("100.00", "cx", momento=_hace(5), publicacion=p2),
        _obs("120.00", "cy", momento=_hace(3), publicacion=p3),
    )
    hoy = _hoy(*historial)
    assert hoy.precio == D("100.00")
    assert hoy.otras_cadenas == frozenset({"cadena-x", "cadena-y"})


def test_el_orden_del_historial_no_cambia_el_resultado():
    p1, p2 = _uuid(), _uuid()
    historial = [
        _obs("95.00", "cx", momento=_hace(10), publicacion=p1),
        _agotada("90.00", "cx", p1, _hace(1)),
        _obs("100.00", "cy", momento=_hace(5), publicacion=p2),
    ]
    assert _hoy(*historial) == _hoy(*reversed(historial))
    assert _precio_hoy(*historial) == D("100.00")


# --- Borde de 48 h (PAR-08 market_today_max_age_hours) -----------------------------------


def test_borde_48_h_exacto_cuenta():
    """RN-002 §4.1: "dato de 48 horas o menos"."""
    assert _precio_hoy(_obs("95.00", "cx", momento=_hace(48)), _y_120()) == D("95.00")


def test_pasadas_las_48_h_no_cuenta():
    assert _precio_hoy(_obs("95.00", "cx", momento=_hace(48, segundos=1)), _y_120()) == D("120.00")


def test_agotada_en_el_borde_exacto_saca_a_la_publicacion():
    """La más reciente dentro de 48 h es la agotada del borde (no hay otra más nueva)."""
    pub_x = _uuid()
    historial = (
        _obs("95.00", "cx", momento=_hace(60), publicacion=pub_x),  # fuera de 48 h
        _agotada("90.00", "cx", pub_x, _hace(48)),
        _y_120(),
    )
    assert _precio_hoy(*historial) == D("120.00")


def test_una_agotada_fuera_de_las_48_h_no_cuenta_como_la_mas_reciente():
    """La agotada fuera de la ventana es más vieja que la disponible: no afecta."""
    pub_x = _uuid()
    historial = (
        _agotada("90.00", "cx", pub_x, _hace(50)),
        _obs("95.00", "cx", momento=_hace(10), publicacion=pub_x),
        _y_120(),
    )
    assert _precio_hoy(*historial) == D("95.00")


def test_solo_observaciones_viejas_no_dan_mercado_hoy():
    pub_x = _uuid()
    assert _hoy(_obs("95.00", "cx", momento=_hace(49), publicacion=pub_x)) is None


# --- Observación posterior al instante (design.md §3: nada posterior entra al contexto) ---


def test_una_agotada_posterior_al_instante_no_saca_a_la_publicacion():
    pub_x = _uuid()
    historial = (
        _obs("95.00", "cx", momento=_hace(10), publicacion=pub_x),
        _agotada("90.00", "cx", pub_x, INSTANTE + dt.timedelta(hours=1)),
        _y_120(),
    )
    hoy = _hoy(*historial)
    assert hoy.precio == D("95.00")
    assert hoy.otras_cadenas == frozenset({"cadena-x", "cadena-y"})


def test_un_precio_posterior_al_instante_no_se_usa():
    pub_x = _uuid()
    historial = (
        _obs("95.00", "cx", momento=_hace(10), publicacion=pub_x),
        _obs("50.00", "cx", momento=INSTANTE + dt.timedelta(minutes=1), publicacion=pub_x),
        _y_120(),
    )
    assert _precio_hoy(*historial) == D("95.00")


def test_una_agotada_en_el_instante_exacto_es_la_mas_reciente():
    """Antigüedad 0 está dentro de "48 horas o menos"."""
    pub_x = _uuid()
    historial = (
        _obs("95.00", "cx", momento=_hace(10), publicacion=pub_x),
        _agotada("90.00", "cx", pub_x, INSTANTE),
        _y_120(),
    )
    assert _precio_hoy(*historial) == D("120.00")


# --- Mismo extractedAt en una publicación ------------------------------------------------


def test_mismo_instante_el_resultado_es_determinista():
    """Dos observaciones de X con el mismo extractedAt (una disponible, otra agotada): el
    resultado no depende del orden de entrada (RNF-3)."""
    pub_x = _uuid()
    momento = _hace(2)
    disponible = _obs("95.00", "cx", momento=momento, publicacion=pub_x)
    agotada = _agotada("90.00", "cx", pub_x, momento)
    a = _hoy(disponible, agotada, _y_120())
    b = _hoy(agotada, disponible, _y_120())
    assert a == b
    # Se toma una sola de las dos: el resultado es $95 (X cuenta) o $120 (X sale); nunca $90.
    assert a.precio in (D("95.00"), D("120.00"))


def test_mismo_instante_dos_precios_disponibles_determinista():
    pub_x = _uuid()
    momento = _hace(2)
    o1 = _obs("95.00", "cx", momento=momento, publicacion=pub_x)
    o2 = _obs("97.00", "cx", momento=momento, publicacion=pub_x)
    assert _hoy(o1, o2, _y_120()) == _hoy(o2, o1, _y_120())
    assert _precio_hoy(o1, o2, _y_120()) in (D("95.00"), D("97.00"))


# --- Tienda física: la confianza (RN-007 §4.1) es la de la más reciente -------------------


def _en_tienda(precio: str, publicacion: UUID, momento: dt.datetime, availability: dict):
    return _obs(
        precio,
        "cx",
        momento=momento,
        publicacion=publicacion,
        purchaseMode="tienda",
        storeCode="cx-001",
        availability=availability,
    )


def test_tienda_fisica_alta_cuenta():
    """Número exacto hace ≤ 6 h → confianza Alta (RN-007 §4.1) → cuenta (S-03)."""
    pub_x = _uuid()
    obs = _en_tienda("95.00", pub_x, _hace(4), {"state": "in_stock", "quantity": 10})
    assert _precio_hoy(obs, _y_120()) == D("95.00")


def test_tienda_fisica_la_mas_reciente_agotada_saca_a_la_publicacion():
    """Hace 4 h "10 disponibles" (Alta); hace 1 h agotada (Baja, DEC-268) → sale."""
    pub_x = _uuid()
    historial = (
        _en_tienda("95.00", pub_x, _hace(4), {"state": "in_stock", "quantity": 10}),
        _en_tienda("95.00", pub_x, _hace(1), {"state": "out_of_stock"}),
        _y_120(),
    )
    assert _precio_hoy(*historial) == D("120.00")


def test_tienda_fisica_la_mas_reciente_no_confirmada_saca_a_la_publicacion():
    pub_x = _uuid()
    historial = (
        _en_tienda("95.00", pub_x, _hace(4), {"state": "in_stock", "quantity": 10}),
        _en_tienda("93.00", pub_x, _hace(1), {"state": "unconfirmed"}),
        _y_120(),
    )
    assert _precio_hoy(*historial) == D("120.00")


def test_tienda_fisica_la_mas_reciente_vieja_con_confianza_baja_saca_a_la_publicacion():
    """Sin número, hace 20 h (más de 12 h) → no es Media; la anterior es aún más vieja."""
    pub_x = _uuid()
    historial = (
        _en_tienda("95.00", pub_x, _hace(30), {"state": "in_stock", "quantity": 10}),
        _en_tienda("95.00", pub_x, _hace(20), {"state": "in_stock"}),
        _y_120(),
    )
    assert _precio_hoy(*historial) == D("120.00")


def test_tienda_fisica_la_mas_reciente_media_cuenta():
    """Sin número, hace 5 h (≤ 12 h) → Media → cuenta con su precio."""
    pub_x = _uuid()
    historial = (
        _en_tienda("99.00", pub_x, _hace(30), {"state": "out_of_stock"}),
        _en_tienda("96.00", pub_x, _hace(5), {"state": "in_stock"}),
        _y_120(),
    )
    assert _precio_hoy(*historial) == D("96.00")


# --- Ficha de Amazon: sin botón de compra en la más reciente ------------------------------


def test_ficha_reciente_sin_boton_de_compra_saca_a_amazon():
    """La ficha de hace 5 h tenía botón de compra $110; la de hace 1 h no tiene (sin oferta
    nueva) → Amazon sale del mercado hoy (DEC-261)."""
    con_boton = _ficha("110.00", _hace(5))
    sin_boton = _ficha(None, _hace(1))

    control = _hoy(_y_120(), fichas=(con_boton,))
    assert control.precio == D("110.00")
    assert "amazon" in control.otras_cadenas

    hoy = _hoy(_y_120(), fichas=(con_boton, sin_boton))
    assert hoy.precio == D("120.00")
    assert hoy.otras_cadenas == frozenset({"cadena-y"})


def test_ficha_sin_boton_antes_y_con_boton_despues_cuenta():
    hoy = _hoy(_y_120(), fichas=(_ficha(None, _hace(5)), _ficha("110.00", _hace(1))))
    assert hoy.precio == D("110.00")


# --- No se cuentan la oferta evaluada ni otras observaciones de su publicación ------------


def test_la_publicacion_de_la_oferta_no_cuenta_aunque_sea_la_mas_barata():
    vieja_de_la_oferta = _obs("70.00", TIENDA_PRUEBA, momento=_hace(5), publicacion=PUB_OFERTA)
    assert _precio_hoy(vieja_de_la_oferta, _y_120()) == D("120.00")


# =========================================================================================
# 1b. La competencia más barata usa el mismo mercado hoy (RN-002 §4.3; B9)
# =========================================================================================
# Datos de B1 (REQ §5): sucursal en liquidación, $29.00 con tachado $129.00, "3 disponibles"
# hace 2 h, 4 kg, tienda a 7.75%; Amazon botón $119 hoy, ranking 6,000; mínimo de 60 días
# $109; Walmart $124 hoy (hace 8 h) y hace 60 días. Mercado hoy de B1: $119.


def _momento_b1(dias: int = 0, horas_antes: float = 0) -> dt.datetime:
    return INSTANTE + dt.timedelta(days=dias) - dt.timedelta(hours=horas_antes)


def _oferta_b1() -> ObservacionRegistrada:
    return _obs(
        "29.00",
        TIENDA_PRUEBA,
        momento=_momento_b1(horas_antes=2),
        publicacion=PUB_OFERTA,
        ident=ID_OFERTA,
        storeCode="hd-chula-vista",
        gtin="036000291452",
        weightKg="4",
        price={"current": "29.00", "was": "129.00", "currency": "USD"},
        availability={"state": "in_stock", "quantity": 3},
        isClearance=True,
        purchaseMode="tienda",
        taxLocation="tienda_prueba",
    )


def _fichas_b1():
    hoy = {"rankMain": 6000, "sellersNew": 5, "boughtLastMonth": 200}
    fichas = [_ficha("119.00", _momento_b1(horas_antes=2), **hoy)]
    fichas += [_ficha("119.00", _momento_b1(-d), rankMain=6000, sellersNew=5) for d in range(1, 7)]
    fichas += [_ficha(None, _momento_b1(-d), rankMain=6000, sellersNew=5) for d in range(30, 37)]
    fichas.append(_ficha("109.00", _momento_b1(-20), sellersNew=5))
    return fichas


def _historial_b1():
    return [
        _obs("124.00", "tienda-b", momento=_momento_b1(-60), publicacion=PUB_WALMART),
        _obs("124.00", "tienda-b", momento=_momento_b1(horas_antes=8), publicacion=PUB_WALMART),
    ]


def _contexto_b1(*extra):
    return _contexto(_oferta_b1(), [*_historial_b1(), *extra], _fichas_b1())


def _canal(registro, canal: Canal) -> EvaluacionCanal:
    return next(c for c in registro.canales if c.canal is canal)


def _target_99() -> ObservacionRegistrada:
    """B9: "Target la vende hoy a $99 (hace 10 h)"."""
    return _obs("99.00", "cx", momento=_momento_b1(horas_antes=10), publicacion=PUB_TARGET)


@pytest.mark.scenario("B9")
def test_b9_competencia_mas_barata():
    registro = motor.evaluar(_contexto_b1(_target_99()))
    assert registro.referencias.precio_mercado_hoy == D("99.00")
    amazon = _canal(registro, Canal.AMAZON)
    assert Marca.COMPETENCIA_MAS_BARATA.value in amazon.marcas
    assert amazon.nivel is Nivel.RECOMENDABLE
    assert amazon.unidades == 3
    assert amazon.ganancia_total == D("134.19")
    local = _canal(registro, Canal.LOCAL)
    assert local.precio_venta == D("75.74")
    assert local.margen_neto == D("34.99")
    assert local.nivel is Nivel.MUY_RECOMENDABLE
    assert local.ganancia_total == D("69.98")
    # "Resultado NIVEL_ASIGNADO = Recomendable, Amazon": el nivel del canal elegido.
    assert registro.resultado is Resultado.NIVEL_ASIGNADO
    assert registro.canal_elegido is Canal.AMAZON
    # REQ §5 B9: "el nivel del aviso sigue en Muy recomendable" (S-33: el más alto).
    assert registro.nivel_aviso is Nivel.MUY_RECOMENDABLE
    assert registro.calidad_precio is CalidadPrecio.BUENA_OFERTA


def test_b9_con_target_agotado_hace_1_h_no_hay_competencia_mas_barata():
    """DEC-261 en la competencia más barata: Target estaba a $99 hace 10 h y hace 1 h está
    agotado → sale; el mercado hoy vuelve a $119 (B1) y no hay competencia (119 ≥ 101.15):
    Amazon queda en Muy recomendable como en B1."""
    registro = motor.evaluar(
        _contexto_b1(_target_99(), _agotada("99.00", "cx", PUB_TARGET, _momento_b1(horas_antes=1)))
    )
    assert registro.referencias.precio_mercado_hoy == D("119.00")
    amazon = _canal(registro, Canal.AMAZON)
    assert Marca.COMPETENCIA_MAS_BARATA.value not in amazon.marcas
    assert Marca.COMPETENCIA_MAS_BARATA.value not in registro.marcas
    assert amazon.nivel is Nivel.MUY_RECOMENDABLE
    assert registro.nivel_aviso is Nivel.MUY_RECOMENDABLE
    assert registro.canal_aviso is Canal.AMAZON


def test_la_competencia_usa_el_valor_de_calcular_referencias():
    contexto = _contexto_b1(
        _target_99(), _agotada("99.00", "cx", PUB_TARGET, _momento_b1(horas_antes=1))
    )
    refs = referencias.calcular_referencias(contexto)
    assert refs.precio_mercado_hoy == referencias.mercado_hoy(contexto).precio == D("119.00")
    assert refs.precio_venta_amazon == D("119.00")
    umbral = D(CONFIG.contenido.levels.cheaper_competition_pct)
    assert umbral == D(15)
    assert not canales.competencia_mas_barata(
        refs.precio_mercado_hoy, refs.precio_venta_amazon, umbral
    )
    # Con el valor viejo (filtrar antes de tomar la más reciente) sí habría competencia.
    assert canales.competencia_mas_barata(D("99.00"), refs.precio_venta_amazon, umbral)


def test_b14_ficha_reciente_sin_boton_saca_a_amazon_del_mercado_hoy():
    """B14 ("Amazon no tiene oferta nueva hoy"): con la ficha más reciente sin botón de
    compra, el mercado hoy es Walmart $124 aunque una ficha de hace 30 h tuviera botón."""
    fichas = [
        _ficha("119.00", _momento_b1(horas_antes=30), rankMain=6000, sellersNew=5),
        _ficha(None, _momento_b1(horas_antes=2), rankMain=6000, sellersNew=5),
    ]
    contexto = _contexto(_oferta_b1(), _historial_b1(), fichas)
    hoy = referencias.mercado_hoy(contexto)
    assert hoy.precio == D("124.00")
    assert hoy.otras_cadenas == frozenset({"cadena-b"})


# --- La reproducción de T10-1 (#34) de punta a punta --------------------------------------


def test_t10_1_reproduccion_de_punta_a_punta():
    """#34, T10-1: habitual $100, oferta $80, publicación X a $90 hace 10 h y agotada hace
    1 h, cadena Y a $120 hace 2 h → mercado hoy $120 con 1 cadena → calidad Precio
    competitivo (RN-012 §4: menos de 2 comercios; S-28: con habitual no es cuestionable)."""
    pub_x = _uuid()
    habitual = [
        _obs("100.00", "cz", momento=_hace(dias=d), publicacion=PUB_WALMART)
        for d in range(10, 5, -1)
    ]
    historial = [
        *habitual,
        _obs("90.00", "cx", momento=_hace(10), publicacion=pub_x),
        _agotada("90.00", "cx", pub_x, _hace(1)),
        _obs("120.00", "cy", momento=_hace(2)),
    ]
    registro = motor.evaluar(_contexto(_oferta_simple("80.00"), historial))
    assert registro.referencias.precio_habitual == D("100.00")
    assert registro.referencias.precio_mercado_hoy == D("120.00")
    assert registro.calidad_precio is CalidadPrecio.PRECIO_COMPETITIVO


# =========================================================================================
# 2. Decisión 10 (#34): PRECIO ANTES INFLADO se revisa antes de "sin datos" (RN-012 §3)
# =========================================================================================


def _params():
    """PAR-10 ``discount_quality`` de la configuración de los escenarios."""
    return CONFIG.contenido.discount_quality


def _datos(**cambios) -> DatosCalidad:
    base = {
        "precio": D("80.00"),
        "precio_habitual": None,
        "descuento_real": None,
        "precio_mercado_hoy": None,
        "otros_comercios": 0,
        "minimo_registrado": None,
        "dias_historial": 0,
        "descuento_anunciado": D("60"),
        "precio_antes_inflado": False,
    }
    base.update(cambios)
    return DatosCalidad(**base)


def test_inflado_sin_habitual_ni_mercado_hoy_es_cuestionable():
    assert (
        calidad_del_precio(_datos(precio_antes_inflado=True), _params())
        is CalidadPrecio.DESCUENTO_CUESTIONABLE
    )


def test_sin_marca_y_sin_datos_sigue_sin_calidad():
    assert calidad_del_precio(_datos(), _params()) is None
    assert calidad_del_precio(_datos(descuento_anunciado=None), _params()) is None


@pytest.mark.parametrize(
    "cambios",
    [
        # Con habitual y mercado hoy, 50% de descuento, el más barato, 3 comercios, 120 días
        # y bajo el mínimo: sin la marca sería Oferta excepcional.
        {
            "precio_habitual": D("160.00"),
            "descuento_real": D("50"),
            "precio_mercado_hoy": D("80.00"),
            "otros_comercios": 3,
            "minimo_registrado": D("90.00"),
            "dias_historial": 120,
        },
        # Solo habitual (sin mercado hoy).
        {"precio_habitual": D("160.00"), "descuento_real": D("50"), "dias_historial": 30},
        # Solo mercado hoy (sin habitual).
        {"precio_mercado_hoy": D("85.00"), "otros_comercios": 3},
    ],
    ids=["habitual_y_mercado", "solo_habitual", "solo_mercado_hoy"],
)
def test_con_datos_cuestionable_sigue_primero(cambios):
    sin_marca = calidad_del_precio(_datos(**cambios), _params())
    assert sin_marca is not None and sin_marca is not CalidadPrecio.DESCUENTO_CUESTIONABLE
    con_marca = calidad_del_precio(_datos(precio_antes_inflado=True, **cambios), _params())
    assert con_marca is CalidadPrecio.DESCUENTO_CUESTIONABLE


def test_inflado_sin_habitual_de_punta_a_punta():
    """Única forma de llegar por el motor (#34, T10-3): una ventana del precio típico de la
    tienda mayor que la del habitual. Típico de tienda-prueba $100 (hace 45 días), sin
    observaciones en los 30 días del habitual y sin mercado hoy; oferta $80 con tachado
    $200 (> 1.5 × 100) → PRECIO ANTES INFLADO → Descuento cuestionable."""
    config = _config(
        ("usual_window_days: 60", "usual_window_days: 30"),
    )
    assert config.contenido.price_reference.store_typical_window_days == 60
    pub_tp = _uuid()
    historial = [
        _obs("100.00", TIENDA_PRUEBA, momento=_hace(dias=d), publicacion=pub_tp)
        for d in (45, 44, 43, 42, 41)
    ]
    oferta = _oferta_simple("80.00", price={"current": "80.00", "was": "200.00", "currency": "USD"})
    registro = motor.evaluar(_contexto(oferta, historial, configuracion=config))
    assert registro.referencias.precio_habitual is None
    assert registro.referencias.precio_mercado_hoy is None
    assert Marca.PRECIO_ANTES_INFLADO.value in registro.marcas
    assert registro.calidad_precio is CalidadPrecio.DESCUENTO_CUESTIONABLE
    assert Motivo.SIN_HISTORIAL_SUFICIENTE in registro.motivos


# =========================================================================================
# 3. Sin red
# =========================================================================================


def test_las_pruebas_no_abren_conexiones(monkeypatch):
    def _prohibido(*_a, **_k):
        raise AssertionError("una prueba de T25 intentó abrir una conexión")

    monkeypatch.setattr(socket, "socket", _prohibido)
    monkeypatch.setattr(socket, "create_connection", _prohibido)
    pub_x = _uuid()
    _hoy(
        _obs("95.00", "cx", momento=_hace(10), publicacion=pub_x),
        _agotada("90.00", "cx", pub_x, _hace(1)),
    )
    motor.evaluar(_contexto_b1(_target_99()))
