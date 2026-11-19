"""Pruebas de integración de las migraciones contra PostgreSQL + TimescaleDB (T05).

Comportamientos de tasks.md T05 (design.md §4 y §12): ``alembic upgrade head`` y
``downgrade base`` funcionan; las hypertables existen; los ``CHECK`` rechazan códigos fuera
del catálogo; las claves únicas de idempotencia existen.

Se saltan sin ``OIP_TEST_DATABASE_URL`` (DEC-233: no son gate mientras ``gates.yml`` no
levante una base). La URL sale **solo** del entorno y nunca se imprime (RNF-8). Debe apuntar
a una base **desechable**: cada prueba borra las tablas de OIP antes y después de correr.

Las pruebas que solo usan ``0001_esquema`` corren en cualquier PostgreSQL ≥ 14; las de
``0002_hypertables`` (y ``head``) necesitan la extensión ``timescaledb``.
"""

from __future__ import annotations

import datetime as dt
import os
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError

from oip.persistencia import tablas

pytestmark = pytest.mark.integracion

RAIZ = Path(__file__).resolve().parent.parent
_VARIABLE = "OIP_TEST_DATABASE_URL"
_INSTANTE = dt.datetime(2026, 11, 16, 18, 0, tzinfo=dt.UTC)
_HUELLA = "0" * 64


def _url():
    valor = os.environ.get(_VARIABLE, "").strip()
    if not valor:
        pytest.skip(f"sin {_VARIABLE}: las pruebas de integración se saltan (DEC-233)")
    url = make_url(valor)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    return url


@pytest.fixture
def motor():
    motor = create_engine(_url())
    _limpiar(motor)
    try:
        yield motor
    finally:
        _limpiar(motor)
        motor.dispose()


def _limpiar(motor) -> None:
    """Borra lo que crean las migraciones; deja la extensión ``timescaledb`` instalada."""
    nombres = ", ".join([*tablas.metadata.tables, "alembic_version"])
    with motor.begin() as conexion:
        conexion.execute(text("DROP VIEW IF EXISTS open_opportunity"))
        conexion.execute(text(f"DROP TABLE IF EXISTS {nombres} CASCADE"))


def _alembic(motor, accion, revision: str) -> None:
    with motor.begin() as conexion:
        config = Config(str(RAIZ / "alembic.ini"))
        config.attributes["connection"] = conexion
        accion(config, revision)


def _revision(motor) -> str | None:
    with motor.connect() as conexion:
        return MigrationContext.configure(conexion).get_current_revision()


def _tablas(motor) -> set[str]:
    return set(inspect(motor).get_table_names())


def _vistas(motor) -> set[str]:
    return set(inspect(motor).get_view_names())


def _con_timescale(motor) -> None:
    with motor.connect() as conexion:
        hay = conexion.execute(
            text("SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb'")
        ).first()
    if hay is None:
        pytest.fail("la base de OIP_TEST_DATABASE_URL no tiene la extensión timescaledb")


# --- 5.1: 0001_esquema sube y baja ------------------------------------------------------


def test_0001_sube_y_baja(motor):
    _alembic(motor, command.upgrade, "0001_esquema")
    assert _revision(motor) == "0001_esquema"
    assert _tablas(motor) == set(tablas.metadata.tables) | {"alembic_version"}
    assert _vistas(motor) == {"open_opportunity"}

    _alembic(motor, command.downgrade, "base")
    assert _revision(motor) is None
    assert _tablas(motor) == {"alembic_version"}
    assert _vistas(motor) == set()


def test_0001_coincide_con_el_modelo(motor):
    from alembic.autogenerate import compare_metadata

    _alembic(motor, command.upgrade, "0001_esquema")
    with motor.connect() as conexion:
        diferencias = compare_metadata(MigrationContext.configure(conexion), tablas.metadata)
    # El índice con expresión (coalesce) no se compara por reflexión; lo cubre la prueba
    # sin base que compara el SQL de 0001 con el del modelo.
    diferencias = [
        d
        for d in diferencias
        if not (
            isinstance(d, tuple) and getattr(d[1], "name", "") == "uq_listing_retailer_url_store"
        )
    ]
    assert diferencias == []


