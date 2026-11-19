"""Repositorios de la parte B (CMP-20; design.md §5, RNF-8).

Interfaz ``Repositorio`` (Protocol) con dos implementaciones equivalentes:
``RepositorioMemoria`` (pruebas y desarrollo) y ``RepositorioPostgres`` (PostgreSQL +
TimescaleDB, con la contraseña del ``podman secret``). Guardan y leen observaciones (con su
recibo de idempotencia, TAB-08), capturas, versiones de configuración, cargas y
evaluaciones; las lecturas son "a un instante" y nadie decide aquí: el motor no ve el
repositorio y el contexto lo arma el ensamblador (CMP-21, T21).

Es un subpaquete (no un solo ``repositorios.py``, como dice tasks.md T06) por la regla de
design.md §1: un módulo de más de ~400 líneas se divide en un subpaquete con el mismo
nombre, sin cambiar su interfaz. Se importa igual: ``from oip.persistencia.repositorios
import RepositorioMemoria``.
"""

from oip.persistencia.repositorios._tipos import (
    CapturaGuardada,
    CapturaNueva,
    Carga,
    CargaGuardada,
    ErrorDeConexion,
    ErrorDeIntegridad,
    ErrorRepositorio,
    IdentificadorProducto,
    ObservacionNueva,
    Producto,
    Publicacion,
    RechazoCarga,
    RegistroRechazo,
    ReporteCarga,
    VersionConfiguracion,
)
from oip.persistencia.repositorios.conexion import (
    ARCHIVO_SECRETO,
    VARIABLE_URL,
    crear_motor,
    url_de_conexion,
)
from oip.persistencia.repositorios.memoria import RepositorioMemoria
from oip.persistencia.repositorios.postgres import RepositorioPostgres
from oip.persistencia.repositorios.protocolo import Repositorio

__all__ = [
    "ARCHIVO_SECRETO",
    "VARIABLE_URL",
    "Carga",
    "CapturaGuardada",
    "CapturaNueva",
    "CargaGuardada",
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
    "Repositorio",
    "RepositorioMemoria",
    "RepositorioPostgres",
    "VersionConfiguracion",
    "crear_motor",
    "url_de_conexion",
]
