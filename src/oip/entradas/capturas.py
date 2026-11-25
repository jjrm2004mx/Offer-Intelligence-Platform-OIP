"""Capturas de Jesús que no son observaciones (CMP-06, CTR-04; REQ §6, familia 2).

Siete esquemas, uno por ``recordType``, con los nombres y tipos de design.md CTR-04 y los
obligatorios de REQ §6. Campos en camelCase en el archivo, códigos en inglés y snake_case
(DEC-199). Reglas comunes:

- Cada obligatorio faltante (o con un valor no válido) da ``CAMPO OBLIGATORIO FALTANTE
  (<campo>)`` con el nombre del campo en el archivo, el primero en el orden de los
  obligatorios de CTR-04 (design.md §6; DEC-234). El **producto** es ``gtin``, o ``brand``
  y ``model``: si falta, se cita ``gtin`` cuando no hay ninguno de los dos, si no el que falte.
- Los campos desconocidos se descartan sin guardarlos (R-20). ``recordType`` no es parte
  de ningún esquema: lo quita el cargador (DEC-227 a).
- ``client_request`` **no tiene campo de notas** ni texto libre (RNF-11, DEC-231), y su
  alias nunca sale en el ``repr`` del modelo ni en un mensaje de error. ``acceptedConditions``
  es opcional: ausente o vacío vale ``[new]`` (RN-011 punto 2; DEC-241).
- Enteros y booleanos estrictos (DEC-238): el texto de un CSV lo convierte el cargador (T08).
- Una fecha y hora sin desfase (``visitedAt``) se toma en la zona que se pasa en ``zona``:
  la de ``general.timezone`` (PAR-01, ``America/Tijuana``; DEC-240). Sin ``zona``, se
  rechaza como campo faltante.
- Rangos de CTR-04 (DEC-257): ``units`` ≥ 1, ``actualCosts`` ≥ 0 con 2 decimales como
  máximo, ``soldOn`` ≥ ``purchasedOn`` y ninguna fecha (``date``, ``visitedAt``,
  ``purchasedOn``, ``soldOn``) posterior a ``dia_de_carga`` (el día de la carga en la zona de
  ``general.timezone``, que llega como dato): si no, ``CAMPO OBLIGATORIO FALTANTE
  (<campo>)``. Los cinco precios (``askingPrice``, ``local_estimate.price``, ``msrp.value``,
  ``purchasePrice`` y ``salePrice``) > 0 con 2 decimales como máximo: si no, la captura queda
  marcada (``precio_invalido``) y ``motivo_de_rechazo`` da ``PRECIO INVÁLIDO``, después de
  los campos faltantes (orden de design.md §6), como ``price.current`` en la observación.

No se valida contra la configuración (ciudades de PAR-09: CMP-07 y CMP-08) ni se guarda
nada (CMP-20).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Any, ClassVar
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import AfterValidator, BeforeValidator, Field, ValidationInfo

from oip.catalogos import Canal, Categoria, Condicion, DemandaLocal, MotivoRechazo, TipoRegistro
from oip.entradas._comun import (
    CONTEXTO_DIA_DE_CARGA,
    CONTEXTO_ZONA,
    Booleano,
    Dec,
    Entero,
    Esquema,
    FechaHoraCaptura,
    Monto,
    RegistroInvalido,
    ausente,
    decimal_o_none,
    faltantes_de_producto,
    mas_de_2_decimales,
    validar_esquema,
)

__all__ = [
    "CONDICIONES_POR_DEFECTO",
    "ESQUEMAS_CAPTURA",
    "Captura",
    "CapturaMsrp",
    "ComparableLocal",
    "DemandaLocalCapturada",
    "EstimadoLocal",
    "Modalidad",
    "Moneda",
    "RegistroInvalido",
    "ResultadoReal",
    "ResultadoVisita",
    "SolicitudCliente",
    "VisitaTienda",
    "leer_captura",
    "motivo_de_rechazo",
]

_PRODUCTO = ("gtin", "brand", "model")
#: Obligatorios que dependen de otros campos: los decide ``_faltan`` de cada esquema.
_CONDICIONALES = frozenset({*_PRODUCTO, "exchangeRate", "evaluationId"})

#: ``acceptedConditions`` de una solicitud que no los trae: solo nuevo (RN-011 punto 2,
#: REQ §3.4 punto 1, CTR-04; DEC-241).
CONDICIONES_POR_DEFECTO: tuple[Condicion, ...] = (Condicion.NEW,)


def _dia_de_carga(info: ValidationInfo) -> dt.date | None:
    contexto = info.context if isinstance(info.context, Mapping) else {}
    dia = contexto.get(CONTEXTO_DIA_DE_CARGA)
    return dia if isinstance(dia, dt.date) and not isinstance(dia, dt.datetime) else None


def _fecha_no_posterior(valor: dt.date, info: ValidationInfo) -> dt.date:
    """DEC-257: una fecha de captura no puede ser posterior al día de la carga."""
    dia = _dia_de_carga(info)
    if dia is not None and valor > dia:
        raise ValueError("la fecha es posterior al día de la carga")
    return valor


def _fecha_hora_no_posterior(valor: dt.datetime, info: ValidationInfo) -> dt.datetime:
    """DEC-257: el día de una fecha y hora es el de la zona de ``general.timezone``
    (la del contexto); sin zona, el de su propio desfase."""
    dia = _dia_de_carga(info)
    if dia is None:
        return valor
    contexto = info.context if isinstance(info.context, Mapping) else {}
    zona = contexto.get(CONTEXTO_ZONA)
    try:
        local = valor.astimezone(zona) if isinstance(zona, dt.tzinfo) else valor
    except OverflowError:
        # Fuera del rango de fechas en la zona de la carga: no es un valor válido del campo
        # (CAMPO OBLIGATORIO FALTANTE, design.md §6); no detiene la carga (lectura de T08b).
        raise ValueError("la fecha y hora no cabe en la zona de la carga") from None
    if local.date() > dia:
        raise ValueError("la fecha es posterior al día de la carga")
    return valor


FechaCaptura = Annotated[dt.date, AfterValidator(_fecha_no_posterior)]
"""Fecha de una captura: no posterior al día de la carga, si se da (DEC-257)."""

FechaHoraDeCaptura = Annotated[FechaHoraCaptura, AfterValidator(_fecha_hora_no_posterior)]
"""Fecha y hora de una captura (DEC-240): su día no es posterior al de la carga (DEC-257)."""


def _precio_invalido(precio: Decimal | None) -> bool:
    """DEC-257: un precio de captura ≤ 0, con más de 2 decimales o que no es un número."""
    return precio is None or precio <= 0 or mas_de_2_decimales(precio)


class Moneda(StrEnum):
    """``currency`` de un comparable local (S-23)."""

    USD = "USD"
    MXN = "MXN"


class ResultadoVisita(StrEnum):
    """``result`` de ``store_visit``."""

    FOUND = "found"
    NOT_FOUND = "not_found"
    DIFFERENT_PRICE = "different_price"
    CONFIRMED_BY_CALL = "confirmed_by_call"


class Modalidad(StrEnum):
    """``modality`` de ``client_request``."""

    LINK_ONLY = "link_only"
    BUY_AND_DELIVER = "buy_and_deliver"


class _Captura(Esquema):
    #: Orden de los obligatorios en el archivo (CTR-04).
    ORDEN: ClassVar[tuple[str, ...]] = ()
    #: Atributos con los precios que dan ``PRECIO INVÁLIDO`` (DEC-257), en orden de CTR-04.
    PRECIOS: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def _faltan(cls, datos: Mapping[str, Any]) -> list[str]:
        """Obligatorios que dependen de otros campos (producto, tipo de cambio)."""
        return []

    @property
    def precio_invalido(self) -> bool:
        """Algún precio de la captura es ≤ 0 o tiene más de 2 decimales: ``PRECIO INVÁLIDO``
        (DEC-257). Las capturas sin precio nunca lo son."""
        return any(_precio_invalido(getattr(self, nombre)) for nombre in self.PRECIOS)

    @classmethod
    def leer(
        cls,
        datos: Mapping[str, Any],
        zona: dt.tzinfo | None = None,
        dia_de_carga: dt.date | None = None,
    ) -> _Captura:
        if not isinstance(datos, Mapping):
            raise TypeError("la captura debe ser un mapa de campos")
        if dia_de_carga is not None and (
            not isinstance(dia_de_carga, dt.date) or isinstance(dia_de_carga, dt.datetime)
        ):
            raise TypeError("dia_de_carga: se esperaba una fecha (datetime.date)")
        orden = cls._orden()
        obligatorios = tuple(c for c in orden if c not in _CONDICIONALES)
        return validar_esquema(
            cls,
            datos,
            orden,
            obligatorios,
            faltan=cls._faltan(datos),
            contexto={CONTEXTO_ZONA: zona, CONTEXTO_DIA_DE_CARGA: dia_de_carga},
        )

    @classmethod
    def _orden(cls) -> tuple[str, ...]:
        return cls.ORDEN


class _ConProducto(_Captura):
    """Captura con producto: ``gtin``, o ``brand`` y ``model``."""

    gtin: str | None = None
    brand: str | None = None
    model: str | None = None

    @classmethod
    def _faltan(cls, datos: Mapping[str, Any]) -> list[str]:
        return faltantes_de_producto(datos)

    @classmethod
    def _orden(cls) -> tuple[str, ...]:
        return _PRODUCTO + cls.ORDEN


class ComparableLocal(_ConProducto):
    """``local_comparable`` (RN-014, RN-016). ``price_usd`` = ``askingPrice ÷ exchangeRate``
    en MXN, **sin redondear** (S-23, DEC-226 b); en USD, el mismo ``askingPrice``."""

    ORDEN: ClassVar[tuple[str, ...]] = (
        "condition",
        "askingPrice",
        "currency",
        "exchangeRate",
        "city",
        "date",
        "sold",
    )
    PRECIOS: ClassVar[tuple[str, ...]] = ("asking_price",)

    condition: Condicion
    asking_price: Annotated[Decimal | None, BeforeValidator(decimal_o_none)]
    currency: Moneda
    exchange_rate: Annotated[Dec, Field(gt=0)] | None = None
    city: str
    date: FechaCaptura
    sold: Booleano

    @classmethod
    def _faltan(cls, datos: Mapping[str, Any]) -> list[str]:
        faltan = faltantes_de_producto(datos)
        moneda = datos.get("currency")
        if isinstance(moneda, str) and moneda.strip() == Moneda.MXN:
            if ausente(datos.get("exchangeRate")):
                faltan.append("exchangeRate")
        return faltan

    @property
    def precio_invalido(self) -> bool:
        """``askingPrice`` no es un número, es ≤ 0 o tiene más de 2 decimales: ``PRECIO
        INVÁLIDO`` (design.md CTR-04; DEC-257)."""
        return _precio_invalido(self.asking_price)

    @property
    def price_usd(self) -> Decimal | None:
        """Precio en USD sin redondear; ``None`` si el precio es inválido."""
        precio = self.asking_price
        if precio is None or _precio_invalido(precio):
            return None
        if self.currency is Moneda.MXN and self.exchange_rate is not None:
            return precio / self.exchange_rate
        return precio


class EstimadoLocal(_ConProducto):
    """``local_estimate`` (RN-016). Sin ``condition`` vale para cualquier estado del
    producto; con ``condition``, solo para ese (DEC-234 punto 9)."""

    ORDEN: ClassVar[tuple[str, ...]] = ("price", "date")
    PRECIOS: ClassVar[tuple[str, ...]] = ("price",)

    condition: Condicion | None = None
    price: Dec
    date: FechaCaptura


class CapturaMsrp(_ConProducto):
    """``msrp``: solo se muestra (DEC-218)."""

    ORDEN: ClassVar[tuple[str, ...]] = ("value", "source", "date")
    PRECIOS: ClassVar[tuple[str, ...]] = ("value",)

    value: Dec
    source: str
    date: FechaCaptura


class DemandaLocalCapturada(_Captura):
    """``local_demand`` (RN-017): vale la más reciente por categoría."""

    ORDEN: ClassVar[tuple[str, ...]] = ("category", "level", "date")

    category: Categoria
    level: DemandaLocal
    date: FechaCaptura


class VisitaTienda(_Captura):
    """``store_visit`` (RN-007): tienda, producto u oportunidad, resultado y fecha y hora.

    Sin producto ni ``evaluationId`` se cita el producto (``gtin``, o el que falte de
    ``brand`` y ``model``)."""

    ORDEN: ClassVar[tuple[str, ...]] = (
        "storeCode",
        "gtin",
        "brand",
        "model",
        "evaluationId",
        "result",
        "visitedAt",
    )

    store_code: str
    gtin: str | None = None
    brand: str | None = None
    model: str | None = None
    evaluation_id: UUID | None = None
    result: ResultadoVisita
    visited_at: FechaHoraDeCaptura

    @classmethod
    def _faltan(cls, datos: Mapping[str, Any]) -> list[str]:
        if not ausente(datos.get("evaluationId")):
            return []
        return faltantes_de_producto(datos)


class ResultadoReal(_Captura):
    """``actual_result``: se guarda en ``opportunity_outcome`` y lo usa la parte C."""

    ORDEN: ClassVar[tuple[str, ...]] = (
        "evaluationId",
        "channel",
        "units",
        "purchasePrice",
        "salePrice",
        "actualCosts",
        "purchasedOn",
        "soldOn",
    )
    PRECIOS: ClassVar[tuple[str, ...]] = ("purchase_price", "sale_price")

    evaluation_id: UUID
    channel: Canal
    units: Annotated[Entero, Field(ge=1)]
    purchase_price: Dec
    sale_price: Dec
    actual_costs: Annotated[Monto, Field(ge=0)]
    purchased_on: FechaCaptura
    sold_on: FechaCaptura

    @classmethod
    def _faltan(cls, datos: Mapping[str, Any]) -> list[str]:
        """DEC-257: ``soldOn`` ≥ ``purchasedOn``; si no, ``soldOn`` no es válido."""
        compra, venta = _fecha_o_none(datos.get("purchasedOn")), _fecha_o_none(datos.get("soldOn"))
        if compra is not None and venta is not None and venta < compra:
            return ["soldOn"]
        return []


def _condiciones_o_por_defecto(valor: object) -> object:
    """``acceptedConditions`` ``null`` o lista vacía → ``[new]`` (DEC-241)."""
    if valor is None or (isinstance(valor, list | tuple) and not valor):
        return CONDICIONES_POR_DEFECTO
    return valor


class SolicitudCliente(_Captura):
    """``client_request`` (RN-011): el cliente solo por alias, **sin notas** (RNF-11).

    ``acceptedConditions`` es opcional: ausente, ``null`` o vacío vale ``[new]`` (RN-011
    punto 2; DEC-241); un código fuera de la tabla cuenta como faltante."""

    ORDEN: ClassVar[tuple[str, ...]] = (
        "clientAlias",
        "items",
        "quantity",
        "modality",
        "date",
    )

    client_alias: str = Field(repr=False)
    items: Annotated[
        tuple[Annotated[str, Field(min_length=1)], ...], Field(min_length=1, max_length=3)
    ]
    quantity: Annotated[Entero, Field(ge=1)]
    accepted_conditions: Annotated[
        tuple[Condicion, ...], BeforeValidator(_condiciones_o_por_defecto), Field(min_length=1)
    ] = CONDICIONES_POR_DEFECTO
    modality: Modalidad
    postal_code: str | None = None
    date: FechaCaptura


Captura = (
    ComparableLocal
    | EstimadoLocal
    | CapturaMsrp
    | DemandaLocalCapturada
    | VisitaTienda
    | ResultadoReal
    | SolicitudCliente
)

#: Esquema de cada ``recordType`` que no es una observación.
ESQUEMAS_CAPTURA: MappingProxyType[TipoRegistro, type[_Captura]] = MappingProxyType(
    {
        TipoRegistro.LOCAL_COMPARABLE: ComparableLocal,
        TipoRegistro.LOCAL_ESTIMATE: EstimadoLocal,
        TipoRegistro.MSRP: CapturaMsrp,
        TipoRegistro.LOCAL_DEMAND: DemandaLocalCapturada,
        TipoRegistro.STORE_VISIT: VisitaTienda,
        TipoRegistro.ACTUAL_RESULT: ResultadoReal,
        TipoRegistro.CLIENT_REQUEST: SolicitudCliente,
    }
)


def leer_captura(
    tipo: str,
    datos: Mapping[str, Any],
    *,
    zona: str | dt.tzinfo | None = None,
    dia_de_carga: dt.date | None = None,
) -> Captura:
    """Lee una captura de ``tipo`` (``recordType`` ya quitado del registro).

    Un tipo que no es una de las 7 capturas levanta ``RegistroInvalido`` con ``TIPO DE
    REGISTRO DESCONOCIDO``; ``observation`` se lee con ``contrato.leer_observacion``.

    ``zona`` es la de ``general.timezone`` de la configuración (PAR-01; nombre IANA o
    ``tzinfo``): una fecha y hora sin desfase se toma en ella (DEC-240). El cargador (T08)
    la pasa siempre; sin ella, una fecha y hora sin desfase se rechaza.

    ``dia_de_carga`` es el día de la carga en esa zona (DEC-257): una fecha de la captura
    (``date``, ``visitedAt``, ``purchasedOn``, ``soldOn``) posterior a él da ``CAMPO
    OBLIGATORIO FALTANTE (<campo>)``. Llega como dato (el cargador lo saca del instante de
    la carga), nunca del reloj; sin él, no se comprueba.

    Un precio ≤ 0 o con más de 2 decimales no levanta aquí: queda en
    ``precio_invalido`` y ``motivo_de_rechazo`` da ``PRECIO INVÁLIDO``, después de los
    campos faltantes (design.md §6), como en la observación.
    """
    esquema = ESQUEMAS_CAPTURA.get(tipo) if isinstance(tipo, str) else None
    if esquema is None:
        raise RegistroInvalido.tipo_desconocido()
    zona_info = ZoneInfo(zona) if isinstance(zona, str) else zona
    return esquema.leer(datos, zona_info, dia_de_carga)  # type: ignore[return-value]


def _fecha_o_none(valor: object) -> dt.date | None:
    """La fecha de un campo tal como la lee el esquema, o ``None`` si no lo es (ausente o no
    válida: eso lo reporta el esquema en su lugar)."""
    if isinstance(valor, dt.datetime):
        return None
    if isinstance(valor, dt.date):
        return valor
    if isinstance(valor, str):
        try:
            return dt.date.fromisoformat(valor.strip())
        except ValueError:
            return None
    return None


def motivo_de_rechazo(captura: Captura) -> str | None:
    """``PRECIO INVÁLIDO`` si la captura ya leída tiene un precio ≤ 0 o con más de 2
    decimales (DEC-257: ``askingPrice``, ``local_estimate.price``, ``msrp.value``,
    ``actual_result.purchasePrice`` y ``salePrice``); si no, ``None``. Sin el valor ni el
    campo en el motivo (R-20). La ciudad (``CIUDAD NO CONFIGURADA``) la comprueba el cargador
    con la configuración, después de esto."""
    if not isinstance(captura, _Captura):
        raise TypeError("se esperaba una captura ya leída")
    return MotivoRechazo.PRECIO_INVALIDO.value if captura.precio_invalido else None
