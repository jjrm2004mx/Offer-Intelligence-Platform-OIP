"""Conexión de ``RepositorioPostgres`` con el ``podman secret`` (T06; RNF-8, design.md §5).

- La URL **sin contraseña** sale de ``OIP_DATABASE_URL``; la contraseña, del archivo del
  secreto si existe. Una URL con la contraseña adentro se rechaza.
- La URL y la contraseña nunca salen en un mensaje de error, un ``repr``, una excepción
  encadenada ni un log.

Sin base de datos ni red: la conexión que falla usa un socket Unix inexistente en un
directorio temporal. Ninguna prueba trae credenciales reales: la "contraseña" se arma aquí y
es falsa (y así no la detecta como URL con credenciales la prueba de T05).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from oip.persistencia.repositorios import (
    ErrorDeConexion,
    RepositorioPostgres,
    url_de_conexion,
)
from oip.persistencia.repositorios.conexion import ARCHIVO_SECRETO, VARIABLE_URL

CLAVE = "ClaveFalsa" + "T06x"  # nunca una credencial real
USUARIO = "usuario_t06"


def _secreto(tmp_path: Path, contenido: str = CLAVE + "\n") -> Path:
    archivo = tmp_path / "oip_db_password"
    archivo.write_text(contenido, encoding="utf-8")
    return archivo


def _entorno(tmp_path: Path, base: str = "oip_t06") -> dict[str, str]:
    # Socket Unix en un directorio vacío: no hay servidor y no sale a la red.
    return {VARIABLE_URL: f"postgresql://{USUARIO}@/{base}?host={tmp_path}"}


def _sin_secretos(texto: str) -> None:
    assert CLAVE not in texto
    assert USUARIO + ":" not in texto


def test_el_secreto_y_la_variable_son_los_de_design():
    assert VARIABLE_URL == "OIP_DATABASE_URL"
    assert Path("/run/secrets/oip_db_password") == ARCHIVO_SECRETO


def test_la_contrasena_sale_del_archivo_del_secreto(tmp_path):
    url = url_de_conexion(_entorno(tmp_path), _secreto(tmp_path))
    assert url.password == CLAVE  # sin el salto de línea final
    assert url.drivername == "postgresql+psycopg"
    assert url.username == USUARIO
    # El objeto URL de SQLAlchemy oculta la contraseña al mostrarse ("***").
    assert CLAVE not in str(url) and CLAVE not in repr(url)


def test_sin_archivo_del_secreto_la_url_queda_sin_contrasena(tmp_path):
    url = url_de_conexion(_entorno(tmp_path), tmp_path / "no-existe")
    assert url.password is None


def test_la_url_con_la_contrasena_adentro_se_rechaza_sin_citarla(tmp_path):
    entorno = {VARIABLE_URL: "postgresql://" + USUARIO + ":" + CLAVE + "@/oip?host=/tmp/x"}
    with pytest.raises(ErrorDeConexion, match="podman secret") as error:
        url_de_conexion(entorno, None)
    _sin_secretos(str(error.value))
    assert error.value.__context__ is None and error.value.__cause__ is None


@pytest.mark.parametrize(
    ("valor", "mensaje"),
    [
        ("", "falta la variable"),
        ("   ", "falta la variable"),
        ("esto no es una url " + CLAVE, "no es una URL"),
        ("mysql://" + USUARIO + "@/oip", "solo PostgreSQL"),
    ],
)
def test_una_variable_invalida_da_un_error_sin_su_valor(valor, mensaje):
    with pytest.raises(ErrorDeConexion, match=mensaje) as error:
        url_de_conexion({VARIABLE_URL: valor}, None)
    _sin_secretos(str(error.value))
    assert error.value.__context__ is None and error.value.__cause__ is None


def test_falta_la_variable_en_el_entorno():
    with pytest.raises(ErrorDeConexion, match="OIP_DATABASE_URL"):
        url_de_conexion({}, None)


def test_un_secreto_vacio_se_rechaza(tmp_path):
    with pytest.raises(ErrorDeConexion, match="vacío"):
        url_de_conexion(_entorno(tmp_path), _secreto(tmp_path, "\n"))


def test_el_repositorio_no_muestra_la_url(tmp_path):
    repo = RepositorioPostgres.desde_entorno(_entorno(tmp_path), _secreto(tmp_path))
    try:
        assert repr(repo) == "RepositorioPostgres()"
        _sin_secretos(repr(repo))
    finally:
        repo.cerrar()


def test_si_no_conecta_el_error_no_lleva_la_url_ni_la_contrasena(tmp_path, caplog):
    import datetime as dt

    caplog.set_level(logging.DEBUG)
    for nombre in ("sqlalchemy.engine", "sqlalchemy.pool"):
        logging.getLogger(nombre).setLevel(logging.DEBUG)
    repo = RepositorioPostgres.desde_entorno(_entorno(tmp_path), _secreto(tmp_path))
    try:
        with pytest.raises(ErrorDeConexion) as error:
            repo.version_configuracion_activa(dt.datetime(2026, 11, 16, tzinfo=dt.UTC))
    finally:
        repo.cerrar()
        for nombre in ("sqlalchemy.engine", "sqlalchemy.pool"):
            logging.getLogger(nombre).setLevel(logging.NOTSET)
    texto = str(error.value) + repr(error.value)
    _sin_secretos(texto)
    assert str(tmp_path) not in texto  # tampoco el host ni la base
    # La excepción original (con la URL) no queda encadenada.
    assert error.value.__context__ is None and error.value.__cause__ is None
    _sin_secretos(caplog.text)
