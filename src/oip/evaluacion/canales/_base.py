"""Tipos, apoyo y estado del canal de CMP-13 (``oip.evaluacion.canales``)."""

from __future__ import annotations

import dataclasses
import datetime as dt
from collections.abc import Iterable
from decimal import Decimal

from oip.catalogos import (
    Canal,
    CausaCanalCerrado,
    CausaCanalPorRevisar,
    Condicion,
    DemandaAmazon,
    DemandaLocal,
    EstadoCanal,
)
from oip.configuracion import (
    Configuracion,
    ProductoRef,
    Temporada,
)
from oip.entradas.contrato import Observacion
from oip.evaluacion import referencias as refs
from oip.evaluacion._tipos import verificar_dataclass
from oip.evaluacion.contexto import ContextoEvaluacion, Referencias

_CIEN = Decimal(100)
_TREINTA = 30  # días de un mes en RN-005 y RN-017 ("30 ÷ días", "× 30 ÷ días")
_ORDEN_DEMANDA_LOCAL = (DemandaLocal.HIGH, DemandaLocal.MEDIUM, DemandaLocal.LOW)


class _Estricto:
    """Verificación estricta de tipos al construir (DEC-238)."""

    __slots__ = ()

    def __post_init__(self) -> None:
        verificar_dataclass(self)


# --- Tipos ---------------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class CostoCompra(_Estricto):
    """Costo de compra de la oferta (RN-001 §4). Montos redondeados una vez cada uno;
    ``total`` = precio + impuesto + envío hacia mí + recogida, ya redondeados.
    ``tasa_impuesto_pct`` en puntos, sin redondear. ``recogida`` es el traslado de recogida de
    una compra a particular (RN-008, S-14; ``TipoMonto.TRASLADO_RECOGIDA``); 0 en las demás."""

    precio: Decimal
    tasa_impuesto_pct: Decimal
    impuesto: Decimal
    envio_hacia_mi: Decimal
    total: Decimal
    recogida: Decimal = Decimal(0)


@dataclasses.dataclass(frozen=True, slots=True)
class Ranking(_Estricto):
    """Ranking de Amazon (DEC-206; design.md §10.3), sin redondear. ``promedio`` es ``None``
    con 0 días de datos; ``promedio_hace_30_dias``, el de los días que terminan
    ``trend_lookback_days`` antes (``None`` sin datos)."""

    promedio: Decimal | None
    dias_con_datos: int
    promedio_hace_30_dias: Decimal | None


@dataclasses.dataclass(frozen=True, slots=True)
class DemandaEnAmazon(_Estricto):
    """Demanda en Amazon (RN-004 §4) y su advertencia ``DEMANDA A LA BAJA``.
    ``empeoramiento_pct`` (puntos, sin redondear) solo existe con los dos promedios."""

    demanda: DemandaAmazon
    a_la_baja: bool
    empeoramiento_pct: Decimal | None


@dataclasses.dataclass(frozen=True, slots=True)
class EnvioAmazon(_Estricto):
    """Envío FBM y empaque de una unidad (RN-006 §4.2; S-06). ``peso_estimado`` = sin peso,
    con el envío y el empaque de ``unknown_weight`` y la marca ``ESTIMADO (peso)``."""

    envio: Decimal
    empaque: Decimal
    peso_estimado: bool


@dataclasses.dataclass(frozen=True, slots=True)
class TasaDevolucion(_Estricto):
    """Tasa de devolución en Amazon y pérdida por devolución (RN-005; S-27), en puntos.
    ``estimada`` = tasa asignada de otra categoría (marca ``ESTIMADO (devolución)``)."""

    tasa_pct: Decimal
    perdida_pct: Decimal
    estimada: bool


@dataclasses.dataclass(frozen=True, slots=True)
class PrecioLocal(_Estricto):
    """Precio de venta local (RN-016 §4), redondeado una vez. ``techo`` es el menor precio
    pedido de los comparables (``None`` sin comparables: marca ``SIN COMPARABLES LOCALES``)."""

    precio: Decimal
    techo: Decimal | None


