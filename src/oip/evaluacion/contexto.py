"""Tipos del dominio del motor: contexto y registro de evaluación (CMP-09; CTR-06, RNF-3).

- ``ContextoEvaluacion``: todo lo que el motor necesita, **ya leído** (design.md §3): la
  observación de la oferta, el historial del producto hasta el ``instante``, las fichas de
  Amazon, los comparables, estimados, MSRP y demanda local vigentes, la versión de
  configuración con su contenido completo (y con ella la versión de cada RN, PAR-01) y el
  ``instante``. También trae los identificadores que el motor no puede inventar porque es
  puro (sin reloj ni aleatoriedad): el de la evaluación, el de la versión de configuración
  (TAB-01), el de la carga y, en una reevaluación, el de la evaluación anterior y las
  referencias que cambiaron (CMP-18).
- ``RegistroEvaluacion``: el registro de REQ §7, con los campos de TAB-10 y, por canal, los
  de TAB-11 (``EvaluacionCanal``). ``entrada`` es el ``input_snapshot`` (CTR-06).
- Serialización **JSON canónica** (CTR-06): ``a_json`` y ``desde_json`` de cada tipo; la ida
  y vuelta da un objeto igual y un texto igual byte a byte (``_canonico``).

Todos los tipos son ``dataclass(frozen=True, slots=True)`` y verifican sus tipos al
construirse, sin conversiones implícitas (DEC-238): un ``float``, un booleano como entero o
una lista donde va una tupla levantan ``TypeError``. Este módulo no lee la base, no usa el
reloj y no hace I/O (design.md §14).

Correspondencia con las columnas (design.md §4; nombres en Python en español, §14).

TAB-10 ``evaluation`` → ``RegistroEvaluacion``:
- ``id`` → ``id``
- ``evaluated_at`` → ``evaluado_en``
- ``offer_observation_id`` → ``id_observacion_oferta``
- ``listing_id`` → ``id_publicacion``
- ``product_id`` → ``id_producto``
- ``config_version_id`` → ``id_version_configuracion``
- ``rn_versions`` → ``versiones_rn``
- ``result`` → ``resultado``
- ``main_reason`` → ``motivo_principal``
- ``reasons`` → ``motivos``
- ``rejection_reason`` → ``motivo_rechazo``
- ``marks`` → ``marcas``
- ``price_quality`` → ``calidad_precio``
- ``confidence`` → ``confianza``
- ``identification`` → ``identificacion``
- ``references`` → ``referencias``
- ``advertised_discount`` → ``descuento_anunciado``
- ``real_discount`` → ``descuento_real``
- ``purchase_cost`` → ``costo_compra``
- ``chosen_channel`` → ``canal_elegido``
- ``alert_level`` → ``nivel_aviso``
- ``alert_channel`` → ``canal_aviso``
- ``observations_used`` → ``observaciones_usadas``
- ``input_snapshot`` → ``entrada``
- ``previous_evaluation_id`` → ``id_evaluacion_anterior``
- ``changed_references`` → ``referencias_cambiadas``
- ``no_longer_recommended`` → ``ya_no_recomendado``
- ``load_run_id`` → ``id_carga``

TAB-11 ``evaluation_channel`` → ``EvaluacionCanal`` (en ``RegistroEvaluacion.canales``):
- ``evaluation_id`` → ``(el registro que lo contiene)``
- ``channel`` → ``canal``
- ``state`` → ``estado``
- ``closed_causes`` → ``causas_cerrado``
- ``review_causes`` → ``causas_por_revisar``
- ``sale_price`` → ``precio_venta``
- ``selling_cost`` → ``costo_venta``
- ``net_margin`` → ``margen_neto``
- ``net_margin_pct`` → ``margen_neto_pct``
- ``returns_cost`` → ``costo_devoluciones``
- ``drop_penalty`` → ``castigo``
- ``adjusted_margin`` → ``margen_ajustado``
- ``adjusted_margin_pct`` → ``margen_ajustado_pct``
- ``units`` → ``unidades``
- ``days_to_recover`` → ``dias_para_recuperar``
- ``monthly_yield_pct`` → ``rendimiento_mensual_pct``
- ``level`` → ``nivel``
- ``calculated_level`` → ``nivel_calculado``
- ``total_profit`` → ``ganancia_total``
- ``marks`` → ``marcas``
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Self
from uuid import UUID

from oip.catalogos import (
    CalidadPrecio,
    Canal,
    CausaCanalCerrado,
    CausaCanalPorRevisar,
    Confianza,
    EstadoCanal,
    Identificacion,
    Motivo,
    Nivel,
    ReferenciaPrecio,
    Resultado,
)
from oip.configuracion import ConfiguracionVersionada
from oip.entradas.capturas import (
    CapturaMsrp,
    ComparableLocal,
    DemandaLocalCapturada,
    EstimadoLocal,
)
from oip.entradas.contrato import Observacion
from oip.evaluacion._canonico import ErrorSerializacion, a_json, desde_json
from oip.evaluacion._tipos import campos_dataclass, verificar_tipo

__all__ = [
    "ContextoEvaluacion",
    "Episodio",
    "ErrorSerializacion",
    "EvaluacionCanal",
    "ObservacionRegistrada",
    "ObservacionUsada",
    "Referencias",
    "RegistroEvaluacion",
]


class _Dominio:
    """Base de los tipos del dominio: verificación estricta y JSON canónico (CTR-06)."""

    __slots__ = ()

    def __post_init__(self) -> None:
        for campo in dataclasses.fields(self):  # type: ignore[arg-type]
            valor = getattr(self, campo.name)
            if isinstance(valor, Mapping) and not isinstance(valor, MappingProxyType):
                # Inmutable sin cambiar su contenido.
                valor = MappingProxyType(dict(valor))
                object.__setattr__(self, campo.name, valor)
            verificar_tipo(valor, _pistas(type(self))[campo.name], campo.name)
            if isinstance(valor, dt.datetime) and valor.tzinfo is not dt.UTC:
                # El mismo instante en UTC (CTR-06): el original y el leído del JSON quedan
                # idénticos también en su zona. El día evaluado usa la zona de PAR-01.
                object.__setattr__(self, campo.name, valor.astimezone(dt.UTC))

    def a_json(self) -> str:
        """JSON canónico (CTR-06): claves ordenadas, decimales como texto, fechas en UTC."""
        return a_json(self, type(self))

    @classmethod
    def desde_json(cls, texto: str | bytes) -> Self:
        """Lee el JSON canónico de ``a_json`` (estricto, DEC-238)."""
        return desde_json(texto, cls)


def _pistas(clase: type) -> dict[str, Any]:
    return dict(campos_dataclass(clase))


# --- Contexto -----------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class ObservacionRegistrada(_Dominio):
    """Una observación del contrato 3.1 con sus identificadores de TAB-05 (``observation_id``,
    ``listing_id``, ``product_id``). Solo la oferta de una evaluación que se rechaza en la
    validación puede no tenerlos: no se guarda (TAB-10, ``offer_observation_id`` null)."""

    observacion: Observacion
    id: UUID | None
    id_publicacion: UUID | None
    id_producto: UUID | None


@dataclasses.dataclass(frozen=True, slots=True)
class ContextoEvaluacion(_Dominio):
    """Entrada del motor, completa y ya leída (design.md §3). Nada posterior al ``instante``
    entra al contexto (lo garantiza quien lo arma, CMP-21).

    ``historial`` y ``fichas_amazon`` traen siempre sus identificadores (son observaciones
    guardadas); las colecciones vacías equivalen a "no hay datos".
    """

    id_evaluacion: UUID
    instante: dt.datetime
    configuracion: ConfiguracionVersionada
    id_version_configuracion: int | None
    oferta: ObservacionRegistrada
    historial: tuple[ObservacionRegistrada, ...] = ()
    fichas_amazon: tuple[ObservacionRegistrada, ...] = ()
    comparables: tuple[ComparableLocal, ...] = ()
    estimados: tuple[EstimadoLocal, ...] = ()
    msrp: tuple[CapturaMsrp, ...] = ()
    demanda_local: tuple[DemandaLocalCapturada, ...] = ()
    id_evaluacion_anterior: UUID | None = None
    referencias_cambiadas: tuple[ReferenciaPrecio, ...] = ()
    id_carga: UUID | None = None

    def __post_init__(self) -> None:
        _Dominio.__post_init__(self)
        for nombre in ("historial", "fichas_amazon"):
            for i, registrada in enumerate(getattr(self, nombre)):
                if None in (registrada.id, registrada.id_publicacion, registrada.id_producto):
                    raise ValueError(f"{nombre}[{i}]: una observación guardada lleva sus ids")
        _sin_repetidos(self.referencias_cambiadas, "referencias_cambiadas")

    @property
    def versiones_rn(self) -> Mapping[str, int]:
        """Versión de cada RN (PAR-01, ``general.rn_versions``) de la configuración."""
        return self.configuracion.contenido.general.rn_versions


# --- Registro -----------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class ObservacionUsada(_Dominio):
    """Observación usada en la evaluación, con su fecha (REQ §7; ``observations_used``)."""

    id: UUID
    fecha: dt.datetime


@dataclasses.dataclass(frozen=True, slots=True)
class Episodio(_Dominio):
    """Episodio de liquidación de la publicación (REQ §3.2 paso 3; design.md §10.2): inicio y
    valor congelado del precio habitual, sin redondear (DEC-226 b)."""

    inicio: dt.date
    valor_congelado: Decimal


@dataclasses.dataclass(frozen=True, slots=True)
class Referencias(_Dominio):
    """Referencias de precio de la evaluación (TAB-10 ``references``; RN-002), sin redondear.

    ``fuente_precio_habitual`` es la fuente de ``FuentePrecios`` (``historial_propio``).
    """

    precio_habitual: Decimal | None = None
    fuente_precio_habitual: str | None = None
    episodio: Episodio | None = None
    precio_mercado_hoy: Decimal | None = None
    msrp: Decimal | None = None
    minimo_60_dias_amazon: Decimal | None = None
    precio_venta_amazon: Decimal | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class EvaluacionCanal(_Dominio):
    """Estado y números de un canal (TAB-11; REQ §3.2.1). Un dato que no se calcula en el
    estado del canal queda en ``None``."""

    canal: Canal
    estado: EstadoCanal
    causas_cerrado: tuple[CausaCanalCerrado, ...] = ()
    causas_por_revisar: tuple[CausaCanalPorRevisar, ...] = ()
    precio_venta: Decimal | None = None
    costo_venta: Decimal | None = None
    margen_neto: Decimal | None = None
    margen_neto_pct: Decimal | None = None
    costo_devoluciones: Decimal | None = None
    castigo: Decimal | None = None
    margen_ajustado: Decimal | None = None
    margen_ajustado_pct: Decimal | None = None
    unidades: int | None = None
    dias_para_recuperar: int | None = None
    rendimiento_mensual_pct: Decimal | None = None
    nivel: Nivel | None = None
    nivel_calculado: Nivel | None = None
    ganancia_total: Decimal | None = None
    marcas: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _Dominio.__post_init__(self)
        _sin_repetidos(self.causas_cerrado, "causas_cerrado")
        _sin_repetidos(self.causas_por_revisar, "causas_por_revisar")
        _sin_repetidos(self.marcas, "marcas")


@dataclasses.dataclass(frozen=True, slots=True)
class RegistroEvaluacion(_Dominio):
    """Registro de evaluación (REQ §7; TAB-10 y TAB-11).

    Invariantes de la precedencia (REQ §3.2.4; CMP-16): ``motivos`` sin repetidos y en el
    orden de §3.2.3; ``motivo_principal`` es el primero; con motivos, el resultado es el
    "lleva a" del principal; ``motivo_rechazo`` solo y siempre en ``RECHAZADA_VALIDACION``;
    nivel del aviso y su canal solo con ``NIVEL_ASIGNADO`` (design.md §10.6), que exige canal
    elegido, nivel del aviso y su canal (REQ §3.2.2). ``entrada`` no sale en el ``repr``.
    """

    id: UUID
    evaluado_en: dt.datetime
    id_observacion_oferta: UUID | None
    id_publicacion: UUID | None
    id_producto: UUID | None
    id_version_configuracion: int | None
    versiones_rn: Mapping[str, int]
    resultado: Resultado
    motivo_principal: Motivo | None
    motivos: tuple[Motivo, ...]
    motivo_rechazo: str | None
    marcas: tuple[str, ...]
    calidad_precio: CalidadPrecio | None
    confianza: Confianza | None
    identificacion: Identificacion | None
    referencias: Referencias | None
    descuento_anunciado: Decimal | None
    descuento_real: Decimal | None
    costo_compra: Decimal | None
    canal_elegido: Canal | None
    nivel_aviso: Nivel | None
    canal_aviso: Canal | None
    canales: tuple[EvaluacionCanal, ...]
    observaciones_usadas: tuple[ObservacionUsada, ...]
    entrada: ContextoEvaluacion = dataclasses.field(repr=False)
    id_evaluacion_anterior: UUID | None = None
    referencias_cambiadas: tuple[ReferenciaPrecio, ...] = ()
    ya_no_recomendado: bool = False
    id_carga: UUID | None = None

    def __post_init__(self) -> None:
        _Dominio.__post_init__(self)
        _sin_repetidos(self.marcas, "marcas")
        _sin_repetidos(self.referencias_cambiadas, "referencias_cambiadas")
        orden = list(Motivo)
        if list(self.motivos) != sorted(set(self.motivos), key=orden.index):
            raise ValueError("motivos: sin repetidos y en el orden de REQ §3.2.3")
        principal = self.motivos[0] if self.motivos else None
        if self.motivo_principal is not principal:
            raise ValueError("motivo_principal: debe ser el primero de motivos (§3.2.3)")
        rechazada = self.resultado is Resultado.RECHAZADA_VALIDACION
        if rechazada != (self.motivo_rechazo is not None):
            raise ValueError("motivo_rechazo: solo y siempre en RECHAZADA_VALIDACION")
        if principal is not None and self.resultado is not principal.lleva_a:
            raise ValueError("resultado: no sigue la precedencia de REQ §3.2.4")
        if principal is None and self.resultado not in _SIN_MOTIVO:
            raise ValueError("resultado: sin motivos solo puede ser rechazo, sin nivel o nivel")
        asignado = self.resultado is Resultado.NIVEL_ASIGNADO
        aviso = (self.canal_elegido, self.nivel_aviso, self.canal_aviso)
        if asignado and None in aviso:
            raise ValueError("NIVEL_ASIGNADO: lleva canal elegido, nivel del aviso y su canal")
        if not asignado and (self.nivel_aviso is not None or self.canal_aviso is not None):
            raise ValueError("nivel_aviso y canal_aviso: solo con NIVEL_ASIGNADO")
        canales = [c.canal for c in self.canales]
        if canales != sorted(set(canales), key=list(Canal).index):
            raise ValueError("canales: uno por canal, en el orden amazon, local")


_SIN_MOTIVO = frozenset(
    {Resultado.RECHAZADA_VALIDACION, Resultado.SIN_NIVEL, Resultado.NIVEL_ASIGNADO}
)


def _sin_repetidos(valores: tuple[Any, ...], nombre: str) -> None:
    if len(set(valores)) != len(valores):
        raise ValueError(f"{nombre}: sin repetidos")
