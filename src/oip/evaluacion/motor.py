"""Motor de evaluación de la parte B (CMP-17; REQ §3.2, design.md §3).

``evaluar(contexto) -> RegistroEvaluacion`` es **puro**: no lee la base ni el reloj (el
``instante`` viene en el contexto), no usa la red ni aleatoriedad, y la configuración entra
dentro del contexto, nunca como global.

Orquesta los pasos en el orden interno de design.md §3 (igual a REQ §3.2): validar →
identificar → referencias → descuento → calidad → costo de compra → estado y números de
cada canal → nivel → unidades, días y rendimiento → elección y nivel del aviso → motivos y
precedencia → registro. Cada paso recibe el contexto y el ``Avance`` acumulado y devuelve
un ``Avance`` nuevo.

En T04 los pasos 1 a 10 eran **funciones vacías** (devuelven el avance sin cambios): las
llenan las tareas siguientes, cada una con sus reglas. T07 llena el paso 1 (validar); T09,
los pasos 3 y 4 (precio habitual, episodio de liquidación, descuento real y franja); T10,
el precio de mercado hoy y el MSRP del paso 3, el descuento anunciado con sus marcas y
``SIN HISTORIAL SUFICIENTE`` del paso 4 y la calidad del precio del paso 5; T11, la
confianza del paso 2 (RN-007), el mínimo de 60 días y la venta esperada en Amazon del paso 3,
el costo de compra (paso 6), el estado y los números de cada canal (pasos 7 y 8), el nivel,
las unidades, los días y el rendimiento, y la elección del canal con el nivel del aviso
(paso 9). Los motivos y la precedencia (``resultado``, CMP-16) y el armado del registro ya
están completos.
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
    Marca,
    Motivo,
    Nivel,
    Resultado,
)
from oip.entradas.validacion import motivo_de_rechazo
from oip.evaluacion import (
    canales,
    descuento,
    eleccion,
    identificacion,
    referencias,
    rentabilidad,
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
    #: Lo que la rentabilidad necesita de cada canal (CMP-13), en el orden de ``canales``.
    insumos_canales: tuple[canales.CanalEvaluado, ...] = ()

    @property
    def rechazada(self) -> bool:
        return self.motivo_rechazo is not None


Paso = Callable[[ContextoEvaluacion, Avance], Avance]


# --- Pasos (design.md §3; REQ §3.2) --------------------------------------------------------


def validar(contexto: ContextoEvaluacion, avance: Avance) -> Avance:
    """Paso 1 (REQ §3.2, §6; CMP-07): primer motivo de rechazo de la oferta o nada.

    La oferta del contexto ya pasó la forma del contrato (``leer_observacion``); aquí se
    comprueba lo que depende de la configuración, en el orden de design.md §6: ``listed``
    del particular (DEC-242), precio, dominio o plataforma (DEC-212) y ciudad. Con un
    motivo, la evaluación termina con ``RECHAZADA_VALIDACION`` (``evaluar``).
    """
    motivo = motivo_de_rechazo(contexto.oferta.observacion, contexto.configuracion.contenido)
    if motivo is None:
        return avance
    return dataclasses.replace(avance, motivo_rechazo=motivo)


def _con_marcas(avance: Avance, nuevas: tuple[str, ...]) -> tuple[str, ...]:
    """Las marcas del registro más las nuevas, en orden y sin repetidos (REQ §3.2.3)."""
    return tuple(dict.fromkeys((*avance.marcas, *nuevas)))


def identificar(contexto: ContextoEvaluacion, avance: Avance) -> Avance:
    """Paso 2 (RN-013, RN-014, RN-015, RN-007; CMP-10): coincidencia, estado, vendedor,
    riesgos, "evitar siempre" y confianza.

    T11: la confianza de la disponibilidad (RN-007 v2; S-25) y, en tienda física con
    confianza Baja, la marca ``CONFIANZA BAJA`` (RN-009 §4.2). Lo demás lo llenan T19 y T20.
    """
    oferta = contexto.oferta.observacion
    parametros = contexto.configuracion.contenido.levels.confidence
    confianza = identificacion.confianza_disponibilidad(oferta, contexto.instante, parametros)
    marcas = avance.marcas
    if identificacion.es_tienda_fisica(oferta) and confianza is Confianza.BAJA:
        marcas = _con_marcas(avance, (Marca.CONFIANZA_BAJA.value,))
    return dataclasses.replace(avance, confianza=confianza, marcas=marcas)


def calcular_referencias(contexto: ContextoEvaluacion, avance: Avance) -> Avance:
    """Paso 3 (RN-002; CMP-11): precio habitual y episodio, mercado hoy, MSRP, mínimo de 60
    días y venta esperada en Amazon. T09: el precio habitual con su fuente y su episodio de
    liquidación; T10: el precio de mercado hoy básico y el MSRP (solo se muestra). El mínimo
    de 60 días y la venta esperada en Amazon los agregan sus tareas."""
    return dataclasses.replace(avance, referencias=referencias.calcular_referencias(contexto))


def calcular_descuento(contexto: ContextoEvaluacion, avance: Avance) -> Avance:
    """Paso 4 (RN-003; CMP-12): descuento anunciado y real, franja y marcas.

    Solo en una oferta **nueva** (S-13): la de un usado se mide contra el valor de
    referencia de RN-014 (REQ §3.2 paso 3) y no lleva ``SIN HISTORIAL SUFICIENTE``; lo
    agrega su tarea (T20). Sin precio habitual no hay descuento real y aplica el motivo
    ``SIN HISTORIAL SUFICIENTE`` (REQ §3.2.3). El descuento anunciado y sus marcas
    (``PRECIO ANTES INFLADO``, ``DESCUENTO ANUNCIADO NO COMPROBADO``) se calculan con o sin
    precio habitual.
    """
    oferta = contexto.oferta.observacion
    precio = oferta.price.current
    if precio is None or not referencias.es_nuevo(oferta):
        return avance
    parametros = contexto.configuracion.contenido.discount_quality
    tachado = oferta.price.was
    anunciado = descuento.descuento_anunciado(tachado, precio)
    tipico = referencias.precio_tipico_de_la_tienda(contexto) if tachado is not None else None
    marcas = tuple(m.value for m in descuento.marcas_del_anunciado(tachado, tipico, parametros))
    avance = dataclasses.replace(
        avance,
        descuento_anunciado=anunciado,
        marcas=(*avance.marcas, *(m for m in marcas if m not in avance.marcas)),
    )
    habitual = avance.referencias.precio_habitual if avance.referencias else None
    if habitual is None:
        motivos = (*avance.motivos, Motivo.SIN_HISTORIAL_SUFICIENTE)
        return dataclasses.replace(avance, motivos=motivos)
    real = descuento.descuento_real(habitual, precio)
    motivo = descuento.franja(real, parametros)
    motivos = avance.motivos if motivo is None else (*avance.motivos, motivo)
    return dataclasses.replace(avance, descuento_real=real, motivos=motivos)


def calcular_calidad(contexto: ContextoEvaluacion, avance: Avance) -> Avance:
    """Paso 5 (RN-012 v1; S-22, S-28; CMP-12): calidad del precio, que se muestra junto al
    resultado y no lo cambia. En un usado no aplica (DEC-215; S-13 para el estado
    desconocido). Sin datos (ni precio habitual ni precio de mercado hoy) queda vacía."""
    oferta = contexto.oferta.observacion
    precio = oferta.price.current
    if precio is None:
        return avance
    if not referencias.es_nuevo(oferta):
        return dataclasses.replace(avance, calidad_precio=CalidadPrecio.NO_APLICA)
    refs = avance.referencias if avance.referencias is not None else Referencias()
    hoy = referencias.mercado_hoy(contexto)
    datos = descuento.DatosCalidad(
        precio=precio,
        precio_habitual=refs.precio_habitual,
        descuento_real=avance.descuento_real if refs.precio_habitual is not None else None,
        precio_mercado_hoy=None if hoy is None else hoy.precio,
        otros_comercios=0 if hoy is None else len(hoy.otras_cadenas),
        minimo_registrado=referencias.minimo_registrado(contexto),
        dias_historial=referencias.dias_de_historial(contexto),
        descuento_anunciado=avance.descuento_anunciado,
        precio_antes_inflado=Marca.PRECIO_ANTES_INFLADO.value in avance.marcas,
    )
    parametros = contexto.configuracion.contenido.discount_quality
    calidad = descuento.calidad_del_precio(datos, parametros)
    return dataclasses.replace(avance, calidad_precio=calidad)


def calcular_costo_compra(contexto: ContextoEvaluacion, avance: Avance) -> Avance:
    """Paso 6 (RN-001; CMP-13): precio + impuesto + envío hacia mí (la recogida con
    particulares la agrega T20)."""
    costo = canales.costo_compra(contexto.oferta.observacion, contexto.configuracion.contenido)
    return dataclasses.replace(avance, costo_compra=None if costo is None else costo.total)


def evaluar_canales(contexto: ContextoEvaluacion, avance: Avance) -> Avance:
    """Pasos 7 y 8 (§3.2.1; CMP-13, CMP-14): estado, causas, precio y costo de venta y
    márgenes de cada canal. Las marcas de cada canal (también sus causas de cerrado, REQ
    §3.2.3) van en el canal (TAB-11 ``marks``); las de la oferta, en el registro (TAB-10)."""
    if avance.costo_compra is None:
        return avance
    configuracion = contexto.configuracion.contenido
    refs = avance.referencias if avance.referencias is not None else Referencias()
    costo = canales.costo_compra(contexto.oferta.observacion, configuracion)
    insumos = (
        canales.evaluar_amazon(contexto, refs, costo),
        canales.evaluar_local(contexto, refs, costo),
    )
    evaluados = []
    for canal in insumos:
        margenes = rentabilidad.calcular_margenes(
            canal,
            avance.costo_compra,
            refs.minimo_60_dias_amazon,
            configuracion.amazon.drop_penalty,
        )
        evaluados.append(
            EvaluacionCanal(
                canal=canal.canal,
                estado=canal.estado,
                causas_cerrado=canal.causas_cerrado,
                causas_por_revisar=canal.causas_por_revisar,
                precio_venta=canal.precio_venta,
                costo_venta=canal.costo_venta,
                margen_neto=None if margenes is None else margenes.margen_neto,
                margen_neto_pct=None if margenes is None else margenes.margen_neto_pct,
                costo_devoluciones=None if margenes is None else margenes.costo_devoluciones,
                castigo=None if margenes is None else margenes.castigo,
                margen_ajustado=None if margenes is None else margenes.margen_ajustado,
                margen_ajustado_pct=None if margenes is None else margenes.margen_ajustado_pct,
                marcas=canal.marcas,
            )
        )
    return dataclasses.replace(avance, canales=tuple(evaluados), insumos_canales=insumos)


def _con_insumos(avance: Avance) -> bool:
    """Los canales los armó ``evaluar_canales`` con sus insumos (uno por canal)."""
    return bool(avance.canales) and len(avance.canales) == len(avance.insumos_canales)


def asignar_nivel(contexto: ContextoEvaluacion, avance: Avance) -> Avance:
    """Nivel y ``nivel_calculado`` por canal (RN-009; CMP-14), antes que las unidades porque
    el tope depende del nivel (design.md §3)."""
    if avance.costo_compra is None or not _con_insumos(avance):
        return avance
    confianza_ok = identificacion.confianza_permite_nivel(
        contexto.oferta.observacion, avance.confianza
    )
    con_nivel = tuple(
        rentabilidad.asignar_nivel(
            canal,
            insumos,
            descuento_real=avance.descuento_real,
            costo_compra=avance.costo_compra,
            confianza_ok=confianza_ok,
            configuracion=contexto.configuracion.contenido,
        )
        for canal, insumos in zip(avance.canales, avance.insumos_canales, strict=True)
    )
    return dataclasses.replace(avance, canales=con_nivel)


def calcular_unidades_y_rendimiento(contexto: ContextoEvaluacion, avance: Avance) -> Avance:
    """Unidades, días, rendimiento y ganancia total por canal (RN-005; CMP-14)."""
    if not _con_insumos(avance):
        return avance
    calculados = tuple(
        rentabilidad.calcular_unidades(
            canal,
            insumos,
            descuento_real=avance.descuento_real,
            configuracion=contexto.configuracion.contenido,
        )
        for canal, insumos in zip(avance.canales, avance.insumos_canales, strict=True)
    )
    return dataclasses.replace(avance, canales=calculados)


def elegir_canal(contexto: ContextoEvaluacion, avance: Avance) -> Avance:
    """Paso 9 (RN-018, S-33; CMP-15): canal elegido y nivel del aviso con su canal."""
    desempate = contexto.configuracion.contenido.levels.channel_tiebreak_pct
    elegida = eleccion.elegir(avance.canales, desempate)
    return dataclasses.replace(
        avance,
        canal_elegido=elegida.canal_elegido,
        nivel_aviso=elegida.nivel_aviso,
        canal_aviso=elegida.canal_aviso,
    )


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
