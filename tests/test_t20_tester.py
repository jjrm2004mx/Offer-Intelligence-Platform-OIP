"""Pruebas independientes de oip-tester para T20 (compra a particular y usados).

Capacidad ``resultado-y-reevaluacion``; REQ-2026-0001 v2.9 §3.2 pasos 3, 5 y 6, §3.2.1
(estado de cada canal), §3.2.3, §3.2.4, §5 (configuración base y redondeo), §6
(publicación de un particular, PAR-09) y §13 S-05, S-12, S-13, S-14 y S-31; escenarios B18 y
B24 (a), (b) y (c). RN-014 v1 §4 (valor de referencia de usados, ejemplo A), RN-015 v1 §4
(particular y riesgo de procedencia), RN-016 v1 §4 (precio local de un usado y techo),
RN-008 v2 §4.3 (recogida). design.md CMP-10 a CMP-13, PAR-09, PAR-12, §9, §10 (puntos 7 y
11) y Open Question 1; DEC-224 (a), DEC-232, DEC-245, DEC-263, DEC-266, DEC-267 y DEC-269.

Escritas por adelantado (DEC-252, etapa 2) **sin ver la implementación**: solo con la
interfaz del commit da237a7 (firmas, tipos y docstrings) y las fuentes. Los datos y los
resultados esperados se copian del REQ y de las RN (precios, montos, porcentajes, motivos,
resultado), no del código. Las pruebas que no son un escenario del REQ no llevan marcador.

Fixtures sintéticos (DEC-194): la plataforma de particulares y el comercio de prueba usan
subdominios de example.com; ninguna prueba abre una URL. Instante explícito en
``America/Tijuana`` (PAR-01), sin reloj, sin red, sin aleatoriedad.
"""

from __future__ import annotations

import datetime as dt
import itertools
import json
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from config_tienda_prueba import BASE, SUCURSAL_PRUEBA, TIENDA_PRUEBA, con_sucursales_prueba
from oip.catalogos import (
    CalidadPrecio,
    Canal,
    CausaCanalCerrado,
    CausaCanalPorRevisar,
    EstadoCanal,
    Marca,
    Motivo,
    Resultado,
)
from oip.configuracion import cargar_configuracion_texto
from oip.dinero import formatear_porcentaje
from oip.entradas.capturas import leer_captura
from oip.entradas.contrato import leer_observacion
from oip.evaluacion import canales, identificacion, motor, referencias
from oip.evaluacion.contexto import ContextoEvaluacion, EvaluacionCanal, ObservacionRegistrada

D = Decimal
TIJUANA = ZoneInfo("America/Tijuana")
INSTANTE = dt.datetime(2026, 11, 16, 14, 0, tzinfo=TIJUANA)

# --- Configuración: base de los escenarios + comercio de prueba + plataforma sintética ----
# ``plataforma_prueba`` (particulares.example.com) es una plataforma permitida sintética, para
# no escribir el dominio de una plataforma real en las pruebas. ``lejana`` y ``fuera_de_zona``
# son ciudades sintéticas para probar la recogida por ciudad (PAR-09) y la zona de venta
# local (RN-014 §4, DEC-171). San Diego queda como en base.yaml: 10 km y 0.5 h = $9.50.
_PLATAFORMA = "    plataforma_prueba: {domains: [particulares.example.com]}\n"
_CIUDADES = (
    "    lejana: {pickup_km: 50, pickup_hours: 1, in_local_sale_zone: true}\n"
    "    fuera_de_zona: {pickup_km: 10, pickup_hours: 0.5, in_local_sale_zone: false}\n"
)


def _config():
    texto = con_sucursales_prueba(BASE.read_text(encoding="utf-8"))
    ancla = "\n  platforms:\n"
    assert texto.count(ancla) == 1
    texto = texto.replace(ancla, ancla + _PLATAFORMA, 1)
    # Las ciudades nuevas van al final de ``cities`` (después de tijuana).
    ancla = "    tijuana: {pickup_km: 10, pickup_hours: 0.5, in_local_sale_zone: true}\n"
    assert texto.count(ancla) == 1
    texto = texto.replace(ancla, ancla + _CIUDADES, 1)
    return cargar_configuracion_texto(texto, origen="t20-tester")


CONFIG = _config()
PARAMS = CONFIG.contenido

PRODUCTO = UUID(int=0x7200_0000)
PUB_PARTICULAR = UUID(int=0x7200_0001)
ID_OFERTA = UUID(int=0x7200_0002)
PUB_TIENDA = UUID(int=0x7200_0003)
PUB_AMAZON = UUID(int=0x7200_0004)
MARCA = "DEWALT"
MODELO = "DCF840"
URL_PARTICULAR = "https://particulares.example.com/item/detail/b18-t20"

_ids = itertools.count(0x7200_1000)


def _uuid() -> UUID:
    return UUID(int=next(_ids))


def _hace(horas: float = 0, dias: int = 0) -> dt.datetime:
    return INSTANTE - dt.timedelta(days=dias, hours=horas)


