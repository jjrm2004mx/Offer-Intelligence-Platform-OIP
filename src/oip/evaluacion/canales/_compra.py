"""Costo de compra de CMP-13 (RN-001 §4; PAR-07; ``oip.evaluacion.canales``)."""

from __future__ import annotations

from decimal import Decimal

from oip.configuracion import (
    Configuracion,
    Impuestos,
)
from oip.dinero import TipoMonto, redondear
from oip.entradas.contrato import Observacion
from oip.evaluacion.canales._base import (
    CostoCompra,
    _pct,
)

# --- Costo de compra (RN-001 §4; PAR-07) ---------------------------------------------------


def tasa_impuesto(observacion: Observacion, impuestos: Impuestos) -> Decimal:
    """Tasa de impuesto en puntos (PAR-07; DEC-220): la de ``taxLocation`` o la de respaldo;
    0 en la compra a un particular si ``private_sellers_exempt`` (S-14)."""
    if not isinstance(observacion, Observacion) or not isinstance(impuestos, Impuestos):
        raise TypeError("se esperaban la observación y los impuestos (PAR-07)")
    if observacion.es_particular and impuestos.private_sellers_exempt:
        return Decimal(0)
    ubicacion = observacion.tax_location
    if ubicacion is not None:
        tasa = impuestos.locations.get(ubicacion.strip())
        if tasa is not None:
            return tasa.rate_pct
    return impuestos.fallback_rate_pct


def costo_recogida(observacion: Observacion, configuracion: Configuracion) -> Decimal | None:
    """Traslado de recogida de una compra a particular (RN-008 §4; RN-014 §4; S-14): km y
    horas de la ciudad ``pickupLocation`` (PAR-09 ``private_sellers.cities``) con las tarifas
    y los costos fijos de PAR-12 (``local_sale.transport``), redondeado una vez
    (``TipoMonto.TRASLADO_RECOGIDA``; B18: $9.50). ``None`` si la oferta no es de un
    particular o su ciudad no está en PAR-09."""
    if not isinstance(observacion, Observacion) or not isinstance(configuracion, Configuracion):
        raise TypeError("se esperaban la observación y la Configuracion")
    if not observacion.es_particular or observacion.pickup_location is None:
        return None
    ciudad = configuracion.private_sellers.cities.get(observacion.pickup_location.strip())
    if ciudad is None:
        return None
    tarifas = configuracion.local_sale.transport
    valor = (
        ciudad.pickup_km * tarifas.cost_per_km
        + ciudad.pickup_hours * tarifas.hour_value
        + tarifas.fixed_costs
    )
    return redondear(TipoMonto.TRASLADO_RECOGIDA, valor)


def costo_compra(observacion: Observacion, configuracion: Configuracion) -> CostoCompra | None:
    """Costo de compra de la oferta (RN-001 §4; REQ §3.2 paso 6). ``None`` sin precio. El envío
    hacia mí es ``shipping.toMeCost`` o el de ``shipping_to_me_default`` (PAR-06); con un
    particular se suma la recogida (``costo_recogida``; T20)."""
    if not isinstance(configuracion, Configuracion):
        raise TypeError("se esperaba la Configuracion")
    precio = observacion.price.current
    if precio is None or observacion.precio_invalido:
        return None
    tasa = tasa_impuesto(observacion, configuracion.taxes)
    impuesto = redondear(TipoMonto.IMPUESTO, precio * _pct(tasa))
    hacia_mi = configuracion.shipping.shipping_to_me_default
    if observacion.shipping is not None and observacion.shipping.to_me_cost is not None:
        hacia_mi = observacion.shipping.to_me_cost
    envio = redondear(TipoMonto.ENVIO, hacia_mi)
    # RN-001 §4 y RN-008: la recogida con un particular entra en el costo de compra (S-14).
    recogida = costo_recogida(observacion, configuracion) or Decimal(0)
    total = redondear(TipoMonto.COSTO_COMPRA, precio + impuesto + envio + recogida)
    return CostoCompra(
        precio=precio,
        tasa_impuesto_pct=tasa,
        impuesto=impuesto,
        envio_hacia_mi=envio,
        total=total,
        recogida=recogida,
    )
