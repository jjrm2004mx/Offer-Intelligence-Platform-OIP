"""Validación de cada observación: paso 1 de REQ §3.2 (CMP-07; REQ §6, §10, §11; B20).

Valida una observación contra el contrato 3.1 (CMP-05) y la configuración versionada
(CMP-04) y devuelve el **primer** motivo de rechazo, uno por registro, en el orden de
design.md §6:

1. ``recordType`` (lo comprueba y lo quita el cargador, CMP-08, antes de llegar aquí);
2. obligatorios del contrato, en el orden de la arquitectura §8, y obligatorios del
   particular (``pickupLocation``, ``brand``, ``model``; DEC-227 b): los da
   ``leer_observacion`` (T03) con ``CAMPO OBLIGATORIO FALTANTE (<campo>)``. Aquí se agrega
   la regla de DEC-242: en la publicación de un particular, ``availability.state`` debe ser
   ``listed`` (REQ §6 punto 1); otro código cuenta como valor no válido del campo, en la
   posición de ``availability`` (DEC-234 punto 2, DEC-237, DEC-239);
3. precio > 0 con 2 decimales como máximo → ``PRECIO INVÁLIDO``;
4. dominio autorizado del comercio (``http`` o ``https``, arquitectura §10) o, en la
   publicación de un particular, enlace ``https`` de una plataforma permitida, con su
   prefijo de ruta si la plataforma lo configura (PAR-09; DEC-212), comparado sobre la
   ruta ya normalizada (``..`` y ``%2e%2e`` resueltos; DEC-256) → ``DOMINIO NO
   AUTORIZADO``;
5. ciudad (``pickupLocation``) en la lista de PAR-09 → ``CIUDAD NO CONFIGURADA``.

La validación de la URL es **sintáctica**: nunca se abre una URL (design.md §16). El host
vale si es igual a un dominio autorizado o un subdominio suyo; cualquier forma dudosa
(credenciales en la URL, puerto explícito, espacios o caracteres de control, barra
invertida) se rechaza, porque el enlace se compara, no se interpreta.

``url_canonica`` da la URL canónica de un ``productUrl`` ya autorizado (DEC-256; design.md
§5): la que guarda la publicación (TAB-04) y entra en la clave de idempotencia (DEC-255).

Un rechazo no devuelve la observación: quien llama no puede guardarla en el historial
(design.md §2, RNF-7). Los motivos solo llevan el código y el nombre del campo, nunca un
valor ni el contenido del registro (R-20, DEC-181). Sin reloj, sin I/O, sin red.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import SplitResult, urlsplit, urlunsplit

from oip.catalogos import EstadoDisponibilidad, MotivoRechazo, Resultado, motivo_campo_faltante
from oip.configuracion import Configuracion
from oip.entradas._comun import RegistroInvalido, ausente, obtener
from oip.entradas.contrato import Observacion, es_publicacion_de_particular, leer_observacion

__all__ = [
    "CAMPO_ESTADO",
    "Validacion",
    "motivo_de_rechazo",
    "ruta_normalizada",
    "url_autorizada",
    "url_canonica",
    "validar",
]

#: Campo del estado de la disponibilidad, con el nombre que tiene en el archivo.
CAMPO_ESTADO = "availability.state"

_ESQUEMAS_COMERCIO = frozenset({"http", "https"})  # arquitectura §10
_ESQUEMAS_PARTICULAR = frozenset({"https"})  # DEC-212
#: ``%2e`` se lee como punto al resolver ``.`` y ``..`` (DEC-256).
_PUNTO_CODIFICADO = re.compile("%2e", re.IGNORECASE)


@dataclasses.dataclass(frozen=True, slots=True)
class Validacion:
    """Resultado del paso 1 sobre un registro.

    Válida: ``observacion`` con la observación leída y ``motivo_rechazo`` en ``None``.
    Rechazada: ``observacion`` en ``None`` (no se guarda, RNF-7), ``motivo_rechazo`` con el
    motivo completo y ``campo`` con el nombre del campo si el motivo lo lleva.
    """

    observacion: Observacion | None = dataclasses.field(default=None, repr=False)
    motivo_rechazo: str | None = None
    campo: str | None = None

    def __post_init__(self) -> None:
        if (self.observacion is None) == (self.motivo_rechazo is None):
            raise ValueError("una validación lleva la observación o el motivo, no los dos")

    @property
    def rechazada(self) -> bool:
        return self.motivo_rechazo is not None

    @property
    def resultado(self) -> Resultado | None:
        """``RECHAZADA_VALIDACION`` si se rechaza (REQ §3.2.2); si no, ``None``: el resultado
        lo decide la evaluación."""
        return Resultado.RECHAZADA_VALIDACION if self.rechazada else None


def validar(datos: Mapping[str, Any], configuracion: Configuracion) -> Validacion:
    """Paso 1 completo sobre un registro ya decodificado y sin ``recordType``.

    Primero la forma del contrato y los obligatorios (``leer_observacion``, con la regla de
    ``listed`` del particular), luego ``motivo_de_rechazo``. Nunca levanta por un registro
    inválido: lo devuelve como rechazo.
    """
    if not isinstance(configuracion, Configuracion):
        raise TypeError("se esperaba la configuración validada (Configuracion)")
    if not isinstance(datos, Mapping):
        raise TypeError("la observación debe ser un mapa de campos")
    try:
        observacion = leer_observacion(datos, no_validos=_estado_no_listado(datos))
    except RegistroInvalido as error:
        return Validacion(motivo_rechazo=error.motivo, campo=error.campo)
    rechazo = _primer_rechazo(observacion, configuracion)
    if rechazo is not None:
        motivo, campo = rechazo
        return Validacion(motivo_rechazo=motivo, campo=campo)
    return Validacion(observacion=observacion)


def motivo_de_rechazo(observacion: Observacion, configuracion: Configuracion) -> str | None:
    """Primer motivo de rechazo de una observación ya leída, o ``None`` si es válida.

    Comprueba lo que la forma del contrato no puede saber, en el orden de design.md §6:
    ``listed`` del particular (DEC-242), precio, dominio o plataforma, ciudad. Es lo que
    corre el paso 1 del motor (CMP-17) sobre la oferta del contexto.
    """
    if not isinstance(observacion, Observacion):
        raise TypeError("se esperaba una Observacion")
    if not isinstance(configuracion, Configuracion):
        raise TypeError("se esperaba la configuración validada (Configuracion)")
    rechazo = _primer_rechazo(observacion, configuracion)
    return None if rechazo is None else rechazo[0]


def url_autorizada(
    url: str,
    dominios: Iterable[str],
    *,
    esquemas: Iterable[str],
    prefijo_ruta: str | None = None,
) -> bool:
    """``True`` si ``url`` usa uno de ``esquemas``, su host es uno de ``dominios`` o un
    subdominio suyo y, con ``prefijo_ruta``, su ruta **normalizada** (``ruta_normalizada``)
    es ese prefijo o está debajo de él: una ruta que sale del prefijo con ``..`` o
    ``%2e%2e`` no vale (DEC-256).

    Solo compara el texto (design.md §16): no resuelve el host ni abre la URL.
    """
    partes = _partes(url)
    if partes is None or partes.scheme not in set(esquemas):
        return False
    host = partes.hostname or ""
    if not any(host == d or host.endswith("." + d) for d in dominios):
        return False
    if prefijo_ruta is None:
        return True
    base = prefijo_ruta.rstrip("/")
    ruta = ruta_normalizada(partes.path)
    return ruta == base or ruta.startswith(base + "/")


def ruta_normalizada(ruta: str) -> str:
    """La ruta con ``.`` y ``..`` resueltos (RFC 3986 §5.2.4, ``remove_dot_segments``) y sin
    barra final (DEC-256). Un segmento que, leyendo ``%2e`` como punto, es ``.`` o ``..``
    cuenta como tal; los demás segmentos quedan como vienen. ``..`` no sube más allá de la
    raíz. La raíz sola (``/``) y la ruta vacía dan ``""``."""
    if not isinstance(ruta, str):
        raise TypeError("ruta: se esperaba texto")
    salida: list[str] = []
    for segmento in ruta.split("/")[1:] if ruta.startswith("/") else ruta.split("/"):
        punto = _PUNTO_CODIFICADO.sub(".", segmento)
        if punto == ".":
            continue
        if punto == "..":
            if salida:
                salida.pop()
            continue
        salida.append(segmento)
    return ("/" + "/".join(salida)).rstrip("/")


def url_canonica(url: str) -> str:
    """URL canónica de un ``productUrl`` (DEC-256; design.md §5): esquema ``https``, host en
    minúsculas y sin ``www.`` inicial, sin fragmento, ruta con ``.`` y ``..`` resueltos
    (``%2e`` se lee como punto) y sin barra final; la query se queda tal cual.

    Solo transforma el texto (design.md §16). Una URL con una forma que no se compara con
    seguridad (la que ``url_autorizada`` rechaza) levanta ``ValueError`` sin la URL: se
    canoniza solo un enlace ya autorizado."""
    partes = _partes(url)
    if partes is None:
        raise ValueError("productUrl: la URL no se puede canonizar")
    host = (partes.hostname or "").lower()
    if host.startswith("www."):
        host = host[len("www.") :]
    return urlunsplit(("https", host, ruta_normalizada(partes.path), partes.query, ""))


# --- Internos -----------------------------------------------------------------------------


def _primer_rechazo(
    observacion: Observacion, configuracion: Configuracion
) -> tuple[str, str | None] | None:
    """(motivo, campo) del primer fallo en el orden de design.md §6, o ``None``."""
    if observacion.es_particular and observacion.availability.state != EstadoDisponibilidad.LISTED:
        return motivo_campo_faltante(CAMPO_ESTADO), CAMPO_ESTADO
    if observacion.precio_invalido:
        return MotivoRechazo.PRECIO_INVALIDO.value, None
    if not _enlace_autorizado(observacion, configuracion):
        return MotivoRechazo.DOMINIO_NO_AUTORIZADO.value, None
    ciudad = observacion.pickup_location
    if ciudad is not None and ciudad not in configuracion.private_sellers.cities:
        return MotivoRechazo.CIUDAD_NO_CONFIGURADA.value, None
    return None


def _estado_no_listado(datos: Mapping[str, Any]) -> tuple[str, ...]:
    """DEC-242: en un particular, un ``availability.state`` presente y distinto de
    ``listed`` no es un valor válido. Ausente o vacío lo reporta ya el contrato (DEC-237)."""
    if not es_publicacion_de_particular(datos):
        return ()
    estado = obtener(datos, CAMPO_ESTADO)
    if ausente(estado):
        return ()
    if isinstance(estado, str) and estado.strip() == EstadoDisponibilidad.LISTED.value:
        return ()
    return (CAMPO_ESTADO,)


def _partes(url: str) -> SplitResult | None:
    """Partes de la URL, o ``None`` si tiene una forma que no se compara con seguridad."""
    if not isinstance(url, str) or not url:
        return None
    if any(c.isspace() or not c.isprintable() or c == "\\" for c in url):
        return None
    try:
        partes = urlsplit(url)
        puerto = partes.port
    except ValueError:
        return None
    if "@" in partes.netloc or puerto is not None or not partes.hostname:
        return None
    return partes


def _enlace_autorizado(observacion: Observacion, configuracion: Configuracion) -> bool:
    url = observacion.product_url
    if observacion.es_particular:
        # DEC-212: enlace https de una plataforma permitida (PAR-09).
        return any(
            url_autorizada(
                url,
                plataforma.domains,
                esquemas=_ESQUEMAS_PARTICULAR,
                prefijo_ruta=plataforma.path_prefix,
            )
            for plataforma in configuracion.private_sellers.platforms.values()
        )
    # Comercio (PAR-02): un código sin comercio configurado no tiene dominio autorizado.
    comercio = configuracion.retailers.get(observacion.retailer_code)
    if comercio is None:
        return False
    return url_autorizada(url, comercio.domains, esquemas=_ESQUEMAS_COMERCIO)