def _cerca(valor: Decimal | None, esperado: Decimal) -> bool:
    """Porcentajes sin redondear, tolerando solo el último dígito del contexto decimal."""
    assert isinstance(valor, Decimal), f"se esperaba Decimal, llegó {type(valor).__name__}"
    return abs(valor - esperado) < D("1e-20")


# --- Constructores ------------------------------------------------------------------------


def _particular(
    precio: str = "70.00",
    *,
    categoria: str = "tools",
    condicion: str | None = "used",
    ciudad: str = "san_diego",
) -> ObservacionRegistrada:
    """B18: atornillador DEWALT DCF840 usado, de un particular en San Diego, $70, modelo +
    marca y mismo contenido (REQ §6 punto 1; DEC-245: ``content`` se conserva)."""
    datos: dict = {
        "schemaVersion": "3.1",
        "retailerCode": "particular",
        "productUrl": URL_PARTICULAR,
        "brand": MARCA,
        "model": MODELO,
        "content": "atornillador, batería y cargador",
        "category": categoria,
        "price": {"current": precio, "currency": "USD"},
        "seller": "particular",
        "availability": {"state": "listed"},
        "purchaseMode": "particular",
        "pickupLocation": ciudad,
        "extractedAt": _hace(2).isoformat(),
        "blocked": False,
    }
    if condicion is not None:
        datos["condition"] = condicion
    return ObservacionRegistrada(leer_observacion(datos), ID_OFERTA, PUB_PARTICULAR, PRODUCTO)


def _comercio(
    precio: str,
    *,
    momento: dt.datetime,
    condicion: str = "new",
    seller: str = "comercio",
    categoria: str = "tools",
    ident: UUID | None = None,
    publicacion: UUID = PUB_TIENDA,
) -> ObservacionRegistrada:
    """Observación sintética de ``tienda-prueba`` en línea (envío al PO Box, disponible
    confirmada), con la tasa de prueba de REQ §5 (7.75%)."""
    datos = {
        "retailerCode": TIENDA_PRUEBA,
        "productUrl": "https://example.com/p/atornillador-t20",
        "title": "Atornillador sintetico T20",
        "brand": MARCA,
        "model": MODELO,
        "content": "atornillador, batería y cargador",
        "category": categoria,
        "condition": condicion,
        "price": {"current": precio, "currency": "USD"},
        "seller": seller,
        "availability": {"state": "in_stock_confirmed"},
        "purchaseMode": "envio",
        "taxLocation": "tienda_prueba",
        "weightKg": "1.5",
        "extractedAt": momento.isoformat(),
        "blocked": False,
    }
    return ObservacionRegistrada(
        leer_observacion(datos), _uuid() if ident is None else ident, publicacion, PRODUCTO
    )


def _ficha(momento: dt.datetime, buy_box: str | None) -> ObservacionRegistrada:
    datos = {
        "retailerCode": "amazon",
        "productUrl": "https://amazon.example.com/dp/t20",
        "title": "Atornillador sintetico T20",
        "brand": MARCA,
        "model": MODELO,
        "category": "tools",
        "condition": "new",
        "price": {"current": buy_box or "150.00", "currency": "USD"},
        "seller": "comercio",
        "availability": {"state": "in_stock_confirmed"},
        "purchaseMode": "envio",
        "weightKg": "1.5",
        "amazonListing": {
            "buyBoxPrice": buy_box,
            "rankMain": 6000,
            "sellersNew": 5,
            "boughtLastMonth": 200,
        },
        "extractedAt": momento.isoformat(),
        "blocked": False,
    }
    return ObservacionRegistrada(leer_observacion(datos), _uuid(), PUB_AMAZON, PRODUCTO)


def _fichas_completas() -> tuple[ObservacionRegistrada, ...]:
    """Ficha de Amazon con botón de compra hoy $150, ranking 6,000 los últimos 7 días y los
    7 días que terminan hace 30, y mínimo de 60 días $140: un canal Amazon que, en un
    producto nuevo, estaría disponible."""
    fichas = [_ficha(_hace(dias=50), "140.00")]
    fichas += [_ficha(_hace(dias=d), None) for d in range(36, 29, -1)]
    fichas += [_ficha(_hace(dias=d), None) for d in range(6, 0, -1)]
    fichas.append(_ficha(_hace(2), "150.00"))
    return tuple(fichas)


def _comparable(
    precio: str,
    *,
    vendido: bool = False,
    condicion: str = "used",
    ciudad: str = "san_diego",
    moneda: str = "USD",
    tipo_cambio: str | None = None,
):
    datos = {
        "brand": MARCA,
        "model": MODELO,
        "condition": condicion,
        "askingPrice": precio,
        "currency": moneda,
        "city": ciudad,
        "date": "2026-11-01",
        "sold": vendido,
    }
    if tipo_cambio is not None:
        datos["exchangeRate"] = tipo_cambio
    return leer_captura("local_comparable", datos, zona=TIJUANA)


def _estimado(precio: str):
    datos = {"brand": MARCA, "model": MODELO, "price": precio, "date": "2026-11-10"}
    return leer_captura("local_estimate", datos, zona=TIJUANA)


