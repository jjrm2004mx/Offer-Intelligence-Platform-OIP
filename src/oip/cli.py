"""Línea de comandos ``oip`` (CMP-22; design.md CTR-07).

- ``oip config cargar <archivo.yaml> [--instante ISO]``: valida la configuración y registra
  su versión (TAB-01); idempotente por ``sha256``. ``--instante`` fija ``loaded_at``; sin
  él, el reloj (DEC-278). Así una carga pasada se reproduce con ``oip cargar --instante``
  aunque ese instante sea anterior al registro original. Una versión ya registrada (mismo
  ``sha256``) conserva su ``loaded_at``.
- ``oip cargar <archivo> [--instante ISO]``: carga un archivo JSON Lines o CSV (CMP-08) con
  la configuración activa a ese instante e imprime el reporte de carga (CTR-05) en JSON.

Sin lógica propia: arma las dependencias y llama a la configuración (CMP-04), al cargador
(CMP-08) y al repositorio (CMP-20). Es el **borde** que lee el reloj: sin ``--instante``, el
instante de la carga (o el ``loaded_at`` de la configuración) es el del reloj, en UTC
(DEC-271, DEC-278); el cargador y el repositorio lo reciben como dato. ``--instante`` exige
el desfase en los dos comandos (no se usa la zona de la máquina). La evaluación de las
observaciones nuevas y ``oip evaluacion recalcular`` llegan con T21.

Los mensajes de error no llevan la URL de la base, la contraseña ni el contenido de un
renglón (RNF-8, DEC-181). Salida: 0 si terminó, 1 si no se pudo hacer, 2 si los argumentos no
son válidos.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TextIO

from oip.configuracion import ErrorConfiguracion, cargar_configuracion
from oip.entradas.cargador import ErrorDeArchivo, cargar_archivo, dia_de_carga
from oip.persistencia.repositorios import ErrorRepositorio, Repositorio

__all__ = ["main"]

Reloj = Callable[[], dt.datetime]
FabricaRepositorio = Callable[[], Repositorio]


def _reloj_utc() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _repositorio_postgres() -> Repositorio:
    """El repositorio de PostgreSQL con la URL del entorno y la contraseña del secreto."""
    from oip.persistencia.repositorios import RepositorioPostgres, crear_motor, url_de_conexion

    return RepositorioPostgres(crear_motor(url_de_conexion()))


def _instante(texto: str) -> dt.datetime:
    try:
        valor = dt.datetime.fromisoformat(texto)
    except ValueError:
        raise argparse.ArgumentTypeError("--instante: fecha y hora ISO 8601") from None
    if valor.utcoffset() is None:
        raise argparse.ArgumentTypeError("--instante: lleva el desfase (por ejemplo -08:00 o Z)")
    try:
        valor.astimezone(dt.UTC)
    except OverflowError:
        raise argparse.ArgumentTypeError("--instante: fuera del rango de fechas en UTC") from None
    return valor


def _analizador() -> argparse.ArgumentParser:
    analizador = argparse.ArgumentParser(prog="oip", description="OIP, Core (parte B).")
    comandos = analizador.add_subparsers(dest="comando", required=True)

    config = comandos.add_parser("config", help="configuración versionada")
    acciones = config.add_subparsers(dest="accion", required=True)
    config_cargar = acciones.add_parser("cargar", help="registrar una versión (TAB-01)")
    config_cargar.add_argument("archivo", type=Path)
    config_cargar.add_argument("--instante", type=_instante, default=None)  # DEC-278

    cargar = comandos.add_parser("cargar", help="cargar un archivo .jsonl o .csv")
    cargar.add_argument("archivo", type=Path)
    cargar.add_argument("--instante", type=_instante, default=None)
    return analizador


def main(
    argv: Sequence[str] | None = None,
    *,
    repositorio: FabricaRepositorio = _repositorio_postgres,
    reloj: Reloj = _reloj_utc,
    salida: TextIO | None = None,
    errores: TextIO | None = None,
) -> int:
    """Corre un comando de ``oip``. ``repositorio`` y ``reloj`` se pueden cambiar (pruebas)."""
    salida = sys.stdout if salida is None else salida
    errores = sys.stderr if errores is None else errores
    try:
        argumentos = _analizador().parse_args(argv)
    except SystemExit as fin:
        return 0 if fin.code == 0 else 2
    try:
        instante = argumentos.instante if argumentos.instante is not None else reloj()
        if argumentos.comando == "config":
            return _config_cargar(argumentos.archivo, repositorio(), instante, salida)
        return _cargar(argumentos.archivo, repositorio(), instante, salida, errores)
    except ErrorConfiguracion as error:
        for mensaje in error.errores:
            print(f"oip: configuración inválida: {mensaje}", file=errores)
    except ErrorDeArchivo as error:
        print(f"oip: {error}", file=errores)
    except OSError as error:
        print(f"oip: no se pudo leer el archivo ({type(error).__name__})", file=errores)
    except ErrorRepositorio as error:
        print(f"oip: {error}", file=errores)
    return 1


def _config_cargar(
    archivo: Path, repo: Repositorio, cargada_en: dt.datetime, salida: TextIO
) -> int:
    configuracion = cargar_configuracion(archivo)
    version, nueva = repo.guardar_version_configuracion(configuracion, cargada_en=cargada_en)
    resultado = {
        "configVersionId": version.id,
        "version": version.configuracion.version,
        "sha256": version.configuracion.sha256,
        "created": nueva,
    }
    print(json.dumps(resultado, ensure_ascii=False), file=salida)
    return 0


def _cargar(
    archivo: Path, repo: Repositorio, instante: dt.datetime, salida: TextIO, errores: TextIO
) -> int:
    version = repo.version_configuracion_activa(instante)
    if version is None:
        print(
            "oip: no hay configuración activa a ese instante; regístrela con oip config cargar",
            file=errores,
        )
        return 1
    try:
        dia_de_carga(instante, version.configuracion.contenido)
    except ValueError as error:
        print(f"oip: {error}", file=errores)
        return 1
    reporte = cargar_archivo(archivo, repo, version, instante)
    print(json.dumps(reporte.a_json(), ensure_ascii=False, indent=2), file=salida)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
