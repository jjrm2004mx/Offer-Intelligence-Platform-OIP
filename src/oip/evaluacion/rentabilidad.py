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

from oip.catalogos import EstadoCanal, Nivel, marca_estimado, nivel_inferior
from oip.configuracion import (
    Castigo,
    Configuracion,
    MinimoPorUnidad,
    TopePrimeraCompra,
    UmbralNivel,
)
from oip.dinero import TipoMonto, redondear
from oip.evaluacion._tipos import exigir_decimal, exigir_entero, verificar_dataclass
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

    def __post_init__(self) -> None:
        verificar_dataclass(self)


_CIEN = Decimal(100)
_TREINTA = 30  # RN-005 §4: "÷ 30" y "× 30"


def _exigir_canal(canal: object, insumos: object) -> None:
    if not isinstance(canal, EvaluacionCanal) or not isinstance(insumos, CanalEvaluado):
        raise TypeError("se esperaban el EvaluacionCanal y su CanalEvaluado")
    if canal.canal is not insumos.canal or canal.estado is not insumos.estado:
        raise ValueError("el EvaluacionCanal y su CanalEvaluado no son del mismo canal")


def _margenes_de(canal: EvaluacionCanal) -> Margenes | None:
    if canal.margen_neto is None or canal.margen_neto_pct is None:
        return None
    return Margenes(
        margen_neto=canal.margen_neto,
        margen_neto_pct=canal.margen_neto_pct,
        costo_devoluciones=canal.costo_devoluciones,
        castigo=canal.castigo,
        margen_ajustado=canal.margen_ajustado,
        margen_ajustado_pct=canal.margen_ajustado_pct,
    )


# --- Fórmulas ------------------------------------------------------------------------------


def porcentaje_sobre_compra(monto: Decimal, costo_compra: Decimal) -> Decimal:
    """``monto ÷ costo de compra × 100``, sin redondear (RN-001, RN-005)."""
    monto = exigir_decimal(monto, "el monto")
    costo = exigir_decimal(costo_compra, "el costo de compra")
    if costo <= 0:
        raise ValueError("el costo de compra debe ser mayor que cero")
    return monto / costo * _CIEN


def margen_neto(precio_venta: Decimal, costo_compra: Decimal, costo_venta: Decimal) -> Decimal:
    """Margen neto de una unidad (RN-001 §4), redondeado una vez."""
    venta = exigir_decimal(precio_venta, "el precio de venta")
    compra = exigir_decimal(costo_compra, "el costo de compra")
    costo = exigir_decimal(costo_venta, "el costo de venta")
    return redondear(TipoMonto.MARGEN_NETO, venta - compra - costo)


def costo_devoluciones(precio_venta: Decimal, tasa_pct: Decimal, perdida_pct: Decimal) -> Decimal:
    """Venta × tasa × pérdida (RN-005 §4), redondeado una vez (B2: 5.215 → 5.22)."""
    venta = exigir_decimal(precio_venta, "el precio de venta")
    tasa = exigir_decimal(tasa_pct, "la tasa de devolución")
    perdida = exigir_decimal(perdida_pct, "la pérdida por devolución")
    return redondear(TipoMonto.DEVOLUCIONES, venta * tasa / _CIEN * perdida / _CIEN)


def castigo_por_baja(
    precio_venta: Decimal, minimo_60_dias: Decimal | None, parametros: Castigo
) -> Decimal:
    """Castigo por baja (RN-005 §4 y §11; S-01, S-05), redondeado una vez."""
    venta = exigir_decimal(precio_venta, "el precio de venta")
    if not isinstance(parametros, Castigo):
        raise TypeError("se esperaban los parámetros del castigo (amazon.drop_penalty)")
    if minimo_60_dias is None:
        # RN-005 §11; S-05: sin mínimo, un porcentaje del precio de venta del canal.
        return redondear(TipoMonto.CASTIGO, venta * parametros.without_minimum_pct / _CIEN)
    minimo = exigir_decimal(minimo_60_dias, "el mínimo de 60 días")
    baja = max(venta - minimo, Decimal(0))  # "si sale negativo, 0"
    return redondear(TipoMonto.CASTIGO, baja * parametros.drop_weight_pct / _CIEN)


def margen_ajustado(margen_neto: Decimal, devoluciones: Decimal, castigo: Decimal) -> Decimal:
    """Margen neto − devoluciones − castigo (RN-005 §4), con los montos ya redondeados."""
    neto = exigir_decimal(margen_neto, "el margen neto")
    devoluciones = exigir_decimal(devoluciones, "el costo por devoluciones")
    castigo = exigir_decimal(castigo, "el castigo por baja")
    return redondear(TipoMonto.MARGEN_AJUSTADO, neto - devoluciones - castigo)


