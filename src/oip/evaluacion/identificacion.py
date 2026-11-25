"""Paso 2 de REQ §3.2: identificar y clasificar riesgo (CMP-10).

T11 llena la **confianza de la disponibilidad** (RN-007 v2 §4.1 y §4.2; S-25). La
coincidencia (RN-013), el estado (RN-014, S-13), el vendedor y los riesgos (RN-015, S-21) y la
lista "evitar siempre" los agregan sus tareas (T19, T20). T20 agrega la **compra a particular**
(``PARTICULAR``, RN-014 §4) y el **riesgo de procedencia** (RN-015 §4, PAR-04 y PAR-05).

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

from oip.catalogos import Confianza, EstadoDisponibilidad, ModoCompra, Motivo, Vendedor
from oip.configuracion import Confianza as ParametrosConfianza
from oip.configuracion import Configuracion
from oip.entradas.contrato import Observacion

__all__ = [
    "antiguedad_horas",
    "confianza_disponibilidad",
    "confianza_permite_nivel",
    "es_compra_a_particular",
    "es_tienda_fisica",
    "motivos_de_particular",
    "riesgo_de_procedencia",
]

_MICROSEGUNDO = dt.timedelta(microseconds=1)
_MICROSEGUNDOS_POR_HORA = Decimal(3_600_000_000)
_EN_EXISTENCIA = (EstadoDisponibilidad.IN_STOCK, EstadoDisponibilidad.IN_STOCK_CONFIRMED)
_ALTA_O_MEDIA = (Confianza.ALTA, Confianza.MEDIA)


def _exigir_observacion(observacion: object) -> Observacion:
    if not isinstance(observacion, Observacion):
        raise TypeError("se esperaba una Observacion")
    return observacion


def antiguedad_horas(instante: dt.datetime, extraida_en: dt.datetime) -> Decimal:
    """Horas exactas de ``extraida_en`` a ``instante`` (``Decimal``, sin ``float``). Las dos
    fechas necesitan su desfase; un dato posterior al instante levanta ``ValueError``."""
    for nombre, valor in (("instante", instante), ("extraida_en", extraida_en)):
        if not isinstance(valor, dt.datetime):
            raise TypeError(f"{nombre} debe ser un datetime")
        if valor.utcoffset() is None:
            raise ValueError(f"{nombre} necesita su desfase: no se usa la zona de la máquina")
    edad = instante - extraida_en
    if edad < dt.timedelta(0):
        raise ValueError("el dato es posterior al instante de la evaluación")
    # timedelta.total_seconds() es float: se cuenta en microsegundos enteros.
    return Decimal(edad // _MICROSEGUNDO) / _MICROSEGUNDOS_POR_HORA


def es_tienda_fisica(observacion: Observacion) -> bool:
    """Compra en tienda física (``purchaseMode = tienda``; RN-007 §4.1)."""
    return _exigir_observacion(observacion).purchase_mode is ModoCompra.TIENDA


def _confianza_en_tienda(
    observacion: Observacion, edad: Decimal, parametros: ParametrosConfianza
) -> Confianza:
    """Tabla de RN-007 v2 §4.1 (tienda física); liquidación con sus ventanas (RN-007 §11: si
    no se sabe, las normales)."""
    ventanas = parametros.clearance if observacion.is_clearance is True else parametros.normal
    if edad > ventanas.max_age_hours:
        return Confianza.BAJA  # "cualquier dato" más viejo que el límite
    estado = observacion.availability.state
    if estado is EstadoDisponibilidad.LIMITED_STOCK:
        # "Pocas unidades" o "existencia limitada": igual en liquidación.
        if edad <= parametros.few_units_medium_max_hours:
            return Confianza.MEDIA
        return Confianza.BAJA
    if estado not in _EN_EXISTENCIA:
        return Confianza.BAJA  # agotado, no confirmada o un estado sin existencia
    if observacion.availability.quantity is not None:
        if edad <= ventanas.exact_high_max_hours:
            return Confianza.ALTA
        return Confianza.MEDIA  # hasta max_age_hours (ya comprobado)
    if edad <= ventanas.no_number_medium_max_hours:
        return Confianza.MEDIA
    return Confianza.BAJA


def confianza_disponibilidad(
    observacion: Observacion, instante: dt.datetime, parametros: ParametrosConfianza
) -> Confianza | None:
    """Confianza de la disponibilidad de la oferta al ``instante`` (RN-007 v2; S-25).

    ``None`` cuando la RN no da confianza: la publicación de un particular, un estado en
    línea distinto de "disponible confirmada" o un dato posterior al ``instante`` (sin
    antigüedad)."""
    observacion = _exigir_observacion(observacion)
    if not isinstance(parametros, ParametrosConfianza):
        raise TypeError("se esperaban los parámetros de confianza (levels.confidence)")
    if observacion.es_particular:
        return None
    if not isinstance(instante, dt.datetime) or instante.utcoffset() is None:
        raise TypeError("instante debe ser un datetime con desfase")
    if observacion.extracted_at > instante:
        # Un dato posterior al instante no tiene antigüedad: sin confianza (vacío = ausente).
        return None
    edad = antiguedad_horas(instante, observacion.extracted_at)
    if es_tienda_fisica(observacion):
        return _confianza_en_tienda(observacion, edad, parametros)
    # En línea y recoger en tienda (RN-007 §4.2): "disponible confirmada" cuenta como Alta
    # (S-25); los demás estados no cuentan como disponibles y la RN no les da confianza.
    if observacion.availability.state is EstadoDisponibilidad.IN_STOCK_CONFIRMED:
        return Confianza.ALTA
    return None


def confianza_permite_nivel(observacion: Observacion, confianza: Confianza | None) -> bool:
    """Requisito de confianza del nivel (RN-009 §4.2; REQ §3.2.1; S-25): en tienda física,
    Alta o Media; en las demás compras, siempre se cumple."""
    if confianza is not None and not isinstance(confianza, Confianza):
        raise TypeError("se esperaba una Confianza o None")
    if not es_tienda_fisica(observacion):
        return True
    return confianza in _ALTA_O_MEDIA


# --- Particular y riesgo de procedencia (RN-014 §4, RN-015; T20) --------------------------


def es_compra_a_particular(observacion: Observacion) -> bool:
    """Compra a un particular (REQ §6 punto 1; DEC-239): ``retailerCode``, ``seller`` y
    ``purchaseMode`` valen ``particular``."""
    observacion = _exigir_observacion(observacion)
    return (
        observacion.retailer_code.strip() == Vendedor.PARTICULAR.value
        and observacion.seller is Vendedor.PARTICULAR
        and observacion.purchase_mode is ModoCompra.PARTICULAR
    )


def riesgo_de_procedencia(observacion: Observacion, configuracion: Configuracion) -> bool:
    """Riesgo de procedencia (RN-015 §4; S-21): producto propenso a falsificación o robo
    (categoría con ``categories.<código>.provenance_risk``, marca de
    ``lists.provenance_risk_brands`` o producto de ``lists.provenance_risk_products``)
    comprado a un particular o a un vendedor externo."""
    # Import local: ``canales`` importa ``referencias``, que importa este módulo.
    from oip.evaluacion.canales._base import _es_el_producto, _marca_en

    observacion = _exigir_observacion(observacion)
    if not isinstance(configuracion, Configuracion):
        raise TypeError("se esperaba la Configuracion")
    if observacion.seller not in (Vendedor.PARTICULAR, Vendedor.EXTERNO):
        return False
    categoria = configuracion.categories.get(observacion.category)
    if categoria is not None and categoria.provenance_risk:
        return True
    listas = configuracion.lists
    return _marca_en(listas.provenance_risk_brands, observacion) or any(
        _es_el_producto(p, observacion) for p in listas.provenance_risk_products
    )


def motivos_de_particular(
    observacion: Observacion, configuracion: Configuracion
) -> tuple[Motivo, ...]:
    """Motivos de revisión manual de una compra a particular (REQ §3.2.3): ``PARTICULAR``
    (inspección física obligatoria, RN-014 §4) y, si aplica, ``RIESGO DE PROCEDENCIA``
    (RN-015), en el orden del catálogo. Vacío si la oferta no es de un particular."""
    if not es_compra_a_particular(observacion):
        return ()
    if riesgo_de_procedencia(observacion, configuracion):
        return (Motivo.PARTICULAR, Motivo.RIESGO_DE_PROCEDENCIA)
    return (Motivo.PARTICULAR,)
