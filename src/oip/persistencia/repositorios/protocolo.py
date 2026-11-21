"""Interfaz ``Repositorio`` (CMP-20; design.md §5): lo que el cargador (CMP-08) y el
ensamblador (CMP-21) pueden pedir a la base. La implementan ``RepositorioMemoria`` y
``RepositorioPostgres`` con el mismo comportamiento (la batería de contrato de
``tests/test_repositorios.py`` corre sobre las dos).

Reglas comunes (design.md §5):

- **Transacciones:** cada método que escribe es **una** transacción: o queda todo o nada.
  Un registro de un archivo = una llamada (``guardar_observacion``, ``guardar_captura``,
  ``guardar_rechazo_carga``); una evaluación y sus canales = ``guardar_evaluacion``; el
  reporte de carga, ``terminar_carga``, al final y aparte.
- **Idempotencia:** ``guardar_observacion`` y ``guardar_captura`` devuelven ``False`` y no
  escriben **nada** si la clave (TAB-08) o la huella (TAB-09) ya existe; ``True`` si
  guardaron. ``guardar_version_configuracion`` es idempotente por ``sha256``.
- **A un instante:** ninguna lectura con ``instante`` devuelve datos posteriores a él
  (``observed_at``, ``captured_at``, ``loaded_at`` o ``evaluated_at`` ≤ ``instante``). El
  instante siempre lo pasa quien llama: el repositorio no lee el reloj.
- **Errores:** una clave o restricción violada levanta ``ErrorDeIntegridad`` con el nombre
  de la restricción; un valor que no cabe en su columna sin cambiarlo, ``ValueError`` o
  ``TypeError``, antes de escribir. Ningún mensaje lleva la URL, la contraseña, el SQL ni
  los valores de un registro (RNF-8, DEC-181).
- El repositorio **no decide**: no identifica productos, no canoniza URL, no calcula claves
  ni evalúa (el motor no lo ve, design.md §5).
"""

from __future__ import annotations

import datetime as dt
from typing import Protocol, runtime_checkable
from uuid import UUID

from oip.catalogos import TipoRegistro
from oip.configuracion import ConfiguracionVersionada
from oip.evaluacion.contexto import ObservacionRegistrada, RegistroEvaluacion
from oip.persistencia.repositorios._tipos import (
    CapturaGuardada,
    CapturaNueva,
    Carga,
    CargaGuardada,
    IdentificadorProducto,
    ObservacionNueva,
    Producto,
    Publicacion,
    RechazoCarga,
    RegistroRechazo,
    ReporteCarga,
    VersionConfiguracion,
)

__all__ = ["Repositorio"]