# --- 5.1: los CHECK rechazan códigos fuera del catálogo ---------------------------------


def _config_version(conexion) -> int:
    return conexion.execute(
        text(
            "INSERT INTO config_version (version, sha256, schema_version, content,"
            " source_file, loaded_at) VALUES ('2026-11-18.1', :h, '1', '{}', 'base.yaml', :t)"
            " RETURNING id"
        ),
        {"h": _HUELLA, "t": _INSTANTE},
    ).scalar_one()


def _carga(conexion, config_id: int) -> uuid.UUID:
    id_carga = uuid.uuid4()
    conexion.execute(
        text(
            "INSERT INTO load_run (id, file_name, file_sha256, format, started_at, loaded,"
            " rejected, duplicates, rejected_by_reason, config_version_id)"
            " VALUES (:id, 'capturas.jsonl', :h, 'jsonl', :t, 0, 0, 0, '{}', :c)"
        ),
        {"id": id_carga, "h": _HUELLA, "t": _INSTANTE, "c": config_id},
    )
    return id_carga


def _producto_y_publicacion(conexion) -> tuple[uuid.UUID, uuid.UUID]:
    producto, publicacion = uuid.uuid4(), uuid.uuid4()
    conexion.execute(
        text("INSERT INTO product (id, category, created_at) VALUES (:p, 'tools', :t)"),
        {"p": producto, "t": _INSTANTE},
    )
    conexion.execute(
        text(
            "INSERT INTO listing (id, product_id, retailer_code, canonical_url, first_seen_at)"
            " VALUES (:l, :p, 'tienda_prueba', 'https://example.com/p/1', :t)"
        ),
        {"l": publicacion, "p": producto, "t": _INSTANTE},
    )
    return producto, publicacion


def _observacion(conexion, producto, publicacion, **cambios) -> None:
    valores = {
        "o": uuid.uuid4(),
        "t": _INSTANTE,
        "l": publicacion,
        "p": producto,
        "price": Decimal("29.00"),
        "seller": "comercio",
        "condition": "new",
        "purchase_mode": "tienda",
        "category": "tools",
        "identification": "confirmed",
        "schema_version": "3.1",
    } | cambios
    conexion.execute(
        text(
            "INSERT INTO price_observation (observation_id, observed_at, listing_id,"
            " product_id, price, seller, condition, purchase_mode, category, title,"
            " identification, schema_version) VALUES (:o, :t, :l, :p, :price, :seller,"
            " :condition, :purchase_mode, :category, 'Marca Modelo', :identification,"
            " :schema_version)"
        ),
        valores,
    )


@pytest.mark.parametrize(
    ("columna", "valor"),
    [
        ("seller", "vendedor_raro"),
        ("condition", "nuevo"),
        ("purchase_mode", "drone"),
        ("category", "foo"),
        ("identification", "maybe"),
        ("schema_version", "2.0"),
        ("price", Decimal("0.00")),
    ],
)
def test_check_rechaza_codigos_fuera_del_catalogo_en_price_observation(motor, columna, valor):
    _alembic(motor, command.upgrade, "0001_esquema")
    with motor.begin() as conexion:
        producto, publicacion = _producto_y_publicacion(conexion)
        _observacion(conexion, producto, publicacion)  # el válido entra
    with pytest.raises(IntegrityError, match="ck_price_observation_"), motor.begin() as c:
        _observacion(c, producto, publicacion, **{columna: valor})


