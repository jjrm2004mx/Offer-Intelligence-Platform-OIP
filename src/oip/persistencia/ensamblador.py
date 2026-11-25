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
from uuid import UUID, uuid4

from oip.evaluacion.contexto import ContextoEvaluacion, RegistroEvaluacion
from oip.persistencia.repositorios import Repositorio, VersionConfiguracion

__all__ = [
    "Diferencia",
    "ErrorEnsamblador",
    "EvaluacionNoEncontrada",
    "EvaluacionNoRecalculable",
    "ResultadoRecalculo",
    "armar_contexto",
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
        raise NotImplementedError


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
    ``TypeError`` si el ``instante`` no lleva desfase."""
    raise NotImplementedError


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
    raise NotImplementedError


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
    raise NotImplementedError


def recalcular(repositorio: Repositorio, id_evaluacion: UUID) -> ResultadoRecalculo:
    """Recalcula la evaluación guardada ``id_evaluacion`` desde su ``input_snapshot`` (que
    trae el contenido completo de la versión de configuración que cita, ``config_version_id``)
    y la compara con el registro guardado (RNF-3,
    CTR-06). No escribe nada. Levanta ``EvaluacionNoEncontrada`` si no existe y
    ``EvaluacionNoRecalculable`` si es un ``RECHAZADA_VALIDACION`` (DEC-250)."""
    raise NotImplementedError
