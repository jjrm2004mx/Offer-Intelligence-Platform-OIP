"""Pasos 6 a 8 de REQ §3.2: costo de compra, estado de cada canal y sus números base (CMP-13).

Reglas (RN-001 v2, RN-004 v2, RN-006 v2, RN-008 v2, RN-016 v1, RN-017 v1; REQ §3.2.1; S-06,
S-08, S-09, S-12, S-24, S-27, S-31; DEC-197, DEC-206, DEC-217, DEC-220, DEC-225). Todas las
cifras salen de la configuración versionada (PAR-04, PAR-05, PAR-06, PAR-07, PAR-09, PAR-11,
PAR-12, PAR-13); ninguna está en el código. Cada monto de la lista cerrada se redondea **una
vez**, al final de su fórmula, con ``oip.dinero.redondear``; los montos combinados usan los ya
redondeados (design.md §8).

- **Costo de compra** (RN-001 §4, REQ §3.2 paso 6) = precio + impuesto + envío hacia mí. El
  impuesto usa la tasa de ``taxLocation`` (PAR-07) o la de respaldo (DEC-220); la compra a un
  particular no lleva impuesto (S-14). La recogida con particulares la agrega T20.
- **Estado del canal** (REQ §3.2.1): con una causa de cerrado queda **cerrado**, aunque tenga
  también una de por revisar (S-31); con solo causas de por revisar, **por revisar**; si no,
  **disponible**.
- **Amazon** (RN-004, RN-006; DEC-206): ranking = promedio de la última ``rankMain`` de cada
  día de los ``rank_window_days`` días que terminan el día evaluado (con 1 a 6 días, el de los
  disponibles; con 0, demanda desconocida); el mismo valor sirve para el umbral, los días de
  venta y el tope. Demanda SUFICIENTE con ranking ≤ tamaño de la categoría ×
  ``category_rank_pct`` (y en relojes y joyería, además, ``rankSub`` ≤
  ``subcategory_max_rank``) y vendedores ≤ ``max_new_sellers``; sin ranking, sin vendedores o
  sin tamaño de categoría, DESCONOCIDA (por revisar, DEC-225). Comisión de la categoría
  (``flat``, ``total_threshold`` o ``tiers``, DEC-217) con su mínimo por unidad; envío y
  empaque por peso (S-06); restricción por categoría, marca, producto o temporada de juguetes
  (S-09, S-10); ``MATERIAL PELIGROSO`` solo marca (S-07).
- **Venta local** (RN-016, RN-017, RN-008): precio estimado = el de Jesús o
  ``market_today_pct`` del precio de mercado hoy; techo = el menor precio pedido de los
  comparables del mismo estado en la zona de venta local; precio de venta local = mínimo de los
  dos × (1 − ``negotiation_pct``), redondeado una vez (B33). Demanda local = la captura más
  reciente de la categoría o la inicial de PAR-04, un nivel menos con más de
  ``competition_threshold`` comparables activos; baja cierra el canal. Entrega por defecto
  (S-24) = km × costo por km + horas × valor de la hora + costos fijos.

En todo cálculo de Amazon se marcan ``MARGEN ESTIMADO`` y ``EMPAQUE POR CONFIRMAR`` (RN-001
§11; RNF-9). Las causas de canal cerrado se registran también como marcas (REQ §3.2.3).

Puro (design.md §14): sin reloj, sin I/O, sin red.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from decimal import Decimal

from oip.catalogos import (
    Canal,
    Categoria,
    CausaCanalCerrado,
    CausaCanalPorRevisar,
    DemandaAmazon,
    DemandaLocal,
    EstadoCanal,
)
from oip.configuracion import (
    Comision,
    Configuracion,
    DemandaLocalConfig,
    Envio,
    Impuestos,
    Listas,
    Traslados,
)
from oip.entradas.contrato import FichaAmazon, Observacion
from oip.evaluacion.contexto import ContextoEvaluacion, Referencias

__all__ = [
    "CanalEvaluado",
    "CostoCompra",
    "DemandaEnAmazon",
    "EnvioAmazon",
    "PrecioLocal",
    "Ranking",
    "TasaDevolucion",
    "comision_amazon",
    "competencia_mas_barata",
    "costo_compra",
    "costo_entrega",
    "demanda_en_amazon",
    "demanda_local",
    "dias_por_unidad_local",
    "envio_amazon",
    "estado_del_canal",
    "evaluar_amazon",
    "evaluar_local",
    "ficha_vigente",
    "material_peligroso",
    "precio_venta_local",
    "ranking_amazon",
    "restringido_en_amazon",
    "tasa_devolucion_amazon",
    "tasa_impuesto",
    "ventas_al_mes_amazon",
    "ventas_al_mes_local",
]


# --- Tipos ---------------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class CostoCompra:
    """Costo de compra de la oferta (RN-001 §4). Montos redondeados una vez cada uno;
    ``total`` = precio + impuesto + envío hacia mí, ya redondeados. ``tasa_impuesto_pct`` en
    puntos, sin redondear."""

    precio: Decimal
    tasa_impuesto_pct: Decimal
    impuesto: Decimal
    envio_hacia_mi: Decimal
    total: Decimal


@dataclasses.dataclass(frozen=True, slots=True)
class Ranking:
    """Ranking de Amazon (DEC-206; design.md §10.3), sin redondear. ``promedio`` es ``None``
    con 0 días de datos; ``promedio_hace_30_dias``, el de los días que terminan
    ``trend_lookback_days`` antes (``None`` sin datos)."""

    promedio: Decimal | None
    dias_con_datos: int
    promedio_hace_30_dias: Decimal | None


@dataclasses.dataclass(frozen=True, slots=True)
class DemandaEnAmazon:
    """Demanda en Amazon (RN-004 §4) y su advertencia ``DEMANDA A LA BAJA``.
    ``empeoramiento_pct`` (puntos, sin redondear) solo existe con los dos promedios."""

    demanda: DemandaAmazon
    a_la_baja: bool
    empeoramiento_pct: Decimal | None


@dataclasses.dataclass(frozen=True, slots=True)
class EnvioAmazon:
    """Envío FBM y empaque de una unidad (RN-006 §4.2; S-06). ``peso_estimado`` = sin peso,
    con el envío y el empaque de ``unknown_weight`` y la marca ``ESTIMADO (peso)``."""

    envio: Decimal
    empaque: Decimal
    peso_estimado: bool


@dataclasses.dataclass(frozen=True, slots=True)
class TasaDevolucion:
    """Tasa de devolución en Amazon y pérdida por devolución (RN-005; S-27), en puntos.
    ``estimada`` = tasa asignada de otra categoría (marca ``ESTIMADO (devolución)``)."""

    tasa_pct: Decimal
    perdida_pct: Decimal
    estimada: bool


@dataclasses.dataclass(frozen=True, slots=True)
class PrecioLocal:
    """Precio de venta local (RN-016 §4), redondeado una vez. ``techo`` es el menor precio
    pedido de los comparables (``None`` sin comparables: marca ``SIN COMPARABLES LOCALES``)."""

    precio: Decimal
    techo: Decimal | None


@dataclasses.dataclass(frozen=True, slots=True)
class CanalEvaluado:
    """Estado de un canal, sus números base y lo que necesita la rentabilidad (CMP-14).

    - ``precio_venta`` y ``costo_venta``: ``None`` si no se pueden calcular (sin precio de venta,
      comisión desconocida, envío por cotizar…); el margen neto solo existe con los dos.
    - ``tasa_devolucion_pct`` y ``perdida_devolucion_pct``: los de RN-005 del canal (en venta
      local, la tasa de PAR-12 y pérdida 100%).
    - ``ventas_al_mes``: ventas al mes que le tocan a Jesús, redondeadas hacia abajo (RN-005,
      RN-017); ``None`` sin dato (Amazon sin comprados el mes pasado).
    - ``dias_tabla`` (Amazon, por ranking) y ``dias_por_unidad`` (local, RN-017): base de los
      días de venta; ``dias_pago``: días de pago del canal.
    - ``disponibles`` (cantidad de la oferta) y ``limite_cliente`` (PAR-03): ``None`` si no
      se saben.
    - ``ranking``: el de DEC-206 (el mismo para los dos canales: decide el tope).
    - ``baja_por_competencia``: ``COMPETENCIA MÁS BARATA`` baja un nivel (solo Amazon).
    - ``marcas``: las del canal, en orden y sin repetidos.
    """

    canal: Canal
    estado: EstadoCanal
    causas_cerrado: tuple[CausaCanalCerrado, ...]
    causas_por_revisar: tuple[CausaCanalPorRevisar, ...]
    precio_venta: Decimal | None
    costo_venta: Decimal | None
    tasa_devolucion_pct: Decimal | None
    perdida_devolucion_pct: Decimal | None
    ventas_al_mes: int | None
    dias_tabla: int | None
    dias_por_unidad: int | None
    dias_pago: int
    disponibles: int | None
    limite_cliente: int | None
    ranking: Decimal | None
    baja_por_competencia: bool
    marcas: tuple[str, ...]


# --- Costo de compra (RN-001 §4; PAR-07) ---------------------------------------------------


def tasa_impuesto(observacion: Observacion, impuestos: Impuestos) -> Decimal:
    """Tasa de impuesto en puntos (PAR-07; DEC-220): la de ``taxLocation`` o la de respaldo;
    0 en la compra a un particular si ``private_sellers_exempt`` (S-14)."""
    raise NotImplementedError


def costo_compra(observacion: Observacion, configuracion: Configuracion) -> CostoCompra | None:
    """Costo de compra de la oferta (RN-001 §4; REQ §3.2 paso 6). ``None`` sin precio. El envío
    hacia mí es ``shipping.toMeCost`` o el de ``shipping_to_me_default`` (PAR-06)."""
    raise NotImplementedError


# --- Estado del canal (REQ §3.2.1; S-31) ---------------------------------------------------


def estado_del_canal(
    causas_cerrado: tuple[CausaCanalCerrado, ...],
    causas_por_revisar: tuple[CausaCanalPorRevisar, ...],
) -> EstadoCanal:
    """Cerrado con alguna causa de cerrado (prevalece sobre por revisar, S-31); por revisar
    con solo causas de por revisar; disponible sin causas."""
    raise NotImplementedError


# --- Amazon (RN-004, RN-006; DEC-206) ------------------------------------------------------


def ranking_amazon(contexto: ContextoEvaluacion) -> Ranking:
    """Ranking de DEC-206 con las fichas de Amazon del contexto (design.md §10.3)."""
    raise NotImplementedError


def ficha_vigente(contexto: ContextoEvaluacion) -> FichaAmazon | None:
    """``amazonListing`` de la ficha de Amazon más reciente del contexto (vendedores y
    comprados el mes pasado). ``None`` si el producto no tiene ficha."""
    raise NotImplementedError


def demanda_en_amazon(
    categoria: Categoria,
    ranking: Ranking,
    ficha: FichaAmazon | None,
    configuracion: Configuracion,
) -> DemandaEnAmazon:
    """Demanda en Amazon (RN-004 §4 y §11; DEC-206, DEC-225) y ``DEMANDA A LA BAJA`` (el
    promedio de hoy empeoró más de ``worsening_pct`` contra el de hace 30 días)."""
    raise NotImplementedError


def comision_amazon(precio_venta: Decimal, comision: Comision) -> Decimal:
    """Comisión de Amazon de una unidad (RN-006 §4.1; DEC-217), redondeada una vez, con el
    mínimo por unidad: ``flat`` (% del precio), ``total_threshold`` (% del precio completo según
    el umbral) o ``tiers`` (parte por parte)."""
    raise NotImplementedError


def envio_amazon(observacion: Observacion, envio: Envio) -> EnvioAmazon | None:
    """Envío FBM y empaque por peso (RN-006 §4.2; S-06): el primer rango con
    ``max_kg`` ≥ peso; sin peso, ``unknown_weight``; con más de ``quote_above_kg``, la
    cotización capturada del producto o ``None`` (``ENVÍO POR COTIZAR``)."""
    raise NotImplementedError


def tasa_devolucion_amazon(
    categoria: Categoria, configuracion: Configuracion
) -> TasaDevolucion | None:
    """Tasa de devolución de la categoría (PAR-04; S-27): propia, o asignada de otra categoría
    (estimada). ``None`` sin tasa (``TASA DE DEVOLUCIÓN DESCONOCIDA``)."""
    raise NotImplementedError


def restringido_en_amazon(
    observacion: Observacion, configuracion: Configuracion, dia: dt.date
) -> bool:
    """Restricción sin cuenta de vendedor (RN-006 §4.3; S-09, S-10): categoría restringida,
    marca o producto en la tabla de PAR-05, o juguete en temporada (``dia`` en
    ``toy_season``)."""
    raise NotImplementedError


def material_peligroso(observacion: Observacion, listas: Listas) -> bool:
    """``MATERIAL PELIGROSO`` por marca o producto (PAR-05; S-07): solo marca, no cierra."""
    raise NotImplementedError


def ventas_al_mes_amazon(ficha: FichaAmazon | None) -> int | None:
    """Ventas al mes que le tocan a Jesús (RN-005 §4) = comprados el mes pasado ÷ (vendedores
    + 1), redondeado hacia abajo. ``None`` sin comprados o sin vendedores."""
    raise NotImplementedError


def competencia_mas_barata(
    precio_mercado_hoy: Decimal | None, precio_venta_amazon: Decimal | None, umbral_pct: Decimal
) -> bool:
    """``COMPETENCIA MÁS BARATA`` (RN-002 §4.3): mercado hoy < venta en Amazon × (1 −
    umbral). Sin alguno de los dos precios no se evalúa (RN-002 §11)."""
    raise NotImplementedError


def evaluar_amazon(
    contexto: ContextoEvaluacion,
    referencias: Referencias,
    costo: CostoCompra | None,
) -> CanalEvaluado:
    """Estado, causas, precio y costo de venta, insumos y marcas del canal Amazon (REQ §3.2
    paso 7, §3.2.1)."""
    raise NotImplementedError


# --- Venta local (RN-016, RN-017, RN-008) --------------------------------------------------


def precio_venta_local(
    contexto: ContextoEvaluacion, precio_mercado_hoy: Decimal | None
) -> PrecioLocal | None:
    """Precio de venta local (RN-016 §4). ``None`` sin estimado de Jesús ni precio de mercado
    hoy (``SIN PRECIO LOCAL``). El valor de referencia de usados (RN-014) lo agrega T20."""
    raise NotImplementedError


def demanda_local(contexto: ContextoEvaluacion) -> DemandaLocal:
    """Demanda local de la categoría (RN-017 §4): la captura más reciente o la inicial de
    PAR-04, un nivel menos con más de ``competition_threshold`` comparables activos."""
    raise NotImplementedError


def dias_por_unidad_local(demanda: DemandaLocal, parametros: DemandaLocalConfig) -> int | None:
    """Días de venta por unidad (RN-017 §4): alta y media de PAR-12; baja, ``None``."""
    raise NotImplementedError


def ventas_al_mes_local(demanda: DemandaLocal, parametros: DemandaLocalConfig) -> int | None:
    """Ventas locales al mes = 30 ÷ días por unidad, redondeado hacia abajo (RN-017 §4).
    ``None`` con demanda baja."""
    raise NotImplementedError


def costo_entrega(traslados: Traslados) -> Decimal:
    """Costo de entrega por defecto (RN-008 §4.3; S-24), redondeado una vez."""
    raise NotImplementedError


def evaluar_local(
    contexto: ContextoEvaluacion,
    referencias: Referencias,
    costo: CostoCompra | None,
) -> CanalEvaluado:
    """Estado, causas, precio y costo de venta, insumos y marcas de la venta local (REQ §3.2
    paso 8, §3.2.1)."""
    raise NotImplementedError