def calcular_margenes(
    canal: CanalEvaluado,
    costo_compra: Decimal,
    minimo_60_dias: Decimal | None,
    parametros: Castigo,
) -> Margenes | None:
    """Márgenes del canal según su estado (REQ §3.2.1). ``None`` sin precio o costo de venta."""
    if not isinstance(canal, CanalEvaluado):
        raise TypeError("se esperaba un CanalEvaluado")
    if canal.precio_venta is None or canal.costo_venta is None:
        return None  # RN-001 §11: sin precio de venta no hay margen de ese canal
    neto = margen_neto(canal.precio_venta, costo_compra, canal.costo_venta)
    neto_pct = porcentaje_sobre_compra(neto, costo_compra)
    if canal.estado is EstadoCanal.CERRADO:
        # REQ §3.2.1: en un canal cerrado, solo el margen neto (informativo).
        return Margenes(neto, neto_pct, None, None, None, None)
    if canal.tasa_devolucion_pct is None or canal.perdida_devolucion_pct is None:
        raise ValueError("un canal abierto necesita su tasa y su pérdida por devolución")
    devoluciones = costo_devoluciones(
        canal.precio_venta, canal.tasa_devolucion_pct, canal.perdida_devolucion_pct
    )
    castigo = castigo_por_baja(canal.precio_venta, minimo_60_dias, parametros)
    ajustado = margen_ajustado(neto, devoluciones, castigo)
    return Margenes(
        margen_neto=neto,
        margen_neto_pct=neto_pct,
        costo_devoluciones=devoluciones,
        castigo=castigo,
        margen_ajustado=ajustado,
        margen_ajustado_pct=porcentaje_sobre_compra(ajustado, costo_compra),
    )


def minimo_por_unidad(costo_compra: Decimal, parametros: MinimoPorUnidad) -> Decimal:
    """Mayor entre ``amount`` y ``pct_of_purchase_cost`` del costo de compra (RN-009 §4.2),
    sin redondear (es un umbral, no un monto de la lista cerrada)."""
    costo = exigir_decimal(costo_compra, "el costo de compra")
    if not isinstance(parametros, MinimoPorUnidad):
        raise TypeError("se esperaban los parámetros del mínimo por unidad (levels.min_per_unit)")
    return max(parametros.amount, costo * parametros.pct_of_purchase_cost / _CIEN)


def nivel_por_umbrales(
    descuento_real: Decimal,
    margen_ajustado_pct: Decimal,
    umbrales: Mapping[Nivel, UmbralNivel],
) -> Nivel | None:
    """El nivel más alto cuyos dos mínimos se cumplen (RN-009 §4.3), o ``None``."""
    real = exigir_decimal(descuento_real, "el descuento real")
    ajustado = exigir_decimal(margen_ajustado_pct, "el margen ajustado %")
    for nivel in Nivel:  # de mayor a menor
        umbral = umbrales[nivel]
        if real >= umbral.min_real_discount_pct and ajustado >= umbral.min_adjusted_margin_pct:
            return nivel
    return None


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
    if margenes is not None and not isinstance(margenes, Margenes):
        raise TypeError("se esperaban Margenes o None")
    if not isinstance(configuracion, Configuracion):
        raise TypeError("se esperaba la Configuracion")
    if type(baja_por_competencia) is not bool:
        raise TypeError("baja_por_competencia debe ser bool")
    if descuento_real is None or margenes is None:
        return None
    real = exigir_decimal(descuento_real, "el descuento real")
    if real < configuracion.discount_quality.reference_only_below_pct:
        return None  # REQ §3.2: el nivel exige descuento real ≥ 25%
    ajustado, ajustado_pct = margenes.margen_ajustado, margenes.margen_ajustado_pct
    if ajustado is None or ajustado_pct is None:
        return None
    niveles = configuracion.levels
    nivel = nivel_por_umbrales(real, ajustado_pct, niveles.thresholds)
    if nivel is None or ajustado < minimo_por_unidad(costo_compra, niveles.min_per_unit):
        return None
    if baja_por_competencia:
        return nivel_inferior(nivel)  # RN-002 §4.3, RN-009 §4.3: Vigilar baja a sin nivel
    return nivel


def tope_primera_compra(
    ranking: Decimal | None, nivel: Nivel | None, parametros: TopePrimeraCompra
) -> int:
    """Tope de primera compra (RN-005 §4; REQ §5): ``boosted_units`` con ranking <
    ``boosted_below_rank`` y nivel en ``boosted_levels``; si no, ``units``."""
    if not isinstance(parametros, TopePrimeraCompra):
        raise TypeError("se esperaban los parámetros del tope (amazon.first_purchase_cap)")
    if nivel is not None and not isinstance(nivel, Nivel):
        raise TypeError("se esperaba un Nivel o None")
    if ranking is not None:
        rank = exigir_decimal(ranking, "el ranking")
        if rank < parametros.boosted_below_rank and nivel in parametros.boosted_levels:
            return parametros.boosted_units
    return parametros.units


