"""Pasos 4 y 5 de REQ §3.2: descuento y calidad del precio (CMP-12; RN-003 v2, RN-012 v1).

Por ahora (T09) solo lo mínimo para la franja: el **descuento real** contra el precio
habitual que aplica (el congelado durante un episodio de liquidación) y su **franja**
(RN-003 v2; REQ §3.2 paso 4; DEC-198). El descuento anunciado con sus marcas y la calidad
del precio los agrega T10.

- Descuento real = (precio habitual − precio de la oferta) ÷ precio habitual, en puntos
  (25 = 25%) y **sin redondear** (DEC-207, DEC-222): se compara así y solo se muestra a 1
  decimal (``oip.dinero.formatear_porcentaje``).
- Franja, con los cortes de PAR-10 (``discount_quality``): menor que
  ``discard_below_pct`` → ``MERCADO YA BARATO`` (descarta); desde ese corte y menor que
  ``reference_only_below_pct`` → ``SOLO REFERENCIA``; desde ahí, sigue (sin motivo).
"""

from __future__ import annotations

from decimal import Decimal

from oip.catalogos import Motivo
from oip.configuracion import DescuentoYCalidad

__all__ = ["descuento_real", "franja"]

_CIEN = Decimal(100)


def _decimal(valor: object, nombre: str) -> Decimal:
    if not isinstance(valor, Decimal) or not valor.is_finite():
        raise TypeError(f"{nombre} debe ser un Decimal finito")
    return valor


def descuento_real(precio_habitual: Decimal, precio: Decimal) -> Decimal:
    """Descuento real en puntos, sin redondear (RN-003 v2). El habitual debe ser > 0."""
    habitual = _decimal(precio_habitual, "el precio habitual")
    oferta = _decimal(precio, "el precio de la oferta")
    if habitual <= 0:
        raise ValueError("el precio habitual debe ser mayor que cero")
    return (habitual - oferta) / habitual * _CIEN


def franja(real: Decimal, parametros: DescuentoYCalidad) -> Motivo | None:
    """Motivo de la franja del descuento real, o ``None`` si sigue (≥ el segundo corte)."""
    real = _decimal(real, "el descuento real")
    if real < parametros.discard_below_pct:
        return Motivo.MERCADO_YA_BARATO
    if real < parametros.reference_only_below_pct:
        return Motivo.SOLO_REFERENCIA
    return None
