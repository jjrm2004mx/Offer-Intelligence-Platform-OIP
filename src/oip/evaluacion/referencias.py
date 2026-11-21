"""Paso 3 de REQ §3.2: referencias de precio (CMP-11; RN-002 v2, RN-003 v2).

Este módulo calcula el **precio habitual** con su **episodio de liquidación** (T09; REQ §3.2
paso 3, DEC-201, DEC-224 b, DEC-226; design.md §10 puntos 1 y 2) y, desde T10, el **precio
de mercado hoy** básico, el **MSRP** (solo se muestra), el **precio típico de la tienda**
(RN-003) y los datos que usa la calidad del precio (RN-012): las cadenas del mercado hoy, el
mínimo registrado y los días de historial. Desde T11, el **mínimo de 60 días en Amazon** y el
**precio de venta esperado en Amazon** con la oferta nueva hoy. El precio habitual en Amazon
sin oferta hoy (S-02), la regla de comercio = cadena en el mercado hoy (con su excepción en
liquidación) y el valor de referencia de usados los agregan sus tareas (T16, T20).

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
- **Precio típico de la tienda** (RN-003 §4; design.md §10.1): lo mismo que el precio
  habitual del producto (mediana, sin el día evaluado, con historial suficiente), pero solo
  con las publicaciones de la cadena de la oferta (PAR-02, ``retailers.<código>.chain``) y
  en la ventana ``store_typical_window_days``.
- **Precio de mercado hoy** (RN-002 v2 §4.1, S-03; design.md §10.4; DEC-261): de cada
  publicación del producto, sin la de la oferta evaluada, se toma **primero** la observación
  más reciente con antigüedad (``instante − extractedAt``) de ``market_today_max_age_hours``
  horas o menos y **después** se exige que sea nueva, vendida por el comercio y disponible:
  si la más reciente no cumple (un agotado reciente, un usado, un vendedor externo, una ficha
  sin botón de compra), la publicación no da precio aunque una anterior sí cumpliera. Una
  consulta bloqueada o con precio inválido no es una observación (REQ §3.1 punto 5) y no
  cuenta como la más reciente. El precio de mercado hoy es el más bajo de las publicaciones
  que quedan. El mismo cálculo da la competencia más barata (RN-002 §4.3, que lo recibe en
  ``Referencias.precio_mercado_hoy``) y la reevaluación. "Disponible" (S-03): en línea,
  ``in_stock_confirmed``; en tienda física, confianza Alta o Media de RN-007 §4.1 al
  instante; en la ficha de Amazon, un botón de compra (``buyBoxPrice``) no nulo (design.md
  §10.3). La exclusión de la misma cadena y su excepción en liquidación en sucursal son de
  T16 (DEC-216).
- **Cadenas del mercado hoy** (RN-012 §4, "comercios"): las cadenas distintas de la evaluada
  entre las publicaciones que dan el precio de mercado hoy (design.md §10.4).
- **Mínimo registrado** (S-22): el precio diario más bajo del producto en todos los
  comercios seguidos, sin la oferta evaluada. **Días de historial**: del primer día con
  observación del producto al día evaluado.
- **MSRP** (DEC-218): solo se muestra; no entra en ningún cálculo. Es el de la captura
  ``msrp`` más reciente del contexto o, sin captura, el que trae la observación de la oferta.

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

from oip.catalogos import Condicion, Confianza, EstadoDisponibilidad, ModoCompra, Vendedor
from oip.configuracion import ReferenciaPrecio as ParametrosReferencia
from oip.entradas.contrato import Observacion
from oip.evaluacion.contexto import (
    ContextoEvaluacion,
    Episodio,
    ObservacionRegistrada,
    Referencias,
)
from oip.evaluacion.identificacion import confianza_disponibilidad

__all__ = [
    "FUENTE_HISTORIAL_PROPIO",
    "FuentePrecios",
    "HistorialPropio",
    "MercadoHoy",
    "ObservacionDiaria",
    "PrecioHabitual",
    "cadena_de",
    "calcular_referencias",
    "dia_calendario",
    "dia_evaluado",
    "dias_de_historial",
    "disponible_para_mercado_hoy",
    "episodio_vigente",
    "es_nuevo",
    "historial_suficiente",
    "mediana",
    "mercado_hoy",
    "minimo_60_dias_amazon",
    "minimo_registrado",
    "msrp",
    "observaciones_diarias",
    "precio_habitual_del_producto",
    "precio_tipico_de_la_tienda",
    "precio_venta_amazon",
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


# --- Cadena (PAR-02) -----------------------------------------------------------------------


def cadena_de(codigo_comercio: str, contexto: ContextoEvaluacion) -> str:
    """Cadena del comercio (PAR-02, ``retailers.<código>.chain``; DEC-216). Un código que no
    está en la configuración es su propia cadena: no se junta con ninguna otra."""
    comercio = contexto.configuracion.contenido.retailers.get(codigo_comercio)
    return codigo_comercio if comercio is None else comercio.chain


# --- Precio típico de la tienda (RN-003) --------------------------------------------------


def precio_tipico_de_la_tienda(contexto: ContextoEvaluacion) -> Decimal | None:
    """Precio típico de la cadena de la oferta (RN-003 §4; design.md §10.1): la mediana de las
    observaciones diarias de sus publicaciones en los ``store_typical_window_days`` días
    anteriores al día evaluado, sin ese día. ``None`` sin historial suficiente de esa tienda
    (PAR-08)."""
    parametros = _parametros(contexto)
    cadena = cadena_de(contexto.oferta.observacion.retailer_code, contexto)
    de_la_cadena = (
        r
        for r in _guardadas(contexto)
        if _cuenta_para_el_habitual(r.observacion)
        and cadena_de(r.observacion.retailer_code, contexto) == cadena
    )
    diarias = _ultimas_del_dia(de_la_cadena, _zona(contexto))
    hoy = dia_evaluado(contexto)
    desde = hoy - dt.timedelta(days=parametros.store_typical_window_days)
    en_ventana = [d for d in diarias if desde <= d.dia < hoy]
    if not historial_suficiente(en_ventana, parametros):
        return None
    return mediana([d.precio for d in en_ventana])


# --- Precio de mercado hoy (RN-002 §4.1, S-03) ------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class MercadoHoy:
    """Precio de mercado hoy (el más bajo, sin redondear) y las cadenas distintas de la
    evaluada que dan datos de hoy (RN-012 §4, mínimo de comercios; design.md §10.4)."""

    precio: Decimal
    otras_cadenas: frozenset[str]


def disponible_para_mercado_hoy(observacion: Observacion, contexto: ContextoEvaluacion) -> bool:
    """Qué es "disponible" para el precio de mercado hoy (S-03; design.md §10.3 y §10.4).

    Ficha de Amazon: botón de compra no nulo (oferta nueva hoy). Tienda física
    (``purchaseMode = tienda``): confianza Alta o Media al ``instante`` (RN-007 §4.1). En
    línea y recoger en tienda (RN-007 §4.2, se trata como compra en línea): disponible
    confirmada (``in_stock_confirmed``).
    """
    if observacion.amazon_listing is not None:
        return observacion.amazon_listing.buy_box_price is not None
    if observacion.purchase_mode is ModoCompra.TIENDA:
        # La confianza de RN-007 §4.1 es la de CMP-10 (T11), con las ventanas de PAR-13.
        parametros = contexto.configuracion.contenido.levels.confidence
        confianza = confianza_disponibilidad(observacion, contexto.instante, parametros)
        return confianza in (Confianza.ALTA, Confianza.MEDIA)
    return observacion.availability.state is EstadoDisponibilidad.IN_STOCK_CONFIRMED


def _cuenta_para_el_mercado_hoy(
    registrada: ObservacionRegistrada, contexto: ContextoEvaluacion, limite: dt.timedelta
) -> bool:
    observacion = registrada.observacion
    edad = contexto.instante - observacion.extracted_at
    return (
        dt.timedelta(0) <= edad <= limite
        and _precio_de_referencia(observacion) is not None
        and _cuenta_para_el_habitual(observacion)
        and disponible_para_mercado_hoy(observacion, contexto)
    )


def mercado_hoy(contexto: ContextoEvaluacion) -> MercadoHoy | None:
    """Precio de mercado hoy básico (RN-002 v2 §4.1; design.md §10.4; DEC-261) y sus cadenas.

    De cada publicación del producto, sin la publicación de la oferta evaluada, se toma
    primero la observación más reciente con antigüedad de ``market_today_max_age_hours`` o
    menos (de 0 a ese límite, incluido; con el mismo ``extractedAt``, desempata el id) y
    después se exige que sea nueva, vendida por el comercio y disponible (S-03). Si no
    cumple, la publicación sale: una observación anterior no la sustituye. Las consultas
    bloqueadas y las de precio inválido no son observaciones y no entran en la elección. El
    precio es el más bajo de las publicaciones que quedan, sin redondear. ``None`` si
    ninguna publicación tiene un dato así (RN-002 §11: no hay precio de mercado hoy).
    """
    oferta = contexto.oferta
    limite = dt.timedelta(hours=_parametros(contexto).market_today_max_age_hours)
    mas_recientes: dict[UUID, ObservacionRegistrada] = {}
    for registrada in _guardadas(contexto):
        if registrada.id_publicacion is None or registrada.id is None:
            continue
        if registrada.id_publicacion == oferta.id_publicacion or registrada.id == oferta.id:
            continue
        if not _cuenta_para_el_mercado_hoy(registrada, contexto, limite):
            continue
        anterior = mas_recientes.get(registrada.id_publicacion)
        clave = (registrada.observacion.extracted_at, registrada.id)
        if anterior is None or clave > (anterior.observacion.extracted_at, anterior.id):
            mas_recientes[registrada.id_publicacion] = registrada
    if not mas_recientes:
        return None
    # Cada una tiene precio: lo exige _cuenta_para_el_mercado_hoy.
    precios = [
        p for r in mas_recientes.values() if (p := _precio_de_referencia(r.observacion)) is not None
    ]
    evaluada = cadena_de(oferta.observacion.retailer_code, contexto)
    cadenas = {cadena_de(r.observacion.retailer_code, contexto) for r in mas_recientes.values()}
    return MercadoHoy(precio=min(precios), otras_cadenas=frozenset(cadenas - {evaluada}))


# --- Datos de la calidad del precio (RN-012, S-22) ---------------------------------------


def _diarias_sin_la_oferta(contexto: ContextoEvaluacion) -> tuple[ObservacionDiaria, ...]:
    oferta = contexto.oferta.id
    que_cuentan = (
        r
        for r in _guardadas(contexto)
        if r.id != oferta and _cuenta_para_el_habitual(r.observacion)
    )
    return _ultimas_del_dia(que_cuentan, _zona(contexto))


def minimo_registrado(contexto: ContextoEvaluacion) -> Decimal | None:
    """Mínimo registrado (S-22): el precio diario más bajo del producto en todos los
    comercios seguidos (nuevo, vendido por el comercio), sin la oferta evaluada. ``None``
    sin observaciones."""
    diarias = _diarias_sin_la_oferta(contexto)
    return min((d.precio for d in diarias), default=None)


def dias_de_historial(contexto: ContextoEvaluacion) -> int:
    """Días de historial del producto (RN-012 §4, Oferta excepcional): del primer día con
    observación diaria al día evaluado. 0 sin observaciones."""
    diarias = _diarias_sin_la_oferta(contexto)
    if not diarias:
        return 0
    return (dia_evaluado(contexto) - min(d.dia for d in diarias)).days


# --- MSRP (solo se muestra) ------------------------------------------------------------


def msrp(contexto: ContextoEvaluacion) -> Decimal | None:
    """MSRP que se muestra (DEC-218; EXT-041): el de la captura ``msrp`` más reciente del
    contexto (por ``date``; con la misma fecha, la última del contexto) o, sin captura, el de
    la observación de la oferta. No entra en ningún cálculo."""
    if contexto.msrp:
        ultima = max(enumerate(contexto.msrp), key=lambda par: (par[1].date, par[0]))[1]
        return ultima.value
    propio = contexto.oferta.observacion.msrp
    return None if propio is None else propio.value


# --- Amazon: mínimo de 60 días y precio de venta esperado (T11) ---------------------------


def minimo_60_dias_amazon(contexto: ContextoEvaluacion) -> Decimal | None:
    """Mínimo de 60 días en Amazon (RN-002 v2; S-01): el precio diario más bajo del botón de
    compra (``buyBoxPrice``) de las fichas de Amazon en los ``amazon_min_window_days`` días que
    terminan el día evaluado, **incluido** (una ficha de hoy lo puede bajar, B2 b y B9 b). Sin
    redondear; ``None`` sin observaciones del botón de compra en la ventana."""
    hoy = dia_evaluado(contexto)
    desde = hoy - dt.timedelta(days=_parametros(contexto).amazon_min_window_days - 1)
    diarias = _ultimas_del_dia(_fichas_amazon(contexto), _zona(contexto))
    return min((d.precio for d in diarias if desde <= d.dia <= hoy), default=None)


def _fichas_amazon(contexto: ContextoEvaluacion) -> tuple[ObservacionRegistrada, ...]:
    """Observaciones de la ficha de Amazon del contexto (``amazonListing`` no nulo) hasta el
    instante. ``_ultimas_del_dia`` quita las repetidas."""
    return tuple(
        r
        for r in _guardadas(contexto)
        if r.observacion.amazon_listing is not None
        and r.observacion.extracted_at <= contexto.instante
    )


def precio_venta_amazon(contexto: ContextoEvaluacion) -> Decimal | None:
    """Precio de venta esperado en Amazon (REQ §3.2 paso 3; design.md §10.3): el botón de
    compra de la "oferta nueva hoy", la ficha más reciente con antigüedad de
    ``market_today_max_age_hours`` o menos y ``buyBoxPrice`` no nulo. Sin oferta nueva hoy,
    ``None``: el precio habitual en Amazon (S-02) y ``SIN OFERTA HOY`` los agrega T16."""
    limite = dt.timedelta(hours=_parametros(contexto).market_today_max_age_hours)
    con_oferta = [
        r
        for r in _fichas_amazon(contexto)
        if contexto.instante - r.observacion.extracted_at <= limite
        and _precio_de_referencia(r.observacion) is not None
    ]
    if not con_oferta:
        return None
    mas_reciente = max(con_oferta, key=lambda r: (r.observacion.extracted_at, str(r.id)))
    return _precio_de_referencia(mas_reciente.observacion)


def calcular_referencias(
    contexto: ContextoEvaluacion, fuente: FuentePrecios | None = None
) -> Referencias:
    """Referencias de precio de la oferta (TAB-10 ``references``): el precio habitual con su
    fuente y, si lo hay, su episodio; el precio de mercado hoy, el MSRP (solo se muestra), el
    mínimo de 60 días y el precio de venta esperado en Amazon.
    Una referencia que no se puede calcular queda en ``None`` (vacío = ausente)."""
    fuente = HistorialPropio() if fuente is None else fuente
    habitual = fuente.precio_habitual(contexto)
    hoy = mercado_hoy(contexto)
    return Referencias(
        precio_habitual=None if habitual is None else habitual.valor,
        fuente_precio_habitual=None if habitual is None else habitual.fuente,
        episodio=None if habitual is None else habitual.episodio,
        precio_mercado_hoy=None if hoy is None else hoy.precio,
        msrp=msrp(contexto),
        minimo_60_dias_amazon=minimo_60_dias_amazon(contexto),
        precio_venta_amazon=precio_venta_amazon(contexto),
    )