def _demanda_baja(categoria: str = "tools"):
    datos = {"category": categoria, "level": "low", "date": "2026-11-01"}
    return leer_captura("local_demand", datos, zona=TIJUANA)


#: Usados comparables de B18 (precios pedidos, sin ventas concretadas).
COMPARABLES_B18 = ("120.00", "130.00", "140.00")
#: B24: solo 2 comparables.
COMPARABLES_B24 = ("120.00", "130.00")


def _contexto(
    oferta: ObservacionRegistrada | None = None,
    *,
    comparables=None,
    historial=(),
    fichas=(),
    **extra,
) -> ContextoEvaluacion:
    """B18 por omisión: sin datos de Amazon (ni ficha ni mínimo de 60 días), sin historial
    de nuevos, sin estimado de Jesús y con los comparables $120, $130 y $140."""
    if comparables is None:
        comparables = tuple(_comparable(p) for p in COMPARABLES_B18)
    return ContextoEvaluacion(
        id_evaluacion=UUID(int=0x7200_00FF),
        instante=INSTANTE,
        configuracion=CONFIG,
        id_version_configuracion=1,
        oferta=_particular() if oferta is None else oferta,
        historial=tuple(historial),
        fichas_amazon=tuple(fichas),
        comparables=tuple(comparables),
        **extra,
    )


def _contexto_b24(**extra) -> ContextoEvaluacion:
    return _contexto(comparables=tuple(_comparable(p) for p in COMPARABLES_B24), **extra)


def _canal(registro, canal: Canal) -> EvaluacionCanal:
    encontrados = [c for c in registro.canales if c.canal is canal]
    assert len(encontrados) == 1, f"se esperaba un canal {canal}: {registro.canales!r}"
    return encontrados[0]


def _amazon_cerrado_por_no_nuevo(registro) -> None:
    """S-12: en el Inc. 1 un producto no nuevo solo se evalúa en venta local. Cerrado no
    tiene ``nivel_calculado`` (DEC-224 a) ni margen ajustado (§3.2.1)."""
    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.CERRADO
    assert CausaCanalCerrado.PRODUCTO_NO_NUEVO in amazon.causas_cerrado
    # Las causas de por revisar que concurran se registran (convención de T11), pero el
    # canal queda cerrado (S-31): no se afirma que estén vacías.
    assert amazon.nivel is None and amazon.nivel_calculado is None
    assert amazon.margen_ajustado is None
    assert amazon.unidades is None and amazon.rendimiento_mensual_pct is None


#: B18 sin redondear: valor de referencia 130 × 85% = 110.50; real = (1 − 70 ÷ 110.50) × 100.
REAL_B18 = (D("110.50") - D("70")) / D("110.50") * 100


# =========================================================================================
# Escenarios
# =========================================================================================


@pytest.mark.scenario("B18")
def test_b18_particular_revision_con_inspeccion():
    """REQ §5 B18; RN-014 ejemplo A; RN-015 §4; S-12, S-14, S-05; DEC-263."""
    registro = motor.evaluar(_contexto())

    # "Modelo + marca y mismo contenido" (RN-013; DEC-245): no da COINCIDENCIA NO
    # CONFIRMADA (se comprueba en los motivos). El campo ``identificacion`` lo llena T19.

    # Valor de referencia 130 × 85% = $110.50; real 36.7%.
    refs = registro.referencias
    assert refs.valor_referencia_usados == D("110.50")
    # DEC-263: en un usado el precio habitual, su fuente y su episodio quedan vacíos.
    assert refs.precio_habitual is None
    assert refs.fuente_precio_habitual is None
    assert refs.episodio is None
    assert _cerca(registro.descuento_real, REAL_B18)
    assert formatear_porcentaje(registro.descuento_real) == "36.7 %"

    # Compra 70 + 9.50 = $79.50 (sin impuesto, S-14).
    assert registro.costo_compra == D("79.50")
    # Calidad del precio: no aplica (usado, EXT-031, DEC-215).
    assert registro.calidad_precio is CalidadPrecio.NO_APLICA

    # Amazon cerrado (usado, S-12).
    _amazon_cerrado_por_no_nuevo(registro)

    # Local: pedido mín(110.50, 120) → venta $99.45; neto $10.45; castigo 10% = $9.95 (sin
    # mínimo de 60 días en Amazon, S-05); ajustado $0.50 → sin nivel.
    local = _canal(registro, Canal.LOCAL)
    assert local.estado is EstadoCanal.DISPONIBLE
    assert local.causas_cerrado == () and local.causas_por_revisar == ()
    assert local.precio_venta == D("99.45")
    assert local.costo_venta == D("9.50")
    assert local.margen_neto == D("10.45")
    assert _cerca(local.margen_neto_pct, D("10.45") / D("79.50") * 100)
    assert local.castigo == D("9.95")
    assert local.margen_ajustado == D("0.50")
    assert local.nivel is None
    # Con descuento real ≥ 25% el nivel se calcula, pero $0.50 no alcanza el mínimo por
    # unidad (mayor de $10 y 10% de 79.50): no hay nivel.
    assert local.nivel_calculado is None

    # Motivos PARTICULAR y RIESGO DE PROCEDENCIA → REVISION_MANUAL, principal PARTICULAR.
    # No hay SIN HISTORIAL SUFICIENTE (no aplica a usados, §3.2.3) ni SIN REFERENCIA DE
    # USADOS (3 comparables), ni MARGEN NEGATIVO (ajustado > 0).
    assert registro.motivos == (Motivo.PARTICULAR, Motivo.RIESGO_DE_PROCEDENCIA)
    assert registro.motivo_principal is Motivo.PARTICULAR
    assert registro.resultado is Resultado.REVISION_MANUAL
    assert registro.nivel_aviso is None


