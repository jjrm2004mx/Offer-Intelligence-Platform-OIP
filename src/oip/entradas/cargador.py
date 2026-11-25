"""Cargador de archivos JSON Lines y CSV (CMP-08; design.md §2, §5, CTR-02, CTR-03, CTR-05).

Un solo cargador (REQ §3.2.6 punto 1): lee el archivo, toma y quita ``recordType``, valida
cada registro según su tipo (observación: contrato 3.1 y paso 1, CMP-05 y CMP-07; capturas:
su esquema, CMP-06), lo guarda en el repositorio (CMP-20) en **una transacción por
registro** y, al terminar, deja el reporte de carga (TAB-02, CTR-05). Un registro inválido
**no detiene la carga**: se rechaza con su motivo y se sigue con el siguiente.

Reglas que fija aquí la parte B:

- **Instante y zona por parámetro.** El cargador no lee el reloj: recibe el ``instante`` de
  la carga (el reloj o ``--instante`` los lee la CLI, CMP-22). ``captured_at`` de cada
  captura = ese instante (DEC-271). La zona es la de ``general.timezone`` de la
  configuración ya validada (PAR-01; DEC-240, DEC-247), y el **día de la carga** es el del
  instante en esa zona: se pasa **siempre** a las capturas, para rechazar una fecha
  posterior (DEC-257, DEC-274).
- **Idempotencia** (design.md §5): una observación usa su ``idempotencyKey`` tal cual; sin
  ella, ``retailerCode|canonical_url|storeCode|extractedAt`` con ``extractedAt`` en UTC
  truncado al minuto y ``storeCode`` ausente como texto vacío (DEC-255). Una captura usa la
  huella ``sha256`` del registro normalizado (tipo + campos). Un duplicado no se guarda y se
  cuenta aparte (``duplicates``).
- **URL canónica** de la publicación (DEC-256): ``validacion.url_canonica``.
- **Identificación del producto** (design.md §10 punto 7): por GTIN válido, si no por
  marca + modelo, si no por la publicación ya conocida, si no un producto nuevo.
- **Rechazos:** cada uno lleva su carga y su renglón (TAB-02; decisión 33 del #34). Una
  observación rechazada (``recordType: observation``) deja además su registro
  ``RECHAZADA_VALIDACION`` sin nada del renglón (DEC-250), en la misma transacción. Un
  renglón sin tipo o con un tipo desconocido solo queda en el reporte (design.md §2).
- **Columna ``recordType`` de un CSV** (DEC-279): opcional. Si su valor, sin espacios al
  inicio y al final, es el tipo del nombre del archivo, se descarta; si es otro o está
  vacío, ese renglón da ``TIPO DE REGISTRO DESCONOCIDO`` sin tipo (como un renglón JSON
  Lines con un tipo desconocido). El tipo sigue saliendo del nombre (CTR-03).
- **Última barrera del repositorio** (DEC-274): un valor que pasó la lectura pero no cabe en
  su columna (``ValueError`` del repositorio, por ejemplo ``price.current`` = ``1e400`` en
  ``numeric(12,2)``) es un rechazo de ese renglón: ``PRECIO INVÁLIDO`` en
  ``price.current`` y en los cinco precios de las capturas (DEC-257 punto 3); en otro
  campo, ``CAMPO OBLIGATORIO FALTANTE (<campo>)``.
- **Sin contenido** de los renglones en el reporte, los rechazos, los logs ni los mensajes
  (R-20, RNF-11, DEC-181): solo números de renglón, tipos, motivos y nombres de campo. La
  única excepción es ``citiesToRegister``: los **códigos** de ciudad que dieron ``CIUDAD
  NO CONFIGURADA``, que el reporte pide dar de alta (REQ §6).

- **Evaluación al final** (design.md §2; T21): después de cargar todo el archivo y de
  escribir el reporte, se evalúa, en el orden del archivo, cada observación nueva de un
  origen de compra con el ensamblador (CMP-21, ``evaluar_carga``), para que una captura del
  mismo archivo ya cuente. Una ficha de Amazon no se evalúa como oferta (DEC-203); un
  duplicado o un rechazo, tampoco. Los ids de las evaluaciones guardadas quedan en
  ``ReporteDeCarga.evaluaciones`` (no son parte de CTR-05).

Sin reloj, sin red.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import re
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from pydantic.alias_generators import to_camel

from oip.catalogos import Identificacion, MotivoRechazo, TipoRegistro, motivo_campo_faltante
from oip.configuracion import Configuracion
from oip.entradas._archivos import (
    CAMPO_TIPO,
    ErrorDeArchivo,
    Formato,
    Renglon,
    formato_de_nombre,
    leer_csv,
    leer_json_lines,
    tipo_de_nombre_csv,
)
from oip.entradas._comun import RegistroInvalido
from oip.entradas.capturas import (
    ESQUEMAS_CAPTURA,
    Captura,
    ComparableLocal,
    VisitaTienda,
    leer_captura,
)
from oip.entradas.capturas import motivo_de_rechazo as motivo_de_captura
from oip.entradas.contrato import Observacion, gtin_valido
from oip.entradas.validacion import url_autorizada, url_canonica, validar
from oip.evaluacion.contexto import ObservacionRegistrada
from oip.persistencia.repositorios import (
    CapturaNueva,
    Carga,
    IdentificadorProducto,
    ObservacionNueva,
    Producto,
    Publicacion,
    RechazoCarga,
    RegistroRechazo,
    ReporteCarga,
    Repositorio,
    VersionConfiguracion,
)

__all__ = [
    "ErrorDeArchivo",
    "RechazoDelReporte",
    "ReporteDeCarga",
    "cargar",
    "cargar_archivo",
    "clave_idempotencia",
    "dia_de_carga",
    "huella_captura",
]

#: Capturas que llevan producto (TAB-09: ``product_id``).
_CON_PRODUCTO = frozenset(
    {
        TipoRegistro.LOCAL_COMPARABLE,
        TipoRegistro.LOCAL_ESTIMATE,
        TipoRegistro.MSRP,
        TipoRegistro.STORE_VISIT,
    }
)

_TIPO_DESCONOCIDO = MotivoRechazo.TIPO_DE_REGISTRO_DESCONOCIDO.value
_PRECIO_INVALIDO = MotivoRechazo.PRECIO_INVALIDO.value
_CIUDAD_NO_CONFIGURADA = MotivoRechazo.CIUDAD_NO_CONFIGURADA.value


# --- Reporte de carga (CTR-05) ------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class RechazoDelReporte:
    """Un renglón rechazado en el reporte: renglón, tipo (``None`` si no se conoce) y motivo."""

    renglon: int
    tipo_registro: TipoRegistro | None
    motivo: str


@dataclasses.dataclass(frozen=True, slots=True)
class ReporteDeCarga:
    """Reporte de una carga (CTR-05). Sin contenido de los renglones."""

    id_carga: UUID
    archivo: str
    formato: Formato
    tipo_registro: TipoRegistro | None
    cargados: int
    rechazados: int
    duplicados: int
    rechazados_por_motivo: Mapping[str, int]
    rechazos: tuple[RechazoDelReporte, ...]
    ciudades_por_registrar: tuple[str, ...]
    #: Ids de las evaluaciones guardadas al final de la carga, en el orden del archivo (T21).
    #: No van en ``a_json``: CTR-05 no las tiene.
    evaluaciones: tuple[UUID, ...] = ()

    def a_json(self) -> dict[str, Any]:
        """El reporte con los nombres de CTR-05, listo para ``json.dumps``."""
        return {
            "loadRunId": str(self.id_carga),
            "fileName": self.archivo,
            "format": self.formato,
            "recordType": None if self.tipo_registro is None else self.tipo_registro.value,
            "loaded": self.cargados,
            "rejected": self.rechazados,
            "duplicates": self.duplicados,
            "rejectedByReason": dict(self.rechazados_por_motivo),
            "rejections": [
                {
                    "line": r.renglon,
                    "recordType": None if r.tipo_registro is None else r.tipo_registro.value,
                    "reason": r.motivo,
                }
                for r in self.rechazos
            ],
            "citiesToRegister": list(self.ciudades_por_registrar),
        }


# --- Reglas públicas ----------------------------------------------------------------------


def dia_de_carga(instante: dt.datetime, configuracion: Configuracion) -> dt.date:
    """El día de la carga: el del ``instante`` en la zona de ``general.timezone`` (PAR-01;
    DEC-257, DEC-274). La zona ya la validó la configuración (DEC-247)."""
    _exigir_instante(instante)
    try:
        return instante.astimezone(ZoneInfo(configuracion.general.timezone)).date()
    except OverflowError:
        raise ValueError("instante: fuera del rango de fechas en la zona de la carga") from None


def clave_idempotencia(observacion: Observacion) -> str:
    """Clave de idempotencia de una observación (design.md §5): su ``idempotencyKey`` si la
    trae, tal cual; si no, ``retailerCode|canonical_url|storeCode|extractedAt`` con
    ``extractedAt`` en UTC truncado al minuto (``AAAA-MM-DDTHH:MM``) y ``storeCode`` ausente
    como texto vacío (DEC-255)."""
    if not isinstance(observacion, Observacion):
        raise TypeError("se esperaba una Observacion")
    if observacion.idempotency_key is not None:
        return observacion.idempotency_key
    extraida = observacion.extracted_at.astimezone(dt.UTC).strftime("%Y-%m-%dT%H:%M")
    return "|".join(
        (
            observacion.retailer_code,
            url_canonica(observacion.product_url),
            observacion.store_code or "",
            extraida,
        )
    )


def huella_captura(tipo: TipoRegistro, captura: Captura) -> str:
    """Huella ``sha256`` del registro normalizado: tipo + campos ya leídos por su esquema
    (design.md §5). Los montos van por su valor (``29.5`` = ``29.50``), las fechas y horas en
    UTC y los valores por defecto ya aplicados; los campos desconocidos no cuentan. La huella
    no revela el contenido (DEC-250)."""
    if ESQUEMAS_CAPTURA.get(tipo) is not type(captura):
        raise TypeError("la captura no es de ese tipo")
    campos = {
        (info.alias or nombre): _canonico(getattr(captura, nombre))
        for nombre, info in type(captura).model_fields.items()
    }
    texto = json.dumps(
        {"recordType": tipo.value, "fields": campos},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


# --- Carga --------------------------------------------------------------------------------


def cargar_archivo(
    ruta: str | Path,
    repositorio: Repositorio,
    version: VersionConfiguracion,
    instante: dt.datetime,
    *,
    nuevo_id: Callable[[], UUID] = uuid4,
) -> ReporteDeCarga:
    """Carga el archivo de ``ruta`` (ver ``cargar``)."""
    ruta = Path(ruta)
    return cargar(ruta.name, ruta.read_bytes(), repositorio, version, instante, nuevo_id=nuevo_id)


def cargar(
    nombre: str,
    contenido: bytes,
    repositorio: Repositorio,
    version: VersionConfiguracion,
    instante: dt.datetime,
    *,
    nuevo_id: Callable[[], UUID] = uuid4,
) -> ReporteDeCarga:
    """Carga un archivo JSON Lines o CSV (``nombre`` da el formato y, en CSV, el tipo) con la
    versión de configuración ``version`` al ``instante`` de la carga, y devuelve su reporte.

    ``nuevo_id`` da los identificadores nuevos (carga, productos, publicaciones,
    observaciones, capturas y registros de rechazo); con uno determinista, la misma carga
    da el mismo resultado; también da los ids de las evaluaciones del final de la carga.
    Levanta ``ErrorDeArchivo`` (antes de empezar la carga) si el
    archivo no se puede leer como carga; nunca por un renglón inválido.
    """
    if not isinstance(contenido, bytes):
        raise TypeError("contenido: se esperaban los bytes del archivo")
    if not isinstance(version, VersionConfiguracion):
        raise TypeError("version: se esperaba la VersionConfiguracion guardada")
    _exigir_instante(instante)
    # El día de la carga, antes de empezarla: un instante sin día en la zona no la inicia.
    dia = dia_de_carga(instante, version.configuracion.contenido)
    nombre = Path(nombre).name
    formato = formato_de_nombre(nombre)
    tipo_csv = tipo_de_nombre_csv(nombre) if formato == "csv" else None
    if formato == "csv":
        renglones = list(leer_csv(contenido, tipo_csv))
    else:
        renglones = list(leer_json_lines(contenido))

    carga = Carga(
        id=nuevo_id(),
        archivo=nombre,
        sha256_archivo=hashlib.sha256(contenido).hexdigest(),
        formato=formato,
        iniciada_en=instante,
        id_version_configuracion=version.id,
        tipo_registro=tipo_csv,
    )
    repositorio.iniciar_carga(carga)
    proceso = _Proceso(repositorio, version, instante, dia, carga.id, nuevo_id)
    for renglon in renglones:
        proceso.registro(renglon, formato, tipo_csv)

    por_motivo = dict(sorted(Counter(r.motivo for r in proceso.rechazos).items()))
    repositorio.terminar_carga(
        carga.id,
        ReporteCarga(
            terminada_en=instante,
            cargados=proceso.cargados,
            rechazados=len(proceso.rechazos),
            duplicados=proceso.duplicados,
            rechazados_por_motivo=por_motivo,
        ),
    )
    return ReporteDeCarga(
        id_carga=carga.id,
        archivo=nombre,
        formato=formato,
        tipo_registro=tipo_csv,
        cargados=proceso.cargados,
        rechazados=len(proceso.rechazos),
        duplicados=proceso.duplicados,
        rechazados_por_motivo=por_motivo,
        rechazos=tuple(proceso.rechazos),
        ciudades_por_registrar=tuple(sorted(proceso.ciudades)),
    )


# --- Internos -----------------------------------------------------------------------------


def _exigir_instante(instante: object) -> None:
    if not isinstance(instante, dt.datetime) or instante.utcoffset() is None:
        raise TypeError("instante: se esperaba una fecha y hora con desfase")


def _canonico(valor: object) -> object:
    """Valor de un campo para la huella: estable y sin ``float``."""
    if isinstance(valor, Enum):
        return valor.value
    if isinstance(valor, Decimal):
        return format(valor.normalize(), "f")
    if isinstance(valor, dt.datetime):
        return valor.astimezone(dt.UTC).isoformat()
    if isinstance(valor, dt.date):
        return valor.isoformat()
    if isinstance(valor, UUID):
        return str(valor)
    if isinstance(valor, list | tuple):
        return [_canonico(v) for v in valor]
    if isinstance(valor, Mapping):
        return {str(k): _canonico(v) for k, v in valor.items()}
    if isinstance(valor, BaseModel):  # pragma: no cover - las capturas no anidan modelos
        return {k: _canonico(v) for k, v in valor.model_dump().items()}
    return valor


def _texto_comparable(texto: str) -> str:
    """Marca o modelo normalizado para identificar: NFKC, minúsculas y espacios simples."""
    return " ".join(unicodedata.normalize("NFKC", texto).casefold().split())


def _identificadores(
    gtin: str | None, marca: str | None, modelo: str | None
) -> tuple[IdentificadorProducto, ...]:
    """Identificadores del producto en el orden de design.md §10 punto 7: el GTIN válido
    (como GTIN-14, así un UPC-A y su EAN-13 son el mismo) y la marca + modelo."""
    salida: list[IdentificadorProducto] = []
    if gtin is not None and gtin_valido(gtin):
        salida.append(IdentificadorProducto("gtin", gtin.strip().zfill(14)))
    if marca and modelo:
        valor = f"{_texto_comparable(marca)}|{_texto_comparable(modelo)}"
        salida.append(IdentificadorProducto("brand_model", valor))
    return tuple(salida)


#: Columnas de una observación (TAB-03 a TAB-08) → campo del archivo, para reportar el
#: rechazo del repositorio con el nombre del campo (design.md §6).
_CAMPOS_OBSERVACION: Mapping[str, str] = {
    "price_observation.was_price": "price.was",
    "price_observation.currency": "price.currency",
    "price_observation.seller": "seller",
    "price_observation.condition": "condition",
    "price_observation.purchase_mode": "purchaseMode",
    "price_observation.is_clearance": "isClearance",
    "price_observation.tax_location": "taxLocation",
    "price_observation.shipping_to_me": "shipping.toMeCost",
    "price_observation.weight_kg": "weightKg",
    "price_observation.dims_cm": "dimsCm",
    "price_observation.category": "category",
    "price_observation.title": "title",
    "price_observation.msrp_value": "msrp.value",
    "price_observation.msrp_source": "msrp.source",
    "price_observation.msrp_date": "msrp.date",
    "price_observation.schema_version": "schemaVersion",
    "price_observation.source_type": "sourceType",
    "price_observation.extraction_method": "extractionMethod",
    "availability_observation.store_code": "storeCode",
    "availability_observation.state": "availability.state",
    "availability_observation.quantity": "availability.quantity",
    "availability_observation.text": "availability.text",
    "availability_observation.scope": "availability.scope",
    "availability_observation.add_to_cart": "availability.addToCart",
    "amazon_listing_observation.buy_box_price": "amazonListing.buyBoxPrice",
    "amazon_listing_observation.sellers_new": "amazonListing.sellersNew",
    "amazon_listing_observation.rank_main": "amazonListing.rankMain",
    "amazon_listing_observation.rank_sub": "amazonListing.rankSub",
    "amazon_listing_observation.reviews": "amazonListing.reviews",
    "amazon_listing_observation.bought_last_month": "amazonListing.boughtLastMonth",
    "ingest_receipt.idempotency_key": "idempotencyKey",
    "listing.retailer_code": "retailerCode",
    "listing.canonical_url": "productUrl",
    "listing.store_code": "storeCode",
    "listing.pickup_location": "pickupLocation",
    "product.brand": "brand",
    "product.model": "model",
    "product.content": "content",
}

#: Columnas de los precios que dan ``PRECIO INVÁLIDO`` (DEC-257 punto 3).
_COLUMNAS_PRECIO = frozenset(
    {
        "price_observation.price",
        "local_comparable.asking_price",
        "local_estimate.price",
        "msrp_capture.value",
        "opportunity_outcome.purchase_price",
        "opportunity_outcome.sale_price",
    }
)

_RUTA_DE_ERROR = re.compile(r"([a-z_]+)\.([a-z_]+)(?:\[\d+\])?: ")


def _motivo_del_repositorio(
    error: ValueError, esquema: type[BaseModel] | None
) -> tuple[str, str | None] | None:
    """(motivo, campo) de un ``ValueError`` del repositorio con la tabla y la columna
    (``price_observation.price: no cabe en numeric(12,2)``); ``None`` si no es de una
    columna conocida (DEC-274)."""
    partes = _RUTA_DE_ERROR.match(str(error))
    if partes is None:
        return None
    ruta = f"{partes.group(1)}.{partes.group(2)}"
    if ruta in _COLUMNAS_PRECIO:
        return _PRECIO_INVALIDO, None
    campo = _CAMPOS_OBSERVACION.get(ruta) if esquema is None else None
    if esquema is not None:
        alias = to_camel(partes.group(2)) if partes.group(1) != "product" else partes.group(2)
        declarados = {info.alias or n for n, info in esquema.model_fields.items()}
        campo = alias if alias in declarados else None
    if campo is None:
        return None
    return motivo_campo_faltante(campo), campo


class _Proceso:
    """Estado de una carga en curso: conteos, rechazos y ciudades por registrar."""

    def __init__(
        self,
        repositorio: Repositorio,
        version: VersionConfiguracion,
        instante: dt.datetime,
        dia: dt.date,
        id_carga: UUID,
        nuevo_id: Callable[[], UUID],
    ) -> None:
        self.repo = repositorio
        self.version = version
        self.config = version.configuracion.contenido
        self.instante = instante
        self.zona = ZoneInfo(self.config.general.timezone)
        self.dia = dia
        self.id_carga = id_carga
        self.nuevo_id = nuevo_id
        self.cargados = 0
        self.duplicados = 0
        self.rechazos: list[RechazoDelReporte] = []
        self.ciudades: set[str] = set()

    # --- Un renglón ---------------------------------------------------------------------

    def registro(self, renglon: Renglon, formato: Formato, tipo_csv: TipoRegistro | None) -> None:
        datos = renglon.datos
        if datos is None:
            # Un renglón que no es un objeto JSON no tiene recordType (DEC-274, lectura).
            self._rechazar(renglon.numero, None, _TIPO_DESCONOCIDO)
            return
        if formato == "csv":
            tipo = tipo_csv
            if CAMPO_TIPO in datos and _tipo_json(datos.pop(CAMPO_TIPO)) is not tipo_csv:
                tipo = None  # DEC-279: la columna contradice el nombre o está vacía.
        else:
            tipo = _tipo_json(datos.pop(CAMPO_TIPO, None))
        if tipo is None:
            self._rechazar(renglon.numero, None, _TIPO_DESCONOCIDO)
        elif tipo is TipoRegistro.OBSERVATION:
            self._observacion(renglon.numero, datos)
        else:
            self._captura(renglon.numero, tipo, datos)

    def _contar(self, guardado: bool) -> None:
        if guardado:
            self.cargados += 1
        else:
            self.duplicados += 1

    def _rechazar(
        self,
        numero: int,
        tipo: TipoRegistro | None,
        motivo: str,
        campo: str | None = None,
        ciudad: str | None = None,
    ) -> None:
        rechazo = RechazoCarga(self.id_carga, numero, motivo, tipo, campo)
        registro = None
        if tipo is TipoRegistro.OBSERVATION:
            # DEC-250: el registro RECHAZADA_VALIDACION, sin nada del renglón.
            registro = RegistroRechazo(
                id=self.nuevo_id(),
                evaluado_en=self.instante,
                id_version_configuracion=self.version.id,
                versiones_rn=self.config.general.rn_versions,
                motivo_rechazo=motivo,
                id_carga=self.id_carga,
                renglon=numero,
            )
        self.repo.guardar_rechazo_carga(rechazo, registro)
        self.rechazos.append(RechazoDelReporte(numero, tipo, motivo))
        if ciudad is not None:
            self.ciudades.add(ciudad)

    # --- Observación --------------------------------------------------------------------

    def _observacion(self, numero: int, datos: dict[str, Any]) -> None:
        tipo = TipoRegistro.OBSERVATION
        validacion = validar(datos, self.config)
        observacion = validacion.observacion
        if validacion.motivo_rechazo is not None or observacion is None:
            motivo = validacion.motivo_rechazo or _TIPO_DESCONOCIDO  # Validacion lleva uno
            ciudad = None
            if motivo == _CIUDAD_NO_CONFIGURADA:
                ciudad = str(datos.get("pickupLocation")).strip()
            self._rechazar(numero, tipo, motivo, validacion.campo, ciudad)
            return
        if observacion.blocked:
            # Arquitectura §8: una consulta bloqueada no genera observación (DEC-274, lectura).
            return
        nueva = self._observacion_nueva(observacion)
        try:
            guardada = self.repo.guardar_observacion(nueva)
        except ValueError as error:
            motivo = _motivo_del_repositorio(error, None)
            if motivo is None:
                raise
            self._rechazar(numero, tipo, *motivo)
            return
        self._contar(guardada)

    def _observacion_nueva(self, observacion: Observacion) -> ObservacionNueva:
        url = url_canonica(observacion.product_url)
        identificadores = _identificadores(observacion.gtin, observacion.brand, observacion.model)
        publicacion = self.repo.buscar_publicacion(
            observacion.retailer_code, url, observacion.store_code
        )
        id_producto = self._producto_conocido(identificadores)
        if id_producto is None and publicacion is not None:
            id_producto = publicacion.id_producto
        producto = None
        if id_producto is None:
            id_producto = self.nuevo_id()
            producto = Producto(
                id=id_producto,
                creado_en=self.instante,
                marca=observacion.brand,
                modelo=observacion.model,
                contenido=observacion.content,
                categoria=observacion.category,
            )
        publicacion_nueva = None
        id_publicacion = publicacion.id if publicacion is not None else self.nuevo_id()
        if publicacion is None:
            particular = observacion.es_particular
            publicacion_nueva = Publicacion(
                id=id_publicacion,
                id_producto=id_producto,
                comercio=observacion.retailer_code,
                url_canonica=url,
                vista_por_primera_vez=observacion.extracted_at,
                tienda=observacion.store_code,
                plataforma=self._plataforma(observacion.product_url) if particular else None,
                ciudad_recogida=observacion.pickup_location if particular else None,
            )
        confirmada = observacion.gtin_valido or bool(observacion.brand and observacion.model)
        return ObservacionNueva(
            registrada=ObservacionRegistrada(
                observacion=observacion,
                id=self.nuevo_id(),
                id_publicacion=id_publicacion,
                id_producto=id_producto,
            ),
            identificacion=Identificacion.CONFIRMED if confirmada else Identificacion.UNCONFIRMED,
            clave_idempotencia=clave_idempotencia(observacion),
            origen="file",
            recibida_en=self.instante,
            id_carga=self.id_carga,
            producto=producto,
            identificadores=self._nuevos(identificadores),
            publicacion=publicacion_nueva,
        )

    def _plataforma(self, url: str) -> str | None:
        """La plataforma de PAR-09 del enlace de un particular (se deduce del dominio)."""
        for codigo, plataforma in self.config.private_sellers.platforms.items():
            if url_autorizada(
                url, plataforma.domains, esquemas=("https",), prefijo_ruta=plataforma.path_prefix
            ):
                return codigo
        return None  # pragma: no cover - la validación ya exigió una plataforma

    def _producto_conocido(self, identificadores: Iterable[IdentificadorProducto]) -> UUID | None:
        for identificador in identificadores:
            id_producto = self.repo.buscar_producto(identificador)
            if id_producto is not None:
                return id_producto
        return None

    def _nuevos(
        self, identificadores: Iterable[IdentificadorProducto]
    ) -> tuple[IdentificadorProducto, ...]:
        """Los identificadores que todavía no tiene ningún producto (se agregan al elegido)."""
        return tuple(i for i in identificadores if self.repo.buscar_producto(i) is None)

    # --- Capturas -----------------------------------------------------------------------

    def _captura(self, numero: int, tipo: TipoRegistro, datos: dict[str, Any]) -> None:
        try:
            captura = leer_captura(tipo, datos, zona=self.zona, dia_de_carga=self.dia)
        except RegistroInvalido as error:
            self._rechazar(numero, tipo, error.motivo, error.campo)
            return
        motivo = motivo_de_captura(captura)
        if motivo is not None:
            self._rechazar(numero, tipo, motivo)
            return
        if isinstance(captura, ComparableLocal):
            if captura.city not in self.config.private_sellers.cities:
                self._rechazar(numero, tipo, _CIUDAD_NO_CONFIGURADA, ciudad=captura.city)
                return
        id_producto, producto, identificadores = self._producto_de_captura(tipo, captura)
        nueva = CapturaNueva(
            id=self.nuevo_id(),
            captura=captura,
            huella=huella_captura(tipo, captura),
            id_carga=self.id_carga,
            capturada_en=self.instante,  # DEC-271
            id_producto=id_producto,
            producto=producto,
            identificadores=identificadores,
        )
        try:
            guardada = self.repo.guardar_captura(nueva)
        except ValueError as error:
            motivo_campo = _motivo_del_repositorio(error, type(captura))
            if motivo_campo is None:
                raise
            self._rechazar(numero, tipo, *motivo_campo)
            return
        self._contar(guardada)

    def _producto_de_captura(
        self, tipo: TipoRegistro, captura: Captura
    ) -> tuple[UUID | None, Producto | None, tuple[IdentificadorProducto, ...]]:
        if tipo not in _CON_PRODUCTO:
            return None, None, ()
        gtin = getattr(captura, "gtin", None)
        marca = getattr(captura, "brand", None)
        modelo = getattr(captura, "model", None)
        identificadores = _identificadores(gtin, marca, modelo)
        if isinstance(captura, VisitaTienda) and not identificadores:
            if captura.evaluation_id is not None:
                return None, None, ()  # la visita es de una oportunidad, sin producto
        id_producto = self._producto_conocido(identificadores)
        producto = None
        if id_producto is None:
            id_producto = self.nuevo_id()
            producto = Producto(id=id_producto, creado_en=self.instante, marca=marca, modelo=modelo)
        return id_producto, producto, self._nuevos(identificadores)


def _tipo_json(valor: object) -> TipoRegistro | None:
    """El ``recordType`` de un renglón JSON Lines; ``None`` si falta, está vacío o no es un
    tipo conocido (``TIPO DE REGISTRO DESCONOCIDO``, REQ §3.2.6)."""
    if not isinstance(valor, str):
        return None
    try:
        return TipoRegistro(valor.strip())
    except ValueError:
        return None
