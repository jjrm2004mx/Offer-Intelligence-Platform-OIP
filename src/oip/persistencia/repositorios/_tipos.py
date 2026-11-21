"""Tipos de entrada y salida del repositorio (CMP-20; design.md §4 y §5).

Son los datos que el cargador (CMP-08) y el ensamblador (CMP-21) entregan al repositorio o
reciben de él, ya decididos: el repositorio **no decide** (no identifica productos, no
calcula claves de idempotencia ni valida contra la configuración); solo guarda y lee.

Todos son ``dataclass(frozen=True, slots=True)`` y verifican sus tipos al construirse, sin
conversiones implícitas (DEC-238): un ``float`` donde va un ``Decimal``, un entero donde va
un booleano o una fecha y hora sin desfase levantan ``TypeError``. Las fechas y horas
quedan en UTC (como en ``oip.evaluacion.contexto``). Los mensajes citan el campo, nunca el
valor (DEC-181).
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal
from uuid import UUID

from oip.catalogos import Categoria, Identificacion, MotivoRechazo, TipoRegistro
from oip.configuracion import ConfiguracionVersionada
from oip.entradas.capturas import Captura
from oip.evaluacion._tipos import campos_dataclass, verificar_tipo
from oip.evaluacion.contexto import ObservacionRegistrada

__all__ = [
    "Carga",
    "CargaGuardada",
    "CapturaGuardada",
    "CapturaNueva",
    "ErrorDeConexion",
    "ErrorDeIntegridad",
    "ErrorRepositorio",
    "IdentificadorProducto",
    "ObservacionNueva",
    "Producto",
    "Publicacion",
    "RechazoCarga",
    "RegistroRechazo",
    "ReporteCarga",
    "VersionConfiguracion",
]

#: ``ingest_receipt.source`` (TAB-08) y ``load_run.format`` (TAB-02).
Origen = Literal["file", "worker"]
Formato = Literal["jsonl", "csv"]
#: ``product_identifier.kind`` (TAB-03).
ClaseIdentificador = Literal["gtin", "brand_model", "retailer_sku", "asin"]

# Se aplican con ``fullmatch``: con ``match``, ``$`` de ``re`` también coincide antes de un
# salto de línea final, y el ``~ '...$'`` de PostgreSQL (ARE) no (``'precio\n'`` no vale).
_HUELLA = re.compile(r"^[0-9a-f]{64}$")
_CAMPO = re.compile(r"^[A-Za-z][A-Za-z0-9_.]*$")
_MOTIVO_CON_CAMPO = re.compile(
    rf"^{re.escape(MotivoRechazo.CAMPO_OBLIGATORIO_FALTANTE.value)} \(([A-Za-z][A-Za-z0-9_.]*)\)$"
)
_MOTIVOS_SIN_CAMPO = frozenset(
    m.value for m in MotivoRechazo if m is not MotivoRechazo.CAMPO_OBLIGATORIO_FALTANTE
)


# --- Errores ------------------------------------------------------------------------------


class ErrorRepositorio(Exception):
    """Falla del repositorio. El mensaje no lleva la URL de la base, la contraseña, el SQL
    ni los valores de un registro (RNF-8, DEC-181): solo la causa."""


class ErrorDeIntegridad(ErrorRepositorio):
    """Se violó una clave o una restricción del esquema; ``restriccion`` es su nombre
    (``pk_evaluation``, ``fk_price_observation_listing_id_listing``…) si se conoce."""

    def __init__(self, restriccion: str | None) -> None:
        self.restriccion = restriccion
        super().__init__(f"restricción violada: {restriccion or 'desconocida'}")


class ErrorDeConexion(ErrorRepositorio):
    """No se pudo armar la conexión o conectar. Sin la URL ni la contraseña (RNF-8)."""


def motivo_rechazo_valido(motivo: str) -> bool:
    """Un motivo del catálogo de rechazo (design.md §6): un código base o ``CAMPO
    OBLIGATORIO FALTANTE (<campo>)`` con el nombre del campo, igual que el ``CHECK`` de
    TAB-02 y TAB-10."""
    return motivo in _MOTIVOS_SIN_CAMPO or _MOTIVO_CON_CAMPO.fullmatch(motivo) is not None


# --- Base ---------------------------------------------------------------------------------


class _Tipado:
    """Verificación estricta de los campos al construir (DEC-238) y fechas en UTC."""

    __slots__ = ()

    def __post_init__(self) -> None:
        pistas = dict(campos_dataclass(type(self)))
        for campo in dataclasses.fields(self):  # type: ignore[arg-type]
            valor = getattr(self, campo.name)
            if isinstance(valor, Mapping) and not isinstance(valor, MappingProxyType):
                valor = MappingProxyType(dict(valor))
                object.__setattr__(self, campo.name, valor)
            verificar_tipo(valor, pistas[campo.name], campo.name)
            if isinstance(valor, dt.datetime) and valor.tzinfo is not dt.UTC:
                object.__setattr__(self, campo.name, valor.astimezone(dt.UTC))


def _texto(valor: str | None, nombre: str) -> None:
    """Vacío = ausente: un texto presente no es vacío ni solo espacios."""
    if valor is not None and not valor.strip():
        raise ValueError(f"{nombre}: texto vacío; lo ausente es None")


def _huella(valor: str, nombre: str) -> None:
    if not _HUELLA.fullmatch(valor):
        raise ValueError(f"{nombre}: huella sha256 en hexadecimal (64 caracteres en minúscula)")


# --- Configuración (TAB-01) -----------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class VersionConfiguracion(_Tipado):
    """Versión guardada de la configuración: su ``id`` de TAB-01, el contenido completo y
    cuándo se cargó (``loaded_at``). ``configuracion.origen`` es ``source_file``."""

    id: int
    configuracion: ConfiguracionVersionada
    cargada_en: dt.datetime


# --- Producto y publicación (TAB-03, TAB-04) ----------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class Producto(_Tipado):
    """Fila de ``product`` (TAB-03). El estado va en la observación, no en el producto."""

    id: UUID
    creado_en: dt.datetime
    marca: str | None = None
    modelo: str | None = None
    contenido: str | None = None
    categoria: Categoria | None = None

    def __post_init__(self) -> None:
        _Tipado.__post_init__(self)
        for nombre in ("marca", "modelo", "contenido"):
            _texto(getattr(self, nombre), nombre)


@dataclasses.dataclass(frozen=True, slots=True)
class IdentificadorProducto(_Tipado):
    """Fila de ``product_identifier`` (TAB-03): clase y valor ya normalizado por quien llama."""

    clase: ClaseIdentificador
    valor: str

    def __post_init__(self) -> None:
        _Tipado.__post_init__(self)
        _texto(self.valor, "valor")


@dataclasses.dataclass(frozen=True, slots=True)
class Publicacion(_Tipado):
    """Fila de ``listing`` (TAB-04). La URL ya canonizada la decide quien llama. Plataforma
    y ciudad de recogida solo en la publicación de un particular (DEC-223)."""

    id: UUID
    id_producto: UUID
    comercio: str
    url_canonica: str
    vista_por_primera_vez: dt.datetime
    tienda: str | None = None
    plataforma: str | None = None
    ciudad_recogida: str | None = None

    def __post_init__(self) -> None:
        _Tipado.__post_init__(self)
        for nombre in ("comercio", "url_canonica", "tienda", "plataforma", "ciudad_recogida"):
            _texto(getattr(self, nombre), nombre)
        if self.comercio != "particular" and (
            self.plataforma is not None or self.ciudad_recogida is not None
        ):
            raise ValueError("plataforma y ciudad_recogida: solo en un particular (DEC-223)")


# --- Observación (TAB-05 a TAB-08) --------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class ObservacionNueva(_Tipado):
    """Una observación válida para guardar con su recibo de idempotencia (TAB-08).

    ``registrada`` lleva sus tres ids (observación, publicación y producto). ``producto``,
    ``identificadores`` y ``publicacion`` son los que hay que **crear** en la misma
    transacción (el cargador decide la identificación, design.md §10 punto 7); si ya
    existen, van vacíos. ``identificacion`` es la coincidencia de **esta** observación
    (RN-013). ``clave_idempotencia`` la calcula quien llama (design.md §5).
    """

    registrada: ObservacionRegistrada
    identificacion: Identificacion
    clave_idempotencia: str
    origen: Origen
    recibida_en: dt.datetime
    id_carga: UUID | None = None
    producto: Producto | None = None
    identificadores: tuple[IdentificadorProducto, ...] = ()
    publicacion: Publicacion | None = None

    def __post_init__(self) -> None:
        _Tipado.__post_init__(self)
        r = self.registrada
        if None in (r.id, r.id_publicacion, r.id_producto):
            raise ValueError("registrada: una observación que se guarda lleva sus tres ids")
        if r.observacion.blocked:
            raise ValueError("registrada: blocked no genera observación (arquitectura §8)")
        _texto(self.clave_idempotencia, "clave_idempotencia")
        if self.origen == "file" and self.id_carga is None:
            raise ValueError("id_carga: una observación de archivo lleva su carga")
        if self.producto is not None and self.producto.id != r.id_producto:
            raise ValueError("producto: debe ser el de la observación")
        if self.publicacion is not None and (
            self.publicacion.id != r.id_publicacion or self.publicacion.id_producto != r.id_producto
        ):
            raise ValueError("publicacion: debe ser la de la observación y su producto")


# --- Capturas (TAB-09) --------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class CapturaNueva(_Tipado):
    """Una captura válida para guardar. ``huella`` es el ``sha256`` del registro
    normalizado (tipo + campos), que calcula quien llama (design.md §5). ``id_producto``
    va solo en los tipos con producto (comparable, estimado, MSRP y, si lo trae, visita);
    ``producto`` e ``identificadores`` son los que hay que crear en la misma transacción."""

    id: UUID
    captura: Captura
    huella: str
    id_carga: UUID
    capturada_en: dt.datetime
    id_producto: UUID | None = None
    producto: Producto | None = None
    identificadores: tuple[IdentificadorProducto, ...] = ()

    def __post_init__(self) -> None:
        _Tipado.__post_init__(self)
        _huella(self.huella, "huella")
        if self.producto is not None and self.producto.id != self.id_producto:
            raise ValueError("producto: debe ser el de la captura")
        if self.identificadores and self.id_producto is None:
            raise ValueError("identificadores: solo con id_producto")


@dataclasses.dataclass(frozen=True, slots=True)
class CapturaGuardada(_Tipado):
    """Una captura leída del repositorio con su ``id``, carga, producto y hora de captura."""

    id: UUID
    captura: Captura
    id_carga: UUID
    capturada_en: dt.datetime
    id_producto: UUID | None = None


# --- Cargas (TAB-02) ----------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class Carga(_Tipado):
    """Inicio de una carga por archivo (``load_run``). ``tipo_registro`` solo en CSV
    (design.md CTR-03)."""

    id: UUID
    archivo: str
    sha256_archivo: str
    formato: Formato
    iniciada_en: dt.datetime
    id_version_configuracion: int
    tipo_registro: TipoRegistro | None = None

    def __post_init__(self) -> None:
        _Tipado.__post_init__(self)
        _texto(self.archivo, "archivo")
        _huella(self.sha256_archivo, "sha256_archivo")
        if self.formato != "csv" and self.tipo_registro is not None:
            raise ValueError("tipo_registro: solo en una carga CSV (CTR-03)")


@dataclasses.dataclass(frozen=True, slots=True)
class ReporteCarga(_Tipado):
    """Cierre de la carga (CTR-05): conteos y rechazos por motivo, sin contenido."""

    terminada_en: dt.datetime
    cargados: int
    rechazados: int
    duplicados: int
    rechazados_por_motivo: Mapping[str, int]

    def __post_init__(self) -> None:
        _Tipado.__post_init__(self)
        if min(self.cargados, self.rechazados, self.duplicados) < 0:
            raise ValueError("conteos: no negativos")
        for motivo, n in self.rechazados_por_motivo.items():
            if not motivo_rechazo_valido(motivo) or n < 0:
                raise ValueError("rechazados_por_motivo: motivos del catálogo y conteos ≥ 0")


@dataclasses.dataclass(frozen=True, slots=True)
class RechazoCarga(_Tipado):
    """Un renglón rechazado (``load_rejection``): carga, renglón, tipo, motivo y el
    **nombre** del campo. Nunca el contenido del renglón (R-20, DEC-181)."""

    id_carga: UUID
    renglon: int
    motivo: str
    tipo_registro: TipoRegistro | None = None
    campo: str | None = None

    def __post_init__(self) -> None:
        _Tipado.__post_init__(self)
        if self.renglon < 1:
            raise ValueError("renglon: empieza en 1")
        if not motivo_rechazo_valido(self.motivo):
            raise ValueError("motivo: fuera del catálogo de rechazo (design.md §6)")
        if self.campo is not None and not _CAMPO.fullmatch(self.campo):
            raise ValueError("campo: solo el nombre del campo")


@dataclasses.dataclass(frozen=True, slots=True)
class CargaGuardada(_Tipado):
    """Una carga leída: su inicio, su reporte (``None`` si no ha terminado) y sus rechazos
    en orden de renglón."""

    carga: Carga
    reporte: ReporteCarga | None
    rechazos: tuple[RechazoCarga, ...]


# --- Registro de un rechazo de validación (TAB-10, DEC-250) -------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class RegistroRechazo(_Tipado):
    """Registro de evaluación ``RECHAZADA_VALIDACION`` de una observación que no pasó el
    paso 1 (B20; DEC-250). **No guarda nada del renglón**: sin ``input_snapshot``, sin
    oferta, publicación, producto, referencias ni números. Lleva el resultado (implícito),
    el motivo de rechazo con su campo, el instante, la versión de configuración, las
    versiones de las RN y el origen: en una carga por archivo, ``id_carga`` y ``renglon``,
    que lo ligan a su ``load_rejection`` (TAB-02). Lo arma el cargador o el ensamblador con
    lo que devuelve ``validar()`` (CMP-07), no el motor. No se recalcula (RNF-3 no aplica):
    se reproduce volviendo a cargar el archivo.
    """

    id: UUID
    evaluado_en: dt.datetime
    id_version_configuracion: int
    versiones_rn: Mapping[str, int]
    motivo_rechazo: str
    id_carga: UUID | None = None
    renglon: int | None = None

    def __post_init__(self) -> None:
        _Tipado.__post_init__(self)
        if not motivo_rechazo_valido(self.motivo_rechazo):
            raise ValueError("motivo_rechazo: fuera del catálogo de rechazo (design.md §6)")
        if (self.id_carga is None) != (self.renglon is None):
            raise ValueError("id_carga y renglon: los dos (carga por archivo) o ninguno")
        if self.renglon is not None and self.renglon < 1:
            raise ValueError("renglon: empieza en 1")