@pytest.mark.parametrize(
    ("sql", "restriccion"),
    [
        (
            "INSERT INTO product (id, category, created_at) VALUES (:id, 'foo', :t)",
            "ck_product_category_catalogo",
        ),
        (
            "INSERT INTO product (id, brand, created_at) VALUES (:id, '  ', :t)",
            "ck_product_brand_no_vacio",
        ),
        (
            "INSERT INTO evaluation (id, evaluated_at, config_version_id, rn_versions, result,"
            " reasons, marks, observations_used, changed_references, no_longer_recommended)"
            " VALUES (:id, :t, :c, '{}', 'APROBADA', '{}', '{}', '[]', '{}', false)",
            "ck_evaluation_result_catalogo",
        ),
        (
            "INSERT INTO evaluation (id, evaluated_at, config_version_id, rn_versions, result,"
            " main_reason, reasons, marks, observations_used, changed_references,"
            " no_longer_recommended) VALUES (:id, :t, :c, '{}', 'DESCARTADA', 'EVITAR',"
            " '{\"EVITAR\",\"OTRO MOTIVO\"}', '{}', '[]', '{}', false)",
            "ck_evaluation_reasons_catalogo",
        ),
        (
            "INSERT INTO evaluation (id, evaluated_at, config_version_id, rn_versions, result,"
            " rejection_reason, reasons, marks, observations_used, changed_references,"
            " no_longer_recommended) VALUES (:id, :t, :c, '{}', 'RECHAZADA_VALIDACION',"
            " 'CAMPO OBLIGATORIO FALTANTE', '{}', '{}', '[]', '{}', false)",
            "ck_evaluation_rejection_reason_catalogo",
        ),
        (
            "INSERT INTO local_demand (id, load_run_id, idempotency_key, captured_at,"
            " category, level, date) VALUES (:id, :carga, :h, :t, 'tools', 'alta',"
            " '2026-11-16')",
            "ck_local_demand_level_catalogo",
        ),
        (
            "INSERT INTO load_rejection (load_run_id, line_number, reason)"
            " VALUES (:carga, 1, 'RENGLÓN FEO')",
            "ck_load_rejection_reason_catalogo",
        ),
        (
            "INSERT INTO client_request (id, load_run_id, idempotency_key, captured_at,"
            " client_alias, items, quantity, accepted_conditions, modality, date)"
            " VALUES (:id, :carga, :h, :t, 'cliente-a', '{\"M1\"}', 1, '{\"nuevo\"}',"
            " 'link_only', '2026-11-16')",
            "ck_client_request_accepted_conditions_catalogo",
        ),
    ],
    ids=[
        "product.category",
        "product.brand vacío",
        "evaluation.result",
        "evaluation.reasons",
        "evaluation.rejection_reason sin campo",
        "local_demand.level",
        "load_rejection.reason",
        "client_request.accepted_conditions",
    ],
)
def test_check_rechaza_valores_fuera_del_catalogo(motor, sql, restriccion):
    _alembic(motor, command.upgrade, "0001_esquema")
    with motor.begin() as conexion:
        config_id = _config_version(conexion)
        carga = _carga(conexion, config_id)
    parametros = {"id": uuid.uuid4(), "t": _INSTANTE, "c": config_id, "carga": carga}
    parametros["h"] = "a" * 64
    with pytest.raises(IntegrityError, match=restriccion), motor.begin() as conexion:
        conexion.execute(text(sql), parametros)


def test_check_acepta_el_motivo_de_rechazo_con_su_campo(motor):
    _alembic(motor, command.upgrade, "0001_esquema")
    with motor.begin() as conexion:
        carga = _carga(conexion, _config_version(conexion))
        conexion.execute(
            text(
                "INSERT INTO load_rejection (load_run_id, line_number, record_type, reason,"
                " field) VALUES (:c, 1, 'local_comparable',"
                " 'CAMPO OBLIGATORIO FALTANTE (exchangeRate)', 'exchangeRate'),"
                " (:c, 2, NULL, 'TIPO DE REGISTRO DESCONOCIDO', NULL)"
            ),
            {"c": carga},
        )


# --- 5.1: únicos de idempotencia --------------------------------------------------------


def test_ingest_receipt_rechaza_la_misma_clave_dos_veces(motor):
    _alembic(motor, command.upgrade, "0001_esquema")
    sql = text(
        "INSERT INTO ingest_receipt (idempotency_key, observation_id, source, received_at)"
        " VALUES ('tienda_prueba|https://example.com/p/1|t-1|2026-11-16T18:00', :o,"
        " 'worker', :t)"
    )
    with motor.begin() as conexion:
        conexion.execute(sql, {"o": uuid.uuid4(), "t": _INSTANTE})
    with pytest.raises(IntegrityError, match="pk_ingest_receipt"), motor.begin() as conexion:
        conexion.execute(sql, {"o": uuid.uuid4(), "t": _INSTANTE})


