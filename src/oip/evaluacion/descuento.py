"""Pasos 4 y 5 de REQ §3.2: descuento y calidad del precio (CMP-12; RN-003 v2, RN-012 v1).

Todos los porcentajes van en puntos (25 = 25%) y **sin redondear** (DEC-207, DEC-222): se
comparan así y solo se muestran a 1 decimal (``oip.dinero.formatear_porcentaje``). Ninguna
cifra está en el código: los cortes, el factor y los umbrales salen de PAR-10
(``discount_quality``).

Paso 4 (RN-003 v2 §4; REQ §3.2 paso 4):

- **Descuento anunciado** = (precio tachado − precio de la oferta) ÷ precio tachado. Solo
  con precio tachado (``price.was``) mayor que cero; si no, no disponible (RN-003 §11). Nunca
  califica la oferta.
- **Descuento real** = (precio habitual − precio de la oferta) ÷ precio habitual, contra el
  habitual que aplica (el congelado durante un episodio de liquidación; DEC-198).
- **Franja**, con los cortes de PAR-10: menor que ``discard_below_pct`` →
  ``MERCADO YA BARATO`` (descarta, también un negativo); desde ese corte y menor que
  ``reference_only_below_pct`` → ``SOLO REFERENCIA``; desde ahí, sigue (sin motivo).
- **Marcas** (informativas, no cambian el resultado): ``PRECIO ANTES INFLADO`` si el precio
  tachado es mayor que ``inflated_factor`` veces el precio típico de esa tienda (con
  historial suficiente; el descuento anunciado se ignora: no entra en nada);
  ``DESCUENTO ANUNCIADO NO COMPROBADO`` si hay precio tachado pero no historial suficiente
  de esa tienda para comprobarlo.

Paso 5 (RN-012 v1 §4, S-22, S-28; REQ §3.2 paso 5): **calidad del precio**, la primera
clase que se cumple:

1. **Descuento cuestionable:** ``PRECIO ANTES INFLADO``; o, **sin historial suficiente**
   (S-28), un descuento anunciado que solo se compara contra un comercio. (El vendedor
   externo sin confirmar, RN-015, lo agrega su tarea, T19.)
2. Sin historial suficiente (sin precio habitual), la calidad no pasa de Precio competitivo:
   **Precio competitivo** si está entre los más baratos; si no, **Precio normal** (S-22).
3. Con precio habitual: precio arriba del habitual → **Precio normal** (S-22). Si no, con
   descuento ≥ ``good_offer_min_discount_pct``, entre los más baratos y datos de al menos
   ``min_other_retailers`` comercios además del evaluado: **Oferta excepcional** si además
   el precio es **menor** que el mínimo registrado con ``exceptional_min_history_days`` días
   de historial o más, si no **Buena oferta**. Entre los más baratos sin lo demás:
   **Precio competitivo**. Lo demás: **Precio normal**.

"Entre los más baratos" = precio ≤ precio de mercado hoy × (1 + ``cheapest_tolerance_pct``
%); sin precio de mercado hoy no se cumple (RN-012 §11). "Comercios" = cadenas distintas de
la evaluada (DEC-216; design.md §10.4). En un **usado** la calidad **no aplica** (DEC-215).
Sin precio habitual ni precio de mercado hoy no hay datos y no hay calidad. El MSRP solo se
muestra (DEC-218): no entra aquí.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

from oip.catalogos import CalidadPrecio, Marca, Motivo
from oip.configuracion import DescuentoYCalidad

__all__ = [
    "DatosCalidad",
    "calidad_del_precio",
    "descuento_anunciado",
    "descuento_real",
    "franja",
    "marcas_del_anunciado",
]

_CIEN = Decimal(100)
#: S-28 / RN-012 §4: el descuento anunciado "solo se puede comparar contra un comercio".
_UN_COMERCIO = 1


def _decimal(valor: object, nombre: str) -> Decimal:
    if not isinstance(valor, Decimal) or not valor.is_finite():
        raise TypeError(f"{nombre} debe ser un Decimal finito")
    return valor


def _decimal_o_none(valor: object, nombre: str) -> Decimal | None:
    return None if valor is None else _decimal(valor, nombre)


def descuento_real(precio_habitual: Decimal, precio: Decimal) -> Decimal:
    """Descuento real en puntos, sin redondear (RN-003 v2). El habitual debe ser > 0."""
    habitual = _decimal(precio_habitual, "el precio habitual")
    oferta = _decimal(precio, "el precio de la oferta")
    if habitual <= 0:
        raise ValueError("el precio habitual debe ser mayor que cero")
    return (habitual - oferta) / habitual * _CIEN


def descuento_anunciado(precio_tachado: Decimal | None, precio: Decimal) -> Decimal | None:
    """Descuento anunciado en puntos, sin redondear (RN-003 v2 §4). ``None`` sin precio
    tachado o con un tachado que no es mayor que cero (no disponible, RN-003 §11)."""
    tachado = _decimal_o_none(precio_tachado, "el precio tachado")
    oferta = _decimal(precio, "el precio de la oferta")
    if tachado is None or tachado <= 0:
        return None
    return (tachado - oferta) / tachado * _CIEN


def franja(real: Decimal, parametros: DescuentoYCalidad) -> Motivo | None:
    """Motivo de la franja del descuento real, o ``None`` si sigue (≥ el segundo corte)."""
    real = _decimal(real, "el descuento real")
    if real < parametros.discard_below_pct:
        return Motivo.MERCADO_YA_BARATO
    if real < parametros.reference_only_below_pct:
        return Motivo.SOLO_REFERENCIA
    return None


def marcas_del_anunciado(
    precio_tachado: Decimal | None,
    precio_tipico_tienda: Decimal | None,
    parametros: DescuentoYCalidad,
) -> tuple[Marca, ...]:
    """Marcas de RN-003 §4 sobre el precio tachado: ``PRECIO ANTES INFLADO`` (tachado mayor
    que ``inflated_factor`` × el precio típico de la tienda) o ``DESCUENTO ANUNCIADO NO
    COMPROBADO`` (hay tachado, pero la tienda no tiene historial suficiente). Sin tachado,
    ninguna."""
    tachado = _decimal_o_none(precio_tachado, "el precio tachado")
    tipico = _decimal_o_none(precio_tipico_tienda, "el precio típico de la tienda")
    if tachado is None or tachado <= 0:
        return ()
    if tipico is None:
        return (Marca.DESCUENTO_ANUNCIADO_NO_COMPROBADO,)
    if tachado > parametros.inflated_factor * tipico:
        return (Marca.PRECIO_ANTES_INFLADO,)
    return ()


@dataclasses.dataclass(frozen=True, slots=True)
class DatosCalidad:
    """Lo que necesita la calidad del precio de una oferta nueva (RN-012 §6).

    ``descuento_real`` (puntos, sin redondear) solo existe con ``precio_habitual``;
    ``otros_comercios`` = cadenas distintas de la evaluada con dato de mercado hoy;
    ``minimo_registrado`` y ``dias_historial``, del producto en todos los comercios (S-22).
    """

    precio: Decimal
    precio_habitual: Decimal | None
    descuento_real: Decimal | None
    precio_mercado_hoy: Decimal | None
    otros_comercios: int
    minimo_registrado: Decimal | None
    dias_historial: int
    descuento_anunciado: Decimal | None
    precio_antes_inflado: bool

    def __post_init__(self) -> None:
        _decimal(self.precio, "el precio de la oferta")
        _decimal_o_none(self.precio_habitual, "el precio habitual")
        _decimal_o_none(self.descuento_real, "el descuento real")
        _decimal_o_none(self.precio_mercado_hoy, "el precio de mercado hoy")
        _decimal_o_none(self.minimo_registrado, "el mínimo registrado")
        _decimal_o_none(self.descuento_anunciado, "el descuento anunciado")
        for nombre in ("otros_comercios", "dias_historial"):
            valor = getattr(self, nombre)
            if type(valor) is not int or valor < 0:
                raise TypeError(f"{nombre} debe ser un entero ≥ 0")
        if type(self.precio_antes_inflado) is not bool:
            raise TypeError("precio_antes_inflado debe ser bool")
        if (self.precio_habitual is None) != (self.descuento_real is None):
            raise ValueError("el descuento real existe si y solo si hay precio habitual")


def calidad_del_precio(datos: DatosCalidad, parametros: DescuentoYCalidad) -> CalidadPrecio | None:
    """Calidad del precio de una oferta **nueva** (RN-012 v1 §4, S-22, S-28). ``None`` si no
    hay precio habitual ni precio de mercado hoy (sin datos). Un usado no llega aquí: su
    calidad es ``NO_APLICA`` (DEC-215)."""
    if not isinstance(datos, DatosCalidad):
        raise TypeError("se esperaba DatosCalidad")
    calidad = parametros.quality
    if datos.precio_habitual is None and datos.precio_mercado_hoy is None:
        return None
    entre_los_mas_baratos = datos.precio_mercado_hoy is not None and datos.precio <= (
        datos.precio_mercado_hoy * (1 + calidad.cheapest_tolerance_pct / _CIEN)
    )
    # 1. Descuento cuestionable (se evalúa primero).
    if datos.precio_antes_inflado:
        return CalidadPrecio.DESCUENTO_CUESTIONABLE
    if datos.precio_habitual is None:
        anunciado = datos.descuento_anunciado
        if anunciado is not None and anunciado > 0 and datos.otros_comercios <= _UN_COMERCIO:
            return CalidadPrecio.DESCUENTO_CUESTIONABLE  # S-28: solo sin historial
        # 2. Sin historial no pasa de Precio competitivo (RN-012 §4, S-22).
        if entre_los_mas_baratos:
            return CalidadPrecio.PRECIO_COMPETITIVO
        return CalidadPrecio.PRECIO_NORMAL
    # 3. Con precio habitual.
    if datos.precio > datos.precio_habitual:
        return CalidadPrecio.PRECIO_NORMAL  # S-22
    real = datos.descuento_real if datos.descuento_real is not None else Decimal(0)
    suficientes = datos.otros_comercios >= calidad.min_other_retailers
    if real >= calidad.good_offer_min_discount_pct and entre_los_mas_baratos and suficientes:
        excepcional = (
            datos.minimo_registrado is not None
            and datos.precio < datos.minimo_registrado
            and datos.dias_historial >= calidad.exceptional_min_history_days
        )
        return CalidadPrecio.OFERTA_EXCEPCIONAL if excepcional else CalidadPrecio.BUENA_OFERTA
    if entre_los_mas_baratos:
        return CalidadPrecio.PRECIO_COMPETITIVO
    return CalidadPrecio.PRECIO_NORMAL
