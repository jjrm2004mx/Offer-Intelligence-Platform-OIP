"""Pruebas de T12: venta local con estimado de Jesús y techo de comparables (RN-016 §4;
DEC-260), castigo sin mínimo de 60 días (RN-005 §4; S-05), envío y empaque sin peso con
``ESTIMADO (peso)`` (RN-006 §4.2; S-06) y ``COMISIÓN DESCONOCIDA`` (RN-006; REQ §3.2.1), con
los escenarios B2 (base), B15, B16 y B17.

B15 de punta a punta queda en ``xfail(strict=True)``: su "Dado" (botón de compra de hoy $149
y sin mínimo de 60 días) no se puede armar con la lectura vigente de
``referencias.minimo_60_dias_amazon``, que incluye el día evaluado (B2 b y B9 b). La decide
Jesús en el issue #34. La regla S-05 se prueba aparte, con sus números de B15.

Fixtures sintéticos: comercios ficticios con dominios de example.com y las sucursales de
``config_tienda_prueba`` (T24); ninguna prueba abre una URL. Instante explícito, sin reloj ni
zona de la máquina. "amazon" es el código de la ficha de Amazon de la configuración base, con
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
    CausaCanalPorRevisar,
    Confianza,
    EstadoCanal,
    Marca,
    Nivel,
    Resultado,
    marca_estimado,
)
from oip.configuracion import cargar_configuracion_texto
from oip.dinero import formatear_porcentaje
from oip.entradas.capturas import leer_captura
from oip.entradas.contrato import leer_observacion
from oip.evaluacion import canales, motor, rentabilidad
from oip.evaluacion.contexto import ContextoEvaluacion, EvaluacionCanal, ObservacionRegistrada

D = Decimal

_TIJUANA = "    tijuana: {pickup_km: 10, pickup_hours: 0.5, in_local_sale_zone: true}\n"
#: Una ciudad sintética configurada fuera de la zona de venta local (PAR-09), para el techo.
_FUERA_DE_ZONA = "ciudad_fuera"


def _config():
    texto = con_sucursales_prueba(BASE.read_text(encoding="utf-8"))
    assert texto.count(_TIJUANA) == 1
    fuera = (
        f"    {_FUERA_DE_ZONA}: {{pickup_km: 10, pickup_hours: 0.5, in_local_sale_zone: false}}\n"
    )
    return cargar_configuracion_texto(texto.replace(_TIJUANA, _TIJUANA + fuera), origen="t12")


CONFIG = _config()
C = CONFIG.contenido
ZONA = ZoneInfo("America/Tijuana")
INSTANTE = dt.datetime(2026, 10, 14, 13, 0, tzinfo=ZONA)  # fuera de la temporada de juguetes
PRODUCTO = UUID(int=1200)
PUB_OFERTA = UUID(int=1201)
PUB_AMAZON = UUID(int=1202)
PUB_OTRA = UUID(int=1203)  # tienda-prueba-2 (Walmart en B2)

_TALADRO = {"title": "Taladro de prueba", "brand": "MarcaT", "model": "TD-2"}
_contador = iter(range(120_000, 120_000_000))
_URL = {
    TIENDA_PRUEBA: "https://tienda.example.com/p/12",
    TIENDA_PRUEBA_2: "https://otra.example.com/p/12",
    "amazon": "https://amazon.example.com/dp/T12",
}

#: Comentario del issue #34 con la contradicción de B15 (pendiente de Jesús).
_B15_PENDIENTE = (
    "B15 pide botón de compra de hoy $149 y ningún mínimo de 60 días; con la lectura vigente "
    "de minimo_60_dias_amazon (incluye el día evaluado, B2 b y B9 b) el mínimo existe y el "
    "castigo da $0. Pendiente de decisión de Jesús: "
    "https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/issues/34"
    "#issuecomment-7177510987"
)


# --- Fixtures de B2 -----------------------------------------------------------------------


def _momento(dias: int = 0, horas_antes: int = 0) -> dt.datetime:
    return INSTANTE + dt.timedelta(days=dias) - dt.timedelta(hours=horas_antes)


def _obs(
    precio: str,
    *,
    comercio: str,
    publicacion: UUID,
    momento: dt.datetime,
    categoria: str = "tools",
    **cambios,
) -> ObservacionRegistrada:
    datos = {
        "retailerCode": comercio,
        "productUrl": _URL[comercio],
        "category": categoria,
        "price": {"current": precio, "currency": "USD"},
        "seller": "comercio",
        "condition": "new",
        "availability": {"state": "in_stock_confirmed"},
        "purchaseMode": "envio",
        "extractedAt": momento.isoformat(),
        "blocked": False,
        **_TALADRO,
    }
    datos.update(cambios)
    return ObservacionRegistrada(
        leer_observacion(datos), UUID(int=next(_contador)), publicacion, PRODUCTO
    )


def _oferta_b2(*, categoria: str = "tools", sin_peso: bool = False) -> ObservacionRegistrada:
    """B2: tienda física (no liquidación), 2 kg, $79.00 con tachado $199.00, "4 disponibles"
    hace 2 h, tienda a 7.75%."""
    datos = {
        "storeCode": SUCURSAL_PRUEBA,
        "gtin": "036000291469",
        "price": {"current": "79.00", "was": "199.00", "currency": "USD"},
        "availability": {"state": "in_stock", "quantity": 4},
        "isClearance": False,
        "purchaseMode": "tienda",
        "taxLocation": "tienda_prueba",
    }
    if not sin_peso:
        datos["weightKg"] = "2"
    return _obs(
        "79.00",
        comercio=TIENDA_PRUEBA,
        publicacion=PUB_OFERTA,
        momento=_momento(horas_antes=2),
        categoria=categoria,
        **datos,
    )


def _historial_b2(categoria: str = "tools"):
    """Precio típico de la tienda $149 (8 observaciones en 6 días, 60 días de historial); la
    segunda cadena a $152 hoy (hace 6 h)."""
    propia = [
        _obs("149.00", comercio=TIENDA_PRUEBA, publicacion=PUB_OFERTA, momento=_momento(-d),
             categoria=categoria, storeCode=SUCURSAL_PRUEBA, purchaseMode="tienda")
        for d in (1, 2, 3, 4, 5, 6, 6, 60)
    ]  # fmt: skip
    otra = _obs("152.00", comercio=TIENDA_PRUEBA_2, publicacion=PUB_OTRA,
                momento=_momento(horas_antes=6), categoria=categoria)  # fmt: skip
    return [*propia, otra]


def _ficha(buy_box: str | None, momento: dt.datetime, categoria: str, **listing):
    return _obs(
        "999.00",
        comercio="amazon",
        publicacion=PUB_AMAZON,
        momento=momento,
        categoria=categoria,
        amazonListing={"buyBoxPrice": buy_box, **listing},
    )


def _fichas_b2(*, categoria: str = "tools", con_minimo: bool = True):
    """Botón de compra $149 hoy (hace 2 h) y los 6 días anteriores; ranking 8,500 los 7 días
    que terminan hoy y 8,000 los 7 que terminan hace 30 días; 9 vendedores; 300 comprados;
    mínimo de 60 días $139 (hace 20 días) si ``con_minimo``."""
    fichas = [
        _ficha("149.00", _momento(horas_antes=2), categoria, rankMain=8500, sellersNew=9,
               boughtLastMonth=300)
    ]  # fmt: skip
    fichas += [
        _ficha("149.00", _momento(-d), categoria, rankMain=8500, sellersNew=9) for d in range(1, 7)
    ]
    fichas += [
        _ficha(None, _momento(-d), categoria, rankMain=8000, sellersNew=9) for d in range(30, 37)
    ]
    if con_minimo:
        fichas.append(_ficha("139.00", _momento(-20), categoria, sellersNew=9))
    return fichas


def _comparable(precio: str, *, ciudad: str = "san_diego", estado: str = "new", vendido=False):
    datos = {
        "brand": _TALADRO["brand"],
        "model": _TALADRO["model"],
        "condition": estado,
        "askingPrice": precio,
        "currency": "USD",
        "city": ciudad,
        "date": "2026-10-10",
        "sold": vendido,
    }
    return leer_captura("local_comparable", datos, zona=ZONA)


def _estimado(precio: str):
    datos = {
        "brand": _TALADRO["brand"],
        "model": _TALADRO["model"],
        "price": precio,
        "date": "2026-10-10",
    }
    return leer_captura("local_estimate", datos, zona=ZONA)


_COMPARABLES_B2 = ("135", "139", "150")


def _contexto_b2(
    *,
    categoria: str = "tools",
    sin_peso: bool = False,
    con_minimo: bool = True,
    comparables=None,
    estimados=None,
) -> ContextoEvaluacion:
    return ContextoEvaluacion(
        id_evaluacion=UUID(int=12),
        instante=INSTANTE,
        configuracion=CONFIG,
        id_version_configuracion=1,
        oferta=_oferta_b2(categoria=categoria, sin_peso=sin_peso),
        historial=tuple(_historial_b2(categoria)),
        fichas_amazon=tuple(_fichas_b2(categoria=categoria, con_minimo=con_minimo)),
        comparables=(
            tuple(_comparable(p) for p in _COMPARABLES_B2) if comparables is None else comparables
        ),
        estimados=(_estimado("129"),) if estimados is None else estimados,
    )


def _canal(registro, canal: Canal) -> EvaluacionCanal:
    return next(c for c in registro.canales if c.canal is canal)


def _pct(valor: Decimal) -> str:
    return formatear_porcentaje(valor).removesuffix(" %")


def _assert_local_de_b2(local: EvaluacionCanal) -> None:
    """La venta local de B2: techo $135 → pedido $129 → $116.10; entrega $9.50; neto $21.48
    (25.2%); castigo $0 (116.10 < 139); 2 unidades; 30 días; 25.2%; Vigilar; total $42.96."""
    assert local.estado is EstadoCanal.DISPONIBLE
    assert local.precio_venta == D("116.10")
    assert local.costo_venta == D("9.50")
    assert (local.margen_neto, _pct(local.margen_neto_pct)) == (D("21.48"), "25.2")
    assert local.costo_devoluciones == D("0.00")
    assert local.castigo == D("0.00")
    assert (local.margen_ajustado, _pct(local.margen_ajustado_pct)) == (D("21.48"), "25.2")
    assert local.unidades == 2
    assert local.dias_para_recuperar == 30
    assert _pct(local.rendimiento_mensual_pct) == "25.2"
    assert local.nivel is Nivel.VIGILAR
    assert local.ganancia_total == D("42.96")
    assert Marca.SIN_COMPARABLES_LOCALES.value not in local.marcas


# --- B2 (base) ----------------------------------------------------------------------------


@pytest.mark.scenario("B2 (base)")
def test_b2_base_taladro_venta_local_vigilar():
    registro = motor.evaluar(_contexto_b2())

    # Descuento y calidad: anunciado 60.3%; no inflado (199 ≤ 223.50); real 47.0%.
    assert _pct(registro.descuento_anunciado) == "60.3"
    assert _pct(registro.descuento_real) == "47.0"
    assert Marca.PRECIO_ANTES_INFLADO.value not in registro.marcas
    assert registro.calidad_precio is CalidadPrecio.BUENA_OFERTA
    assert registro.confianza is Confianza.ALTA
    assert registro.costo_compra == D("85.12")
    assert registro.referencias.minimo_60_dias_amazon == D("139.00")
    assert registro.referencias.precio_venta_amazon == D("149.00")

    # Amazon: comisión $22.35, envío $12, empaque $2 → $36.35; neto $27.53 (32.3%);
    # devoluciones 5.215 → $5.22; castigo $5.00; ajustado $17.31 (20.3%); sin nivel.
    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.DISPONIBLE
    assert amazon.precio_venta == D("149.00")
    assert amazon.costo_venta == D("36.35")
    assert (amazon.margen_neto, _pct(amazon.margen_neto_pct)) == (D("27.53"), "32.3")
    assert amazon.costo_devoluciones == D("5.22")
    assert amazon.castigo == D("5.00")
    assert (amazon.margen_ajustado, _pct(amazon.margen_ajustado_pct)) == (D("17.31"), "20.3")
    assert amazon.unidades == 3
    assert amazon.dias_para_recuperar == 37
    assert _pct(amazon.rendimiento_mensual_pct) == "16.5"
    assert amazon.nivel is None and amazon.nivel_calculado is None
    assert marca_estimado("peso") not in amazon.marcas

    _assert_local_de_b2(_canal(registro, Canal.LOCAL))

    assert registro.resultado is Resultado.NIVEL_ASIGNADO
    assert registro.canal_elegido is Canal.LOCAL
    assert (registro.nivel_aviso, registro.canal_aviso) == (Nivel.VIGILAR, Canal.LOCAL)


def test_b2_las_cuentas_de_amazon_paso_a_paso():
    """Comisión 149 × 15% = 22.35, envío por 2 kg $12 y empaque > 1 kg $2 (RN-006)."""
    contexto = _contexto_b2()
    comision = canales.comision_amazon(D("149.00"), C.categories[_categoria("tools")].commission)
    assert comision == D("22.35")
    envio = canales.envio_amazon(contexto.oferta.observacion, C.shipping)
    assert (envio.envio, envio.empaque, envio.peso_estimado) == (D("12.00"), D("2.00"), False)


def _categoria(codigo: str):
    return next(c for c in C.categories if c.value == codigo)


# --- Techo local con comparables (RN-016 §4; PAR-09; DEC-260) ------------------------------


def test_techo_menor_que_el_estimado_pone_el_pedido():
    """Estimado de Jesús $140 > techo $135 → pedido $135 → 135 × 0.90 = $121.50."""
    precio = canales.precio_venta_local(_contexto_b2(estimados=(_estimado("140"),)), D("149"))
    assert (precio.precio, precio.techo) == (D("121.50"), D("135"))


def test_sin_estimado_el_techo_acota_el_85_por_ciento_del_mercado_hoy():
    """Sin estimado: 149 × 85% = 126.65 < techo 135 → 126.65 × 0.90 = 113.985 → $113.99."""
    precio = canales.precio_venta_local(_contexto_b2(estimados=()), D("149"))
    assert (precio.precio, precio.techo) == (D("113.99"), D("135"))


@pytest.mark.parametrize(
    ("comparable", "techo"),
    [
        (_comparable("100", ciudad="otra"), D("135")),  # ciudad fuera de la lista (PAR-09)
        (_comparable("100", ciudad=_FUERA_DE_ZONA), D("135")),  # fuera de la zona de venta
        (_comparable("100", estado="used"), D("135")),  # otro estado
        (_comparable("100", vendido=True), D("100")),  # DEC-260: un vendido sí cuenta
    ],
)
def test_que_comparables_cuentan_para_el_techo(comparable, techo):
    comparables = (*(_comparable(p) for p in _COMPARABLES_B2), comparable)
    contexto = _contexto_b2(comparables=comparables, estimados=(_estimado("200"),))
    assert canales.precio_venta_local(contexto, D("149")).techo == techo


def test_dec260_el_vendido_cuenta_para_el_techo_pero_no_como_competencia():
    """RN-017: la competencia cuenta solo los activos; 11 vendidos no bajan la demanda."""
    vendidos = tuple(_comparable("140", vendido=True) for _ in range(11))
    contexto = _contexto_b2(comparables=vendidos)
    assert canales.demanda_local(contexto) is C.categories[_categoria("tools")].initial_local_demand
    activos = tuple(_comparable("140") for _ in range(11))
    assert canales.demanda_local(_contexto_b2(comparables=activos)) is not (
        C.categories[_categoria("tools")].initial_local_demand
    )


def test_sin_comparables_en_la_zona_marca_sin_comparables_locales():
    registro = motor.evaluar(_contexto_b2(comparables=(_comparable("100", ciudad=_FUERA_DE_ZONA),)))
    local = _canal(registro, Canal.LOCAL)
    assert local.precio_venta == D("116.10")  # sin techo, pedido = estimado $129
    assert Marca.SIN_COMPARABLES_LOCALES.value in local.marcas
    assert Marca.SIN_COMPARABLES_LOCALES.value not in registro.marcas  # DEC-267


# --- B15 y S-05 (castigo sin mínimo de 60 días) ---------------------------------------------


@pytest.mark.parametrize(
    ("venta", "castigo"),
    [
        (D("149.00"), D("14.90")),  # B15, Amazon
        (D("116.10"), D("11.61")),  # B15, venta local
        (D("76.61"), D("7.66")),  # B33: 7.661 → 7.66
        (D("99.45"), D("9.95")),  # B18: 9.945 → 9.95 (medio centavo hacia arriba)
    ],
)
def test_s05_sin_minimo_el_castigo_es_el_10_por_ciento_de_la_venta_del_canal(venta, castigo):
    assert rentabilidad.castigo_por_baja(venta, None, C.amazon.drop_penalty) == castigo


def test_s05_el_porcentaje_sin_minimo_sale_de_la_configuracion():
    assert C.amazon.drop_penalty.without_minimum_pct == D("10")


def test_s05_con_minimo_se_usa_la_baja_y_no_el_10_por_ciento():
    """Con mínimo $139 la venta local de $116.10 no castiga (sale negativo → 0)."""
    assert rentabilidad.castigo_por_baja(D("116.10"), D("139"), C.amazon.drop_penalty) == D("0")


def test_s05_los_numeros_de_b15_en_los_dos_canales_sin_minimo():
    """Los canales de B2 con mínimo de 60 días ``None``: Amazon castigo $14.90, ajustado $7.41;
    local castigo $11.61, ajustado $9.87 (11.6%); los dos < mayor(10, 8.51) = $10."""
    contexto = _contexto_b2()
    registro = motor.evaluar(contexto)
    costo = canales.costo_compra(contexto.oferta.observacion, C)
    referencias_b2 = registro.referencias
    amazon = canales.evaluar_amazon(contexto, referencias_b2, costo)
    local = canales.evaluar_local(contexto, referencias_b2, costo)
    m_amazon = rentabilidad.calcular_margenes(amazon, costo.total, None, C.amazon.drop_penalty)
    m_local = rentabilidad.calcular_margenes(local, costo.total, None, C.amazon.drop_penalty)
    assert (m_amazon.castigo, m_amazon.margen_ajustado) == (D("14.90"), D("7.41"))
    assert (m_local.castigo, m_local.margen_ajustado) == (D("11.61"), D("9.87"))
    assert _pct(m_local.margen_ajustado_pct) == "11.6"
    minimo = rentabilidad.minimo_por_unidad(costo.total, C.levels.min_per_unit)
    assert minimo == D("10")
    assert m_amazon.margen_ajustado < minimo and m_local.margen_ajustado < minimo


@pytest.mark.scenario("B15")
@pytest.mark.xfail(strict=True, reason=_B15_PENDIENTE)
def test_b15_sin_minimo_de_60_dias_sin_nivel():
    """El "Dado" de B15 tal como lo escribe el REQ: los datos de B2 sin el mínimo de 60 días
    en Amazon (se quita la ficha de $139; el botón de compra de hoy sigue en $149)."""
    registro = motor.evaluar(_contexto_b2(con_minimo=False))
    amazon = _canal(registro, Canal.AMAZON)
    local = _canal(registro, Canal.LOCAL)
    assert (amazon.castigo, amazon.margen_ajustado) == (D("14.90"), D("7.41"))
    assert (local.castigo, local.margen_ajustado) == (D("11.61"), D("9.87"))
    assert _pct(local.margen_ajustado_pct) == "11.6"
    assert amazon.nivel is None and local.nivel is None
    assert registro.resultado is Resultado.SIN_NIVEL


# --- B16 (peso desconocido; S-06) -----------------------------------------------------------


@pytest.mark.scenario("B16")
def test_b16_peso_desconocido_envio_14_empaque_2_estimado_peso():
    registro = motor.evaluar(_contexto_b2(sin_peso=True))
    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.DISPONIBLE
    assert amazon.costo_venta == D("38.35")  # 22.35 + 14 + 2
    assert amazon.margen_neto == D("25.53")
    assert (amazon.margen_ajustado, _pct(amazon.margen_ajustado_pct)) == (D("15.31"), "18.0")
    assert amazon.nivel is None and amazon.nivel_calculado is None
    assert marca_estimado("peso") in amazon.marcas
    assert marca_estimado("peso") not in registro.marcas  # DEC-267: marca del canal
    _assert_local_de_b2(_canal(registro, Canal.LOCAL))
    assert marca_estimado("peso") not in _canal(registro, Canal.LOCAL).marcas
    assert registro.resultado is Resultado.NIVEL_ASIGNADO
    assert (registro.nivel_aviso, registro.canal_aviso) == (Nivel.VIGILAR, Canal.LOCAL)


def test_s06_sin_peso_el_envio_y_el_empaque_salen_de_la_configuracion():
    envio = canales.envio_amazon(_oferta_b2(sin_peso=True).observacion, C.shipping)
    assert (envio.envio, envio.empaque, envio.peso_estimado) == (
        C.shipping.unknown_weight.shipping,
        C.shipping.unknown_weight.packaging,
        True,
    )


# --- B17 (comisión desconocida) -------------------------------------------------------------


@pytest.mark.scenario("B17")
def test_b17_comision_desconocida_cierra_amazon_y_gana_la_venta_local():
    """``electronics`` no tiene comisión en la tabla de REQ §5 y sí tasa de devolución
    propia: la única causa de cierre por categoría es ``COMISIÓN DESCONOCIDA``. Su umbral de
    demanda también es "—" (``DEMANDA DESCONOCIDA``, por revisar), y el cerrado prevalece
    (S-31)."""
    assert C.categories[_categoria("electronics")].commission is None
    registro = motor.evaluar(_contexto_b2(categoria="electronics"))
    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.CERRADO
    assert amazon.causas_cerrado == (CausaCanalCerrado.COMISION_DESCONOCIDA,)
    assert amazon.causas_por_revisar == (CausaCanalPorRevisar.DEMANDA_DESCONOCIDA,)
    assert CausaCanalCerrado.COMISION_DESCONOCIDA.value in amazon.marcas
    assert amazon.nivel is None and amazon.nivel_calculado is None
    assert amazon.unidades is None
    _assert_local_de_b2(_canal(registro, Canal.LOCAL))
    assert registro.resultado is Resultado.NIVEL_ASIGNADO
    assert registro.canal_elegido is Canal.LOCAL
    assert (registro.nivel_aviso, registro.canal_aviso) == (Nivel.VIGILAR, Canal.LOCAL)