@pytest.mark.parametrize(
    "tabla",
    [
        "local_comparable",
        "local_estimate",
        "msrp_capture",
        "local_demand",
        "store_visit",
        "opportunity_outcome",
        "client_request",
    ],
)
def test_cada_captura_tiene_su_unico_de_idempotencia_en_la_base(motor, tabla):
    _alembic(motor, command.upgrade, "0001_esquema")
    unicos = inspect(motor).get_unique_constraints(tabla)
    assert {"name": f"uq_{tabla}_idempotency_key", "column_names": ["idempotency_key"]} in [
        {"name": u["name"], "column_names": u["column_names"]} for u in unicos
    ]


def test_la_misma_captura_dos_veces_choca_con_su_huella(motor):
    _alembic(motor, command.upgrade, "0001_esquema")
    with motor.begin() as conexion:
        carga = _carga(conexion, _config_version(conexion))
    sql = text(
        "INSERT INTO local_demand (id, load_run_id, idempotency_key, captured_at, category,"
        " level, date) VALUES (:id, :c, :h, :t, 'tools', 'high', '2026-11-16')"
    )
    datos = {"c": carga, "h": "b" * 64, "t": _INSTANTE}
    with motor.begin() as conexion:
        conexion.execute(sql, {"id": uuid.uuid4(), **datos})
    with pytest.raises(IntegrityError, match="uq_local_demand_idempotency_key"):
        with motor.begin() as conexion:
            conexion.execute(sql, {"id": uuid.uuid4(), **datos})


def test_los_montos_vuelven_como_decimal(motor):
    _alembic(motor, command.upgrade, "0001_esquema")
    with motor.begin() as conexion:
        producto, publicacion = _producto_y_publicacion(conexion)
        _observacion(conexion, producto, publicacion)
    with motor.connect() as conexion:
        precio = conexion.execute(text("SELECT price FROM price_observation")).scalar_one()
    assert precio == Decimal("29.00")
    assert isinstance(precio, Decimal)


def test_la_vista_da_la_evaluacion_mas_reciente_con_nivel_asignado(motor):
    _alembic(motor, command.upgrade, "0001_esquema")
    insertar = text(
        "INSERT INTO evaluation (id, evaluated_at, listing_id, product_id, config_version_id,"
        " rn_versions, result, main_reason, reasons, marks, chosen_channel, alert_level,"
        " alert_channel, observations_used, changed_references, no_longer_recommended)"
        " VALUES (:id, :t, :l, :p, :c, '{}', :r, :m, :motivos, '{}', :canal, :nivel, :canal,"
        " '[]', '{}', false)"
    )
    with motor.begin() as conexion:
        config_id = _config_version(conexion)
        producto, abierta = _producto_y_publicacion(conexion)
        cerrada = uuid.uuid4()
        conexion.execute(
            text(
                "INSERT INTO listing (id, product_id, retailer_code, canonical_url,"
                " first_seen_at) VALUES (:l, :p, 'tienda_prueba', 'https://example.com/p/2',"
                " :t)"
            ),
            {"l": cerrada, "p": producto, "t": _INSTANTE},
        )
        nivel = {"r": "NIVEL_ASIGNADO", "m": None, "motivos": [], "canal": "amazon"}
        sin_nivel = {"r": "SIN_NIVEL", "m": None, "motivos": [], "canal": None, "nivel": None}
        comun = {"p": producto, "c": config_id}
        id_abierta = uuid.uuid4()
        # Publicación abierta: antes sin nivel, ahora con nivel.
        conexion.execute(
            insertar,
            {"id": uuid.uuid4(), "t": _INSTANTE, "l": abierta, **comun, **sin_nivel},
        )
        conexion.execute(
            insertar,
            {
                "id": id_abierta,
                "t": _INSTANTE + dt.timedelta(hours=1),
                "l": abierta,
                **comun,
                **nivel,
                "nivel": "VIGILAR",
            },
        )
        # Publicación que perdió el nivel: la más reciente es SIN_NIVEL.
        conexion.execute(
            insertar,
            {
                "id": uuid.uuid4(),
                "t": _INSTANTE,
                "l": cerrada,
                **comun,
                **nivel,
                "nivel": "RECOMENDABLE",
            },
        )
        conexion.execute(
            insertar,
            {
                "id": uuid.uuid4(),
                "t": _INSTANTE + dt.timedelta(hours=1),
                "l": cerrada,
                **comun,
                **sin_nivel,
            },
        )
    with motor.connect() as conexion:
        filas = conexion.execute(text("SELECT id, listing_id FROM open_opportunity")).all()
    assert filas == [(id_abierta, abierta)]


