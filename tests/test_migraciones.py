"""Pruebas sin base de las migraciones (CMP-19; design.md §4, Migration Plan; tasks.md T05).

Corren Alembic en **modo sin conexión** (``alembic upgrade head --sql``): generan el SQL de
PostgreSQL sin tocar ninguna base. Comprueban que la copia congelada de ``0001_esquema``
coincide con el modelo de ``oip.persistencia.tablas`` en esa revisión (``metadata_0001``:
tablas, columnas, restricciones e índices), que ``0002_hypertables`` convierte TAB-05 a TAB-07
con chunks de 7 días, que ``0003_registro_de_rechazo`` agrega a TAB-10 justo lo que el modelo
vigente tiene de más (DEC-250) y que la cadena de revisiones es ``0001_esquema`` →
``0002_hypertables`` → ``0003_registro_de_rechazo``. Que el SQL corre contra
PostgreSQL + TimescaleDB lo prueban las pruebas de integración.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from oip.persistencia import tablas

RAIZ = Path(__file__).resolve().parent.parent
DIALECTO = postgresql.dialect()


def _config() -> tuple[Config, io.StringIO]:
    salida = io.StringIO()
    config = Config(str(RAIZ / "alembic.ini"), output_buffer=salida)
    return config, salida


def _sql(accion, *argumentos) -> str:
    config, salida = _config()
    accion(config, *argumentos, sql=True)
    return salida.getvalue()


@pytest.fixture(scope="module")
def sql_0001() -> str:
    return _sql(command.upgrade, "0001_esquema")


@pytest.fixture(scope="module")
def sql_head() -> str:
    return _sql(command.upgrade, "head")


def _sentencias(sql: str) -> list[str]:
    sentencias = []
    for bruto in sql.split(";\n"):
        renglones = [r for r in bruto.strip().splitlines() if not r.startswith("-- ")]
        sentencia = "\n".join(renglones).strip()
        if sentencia:
            sentencias.append(sentencia)
    return sentencias


def _cuerpo(sentencia: str) -> tuple[str, frozenset[str]]:
    """Encabezado y renglones de un ``CREATE TABLE``, sin depender del orden."""
    renglones = [r.strip().rstrip(",").strip() for r in sentencia.strip().splitlines()]
    return renglones[0], frozenset(r for r in renglones[1:] if r not in {")", ");"})


def _create_tables(sql: str) -> dict[str, frozenset[str]]:
    tablas_sql = {}
    for sentencia in _sentencias(sql):
        if sentencia.startswith("CREATE TABLE ") and "alembic_version" not in sentencia:
            encabezado, cuerpo = _cuerpo(sentencia)
            tablas_sql[encabezado.split()[2]] = cuerpo
    return tablas_sql


def test_revisiones_0001_0002_y_0003_en_cadena():
    config, _ = _config()
    guion = ScriptDirectory.from_config(config)
    assert guion.get_heads() == ["0003_registro_de_rechazo"]
    assert guion.get_revision("0003_registro_de_rechazo").down_revision == "0002_hypertables"
    assert guion.get_revision("0002_hypertables").down_revision == "0001_esquema"
    assert guion.get_revision("0001_esquema").down_revision is None


def test_0001_crea_las_mismas_tablas_que_el_modelo(sql_0001):
    generadas = _create_tables(sql_0001)
    assert set(generadas) == set(tablas.metadata_0001.tables)
    for tabla in tablas.metadata_0001.tables.values():
        _, esperado = _cuerpo(str(CreateTable(tabla).compile(dialect=DIALECTO)))
        assert generadas[tabla.name] == esperado, tabla.name


def test_0001_crea_los_mismos_indices_que_el_modelo(sql_0001):
    generados = {s for s in _sentencias(sql_0001) if s.startswith("CREATE ") and "INDEX" in s}
    esperados = {
        str(CreateIndex(indice).compile(dialect=DIALECTO)).strip()
        for tabla in tablas.metadata_0001.tables.values()
        for indice in tabla.indexes
    }
    assert generados == esperados


def test_0001_crea_la_vista_tab12(sql_0001):
    assert f"CREATE VIEW open_opportunity AS {tablas.SQL_OPEN_OPPORTUNITY}" in sql_0001


def test_0001_no_crea_hypertables(sql_0001):
    assert "create_hypertable" not in sql_0001
    assert "timescaledb" not in sql_0001


def test_0002_convierte_tab05_a_tab07_con_chunks_de_7_dias(sql_head):
    parte = sql_head.split("-- Running upgrade 0001_esquema -> 0002_hypertables", 1)[1]
    assert "CREATE EXTENSION IF NOT EXISTS timescaledb" in parte
    llamadas = re.findall(
        r"SELECT create_hypertable\('(\w+)', 'observed_at', "
        r"chunk_time_interval => INTERVAL '([^']+)'\)",
        parte,
    )
    assert llamadas == [(t, tablas.INTERVALO_CHUNK) for t in tablas.HYPERTABLES]
    # Sin compresión, agregados ni retención (Pendiente 8).
    for politica in ("compress", "continuous", "retention", "add_"):
        assert politica not in parte


def test_0002_revierte_solo_sin_datos_y_vuelve_a_crear_las_tablas_normales():
    sql = _sql(command.downgrade, "0002_hypertables:0001_esquema")
    sentencias = _sentencias(sql)
    guardia = next(s for s in sentencias if s.startswith("DO $$"))
    revisadas = re.findall(r"EXISTS \(SELECT 1 FROM (\w+)\)", guardia)
    assert revisadas == list(tablas.HYPERTABLES)
    assert "RAISE EXCEPTION" in guardia
    # La guardia va antes de borrar nada.
    posicion_guardia = sentencias.index(guardia)
    borrados = [i for i, s in enumerate(sentencias) if s.startswith("DROP TABLE")]
    assert borrados and min(borrados) > posicion_guardia
    recreadas = _create_tables(sql)
    assert set(recreadas) == set(tablas.HYPERTABLES)
    for nombre in tablas.HYPERTABLES:
        _, esperado = _cuerpo(
            str(CreateTable(tablas.metadata.tables[nombre]).compile(dialect=DIALECTO))
        )
        assert recreadas[nombre] == esperado
    assert "DROP EXTENSION" not in sql


def test_downgrade_base_borra_todo_lo_de_0001():
    sql = _sql(command.downgrade, "0001_esquema:base")
    assert "DROP VIEW open_opportunity" in sql
    borradas = re.findall(r"^DROP TABLE (\w+)", sql, flags=re.MULTILINE)
    assert set(borradas) == set(tablas.metadata.tables)
    # Primero las que referencian: la vista, luego TAB-11 y TAB-10, al final TAB-01.
    assert borradas[0] == "evaluation_channel"
    assert borradas[-1] == "config_version"


# --- 0003_registro_de_rechazo (DEC-250) -------------------------------------------------

_INICIO_0003 = "-- Running upgrade 0002_hypertables -> 0003_registro_de_rechazo"


def _renglones_del_modelo(md, nombre: str) -> frozenset[str]:
    return _cuerpo(str(CreateTable(md.tables[nombre]).compile(dialect=DIALECTO)))[1]


def test_el_modelo_vigente_es_el_de_0001_mas_lo_de_0003():
    assert set(tablas.metadata.tables) == set(tablas.metadata_0001.tables)
    for nombre in tablas.metadata.tables:
        agregados = _renglones_del_modelo(tablas.metadata, nombre) - _renglones_del_modelo(
            tablas.metadata_0001, nombre
        )
        quitados = _renglones_del_modelo(tablas.metadata_0001, nombre) - _renglones_del_modelo(
            tablas.metadata, nombre
        )
        assert quitados == frozenset(), nombre
        nombres = {r.split()[0] for r in agregados if not r.startswith("CONSTRAINT ")}
        restricciones = {r.split()[1] for r in agregados if r.startswith("CONSTRAINT ")}
        assert nombres == set(tablas.COLUMNAS_0003.get(nombre, ())), nombre
        assert restricciones == set(tablas.RESTRICCIONES_0003.get(nombre, ())), nombre


def test_0003_agrega_a_tab10_lo_que_tiene_el_modelo(sql_head):
    parte = sql_head.split(_INICIO_0003, 1)[1]
    alter = "ALTER TABLE evaluation ADD "
    agregados = {
        s.removeprefix(alter).removeprefix("COLUMN ")
        for s in _sentencias(parte)
        if s.startswith(alter)
    }
    esperado = _renglones_del_modelo(tablas.metadata, "evaluation") - _renglones_del_modelo(
        tablas.metadata_0001, "evaluation"
    )
    assert agregados == esperado
    # TAB-12 se vuelve a crear para que tenga la columna nueva, con el mismo texto.
    vista = [s for s in _sentencias(parte) if "open_opportunity" in s]
    assert vista == [
        "DROP VIEW open_opportunity",
        f"CREATE VIEW open_opportunity AS {tablas.SQL_OPEN_OPPORTUNITY}",
    ]
    assert [c.name for c in tablas.open_opportunity.columns][-1] == "line_number"


def test_0003_se_revierte_quitando_justo_lo_que_agrega():
    sql = _sql(command.downgrade, "0003_registro_de_rechazo:0002_hypertables")
    sentencias = _sentencias(sql)
    restricciones = {
        s.removeprefix("ALTER TABLE evaluation DROP CONSTRAINT ")
        for s in sentencias
        if s.startswith("ALTER TABLE evaluation DROP CONSTRAINT ")
    }
    assert restricciones == set(tablas.RESTRICCIONES_0003["evaluation"])
    assert "ALTER TABLE evaluation DROP COLUMN line_number" in sentencias
    # La vista se borra antes de quitar la columna de la que depende.
    assert sentencias.index("DROP VIEW open_opportunity") < sentencias.index(
        "ALTER TABLE evaluation DROP COLUMN line_number"
    )
    assert f"CREATE VIEW open_opportunity AS {tablas.SQL_OPEN_OPPORTUNITY}" in sentencias


def test_la_url_de_la_base_no_esta_en_el_repo():
    texto = (RAIZ / "alembic.ini").read_text(encoding="utf-8")
    assert "sqlalchemy.url" not in texto
    assert "postgresql://" not in texto
    for archivo in (RAIZ / "migrations").rglob("*.py"):
        contenido = archivo.read_text(encoding="utf-8")
        assert "postgresql://" not in contenido
        assert "postgresql+psycopg://" not in contenido


def test_sin_url_ni_conexion_se_detiene_sin_mostrar_nada(monkeypatch):
    monkeypatch.delenv("OIP_DATABASE_URL", raising=False)
    config, _ = _config()
    with pytest.raises(RuntimeError, match="falta la variable de entorno OIP_DATABASE_URL"):
        command.upgrade(config, "head")