@dataclasses.dataclass(frozen=True, slots=True)
class CanalEvaluado(_Estricto):
    """Estado de un canal, sus números base y lo que necesita la rentabilidad (CMP-14).

    - ``precio_venta`` y ``costo_venta``: ``None`` si no se pueden calcular (sin precio de venta,
      comisión desconocida, envío por cotizar…); el margen neto solo existe con los dos. En
      venta local, ``costo_venta`` = entrega de RN-008 + otros (RN-001 §4; PAR-12 no trae
      otros; design.md §10 punto 14), de modo que neto = venta − compra − costo de venta.
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

    def __post_init__(self) -> None:
        _Estricto.__post_init__(self)
        for nombre in ("causas_cerrado", "causas_por_revisar", "marcas"):
            valores = getattr(self, nombre)
            if len(set(valores)) != len(valores):
                raise ValueError(f"{nombre}: sin repetidos")
        if self.estado is not estado_del_canal(self.causas_cerrado, self.causas_por_revisar):
            raise ValueError("estado: no sigue las causas del canal (REQ §3.2.1, S-31)")


# --- Apoyo ---------------------------------------------------------------------------------


def _pct(valor: Decimal) -> Decimal:
    return valor / _CIEN


def _sin_repetidos(valores: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(valores))


def _normal(texto: str | None) -> str | None:
    if texto is None:
        return None
    limpio = " ".join(texto.split()).casefold()
    return limpio or None


def _es_el_producto(ref: ProductoRef, observacion: Observacion) -> bool:
    """El producto de una lista de PAR-05 (RN-013): por GTIN o por marca + modelo."""
    if ref.gtin is not None and observacion.gtin is not None:
        if ref.gtin == observacion.gtin.strip():
            return True
    marca, modelo = _normal(observacion.brand), _normal(observacion.model)
    if ref.brand is None or ref.model is None or marca is None or modelo is None:
        return False
    return _normal(ref.brand) == marca and _normal(ref.model) == modelo


def _marca_en(marcas: tuple[str, ...], observacion: Observacion) -> bool:
    marca = _normal(observacion.brand)
    return marca is not None and any(_normal(m) == marca for m in marcas)


def _en_temporada(dia: dt.date, temporada: Temporada) -> bool:
    """``dia`` dentro de la temporada ``MM-DD`` (inclusiva; puede cruzar el fin de año)."""
    hoy = f"{dia.month:02d}-{dia.day:02d}"
    if temporada.start <= temporada.end:
        return temporada.start <= hoy <= temporada.end
    return hoy >= temporada.start or hoy <= temporada.end


def _condicion_de(observacion: Observacion) -> Condicion:
    """Estado de la oferta para comparar (S-13): desconocido de un comercio = nuevo; de un
    particular = usado."""
    if observacion.condition is not None:
        return observacion.condition
    return Condicion.NEW if refs.es_nuevo(observacion) else Condicion.USED


# --- Estado del canal (REQ §3.2.1; S-31) ---------------------------------------------------


def estado_del_canal(
    causas_cerrado: tuple[CausaCanalCerrado, ...],
    causas_por_revisar: tuple[CausaCanalPorRevisar, ...],
) -> EstadoCanal:
    """Cerrado con alguna causa de cerrado (prevalece sobre por revisar, S-31); por revisar
    con solo causas de por revisar; disponible sin causas."""
    for nombre, causas, tipo in (
        ("causas_cerrado", causas_cerrado, CausaCanalCerrado),
        ("causas_por_revisar", causas_por_revisar, CausaCanalPorRevisar),
    ):
        if not isinstance(causas, tuple) or not all(isinstance(c, tipo) for c in causas):
            raise TypeError(f"{nombre} debe ser una tupla de {tipo.__name__}")
    if causas_cerrado:
        return EstadoCanal.CERRADO
    if causas_por_revisar:
        return EstadoCanal.POR_REVISAR
    return EstadoCanal.DISPONIBLE


# --- Comunes a los dos canales ------------------------------------------------------------


def _limite_cliente(observacion: Observacion, configuracion: Configuracion) -> int | None:
    if observacion.store_code is None:
        return None
    sucursal = configuracion.stores.get(observacion.store_code.strip())
    return None if sucursal is None else sucursal.max_units_per_customer


def _exigir_entradas(
    contexto: object, referencias: object, costo: object
) -> tuple[ContextoEvaluacion, Referencias]:
    if not isinstance(contexto, ContextoEvaluacion):
        raise TypeError("se esperaba un ContextoEvaluacion")
    if not isinstance(referencias, Referencias):
        raise TypeError("se esperaban las Referencias")
    if costo is not None and not isinstance(costo, CostoCompra):
        raise TypeError("se esperaba un CostoCompra o None")
    return contexto, referencias
