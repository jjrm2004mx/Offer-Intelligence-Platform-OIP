"""Pruebas independientes de oip-tester para T10 (descuento, franja, mercado hoy y calidad).

Capacidad ``referencias-de-precio``; REQ-2026-0001 §3.2 pasos 3 a 5, §3.2.3 (motivos y
marcas), §3.2.4 (precedencia), §5 B6 y B7 y §13 S-03, S-22 y S-28; RN-002 v2 §4.1, RN-003 v2
§4 y §11, RN-007 v2 §4.1 y §4.2, RN-012 v1 §4, §5 y §11; design.md §8, §10 punto 4 y §12.

Los datos y los resultados esperados se copian del REQ y de las RN (precios, porcentajes,
clases y motivos), no del código. Donde el escenario da un "Dado" parcial (B6, B7), el
fixture completa el resto con datos neutros que no agregan motivos de mayor precedencia
(design.md §12) y la prueba verifica solo lo que el escenario afirma. Las pruebas que
reproducen números de otros escenarios (B1, B2, B3, B9, B14, B29) **no** llevan su marcador:
esos escenarios son de otras tareas; aquí solo se comprueban la marca, el descuento y la
calidad que T10 construye.

Fixtures sintéticos (DEC-194): comercios ficticios con subdominios de example.com; ninguna
prueba abre una URL. Instante explícito en ``America/Tijuana`` (PAR-01), sin reloj, sin red,
sin aleatoriedad y sin depender de la zona de la máquina.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import itertools
import re
import socket
from decimal import Decimal
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from config_tienda_prueba import BASE, TIENDA_PRUEBA, con_tienda_prueba
from oip.catalogos import (
    CalidadPrecio,
    Canal,
    EstadoCanal,
    Marca,
    Motivo,
    Nivel,
    Resultado,
)
from oip.configuracion import cargar_configuracion_texto
from oip.dinero import formatear_porcentaje
from oip.entradas.capturas import leer_captura
from oip.entradas.contrato import leer_observacion
from oip.evaluacion import descuento, motor, referencias
from oip.evaluacion.contexto import (
    ContextoEvaluacion,
    EvaluacionCanal,
    ObservacionRegistrada,
)

RAIZ = Path(__file__).resolve().parent
SRC_EVALUACION = RAIZ.parent / "src" / "oip" / "evaluacion"

# --- Configuración: la base de los escenarios + tienda-prueba + comercios sintéticos -------
# ``tp-sucursal`` es otra tienda de la cadena de la oferta; X, Y y Z son tres cadenas más;
# la ficha de Amazon es el comercio ``amazon`` de la base (cadena ``amazon``); su URL es
# sintética (amazon.example.com) y nadie la abre.
_EXTRA = (
    "  tp-sucursal: {chain: tienda-prueba, domains: [sucursal.example.com], "
    "amazon_listing: false}\n"
    "  cx: {chain: cadena-x, domains: [x.example.com], amazon_listing: false}\n"
    "  cy: {chain: cadena-y, domains: [y.example.com], amazon_listing: false}\n"
    "  cz: {chain: cadena-z, domains: [z.example.com], amazon_listing: false}\n"
)
_DOMINIO = {
    TIENDA_PRUEBA: "tienda.example.com",
    "tp-sucursal": "sucursal.example.com",
    "cx": "x.example.com",
    "cy": "y.example.com",
    "cz": "z.example.com",
    "amazon": "amazon.example.com",
}


def _texto(*reemplazos: tuple[str, str]) -> str:
    texto = con_tienda_prueba(BASE.read_text(encoding="utf-8"))
    texto = texto.replace("\nretailers:\n", "\nretailers:\n" + _EXTRA, 1)
    for viejo, nuevo in reemplazos:
        assert texto.count(viejo) == 1, viejo
        texto = texto.replace(viejo, nuevo)
    return texto


def _config(*reemplazos: tuple[str, str]):
    return cargar_configuracion_texto(_texto(*reemplazos), origen="t10-tester")


CONFIG = _config()
TIJUANA = ZoneInfo("America/Tijuana")
HOY = dt.date(2026, 11, 16)  # día 0
INSTANTE = dt.datetime(2026, 11, 16, 14, 0, tzinfo=TIJUANA)
PRODUCTO = UUID(int=0x7100_0000)
PUB_OFERTA = UUID(int=0x7100_0001)
ID_OFERTA = UUID(int=0x7100_0002)

_ids = itertools.count(0x7100_1000)


def _uuid() -> UUID:
    return UUID(int=next(_ids))


def _hace(horas: float = 0, dias: int = 0) -> dt.datetime:
    return INSTANTE - dt.timedelta(days=dias, hours=horas)


def _obs(
    precio: str,
    comercio: str = "cx",
    *,
    momento: dt.datetime | None = None,
    publicacion: UUID | None = None,
    ident: UUID | None = None,
    was: str | None = None,
    estado: str = "in_stock_confirmed",
    cantidad: int | None = None,
    modo: str = "envio",
    tienda: str | None = None,
    liquidacion: bool = False,
    seller: str = "comercio",
    condition: str | None = "new",
    ficha: dict | None = None,
) -> ObservacionRegistrada:
    price = {"current": precio, "currency": "USD"}
    if was is not None:
        price["was"] = was
    availability: dict = {"state": estado}
    if cantidad is not None:
        availability["quantity"] = cantidad
    datos = {
        "retailerCode": comercio,
        "productUrl": f"https://{_DOMINIO[comercio]}/p/t10",
        "title": "Producto sintético T10",
        "brand": "MarcaT",
        "model": "MT-10",
        "category": "tools",
        "price": price,
        "seller": seller,
        "availability": availability,
        "purchaseMode": modo,
        "isClearance": liquidacion,
        "extractedAt": (momento or _hace(2)).isoformat(),
        "blocked": False,
    }
    if condition is not None:
        datos["condition"] = condition
    if tienda is not None:
        datos["storeCode"] = tienda
    if ficha is not None:
        datos["amazonListing"] = ficha
    return ObservacionRegistrada(
        leer_observacion(datos),
        _uuid() if ident is None else ident,
        _uuid() if publicacion is None else publicacion,
        PRODUCTO,
    )


def _oferta(precio: str, was: str | None = None, **cambios) -> ObservacionRegistrada:
    cambios.setdefault("momento", _hace(1))
    return _obs(precio, TIENDA_PRUEBA, publicacion=PUB_OFERTA, ident=ID_OFERTA, was=was, **cambios)


def _ficha(buy_box: str | None, horas: float = 2) -> ObservacionRegistrada:
    return _obs("1.00", "amazon", momento=_hace(horas), ficha={"buyBoxPrice": buy_box})


def _serie(precio: str, dias, comercio: str = "cx") -> list[ObservacionRegistrada]:
    """Una observación diaria de una publicación, en los días indicados (días antes de hoy)."""
    pub = _uuid()
    return [_obs(precio, comercio, momento=_hace(dias=d), publicacion=pub) for d in dias]


def _msrp(valor: str, fecha: str = "2026-11-01"):
    datos = {"brand": "MarcaT", "model": "MT-10", "value": valor, "source": "fab", "date": fecha}
    return leer_captura("msrp", datos, zona=TIJUANA)


def _contexto(oferta, historial=(), fichas=(), msrp=(), configuracion=CONFIG):
    return ContextoEvaluacion(
        id_evaluacion=UUID(int=0x7100_00FF),
        instante=INSTANTE,
        configuracion=configuracion,
        id_version_configuracion=1,
        oferta=oferta,
        historial=tuple(historial),
        fichas_amazon=tuple(fichas),
        msrp=tuple(msrp),
    )


def _evaluar(*args, **kwargs):
    return motor.evaluar(_contexto(*args, **kwargs))


def _con_habitual(precio: str = "100.00") -> list[ObservacionRegistrada]:
    """Historial suficiente (5 observaciones en 5 días, de otra cadena) con mediana ``precio``,
    sin dato de hoy: el habitual existe y no hay precio de mercado hoy."""
    return _serie(precio, range(10, 5, -1), "cy")


def _pct(valor: Decimal | None) -> str:
    assert valor is not None
    return formatear_porcentaje(valor)


# =========================================================================================
# Escenarios (REQ §5)
# =========================================================================================


def _b6_historial():
    # "3 observaciones en 2 días" antes de hoy (no alcanza 5 en 3 días) y "hoy otros 3
    # comercios a $179, $185 y $189", de tres cadenas distintas de la evaluada.
    return [
        _obs("189.00", "cx", momento=_hace(dias=2)),
        _obs("189.00", "cy", momento=_hace(dias=2, horas=1)),
        _obs("189.00", "cz", momento=_hace(dias=1)),
        _obs("179.00", "cx", momento=_hace(3)),
        _obs("185.00", "cy", momento=_hace(5)),
        _obs("189.00", "cz", momento=_hace(7)),
    ]


@pytest.mark.scenario("B6")
def test_b6_sin_historial_suficiente():
    contexto = _contexto(_oferta("169.00"), _b6_historial(), msrp=[_msrp("199.00")])
    r = motor.evaluar(contexto)
    # No hay descuento real ni nivel (nivel_calculado no disponible).
    assert r.referencias is not None and r.referencias.precio_habitual is None
    assert r.descuento_real is None
    assert r.nivel_aviso is None and r.canal_aviso is None
    assert all(c.nivel is None and c.nivel_calculado is None for c in r.canales)
    # Calidad Precio competitivo (169 ≤ 182.58).
    assert r.referencias.precio_mercado_hoy == Decimal("179.00")
    assert Decimal("179.00") * (1 + Decimal(2) / 100) == Decimal("182.58")
    assert r.calidad_precio is CalidadPrecio.PRECIO_COMPETITIVO
    # MSRP $199: solo se muestra.
    assert r.referencias.msrp == Decimal("199.00")
    # Resultado REVISION_MANUAL, motivo SIN HISTORIAL SUFICIENTE.
    assert r.resultado is Resultado.REVISION_MANUAL
    assert r.motivo_principal is Motivo.SIN_HISTORIAL_SUFICIENTE
    assert r.motivos == (Motivo.SIN_HISTORIAL_SUFICIENTE,)


@pytest.mark.scenario("B7")
def test_b7_solo_referencia():
    r = _evaluar(_oferta("80.00"), _con_habitual("100.00"))
    assert r.referencias.precio_habitual == Decimal("100.00")
    # Real 20.0%.
    assert r.descuento_real == Decimal(20)
    assert _pct(r.descuento_real) == "20.0 %"
    # Resultado SOLO_REFERENCIA.
    assert r.resultado is Resultado.SOLO_REFERENCIA
    assert r.motivo_principal is Motivo.SOLO_REFERENCIA
    assert r.motivos == (Motivo.SOLO_REFERENCIA,)
    # No se calculan unidades, días, rendimiento ni nivel.
    for canal in r.canales:
        assert canal.unidades is None
        assert canal.dias_para_recuperar is None
        assert canal.rendimiento_mensual_pct is None
        assert canal.nivel is None and canal.nivel_calculado is None
    assert r.nivel_aviso is None


# =========================================================================================
# B6: bordes y variantes del "Dado"
# =========================================================================================


@pytest.mark.parametrize(
    ("precio", "calidad"),
    [
        ("182.58", CalidadPrecio.PRECIO_COMPETITIVO),  # = 179 × 1.02: entre los más baratos
        ("182.59", CalidadPrecio.PRECIO_NORMAL),  # S-22: sin historial y fuera → normal
    ],
)
def test_b6_borde_de_entre_los_mas_baratos(precio, calidad):
    r = _evaluar(_oferta(precio), _b6_historial(), msrp=[_msrp("199.00")])
    assert r.calidad_precio is calidad
    assert r.resultado is Resultado.REVISION_MANUAL


@pytest.mark.parametrize("valor", [None, "169.00", "1000.00", "100.00"])
def test_b6_el_msrp_no_entra_en_ningun_calculo(valor):
    """DEC-218: con o sin MSRP, y sea cual sea, la calidad y el resultado no cambian. Un MSRP
    de $1000 daría 83% de "descuento": no se convierte en descuento real ni en Buena oferta."""
    msrp = [] if valor is None else [_msrp(valor)]
    r = _evaluar(_oferta("169.00"), _b6_historial(), msrp=msrp)
    assert r.calidad_precio is CalidadPrecio.PRECIO_COMPETITIVO
    assert r.descuento_real is None
    assert r.resultado is Resultado.REVISION_MANUAL
    assert r.motivos == (Motivo.SIN_HISTORIAL_SUFICIENTE,)
    assert r.referencias.msrp == (None if valor is None else Decimal(valor))


def test_b6_con_los_3_comercios_de_hoy_como_toda_su_historia():
    """Otra lectura de "3 observaciones en 2 días": las de los 3 comercios, una de ayer. El
    habitual no incluye el día evaluado, así que tampoco hay historial suficiente."""
    historial = [
        _obs("179.00", "cx", momento=_hace(3)),
        _obs("185.00", "cy", momento=_hace(5)),
        _obs("189.00", "cz", momento=_hace(23)),  # ayer, dentro de 48 h
    ]
    r = _evaluar(_oferta("169.00"), historial, msrp=[_msrp("199.00")])
    assert r.referencias.precio_habitual is None
    assert r.calidad_precio is CalidadPrecio.PRECIO_COMPETITIVO
    assert r.motivo_principal is Motivo.SIN_HISTORIAL_SUFICIENTE


def test_b6_sin_historial_no_pasa_de_precio_competitivo_aunque_sea_mucho_mas_barato():
    """RN-012 §4: sin historial suficiente nunca pasa de Precio competitivo (ejemplo D)."""
    r = _evaluar(_oferta("50.00"), _b6_historial(), msrp=[_msrp("199.00")])
    assert r.calidad_precio is CalidadPrecio.PRECIO_COMPETITIVO


# =========================================================================================
# Franjas del descuento real (RN-003 §4), porcentajes sin redondear
# =========================================================================================


@pytest.mark.parametrize(
    ("precio", "motivo", "mostrado"),
    [
        ("80.04", Motivo.MERCADO_YA_BARATO, "20.0 %"),  # 19.96: se muestra 20.0 y descarta
        ("80.01", Motivo.MERCADO_YA_BARATO, "20.0 %"),  # 19.99
        ("80.00", Motivo.SOLO_REFERENCIA, "20.0 %"),  # 20 exacto: solo referencia
        ("75.04", Motivo.SOLO_REFERENCIA, "25.0 %"),  # 24.96: se muestra 25.0 y no sigue
        ("75.01", Motivo.SOLO_REFERENCIA, "25.0 %"),  # 24.99
        ("75.00", None, "25.0 %"),  # 25 exacto: sigue
        ("120.00", Motivo.MERCADO_YA_BARATO, "-20.0 %"),  # negativo (RN-003 §11)
        ("100.00", Motivo.MERCADO_YA_BARATO, "0.0 %"),
    ],
)
def test_franjas_en_los_bordes_sin_redondear(precio, motivo, mostrado):
    r = _evaluar(_oferta(precio), _con_habitual("100.00"))
    assert _pct(r.descuento_real) == mostrado
    motivos_de_franja = {Motivo.MERCADO_YA_BARATO, Motivo.SOLO_REFERENCIA}
    assert [m for m in r.motivos if m in motivos_de_franja] == ([] if motivo is None else [motivo])
    assert Motivo.SIN_HISTORIAL_SUFICIENTE not in r.motivos


def test_franja_con_un_porcentaje_periodico():
    """Habitual $119 y oferta $95.20 → exactamente 20% (sin redondeo); $95.21 → 19.99…%."""
    assert (
        descuento.franja(
            descuento.descuento_real(Decimal("119"), Decimal("95.20")),
            CONFIG.contenido.discount_quality,
        )
        is Motivo.SOLO_REFERENCIA
    )
    assert (
        descuento.franja(
            descuento.descuento_real(Decimal("119"), Decimal("95.21")),
            CONFIG.contenido.discount_quality,
        )
        is Motivo.MERCADO_YA_BARATO
    )


def test_los_cortes_de_la_franja_salen_de_la_configuracion():
    config = _config(("reference_only_below_pct: 25", "reference_only_below_pct: 30"))
    r = _evaluar(_oferta("72.00"), _con_habitual("100.00"), configuracion=config)  # 28%
    assert r.motivos == (Motivo.SOLO_REFERENCIA,)
    config = _config(("discard_below_pct: 20", "discard_below_pct: 10"))
    r = _evaluar(_oferta("85.00"), _con_habitual("100.00"), configuracion=config)  # 15%
    assert r.motivos == (Motivo.SOLO_REFERENCIA,)


# =========================================================================================
# Descuento anunciado y marcas (RN-003 §4, §11)
# =========================================================================================


@pytest.mark.parametrize(
    ("tachado", "precio", "mostrado"),
    [("129.00", "29.00", "77.5 %"), ("199.00", "79.00", "60.3 %"), ("200.00", "20.00", "90.0 %")],
)
def test_descuento_anunciado_de_b1_b2_b3(tachado, precio, mostrado):
    r = _evaluar(_oferta(precio, was=tachado), _con_habitual("119.00"))
    assert _pct(r.descuento_anunciado) == mostrado
    esperado = (1 - Decimal(precio) / Decimal(tachado)) * 100
    assert abs(r.descuento_anunciado - esperado) < Decimal("1e-20")  # sin redondear


def test_sin_precio_tachado_el_anunciado_no_esta_disponible_y_no_hay_marcas():
    r = _evaluar(_oferta("29.00"), _con_habitual("119.00"))
    assert r.descuento_anunciado is None
    assert Marca.DESCUENTO_ANUNCIADO_NO_COMPROBADO.value not in r.marcas
    assert Marca.PRECIO_ANTES_INFLADO.value not in r.marcas


def _historial_b1(hoy_x: str | None = "124.00", amazon_hoy: str | None = "119.00"):
    """B1: precio habitual $119 (8 observaciones en 6 días, 60 días de historial) de otras
    cadenas (la tienda de la oferta no tiene historial propio); hoy Amazon (botón de compra)
    $119 y otra cadena $124 hace 8 h."""
    historial = [
        _obs("119.00", "cy", momento=_hace(dias=60)),
        _obs("119.00", "cy", momento=_hace(dias=50)),
        _obs("119.00", "cy", momento=_hace(dias=40)),
        _obs("119.00", "cy", momento=_hace(dias=30)),
        _obs("124.00", "cx", momento=_hace(dias=20)),
        _obs("124.00", "cx", momento=_hace(dias=10)),
        _obs("115.00", "cz", momento=_hace(dias=10, horas=1)),
        _obs("112.00", "cz", momento=_hace(dias=10, horas=2)),
    ]
    if hoy_x is not None:
        historial.append(_obs(hoy_x, "cx", momento=_hace(8)))
    fichas = [] if amazon_hoy is None else [_ficha(amazon_hoy)]
    return historial, fichas


def test_b1_descuento_anunciado_no_comprobado_y_buena_oferta():
    historial, fichas = _historial_b1()
    r = _evaluar(_oferta("29.00", was="129.00", liquidacion=True), historial, fichas)
    assert r.referencias.precio_habitual == Decimal("119.00")
    assert _pct(r.descuento_anunciado) == "77.5 %"
    assert _pct(r.descuento_real) == "75.6 %"
    assert Marca.DESCUENTO_ANUNCIADO_NO_COMPROBADO.value in r.marcas
    assert Marca.PRECIO_ANTES_INFLADO.value not in r.marcas
    assert r.referencias.precio_mercado_hoy == Decimal("119.00")
    # Buena oferta (2 comercios; 60 días < 90).
    assert r.calidad_precio is CalidadPrecio.BUENA_OFERTA
    # La marca no cambia el resultado: sin motivos de T10.
    assert r.motivos == ()


def test_b9_con_un_comercio_mas_barato_la_calidad_sigue_en_buena_oferta():
    historial, fichas = _historial_b1()
    historial.append(_obs("99.00", "cz", momento=_hace(10)))
    r = _evaluar(_oferta("29.00", was="129.00"), historial, fichas)
    assert r.referencias.precio_mercado_hoy == Decimal("99.00")
    assert r.calidad_precio is CalidadPrecio.BUENA_OFERTA  # 29 ≤ 100.98


def test_b14_con_habitual_y_un_solo_comercio_no_pasa_de_precio_competitivo():
    """S-28: con precio habitual, el anunciado se considera comparado; con menos de 2
    comercios, la calidad no pasa de Precio competitivo (B14: Walmart $124, 1 comercio)."""
    historial, _ = _historial_b1(hoy_x="124.00", amazon_hoy=None)
    r = _evaluar(_oferta("29.00", was="129.00"), historial)
    assert r.referencias.precio_mercado_hoy == Decimal("124.00")
    assert r.calidad_precio is CalidadPrecio.PRECIO_COMPETITIVO


def _historial_tienda(precio: str, dias=range(10, 5, -1), comercio: str = TIENDA_PRUEBA):
    return _serie(precio, dias, comercio)


def test_b3_precio_antes_inflado_mercado_ya_barato_y_descuento_cuestionable():
    """B3 / RN-003 ejemplo A: tienda a $25 en 60 días, tachado $200 > 37.50 → inflado; habitual
    $22 → real 9.1% → MERCADO YA BARATO; calidad Descuento cuestionable; hoy solo Amazon $22."""
    historial = _historial_tienda("25.00") + _serie("22.00", range(16, 10, -1), "cy")
    r = _evaluar(_oferta("20.00", was="200.00"), historial, [_ficha("22.00")])
    assert referencias.precio_tipico_de_la_tienda(
        _contexto(_oferta("20.00", was="200.00"), historial)
    ) == Decimal("25.00")
    assert r.referencias.precio_habitual == Decimal("22.00")
    assert _pct(r.descuento_anunciado) == "90.0 %"
    assert Marca.PRECIO_ANTES_INFLADO.value in r.marcas
    assert Marca.DESCUENTO_ANUNCIADO_NO_COMPROBADO.value not in r.marcas
    assert _pct(r.descuento_real) == "9.1 %"
    assert r.motivo_principal is Motivo.MERCADO_YA_BARATO
    assert r.calidad_precio is CalidadPrecio.DESCUENTO_CUESTIONABLE


@pytest.mark.parametrize(
    ("tachado", "inflado"),
    [("37.50", False), ("37.51", True), ("223.50", None)],
)
def test_inflado_es_estrictamente_mayor_que_1_5_veces(tachado, inflado):
    tipico = "25.00" if inflado is not None else "149.00"
    historial = _historial_tienda(tipico) + _con_habitual("30.00")
    r = _evaluar(_oferta("20.00", was=tachado), historial)
    assert (Marca.PRECIO_ANTES_INFLADO.value in r.marcas) is bool(inflado)
    assert Marca.DESCUENTO_ANUNCIADO_NO_COMPROBADO.value not in r.marcas


def test_b2_no_inflado_199_contra_223_50():
    historial = _historial_tienda("149.00") + _serie("149.00", range(20, 15, -1), "cy")
    r = _evaluar(_oferta("79.00", was="199.00"), historial)
    assert _pct(r.descuento_anunciado) == "60.3 %"
    assert _pct(r.descuento_real) == "47.0 %"
    assert Marca.PRECIO_ANTES_INFLADO.value not in r.marcas
    assert Marca.DESCUENTO_ANUNCIADO_NO_COMPROBADO.value not in r.marcas


def test_el_precio_tipico_de_la_tienda_usa_la_cadena_y_no_las_demas():
    """La otra tienda de la misma cadena cuenta (design.md §10.1); otra cadena, no."""
    solo_otra_cadena = _serie("25.00", range(10, 5, -1), "cx")
    r = _evaluar(_oferta("20.00", was="200.00"), solo_otra_cadena)
    assert Marca.DESCUENTO_ANUNCIADO_NO_COMPROBADO.value in r.marcas
    misma_cadena = _serie("25.00", range(10, 5, -1), "tp-sucursal")
    r = _evaluar(_oferta("20.00", was="200.00"), misma_cadena)
    assert Marca.PRECIO_ANTES_INFLADO.value in r.marcas


def test_historial_de_la_tienda_insuficiente_da_no_comprobado():
    """4 observaciones (no 5) de la tienda: no hay precio típico → no comprobado."""
    historial = _historial_tienda("25.00", range(10, 6, -1)) + _con_habitual("22.00")
    r = _evaluar(_oferta("20.00", was="200.00"), historial)
    assert Marca.DESCUENTO_ANUNCIADO_NO_COMPROBADO.value in r.marcas
    assert Marca.PRECIO_ANTES_INFLADO.value not in r.marcas


def test_el_factor_de_inflado_sale_de_la_configuracion():
    config = _config(("inflated_factor: 1.5", "inflated_factor: 10"))
    historial = _historial_tienda("25.00") + _con_habitual("22.00")
    r = _evaluar(_oferta("20.00", was="200.00"), historial, configuracion=config)
    assert Marca.PRECIO_ANTES_INFLADO.value not in r.marcas


def test_las_marcas_no_cambian_el_resultado():
    """§3.2.3: marcas informativas. Con real ≥ 25% y la marca, no se agrega ningún motivo."""
    historial = _historial_tienda("25.00") + _serie("100.00", range(30, 20, -1), "cy")
    r = _evaluar(_oferta("20.00", was="200.00"), historial)
    assert Marca.PRECIO_ANTES_INFLADO.value in r.marcas
    assert r.motivos == ()


# =========================================================================================
# Calidad del precio (RN-012 §4 con S-22 y S-28)
# =========================================================================================


def _dos_comercios_hoy(a: str, b: str):
    return [_obs(a, "cx", momento=_hace(3)), _obs(b, "cz", momento=_hace(4))]


def test_rn012_ejemplo_e_precio_normal():
    """$105 con habitual $110 (4.5%) y el más barato hoy a $95 → 105 > 96.90 → Precio normal."""
    historial = _con_habitual("110.00") + _dos_comercios_hoy("95.00", "120.00")
    r = _evaluar(_oferta("105.00"), historial)
    assert r.calidad_precio is CalidadPrecio.PRECIO_NORMAL


@pytest.mark.parametrize(
    ("precio", "calidad"),
    [
        ("85.00", CalidadPrecio.BUENA_OFERTA),  # 15% exacto
        ("85.01", CalidadPrecio.PRECIO_COMPETITIVO),  # 14.99%
    ],
)
def test_borde_del_15_por_ciento_sin_redondear(precio, calidad):
    historial = _con_habitual("100.00") + _dos_comercios_hoy("86.00", "90.00")
    r = _evaluar(_oferta(precio), historial)
    assert r.calidad_precio is calidad


def test_arriba_del_habitual_es_precio_normal_aunque_sea_el_mas_barato():
    """S-22: precio arriba del habitual → Precio normal."""
    historial = _con_habitual("100.00") + _dos_comercios_hoy("120.00", "130.00")
    r = _evaluar(_oferta("101.00"), historial)
    assert r.calidad_precio is CalidadPrecio.PRECIO_NORMAL


def test_con_habitual_y_los_comercios_de_hoy_de_la_misma_cadena_no_pasa_de_competitivo():
    """RN-012: los 2 comercios son además del evaluado; la otra tienda de su cadena no cuenta
    (comercio = cadena; guía de T10)."""
    historial = _con_habitual("100.00") + [
        _obs("80.00", "tp-sucursal", momento=_hace(3)),
        _obs("82.00", "cx", momento=_hace(3)),
    ]
    r = _evaluar(_oferta("70.00"), historial)
    assert r.calidad_precio is CalidadPrecio.PRECIO_COMPETITIVO


def _excepcional(dias_historial: int, minimo: str):
    historial = (
        [_obs(minimo, "cy", momento=_hace(dias=dias_historial))]
        + _serie("100.00", range(20, 15, -1), "cy")
        + _dos_comercios_hoy("80.00", "90.00")
    )
    return _evaluar(_oferta("70.00"), historial)


def test_oferta_excepcional_con_90_dias_y_menor_que_el_minimo():
    assert _excepcional(90, "75.00").calidad_precio is CalidadPrecio.OFERTA_EXCEPCIONAL


def test_igualar_el_minimo_no_basta_ejemplo_a():
    assert _excepcional(90, "70.00").calidad_precio is CalidadPrecio.BUENA_OFERTA


def test_sin_90_dias_de_historial_no_es_excepcional_ejemplo_b():
    assert _excepcional(89, "75.00").calidad_precio is CalidadPrecio.BUENA_OFERTA


def test_b29_sin_historial_con_anunciado_y_2_comercios_es_precio_competitivo():
    """B29: sin precio habitual, tachado $199 (anunciado 60.3%), hoy Amazon $149 y otra cadena
    $152 → 79 ≤ 151.98 → Precio competitivo (no Descuento cuestionable: 2 comercios)."""
    historial = [
        _obs("152.00", "cx", momento=_hace(6)),
        _obs("150.00", "cx", momento=_hace(dias=1)),
    ]
    r = _evaluar(_oferta("79.00", was="199.00"), historial, [_ficha("149.00")])
    assert r.referencias.precio_habitual is None
    assert r.calidad_precio is CalidadPrecio.PRECIO_COMPETITIVO
    assert Motivo.SIN_HISTORIAL_SUFICIENTE in r.motivos


def test_s28_sin_historial_y_anunciado_contra_un_solo_comercio_es_cuestionable():
    """S-28 / RN-012 §11: sin historial y el anunciado solo se compara contra un comercio."""
    r = _evaluar(_oferta("79.00", was="199.00"), [_obs("152.00", "cx", momento=_hace(6))])
    assert r.calidad_precio is CalidadPrecio.DESCUENTO_CUESTIONABLE


def test_s28_sin_historial_un_comercio_y_sin_tachado_no_es_cuestionable():
    r = _evaluar(_oferta("79.00"), [_obs("152.00", "cx", momento=_hace(6))])
    assert r.calidad_precio is CalidadPrecio.PRECIO_COMPETITIVO


def test_s28_con_historial_el_anunciado_contra_un_comercio_no_es_cuestionable():
    historial = _con_habitual("150.00") + [_obs("152.00", "cx", momento=_hace(6))]
    r = _evaluar(_oferta("79.00", was="199.00"), historial)
    assert r.calidad_precio is CalidadPrecio.PRECIO_COMPETITIVO


def test_los_umbrales_de_calidad_salen_de_la_configuracion():
    historial = _con_habitual("100.00") + _dos_comercios_hoy("86.00", "90.00")
    config = _config(("good_offer_min_discount_pct: 15", "good_offer_min_discount_pct: 20"))
    r = _evaluar(_oferta("85.00"), historial, configuracion=config)
    assert r.calidad_precio is CalidadPrecio.PRECIO_COMPETITIVO
    config = _config(("min_other_retailers: 2", "min_other_retailers: 3"))
    r = _evaluar(_oferta("85.00"), historial, configuracion=config)
    assert r.calidad_precio is CalidadPrecio.PRECIO_COMPETITIVO
    config = _config(("cheapest_tolerance_pct: 2", "cheapest_tolerance_pct: 0"))
    r = _evaluar(_oferta("86.01"), historial, configuracion=config)
    assert r.calidad_precio is CalidadPrecio.PRECIO_NORMAL


# =========================================================================================
# Precio de mercado hoy (RN-002 v2 §4.1; S-03; RN-007 §4.1 y §4.2)
# =========================================================================================


def _hoy(*observaciones, fichas=(), oferta=None):
    contexto = _contexto(oferta or _oferta("50.00"), observaciones, fichas)
    return referencias.mercado_hoy(contexto)


def test_mercado_hoy_es_el_mas_bajo_y_un_precio_invalido_no_cuenta():
    hoy = _hoy(
        _obs("124.01", "cx"), _obs("130.00", "cy"), _obs("90.00", "cz", estado="out_of_stock")
    )
    assert hoy.precio == Decimal("124.01")
    # Un precio con más de 2 decimales es PRECIO INVÁLIDO (REQ §3.2 paso 1): no aporta precio.
    assert _hoy(_obs("124.005", "cx"), _obs("130.00", "cy")).precio == Decimal("130.00")


@pytest.mark.parametrize(
    ("antiguedad", "cuenta"),
    [
        (dt.timedelta(hours=48), True),
        (dt.timedelta(hours=48, seconds=1), False),
        (dt.timedelta(days=4), False),  # RN-002 ejemplo C
    ],
)
def test_mercado_hoy_48_horas_o_menos(antiguedad, cuenta):
    hoy = _hoy(_obs("90.00", "cx", momento=INSTANTE - antiguedad))
    assert (hoy is not None) is cuenta


def test_mercado_hoy_no_cuenta_la_oferta_evaluada_ni_su_publicacion():
    misma_pub = _obs("40.00", TIENDA_PRUEBA, momento=_hace(5), publicacion=PUB_OFERTA)
    oferta = _oferta("50.00")
    assert _hoy(misma_pub, oferta, oferta=oferta) is None
    assert _hoy(misma_pub, _obs("60.00", "cx"), oferta=oferta).precio == Decimal("60.00")


@pytest.mark.parametrize(
    "cambios",
    [
        {"seller": "externo"},
        {"seller": "desconocido"},
        {"condition": "used"},
        {"estado": "out_of_stock"},
        {"estado": "limited_stock"},  # en línea: no cuenta como disponible (RN-007 §4.2)
        {"estado": "unconfirmed"},
        {"estado": "in_stock"},  # en línea sin confirmar el carrito
    ],
)
def test_mercado_hoy_solo_nuevo_vendido_por_el_comercio_y_disponible(cambios):
    assert _hoy(_obs("60.00", "cx", **cambios)) is None


def test_mercado_hoy_recoger_en_tienda_se_trata_como_en_linea():
    assert _hoy(_obs("60.00", "cx", modo="recoleccion")).precio == Decimal("60.00")
    assert _hoy(_obs("60.00", "cx", modo="recoleccion", estado="in_stock")) is None


@pytest.mark.parametrize(
    ("estado", "cantidad", "liquidacion", "horas", "cuenta"),
    [
        ("in_stock", 4, False, 24, True),  # cantidad exacta: Media hasta 24 h
        ("in_stock", 4, False, 24.01, False),
        ("in_stock", 4, True, 12, True),  # en liquidación, hasta 12 h
        ("in_stock", 4, True, 12.01, False),
        ("in_stock", None, False, 12, True),  # sin número: Media hasta 12 h
        ("in_stock", None, False, 12.01, False),  # después, Baja
        ("in_stock", None, True, 6, True),
        ("in_stock", None, True, 6.01, False),
        ("limited_stock", None, False, 2, True),  # pocas unidades: Media hasta 2 h
        ("limited_stock", None, False, 2.01, False),
        ("out_of_stock", None, False, 1, False),
    ],
)
def test_mercado_hoy_en_tienda_fisica_confianza_alta_o_media(
    estado, cantidad, liquidacion, horas, cuenta
):
    obs = _obs(
        "60.00",
        "cx",
        modo="tienda",
        tienda="wm-chula-vista",
        estado=estado,
        cantidad=cantidad,
        liquidacion=liquidacion,
        momento=INSTANTE - dt.timedelta(hours=horas),
    )
    assert (_hoy(obs) is not None) is cuenta


def test_mercado_hoy_ficha_de_amazon_con_y_sin_boton_de_compra():
    assert _hoy(fichas=[_ficha("119.00")]).precio == Decimal("119.00")
    assert _hoy(fichas=[_ficha(None)]) is None
    assert _hoy(fichas=[_ficha("119.00", horas=49)]) is None


def test_mercado_hoy_usa_la_observacion_mas_reciente_de_cada_publicacion():
    pub = _uuid()
    vieja = _obs("90.00", "cx", momento=_hace(20), publicacion=pub)
    nueva = _obs("110.00", "cx", momento=_hace(2), publicacion=pub)
    assert _hoy(vieja, nueva).precio == Decimal("110.00")


def test_mercado_hoy_cuenta_cadenas_distintas_de_la_evaluada():
    hoy = _hoy(
        _obs("60.00", "cx"),
        _obs("61.00", "cx"),  # otra publicación de la misma cadena X
        _obs("62.00", "tp-sucursal"),  # la cadena de la oferta
        fichas=[_ficha("63.00")],
    )
    assert hoy.otras_cadenas == frozenset({"cadena-x", "amazon"})


def test_mercado_hoy_la_antiguedad_sale_de_la_configuracion():
    config = _config(("market_today_max_age_hours: 48", "market_today_max_age_hours: 24"))
    obs = _obs("90.00", "cx", momento=_hace(30))
    assert referencias.mercado_hoy(_contexto(_oferta("50.00"), [obs], configuracion=config)) is None


# =========================================================================================
# Usados, estado desconocido, vacío = ausente y orden de los motivos
# =========================================================================================


def test_usado_calidad_no_aplica_y_sin_motivo_de_historial():
    """DEC-215: calidad no aplica en usados; SIN HISTORIAL SUFICIENTE no aplica a usados."""
    r = _evaluar(_oferta("70.00", condition="used"), _b6_historial())
    assert r.calidad_precio is CalidadPrecio.NO_APLICA
    assert Motivo.SIN_HISTORIAL_SUFICIENTE not in r.motivos
    assert r.descuento_real is None


def test_estado_desconocido_de_un_comercio_es_nuevo():
    """S-13: de un comercio, estado desconocido = nuevo → sin historial, SIN HISTORIAL."""
    r = _evaluar(_oferta("169.00", condition=None), _b6_historial())
    assert r.motivos == (Motivo.SIN_HISTORIAL_SUFICIENTE,)
    assert r.calidad_precio is CalidadPrecio.PRECIO_COMPETITIVO


def test_sin_datos_no_hay_calidad_y_las_referencias_quedan_vacias():
    r = _evaluar(_oferta("50.00"))
    assert r.calidad_precio is None
    assert r.descuento_real is None and r.descuento_anunciado is None
    refs = r.referencias
    assert refs is None or all(
        getattr(refs, campo.name) is None for campo in dataclasses.fields(refs)
    )
    texto = r.a_json()
    assert "NaN" not in texto and '""' not in texto


def _con_paso(monkeypatch, nombre, funcion):
    def envolver(original):
        def paso(contexto, avance):
            return funcion(contexto, original(contexto, avance))

        return paso

    pasos = tuple(envolver(p) if p.__name__ == nombre else p for p in motor.PASOS)
    monkeypatch.setattr(motor, "PASOS", pasos)


def test_b29_sin_historial_y_margen_negativo_descartada_y_guarda_los_dos(monkeypatch):
    """§3.2.3/§3.2.4: MARGEN NEGATIVO va antes; SIN HISTORIAL SUFICIENTE también se guarda."""

    def margen_negativo(contexto, avance):
        return dataclasses.replace(avance, motivos=(*avance.motivos, Motivo.MARGEN_NEGATIVO))

    _con_paso(monkeypatch, "elegir_canal", margen_negativo)
    r = _evaluar(_oferta("79.00"), _b6_historial())
    assert r.resultado is Resultado.DESCARTADA
    assert r.motivo_principal is Motivo.MARGEN_NEGATIVO
    assert r.motivos == (Motivo.MARGEN_NEGATIVO, Motivo.SIN_HISTORIAL_SUFICIENTE)


def test_sin_historial_va_antes_que_los_demas_motivos_de_revision(monkeypatch):
    def otros(contexto, avance):
        return dataclasses.replace(
            avance,
            motivos=(
                Motivo.DEMANDA_DESCONOCIDA,
                *avance.motivos,
                Motivo.COINCIDENCIA_NO_CONFIRMADA,
            ),
        )

    _con_paso(monkeypatch, "elegir_canal", otros)
    r = _evaluar(_oferta("169.00"), _b6_historial())
    assert r.motivos == (
        Motivo.SIN_HISTORIAL_SUFICIENTE,
        Motivo.COINCIDENCIA_NO_CONFIRMADA,
        Motivo.DEMANDA_DESCONOCIDA,
    )
    assert r.motivo_principal is Motivo.SIN_HISTORIAL_SUFICIENTE


def test_solo_referencia_va_antes_que_sin_historial_no_se_dan_juntos():
    """Con habitual hay franja y no SIN HISTORIAL; sin habitual, SIN HISTORIAL y no franja."""
    r = _evaluar(_oferta("80.00"), _con_habitual("100.00"))
    assert Motivo.SIN_HISTORIAL_SUFICIENTE not in r.motivos
    r = _evaluar(_oferta("80.00"), _b6_historial())
    assert Motivo.SOLO_REFERENCIA not in r.motivos and Motivo.MERCADO_YA_BARATO not in r.motivos


# =========================================================================================
# Pruebas de T04 / precedencia que el developer cambió: misma conclusión SIN apagar el paso 4
# =========================================================================================


def _canal_disponible_con_nivel(contexto, avance):
    canal = EvaluacionCanal(Canal.AMAZON, EstadoCanal.DISPONIBLE, nivel=Nivel.MUY_RECOMENDABLE)
    return dataclasses.replace(
        avance,
        canales=(canal,),
        canal_elegido=Canal.AMAZON,
        nivel_aviso=Nivel.MUY_RECOMENDABLE,
        canal_aviso=Canal.AMAZON,
    )


def _canal_por_revisar(contexto, avance):
    canal = EvaluacionCanal(Canal.AMAZON, EstadoCanal.POR_REVISAR, nivel_calculado=Nivel.COMPRAR_YA)
    return dataclasses.replace(avance, canales=(canal,))


def test_con_historial_real_un_canal_con_nivel_da_nivel_asignado(monkeypatch):
    """Lo que verifican ``test_motor_nivel_asignado_con_canal_disponible_con_nivel`` (T04) y
    ``test_nivel_asignado_solo_con_un_canal_disponible_con_nivel`` con el paso 4 apagado se
    cumple también con el paso 4 real y un contexto completado con historial (real 50%)."""
    _con_paso(monkeypatch, "elegir_canal", _canal_disponible_con_nivel)
    r = _evaluar(_oferta("50.00"), _con_habitual("100.00"))
    assert r.motivos == ()
    assert r.resultado is Resultado.NIVEL_ASIGNADO
    assert (r.canal_elegido, r.nivel_aviso) == (Canal.AMAZON, Nivel.MUY_RECOMENDABLE)


def test_con_historial_real_un_canal_por_revisar_no_da_nivel(monkeypatch):
    _con_paso(monkeypatch, "elegir_canal", _canal_por_revisar)
    r = _evaluar(_oferta("50.00"), _con_habitual("100.00"))
    assert r.resultado is Resultado.SIN_NIVEL
    assert r.canales[0].nivel_calculado is Nivel.COMPRAR_YA


def test_sin_historial_el_canal_con_nivel_no_evita_la_revision_manual(monkeypatch):
    """Sin apagar el paso 4 y sin historial, SIN HISTORIAL SUFICIENTE manda a revisión."""
    _con_paso(monkeypatch, "elegir_canal", _canal_disponible_con_nivel)
    r = _evaluar(_oferta("50.00"))
    assert r.resultado is Resultado.REVISION_MANUAL
    assert r.motivo_principal is Motivo.SIN_HISTORIAL_SUFICIENTE


# =========================================================================================
# Tipos estrictos (DEC-238), dinero sin float, pureza y reproducibilidad
# =========================================================================================


def _datos(**cambios):
    base = dict(
        precio=Decimal("29.00"),
        precio_habitual=Decimal("119"),
        descuento_real=descuento.descuento_real(Decimal("119"), Decimal("29.00")),
        precio_mercado_hoy=Decimal("119"),
        otros_comercios=2,
        minimo_registrado=None,
        dias_historial=60,
        descuento_anunciado=None,
        precio_antes_inflado=False,
    )
    base.update(cambios)
    return descuento.DatosCalidad(**base)


@pytest.mark.parametrize(
    "cambios",
    [
        {"precio": 29.0},
        {"precio_mercado_hoy": 119.0},
        {"precio_mercado_hoy": Decimal("NaN")},
        {"otros_comercios": True},
        {"otros_comercios": 2.0},
        {"otros_comercios": -1},
        {"dias_historial": "60"},
        {"precio_antes_inflado": 0},
        {"descuento_anunciado": 77.5},
    ],
)
def test_datos_calidad_rechazan_tipos_laxos(cambios):
    with pytest.raises((TypeError, ValueError)):
        _datos(**cambios)


def test_funciones_del_descuento_rechazan_float():
    parametros = CONFIG.contenido.discount_quality
    with pytest.raises(TypeError):
        descuento.descuento_anunciado(129.0, Decimal("29"))
    with pytest.raises(TypeError):
        descuento.descuento_real(Decimal("119"), 29.0)
    with pytest.raises(TypeError):
        descuento.franja(20.0, parametros)
    with pytest.raises(TypeError):
        descuento.marcas_del_anunciado(Decimal("200"), 25.0, parametros)
    with pytest.raises(TypeError):
        descuento.calidad_del_precio({"precio": Decimal(1)}, parametros)


def _codigo(nombre: str) -> str:
    texto = (SRC_EVALUACION / nombre).read_text(encoding="utf-8")
    # Sin docstrings ni comentarios, para no contar la palabra en la documentación.
    texto = re.sub(r'"""(?:.|\n)*?"""', "", texto)
    return "\n".join(linea.split("#", 1)[0] for linea in texto.splitlines())


@pytest.mark.parametrize("nombre", ["descuento.py", "referencias.py", "motor.py"])
def test_sin_float_quantize_reloj_ni_red_en_el_codigo(nombre):
    codigo = _codigo(nombre)
    for prohibido in (
        r"\bfloat\(",
        r"\.quantize\(",
        r"\bround\(",
        r"\.now\(",
        r"\.today\(",
        r"\butcnow\(",
        r"\btime\.time\(",
        r"\brandom\b",
        r"\brequests\b",
        r"\bhttpx\b",
        r"\burllib\b",
        r"\bsocket\b",
        r"total_seconds\(",
    ):
        assert not re.search(prohibido, codigo), (nombre, prohibido)


def test_motor_puro_sin_red_y_reproducible(monkeypatch):
    historial, fichas = _historial_b1()
    contexto = _contexto(_oferta("29.00", was="129.00"), historial, fichas, [_msrp("199.00")])

    def prohibido(*a, **k):
        raise AssertionError("el motor no usa la red")

    monkeypatch.setattr(socket, "socket", prohibido)
    monkeypatch.setattr(socket, "create_connection", prohibido)
    r1 = motor.evaluar(contexto)
    r2 = motor.evaluar(ContextoEvaluacion.desde_json(contexto.a_json()))
    assert r1 == r2 and r1.a_json() == r2.a_json()
    assert r1.calidad_precio is CalidadPrecio.BUENA_OFERTA


def test_el_resultado_no_depende_de_la_zona_de_la_maquina(monkeypatch):
    import time

    historial, fichas = _historial_b1()
    contexto = _contexto(_oferta("29.00", was="129.00"), historial, fichas)
    antes = motor.evaluar(contexto).a_json()
    if not hasattr(time, "tzset"):
        pytest.skip("sin time.tzset")
    monkeypatch.setenv("TZ", "Asia/Tokyo")
    time.tzset()
    try:
        assert motor.evaluar(contexto).a_json() == antes
    finally:
        monkeypatch.undo()
        time.tzset()


def test_el_alias_ni_datos_personales_entran_en_el_registro():
    """R-20: la evaluación de T10 no agrega texto libre; los motivos y marcas son de catálogo."""
    historial, fichas = _historial_b1()
    r = _evaluar(_oferta("29.00", was="129.00"), historial, fichas)
    validas = {m.value for m in Marca}
    assert all(m in validas for m in r.marcas)
