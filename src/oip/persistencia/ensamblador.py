"""Ensamblador: servicio de evaluación de la parte B (CMP-21; design.md §2, §3, §5, CTR-06).

Une el repositorio (CMP-20) con el motor puro (CMP-17):

- **Contexto "a un instante"** (design.md §3 y §5): ``armar_contexto`` lee del repositorio lo
  que se sabía al ``instante`` y nada posterior: las observaciones del producto con
  ``observed_at ≤ instante`` en la ventana del contexto (los días del precio habitual más
  el límite del episodio, PAR-08: 60 + 30 = 90 días; DEC-264), las fichas de Amazon de la
  ventana del mínimo de Amazon (PAR-08, 60 días), y las capturas (comparables, estimados,
  MSRP y demanda local) con ``captured_at ≤ instante`` (DEC-271). Las ventanas salen de la
  configuración de la evaluación, no del código.
- **Evaluar y guardar:** ``evaluar_observacion`` arma el contexto, llama a
  ``motor.evaluar`` y guarda el registro (TAB-10 y TAB-11) con su ``config_version_id``, las
  versiones de las RN (PAR-01) y su ``input_snapshot`` (CTR-06), en una transacción.
- **Después de una carga:** ``evaluar_carga`` evalúa, en el orden del archivo, cada
  observación nueva de un origen de compra; una ficha de Amazon no se evalúa como oferta
  (DEC-203).
- **Recalcular** (RNF-3, CTR-06): ``recalcular`` deserializa el ``input_snapshot`` de una
  evaluación guardada, vuelve a evaluar y compara con el registro guardado. Un registro
  ``RECHAZADA_VALIDACION`` no tiene ``input_snapshot`` y no se recalcula (DEC-250).

Fuera de alcance: la reevaluación de oportunidades abiertas (CMP-18, T22).

No decide reglas de negocio, no lee el reloj (el ``instante`` lo pasa quien llama) y no usa
la red. Ningún mensaje lleva contenido de un renglón ni el alias de un cliente (DEC-181).
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from collections.abc import Callable, Sequence
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from oip.catalogos import TipoRegistro
from oip.evaluacion import motor
from oip.evaluacion._canonico import a_json
from oip.evaluacion._tipos import campos_dataclass
from oip.evaluacion.contexto import (
    ContextoEvaluacion,
    EvaluacionCanal,
    ObservacionRegistrada,
    RegistroEvaluacion,
)
from oip.persistencia.repositorios import Repositorio, VersionConfiguracion

__all__ = [
    "Diferencia",
    "ErrorEnsamblador",
    "EvaluacionNoEncontrada",
    "EvaluacionNoRecalculable",
    "ResultadoRecalculo",
    "armar_contexto",
    "dias_del_contexto",
    "evaluar_carga",
    "evaluar_observacion",
    "recalcular",
]


class ErrorEnsamblador(Exception):
    """Error del servicio de evaluación. El mensaje lleva solo identificadores."""


class EvaluacionNoEncontrada(ErrorEnsamblador, LookupError):
    """No hay una evaluación guardada con ese id, o una observación guardada con ese id."""


class EvaluacionNoRecalculable(ErrorEnsamblador):
    """La evaluación no se recalcula: un ``RECHAZADA_VALIDACION`` no guarda
    ``input_snapshot`` (DEC-250)."""


@dataclasses.dataclass(frozen=True, slots=True)
class Diferencia:
    """Un campo del registro (nombre de TAB-10, o ``canales[<canal>].<campo>`` de TAB-11)
    cuyo valor guardado no es igual al recalculado; los valores, en el JSON canónico de
    CTR-06."""

    campo: str
    guardado: str
    recalculado: str


@dataclasses.dataclass(frozen=True, slots=True)
class ResultadoRecalculo:
    """Resultado de ``recalcular``: ``coincide`` si el registro recalculado es igual al
    guardado (RNF-3); si no, ``diferencias`` dice en qué campos, en orden de campo."""

    id_evaluacion: UUID
    coincide: bool
    diferencias: tuple[Diferencia, ...] = ()

    def a_json(self) -> dict[str, object]:
        """``{"evaluationId", "matches", "differences": [{"field", "stored",
        "recalculated"}]}``, listo para ``json.dumps``."""
        return {
            "evaluationId": str(self.id_evaluacion),
            "matches": self.coincide,
            "differences": [
                {"field": d.campo, "stored": d.guardado, "recalculated": d.recalculado}
                for d in self.diferencias
            ],
        }


# --- Contexto "a un instante" ---------------------------------------------------------------


def _exigir_instante(instante: object) -> dt.datetime:
    if not isinstance(instante, dt.datetime) or instante.utcoffset() is None:
        raise TypeError("instante: se esperaba una fecha y hora con desfase")
    return instante


def _exigir_version(version: object) -> VersionConfiguracion:
    if not isinstance(version, VersionConfiguracion):
        raise TypeError("version: se esperaba la VersionConfiguracion guardada")
    return version


def dias_del_contexto(version: VersionConfiguracion) -> int:
    """Días de historial del contexto (design.md §3; DEC-264): la ventana del precio
    habitual más el límite del episodio (PAR-08, ``usual_window_days`` +
    ``clearance_episode_max_days``; 60 + 30 = 90 en la configuración base)."""
    parametros = _exigir_version(version).configuracion.contenido.price_reference
    return parametros.usual_window_days + parametros.clearance_episode_max_days


def _desde(instante: dt.datetime, version: VersionConfiguracion) -> dt.datetime:
    """Inicio (00:00 en la zona de PAR-01) del primer día del contexto: el día evaluado
    menos ``dias_del_contexto`` días. Así entra el día completo más antiguo que puede pedir
    el precio habitual del primer día de un episodio (design.md §10.2)."""
    zona = ZoneInfo(version.configuracion.contenido.general.timezone)
    try:
        dia = instante.astimezone(zona).date() - dt.timedelta(days=dias_del_contexto(version))
        return dt.datetime.combine(dia, dt.time(0), tzinfo=zona).astimezone(dt.UTC)
    except OverflowError:
        return dt.datetime.min.replace(tzinfo=dt.UTC)


def armar_contexto(
    repositorio: Repositorio,
    id_observacion: UUID,
    instante: dt.datetime,
    version: VersionConfiguracion,
    *,
    id_evaluacion: UUID,
    id_carga: UUID | None = None,
) -> ContextoEvaluacion:
    """El ``ContextoEvaluacion`` de la observación guardada ``id_observacion`` (la oferta) al
    ``instante``, con la configuración ``version`` (design.md §3 y §5). Nada posterior al
    ``instante`` entra. Levanta ``EvaluacionNoEncontrada`` si la observación no existe y
    ``TypeError`` si el ``instante`` no lleva desfase.

    - ``historial``: las observaciones del producto que no son fichas de Amazon, sin la
      oferta, con ``observed_at`` entre el inicio del primer día del contexto
      (``dias_del_contexto``) y el ``instante``.
    - ``fichas_amazon``: las fichas de Amazon del producto en la **misma** ventana. Cubre los
      60 días del mínimo de Amazon (PAR-08) y no deja fuera el botón de compra de los días
      que el precio habitual cuenta (design.md §10.1; lectura de T21).
    - Capturas con ``captured_at ≤ instante`` (DEC-271): comparables, estimados y MSRP del
      producto, y la demanda local de todas las categorías. Cuál vale (la más reciente por
      ``date``, el estado, la zona) lo decide el motor.
    """
    _exigir_instante(instante)
    _exigir_version(version)
    oferta = repositorio.leer_observacion(id_observacion)
    if oferta is None or oferta.id_producto is None:
        raise EvaluacionNoEncontrada(f"observación {id_observacion}: no está guardada")
    id_producto = oferta.id_producto
    guardadas = repositorio.observaciones_del_producto(
        id_producto, instante=instante, desde=_desde(instante, version)
    )
    historial: list[ObservacionRegistrada] = []
    fichas: list[ObservacionRegistrada] = []
    for registrada in guardadas:
        if registrada.id == oferta.id:
            continue
        (fichas if registrada.observacion.es_ficha_amazon else historial).append(registrada)

    def capturas(tipo: TipoRegistro, *, del_producto: bool = True) -> tuple[Any, ...]:
        guardadas_ = repositorio.capturas(
            tipo, instante=instante, id_producto=id_producto if del_producto else None
        )
        return tuple(g.captura for g in guardadas_)

    return ContextoEvaluacion(
        id_evaluacion=id_evaluacion,
        instante=instante,
        configuracion=version.configuracion,
        id_version_configuracion=version.id,
        oferta=oferta,
        historial=tuple(historial),
        fichas_amazon=tuple(fichas),
        comparables=capturas(TipoRegistro.LOCAL_COMPARABLE),
        estimados=capturas(TipoRegistro.LOCAL_ESTIMATE),
        msrp=capturas(TipoRegistro.MSRP),
        demanda_local=capturas(TipoRegistro.LOCAL_DEMAND, del_producto=False),
        id_carga=id_carga,
    )


# --- Evaluar y guardar ----------------------------------------------------------------------


def evaluar_observacion(
    repositorio: Repositorio,
    id_observacion: UUID,
    instante: dt.datetime,
    version: VersionConfiguracion,
    *,
    id_carga: UUID | None = None,
    nuevo_id: Callable[[], UUID] = uuid4,
) -> RegistroEvaluacion:
    """Evalúa la observación guardada ``id_observacion`` al ``instante`` y guarda su registro
    (TAB-10 y TAB-11) en una transacción; devuelve el registro guardado. ``nuevo_id`` da el
    id de la evaluación."""
    contexto = armar_contexto(
        repositorio,
        id_observacion,
        instante,
        version,
        id_evaluacion=nuevo_id(),
        id_carga=id_carga,
    )
    registro = motor.evaluar(contexto)
    repositorio.guardar_evaluacion(registro)
    return registro


def evaluar_carga(
    repositorio: Repositorio,
    ids_observaciones: Sequence[UUID],
    instante: dt.datetime,
    version: VersionConfiguracion,
    *,
    id_carga: UUID | None = None,
    nuevo_id: Callable[[], UUID] = uuid4,
) -> tuple[RegistroEvaluacion, ...]:
    """Evalúa, en el orden dado (el del archivo), cada observación nueva de una carga que
    sea de un origen de compra, y guarda cada registro. Una ficha de Amazon no se evalúa
    como oferta (DEC-203). Devuelve los registros guardados, en el mismo orden."""
    _exigir_instante(instante)
    _exigir_version(version)
    registros: list[RegistroEvaluacion] = []
    for id_observacion in ids_observaciones:
        registrada = repositorio.leer_observacion(id_observacion)
        if registrada is None:
            raise EvaluacionNoEncontrada(f"observación {id_observacion}: no está guardada")
        if registrada.observacion.es_ficha_amazon:
            continue  # DEC-203: la ficha de Amazon solo puede disparar reevaluaciones (T22).
        registros.append(
            evaluar_observacion(
                repositorio,
                id_observacion,
                instante,
                version,
                id_carga=id_carga,
                nuevo_id=nuevo_id,
            )
        )
    return tuple(registros)


# --- Recalcular (RNF-3) ---------------------------------------------------------------------


def recalcular(repositorio: Repositorio, id_evaluacion: UUID) -> ResultadoRecalculo:
    """Recalcula la evaluación guardada ``id_evaluacion`` desde su ``input_snapshot`` (que
    trae el contenido completo de la versión de configuración que cita, ``config_version_id``)
    y la compara con el registro guardado (RNF-3, CTR-06). No escribe nada. Levanta
    ``EvaluacionNoEncontrada`` si no existe y ``EvaluacionNoRecalculable`` si es un
    ``RECHAZADA_VALIDACION`` (DEC-250).

    La comparación es por valor (``Decimal("99.45")`` es igual a ``Decimal("99.4500")``, que
    es como vuelve de una columna ``numeric(14,4)``); las diferencias se muestran en el JSON
    canónico de cada campo.
    """
    if not isinstance(id_evaluacion, UUID):
        raise TypeError("id_evaluacion: se esperaba un UUID")
    guardado = repositorio.leer_evaluacion(id_evaluacion)
    if guardado is None:
        raise EvaluacionNoEncontrada(f"evaluación {id_evaluacion}: no está guardada")
    if not isinstance(guardado, RegistroEvaluacion):
        raise EvaluacionNoRecalculable(
            f"evaluación {id_evaluacion}: RECHAZADA_VALIDACION no se recalcula (DEC-250)"
        )
    recalculado = motor.evaluar(guardado.entrada)
    diferencias = tuple(_diferencias(guardado, recalculado))
    return ResultadoRecalculo(id_evaluacion, not diferencias, diferencias)


#: Campo de ``RegistroEvaluacion`` → columna de TAB-10 (contexto.py, design.md §4).
_COLUMNAS_TAB10: dict[str, str] = {
    "id": "id",
    "evaluado_en": "evaluated_at",
    "id_observacion_oferta": "offer_observation_id",
    "id_publicacion": "listing_id",
    "id_producto": "product_id",
    "id_version_configuracion": "config_version_id",
    "versiones_rn": "rn_versions",
    "resultado": "result",
    "motivo_principal": "main_reason",
    "motivos": "reasons",
    "motivo_rechazo": "rejection_reason",
    "marcas": "marks",
    "calidad_precio": "price_quality",
    "confianza": "confidence",
    "identificacion": "identification",
    "referencias": "references",
    "descuento_anunciado": "advertised_discount",
    "descuento_real": "real_discount",
    "costo_compra": "purchase_cost",
    "canal_elegido": "chosen_channel",
    "nivel_aviso": "alert_level",
    "canal_aviso": "alert_channel",
    "observaciones_usadas": "observations_used",
    "entrada": "input_snapshot",
    "id_evaluacion_anterior": "previous_evaluation_id",
    "referencias_cambiadas": "changed_references",
    "ya_no_recomendado": "no_longer_recommended",
    "id_carga": "load_run_id",
}

#: Campo de ``EvaluacionCanal`` → columna de TAB-11.
_COLUMNAS_TAB11: dict[str, str] = {
    "canal": "channel",
    "estado": "state",
    "causas_cerrado": "closed_causes",
    "causas_por_revisar": "review_causes",
    "precio_venta": "sale_price",
    "costo_venta": "selling_cost",
    "margen_neto": "net_margin",
    "margen_neto_pct": "net_margin_pct",
    "costo_devoluciones": "returns_cost",
    "castigo": "drop_penalty",
    "margen_ajustado": "adjusted_margin",
    "margen_ajustado_pct": "adjusted_margin_pct",
    "unidades": "units",
    "dias_para_recuperar": "days_to_recover",
    "rendimiento_mensual_pct": "monthly_yield_pct",
    "nivel": "level",
    "nivel_calculado": "calculated_level",
    "ganancia_total": "total_profit",
    "marcas": "marks",
}


def _texto(valor: Any, tipo: Any) -> str:
    return a_json(valor, tipo)


def _diferencias(guardado: RegistroEvaluacion, recalculado: RegistroEvaluacion) -> list[Diferencia]:
    salida: list[Diferencia] = []
    for nombre, tipo in campos_dataclass(RegistroEvaluacion):
        antes, ahora = getattr(guardado, nombre), getattr(recalculado, nombre)
        if nombre == "canales":
            salida.extend(_diferencias_canales(antes, ahora))
        elif antes != ahora:
            columna = _COLUMNAS_TAB10[nombre]
            salida.append(Diferencia(columna, _texto(antes, tipo), _texto(ahora, tipo)))
    return salida


def _diferencias_canales(
    antes: tuple[EvaluacionCanal, ...], ahora: tuple[EvaluacionCanal, ...]
) -> list[Diferencia]:
    salida: list[Diferencia] = []
    por_canal_antes = {c.canal: c for c in antes}
    por_canal_ahora = {c.canal: c for c in ahora}
    for canal in sorted(por_canal_antes.keys() | por_canal_ahora.keys(), key=lambda c: c.value):
        uno, otro = por_canal_antes.get(canal), por_canal_ahora.get(canal)
        if uno is None or otro is None:
            salida.append(
                Diferencia(
                    f"canales[{canal.value}]",
                    "null" if uno is None else uno.a_json(),
                    "null" if otro is None else otro.a_json(),
                )
            )
            continue
        for nombre, tipo in campos_dataclass(EvaluacionCanal):
            a, b = getattr(uno, nombre), getattr(otro, nombre)
            if a != b:
                salida.append(
                    Diferencia(
                        f"canales[{canal.value}].{_COLUMNAS_TAB11[nombre]}",
                        _texto(a, tipo),
                        _texto(b, tipo),
                    )
                )
    return salida