@pytest.mark.scenario("B24 (a)")
def test_b24_a_usado_sin_referencia_venta_local_por_revisar():
    """REQ §5 B24 (a); RN-014 §4 y ejemplo B; S-31; §3.2.4."""
    registro = motor.evaluar(_contexto_b24())

    # 2 < 3 → sin valor de referencia ni descuento real.
    refs = registro.referencias
    assert refs.valor_referencia_usados is None
    assert refs.precio_habitual is None and refs.fuente_precio_habitual is None
    assert refs.episodio is None
    assert registro.descuento_real is None
    assert registro.costo_compra == D("79.50")
    assert registro.calidad_precio is CalidadPrecio.NO_APLICA

    _amazon_cerrado_por_no_nuevo(registro)

    # Venta local por revisar (S-31): sin estimado ni valor de referencia no hay precio local,
    # no se calcula margen y nivel_calculado no está disponible. No es SIN PRECIO LOCAL
    # (cerrado): §3.2.1 lo exceptúa para el usado sin valor de referencia.
    local = _canal(registro, Canal.LOCAL)
    assert local.estado is EstadoCanal.POR_REVISAR
    assert local.causas_por_revisar == (CausaCanalPorRevisar.SIN_REFERENCIA_DE_USADOS,)
    assert local.causas_cerrado == ()
    assert local.precio_venta is None
    assert local.margen_neto is None and local.margen_ajustado is None
    assert local.nivel is None and local.nivel_calculado is None
    assert local.unidades is None and local.rendimiento_mensual_pct is None

    # Sin SIN CANAL DISPONIBLE (un canal por revisar), sin MARGEN NEGATIVO, sin MERCADO YA
    # BARATO ni SOLO REFERENCIA (no hay descuento real) → REVISION_MANUAL, principal
    # SIN REFERENCIA DE USADOS (va antes en §3.2.3).
    assert registro.motivos == (
        Motivo.SIN_REFERENCIA_DE_USADOS,
        Motivo.PARTICULAR,
        Motivo.RIESGO_DE_PROCEDENCIA,
    )
    assert registro.motivo_principal is Motivo.SIN_REFERENCIA_DE_USADOS
    assert registro.resultado is Resultado.REVISION_MANUAL


@pytest.mark.scenario("B24 (b)")
def test_b24_b_demanda_local_baja_prevalece_cerrado():
    """REQ §5 B24 (b), parte de canales: S-31 (una causa de cerrado prevalece sobre por
    revisar); §3.2.1. Los motivos de revisión se guardan."""
    registro = motor.evaluar(_contexto_b24(demanda_local=(_demanda_baja(),)))

    _amazon_cerrado_por_no_nuevo(registro)
    local = _canal(registro, Canal.LOCAL)
    assert local.estado is EstadoCanal.CERRADO
    assert local.causas_cerrado == (CausaCanalCerrado.DEMANDA_LOCAL_BAJA,)
    assert local.nivel_calculado is None and local.margen_ajustado is None
    assert local.precio_venta is None

    for motivo in (
        Motivo.SIN_REFERENCIA_DE_USADOS,
        Motivo.PARTICULAR,
        Motivo.RIESGO_DE_PROCEDENCIA,
    ):
        assert motivo in registro.motivos
    assert registro.descuento_real is None
    assert registro.calidad_precio is CalidadPrecio.NO_APLICA


@pytest.mark.scenario("B24 (b)")
@pytest.mark.xfail(
    strict=True,
    reason=(
        "Hueco del plan, no defecto de T20 (DEC-249): SIN CANAL DISPONIBLE lo construye T18 "
        "y T20 no depende de T18 (issue #34, T20-2). Quitar el xfail cuando T18 lo agregue."
    ),
)
def test_b24_b_resultado_descartada_sin_canal_disponible():
    """REQ §5 B24 (b), resultado: los dos canales cerrados → SIN CANAL DISPONIBLE →
    DESCARTADA; los motivos de revisión se guardan después (orden de §3.2.3)."""
    registro = motor.evaluar(_contexto_b24(demanda_local=(_demanda_baja(),)))
    assert registro.resultado is Resultado.DESCARTADA
    assert registro.motivo_principal is Motivo.SIN_CANAL_DISPONIBLE
    assert registro.motivos == (
        Motivo.SIN_CANAL_DISPONIBLE,
        Motivo.SIN_REFERENCIA_DE_USADOS,
        Motivo.PARTICULAR,
        Motivo.RIESGO_DE_PROCEDENCIA,
    )


