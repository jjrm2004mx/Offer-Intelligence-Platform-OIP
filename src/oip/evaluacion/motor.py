"""Motor de evaluación de la parte B (CMP-17; REQ §3.2, design.md §3).

``evaluar(contexto) -> RegistroEvaluacion`` es **puro**: no lee la base ni el reloj (el
``instante`` viene en el contexto), no usa la red ni aleatoriedad, y la configuración entra
dentro del contexto, nunca como global.

Orquesta los pasos en el orden interno de design.md §3 (igual a REQ §3.2): validar →
identificar → referencias → descuento → calidad → costo de compra → estado y números de
cada canal → nivel → unidades, días y rendimiento → elección y nivel del aviso → motivos y
precedencia → registro. Cada paso recibe el contexto y el ``Avance`` acumulado y devuelve
un ``Avance`` nuevo.

En T04 los pasos 1 a 10 son **funciones vacías** (devuelven el avance sin cambios): las
llenan las tareas siguientes, cada una con sus reglas. Los motivos y la precedencia
(``resultado``, CMP-16) y el armado del registro ya están completos.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from decimal import Decimal

from oip.catalogos import (
    CalidadPrecio,
    Canal,
    Confianza,
    EstadoCanal,
    Identificacion,
    Motivo,
    Nivel,
    Resultado,
)
from oip.evaluacion.contexto import (
    ContextoEvaluacion,
    EvaluacionCanal,
    ObservacionUsada,
    Referencias,
    RegistroEvaluacion,
)
from oip.evaluacion.resultado import Decision, decidir, reunir_motivos

__all__ = ["PASOS", "Avance", "evaluar"]


@dataclasses.dataclass(frozen=True, slots=True)
class Avance:
    """Lo que los pasos van calculando. ``motivos`` y ``marcas`` se acumulan; el resultado y
    el motivo principal no: los decide solo el paso de motivos y precedencia."""

    motivo_rechazo: str | None = None
    identificacion: Identificacion | None = None
    confianza: Confianza | None = None
    referencias: Referencias | None = None
    descuento_anunciado: Decimal | None = None
    descuento_real: Decimal | None = None
    calidad_precio: CalidadPrecio | None = None
    costo_compra: Decimal | None = None
    canales: tuple[EvaluacionCanal, ...] = ()
    canal_elegido: Canal | None = None
    nivel_aviso: Nivel | None = None
    canal_aviso: Canal | None = None
    motivos: tuple[Motivo, ...] = ()
    marcas: tuple[str, ...] = ()
    observaciones_usadas: tuple[ObservacionUsada, ...] = ()
    decision: Decision | None = None

    @property
    def rechazada(self) -> bool:
        return self.motivo_rechazo is not None


Paso = Callable[[ContextoEvaluacion, Avance], Avance]


# --- Pasos (design.md §3; REQ §3.2) --------------------------------------------------------


def validar(contexto: ContextoEvaluacion, avance: Avance) -> Avance:
    """Paso 1 (REQ §3.2, §6; CMP-07): primer motivo de rechazo o nada. Lo llena T07."""
    return avance


def identificar(contexto: ContextoEvaluacion, avance: Avance) -> Avance:
    """Paso 2 (RN-013, RN-014, RN-015, RN-007; CMP-10): coincidencia, estado, vendedor,
    riesgos, "evitar siempre" y confianza. Lo llena su tarea."""
    return avance


def calcular_referencias(contexto: ContextoEvaluacion, avance: Avance) -> Avance:
    """Paso 3 (RN-002; CMP-11): precio habitual y episodio, mercado hoy, MSRP, mínimo de 60
    días y venta esperada en Amazon. Lo llena su tarea."""
    return avance


def calcular_descuento(contexto: ContextoEvaluacion, avance: Avance) -> Avance:
    """Paso 4 (RN-003; CMP-12): descuento anunciado y real, franja y marcas."""
    return avance


def calcular_calidad(contexto: ContextoEvaluacion, avance: Avance) -> Avance:
    """Paso 5 (RN-012; CMP-12): calidad del precio."""
    return avance


def calcular_costo_compra(contexto: ContextoEvaluacion, avance: Avance) -> Avance:
    """Paso 6 (RN-001; CMP-13): precio + impuesto + envío + recogida."""
    return avance


def evaluar_canales(contexto: ContextoEvaluacion, avance: Avance) -> Avance:
    """Pasos 7 y 8 (§3.2.1; CMP-13, CMP-14): estado y números de cada canal."""
    return avance


def asignar_nivel(contexto: ContextoEvaluacion, avance: Avance) -> Avance:
    """Nivel y ``nivel_calculado`` por canal (RN-009; CMP-14), antes que las unidades porque
    el tope depende del nivel (design.md §3)."""
    return avance


def calcular_unidades_y_rendimiento(contexto: ContextoEvaluacion, avance: Avance) -> Avance:
    """Unidades, días y rendimiento por canal (RN-005; CMP-14)."""
    return avance


def elegir_canal(contexto: ContextoEvaluacion, avance: Avance) -> Avance:
    """Paso 9 (RN-018, S-33; CMP-15): canal elegido y nivel del aviso con su canal."""
    return avance


def decidir_resultado(contexto: ContextoEvaluacion, avance: Avance) -> Avance:
    """Paso 10 (REQ §3.2.3 y §3.2.4; CMP-16): todos los motivos y la precedencia.

    "Algún canal tiene nivel" = algún canal **disponible** con nivel (§3.2.1: un canal por
    revisar solo tiene ``nivel_calculado``, informativo).
    """
    hay_nivel = any(
        c.estado is EstadoCanal.DISPONIBLE and c.nivel is not None for c in avance.canales
    )
    decision = decidir(reunir_motivos(avance.motivos), hay_nivel)
    return dataclasses.replace(avance, motivos=decision.motivos, decision=decision)


#: Pasos 1 a 10 en el orden interno de design.md §3. El 11 (registro) es ``_armar_registro``.
PASOS: tuple[Paso, ...] = (
    validar,
    identificar,
    calcular_referencias,
    calcular_descuento,
    calcular_calidad,
    calcular_costo_compra,
    evaluar_canales,
    asignar_nivel,
    calcular_unidades_y_rendimiento,
    elegir_canal,
    decidir_resultado,
)


def evaluar(contexto: ContextoEvaluacion) -> RegistroEvaluacion:
    """Evalúa la oferta del contexto y devuelve su registro (REQ §3.2 y §7). Puro."""
    if not isinstance(contexto, ContextoEvaluacion):
        raise TypeError("se esperaba un ContextoEvaluacion")
    avance = Avance()
    for paso in PASOS:
        avance = paso(contexto, avance)
        if avance.rechazada:
            # Paso 1: RECHAZADA_VALIDACION termina la evaluación (REQ §3.2 paso 1).
            break
    return _armar_registro(contexto, avance)


def _armar_registro(contexto: ContextoEvaluacion, avance: Avance) -> RegistroEvaluacion:
    """Paso 11 (REQ §7): arma el registro. Guardarlo es de la persistencia (CMP-21)."""
    oferta = contexto.oferta
    if avance.rechazada:
        return RegistroEvaluacion(
            id=contexto.id_evaluacion,
            evaluado_en=contexto.instante,
            # Una oferta rechazada no se guarda (TAB-10: offer_observation_id null).
            id_observacion_oferta=None,
            id_publicacion=oferta.id_publicacion,
            id_producto=oferta.id_producto,
            id_version_configuracion=contexto.id_version_configuracion,
            versiones_rn=contexto.versiones_rn,
            resultado=Resultado.RECHAZADA_VALIDACION,
            motivo_principal=None,
            motivos=(),
            motivo_rechazo=avance.motivo_rechazo,
            marcas=(),
            calidad_precio=None,
            confianza=None,
            identificacion=None,
            referencias=None,
            descuento_anunciado=None,
            descuento_real=None,
            costo_compra=None,
            canal_elegido=None,
            nivel_aviso=None,
            canal_aviso=None,
            canales=(),
            observaciones_usadas=(),
            entrada=contexto,
            id_evaluacion_anterior=contexto.id_evaluacion_anterior,
            referencias_cambiadas=contexto.referencias_cambiadas,
            id_carga=contexto.id_carga,
        )
    decision = avance.decision
    if decision is None:
        raise RuntimeError("el paso de motivos y precedencia no corrió")
    asignado = decision.resultado is Resultado.NIVEL_ASIGNADO
    return RegistroEvaluacion(
        id=contexto.id_evaluacion,
        evaluado_en=contexto.instante,
        id_observacion_oferta=oferta.id,
        id_publicacion=oferta.id_publicacion,
        id_producto=oferta.id_producto,
        id_version_configuracion=contexto.id_version_configuracion,
        versiones_rn=contexto.versiones_rn,
        resultado=decision.resultado,
        motivo_principal=decision.motivo_principal,
        motivos=decision.motivos,
        motivo_rechazo=None,
        marcas=avance.marcas,
        calidad_precio=avance.calidad_precio,
        confianza=avance.confianza,
        identificacion=avance.identificacion,
        referencias=avance.referencias,
        descuento_anunciado=avance.descuento_anunciado,
        descuento_real=avance.descuento_real,
        costo_compra=avance.costo_compra,
        canal_elegido=avance.canal_elegido,
        # Nivel del aviso y su canal solo con NIVEL_ASIGNADO (design.md §10.6).
        nivel_aviso=avance.nivel_aviso if asignado else None,
        canal_aviso=avance.canal_aviso if asignado else None,
        canales=avance.canales,
        observaciones_usadas=avance.observaciones_usadas,
        entrada=contexto,
        id_evaluacion_anterior=contexto.id_evaluacion_anterior,
        referencias_cambiadas=contexto.referencias_cambiadas,
        id_carga=contexto.id_carga,
    )
