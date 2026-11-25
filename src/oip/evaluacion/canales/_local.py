"""Venta local de CMP-13 (RN-016, RN-017, RN-008; ``oip.evaluacion.canales``)."""

from __future__ import annotations

from decimal import Decimal

from oip.catalogos import (
    Canal,
    CausaCanalCerrado,
    CausaCanalPorRevisar,
    DemandaLocal,
    Marca,
)
from oip.configuracion import (
    DemandaLocalConfig,
    Traslados,
)
from oip.dinero import TipoMonto, redondear
from oip.entradas.capturas import ComparableLocal
from oip.evaluacion import referencias as refs
from oip.evaluacion._tipos import exigir_decimal
from oip.evaluacion.canales._amazon import (
    ranking_amazon,
)
from oip.evaluacion.canales._base import (
    _CIEN,
    _ORDEN_DEMANDA_LOCAL,
    _TREINTA,
    CanalEvaluado,
    CostoCompra,
    PrecioLocal,
    _condicion_de,
    _exigir_entradas,
    _limite_cliente,
    _pct,
    _sin_repetidos,
    estado_del_canal,
)
from oip.evaluacion.contexto import ContextoEvaluacion, Referencias

# --- Venta local (RN-016, RN-017, RN-008) --------------------------------------------------


def _comparables(contexto: ContextoEvaluacion) -> tuple[ComparableLocal, ...]:
    """Comparables del mismo estado en la zona de venta local, con precio (RN-016 §4)."""
    condicion = _condicion_de(contexto.oferta.observacion)
    ciudades = contexto.configuracion.contenido.private_sellers.cities
    validos = []
    for comparable in contexto.comparables:
        ciudad = ciudades.get(comparable.city.strip())
        if comparable.condition is not condicion or ciudad is None:
            continue
        if not ciudad.in_local_sale_zone or comparable.price_usd is None:
            continue
        validos.append(comparable)
    return tuple(validos)


def precio_venta_local(
    contexto: ContextoEvaluacion,
    precio_mercado_hoy: Decimal | None,
    valor_referencia_usados: Decimal | None = None,
) -> PrecioLocal | None:
    """Precio de venta local (RN-016 §4). Estimado = el de Jesús; si no, en un nuevo,
    ``market_today_pct`` del precio de mercado hoy, y en un no nuevo,
    ``used_reference_value_pct`` de ``valor_referencia_usados`` (RN-014; T20). ``None`` sin
    estimado (``SIN PRECIO LOCAL``, o ``SIN REFERENCIA DE USADOS`` por revisar en un no nuevo
    sin valor de referencia, S-31)."""
    if not isinstance(contexto, ContextoEvaluacion):
        raise TypeError("se esperaba un ContextoEvaluacion")
    if precio_mercado_hoy is not None:
        exigir_decimal(precio_mercado_hoy, "el precio de mercado hoy")
    if valor_referencia_usados is not None:
        exigir_decimal(valor_referencia_usados, "el valor de referencia de usados")
    parametros = contexto.configuracion.contenido.local_sale
    observacion = contexto.oferta.observacion
    condicion = _condicion_de(observacion)
    aplican = [
        (e.date, i, e.price)
        for i, e in enumerate(contexto.estimados)
        if e.condition is None or e.condition is condicion  # DEC-234 (9)
    ]
    if aplican:
        estimado: Decimal | None = max(aplican)[2]  # el más reciente
    elif refs.es_nuevo(observacion):
        estimado = (
            None
            if precio_mercado_hoy is None
            else precio_mercado_hoy * _pct(parametros.market_today_pct)
        )
    elif valor_referencia_usados is not None:
        estimado = valor_referencia_usados * _pct(parametros.used_reference_value_pct)
    else:
        estimado = None
    if estimado is None:
        return None
    precios = [c.price_usd for c in _comparables(contexto) if c.price_usd is not None]
    techo = min(precios) if precios else None
    pedido = estimado if techo is None else min(estimado, techo)
    precio = redondear(
        TipoMonto.PRECIO_VENTA_LOCAL, pedido * (1 - _pct(parametros.negotiation_pct))
    )
    return PrecioLocal(precio=precio, techo=techo)


def demanda_local(contexto: ContextoEvaluacion) -> DemandaLocal:
    """Demanda local de la categoría (RN-017 §4): la captura más reciente o la inicial de
    PAR-04, un nivel menos con más de ``competition_threshold`` comparables activos."""
    if not isinstance(contexto, ContextoEvaluacion):
        raise TypeError("se esperaba un ContextoEvaluacion")
    configuracion = contexto.configuracion.contenido
    categoria = contexto.oferta.observacion.category
    capturas = [
        (d.date, i, d.level)
        for i, d in enumerate(contexto.demanda_local)
        if d.category is categoria
    ]
    nivel = (
        max(capturas)[2] if capturas else configuracion.categories[categoria].initial_local_demand
    )
    activos = sum(1 for c in _comparables(contexto) if not c.sold)
    if activos > configuracion.local_sale.demand.competition_threshold:
        posicion = _ORDEN_DEMANDA_LOCAL.index(nivel)
        nivel = _ORDEN_DEMANDA_LOCAL[min(posicion + 1, len(_ORDEN_DEMANDA_LOCAL) - 1)]
    return nivel