@pytest.mark.scenario("B24 (c)")
def test_b24_c_usado_sin_referencia_con_estimado_margen_informativo():
    """REQ §5 B24 (c); S-31 (con estimado: márgenes informativos con el techo de los
    comparables que haya); RN-016 §4; S-05."""
    registro = motor.evaluar(_contexto_b24(estimados=(_estimado("115.00"),)))

    _amazon_cerrado_por_no_nuevo(registro)

    # Techo $120 (menor de los 2 comparables) → pedido $115 → venta $103.50; neto 103.50 −
    # 79.50 − 9.50 = $14.50 (18.2%); castigo 10% = $10.35; ajustado $4.15 (5.2%).
    local = _canal(registro, Canal.LOCAL)
    assert local.estado is EstadoCanal.POR_REVISAR
    assert local.causas_por_revisar == (CausaCanalPorRevisar.SIN_REFERENCIA_DE_USADOS,)
    assert local.causas_cerrado == ()
    assert local.precio_venta == D("103.50")
    assert local.costo_venta == D("9.50")
    assert local.margen_neto == D("14.50")
    assert _cerca(local.margen_neto_pct, D("14.50") / D("79.50") * 100)
    assert formatear_porcentaje(local.margen_neto_pct) == "18.2 %"
    assert local.castigo == D("10.35")
    assert local.margen_ajustado == D("4.15")
    assert _cerca(local.margen_ajustado_pct, D("4.15") / D("79.50") * 100)
    assert formatear_porcentaje(local.margen_ajustado_pct) == "5.2 %"
    # Sin descuento real no hay nivel_calculado; por revisar: sin unidades, días ni
    # rendimiento (S-30).
    assert local.nivel is None and local.nivel_calculado is None
    assert local.unidades is None
    assert local.dias_para_recuperar is None
    assert local.rendimiento_mensual_pct is None
    assert local.ganancia_total is None

    assert registro.descuento_real is None
    assert registro.costo_compra == D("79.50")
    assert registro.calidad_precio is CalidadPrecio.NO_APLICA
    assert registro.resultado is Resultado.REVISION_MANUAL
    assert registro.motivo_principal is Motivo.SIN_REFERENCIA_DE_USADOS
    assert registro.motivos == (
        Motivo.SIN_REFERENCIA_DE_USADOS,
        Motivo.PARTICULAR,
        Motivo.RIESGO_DE_PROCEDENCIA,
    )


# =========================================================================================
# Valor de referencia de usados (RN-014 §4; PAR-12; REQ §5 redondeo)
# =========================================================================================


def test_valor_referencia_b18_con_precios_pedidos():
    """RN-014 ejemplo A: mediana de pedidos $130 × 85% = $110.50."""
    contexto = _contexto()
    assert len(referencias.comparables_de_usados(contexto)) == 3
    assert referencias.valor_referencia_usados(contexto) == D("110.50")


def test_valor_referencia_con_menos_de_3_comparables_es_none():
    """RN-014 §4 y ejemplo B: con 2 comparables no hay valor de referencia."""
    assert referencias.valor_referencia_usados(_contexto_b24()) is None
    assert referencias.valor_referencia_usados(_contexto(comparables=())) is None


def test_valor_referencia_con_3_ventas_concretadas_es_su_mediana_sin_factor():
    """RN-014 §4: mediana de ventas concretadas; el 85% solo aplica si solo hay precios
    pedidos. Ventas $100, $110 y $150 → $110.00."""
    comparables = tuple(_comparable(p, vendido=True) for p in ("100.00", "110.00", "150.00"))
    assert referencias.valor_referencia_usados(_contexto(comparables=comparables)) == D("110.00")


def test_valor_referencia_prefiere_ventas_cuando_hay_3_o_mas():
    """RN-014 §4 "de preferencia ventas concretadas": con 3 ventas ($100, $110, $150) y 2
    precios pedidos altos ($300, $310), el valor es la mediana de las ventas, $110.00."""
    comparables = tuple(
        _comparable(p, vendido=True) for p in ("100.00", "110.00", "150.00")
    ) + tuple(_comparable(p) for p in ("300.00", "310.00"))
    assert referencias.valor_referencia_usados(_contexto(comparables=comparables)) == D("110.00")


def test_tres_comparables_entre_pedidos_y_ventas_dan_referencia():
    """RN-014 §4: "se necesitan al menos 3 comparables". Con 2 ventas y 1 precio pedido hay 3
    comparables: hay valor de referencia y no hay SIN REFERENCIA DE USADOS. **No** se
    afirma el valor: RN-014 no dice cómo se combinan pedidos y ventas con menos de 3 ventas
    (lectura que va al #34)."""
    comparables = (
        _comparable("120.00", vendido=True),
        _comparable("125.00", vendido=True),
        _comparable("140.00"),
    )
    contexto = _contexto(comparables=comparables)
    assert len(referencias.comparables_de_usados(contexto)) == 3
    assert referencias.valor_referencia_usados(contexto) is not None
    registro = motor.evaluar(contexto)
    assert Motivo.SIN_REFERENCIA_DE_USADOS not in registro.motivos
    assert _canal(registro, Canal.LOCAL).estado is not EstadoCanal.POR_REVISAR


