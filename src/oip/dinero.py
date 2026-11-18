"""Dinero de OIP: el único módulo que redondea (CMP-02).

Reglas (DEC-060, precisada por DEC-207 y DEC-222; REQ-2026-0001 §5 y §10):

- Los montos son ``Decimal`` y se leen desde texto; un ``float`` levanta ``TypeError``.
- Solo se redondean los montos de la **lista cerrada** del REQ §5 (``TipoMonto``), a
  centavos y con ``ROUND_HALF_UP`` (en negativos el medio centavo se aleja de cero).
- Cada fórmula se calcula completa, sin redondeos intermedios, y se redondea **una sola
  vez, al final**, con ``redondear``. Ningún otro módulo llama a ``quantize``.
- El precio habitual, las medianas, los precios convertidos de MXN y los porcentajes no
  se redondean (DEC-226 b). Los porcentajes solo se formatean a 1 decimal para mostrarlos.
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import StrEnum

__all__ = ["TipoMonto", "formatear_porcentaje", "leer_monto", "redondear"]

_CENTAVO = Decimal("0.01")
_DECIMA = Decimal("0.1")


class TipoMonto(StrEnum):
    """Lista cerrada de montos que se redondean (REQ §5, DEC-207; design.md §8).

    Los costos de traslado del REQ (entrega, recogida y viaje) van como tres tipos,
    uno por fórmula.
    """

    IMPUESTO = "impuesto"
    COSTO_COMPRA = "costo_compra"
    COMISION = "comision"
    ENVIO = "envio"
    DEVOLUCIONES = "devoluciones"
    CASTIGO = "castigo"
    PRECIO_VENTA_LOCAL = "precio_venta_local"
    VALOR_REFERENCIA_USADOS = "valor_referencia_usados"
    TRASLADO_ENTREGA = "traslado_entrega"
    TRASLADO_RECOGIDA = "traslado_recogida"
    TRASLADO_VIAJE = "traslado_viaje"
    MARGEN_NETO = "margen_neto"
    MARGEN_AJUSTADO = "margen_ajustado"
    GANANCIA_TOTAL = "ganancia_total"


def _exigir_decimal_finito(valor: object, nombre: str) -> Decimal:
    if isinstance(valor, float):
        raise TypeError(f"{nombre} no puede ser float; use Decimal leído desde texto")
    if not isinstance(valor, Decimal):
        raise TypeError(f"{nombre} debe ser Decimal, no {type(valor).__name__}")
    if not valor.is_finite():
        raise ValueError(f"{nombre} debe ser un número finito")
    return valor


def leer_monto(texto: str | Decimal) -> Decimal:
    """Lee un monto desde texto decimal (``"29.00"``) sin pasar por ``float`` ni redondear.

    Un ``Decimal`` se devuelve igual. Un ``float`` levanta ``TypeError``; un texto que no es
    un número finito levanta ``ValueError``.
    """
    if isinstance(texto, Decimal):
        return _exigir_decimal_finito(texto, "el monto")
    if isinstance(texto, float):
        raise TypeError("el monto no puede ser float; páselo como texto decimal")
    if not isinstance(texto, str):
        raise TypeError(f"el monto debe ser texto o Decimal, no {type(texto).__name__}")
    try:
        valor = Decimal(texto.strip())
    except InvalidOperation:
        raise ValueError("el monto no es un número decimal válido") from None
    return _exigir_decimal_finito(valor, "el monto")


def redondear(tipo: TipoMonto, valor: Decimal) -> Decimal:
    """Redondea a centavos con ``ROUND_HALF_UP`` un monto de la lista cerrada.

    Se llama **una vez**, al final de la fórmula completa del monto (DEC-207, DEC-222;
    B33: 100.15 × 85% × 90% = 76.614750 → 76.61).
    """
    if not isinstance(tipo, TipoMonto):
        raise TypeError("solo se redondean los montos de la lista cerrada (TipoMonto)")
    valor = _exigir_decimal_finito(valor, "el monto")
    return valor.quantize(_CENTAVO, rounding=ROUND_HALF_UP)


def formatear_porcentaje(porcentaje: Decimal) -> str:
    """Texto del porcentaje con 1 decimal, solo para mostrar (``Decimal("75.63")`` → ``"75.6 %"``).

    El porcentaje va en puntos (25 = 25%). No cambia el valor: para calcular y comparar se
    usa el ``Decimal`` sin redondear. Formato de la guía de estilo §11.
    """
    porcentaje = _exigir_decimal_finito(porcentaje, "el porcentaje")
    mostrado = porcentaje.quantize(_DECIMA, rounding=ROUND_HALF_UP)
    if mostrado.is_zero():
        mostrado = abs(mostrado)  # sin "-0.0"
    return f"{mostrado} %"