def unidades_recomendadas(
    ventas_al_mes: int | None,
    disponibles: int | None,
    limite_cliente: int | None,
    tope: int,
    maximo_sin_ventas: int,
) -> int:
    """El menor de ventas al mes (o ``maximo_sin_ventas`` sin dato), disponibles, límite por
    cliente y tope (RN-005 §4 y §11). Un dato ``None`` no limita."""
    tope = exigir_entero(tope, "el tope", minimo=1)
    maximo = exigir_entero(maximo_sin_ventas, "el máximo sin ventas al mes", minimo=1)
    limites = [tope, maximo if ventas_al_mes is None else ventas_al_mes]
    for nombre, valor in (
        ("ventas_al_mes", ventas_al_mes),
        ("disponibles", disponibles),
        ("limite_cliente", limite_cliente),
    ):
        if valor is not None:
            exigir_entero(valor, nombre)
    limites.extend(v for v in (disponibles, limite_cliente) if v is not None)
    return min(limites)


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
    unidades = exigir_entero(unidades, "las unidades")
    pago = exigir_entero(dias_pago, "los días de pago")
    if unidades == 0:
        return None
    candidatos: list[int] = []
    if dias_tabla is not None:
        candidatos.append(exigir_entero(dias_tabla, "los días de la tabla", minimo=1))
    elif dias_por_unidad is not None:
        candidatos.append(
            exigir_entero(dias_por_unidad, "los días por unidad", minimo=1) * unidades
        )
    if ventas_al_mes is not None and exigir_entero(ventas_al_mes, "las ventas al mes") > 0:
        # unidades ÷ (ventas al mes ÷ 30), hasta vender la última unidad: hacia arriba.
        candidatos.append(-(-unidades * _TREINTA // ventas_al_mes))
    if not candidatos:
        raise ValueError("faltan los días de la tabla, los días por unidad o las ventas al mes")
    return max(candidatos) + pago


def rendimiento_mensual(margen_ajustado_pct: Decimal, dias: int) -> Decimal:
    """Margen ajustado % × 30 ÷ días para recuperar (RN-005 §4), sin redondear."""
    pct = exigir_decimal(margen_ajustado_pct, "el margen ajustado %")
    dias = exigir_entero(dias, "los días para recuperar", minimo=1)
    return pct * _TREINTA / dias


def ganancia_total(margen_ajustado: Decimal, unidades: int) -> Decimal:
    """Margen ajustado × unidades (RN-018 §4), redondeado una vez."""
    ajustado = exigir_decimal(margen_ajustado, "el margen ajustado")
    unidades = exigir_entero(unidades, "las unidades")
    return redondear(TipoMonto.GANANCIA_TOTAL, ajustado * unidades)


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
    _exigir_canal(canal, insumos)
    if canal.estado is EstadoCanal.CERRADO:
        return canal  # DEC-224 a: un canal cerrado no tiene nivel_calculado
    if type(confianza_ok) is not bool:
        raise TypeError("confianza_ok debe ser bool")
    margenes = _margenes_de(canal)
    calculado = nivel_calculado(
        descuento_real, margenes, costo_compra, configuracion, insumos.baja_por_competencia
    )
    # RN-009 §4.2: el nivel cuenta en un canal disponible con el requisito de confianza
    # (tienda física: Alta o Media; S-25). Por revisar: solo nivel_calculado (S-30).
    con_nivel = canal.estado is EstadoCanal.DISPONIBLE and confianza_ok
    return dataclasses.replace(
        canal, nivel_calculado=calculado, nivel=calculado if con_nivel else None
    )


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
    _exigir_canal(canal, insumos)
    if not isinstance(configuracion, Configuracion):
        raise TypeError("se esperaba la Configuracion")
    if canal.estado is not EstadoCanal.DISPONIBLE or canal.margen_ajustado is None:
        return canal  # REQ §3.2.1: solo en canales disponibles
    if canal.margen_ajustado_pct is None or descuento_real is None:
        return canal
    real = exigir_decimal(descuento_real, "el descuento real")
    if real < configuracion.discount_quality.reference_only_below_pct:
        return canal  # REQ §3.2: unidades, días y rendimiento con descuento real ≥ 25%
    amazon = configuracion.amazon
    tope = tope_primera_compra(insumos.ranking, canal.nivel, amazon.first_purchase_cap)
    unidades = unidades_recomendadas(
        insumos.ventas_al_mes,
        insumos.disponibles,
        insumos.limite_cliente,
        tope,
        amazon.max_units_without_monthly_sales,
    )
    dias = dias_para_recuperar(
        unidades,
        insumos.ventas_al_mes,
        insumos.dias_tabla,
        insumos.dias_por_unidad,
        insumos.dias_pago,
    )
    marcas = canal.marcas
    if insumos.ventas_al_mes is None:
        # RN-005 §11: sin ventas al mes, máximo de unidades y la marca de estimado.
        marcas = tuple(dict.fromkeys((*marcas, marca_estimado("unidades"))))
    return dataclasses.replace(
        canal,
        unidades=unidades,
        dias_para_recuperar=dias,
        rendimiento_mensual_pct=None
        if dias is None
        else rendimiento_mensual(canal.margen_ajustado_pct, dias),
        ganancia_total=ganancia_total(canal.margen_ajustado, unidades),
        marcas=marcas,
    )