@pytest.mark.parametrize(
    ("precios", "esperado"),
    [
        # Mediana par = promedio de las dos centrales, sin redondear (DEC-226 b):
        # 135 × 85% = 114.75.
        (("120.00", "130.00", "140.00", "150.00"), D("114.75")),
        # 127.5 × 85% = 108.375 → 108.38 (medio centavo hacia arriba, una sola vez al final).
        (("120.00", "125.00", "130.00", "141.00"), D("108.38")),
    ],
)
def test_valor_referencia_mediana_par_y_redondeo_una_vez(precios, esperado):
    comparables = tuple(_comparable(p) for p in precios)
    assert referencias.valor_referencia_usados(_contexto(comparables=comparables)) == esperado


def test_comparables_cuentan_solo_mismo_estado_y_zona_de_venta_local():
    """RN-014 §4: mismo producto y **mismo estado**, solo en la zona de venta local (PAR-09
    ``in_local_sale_zone``, DEC-171). Un MXN cuenta convertido con su tipo de cambio (S-23):
    2,600 MXN ÷ 20 = $130. Los de otro estado o de fuera de la zona no cuentan."""
    comparables = (
        _comparable("120.00"),
        _comparable("2600.00", moneda="MXN", tipo_cambio="20", ciudad="tijuana"),
        _comparable("140.00"),
        _comparable("50.00", condicion="open_box"),
        _comparable("10.00", ciudad="fuera_de_zona"),
    )
    contexto = _contexto(comparables=comparables)
    assert len(referencias.comparables_de_usados(contexto)) == 3
    assert referencias.valor_referencia_usados(contexto) == D("110.50")


def test_solo_dos_comparables_validos_no_alcanzan_aunque_haya_otros():
    """Los de otro estado o fuera de la zona no completan los 3 (RN-014 §4)."""
    comparables = (
        _comparable("120.00"),
        _comparable("130.00"),
        _comparable("140.00", condicion="for_parts"),
        _comparable("150.00", ciudad="fuera_de_zona"),
    )
    contexto = _contexto(comparables=comparables)
    assert referencias.valor_referencia_usados(contexto) is None
    registro = motor.evaluar(contexto)
    assert registro.motivo_principal is Motivo.SIN_REFERENCIA_DE_USADOS


def test_oferta_nueva_no_tiene_valor_de_referencia_de_usados():
    """Docstring de la interfaz y RN-014: el valor de referencia es solo de un no nuevo."""
    oferta = _particular(condicion="new")
    contexto = _contexto(oferta)
    assert referencias.comparables_de_usados(contexto) == ()
    assert referencias.valor_referencia_usados(contexto) is None


def test_estado_desconocido_de_particular_se_trata_como_usado():
    """S-13 y RN-014 §11: sin estado, un particular es "usado" hasta la inspección; con los
    comparables usados de B18 tiene valor de referencia $110.50."""
    registro = motor.evaluar(_contexto(_particular(condicion=None)))
    assert registro.referencias.valor_referencia_usados == D("110.50")
    assert registro.resultado is Resultado.REVISION_MANUAL
    assert registro.motivo_principal is Motivo.PARTICULAR


# =========================================================================================
# El usado no se compara contra el precio de uno nuevo (RN-014 §1 y ejemplo A; DEC-263)
# =========================================================================================


def _historial_nuevos_a_179() -> list[ObservacionRegistrada]:
    """Precio de nuevo con historial suficiente (6 observaciones en 6 días, mediana $179),
    todas de hace más de 48 h para no dar precio de mercado hoy."""
    return [_comercio("179.00", momento=_hace(dias=d)) for d in (40, 30, 20, 10, 6, 4)]


def test_usado_ignora_el_precio_habitual_de_nuevos():
    """RN-014 ejemplo A ("precio de nuevo: $179, no cuenta") y DEC-263: con historial de
    nuevos, el usado sigue sin precio habitual y su real se mide contra $110.50."""
    registro = motor.evaluar(_contexto(historial=_historial_nuevos_a_179()))
    refs = registro.referencias
    assert refs.precio_habitual is None
    assert refs.fuente_precio_habitual is None
    assert refs.episodio is None
    assert refs.valor_referencia_usados == D("110.50")
    assert _cerca(registro.descuento_real, REAL_B18)
    assert registro.calidad_precio is CalidadPrecio.NO_APLICA
    assert Motivo.SIN_HISTORIAL_SUFICIENTE not in registro.motivos


