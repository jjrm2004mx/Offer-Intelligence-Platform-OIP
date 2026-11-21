"""Paso 9 de REQ §3.2: canal elegido y nivel del aviso (CMP-15; RN-018 v1, S-33).

- **Canales con nivel** = disponibles con nivel (REQ §3.2.4: un canal por revisar solo tiene
  ``nivel_calculado``, informativo, y no entra en la elección; S-30).
- **Canal elegido** (RN-018 §4; DEC-170): sin canales con nivel, ninguno; con uno, ese; con
  dos, el de mayor ganancia total; si la diferencia, medida contra la ganancia mayor, es menor
  que ``channel_tiebreak_pct`` (PAR-13), el de mayor rendimiento mensual. Con el mismo
  rendimiento, el de mayor ganancia total y, si también empatan, el primero en el orden del
  catálogo (Amazon, local), para que el resultado sea determinista.
- **Nivel del aviso** (S-33; DEC-219, DEC-221; design.md §10.6): el nivel más alto entre los
  canales con nivel, aunque el elegido sea otro; con empate, el del canal elegido. El canal
  del aviso es el de ese nivel.

Puro (design.md §14).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from decimal import Decimal

from oip.catalogos import Canal, EstadoCanal, Nivel
from oip.evaluacion._tipos import exigir_decimal, verificar_dataclass
from oip.evaluacion.contexto import EvaluacionCanal

__all__ = ["Eleccion", "canal_elegido", "elegir", "nivel_del_aviso"]


@dataclasses.dataclass(frozen=True, slots=True)
class Eleccion:
    """Canal elegido y nivel del aviso con su canal; todo ``None`` sin canales con nivel."""

    canal_elegido: Canal | None
    nivel_aviso: Nivel | None
    canal_aviso: Canal | None

    def __post_init__(self) -> None:
        verificar_dataclass(self)
        if (self.nivel_aviso is None) != (self.canal_aviso is None):
            raise ValueError("nivel_aviso y canal_aviso van juntos")
        if (self.canal_elegido is None) != (self.nivel_aviso is None):
            raise ValueError("hay nivel del aviso si y solo si hay canal elegido")


_CIEN = Decimal(100)


def _con_nivel(canales: Sequence[EvaluacionCanal]) -> list[EvaluacionCanal]:
    """Canales disponibles con nivel (REQ §3.2.4; S-30), en el orden del catálogo."""
    if isinstance(canales, str | bytes) or not all(isinstance(c, EvaluacionCanal) for c in canales):
        raise TypeError("se esperaba una secuencia de EvaluacionCanal")
    vistos = [c.canal for c in canales]
    if len(set(vistos)) != len(vistos):
        raise ValueError("un EvaluacionCanal por canal")
    return [c for c in canales if c.estado is EstadoCanal.DISPONIBLE and c.nivel is not None]


def canal_elegido(canales: Sequence[EvaluacionCanal], desempate_pct: Decimal) -> Canal | None:
    """Canal elegido por RN-018 §4 entre los canales con nivel."""
    desempate = exigir_decimal(desempate_pct, "el desempate de canal")
    candidatos = _con_nivel(canales)
    if not candidatos:
        return None  # RN-018 §4.1: sin canales con nivel, la oferta queda sin nivel
    if len(candidatos) == 1:
        return candidatos[0].canal
    orden = list(Canal)

    def _ganancia(c: EvaluacionCanal) -> Decimal:
        if c.ganancia_total is None:
            raise ValueError("un canal con nivel necesita su ganancia total")
        return c.ganancia_total

    def _rendimiento(c: EvaluacionCanal) -> Decimal:
        if c.rendimiento_mensual_pct is None:
            raise ValueError("un canal con nivel necesita su rendimiento mensual")
        return c.rendimiento_mensual_pct

    # Mayor ganancia total; con la misma, el primero del catálogo (determinista).
    por_ganancia = sorted(candidatos, key=lambda c: (-_ganancia(c), orden.index(c.canal)))
    mayor, otro = por_ganancia[0], por_ganancia[1]
    ganancia_mayor = _ganancia(mayor)
    if ganancia_mayor > 0:
        diferencia = (ganancia_mayor - _ganancia(otro)) / ganancia_mayor * _CIEN
    else:
        diferencia = Decimal(0)
    if diferencia >= desempate:
        return mayor.canal
    # DEC-170: diferencia < desempate → el de mayor rendimiento mensual.
    por_rendimiento = sorted(
        por_ganancia[:2],
        key=lambda c: (-_rendimiento(c), -_ganancia(c), orden.index(c.canal)),
    )
    return por_rendimiento[0].canal


def nivel_del_aviso(
    canales: Sequence[EvaluacionCanal], elegido: Canal | None
) -> tuple[Nivel | None, Canal | None]:
    """Nivel del aviso y su canal (S-33)."""
    if elegido is not None and not isinstance(elegido, Canal):
        raise TypeError("se esperaba un Canal o None")
    candidatos = _con_nivel(canales)
    if not candidatos:
        return None, None
    orden = list(Nivel)  # de mayor a menor
    mejor = min(orden.index(c.nivel) for c in candidatos if c.nivel is not None)
    con_mejor = [c for c in candidatos if c.nivel is orden[mejor]]
    # Empate de nivel: el del canal elegido (design.md §10.6); si no está, el primero.
    canal = next((c for c in con_mejor if c.canal is elegido), con_mejor[0])
    return orden[mejor], canal.canal


def elegir(canales: Sequence[EvaluacionCanal], desempate_pct: Decimal) -> Eleccion:
    """Canal elegido y nivel del aviso (paso 9)."""
    elegido = canal_elegido(canales, desempate_pct)
    nivel, canal = nivel_del_aviso(canales, elegido)
    return Eleccion(canal_elegido=elegido, nivel_aviso=nivel, canal_aviso=canal)
