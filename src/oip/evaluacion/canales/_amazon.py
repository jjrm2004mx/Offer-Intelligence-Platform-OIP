"""Canal Amazon de CMP-13 (RN-004, RN-006; DEC-206; ``oip.evaluacion.canales``)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from zoneinfo import ZoneInfo

from oip.catalogos import (
    Canal,
    Categoria,
    CausaCanalCerrado,
    CausaCanalPorRevisar,
    DemandaAmazon,
    EstadoCanal,
    Marca,
    marca_estimado,
)
from oip.configuracion import (
    Comision,
    ComisionConUmbral,
    ComisionFija,
    ComisionPorTramos,
    Configuracion,
    CuentaAmazon,
    Envio,
    Listas,
    TasaAsignada,
    TasaPropia,
)
from oip.dinero import TipoMonto, redondear
from oip.entradas.contrato import FichaAmazon, Observacion
from oip.evaluacion import referencias as refs
from oip.evaluacion._tipos import exigir_decimal
from oip.evaluacion.canales._base import (
    _CIEN,
    CanalEvaluado,
    CostoCompra,
    DemandaEnAmazon,
    EnvioAmazon,
    Ranking,
    TasaDevolucion,
    _en_temporada,
    _es_el_producto,
    _exigir_entradas,
    _limite_cliente,
    _marca_en,
    _pct,
    _sin_repetidos,
    estado_del_canal,
)
from oip.evaluacion.contexto import ContextoEvaluacion, ObservacionRegistrada, Referencias

# --- Amazon (RN-004, RN-006; DEC-206) ------------------------------------------------------


def _fichas(contexto: ContextoEvaluacion) -> tuple[ObservacionRegistrada, ...]:
    """Fichas de Amazon del contexto (historial y fichas), sin repetir y hasta el instante."""
    vistas: set[object] = set()
    fichas = []
    for registrada in (*contexto.historial, *contexto.fichas_amazon):
        observacion = registrada.observacion
        if observacion.amazon_listing is None or registrada.id in vistas:
            continue
        if observacion.extracted_at > contexto.instante:
            continue
        vistas.add(registrada.id)
        fichas.append(registrada)
    return tuple(sorted(fichas, key=lambda r: (r.observacion.extracted_at, str(r.id))))


def _promedio(valores: list[int]) -> Decimal | None:
    if not valores:
        return None
    return Decimal(sum(valores)) / Decimal(len(valores))


def ranking_amazon(contexto: ContextoEvaluacion) -> Ranking:
    """Ranking de DEC-206 con las fichas de Amazon del contexto (design.md §10.3)."""
    if not isinstance(contexto, ContextoEvaluacion):
        raise TypeError("se esperaba un ContextoEvaluacion")
    parametros = contexto.configuracion.contenido.amazon.demand
    zona = ZoneInfo(contexto.configuracion.contenido.general.timezone)
    por_dia: dict[dt.date, int] = {}
    for registrada in _fichas(contexto):  # en orden: la última del día queda al final
        ficha = registrada.observacion.amazon_listing
        if ficha is None or ficha.rank_main is None:
            continue
        por_dia[refs.dia_calendario(registrada.observacion.extracted_at, zona)] = ficha.rank_main
    hoy = refs.dia_evaluado(contexto)
    ventana = dt.timedelta(days=parametros.rank_window_days - 1)
    atras = dt.timedelta(days=parametros.trend_lookback_days)

    def _dias(fin: dt.date) -> list[int]:
        return [r for d, r in sorted(por_dia.items()) if fin - ventana <= d <= fin]

    actuales = _dias(hoy)
    return Ranking(
        promedio=_promedio(actuales),
        dias_con_datos=len(actuales),
        promedio_hace_30_dias=_promedio(_dias(hoy - atras)),
    )


def ficha_vigente(contexto: ContextoEvaluacion) -> FichaAmazon | None:
    """``amazonListing`` de la ficha de Amazon más reciente del contexto (vendedores y
    comprados el mes pasado). ``None`` si el producto no tiene ficha."""
    if not isinstance(contexto, ContextoEvaluacion):
        raise TypeError("se esperaba un ContextoEvaluacion")
    fichas = _fichas(contexto)
    return fichas[-1].observacion.amazon_listing if fichas else None


def demanda_en_amazon(
    categoria: Categoria,
    ranking: Ranking,
    ficha: FichaAmazon | None,
    configuracion: Configuracion,
) -> DemandaEnAmazon:
    """Demanda en Amazon (RN-004 §4 y §11; DEC-206, DEC-225) y ``DEMANDA A LA BAJA`` (el
    promedio de hoy empeoró más de ``worsening_pct`` contra el de hace 30 días)."""
    if not isinstance(ranking, Ranking) or not isinstance(configuracion, Configuracion):
        raise TypeError("se esperaban el Ranking y la Configuracion")
    parametros = configuracion.amazon.demand
    valores = configuracion.categories[Categoria(categoria)]
    promedio = ranking.promedio
    # Cada condición: True (se cumple), False (no se cumple) o None (no se sabe).
    condiciones: list[bool | None] = []
    if promedio is None or valores.main_category_size is None:
        condiciones.append(None)
    else:
        umbral = Decimal(valores.main_category_size) * _pct(parametros.category_rank_pct)
        condiciones.append(promedio <= umbral)
    if valores.subcategory_rank_required:
        sub = None if ficha is None else ficha.rank_sub
        condiciones.append(None if sub is None else sub <= parametros.subcategory_max_rank)
    vendedores = None if ficha is None else ficha.sellers_new
    condiciones.append(None if vendedores is None else vendedores <= parametros.max_new_sellers)
    if False in condiciones:
        demanda = DemandaAmazon.INSUFICIENTE
    elif None in condiciones:
        demanda = DemandaAmazon.DESCONOCIDA
    else:
        demanda = DemandaAmazon.SUFICIENTE
    empeoramiento = None
    antes = ranking.promedio_hace_30_dias
    if promedio is not None and antes is not None and antes > 0:
        empeoramiento = (promedio - antes) / antes * _CIEN
    a_la_baja = empeoramiento is not None and empeoramiento > parametros.worsening_pct
    return DemandaEnAmazon(demanda=demanda, a_la_baja=a_la_baja, empeoramiento_pct=empeoramiento)


def comision_amazon(precio_venta: Decimal, comision: Comision) -> Decimal:
    """Comisión de Amazon de una unidad (RN-006 §4.1; DEC-217), redondeada una vez, con el
    mínimo por unidad: ``flat`` (% del precio), ``total_threshold`` (% del precio completo según
    el umbral) o ``tiers`` (parte por parte)."""
    precio = exigir_decimal(precio_venta, "el precio de venta")
    if precio < 0:
        raise ValueError("el precio de venta no puede ser negativo")
    if isinstance(comision, ComisionFija):
        valor = precio * _pct(comision.rate_pct)
    elif isinstance(comision, ComisionConUmbral):
        if precio <= comision.threshold:
            valor = precio * _pct(comision.rate_pct_at_or_below)
        else:
            valor = precio * _pct(comision.rate_pct_above)
    elif isinstance(comision, ComisionPorTramos):
        valor = Decimal(0)
        desde = Decimal(0)
        for tramo in comision.tiers:
            hasta = precio if tramo.up_to is None else min(precio, tramo.up_to)
            if hasta > desde:
                valor += (hasta - desde) * _pct(tramo.rate_pct)
            if tramo.up_to is None or precio <= tramo.up_to:
                break
            desde = tramo.up_to
    else:
        raise TypeError("se esperaba una comisión de PAR-04 (flat, total_threshold o tiers)")
    return redondear(TipoMonto.COMISION, max(valor, comision.min_per_unit))


def _cotizacion(observacion: Observacion, envio: Envio) -> Decimal | None:
    """La cotización capturada más reciente del producto (PAR-06), o ``None``."""
    del_producto = [
        (c.date, i, c.shipping)
        for i, c in enumerate(envio.quotes)
        if _es_el_producto(c.product, observacion)
    ]
    return max(del_producto)[2] if del_producto else None


def envio_amazon(observacion: Observacion, envio: Envio) -> EnvioAmazon | None:
    """Envío FBM y empaque por peso (RN-006 §4.2; S-06): el primer rango con
    ``max_kg`` ≥ peso; sin peso, ``unknown_weight``; con más de ``quote_above_kg``, la
    cotización capturada del producto o ``None`` (``ENVÍO POR COTIZAR``)."""
    if not isinstance(observacion, Observacion) or not isinstance(envio, Envio):
        raise TypeError("se esperaban la observación y el envío (PAR-06)")
    peso = observacion.weight_kg
    if peso is None:
        sin_peso = envio.unknown_weight
        return EnvioAmazon(
            envio=redondear(TipoMonto.ENVIO, sin_peso.shipping),
            empaque=sin_peso.packaging,
            peso_estimado=True,
        )
    if peso > envio.quote_above_kg:
        cotizado = _cotizacion(observacion, envio)
        if cotizado is None:
            return None
        # El empaque de más de 6 kg es el del último rango (RN-001: "$2 más de 1 kg").
        return EnvioAmazon(
            envio=redondear(TipoMonto.ENVIO, cotizado),
            empaque=envio.weight_bands[-1].packaging,
            peso_estimado=False,
        )
    rango = next(r for r in envio.weight_bands if peso <= r.max_kg)
    return EnvioAmazon(
        envio=redondear(TipoMonto.ENVIO, rango.shipping),
        empaque=rango.packaging,
        peso_estimado=False,
    )


def tasa_devolucion_amazon(
    categoria: Categoria, configuracion: Configuracion
) -> TasaDevolucion | None:
    """Tasa de devolución de la categoría (PAR-04; S-27): propia, o asignada de otra categoría
    (estimada). ``None`` sin tasa (``TASA DE DEVOLUCIÓN DESCONOCIDA``)."""
    valores = configuracion.categories[Categoria(categoria)]
    tasa = valores.return_rate
    if isinstance(tasa, TasaPropia):
        return TasaDevolucion(
            tasa_pct=tasa.rate_pct, perdida_pct=valores.return_loss_pct, estimada=False
        )
    if isinstance(tasa, TasaAsignada):
        origen = configuracion.categories[tasa.from_category].return_rate
        if isinstance(origen, TasaPropia):  # lo garantiza la configuración
            return TasaDevolucion(
                tasa_pct=origen.rate_pct, perdida_pct=valores.return_loss_pct, estimada=True
            )
    return None


def restringido_en_amazon(
    observacion: Observacion, configuracion: Configuracion, dia: dt.date
) -> bool:
    """Restricción sin cuenta de vendedor (RN-006 §4.3; S-09, S-10): categoría restringida,
    marca o producto en la tabla de PAR-05, o juguete en temporada (``dia`` en
    ``toy_season``)."""
    if type(dia) is not dt.date:
        raise TypeError("dia debe ser una fecha (date)")
    listas = configuracion.lists
    if configuracion.categories[observacion.category].amazon_restricted:
        return True
    if _marca_en(listas.amazon_restricted_brands, observacion):
        return True
    if any(_es_el_producto(p, observacion) for p in listas.amazon_restricted_products):
        return True
    return observacion.category is Categoria.TOYS and _en_temporada(dia, listas.toy_season)


def material_peligroso(observacion: Observacion, listas: Listas) -> bool:
    """``MATERIAL PELIGROSO`` por marca o producto (PAR-05; S-07): solo marca, no cierra."""
    if not isinstance(listas, Listas):
        raise TypeError("se esperaban las listas (PAR-05)")
    return _marca_en(listas.hazmat_brands, observacion) or any(
        _es_el_producto(p, observacion) for p in listas.hazmat_products
    )


def ventas_al_mes_amazon(ficha: FichaAmazon | None) -> int | None:
    """Ventas al mes que le tocan a Jesús (RN-005 §4) = comprados el mes pasado ÷ (vendedores
    + 1), redondeado hacia abajo. ``None`` sin comprados o sin vendedores."""
    if ficha is None:
        return None
    if not isinstance(ficha, FichaAmazon):
        raise TypeError("se esperaba la ficha de Amazon (amazonListing)")
    if ficha.bought_last_month is None or ficha.sellers_new is None:
        return None
    return ficha.bought_last_month // (ficha.sellers_new + 1)


def competencia_mas_barata(
    precio_mercado_hoy: Decimal | None, precio_venta_amazon: Decimal | None, umbral_pct: Decimal
) -> bool:
    """``COMPETENCIA MÁS BARATA`` (RN-002 §4.3): mercado hoy < venta en Amazon × (1 −
    umbral). Sin alguno de los dos precios no se evalúa (RN-002 §11)."""
    umbral = exigir_decimal(umbral_pct, "el umbral de competencia")
    if precio_mercado_hoy is None or precio_venta_amazon is None:
        return False
    hoy = exigir_decimal(precio_mercado_hoy, "el precio de mercado hoy")
    venta = exigir_decimal(precio_venta_amazon, "el precio de venta en Amazon")
    return hoy < venta * (1 - _pct(umbral))


def _dias_por_ranking(ranking: Decimal | None, configuracion: Configuracion) -> int | None:
    """Días de venta en Amazon por ranking (RN-005 §4; PAR-11)."""
    if ranking is None:
        return None
    tabla = configuracion.amazon.sale_days_by_rank
    if ranking < tabla.fast_below_rank:
        return tabla.fast_days
    if ranking <= tabla.medium_up_to_rank:
        return tabla.medium_days
    return tabla.slow_days


def _dias_pago_amazon(configuracion: Configuracion) -> int:
    pago = configuracion.amazon.payment_days
    if configuracion.general.amazon_account is CuentaAmazon.ESTABLISHED:
        return pago.established
    return pago.new


def evaluar_amazon(
    contexto: ContextoEvaluacion,
    referencias: Referencias,
    costo: CostoCompra | None,
) -> CanalEvaluado:
    """Estado, causas, precio y costo de venta, insumos y marcas del canal Amazon (REQ §3.2
    paso 7, §3.2.1)."""
    contexto, referencias = _exigir_entradas(contexto, referencias, costo)
    configuracion = contexto.configuracion.contenido
    observacion = contexto.oferta.observacion
    precio = referencias.precio_venta_amazon
    ranking = ranking_amazon(contexto)
    ficha = ficha_vigente(contexto)
    demanda = demanda_en_amazon(observacion.category, ranking, ficha, configuracion)
    comision_cfg = configuracion.categories[observacion.category].commission
    tasa = tasa_devolucion_amazon(observacion.category, configuracion)
    envio = envio_amazon(observacion, configuracion.shipping)
    ventas = ventas_al_mes_amazon(ficha)

    # Causas de cerrado en el orden del catálogo (REQ §3.2.1).
    cerrado: list[CausaCanalCerrado] = []
    if precio is None:
        cerrado.append(CausaCanalCerrado.SIN_PRECIO_DE_VENTA_EN_AMAZON)
    if demanda.demanda is DemandaAmazon.INSUFICIENTE:
        cerrado.append(CausaCanalCerrado.DEMANDA_INSUFICIENTE_EN_AMAZON)
    if restringido_en_amazon(observacion, configuracion, refs.dia_evaluado(contexto)):
        cerrado.append(CausaCanalCerrado.NO_VENDIBLE_EN_AMAZON)
    if comision_cfg is None:
        cerrado.append(CausaCanalCerrado.COMISION_DESCONOCIDA)
    if tasa is None:
        cerrado.append(CausaCanalCerrado.TASA_DE_DEVOLUCION_DESCONOCIDA)
    if envio is None:
        cerrado.append(CausaCanalCerrado.ENVIO_POR_COTIZAR)
    if not refs.es_nuevo(observacion):
        cerrado.append(CausaCanalCerrado.PRODUCTO_NO_NUEVO)  # S-12
    if ventas is not None and ventas < 1:
        cerrado.append(CausaCanalCerrado.SIN_ROTACION)  # S-08
    por_revisar: list[CausaCanalPorRevisar] = []
    if demanda.demanda is DemandaAmazon.DESCONOCIDA:
        por_revisar.append(CausaCanalPorRevisar.DEMANDA_DESCONOCIDA)
    estado = estado_del_canal(tuple(cerrado), tuple(por_revisar))

    costo_venta = None
    if precio is not None and comision_cfg is not None and envio is not None:
        costo_venta = (
            comision_amazon(precio, comision_cfg)
            + envio.envio
            + envio.empaque
            + configuracion.amazon.other_selling_costs
        )
    competencia = competencia_mas_barata(
        referencias.precio_mercado_hoy, precio, configuracion.levels.cheaper_competition_pct
    )
    marcas: list[str] = [c.value for c in cerrado]
    if material_peligroso(observacion, configuracion.lists):
        marcas.append(Marca.MATERIAL_PELIGROSO.value)
    if demanda.a_la_baja:
        marcas.append(Marca.DEMANDA_A_LA_BAJA.value)
    if competencia:
        marcas.append(Marca.COMPETENCIA_MAS_BARATA.value)
    if costo_venta is not None:
        if envio is not None and envio.peso_estimado:
            marcas.append(marca_estimado("peso"))
        if estado is not EstadoCanal.CERRADO and tasa is not None and tasa.estimada:
            marcas.append(marca_estimado("devolución"))
        # RN-001 §11 y §10; REQ §3.2.3; RNF-9: todo cálculo de Amazon es estimado.
        marcas.append(Marca.MARGEN_ESTIMADO.value)
        marcas.append(Marca.EMPAQUE_POR_CONFIRMAR.value)
    return CanalEvaluado(
        canal=Canal.AMAZON,
        estado=estado,
        causas_cerrado=tuple(cerrado),
        causas_por_revisar=tuple(por_revisar),
        precio_venta=precio,
        costo_venta=costo_venta,
        tasa_devolucion_pct=None if tasa is None else tasa.tasa_pct,
        perdida_devolucion_pct=None if tasa is None else tasa.perdida_pct,
        ventas_al_mes=ventas,
        dias_tabla=_dias_por_ranking(ranking.promedio, configuracion),
        dias_por_unidad=None,
        dias_pago=_dias_pago_amazon(configuracion),
        disponibles=observacion.availability.quantity,
        limite_cliente=_limite_cliente(observacion, configuracion),
        ranking=ranking.promedio,
        baja_por_competencia=competencia,
        marcas=_sin_repetidos(marcas),
    )
