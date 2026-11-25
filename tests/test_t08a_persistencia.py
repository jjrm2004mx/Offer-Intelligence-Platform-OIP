"""T08a: conexión, ``CHECK`` de memoria y columnas (decisiones 18 y 19 del #34; RNF-8).

- ``url_de_conexion`` rechaza ``password`` y ``passfile`` en la query, sin distinguir
  mayúsculas, con ``ErrorDeConexion`` y sin la URL en el mensaje (decisión 18).
- ``_checks`` levanta ``NotImplementedError`` **al compilar** (al importar el módulo, sobre
  los metadatos) ante un cast distinto de ``::text[]``, un identificador que no es columna de
  la tabla, ``TRUE``/``FALSE`` y, en ``_patron_are``, ``[:``, ``[.``, ``[=``, ``(?``, ``***``
  y los escapes alfabéticos (decisión 19).
- ``_columnas`` trata ``SmallInteger`` con 16 bits (decisión 19).

Las pruebas del repositorio en memoria y en PostgreSQL (tienda vacía, tipos de id,
``price_usd``) están en la batería de ``tests/test_repositorios.py``. Sin red ni base.
"""

from __future__ import annotations

import importlib
from decimal import Decimal

import pytest
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Integer,
    MetaData,
    SmallInteger,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY

from oip.persistencia import tablas
from oip.persistencia.repositorios import _checks, _columnas
from oip.persistencia.repositorios._tipos import ErrorDeConexion
from oip.persistencia.repositorios.conexion import VARIABLE_URL, url_de_conexion

# --- Conexión (decisión 18) ---------------------------------------------------------------

_SECRETO_FALSO = "valor-sintetico-no-secreto"


@pytest.mark.parametrize("clave", ["password", "PASSWORD", "PassWord", "passfile", "PassFile"])
def test_la_contrasena_o_su_archivo_en_la_query_se_rechazan(clave):
    url = f"postgresql://oip@db.example.com:5432/oip?sslmode=require&{clave}={_SECRETO_FALSO}"
    with pytest.raises(ErrorDeConexion) as error:
        url_de_conexion({VARIABLE_URL: url}, None)
    texto = f"{error.value} {error.value!r} {error.value.args}"
    assert _SECRETO_FALSO not in texto
    assert "db.example.com" not in texto
    assert url not in texto
    assert error.value.__cause__ is None


def test_la_query_sin_contrasena_se_acepta():
    url = url_de_conexion(
        {VARIABLE_URL: "postgresql://oip@db.example.com/oip?sslmode=require"}, None
    )
    assert url.query == {"sslmode": "require"}
    assert url.password is None


def test_otra_clave_que_contiene_password_no_se_confunde():
    # Solo las claves exactas (sin distinguir mayúsculas): una clave distinta no se rechaza.
    url = url_de_conexion(
        {VARIABLE_URL: "postgresql://oip@db.example.com/oip?x_password_hint=1"}, None
    )
    assert "x_password_hint" in url.query


# --- CHECK de memoria (decisión 19) ---------------------------------------------------------


def _tabla(*restricciones: CheckConstraint) -> Table:
    return Table(
        "t",
        MetaData(),
        Column("x", Text),
        Column("y", Text),
        Column("n", Integer),
        Column("lista", ARRAY(Text)),
        *restricciones,
    )


@pytest.mark.parametrize(
    "texto",
    [
        "n::integer > 0",
        "x::text = 'a'",
        "lista <@ ARRAY['a']::integer[]",
        "lista <@ ARRAY['a']::varchar[]",
        "x::text[] IS NULL AND n::bigint > 0",
    ],
)
def test_un_cast_distinto_de_text_array_falla_al_compilar(texto):
    with pytest.raises(NotImplementedError, match="text\\[\\]"):
        _checks._compilar(_tabla(CheckConstraint(texto, name="c")))


def test_el_cast_text_array_se_admite():
    (compilado,) = _checks._compilar(
        _tabla(CheckConstraint("lista <@ ARRAY['a', 'b']::text[]", name="c"))
    )
    _, expr = compilado
    assert expr({"lista": ["a"]}) is True
    assert expr({"lista": ["z"]}) is False


@pytest.mark.parametrize("texto", ["z = 'a'", "x = otra", "btrim(columna_que_no_existe) <> ''"])
def test_un_identificador_que_no_es_columna_falla_al_compilar(texto):
    with pytest.raises(NotImplementedError, match="no es una columna"):
        _checks._compilar(_tabla(CheckConstraint(texto, name="c")))


@pytest.mark.parametrize("texto", ["x = TRUE", "x = FALSE", "x = true", "NOT false", "TRUE"])
def test_true_y_false_fallan_al_compilar(texto):
    with pytest.raises(NotImplementedError, match="TRUE y FALSE"):
        _checks._compilar(_tabla(CheckConstraint(texto, name="c")))


def test_dos_columnas_de_la_tabla_se_admiten():
    ((_, expr),) = _checks._compilar(_tabla(CheckConstraint("x = y", name="c")))
    assert expr({"x": "a", "y": "a"}) is True
    assert expr({"x": "a", "y": "b"}) is False


@pytest.mark.parametrize(
    "patron",
    [
        "^[[:alpha:]]$",
        "^[[.space.]]$",
        "^[[=a=]]$",
        "(?i)abc",
        "***:abc",
        "***=abc",
        "\\yabc\\y",
        "\\mabc\\M",
        "a\\bc",
        "\\d+",
        "\\w",
        "\\s",
        "\\A",
        "\\Z",
    ],
)
def test_patron_are_fuera_del_subconjunto_comun_levanta_not_implemented(patron):
    with pytest.raises(NotImplementedError):
        _checks._patron_are(patron)