@runtime_checkable
class Repositorio(Protocol):
    """Guarda y lee observaciones, capturas, versiones de configuración, cargas y
    evaluaciones (CMP-20)."""

    # --- TAB-01 configuración ---------------------------------------------------------

    def guardar_version_configuracion(
        self, configuracion: ConfiguracionVersionada, *, cargada_en: dt.datetime
    ) -> tuple[VersionConfiguracion, bool]:
        """Registra la versión (contenido completo). Si su ``sha256`` ya está, devuelve la
        guardada y ``False`` sin escribir; la misma ``version`` con otro contenido levanta
        ``ErrorDeIntegridad`` (``uq_config_version_version``)."""
        ...

    def version_configuracion(self, id_: int) -> VersionConfiguracion | None:
        """La versión con ese ``id`` (para recalcular una evaluación, RNF-3)."""
        ...

    def version_configuracion_activa(self, instante: dt.datetime) -> VersionConfiguracion | None:
        """La de ``loaded_at`` más reciente ≤ ``instante`` (design.md §4, TAB-01); con el
        mismo ``loaded_at``, la de ``id`` mayor. ``None`` si no hay ninguna."""
        ...

    # --- TAB-03 y TAB-04 producto y publicación ---------------------------------------

    def guardar_producto(
        self, producto: Producto, identificadores: tuple[IdentificadorProducto, ...] = ()
    ) -> None:
        """Crea un producto con sus identificadores, en una transacción."""
        ...

    def leer_producto(self, id_: UUID) -> Producto | None: ...

    def buscar_producto(self, identificador: IdentificadorProducto) -> UUID | None:
        """El producto de un identificador (clase y valor ya normalizado)."""
        ...

    def buscar_publicacion(
        self, comercio: str, url_canonica: str, tienda: str | None
    ) -> Publicacion | None:
        """La publicación por su clave única (comercio, URL canónica, tienda)."""
        ...

    # --- TAB-05 a TAB-08 observaciones ------------------------------------------------

    def guardar_observacion(self, nueva: ObservacionNueva) -> bool:
        """Guarda el recibo (TAB-08), lo nuevo de producto y publicación, y TAB-05, TAB-06
        y (ficha de Amazon) TAB-07, en una transacción. ``False`` si la clave ya existe."""
        ...

    def observacion_por_clave(self, clave_idempotencia: str) -> UUID | None:
        """El ``observation_id`` del recibo con esa clave (TAB-08), si existe."""
        ...

    def leer_observacion(self, id_: UUID) -> ObservacionRegistrada | None: ...

    def observaciones_del_producto(
        self, id_producto: UUID, *, instante: dt.datetime, desde: dt.datetime | None = None
    ) -> tuple[ObservacionRegistrada, ...]:
        """Las observaciones del producto (también las fichas de Amazon) con
        ``desde ≤ observed_at ≤ instante``, en orden de ``observed_at`` y ``id``."""
        ...

    # --- TAB-09 capturas --------------------------------------------------------------

    def guardar_captura(self, nueva: CapturaNueva) -> bool:
        """Guarda la captura (y su producto nuevo, si lo trae). ``False`` si su huella ya
        existe."""
        ...

    def capturas(
        self, tipo: TipoRegistro, *, instante: dt.datetime, id_producto: UUID | None = None
    ) -> tuple[CapturaGuardada, ...]:
        """Las capturas de ``tipo`` con ``captured_at ≤ instante`` (y del producto, si se
        pide), en orden de ``captured_at`` e ``id``."""
        ...

    # --- TAB-02 cargas ----------------------------------------------------------------

    def iniciar_carga(self, carga: Carga) -> None:
        """Registra el inicio de una carga (conteos en cero, sin terminar)."""
        ...

    def guardar_rechazo_carga(
        self, rechazo: RechazoCarga, registro: RegistroRechazo | None = None
    ) -> None:
        """Guarda un renglón rechazado y, si se da, su registro ``RECHAZADA_VALIDACION``
        (DEC-250), que debe ser de la misma carga y renglón, en una transacción."""
        ...

    def terminar_carga(self, id_carga: UUID, reporte: ReporteCarga) -> None:
        """Escribe el reporte de la carga (CTR-05), en su propia transacción."""
        ...

    def leer_carga(self, id_carga: UUID) -> CargaGuardada | None: ...

    # --- TAB-10 y TAB-11 evaluaciones -------------------------------------------------

    def guardar_evaluacion(self, registro: RegistroEvaluacion) -> None:
        """Guarda el registro del motor con su ``input_snapshot`` (CTR-06) y sus canales,
        en una transacción. Un ``RECHAZADA_VALIDACION`` va por ``guardar_registro_rechazo``."""
        ...

    def guardar_registro_rechazo(self, registro: RegistroRechazo) -> None:
        """Guarda el registro de un rechazo de validación sin nada del renglón (DEC-250)."""
        ...

    def leer_evaluacion(self, id_: UUID) -> RegistroEvaluacion | RegistroRechazo | None: ...

    def oportunidades_abiertas(
        self, *, instante: dt.datetime, id_producto: UUID | None = None
    ) -> tuple[RegistroEvaluacion, ...]:
        """La evaluación más reciente (``evaluated_at ≤ instante``; desempata el ``id``
        mayor) de cada publicación, si es ``NIVEL_ASIGNADO`` (TAB-12 a un instante), en
        orden de ``listing_id``."""
        ...
