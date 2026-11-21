"""Rentabilidad por canal: márgenes, nivel, unidades, días y rendimiento (CMP-14).

Reglas (RN-001 v2 §4, RN-005 v2 §4, RN-009 v2 §4.2 y §4.3; REQ §3.2 pasos 7 y 8, §3.2.1,
§3.2.2; S-05, S-30; DEC-202, DEC-224 a). Todas las cifras salen de la configuración
(PAR-11, PAR-12, PAR-13). Los montos de la lista cerrada se redondean **una vez** con
``oip.dinero.redondear``; las fórmulas que combinan montos usan los ya redondeados
(design.md §8). Los porcentajes van en puntos y **sin redondear**.

- Margen neto = precio de venta − costo de compra − costo de venta; % sobre el costo de
  compra (RN-001).
- Devoluciones = venta × tasa × pérdida; castigo por baja = (venta − mínimo de 60 días en
  Amazon) × ``drop_weight_pct`` (0 si sale negativo) o, sin mínimo, venta ×
  ``without_minimum_pct`` (S-05, igual en los dos canales); margen ajustado = neto −
  devoluciones − castigo (RN-005).
- **Qué se calcula en cada estado** (REQ §3.2.1): cerrado, solo el margen neto; por revisar,
  márgenes y ``nivel_calculado``; disponible, márgenes y, con descuento real ≥
  ``reference_only_below_pct``, nivel, unidades, días y rendimiento.
- **Nivel** (RN-009 §4.3): el más alto cuyos dos mínimos (descuento real y margen ajustado %)
  se cumplen, con margen ajustado ≥ mayor(``min_per_unit.amount``, % del costo de compra);
  en Amazon, ``COMPETENCIA MÁS BARATA`` baja un nivel. Eso es ``nivel_calculado`` (DEC-202),
  que solo existe en canales disponibles o por revisar (DEC-224 a). El **nivel** del canal es
  ``nivel_calculado`` en un canal disponible que cumple el requisito de confianza.
- **Nivel antes que unidades** (design.md §3): el tope de primera compra depende del nivel.
- Unidades = el menor de ventas al mes, disponibles, límite por cliente y tope (sin ventas al
  mes, ``max_units_without_monthly_sales``); días para recuperar = mayor(días base, unidades ÷
  (ventas al mes ÷ 30), hacia arriba) + días de pago; rendimiento = margen ajustado % × 30 ÷
  días; ganancia total = margen ajustado × unidades (RN-005, RN-018).

Puro (design.md §14): sin reloj, sin I/O, sin red.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from decimal import Decimal

from oip.catalogos import Nivel
from oip.configuracion import (
    Castigo,
    Configuracion,
    MinimoPorUnidad,
    TopePrimeraCompra,
    UmbralNivel,
)
from oip.evaluacion.canales import CanalEvaluado
from oip.evaluacion.contexto import EvaluacionCanal

__all__ = [
    "Margenes",
    "asignar_nivel",
    "calcular_margenes",
    "calcular_unidades",
    "castigo_por_baja",
    "costo_devoluciones",
    "dias_para_recuperar",
    "ganancia_total",
    "margen_ajustado",
    "margen_neto",
    "minimo_por_unidad",
    "nivel_calculado",
    "nivel_por_umbrales",
    "porcentaje_sobre_compra",
    "rendimiento_mensual",
    "tope_primera_compra",
    "unidades_recomendadas",
]


@dataclasses.dataclass(frozen=True, slots=True)
class Margenes:
    """Márgenes de una unidad en un canal. En un canal cerrado solo hay margen neto: los
    demás quedan en ``None``."""

    margen_neto: Decimal
    margen_neto_pct: Decimal
    costo_devoluciones: Decimal | None
    castigo: Decimal | None
    margen_ajustado: Decimal | None
    margen_ajustado_pct: Decimal | None


# --- Fórmulas ------------------------------------------------------------------------------


def porcentaje_sobre_compra(monto: Decimal, costo_compra: Decimal) -> Decimal:
    """``monto ÷ costo de compra × 100``, sin redondear (RN-001, RN-005)."""
    raise NotImplementedError


def margen_neto(precio_venta: Decimal, costo_compra: Decimal, costo_venta: Decimal) -> Decimal:
    """Margen neto de una unidad (RN-001 §4), redondeado una vez."""
    raise NotImplementedError


def costo_devoluciones(precio_venta: Decimal, tasa_pct: Decimal, perdida_pct: Decimal) -> Decimal:
    """Venta × tasa × pérdida (RN-005 §4), redondeado una vez (B2: 5.215 → 5.22)."""
    raise NotImplementedError


def castigo_por_baja(
    precio_venta: Decimal, minimo_60_dias: Decimal | None, parametros: Castigo
) -> Decimal:
    """Castigo por baja (RN-005 §4 y §11; S-01, S-05), redondeado una vez."""
    raise NotImplementedError


def margen_ajustado(margen_neto: Decimal, devoluciones: Decimal, castigo: Decimal) -> Decimal:
    """Margen neto − devoluciones − castigo (RN-005 §4), con los montos ya redondeados."""
    raise NotImplementedError


def calcular_margenes(
    canal: CanalEvaluado,
    costo_compra: Decimal,
    minimo_60_dias: Decimal | None,
    parametros: Castigo,
) -> Margenes | None:
    """Márgenes del canal según su estado (REQ §3.2.1). ``None`` sin precio o costo de venta."""
    raise NotImplementedError


def minimo_por_unidad(costo_compra: Decimal, parametros: MinimoPorUnidad) -> Decimal:
    """Mayor entre ``amount`` y ``pct_of_purchase_cost`` del costo de compra (RN-009 §4.2),
    sin redondear (es un umbral, no un monto de la lista cerrada)."""
    raise NotImplementedError


def nivel_por_umbrales(
    descuento_real: Decimal,
    margen_ajustado_pct: Decimal,
    umbrales: Mapping[Nivel, UmbralNivel],
) -> Nivel | None:
    """El nivel más alto cuyos dos mínimos se cumplen (RN-009 §4.3), o ``None``."""
    raise NotImplementedError


def nivel_calculado(
    descuento_real: Decimal | None,
    margenes: Margenes | None,
    costo_compra: Decimal,
    configuracion: Configuracion,
    baja_por_competencia: bool,
) -> Nivel | None:
    """``nivel_calculado`` (DEC-202): RN-009 §4.3 con el mínimo por unidad y la baja por
    competencia, sin los demás requisitos del canal. ``None`` sin descuento real ≥
    ``reference_only_below_pct`` o sin margen ajustado."""
    raise NotImplementedError


def tope_primera_compra(
    ranking: Decimal | None, nivel: Nivel | None, parametros: TopePrimeraCompra
) -> int:
    """Tope de primera compra (RN-005 §4; REQ §5): ``boosted_units`` con ranking <
    ``boosted_below_rank`` y nivel en ``boosted_levels``; si no, ``units``."""
    raise NotImplementedError


def unidades_recomendadas(
    ventas_al_mes: int | None,
    disponibles: int | None,
    limite_cliente: int | None,
    tope: int,
    maximo_sin_ventas: int,
) -> int:
    """El menor de ventas al mes (o ``maximo_sin_ventas`` sin dato), disponibles, límite por
    cliente y tope (RN-005 §4 y §11). Un dato ``None`` no limita."""
    raise NotImplementedError


def dias_para_recuperar(
    unidades: int,
    ventas_al_mes: int | None,
    dias_tabla: int | None,
    dias_por_unidad: int | None,
    dias_pago: int,
) -> int | None:
    """Días de venta + días de pago (RN-005 §4). Días de venta = mayor(días de la tabla o días
    por unidad × unidades, unidades ÷ (ventas al mes ÷ 30) hacia arriba). ``None`` con 0
    unidades."""
    raise NotImplementedError


def rendimiento_mensual(margen_ajustado_pct: Decimal, dias: int) -> Decimal:
    """Margen ajustado % × 30 ÷ días para recuperar (RN-005 §4), sin redondear."""
    raise NotImplementedError


def ganancia_total(margen_ajustado: Decimal, unidades: int) -> Decimal:
    """Margen ajustado × unidades (RN-018 §4), redondeado una vez."""
    raise NotImplementedError


# --- Pasos del motor -----------------------------------------------------------------------


def asignar_nivel(
    canal: EvaluacionCanal,
    insumos: CanalEvaluado,
    *,
    descuento_real: Decimal | None,
    costo_compra: Decimal,
    confianza_ok: bool,
    configuracion: Configuracion,
) -> EvaluacionCanal:
    """``nivel_calculado`` y nivel del canal (RN-009; DEC-202, DEC-224 a)."""
    raise NotImplementedError


def calcular_unidades(
    canal: EvaluacionCanal,
    insumos: CanalEvaluado,
    *,
    descuento_real: Decimal | None,
    configuracion: Configuracion,
) -> EvaluacionCanal:
    """Unidades, días, rendimiento y ganancia total de un canal disponible con descuento real
    ≥ ``reference_only_below_pct`` (RN-005; REQ §3.2.1). Sin dato de ventas al mes agrega
    ``ESTIMADO (unidades)``."""
    raise NotImplementedError
