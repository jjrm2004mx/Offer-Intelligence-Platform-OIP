"""Conexión de ``RepositorioPostgres`` con la contraseña del ``podman secret`` (CMP-20; RNF-8).

La URL **sin contraseña** sale de ``OIP_DATABASE_URL``; la contraseña, del archivo del
secreto montado (``/run/secrets/oip_db_password``) si existe (design.md §5). La URL nunca
va a un log, a un ``repr`` ni a un mensaje de error: los errores se traducen sin el SQL, los
parámetros ni la URL, y sin encadenar la excepción original.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from pathlib import Path

from sqlalchemy import (
    Engine,
    create_engine,
)
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import (
    ArgumentError,
    DBAPIError,
    IntegrityError,
    InterfaceError,
    OperationalError,
    SQLAlchemyError,
)

from oip.persistencia.repositorios._tipos import (
    ErrorDeConexion,
    ErrorDeIntegridad,
    ErrorRepositorio,
)

__all__ = ["ARCHIVO_SECRETO", "VARIABLE_URL", "crear_motor", "traducir_error", "url_de_conexion"]

#: Variable de entorno con la URL de la base **sin** contraseña (design.md §5).
VARIABLE_URL = "OIP_DATABASE_URL"
#: Archivo del ``podman secret`` con la contraseña (design.md §5; T23 lo monta).
ARCHIVO_SECRETO = Path("/run/secrets/oip_db_password")

_DRIVER = "postgresql+psycopg"


# --- Conexión (RNF-8) ---------------------------------------------------------------------


def _leer_secreto(archivo: Path) -> str:
    error: ErrorDeConexion | None = None
    try:
        contrasena = archivo.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        error = ErrorDeConexion("no se pudo leer el archivo del secreto de la base")
    if error is not None:
        raise error
    contrasena = contrasena.rstrip("\r\n")
    if not contrasena:
        raise ErrorDeConexion("el archivo del secreto de la base está vacío")
    return contrasena


def url_de_conexion(
    entorno: Mapping[str, str] | None = None,
    archivo_secreto: Path | None = ARCHIVO_SECRETO,
) -> URL:
    """La URL de conexión: la de ``OIP_DATABASE_URL`` (sin contraseña) con la contraseña del
    archivo del secreto, si existe. ``postgresql://`` usa psycopg 3.

    Levanta ``ErrorDeConexion`` sin la URL si falta la variable, si no es una URL de
    PostgreSQL, si trae la contraseña (va en el secreto, RNF-8) o si el secreto está vacío.
    """
    valores = os.environ if entorno is None else entorno
    texto = (valores.get(VARIABLE_URL) or "").strip()
    if not texto:
        raise ErrorDeConexion(f"falta la variable de entorno {VARIABLE_URL}")
    url: URL | None = None
    try:
        url = make_url(texto)
    except (ArgumentError, ValueError):
        pass
    if url is None:
        raise ErrorDeConexion(f"{VARIABLE_URL} no es una URL de base de datos válida")
    if url.drivername not in ("postgresql", _DRIVER):
        raise ErrorDeConexion(f"{VARIABLE_URL}: solo PostgreSQL con psycopg 3")
    if url.password is not None:
        raise ErrorDeConexion(
            f"{VARIABLE_URL} no debe llevar la contraseña: va en el podman secret (RNF-8)"
        )
    url = url.set(drivername=_DRIVER)
    if archivo_secreto is not None and archivo_secreto.is_file():
        url = url.set(password=_leer_secreto(archivo_secreto))
    return url


#: Nombre de los loggers del motor y del pool de OIP (``sqlalchemy.engine.Engine.oip`` y
#: ``sqlalchemy.pool.impl.QueuePool.oip``): quedan fijos en WARNING.
_NOMBRE_LOG = "oip"


def crear_motor(url: URL) -> Engine:
    """Motor de SQLAlchemy sin parámetros en los mensajes ni en los logs (RNF-8).

    ``hide_parameters`` quita los valores de los mensajes de error y del log del SQL; además
    los loggers de **este** motor quedan en WARNING aunque la aplicación suba a DEBUG los de
    SQLAlchemy, porque en DEBUG SQLAlchemy registra las **filas** leídas (el alias de un
    cliente, RNF-11). No cambia los loggers de otros motores.
    """
    if not isinstance(url, URL):
        raise TypeError("url: se esperaba un sqlalchemy.engine.URL")
    motor = create_engine(
        url,
        hide_parameters=True,
        pool_pre_ping=True,
        logging_name=_NOMBRE_LOG,
        pool_logging_name=_NOMBRE_LOG,
    )
    for nombre in (motor.logger.name, motor.pool.logger.name):
        logging.getLogger(nombre).setLevel(logging.WARNING)
    return motor


def traducir_error(error: SQLAlchemyError) -> ErrorRepositorio:
    """El error de la base sin SQL, parámetros, URL ni valores (RNF-8, DEC-181)."""
    if isinstance(error, IntegrityError):
        diag = getattr(error.orig, "diag", None)
        return ErrorDeIntegridad(getattr(diag, "constraint_name", None))
    origen = error.orig if isinstance(error, DBAPIError) else error
    clase = type(origen).__name__
    if isinstance(error, OperationalError | InterfaceError):
        return ErrorDeConexion(f"no se pudo usar la conexión a la base ({clase})")
    return ErrorRepositorio(f"error de la base de datos ({clase})")