def dias_por_unidad_local(demanda: DemandaLocal, parametros: DemandaLocalConfig) -> int | None:
    """Días de venta por unidad (RN-017 §4): alta y media de PAR-12; baja, ``None``."""
    if not isinstance(parametros, DemandaLocalConfig):
        raise TypeError("se esperaban los parámetros de demanda local (PAR-12)")
    demanda = DemandaLocal(demanda)
    if demanda is DemandaLocal.HIGH:
        return parametros.days_per_unit_high
    if demanda is DemandaLocal.MEDIUM:
        return parametros.days_per_unit_medium
    return None


def ventas_al_mes_local(demanda: DemandaLocal, parametros: DemandaLocalConfig) -> int | None:
    """Ventas locales al mes = 30 ÷ días por unidad, redondeado hacia abajo (RN-017 §4).
    ``None`` con demanda baja."""
    dias = dias_por_unidad_local(demanda, parametros)
    return None if dias is None else _TREINTA // dias


def costo_entrega(traslados: Traslados) -> Decimal:
    """Costo de entrega por defecto (RN-008 §4.3; S-24), redondeado una vez."""
    if not isinstance(traslados, Traslados):
        raise TypeError("se esperaban los traslados (PAR-12)")
    valor = (
        traslados.default_delivery_km * traslados.cost_per_km
        + traslados.default_delivery_hours * traslados.hour_value
        + traslados.fixed_costs
    )
    return redondear(TipoMonto.TRASLADO_ENTREGA, valor)


def evaluar_local(
    contexto: ContextoEvaluacion,
    referencias: Referencias,
    costo: CostoCompra | None,
) -> CanalEvaluado:
    """Estado, causas, precio y costo de venta, insumos y marcas de la venta local (REQ §3.2
    paso 8, §3.2.1)."""
    contexto, referencias = _exigir_entradas(contexto, referencias, costo)
    configuracion = contexto.configuracion.contenido
    observacion = contexto.oferta.observacion
    parametros = configuracion.local_sale
    precio = precio_venta_local(
        contexto, referencias.precio_mercado_hoy, referencias.valor_referencia_usados
    )
    demanda = demanda_local(contexto)
    ventas = ventas_al_mes_local(demanda, parametros.demand)
    # S-31: un no nuevo sin valor de referencia deja la venta local por revisar.
    sin_referencia = not refs.es_nuevo(observacion) and referencias.valor_referencia_usados is None

    cerrado: list[CausaCanalCerrado] = []
    por_revisar: list[CausaCanalPorRevisar] = []
    if demanda is DemandaLocal.LOW:
        cerrado.append(CausaCanalCerrado.DEMANDA_LOCAL_BAJA)
    if precio is None and not sin_referencia:
        cerrado.append(CausaCanalCerrado.SIN_PRECIO_LOCAL)
    if ventas is not None and ventas < 1:
        cerrado.append(CausaCanalCerrado.SIN_ROTACION)  # S-08
    if sin_referencia:
        por_revisar.append(CausaCanalPorRevisar.SIN_REFERENCIA_DE_USADOS)
    estado = estado_del_canal(tuple(cerrado), tuple(por_revisar))
    marcas: list[str] = [c.value for c in cerrado]
    if precio is not None and precio.techo is None:
        marcas.append(Marca.SIN_COMPARABLES_LOCALES.value)  # RN-016 §11
    ranking = ranking_amazon(contexto)
    return CanalEvaluado(
        canal=Canal.LOCAL,
        estado=estado,
        causas_cerrado=tuple(cerrado),
        causas_por_revisar=tuple(por_revisar),
        precio_venta=None if precio is None else precio.precio,
        # RN-001 §4: costo de entrega (RN-008) + otros; PAR-12 no trae otros costos locales.
        costo_venta=None if precio is None else costo_entrega(parametros.transport),
        tasa_devolucion_pct=parametros.return_rate_pct,
        # RN-005: la venta local no tiene pérdida por devolución propia ("—"): se pierde todo.
        perdida_devolucion_pct=_CIEN,
        ventas_al_mes=ventas,
        dias_tabla=None,
        dias_por_unidad=dias_por_unidad_local(demanda, parametros.demand),
        dias_pago=parametros.payment_days,
        disponibles=observacion.availability.quantity,
        limite_cliente=_limite_cliente(observacion, configuracion),
        ranking=ranking.promedio,
        baja_por_competencia=False,  # RN-009 §4.3: la baja por competencia es solo de Amazon
        marcas=_sin_repetidos(marcas),
    )
