"""Paso 3 de REQ §3.2: referencias de precio (CMP-11; RN-002 v2, RN-003 v2).

Este módulo calcula, por ahora, el **precio habitual** con su **episodio de liquidación**
(T09; REQ §3.2 paso 3, DEC-201, DEC-224 b, DEC-226; design.md §10 puntos 1 y 2). El precio
de mercado hoy, el mínimo de 60 días y la venta esperada en Amazon, el MSRP y el valor de
referencia de usados los agregan sus tareas.

Implementa la interfaz ``FuentePrecios`` (``PriceReferenceSource`` de la arquitectura §2.2,
ADR-007) con la fuente ``historial_propio``: cada referencia guarda la fuente que la dio.

Reglas (todas sus cifras salen de PAR-08, ``price_reference``; ninguna está en el código):

- **Día calendario** de una observación y **día evaluado** = el día de ``extractedAt`` y del
  ``instante`` en la zona de PAR-01 (``general.timezone``; DEC-234 5). Nunca la zona de la
  máquina.
- **Observación diaria** (DEC-201 1): de cada publicación y día cuenta solo la **última**
  observación del día.
- **Qué cuenta para el precio habitual del producto** (design.md §10.1): nuevo, vendido por
  el comercio, de todos los comercios seguidos, incluido el botón de compra de la ficha de
  Amazon (``amazonListing.buyBoxPrice``; DEC-234 3). Un estado desconocido de un comercio
  cuenta como nuevo (S-13). Una observación con ``blocked`` no trae precio y no cuenta.
- **Mediana** de las observaciones diarias de los ``usual_window_days`` días **anteriores**
  al día evaluado, **sin** ese día (DEC-224 b). Con un número par, el promedio de las dos
  centrales, **sin redondear** (DEC-226 b): el precio habitual no está en la lista cerrada
  de montos (DEC-207).
- **Historial suficiente**: al menos ``sufficient_history_observations`` observaciones
  diarias en ``sufficient_history_days`` días distintos dentro de la ventana; si no, no hay
  precio habitual.
- **Baja** (DEC-224 b, DEC-226 c): el precio diario de la publicación es menor que el de su
  día anterior o, si ese día no tiene observación, que el de su última observación anterior.
  La primera observación de la publicación no es baja.
- **Episodio de liquidación** por publicación (DEC-201, DEC-224, DEC-226 a; design.md
  §10.2), recalculado desde el historial en cada evaluación: una baja que queda bajo el
  precio habitual del producto de ese día abre el episodio y congela ese habitual (la
  mediana con que se habría evaluado ese día, no el precio del día anterior). El episodio
  termina cuando el precio vuelve al valor congelado o más, o cuando pasa de
  ``clearance_episode_max_days`` días (el día de la baja es el día 1). Después hace falta
  una baja nueva. Durante el episodio, la oferta de esa publicación se evalúa contra el
  valor congelado; la mediana del producto sigue incluyendo los días del episodio.

Puro (design.md §14): sin reloj, sin I/O, sin red y sin aleatoriedad; el resultado depende
solo del contexto.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from typing import Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from oip.catalogos import Condicion, Vendedor
from oip.configuracion import ReferenciaPrecio as ParametrosReferencia
from oip.entradas.contrato import Observacion
from oip.evaluacion.contexto import (
    ContextoEvaluacion,
    Episodio,
    ObservacionRegistrada,
    Referencias,
)

__all__ = [
    "FUENTE_HISTORIAL_PROPIO",
    "FuentePrecios",
    "HistorialPropio",
    "ObservacionDiaria",
    "PrecioHabitual",
    "calcular_referencias",
    "dia_calendario",
    "dia_evaluado",
    "episodio_vigente",
    "es_nuevo",
    "historial_suficiente",
    "mediana",
    "observaciones_diarias",
    "precio_habitual_del_producto",
    "serie_de_la_publicacion",
]

#: Fuente del precio habitual calculado con las observaciones de OIP (ADR-007, DEC-123).
FUENTE_HISTORIAL_PROPIO = "historial_propio"


@dataclasses.dataclass(frozen=True, slots=True)
class ObservacionDiaria:
    """La última observación de una publicación en un día calendario (DEC-201 1)."""

    id_publicacion: UUID
    dia: dt.date
    precio: Decimal
    id_observacion: UUID
    extraida_en: dt.datetime


@dataclasses.dataclass(frozen=True, slots=True)
class PrecioHabitual:
    """Precio habitual contra el que se evalúa la oferta, sin redondear.

    ``valor`` es el que aplica: el congelado si la publicación está en un episodio de
    liquidación, si no la mediana del producto. ``episodio`` trae su inicio y su valor
    congelado, o ``None``.
    """

    valor: Decimal
    fuente: str
    episodio: Episodio | None


class FuentePrecios(Protocol):
    """Interfaz de una fuente de referencias de precio (``PriceReferenceSource``, ADR-007).

    Cada fuente dice su nombre (``fuente``), que se guarda junto a cada referencia.
    """

    @property
    def fuente(self) -> str: ...

    def precio_habitual(self, contexto: ContextoEvaluacion) -> PrecioHabitual | None:
        """Precio habitual que aplica a la oferta del contexto, o ``None`` sin historial
        suficiente."""
        ...


# --- Día calendario ------------------------------------------------------------------------


def dia_calendario(momento: dt.datetime, zona: ZoneInfo) -> dt.date:
    """Día calendario de ``momento`` en la ``zona`` de PAR-01 (DEC-234 5)."""
    if momento.utcoffset() is None:
        raise ValueError("el momento necesita su desfase: no se usa la zona de la máquina")
    return momento.astimezone(zona).date()


def _zona(contexto: ContextoEvaluacion) -> ZoneInfo:
    return ZoneInfo(contexto.configuracion.contenido.general.timezone)


def _parametros(contexto: ContextoEvaluacion) -> ParametrosReferencia:
    return contexto.configuracion.contenido.price_reference


def dia_evaluado(contexto: ContextoEvaluacion) -> dt.date:
    """Día calendario del ``instante`` en la zona de PAR-01 (design.md §3)."""
    return dia_calendario(contexto.instante, _zona(contexto))


# --- Mediana e historial suficiente -------------------------------------------------------


def mediana(valores: Sequence[Decimal]) -> Decimal:
    """Mediana sin redondear (DEC-226 b): con número par, el promedio de las dos centrales.

    Una lista vacía levanta ``ValueError``; un valor que no es ``Decimal`` (un ``float``),
    ``TypeError``.
    """
    if not valores:
        raise ValueError("la mediana necesita al menos un valor")
    for valor in valores:
        if not isinstance(valor, Decimal) or not valor.is_finite():
            raise TypeError("la mediana solo admite Decimal finitos")
    ordenados = sorted(valores)
    medio = len(ordenados) // 2
    if len(ordenados) % 2:
        return ordenados[medio]
    return (ordenados[medio - 1] + ordenados[medio]) / 2


def historial_suficiente(
    diarias: Iterable[ObservacionDiaria], parametros: ParametrosReferencia
) -> bool:
    """Al menos N observaciones diarias en M días distintos (PAR-08; RN-002, S-22)."""
    lista = list(diarias)
    dias = {d.dia for d in lista}
    return (
        len(lista) >= parametros.sufficient_history_observations
        and len(dias) >= parametros.sufficient_history_days
    )


# --- Observaciones que cuentan ------------------------------------------------------------


def es_nuevo(observacion: Observacion) -> bool:
    """Producto nuevo: ``condition = new`` o, de un comercio, estado desconocido (S-13)."""
    if observacion.condition is None:
        return not observacion.es_particular
    return observacion.condition is Condicion.NEW


def _precio_de_referencia(observacion: Observacion) -> Decimal | None:
    """Precio que la observación aporta a las referencias: en la ficha de Amazon, el botón
    de compra (``None`` = sin oferta nueva hoy; DEC-234 3); en las demás, ``price.current``.
    Una observación bloqueada o con precio inválido no aporta precio."""
    if observacion.blocked:
        return None
    if observacion.amazon_listing is not None:
        return observacion.amazon_listing.buy_box_price
    if observacion.precio_invalido:
        return None
    return observacion.price.current


def _cuenta_para_el_habitual(observacion: Observacion) -> bool:
    """Nuevo y vendido por el comercio (design.md §10.1)."""
    return observacion.seller is Vendedor.COMERCIO and es_nuevo(observacion)


def _ultimas_del_dia(
    registradas: Iterable[ObservacionRegistrada], zona: ZoneInfo
) -> tuple[ObservacionDiaria, ...]:
    """La última observación de cada publicación y día; sin repetir una observación que
    llegue dos veces (por ejemplo, en el historial y en las fichas de Amazon)."""
    ultimas: dict[tuple[UUID, dt.date], ObservacionDiaria] = {}
    vistas: set[UUID] = set()
    for registrada in registradas:
        if registrada.id is None or registrada.id_publicacion is None:
            continue
        if registrada.id in vistas:
            continue
        vistas.add(registrada.id)
        precio = _precio_de_referencia(registrada.observacion)
        if precio is None:
            continue
        extraida = registrada.observacion.extracted_at
        diaria = ObservacionDiaria(
            id_publicacion=registrada.id_publicacion,
            dia=dia_calendario(extraida, zona),
            precio=precio,
            id_observacion=registrada.id,
            extraida_en=extraida,
        )
        clave = (diaria.id_publicacion, diaria.dia)
        anterior = ultimas.get(clave)
        # La última del día; con la misma hora, desempata el id (determinista).
        if anterior is None or (diaria.extraida_en, diaria.id_observacion) > (
            anterior.extraida_en,
            anterior.id_observacion,
        ):
            ultimas[clave] = diaria
    return tuple(sorted(ultimas.values(), key=lambda d: (d.dia, d.id_publicacion)))


def _guardadas(contexto: ContextoEvaluacion) -> tuple[ObservacionRegistrada, ...]:
    return (*contexto.historial, *contexto.fichas_amazon)


def observaciones_diarias(contexto: ContextoEvaluacion) -> tuple[ObservacionDiaria, ...]:
    """Observaciones diarias del producto que cuentan para su precio habitual (§10.1)."""
    que_cuentan = (r for r in _guardadas(contexto) if _cuenta_para_el_habitual(r.observacion))
    return _ultimas_del_dia(que_cuentan, _zona(contexto))


def precio_habitual_del_producto(
    diarias: Sequence[ObservacionDiaria], dia: dt.date, parametros: ParametrosReferencia
) -> Decimal | None:
    """Mediana con que se evalúa una oferta del ``dia``: observaciones diarias de los
    ``usual_window_days`` días anteriores, sin ese día (DEC-224 b). ``None`` sin historial
    suficiente."""
    desde = dia - dt.timedelta(days=parametros.usual_window_days)
    en_ventana = [d for d in diarias if desde <= d.dia < dia]
    if not historial_suficiente(en_ventana, parametros):
        return None
    return mediana([d.precio for d in en_ventana])


# --- Episodio de liquidación --------------------------------------------------------------


def serie_de_la_publicacion(contexto: ContextoEvaluacion) -> tuple[tuple[dt.date, Decimal], ...]:
    """Precio diario de la publicación de la oferta: la última observación de cada día
    anterior al día evaluado y, el día evaluado, el precio de la oferta.

    Vacía si la oferta no tiene publicación (no se guardó) o no tiene precio.
    """
    oferta = contexto.oferta
    precio_oferta = _precio_de_referencia(oferta.observacion)
    if oferta.id_publicacion is None or precio_oferta is None:
        return ()
    hoy = dia_evaluado(contexto)
    publicacion = oferta.id_publicacion
    de_la_publicacion = (r for r in _guardadas(contexto) if r.id_publicacion == publicacion)
    anteriores = [
        (d.dia, d.precio)
        for d in _ultimas_del_dia(de_la_publicacion, _zona(contexto))
        if d.dia < hoy
    ]
    return (*anteriores, (hoy, precio_oferta))


def episodio_vigente(
    serie: Sequence[tuple[dt.date, Decimal]],
    habitual_del_dia: Mapping[dt.date, Decimal | None],
    parametros: ParametrosReferencia,
) -> Episodio | None:
    """Episodio de liquidación vigente el último día de la ``serie`` (design.md §10.2).

    ``serie``: precio diario de la publicación en orden de día. ``habitual_del_dia``: el
    precio habitual del producto con que se habría evaluado cada día de la serie (``None``
    sin historial suficiente).
    """
    limite = parametros.clearance_episode_max_days
    episodio: Episodio | None = None
    anterior: Decimal | None = None
    for dia, precio in serie:
        if episodio is not None:
            dia_del_episodio = (dia - episodio.inicio).days + 1
            if precio >= episodio.valor_congelado or dia_del_episodio > limite:
                episodio = None
        if episodio is None and anterior is not None and precio < anterior:
            habitual = habitual_del_dia.get(dia)
            if habitual is not None and precio < habitual:
                episodio = Episodio(inicio=dia, valor_congelado=habitual)
        anterior = precio
    return episodio


# --- Fuente: historial propio -------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class HistorialPropio:
    """``FuentePrecios`` con las observaciones de OIP (fuente ``historial_propio``)."""

    @property
    def fuente(self) -> str:
        return FUENTE_HISTORIAL_PROPIO

    def precio_habitual(self, contexto: ContextoEvaluacion) -> PrecioHabitual | None:
        parametros = _parametros(contexto)
        diarias = observaciones_diarias(contexto)
        serie = serie_de_la_publicacion(contexto)
        habitual_del_dia = {
            dia: precio_habitual_del_producto(diarias, dia, parametros) for dia, _ in serie
        }
        episodio = episodio_vigente(serie, habitual_del_dia, parametros)
        if episodio is not None:
            return PrecioHabitual(episodio.valor_congelado, self.fuente, episodio)
        normal = precio_habitual_del_producto(diarias, dia_evaluado(contexto), parametros)
        if normal is None:
            return None
        return PrecioHabitual(normal, self.fuente, None)


def calcular_referencias(
    contexto: ContextoEvaluacion, fuente: FuentePrecios | None = None
) -> Referencias:
    """Referencias de precio de la oferta (TAB-10 ``references``). Hoy: el precio habitual
    con su fuente y, si lo hay, su episodio. Sin historial suficiente, sin precio habitual
    ni fuente (vacío = ausente)."""
    fuente = HistorialPropio() if fuente is None else fuente
    habitual = fuente.precio_habitual(contexto)
    if habitual is None:
        return Referencias()
    return Referencias(
        precio_habitual=habitual.valor,
        fuente_precio_habitual=habitual.fuente,
        episodio=habitual.episodio,
    )
