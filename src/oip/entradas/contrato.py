"""Observación del contrato de ingesta 3.1 (CMP-05, CTR-01; arquitectura v2.2 §8).

El contrato **se cita, no se redefine** (DEC-199, DEC-223): los nombres y los obligatorios
son los de la arquitectura §8. Este módulo agrega solo las reglas de la parte B:

- ``schemaVersion`` ``3.1``, ``3.0`` (N-1, ADR-027) o ausente (se toma ``3.1``). La 3.1 es
  la 3.0 más el código ``listed`` de ``availability.state`` y el campo ``pickupLocation``:
  en una observación 3.0, ``listed`` no es un código válido y ``pickupLocation`` no existe.
- **Publicación de un particular** (DEC-227 b, DEC-212): además de los obligatorios del
  contrato exige ``pickupLocation``, ``brand`` y ``model``, y su ``title`` lo arma el Core
  con ``brand`` + ``model``, ignorando el que venga (sin texto del vendedor, R-20). Si uno
  de ``retailerCode``, ``seller`` o ``purchaseMode`` vale ``particular``, los tres deben
  valerlo (DEC-239). Se descartan ``availability.text`` y ``evidence``, texto libre que no
  es parte de la publicación (DEC-236).
- ``availability`` sin ``state`` cuenta como ``availability.state`` faltante (DEC-237).
- Enteros y booleanos estrictos (DEC-238); ``extractedAt`` y las demás horas, con desfase.
- **GTIN** con dígito verificador (RN-013, arquitectura §7.3): un GTIN inválido no rechaza
  la observación, pero ``gtin_valido`` es falso y no confirma la coincidencia.
- ``price.current`` > 0 y con 2 decimales como máximo: si no, la observación queda
  marcada (``precio_invalido``) para que la validación (CMP-07, T07) dé ``PRECIO INVÁLIDO``
  en su lugar del orden de design.md §6.
- Los demás montos (``price.was``, ``shipping.toMeCost``, ``msrp.value``,
  ``amazonListing.buyBoxPrice``) con más de 2 decimales no son válidos: ``CAMPO OBLIGATORIO
  FALTANTE (<campo>)`` al leer (DEC-257, DEC-244). El repositorio queda como última barrera.
- En la observación de un **comercio**, ``pickupLocation`` se descarta al leer: ni se valida
  ni se guarda (design.md §6; decisión 37 del #34).

``recordType`` no es parte del contrato: lo quita el cargador (DEC-227 a); si llega, se
descarta como cualquier campo desconocido. Este módulo no valida contra la configuración
(dominios, plataformas, ciudades: CMP-07) ni lee archivos (CMP-08).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BeforeValidator

from oip.catalogos import (
    Categoria,
    Condicion,
    EstadoDisponibilidad,
    ModoCompra,
    Vendedor,
)
from oip.entradas._comun import (
    Booleano,
    Dec,
    Entero,
    Esquema,
    Monto,
    RegistroInvalido,
    ausente,
    decimal_o_none,
    mas_de_2_decimales,
    validar_esquema,
)

__all__ = [
    "CAMPOS_PARTICULAR",
    "OBLIGATORIOS_CONTRATO",
    "OBLIGATORIOS_PARTICULAR",
    "VERSIONES_ACEPTADAS",
    "Disponibilidad",
    "Envio",
    "FichaAmazon",
    "MsrpObservado",
    "Observacion",
    "Precio",
    "RegistroInvalido",
    "es_publicacion_de_particular",
    "gtin_valido",
    "leer_observacion",
]

#: ``schemaVersion`` que acepta la parte B (N y N-1, ADR-027). Ausente = la primera.
VERSIONES_ACEPTADAS = ("3.1", "3.0")

#: Obligatorios del contrato, en el orden de la arquitectura v2.2 §8.
OBLIGATORIOS_CONTRATO = (
    "retailerCode",
    "productUrl",
    "title",
    "category",
    "price.current",
    "seller",
    "availability",
    "purchaseMode",
    "extractedAt",
    "blocked",
)

#: Obligatorios de la publicación de un particular (DEC-227 b), en este orden.
OBLIGATORIOS_PARTICULAR = ("pickupLocation", "brand", "model")

#: Campos que valen ``particular`` en la publicación de un particular, en el orden de
#: REQ §6 (familia 1). Si uno lo vale, los tres deben valerlo (DEC-239).
CAMPOS_PARTICULAR = ("retailerCode", "seller", "purchaseMode")

#: Texto libre que se descarta de la publicación de un particular (DEC-236; REQ §6 y §10,
#: R-20). ``availability.text`` se quita dentro de ``availability``.
_DESCARTADOS_PARTICULAR = ("evidence",)

_PARTICULAR = "particular"
_LONGITUDES_GTIN = (8, 12, 13, 14)  # GTIN-8, GTIN-12 (UPC-A), GTIN-13 (EAN), GTIN-14


def gtin_valido(gtin: str | None) -> bool:
    """``True`` si ``gtin`` es un GTIN-8, 12, 13 o 14 con dígito verificador correcto.

    Algoritmo GS1 (módulo 10): de derecha a izquierda, sin el dígito verificador, los dígitos
    se multiplican alternadamente por 3 y por 1 (RN-013; arquitectura §7.3).
    """
    if not isinstance(gtin, str):
        return False
    texto = gtin.strip()
    if len(texto) not in _LONGITUDES_GTIN or not (texto.isascii() and texto.isdigit()):
        return False
    *cuerpo, verificador = (int(c) for c in texto)
    suma = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(cuerpo)))
    return (10 - suma % 10) % 10 == verificador


def _vale_particular(valor: object) -> bool:
    return isinstance(valor, str) and valor.strip() == _PARTICULAR


def es_publicacion_de_particular(datos: Mapping[str, Any]) -> bool:
    """Una observación es de un particular si ``retailerCode``, ``seller`` o ``purchaseMode``
    vale ``particular`` (REQ §6: los tres llevan ese valor). Con cualquiera de los tres se
    aplican las reglas del particular, para no dejar pasar texto del vendedor; si no valen
    los tres, ``leer_observacion`` la rechaza (DEC-239)."""
    return any(_vale_particular(datos.get(campo)) for campo in CAMPOS_PARTICULAR)


def _incoherente_de_particular(datos: Mapping[str, Any]) -> str | None:
    """El primero de ``CAMPOS_PARTICULAR`` que no vale ``particular`` (DEC-239)."""
    for campo in CAMPOS_PARTICULAR:
        if not _vale_particular(datos.get(campo)):
            return campo
    return None


# --- Partes del contrato --------------------------------------------------------------


class Precio(Esquema):
    """``price``. ``current`` que no es un número queda en ``None`` y marca la observación
    para ``PRECIO INVÁLIDO`` (no es un campo faltante)."""

    current: Annotated[Decimal | None, BeforeValidator(decimal_o_none)] = None
    was: Monto | None = None
    currency: str | None = None


class Disponibilidad(Esquema):
    """``availability``. Sin ``state`` cuenta como ``availability.state`` faltante (DEC-237)."""

    state: EstadoDisponibilidad
    text: str | None = None
    quantity: Entero | None = None
    scope: str | None = None
    add_to_cart: Booleano | None = None


class Envio(Esquema):
    """``shipping``."""

    to_me_cost: Monto | None = None
    days: Entero | None = None
    mode: str | None = None


class MsrpObservado(Esquema):
    """``msrp`` de la observación (solo se muestra, DEC-218)."""

    value: Monto | None = None
    source: str | None = None
    date: dt.date | None = None


class FichaAmazon(Esquema):
    """``amazonListing``: solo en la ficha de Amazon. ``buyBoxPrice`` ``null`` = sin oferta
    hoy (S-02); las referencias usan este precio y no ``price.current`` (DEC-234 punto 3)."""

    buy_box_price: Monto | None = None
    sellers_new: Entero | None = None
    rank_main: Entero | None = None
    rank_sub: Entero | None = None
    reviews: Entero | None = None
    bought_last_month: Entero | None = None


class Observacion(Esquema):
    """Observación del contrato de ingesta 3.1 (arquitectura v2.2 §8), ya validada en forma.

    Los nombres de los campos en Python son los del contrato en snake_case; en el archivo,
    en camelCase. Se construye con ``leer_observacion``.
    """

    schema_version: Literal["3.1", "3.0"] = "3.1"
    crawl_job_id: str | None = None
    idempotency_key: str | None = None
    retailer_code: str
    store_code: str | None = None
    source_type: str | None = None
    product_url: str
    title: str
    brand: str | None = None
    model: str | None = None
    gtin: str | None = None
    content: str | None = None
    category: Categoria
    weight_kg: Dec | None = None
    dims_cm: dict[str, Dec] | None = None
    price: Precio
    seller: Vendedor
    condition: Condicion | None = None
    availability: Disponibilidad
    is_clearance: Booleano | None = None
    purchase_mode: ModoCompra
    tax_location: str | None = None
    pickup_location: str | None = None
    shipping: Envio | None = None
    msrp: MsrpObservado | None = None
    amazon_listing: FichaAmazon | None = None
    extracted_at: AwareDatetime
    extraction_method: str | None = None
    blocked: Booleano
    evidence: dict[str, Any] | None = None

    @property
    def es_particular(self) -> bool:
        """Publicación de un particular (DEC-223)."""
        return _PARTICULAR in (self.seller, self.retailer_code, self.purchase_mode)

    @property
    def es_ficha_amazon(self) -> bool:
        """Ficha de Amazon: no se evalúa como oferta (DEC-203)."""
        return self.amazon_listing is not None

    @property
    def gtin_valido(self) -> bool:
        """El GTIN existe y su dígito verificador es correcto; si no, no confirma (RN-013)."""
        return gtin_valido(self.gtin)

    @property
    def precio_invalido(self) -> bool:
        """``price.current`` no es un número, es ≤ 0 o tiene más de 2 decimales: la
        validación lo rechaza con ``PRECIO INVÁLIDO`` (REQ §3.2 paso 1; design.md §6)."""
        actual = self.price.current
        return actual is None or actual <= 0 or mas_de_2_decimales(actual)


def _version(datos: Mapping[str, Any]) -> str:
    version = datos.get("schemaVersion")
    if ausente(version):
        return VERSIONES_ACEPTADAS[0]
    if not isinstance(version, str) or version.strip() not in VERSIONES_ACEPTADAS:
        raise RegistroInvalido.campo_faltante("schemaVersion")
    return version.strip()


def leer_observacion(datos: Mapping[str, Any], *, no_validos: Iterable[str] = ()) -> Observacion:
    """Lee una observación del contrato 3.1 desde un registro ya decodificado.

    Levanta ``RegistroInvalido`` con ``CAMPO OBLIGATORIO FALTANTE (<campo>)`` y el nombre
    del campo en el archivo: primero ``schemaVersion`` no aceptada, luego los obligatorios
    del contrato (en el orden de la arquitectura §8), luego los del particular y al final
    los demás campos con un valor no válido. Un código fuera de las tablas cerradas, o un
    opcional con un valor no válido, cuenta como faltante (DEC-234 punto 2, DEC-244). Los
    campos desconocidos se descartan.

    ``no_validos`` son campos que el llamador ya sabe que no traen un valor válido (la
    validación del paso 1, CMP-07: ``availability.state`` distinto de ``listed`` en un
    particular, DEC-242); se ordenan con los demás problemas en el mismo orden.

    El precio inválido no levanta: queda en ``Observacion.precio_invalido``.
    """
    if not isinstance(datos, Mapping):
        raise TypeError("la observación debe ser un mapa de campos")
    version = _version(datos)
    registro = dict(datos)
    registro["schemaVersion"] = version
    orden: list[str] = list(OBLIGATORIOS_CONTRATO)
    faltan: list[str] = list(no_validos)
    ignorar: list[str] = []

    if version == "3.0":
        # 3.0 no tiene pickupLocation ni el código listed (los agrega la 3.1).
        registro.pop("pickupLocation", None)
        disponibilidad = registro.get("availability")
        if isinstance(disponibilidad, Mapping):
            estado = disponibilidad.get("state")
            if isinstance(estado, str) and estado.strip() == EstadoDisponibilidad.LISTED:
                faltan.append("availability.state")

    if not es_publicacion_de_particular(registro):
        # Decisión 37 del #34: pickupLocation solo existe en la publicación de un particular
        # (arquitectura §8); en la de un comercio se descarta al leer, sin validarlo.
        registro.pop("pickupLocation", None)
    else:
        # DEC-239: retailerCode, seller y purchaseMode valen particular los tres.
        incoherente = _incoherente_de_particular(registro)
        if incoherente is not None:
            faltan.append(incoherente)
        # DEC-236: sin texto libre del vendedor (REQ §6 y §10, R-20).
        for campo in _DESCARTADOS_PARTICULAR:
            registro.pop(campo, None)
        disponibilidad = registro.get("availability")
        if isinstance(disponibilidad, Mapping):
            registro["availability"] = {k: v for k, v in disponibilidad.items() if k != "text"}
        # DEC-227 b y DEC-212: title = brand + model, armado por el Core.
        orden.remove("title")
        orden.extend(OBLIGATORIOS_PARTICULAR)
        ignorar.append("title")
        registro.pop("title", None)
        marca, modelo = registro.get("brand"), registro.get("model")
        if not ausente(marca) and not ausente(modelo):
            if isinstance(marca, str) and isinstance(modelo, str):
                registro["title"] = f"{marca.strip()} {modelo.strip()}"

    return validar_esquema(Observacion, registro, orden, faltan=faltan, ignorar=ignorar)
