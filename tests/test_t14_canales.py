"""Pruebas de T14: ranking de DEC-206 (promedio de 1 a 7 días; el mismo valor para el umbral,
los días y el tope), demanda desconocida con Amazon por revisar y ``nivel_calculado``
informativo (S-30), unidades sin ventas al mes (``ESTIMADO (unidades)``), ``DEMANDA A LA
BAJA`` y envío de más de 6 kg (cotización capturada o ``ENVÍO POR COTIZAR``), con los
escenarios B10 (a), B10 (b), B12, B13, B26 (a) y B26 (b).

Fixtures sintéticos: comercios ficticios con dominios de example.com y las sucursales de
``config_tienda_prueba``; ninguna prueba abre una URL. Instante explícito, sin reloj ni zona
de la máquina. "Amazon" es el código de la ficha de Amazon de la configuración base, con una
URL de example.com que solo se lee como texto.
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
    Canal,
    CausaCanalCerrado,
    CausaCanalPorRevisar,
    DemandaAmazon,
    EstadoCanal,
    Marca,
    Nivel,
    Resultado,
    marca_estimado,
)
from oip.configuracion import cargar_configuracion_texto
from oip.dinero import formatear_porcentaje
from oip.entradas.contrato import leer_observacion
from oip.evaluacion import canales, motor, referencias
from oip.evaluacion.contexto import ContextoEvaluacion, EvaluacionCanal, ObservacionRegistrada

D = Decimal

# --- Configuración ------------------------------------------------------------------------


def _config(*reemplazos: tuple[str, str]):
    texto = con_sucursales_prueba(BASE.read_text(encoding="utf-8"))
    for viejo, nuevo in reemplazos:
        assert texto.count(viejo) == 1, viejo
        texto = texto.replace(viejo, nuevo)
    return cargar_configuracion_texto(texto, origen="t14")


CONFIG = _config()
C = CONFIG.contenido
GTIN = "036000291452"
#: B26 (b): cotización capturada de $22 para la sierra de B1 (PAR-06, ``shipping.quotes``).
CONFIG_COTIZACION = _config(
    (
        "  quotes: []\n",
        f'  quotes:\n    - {{product: {{gtin: "{GTIN}"}}, shipping: 22.00, date: 2026-10-10}}\n',
    )
)

ZONA = ZoneInfo("America/Tijuana")
INSTANTE = dt.datetime(2026, 10, 14, 13, 0, tzinfo=ZONA)  # fuera de la temporada de juguetes
PRODUCTO = UUID(int=1400)
PUB_OFERTA = UUID(int=1401)
PUB_AMAZON = UUID(int=1402)
PUB_OTRA = UUID(int=1403)

_contador = iter(range(140_000, 140_000_000))
_URL = {
    TIENDA_PRUEBA: "https://tienda.example.com/p/14",
    TIENDA_PRUEBA_2: "https://otra.example.com/p/14",
    "amazon": "https://amazon.example.com/dp/T14",
}
_SIERRA = {"title": "Sierra circular de prueba", "brand": "MarcaP", "model": "SC-1"}


def _momento(dias: int = 0, horas_antes: int = 0) -> dt.datetime:
    return INSTANTE + dt.timedelta(days=dias) - dt.timedelta(hours=horas_antes)


def _obs(
    precio: str, *, comercio: str, publicacion: UUID, momento: dt.datetime, **cambios
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
        **_SIERRA,
    }
    datos.update(cambios)
    return ObservacionRegistrada(
        leer_observacion(datos), UUID(int=next(_contador)), publicacion, PRODUCTO
    )


def _ficha(buy_box: str | None, momento: dt.datetime, **listing) -> ObservacionRegistrada:
    return _obs(
        "999.00",
        comercio="amazon",
        publicacion=PUB_AMAZON,
        momento=momento,
        amazonListing={"buyBoxPrice": buy_box, **listing},
    )


def _oferta_b1(**cambios) -> ObservacionRegistrada:
    """B1: tienda física en liquidación, herramientas, 4 kg, $29.00 con tachado $129.00,
    "3 disponibles" hace 2 h, tienda a 7.75%."""
    datos = {
        "storeCode": SUCURSAL_PRUEBA,
        "gtin": GTIN,
        "weightKg": "4",
        "price": {"current": "29.00", "was": "129.00", "currency": "USD"},
        "availability": {"state": "in_stock", "quantity": 3},
        "isClearance": True,
        "purchaseMode": "tienda",
        "taxLocation": "tienda_prueba",
        **cambios,
    }
    return _obs(
        "29.00", comercio=TIENDA_PRUEBA, publicacion=PUB_OFERTA, momento=_momento(horas_antes=2),
        **datos,
    )  # fmt: skip


def _historial_b1() -> list[ObservacionRegistrada]:
    """La segunda cadena: $124 hoy (hace 8 h) y hace 60 días (60 días de historial)."""
    return [
        _obs("124.00", comercio=TIENDA_PRUEBA_2, publicacion=PUB_OTRA, momento=_momento(-60)),
        _obs("124.00", comercio=TIENDA_PRUEBA_2, publicacion=PUB_OTRA,
             momento=_momento(horas_antes=8)),
    ]  # fmt: skip


def _fichas(
    rangos_hoy: list[int | None],
    rangos_antes: list[int | None],
    *,
    vendedores: int = 5,
    vendidos: int | None = 200,
) -> list[ObservacionRegistrada]:
    """Botón de compra $119 hoy (hace 2 h) y los 6 días anteriores; ``rangos_hoy[d]`` es la
    ``rankMain`` del día −d (0 = hoy; ``None`` = sin ranking ese día); ``rangos_antes[d]``, la
    del día −(30 + d), sin botón de compra; mínimo de 60 días $109 (hace 20 días)."""
    assert len(rangos_hoy) == 7
    hoy = {"sellersNew": vendedores}
    if vendidos is not None:
        hoy["boughtLastMonth"] = vendidos
    fichas = []
    for d, rango in enumerate(rangos_hoy):
        listing = dict(hoy) if d == 0 else {"sellersNew": vendedores}
        if rango is not None:
            listing["rankMain"] = rango
        momento = _momento(horas_antes=2) if d == 0 else _momento(-d)
        fichas.append(_ficha("119.00", momento, **listing))
    for d, rango in enumerate(rangos_antes):
        listing = {"sellersNew": vendedores}
        if rango is not None:
            listing["rankMain"] = rango
        fichas.append(_ficha(None, _momento(-(30 + d)), **listing))
    fichas.append(_ficha("109.00", _momento(-20), sellersNew=vendedores))
    return fichas


def _fichas_b1(**cambios) -> list[ObservacionRegistrada]:
    """B1: ranking 6,000 los 7 días que terminan hoy y los 7 que terminan hace 30 días."""
    return _fichas([6000] * 7, [6000] * 7, **cambios)


def _contexto(oferta=None, fichas=None, configuracion=CONFIG) -> ContextoEvaluacion:
    return ContextoEvaluacion(
        id_evaluacion=UUID(int=14),
        instante=INSTANTE,
        configuracion=configuracion,
        id_version_configuracion=1,
        oferta=_oferta_b1() if oferta is None else oferta,
        historial=tuple(_historial_b1()),
        fichas_amazon=tuple(_fichas_b1() if fichas is None else fichas),
    )


def _canal(registro, canal: Canal) -> EvaluacionCanal:
    return next(c for c in registro.canales if c.canal is canal)


def _local_como_b1(local: EvaluacionCanal) -> None:
    assert local.estado is EstadoCanal.DISPONIBLE
    assert local.margen_ajustado == D("50.29")
    assert local.unidades == 2
    assert local.dias_para_recuperar == 30
    assert formatear_porcentaje(local.rendimiento_mensual_pct) == "160.9 %"
    assert local.nivel is Nivel.MUY_RECOMENDABLE
    assert local.ganancia_total == D("100.58")


def _diferencia(mayor: Decimal, menor: Decimal) -> str:
    return formatear_porcentaje((mayor - menor) / mayor * 100)


# --- B10: ranking de DEC-206 y demanda desconocida ----------------------------------------

#: B10 (a): ninguna ficha trae ``rankMain`` (0 días de datos).
_SIN_RANKING = [None] * 7
#: B10 (b): 3 días de ranking (hoy, −1 y −2); sin dato de hace 30 días.
_TRES_DIAS = [15000, 12000, 9000, None, None, None, None]


@pytest.mark.scenario("B10 (a)")
def test_b10a_sin_ranking_amazon_por_revisar_y_nivel_en_venta_local():
    contexto = _contexto(fichas=_fichas(_SIN_RANKING, _SIN_RANKING))
    ranking = canales.ranking_amazon(contexto)
    assert (ranking.promedio, ranking.dias_con_datos) == (None, 0)

    registro = motor.evaluar(contexto)
    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.POR_REVISAR
    assert amazon.causas_por_revisar == (CausaCanalPorRevisar.DEMANDA_DESCONOCIDA,)
    assert amazon.causas_cerrado == ()
    # S-30: por revisar → márgenes y nivel_calculado informativo; sin nivel, unidades,
    # días ni rendimiento, y no entra en la elección.
    assert amazon.margen_ajustado == D("44.73")
    assert formatear_porcentaje(amazon.margen_ajustado_pct) == "143.1 %"
    assert amazon.nivel_calculado is Nivel.MUY_RECOMENDABLE
    assert amazon.nivel is None
    assert (amazon.unidades, amazon.dias_para_recuperar) == (None, None)
    assert (amazon.rendimiento_mensual_pct, amazon.ganancia_total) == (None, None)

    local = _canal(registro, Canal.LOCAL)
    _local_como_b1(local)  # tope 3 (sin ranking no hay tope de 5) → 2 unidades
    assert registro.resultado is Resultado.NIVEL_ASIGNADO
    assert registro.canal_elegido is Canal.LOCAL
    assert (registro.nivel_aviso, registro.canal_aviso) == (Nivel.MUY_RECOMENDABLE, Canal.LOCAL)
    # DEMANDA DESCONOCIDA no es motivo: el otro canal tiene nivel (REQ §3.2.4).
    assert registro.motivos == ()


@pytest.mark.scenario("B10 (b)")
def test_b10b_ranking_con_3_dias_promedio_de_los_disponibles():
    contexto = _contexto(fichas=_fichas(_TRES_DIAS, _SIN_RANKING))
    ranking = canales.ranking_amazon(contexto)
    assert ranking.promedio == D(12000)  # (9,000 + 12,000 + 15,000) ÷ 3
    assert ranking.dias_con_datos == 3
    assert ranking.promedio_hace_30_dias is None

    # Umbral: 12,000 ≤ 168,440 → SUFICIENTE; sin hace 30 días no se evalúa la baja.
    tamano = C.categories[contexto.oferta.observacion.category].main_category_size
    umbral = D(tamano) * C.amazon.demand.category_rank_pct / 100  # DEC-225: tamaño × 0.5%
    assert int(umbral) == 168440  # REQ §5 lo muestra entero
    assert ranking.promedio <= umbral
    demanda = canales.demanda_en_amazon(
        contexto.oferta.observacion.category,
        ranking,
        canales.ficha_vigente(contexto),
        C,
    )
    assert demanda.demanda is DemandaAmazon.SUFICIENTE
    assert (demanda.a_la_baja, demanda.empeoramiento_pct) == (False, None)

    registro = motor.evaluar(contexto)
    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.DISPONIBLE
    assert Marca.DEMANDA_A_LA_BAJA.value not in amazon.marcas
    assert amazon.margen_ajustado == D("44.73")
    assert formatear_porcentaje(amazon.margen_ajustado_pct) == "143.1 %"
    # Días: 10,000 a 50,000 → 21; + 30 de pago. Tope: 12,000 no es < 10,000 → 3.
    assert amazon.unidades == 3
    assert amazon.dias_para_recuperar == 51
    assert formatear_porcentaje(amazon.rendimiento_mensual_pct) == "84.2 %"
    assert amazon.nivel is Nivel.MUY_RECOMENDABLE
    assert amazon.ganancia_total == D("134.19")

    _local_como_b1(_canal(registro, Canal.LOCAL))
    assert _diferencia(amazon.ganancia_total, D("100.58")) == "25.0 %"
    assert registro.resultado is Resultado.NIVEL_ASIGNADO
    assert registro.canal_elegido is Canal.AMAZON
    assert (registro.nivel_aviso, registro.canal_aviso) == (Nivel.MUY_RECOMENDABLE, Canal.AMAZON)


def test_ranking_promedia_la_ultima_rank_de_cada_dia_de_la_ventana():
    """design.md §10.3: última ``rankMain`` de cada día de los 7 que terminan el día evaluado
    (incluido); el día −7 queda fuera; "hace 30 días" = los 7 que terminan el día −30."""
    fichas = _fichas([1000, None, None, None, None, None, 3000], [5000] * 7)
    fichas.append(_ficha("119.00", _momento(horas_antes=1), rankMain=2000))  # última de hoy
    fichas.append(_ficha("119.00", _momento(-7), rankMain=900_000))  # fuera de la ventana
    ranking = canales.ranking_amazon(_contexto(fichas=fichas))
    assert ranking.promedio == D(2500)  # (2,000 + 3,000) ÷ 2
    assert ranking.dias_con_datos == 2
    assert ranking.promedio_hace_30_dias == D(5000)


def test_el_mismo_ranking_decide_umbral_dias_y_tope():
    """DEC-206: con 3 días que promedian 9,000 (< 10,000), días 7 y tope 5, aunque un día
    suelto pase de 10,000."""
    contexto = _contexto(fichas=_fichas([6000, 9000, 12000, None, None, None, None], [None] * 7))
    assert canales.ranking_amazon(contexto).promedio == D(9000)
    insumos = canales.evaluar_amazon(
        contexto,
        referencias.calcular_referencias(contexto),
        canales.costo_compra(contexto.oferta.observacion, C),
    )
    assert insumos.ranking == D(9000)  # el que usa el tope
    assert insumos.dias_tabla == C.amazon.sale_days_by_rank.fast_days == 7
    amazon = _canal(motor.evaluar(contexto), Canal.AMAZON)
    assert amazon.dias_para_recuperar == 37  # 7 + 30
    assert amazon.unidades == 3  # mín(33, 3 disponibles, tope 5)
    assert C.amazon.first_purchase_cap.boosted_units == 5


# --- B12 y B13: unidades y demanda a la baja ----------------------------------------------


@pytest.mark.scenario("B12")
def test_b12_sin_ventas_al_mes_maximo_2_unidades_y_cambia_el_canal():
    registro = motor.evaluar(_contexto(fichas=_fichas_b1(vendidos=None)))
    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.DISPONIBLE
    assert amazon.unidades == 2  # mín(2 sin ventas al mes, 3 disponibles, tope 5)
    assert C.amazon.max_units_without_monthly_sales == 2
    assert marca_estimado("unidades") == "ESTIMADO (unidades)"
    assert "ESTIMADO (unidades)" in amazon.marcas
    assert amazon.dias_para_recuperar == 37  # 7 + 30
    assert formatear_porcentaje(amazon.rendimiento_mensual_pct) == "116.1 %"
    assert amazon.ganancia_total == D("89.46")

    local = _canal(registro, Canal.LOCAL)
    _local_como_b1(local)
    assert "ESTIMADO (unidades)" not in local.marcas
    assert _diferencia(local.ganancia_total, amazon.ganancia_total) == "11.1 %"
    assert registro.resultado is Resultado.NIVEL_ASIGNADO
    assert registro.canal_elegido is Canal.LOCAL
    assert (registro.nivel_aviso, registro.canal_aviso) == (Nivel.MUY_RECOMENDABLE, Canal.LOCAL)


@pytest.mark.scenario("B13")
def test_b13_demanda_a_la_baja_es_informativa():
    contexto = _contexto(fichas=_fichas([30000] * 7, [18000] * 7, vendedores=10))
    ranking = canales.ranking_amazon(contexto)
    assert (ranking.promedio, ranking.promedio_hace_30_dias) == (D(30000), D(18000))
    demanda = canales.demanda_en_amazon(
        contexto.oferta.observacion.category, ranking, canales.ficha_vigente(contexto), C
    )
    assert demanda.demanda is DemandaAmazon.SUFICIENTE
    assert demanda.a_la_baja is True
    assert formatear_porcentaje(demanda.empeoramiento_pct) == "66.7 %"

    registro = motor.evaluar(contexto)
    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.DISPONIBLE
    assert Marca.DEMANDA_A_LA_BAJA.value in amazon.marcas
    assert Marca.DEMANDA_A_LA_BAJA.value not in registro.marcas  # marca del canal
    assert amazon.unidades == 3  # mín(200 ÷ 11 = 18, 3, tope 3)
    assert amazon.dias_para_recuperar == 51  # 21 + 30
    assert formatear_porcentaje(amazon.rendimiento_mensual_pct) == "84.2 %"
    assert amazon.ganancia_total == D("134.19")
    _local_como_b1(_canal(registro, Canal.LOCAL))
    assert registro.resultado is Resultado.NIVEL_ASIGNADO
    assert registro.canal_elegido is Canal.AMAZON
    assert registro.motivos == ()


def test_demanda_a_la_baja_solo_con_mas_del_umbral():
    """RN-004 §4: empeorar exactamente ``worsening_pct`` (50%) no marca; más, sí."""
    assert C.amazon.demand.worsening_pct == D(50)
    for hoy, marca in ((9000, False), (9001, True)):
        contexto = _contexto(fichas=_fichas([hoy] * 7, [6000] * 7))
        demanda = canales.demanda_en_amazon(
            contexto.oferta.observacion.category,
            canales.ranking_amazon(contexto),
            canales.ficha_vigente(contexto),
            C,
        )
        assert demanda.a_la_baja is marca


# --- B26: más de 6 kg ---------------------------------------------------------------------


@pytest.mark.scenario("B26 (a)")
def test_b26a_mas_de_6_kg_sin_cotizacion_cierra_amazon():
    assert C.shipping.quote_above_kg == D(6)
    assert C.shipping.quotes == ()
    registro = motor.evaluar(_contexto(oferta=_oferta_b1(weightKg="8")))
    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.CERRADO
    assert amazon.causas_cerrado == (CausaCanalCerrado.ENVIO_POR_COTIZAR,)
    assert amazon.costo_venta is None
    assert (amazon.nivel_calculado, amazon.nivel, amazon.unidades) == (None, None, None)
    _local_como_b1(_canal(registro, Canal.LOCAL))
    assert registro.resultado is Resultado.NIVEL_ASIGNADO
    assert registro.canal_elegido is Canal.LOCAL
    assert (registro.nivel_aviso, registro.canal_aviso) == (Nivel.MUY_RECOMENDABLE, Canal.LOCAL)


@pytest.mark.scenario("B26 (b)")
def test_b26b_mas_de_6_kg_con_cotizacion_desempata_el_rendimiento():
    registro = motor.evaluar(
        _contexto(oferta=_oferta_b1(weightKg="8"), configuracion=CONFIG_COTIZACION)
    )
    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.DISPONIBLE
    assert amazon.costo_venta == D("41.85")  # 17.85 + 22 + 2
    assert amazon.margen_neto == D("45.90")
    assert amazon.margen_ajustado == D("36.73")
    assert formatear_porcentaje(amazon.margen_ajustado_pct) == "117.5 %"
    assert amazon.unidades == 3
    assert amazon.ganancia_total == D("110.19")
    assert formatear_porcentaje(amazon.rendimiento_mensual_pct) == "95.3 %"
    assert amazon.nivel is Nivel.MUY_RECOMENDABLE
    assert "ESTIMADO (peso)" not in amazon.marcas

    local = _canal(registro, Canal.LOCAL)
    _local_como_b1(local)
    diferencia = (amazon.ganancia_total - local.ganancia_total) / amazon.ganancia_total * 100
    assert formatear_porcentaje(diferencia) == "8.7 %"
    assert diferencia < C.levels.channel_tiebreak_pct
    assert registro.resultado is Resultado.NIVEL_ASIGNADO
    assert registro.canal_elegido is Canal.LOCAL  # 160.9% > 95.3%
    assert (registro.nivel_aviso, registro.canal_aviso) == (Nivel.MUY_RECOMENDABLE, Canal.LOCAL)


def test_mas_de_6_kg_usa_la_cotizacion_mas_reciente_del_producto():
    """PAR-06: la cotización más reciente del mismo producto; la de otro producto no cuenta."""
    config = _config(
        (
            "  quotes: []\n",
            "  quotes:\n"
            f'    - {{product: {{gtin: "{GTIN}"}}, shipping: 30.00, date: 2026-09-01}}\n'
            f'    - {{product: {{gtin: "{GTIN}"}}, shipping: 22.00, date: 2026-10-10}}\n'
            '    - {product: {gtin: "012345678905"}, shipping: 5.00, date: 2026-10-12}\n',
        )
    )
    observacion = _oferta_b1(weightKg="8").observacion
    envio = canales.envio_amazon(observacion, config.contenido.shipping)
    assert envio is not None
    assert (envio.envio, envio.empaque, envio.peso_estimado) == (D("22.00"), D("2.00"), False)
    # Exactamente 6 kg todavía es de la tabla (> 3 y ≤ 6 kg → $14).
    seis = canales.envio_amazon(_oferta_b1(weightKg="6").observacion, C.shipping)
    assert seis is not None and seis.envio == D("14.00")