def test_valor_referencia_reemplaza_al_habitual_en_el_descuento_real():
    """RN-014 §4: el valor de referencia reemplaza al habitual en el descuento real (RN-003).
    $95 contra $110.50 → (1 − 95 ÷ 110.50) × 100 = 14.0% < 20% → MERCADO YA BARATO →
    DESCARTADA; los motivos de particular se guardan."""
    registro = motor.evaluar(_contexto(_particular("95.00")))
    assert _cerca(registro.descuento_real, (D("110.50") - D("95")) / D("110.50") * 100)
    assert registro.resultado is Resultado.DESCARTADA
    assert registro.motivo_principal is Motivo.MERCADO_YA_BARATO
    assert Motivo.PARTICULAR in registro.motivos
    assert Motivo.RIESGO_DE_PROCEDENCIA in registro.motivos


def test_sin_historial_suficiente_no_aplica_a_usados_sin_referencia():
    """§3.2.3: SIN HISTORIAL SUFICIENTE no aplica a usados, que usan SIN REFERENCIA DE
    USADOS, aunque tampoco haya historial de nuevos."""
    registro = motor.evaluar(_contexto_b24())
    assert Motivo.SIN_HISTORIAL_SUFICIENTE not in registro.motivos


def test_referencias_json_llevan_el_valor_de_referencia_de_usados():
    """CTR-06: el valor sale en ``references`` como texto decimal, y el habitual vacío."""
    registro = motor.evaluar(_contexto())
    datos = json.loads(registro.referencias.a_json())
    assert datos["valor_referencia_usados"] == "110.50"
    assert datos["precio_habitual"] is None
    assert datos["fuente_precio_habitual"] is None
    assert datos["episodio"] is None


# =========================================================================================
# Amazon cerrado para no nuevos (S-12), también con datos completos de Amazon
# =========================================================================================


def test_usado_con_datos_de_amazon_completos_cierra_amazon():
    """S-12: aunque la ficha dé precio, ranking y vendedores, un usado no se evalúa en
    Amazon: cerrado con PRODUCTO NO NUEVO, sin nivel_calculado (DEC-224 a)."""
    registro = motor.evaluar(_contexto(fichas=_fichas_completas()))
    _amazon_cerrado_por_no_nuevo(registro)
    assert registro.canal_elegido is not Canal.AMAZON
    assert registro.canal_aviso is not Canal.AMAZON


@pytest.mark.parametrize("condicion", ["open_box", "refurbished"])
def test_no_nuevo_de_comercio_cierra_amazon_sin_motivo_particular(condicion):
    """S-12 vale para todo producto no nuevo, también de un comercio; ahí no hay compra a
    particular (RN-015): sin PARTICULAR."""
    oferta = _comercio("70.00", momento=_hace(2), condicion=condicion, ident=ID_OFERTA)
    registro = motor.evaluar(_contexto(oferta, fichas=_fichas_completas()))
    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.CERRADO
    assert CausaCanalCerrado.PRODUCTO_NO_NUEVO in amazon.causas_cerrado
    assert amazon.nivel_calculado is None
    assert Motivo.PARTICULAR not in registro.motivos


def test_causas_de_amazon_en_el_orden_del_catalogo():
    """DEC-269: sin datos de Amazon (B18) pueden concurrir SIN PRECIO DE VENTA EN AMAZON y
    PRODUCTO NO NUEVO; si van las dos, en el orden del catálogo de design.md §9."""
    amazon = _canal(motor.evaluar(_contexto()), Canal.AMAZON)
    orden = list(CausaCanalCerrado)
    indices = [orden.index(c) for c in amazon.causas_cerrado]
    assert indices == sorted(indices)


# =========================================================================================
# Venta local de un usado (RN-016 §4; S-31)
# =========================================================================================


def test_precio_local_del_usado_con_valor_de_referencia_y_techo():
    """B18 y RN-016 §4: estimado = 100% del valor de referencia ($110.50); techo $120 →
    pedido $110.50 → × 0.90 = 99.45."""
    precio = canales.precio_venta_local(_contexto(), None, D("110.50"))
    assert precio is not None
    assert precio.precio == D("99.45")
    assert precio.techo == D("120.00")


def test_precio_local_del_usado_sin_referencia_con_estimado():
    """B24 (c): techo $120 con los 2 comparables; pedido $115 → $103.50."""
    contexto = _contexto_b24(estimados=(_estimado("115.00"),))
    precio = canales.precio_venta_local(contexto, None, None)
    assert precio is not None
    assert (precio.precio, precio.techo) == (D("103.50"), D("120.00"))


def test_precio_local_del_usado_sin_referencia_ni_estimado_es_none():
    """B24 (a) y S-31: sin estimado ni valor de referencia no hay precio local."""
    assert canales.precio_venta_local(_contexto_b24(), None, None) is None


def test_usado_con_estimado_y_sin_comparables_marca_sin_comparables_locales():
    """S-31: con estimado y sin comparables, sin techo y marca SIN COMPARABLES LOCALES (en el
    canal, DEC-267). $115 × 0.90 = $103.50; el canal sigue por revisar."""
    registro = motor.evaluar(_contexto(comparables=(), estimados=(_estimado("115.00"),)))
    local = _canal(registro, Canal.LOCAL)
    assert local.estado is EstadoCanal.POR_REVISAR
    assert local.precio_venta == D("103.50")
    assert Marca.SIN_COMPARABLES_LOCALES.value in local.marcas
    assert Marca.SIN_COMPARABLES_LOCALES.value not in registro.marcas
    assert registro.motivo_principal is Motivo.SIN_REFERENCIA_DE_USADOS