@pytest.mark.parametrize("patron", ["^[[:alpha:]]$", "(?i)a", "***:a", "^\\d$", "\\ya"])
def test_un_patron_no_admitido_falla_al_compilar_y_no_en_la_primera_fila(patron):
    restriccion = CheckConstraint(f"x ~ '{patron}'", name="c")
    with pytest.raises(NotImplementedError):
        _checks._compilar(_tabla(restriccion))


def test_el_patron_de_regex_debe_ser_literal():
    with pytest.raises(NotImplementedError, match="literal"):
        _checks._compilar(_tabla(CheckConstraint("x ~ y", name="c")))


@pytest.mark.parametrize(
    ("patron", "texto", "coincide"),
    [
        ("^[0-9a-f]{64}$", "a" * 64, True),
        ("^[0-9a-f]{64}$", "a" * 64 + "\n", False),
        ("^CAMPO \\([A-Za-z][A-Za-z0-9_.]*\\)$", "CAMPO (price.current)", True),
        ("^a\\$$", "a$", True),
        ("^a\\.b$", "a.b", True),
        ("^a\\.b$", "axb", False),
    ],
)
def test_los_patrones_admitidos_se_siguen_evaluando_igual(patron, texto, coincide):
    ((_, expr),) = _checks._compilar(_tabla(CheckConstraint(f"x ~ '{patron}'", name="c")))
    assert expr({"x": texto}) is coincide
    assert expr({"x": None}) is None


def test_el_esquema_vigente_compila_al_importar():
    """Los CHECK de ``tablas.metadata`` pasan las comprobaciones nuevas al importar."""
    modulo = importlib.reload(_checks)
    assert set(modulo.CHECKS) == set(tablas.metadata.tables)
    assert sum(len(v) for v in modulo.CHECKS.values()) > 0


def test_un_check_nuevo_no_admitido_falla_al_importar(monkeypatch):
    """Una regla del esquema que la memoria no entiende falla al importar ``_checks``."""
    metadatos = MetaData()
    Table("t", metadatos, Column("x", Text), CheckConstraint("x::integer > 0", name="c"))
    monkeypatch.setattr(tablas, "metadata", metadatos)
    try:
        with pytest.raises(NotImplementedError):
            importlib.reload(_checks)
    finally:
        monkeypatch.undo()
        importlib.reload(_checks)


# --- Columnas enteras (decisión 19) ---------------------------------------------------------


def _enteros() -> Table:
    return Table(
        "e",
        MetaData(),
        Column("chico", SmallInteger),
        Column("normal", Integer),
        Column("grande", BigInteger),
    )


@pytest.mark.parametrize(
    ("columna", "minimo", "maximo", "nombre"),
    [
        ("chico", -(2**15), 2**15 - 1, "smallint"),
        ("normal", -(2**31), 2**31 - 1, "integer"),
        ("grande", -(2**63), 2**63 - 1, "bigint"),
    ],
)
def test_cada_entero_tiene_su_rango(columna, minimo, maximo, nombre):
    tabla = _enteros()
    assert _columnas.normalizar(tabla, {columna: minimo})[columna] == minimo
    assert _columnas.normalizar(tabla, {columna: maximo})[columna] == maximo
    for fuera in (minimo - 1, maximo + 1):
        with pytest.raises(ValueError, match=nombre):
            _columnas.normalizar(tabla, {columna: fuera})


def test_smallint_rechaza_bool():
    with pytest.raises(TypeError):
        _columnas.normalizar(_enteros(), {"chico": True})


# --- Tipos de los parámetros de lectura (decisiones 16 y 17) -------------------------------


@pytest.mark.parametrize("valor", [True, False])
def test_exigir_tipo_int_rechaza_bool(valor):
    with pytest.raises(TypeError, match="id_"):
        _columnas.exigir_tipo(valor, int, "id_")


def test_exigir_tipo_acepta_el_tipo_exacto():
    from uuid import UUID

    _columnas.exigir_tipo(1, int, "id_")
    _columnas.exigir_tipo(UUID(int=1), UUID, "id_")
    _columnas.exigir_tipo("clave", str, "clave")


def test_exigir_tipo_no_pone_el_valor_en_el_mensaje():
    with pytest.raises(TypeError) as error:
        _columnas.exigir_tipo("valor-sintetico", int, "id_")
    assert "valor-sintetico" not in str(error.value)


@pytest.mark.parametrize("tienda", ["", " ", "\t\n"])
def test_tienda_de_busqueda_vacia_es_value_error(tienda):
    with pytest.raises(ValueError):
        _columnas.tienda_de_busqueda(tienda)


def test_tienda_de_busqueda_none_y_texto():
    assert _columnas.tienda_de_busqueda(None) is None
    assert _columnas.tienda_de_busqueda("tp-01") == "tp-01"


# --- price_usd sin escala (DEC-258) ---------------------------------------------------------


def test_price_usd_es_numeric_sin_escala_y_conserva_el_valor_exacto():
    columna = tablas.local_comparable.c.price_usd
    assert (columna.type.precision, columna.type.scale) == (None, None)
    exacto = Decimal("1500.00") / Decimal("17.3")
    fila = _columnas._valor(columna, exacto, "local_comparable.price_usd")
    assert fila == exacto
    assert str(fila) == str(exacto)


def test_la_excepcion_derivadas_de_t06_ya_no_existe():
    assert not hasattr(_columnas, "_DERIVADAS")


def test_en_0001_price_usd_era_numeric_14_4():
    columna = tablas.metadata_0001.tables["local_comparable"].c.price_usd
    assert (columna.type.precision, columna.type.scale) == (14, 4)
    assert tablas.CAMBIOS_0004 == {"local_comparable": ("price_usd",)}
