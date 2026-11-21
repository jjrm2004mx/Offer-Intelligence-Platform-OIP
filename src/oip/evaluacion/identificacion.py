"""Paso 2 de REQ §3.2: identificar y clasificar riesgo (CMP-10).

T11 llena la **confianza de la disponibilidad** (RN-007 v2 §4.1 y §4.2; S-25). La
coincidencia (RN-013), el estado (RN-014, S-13), el vendedor y los riesgos (RN-015, S-21) y la
lista "evitar siempre" los agregan sus tareas (T19, T20).

Reglas de la confianza (todas sus cifras salen de PAR-13, ``levels.confidence``; ninguna está
en el código):

- **Antigüedad** del dato = ``instante − extractedAt`` (design.md §3), en horas exactas, sin
  ``float``.
- **Tienda física** (``purchaseMode = tienda``), con las ventanas de liquidación si
  ``isClearance`` es verdadero y las normales si es falso o no se sabe (RN-007 §11):

  - cantidad exacta (``availability.quantity``): **Alta** hasta ``exact_high_max_hours``,
    **Media** hasta ``max_age_hours``, después **Baja**;
  - "en existencia" sin número: **Media** hasta ``no_number_medium_max_hours``, después
    **Baja**;
  - "pocas unidades" o "existencia limitada" (``limited_stock``): **Media** hasta
    ``few_units_medium_max_hours``, después **Baja**;
  - agotado o no confirmada: **Baja**.

- **En línea y recoger en tienda** (RN-007 §4.2; S-25): "disponible confirmada"
  (``in_stock_confirmed``) cuenta como **Alta**. RN-007 no da confianza a los demás estados en
  línea (solo dice que no cuentan como disponibles): quedan **sin confianza** (``None``).
- **Particular:** la publicación no tiene disponibilidad que calificar: sin confianza.
- El ajuste por el historial de visitas de la tienda (RN-007 §4.1) no se aplica: el contexto
  no trae visitas (las usa la parte C).

**Requisito del nivel** (RN-009 §4.2; REQ §3.2.1): en tienda física, el nivel de un canal
exige confianza Alta o Media al evaluar; en las demás compras la confianza no es requisito.

Puro (design.md §14): sin reloj, sin I/O, sin red.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from oip.catalogos import Confianza
from oip.configuracion import Confianza as ParametrosConfianza
from oip.entradas.contrato import Observacion

__all__ = [
    "antiguedad_horas",
    "confianza_disponibilidad",
    "confianza_permite_nivel",
    "es_tienda_fisica",
]


def antiguedad_horas(instante: dt.datetime, extraida_en: dt.datetime) -> Decimal:
    """Horas exactas de ``extraida_en`` a ``instante`` (``Decimal``, sin ``float``). Las dos
    fechas necesitan su desfase; un dato posterior al instante levanta ``ValueError``."""
    raise NotImplementedError


def es_tienda_fisica(observacion: Observacion) -> bool:
    """Compra en tienda física (``purchaseMode = tienda``; RN-007 §4.1)."""
    raise NotImplementedError


def confianza_disponibilidad(
    observacion: Observacion, instante: dt.datetime, parametros: ParametrosConfianza
) -> Confianza | None:
    """Confianza de la disponibilidad de la oferta al ``instante`` (RN-007 v2; S-25).

    ``None`` cuando la RN no da confianza: la publicación de un particular o un estado en
    línea distinto de "disponible confirmada"."""
    raise NotImplementedError


def confianza_permite_nivel(observacion: Observacion, confianza: Confianza | None) -> bool:
    """Requisito de confianza del nivel (RN-009 §4.2; REQ §3.2.1; S-25): en tienda física,
    Alta o Media; en las demás compras, siempre se cumple."""
    raise NotImplementedError