# =========================================================================================
# Compra a particular: recogida por ciudad (PAR-09) sin impuesto (S-14; RN-008 §4.3)
# =========================================================================================


def test_recogida_de_san_diego_es_9_50():
    """B18: recogida $9.50 = 10 km × $0.20 + 0.5 h × $15 + $0 (PAR-09, PAR-12)."""
    assert canales.costo_recogida(_particular().observacion, PARAMS) == D("9.50")


def test_recogida_depende_de_la_ciudad():
    """RN-008 §4.2/§4.3 con la ciudad sintética ``lejana``: 50 × 0.20 + 1 × 15 = $25.00."""
    oferta = _particular(ciudad="lejana").observacion
    assert canales.costo_recogida(oferta, PARAMS) == D("25.00")


def test_sin_recogida_en_un_comercio():
    oferta = _comercio("70.00", momento=_hace(2)).observacion
    assert canales.costo_recogida(oferta, PARAMS) is None


def test_costo_de_compra_del_particular_sin_impuesto_con_recogida():
    """S-14: 70 + 0 + 0 + 9.50 = $79.50."""
    costo = canales.costo_compra(_particular().observacion, PARAMS)
    assert costo is not None
    assert costo.precio == D("70.00")
    assert costo.tasa_impuesto_pct == 0
    assert costo.impuesto == D("0.00")
    assert costo.recogida == D("9.50")
    assert costo.total == D("79.50")


def test_costo_de_compra_de_un_comercio_no_lleva_recogida():
    """CostoCompra.recogida = 0 fuera de particulares; 70 × 7.75% = 5.425 → $5.43."""
    costo = canales.costo_compra(_comercio("70.00", momento=_hace(2)).observacion, PARAMS)
    assert costo is not None
    assert costo.recogida == 0
    assert costo.impuesto == D("5.43")
    assert costo.total == D("75.43")


# =========================================================================================
# Particular y riesgo de procedencia (RN-014 §4; RN-015 §4)
# =========================================================================================


def test_es_compra_a_particular():
    assert identificacion.es_compra_a_particular(_particular().observacion) is True
    comercio = _comercio("70.00", momento=_hace(2)).observacion
    assert identificacion.es_compra_a_particular(comercio) is False


def test_motivos_de_particular_herramienta():
    """RN-015 §4: herramienta de particular → PARTICULAR y RIESGO DE PROCEDENCIA."""
    motivos = identificacion.motivos_de_particular(_particular().observacion, PARAMS)
    assert motivos == (Motivo.PARTICULAR, Motivo.RIESGO_DE_PROCEDENCIA)
    assert identificacion.riesgo_de_procedencia(_particular().observacion, PARAMS) is True


def test_motivos_de_particular_sin_categoria_de_riesgo():
    """RN-015 §4: una categoría sin riesgo de procedencia (``home_lighting``) solo da
    PARTICULAR."""
    oferta = _particular(categoria="home_lighting").observacion
    assert identificacion.riesgo_de_procedencia(oferta, PARAMS) is False
    assert identificacion.motivos_de_particular(oferta, PARAMS) == (Motivo.PARTICULAR,)


def test_motivos_de_particular_vacios_en_un_comercio():
    oferta = _comercio("70.00", momento=_hace(2)).observacion
    assert identificacion.motivos_de_particular(oferta, PARAMS) == ()
    # Herramienta vendida por el comercio: sin riesgo de procedencia (RN-015 §4).
    assert identificacion.riesgo_de_procedencia(oferta, PARAMS) is False


def test_riesgo_de_procedencia_con_vendedor_externo():
    """RN-015 §4: herramienta de un vendedor externo también tiene riesgo (B8)."""
    oferta = _comercio("70.00", momento=_hace(2), seller="externo").observacion
    assert identificacion.riesgo_de_procedencia(oferta, PARAMS) is True


def test_particular_sin_riesgo_en_el_motor_solo_particular():
    """B18 en una categoría sin riesgo: motivos = (PARTICULAR,)."""
    registro = motor.evaluar(_contexto(_particular(categoria="home_lighting")))
    assert registro.motivos == (Motivo.PARTICULAR,)
    assert registro.resultado is Resultado.REVISION_MANUAL


# --- Coherencia del fixture ---------------------------------------------------------------


def test_fixture_usa_la_sucursal_de_prueba_y_dominios_sinteticos():
    """Guarda: la configuración trae el comercio sintético y la plataforma sintética."""
    assert SUCURSAL_PRUEBA in PARAMS.stores
    assert "plataforma_prueba" in PARAMS.private_sellers.platforms
    assert PARAMS.private_sellers.cities["san_diego"].in_local_sale_zone is True
    assert PARAMS.private_sellers.cities["fuera_de_zona"].in_local_sale_zone is False