# --- 5.2: 0002_hypertables --------------------------------------------------------------


def test_upgrade_head_y_downgrade_base(motor):
    _con_timescale(motor)
    _alembic(motor, command.upgrade, "head")
    assert _revision(motor) == "0002_hypertables"
    assert set(tablas.metadata.tables) <= _tablas(motor)

    _alembic(motor, command.downgrade, "base")
    assert _revision(motor) is None
    assert _tablas(motor) == {"alembic_version"}
    assert _vistas(motor) == set()

    # Volver a subir después de bajar (la PoC de T23 hace lo mismo).
    _alembic(motor, command.upgrade, "head")
    assert _revision(motor) == "0002_hypertables"


def test_tab05_a_tab07_son_hypertables_con_chunks_de_7_dias(motor):
    _con_timescale(motor)
    _alembic(motor, command.upgrade, "head")
    with motor.connect() as conexion:
        filas = conexion.execute(
            text(
                "SELECT hypertable_name, column_name, time_interval"
                " FROM timescaledb_information.dimensions"
                " WHERE hypertable_schema = 'public' ORDER BY hypertable_name"
            )
        ).all()
    assert filas == [
        (nombre, "observed_at", dt.timedelta(days=7)) for nombre in sorted(tablas.HYPERTABLES)
    ]


def test_las_demas_tablas_no_son_hypertables(motor):
    _con_timescale(motor)
    _alembic(motor, command.upgrade, "head")
    with motor.connect() as conexion:
        nombres = set(
            conexion.execute(
                text("SELECT hypertable_name FROM timescaledb_information.hypertables")
            ).scalars()
        )
    assert nombres == set(tablas.HYPERTABLES)


def test_0002_no_se_revierte_con_datos(motor):
    _con_timescale(motor)
    _alembic(motor, command.upgrade, "head")
    with motor.begin() as conexion:
        producto, publicacion = _producto_y_publicacion(conexion)
        _observacion(conexion, producto, publicacion)
    with pytest.raises(Exception, match="solo se revierte sin datos"):
        _alembic(motor, command.downgrade, "0001_esquema")
    assert _revision(motor) == "0002_hypertables"
    with motor.connect() as conexion:
        assert conexion.execute(text("SELECT count(*) FROM price_observation")).scalar_one() == 1


def test_0002_revertida_sin_datos_deja_las_tablas_normales(motor):
    _con_timescale(motor)
    _alembic(motor, command.upgrade, "head")
    _alembic(motor, command.downgrade, "0001_esquema")
    assert _revision(motor) == "0001_esquema"
    with motor.connect() as conexion:
        nombres = set(
            conexion.execute(
                text("SELECT hypertable_name FROM timescaledb_information.hypertables")
            ).scalars()
        )
    assert nombres == set()
    assert set(tablas.HYPERTABLES) <= _tablas(motor)


def test_sin_timescaledb_la_0002_falla_y_no_deja_nada_a_medias(motor):
    with motor.connect() as conexion:
        hay = conexion.execute(
            text("SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb'")
        ).first()
    if hay is not None:
        pytest.skip("la base tiene timescaledb: este caso es para PostgreSQL sin la extensión")
    _alembic(motor, command.upgrade, "0001_esquema")
    with pytest.raises(DBAPIError, match="timescaledb"):
        _alembic(motor, command.upgrade, "head")
    assert _revision(motor) == "0001_esquema"
