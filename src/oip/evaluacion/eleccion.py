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

from oip.catalogos import Canal, Nivel
from oip.evaluacion.contexto import EvaluacionCanal

__all__ = ["Eleccion", "canal_elegido", "elegir", "nivel_del_aviso"]


@dataclasses.dataclass(frozen=True, slots=True)
class Eleccion:
    """Canal elegido y nivel del aviso con su canal; todo ``None`` sin canales con nivel."""

    canal_elegido: Canal | None
    nivel_aviso: Nivel | None
    canal_aviso: Canal | None


def canal_elegido(canales: Sequence[EvaluacionCanal], desempate_pct: Decimal) -> Canal | None:
    """Canal elegido por RN-018 §4 entre los canales con nivel."""
    raise NotImplementedError


def nivel_del_aviso(
    canales: Sequence[EvaluacionCanal], elegido: Canal | None
) -> tuple[Nivel | None, Canal | None]:
    """Nivel del aviso y su canal (S-33)."""
    raise NotImplementedError


def elegir(canales: Sequence[EvaluacionCanal], desempate_pct: Decimal) -> Eleccion:
    """Canal elegido y nivel del aviso (paso 9)."""
    raise NotImplementedError
