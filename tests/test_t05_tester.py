"""Pruebas independientes de oip-tester para T05 (modelo de datos y migraciones).

T05 no tiene escenarios propios (tasks.md §5): estas pruebas verifican los comportamientos
esperados de tasks.md T05 y la guía de implementación, con los valores **copiados de las
fuentes** (design.md §4, §5, §9, CTR-04, §11 RNF-7/8/11, §16; arquitectura §8), no del código:

- metadatos de TAB-01 a TAB-12 (columnas, tipos ``numeric`` exactos, claves primarias con el
  tiempo, únicos de idempotencia, índices), sin base;
- en una base PostgreSQL (``OIP_TEST_DATABASE_URL``): los ``CHECK`` aceptan cada código de
  cada catálogo cerrado y rechazan los de fuera; ninguna columna ``float``; ``0001`` y el
  modelo dan el mismo catálogo de PostgreSQL (columnas, restricciones, índices y vista);
  ninguna tabla admite el contenido de un renglón rechazado;
- con TimescaleDB: ``0002`` revertida deja exactamente lo que crea ``0001``;
- estáticas: sin URL ni credenciales en el repo ni en la salida de Alembic, y las de
  integración se saltan sin ``OIP_TEST_DATABASE_URL``.

Las de base van marcadas ``@pytest.mark.integracion`` y se saltan sin la variable. Deben
apuntar a una base **desechable**: borran las tablas de OIP antes y después. Datos
sintéticos; dominios ``example.com``; reloj fijo en UTC.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
import sys
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import Numeric, create_engine, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from oip.persistencia import tablas

RAIZ = Path(__file__).resolve().parent.parent
_VARIABLE = "OIP_TEST_DATABASE_URL"
_T = dt.datetime(2026, 11, 16, 18, 0, tzinfo=dt.UTC)
_D = dt.date(2026, 11, 16)
DIALECTO = postgresql.dialect()

# --- Lo que dicen las fuentes (copiado, no derivado del código) -----------------------

#: Columnas de design.md §4 (TAB-01 a TAB-11) y, en TAB-09, los campos de CTR-04 en
#: snake_case más ``id``, ``product_id`` (si el tipo trae producto), ``load_run_id``,
#: ``idempotency_key`` y ``captured_at``.
_COMUNES = {"id", "load_run_id", "idempotency_key", "captured_at"}
COLUMNAS = {
    "config_version": {
        "id",
        "version",
        "sha256",
        "schema_version",
        "content",
        "source_file",
        "loaded_at",
    },
    "load_run": {
        "id",
        "file_name",
        "file_sha256",
        "format",
        "record_type",
        "started_at",
        "finished_at",
        "loaded",
        "rejected",
        "duplicates",
        "rejected_by_reason",
        "config_version_id",
    },
    "load_rejection": {"load_run_id", "line_number", "record_type", "reason", "field"},
    "product": {"id", "brand", "model", "content", "category", "created_at"},
    "product_identifier": {"product_id", "kind", "value"},
    "listing": {
        "id",
        "product_id",
        "retailer_code",
        "store_code",
        "canonical_url",
        "platform",
        "pickup_location",
        "first_seen_at",
    },
    "price_observation": {
        "observation_id",
        "observed_at",
        "listing_id",
        "product_id",
        "price",
        "was_price",
        "currency",
        "seller",
        "condition",
        "purchase_mode",
        "is_clearance",
        "tax_location",
        "shipping_to_me",
        "weight_kg",
        "dims_cm",
        "category",
        "title",
        "identification",
        "msrp_value",
        "msrp_source",
        "msrp_date",
        "schema_version",
        "load_run_id",
        # §4 da las "columnas principales"; RNF-7 / DEC-236 conservan estas dos.
        "source_type",
        "extraction_method",
    },
    "availability_observation": {
        "observation_id",
        "observed_at",
        "listing_id",
        "store_code",
        "state",
        "quantity",
        "text",
        "scope",
        "add_to_cart",
    },
    "amazon_listing_observation": {
        "observation_id",
        "observed_at",
        "product_id",
        "listing_id",
        "buy_box_price",
        "sellers_new",
        "rank_main",
        "rank_sub",
        "reviews",
        "bought_last_month",
    },
    "ingest_receipt": {"idempotency_key", "observation_id", "source", "received_at", "load_run_id"},
    "local_comparable": _COMUNES
    | {
        "product_id",
        "gtin",
        "brand",
        "model",
        "condition",
        "asking_price",
        "currency",
        "exchange_rate",
        "city",
        "date",
        "sold",
        "price_usd",
    },
    "local_estimate": _COMUNES
    | {"product_id", "gtin", "brand", "model", "condition", "price", "date"},
    "msrp_capture": _COMUNES | {"product_id", "gtin", "brand", "model", "value", "source", "date"},
    "local_demand": _COMUNES | {"category", "level", "date"},
    "store_visit": _COMUNES
    | {
        "product_id",
        "store_code",
        "gtin",
        "brand",
        "model",
        "evaluation_id",
        "result",
        "visited_at",
    },
    "opportunity_outcome": _COMUNES
    | {
        "evaluation_id",
        "channel",
        "units",
        "purchase_price",
        "sale_price",
        "actual_costs",
        "purchased_on",
        "sold_on",
    },
    "client_request": _COMUNES
    | {
        "client_alias",
        "items",
        "quantity",
        "accepted_conditions",
        "modality",
        "postal_code",
        "date",
    },
    "evaluation": {
        "id",
        "evaluated_at",
        "offer_observation_id",
        "listing_id",
        "product_id",
        "config_version_id",
        "rn_versions",
        "result",
        "main_reason",
        "reasons",
        "rejection_reason",
        "marks",
        "price_quality",
        "confidence",
        "identification",
        "references",
        "advertised_discount",
        "real_discount",
        "purchase_cost",
        "chosen_channel",
        "alert_level",
        "alert_channel",
        "observations_used",
        "input_snapshot",
        "previous_evaluation_id",
        "changed_references",
        "no_longer_recommended",
        "load_run_id",
        # 0003_registro_de_rechazo (DEC-250): renglón del rechazo de una carga por archivo.
        "line_number",
    },
    "evaluation_channel": {
        "evaluation_id",
        "channel",
        "state",
        "closed_causes",
        "review_causes",
        "sale_price",
        "selling_cost",
        "net_margin",
        "net_margin_pct",
        "returns_cost",
        "drop_penalty",
        "adjusted_margin",
        "adjusted_margin_pct",
        "units",
        "days_to_recover",
        "monthly_yield_pct",
        "level",
        "calculated_level",
        "total_profit",
        "marks",
    },
}

#: Montos (design.md §4, "numeric(12,2)"; lista de dinero de §8 y precios leídos).
MONTOS = {
    ("price_observation", "price"),
    ("price_observation", "was_price"),
    ("price_observation", "shipping_to_me"),
    ("price_observation", "msrp_value"),
    ("amazon_listing_observation", "buy_box_price"),
    ("local_comparable", "asking_price"),
    ("local_estimate", "price"),
    ("msrp_capture", "value"),
    ("opportunity_outcome", "purchase_price"),
    ("opportunity_outcome", "sale_price"),
    ("opportunity_outcome", "actual_costs"),
    ("evaluation", "purchase_cost"),
    ("evaluation_channel", "selling_cost"),
    ("evaluation_channel", "net_margin"),
    ("evaluation_channel", "returns_cost"),
    ("evaluation_channel", "drop_penalty"),
    ("evaluation_channel", "adjusted_margin"),
    ("evaluation_channel", "total_profit"),
}
#: Conversiones de MXN y medianas (design.md §4, "numeric(14,4)"). ``sale_price`` de TAB-11
#: es la lectura de G4 del developer (T05-5 en #34).
CONVERSIONES = {("local_comparable", "price_usd"), ("evaluation_channel", "sale_price")}
#: Sin redondear (design.md §4 "real_discount numeric (sin redondear)"; DEC-207).
SIN_ESCALA = {
    ("price_observation", "weight_kg"),
    ("local_comparable", "exchange_rate"),
    ("evaluation", "advertised_discount"),
    ("evaluation", "real_discount"),
    ("evaluation_channel", "net_margin_pct"),
    ("evaluation_channel", "adjusted_margin_pct"),
    ("evaluation_channel", "days_to_recover"),
    ("evaluation_channel", "monthly_yield_pct"),
}

#: Claves primarias: las de §4 y, en las hypertables, con la columna de tiempo.
CLAVES = {
    "config_version": ("id",),
    "load_run": ("id",),
    "load_rejection": ("load_run_id", "line_number"),
    "product": ("id",),
    "listing": ("id",),
    "price_observation": ("observation_id", "observed_at"),
    "availability_observation": ("observation_id", "observed_at"),
    "amazon_listing_observation": ("observation_id", "observed_at"),
    "ingest_receipt": ("idempotency_key",),
    "local_comparable": ("id",),
    "local_estimate": ("id",),
    "msrp_capture": ("id",),
    "local_demand": ("id",),
    "store_visit": ("id",),
    "opportunity_outcome": ("id",),
    "client_request": ("id",),
    "evaluation": ("id",),
    "evaluation_channel": ("evaluation_id", "channel"),
}
CAPTURAS = (
    "local_comparable",
    "local_estimate",
    "msrp_capture",
    "local_demand",
    "store_visit",
    "opportunity_outcome",
    "client_request",
)

#: Índices de design.md §4 (cuerpo de ``pg_get_indexdef``). La demanda local usa ``date``
#: en lugar de ``captured_on`` (T05-4 en #34).
INDICES = {
    ("listing", "(product_id)"),
    ("listing", "UNIQUE (retailer_code, canonical_url, COALESCE(store_code, ''::text))"),
    ("price_observation", "(product_id, observed_at DESC)"),
    ("price_observation", "(listing_id, observed_at DESC)"),
    ("availability_observation", "(listing_id, observed_at DESC)"),
    ("amazon_listing_observation", "(product_id, observed_at DESC)"),
    ("local_comparable", "(product_id, condition)"),
    ("local_estimate", "(product_id, condition)"),
    ("local_demand", "(category, date DESC)"),
    ("evaluation", "(listing_id, evaluated_at DESC)"),
    ("evaluation", "(product_id, result)"),
    *((captura, "UNIQUE (idempotency_key)") for captura in CAPTURAS),
    ("config_version", "UNIQUE (version)"),
    ("config_version", "UNIQUE (sha256)"),
    ("product_identifier", "UNIQUE (kind, value)"),
}

# Catálogos cerrados: design.md §9 y arquitectura §8 (códigos del contrato 3.1).
CATEGORIAS = (
    "tools",
    "home_lighting",
    "home_kitchen",
    "electronics",
    "video_game_consoles",
    "video_games",
    "toys",
    "watches",
    "jewelry",
    "beauty",
)
CONDICIONES = ("new", "open_box", "refurbished", "used", "for_parts")
VENDEDORES = ("comercio", "externo", "particular", "desconocido")
MODOS_COMPRA = ("envio", "recoleccion", "tienda", "particular")
ESTADOS_DISPONIBILIDAD = (
    "in_stock_confirmed",
    "in_stock",
    "limited_stock",
    "unconfirmed",
    "out_of_stock",
    "listed",
)
IDENTIFICACIONES = ("confirmed", "unconfirmed")
VERSIONES_CONTRATO = ("3.1", "3.0")
TIPOS_REGISTRO = (
    "observation",
    "local_comparable",
    "local_estimate",
    "msrp",
    "local_demand",
    "store_visit",
    "actual_result",
    "client_request",
)
RESULTADOS = (
    "RECHAZADA_VALIDACION",
    "DESCARTADA",
    "SOLO_REFERENCIA",
    "REVISION_MANUAL",
    "SIN_NIVEL",
    "NIVEL_ASIGNADO",
)
MOTIVOS_RECHAZO = (
    "PRECIO INVÁLIDO",
    "DOMINIO NO AUTORIZADO",
    "CAMPO OBLIGATORIO FALTANTE (exchangeRate)",
    "CAMPO OBLIGATORIO FALTANTE (availability.state)",
    "CIUDAD NO CONFIGURADA",
    "TIPO DE REGISTRO DESCONOCIDO",
)
MOTIVOS = (
    "EVITAR",
    "MERCADO YA BARATO",
    "SIN CANAL DISPONIBLE",
    "MARGEN NEGATIVO",
    "SOLO REFERENCIA",
    "SIN HISTORIAL SUFICIENTE",
    "SIN REFERENCIA DE USADOS",
    "COINCIDENCIA NO CONFIRMADA",
    "VENDEDOR EXTERNO",
    "PARTICULAR",
    "RIESGO DE PROCEDENCIA",
    "DEMANDA DESCONOCIDA",
)
CAUSAS_CERRADO = (
    "SIN PRECIO DE VENTA EN AMAZON",
    "DEMANDA INSUFICIENTE EN AMAZON",
    "NO VENDIBLE EN AMAZON (POR AHORA)",
    "COMISIÓN DESCONOCIDA",
    "TASA DE DEVOLUCIÓN DESCONOCIDA",
    "ENVÍO POR COTIZAR",
    "PRODUCTO NO NUEVO",
    "SIN ROTACIÓN",
    "DEMANDA LOCAL BAJA",
    "SIN PRECIO LOCAL",
)
CAUSAS_POR_REVISAR = ("DEMANDA DESCONOCIDA", "SIN REFERENCIA DE USADOS")
ESTADOS_CANAL = ("CERRADO", "POR_REVISAR", "DISPONIBLE")
CANALES = ("amazon", "local")
NIVELES = ("COMPRAR_YA", "MUY_RECOMENDABLE", "RECOMENDABLE", "VIGILAR")
CALIDADES = (
    "OFERTA_EXCEPCIONAL",
    "BUENA_OFERTA",
    "PRECIO_COMPETITIVO",
    "DESCUENTO_CUESTIONABLE",
    "PRECIO_NORMAL",
    "NO_APLICA",
)
CONFIANZAS = ("ALTA", "MEDIA", "BAJA")
DEMANDAS_LOCALES = ("high", "medium", "low")
REFERENCIAS = (
    "precio_habitual",
    "precio_mercado_hoy",
    "minimo_60_dias_amazon",
    "precio_venta_amazon",
)
MONEDAS = ("USD", "MXN")
RESULTADOS_VISITA = ("found", "not_found", "different_price", "confirmed_by_call")
MODALIDADES = ("link_only", "buy_and_deliver")
FORMATOS = ("jsonl", "csv")
CLASES_IDENTIFICADOR = ("gtin", "brand_model", "retailer_sku", "asin")
ORIGENES = ("file", "worker")


# --- 1. Metadatos, sin base -----------------------------------------------------------


def test_tab01_a_tab11_y_la_vista_tab12_existen_y_nada_mas():
    assert set(tablas.metadata.tables) == set(COLUMNAS)
    assert "open_opportunity" not in tablas.metadata.tables
    assert "open_opportunity" in tablas.metadata_vistas.tables


@pytest.mark.parametrize("nombre", sorted(COLUMNAS))
def test_columnas_de_cada_tabla_son_las_de_design(nombre):
    assert {c.name for c in tablas.metadata.tables[nombre].columns} == COLUMNAS[nombre]


@pytest.mark.parametrize("nombre", sorted(CLAVES))
def test_claves_primarias(nombre):
    clave = tuple(c.name for c in tablas.metadata.tables[nombre].primary_key.columns)
    assert clave == CLAVES[nombre]


def _numeric(tabla: str, columna: str) -> tuple[int | None, int | None]:
    tipo = tablas.metadata.tables[tabla].c[columna].type
    assert isinstance(tipo, Numeric), f"{tabla}.{columna} no es numeric: {tipo!r}"
    assert type(tipo).__name__ == "Numeric", f"{tabla}.{columna} es {type(tipo).__name__}"
    assert tipo.asdecimal is True
    return tipo.precision, tipo.scale


@pytest.mark.parametrize(("tabla", "columna"), sorted(MONTOS))
def test_montos_numeric_12_2(tabla, columna):
    assert _numeric(tabla, columna) == (12, 2)


#: ``0004_price_usd_sin_escala`` deja ``price_usd`` en ``numeric`` sin escala (DEC-258, T08a):
#: en ``head`` ya no es (14,4); en ``0001_esquema`` sí (lo comprueba la prueba de integración).
CAMBIADAS_0004 = {("local_comparable", "price_usd")}


@pytest.mark.parametrize(("tabla", "columna"), sorted(CONVERSIONES - CAMBIADAS_0004))
def test_conversiones_y_medianas_numeric_14_4(tabla, columna):
    assert _numeric(tabla, columna) == (14, 4)


@pytest.mark.parametrize(("tabla", "columna"), sorted(CAMBIADAS_0004))
def test_price_usd_sin_escala_en_head(tabla, columna):
    assert _numeric(tabla, columna) == (None, None)


@pytest.mark.parametrize(("tabla", "columna"), sorted(SIN_ESCALA))
def test_porcentajes_y_descuentos_sin_escala(tabla, columna):
    assert _numeric(tabla, columna) == (None, None)


def test_ninguna_columna_float_real_o_double():
    for tabla in tablas.metadata.tables.values():
        for columna in tabla.columns:
            tipo = columna.type.compile(dialect=DIALECTO).upper()
            assert not re.search(r"FLOAT|REAL|DOUBLE", tipo), f"{tabla.name}.{columna.name}"


def test_load_rejection_solo_carga_renglon_tipo_motivo_y_campo():
    # R-20, DEC-181, design.md TAB-02 y §16: sin el contenido del renglón.
    columnas = {c.name for c in tablas.load_rejection.columns}
    assert columnas == {"load_run_id", "line_number", "record_type", "reason", "field"}
    sospechosas = re.compile(r"raw|line$|content|payload|row|data|body|text|json")
    for tabla in (tablas.load_rejection, tablas.load_run):
        for columna in tabla.columns:
            assert not sospechosas.search(columna.name), f"{tabla.name}.{columna.name}"


def test_client_request_sin_notas_ni_texto_libre():
    # RNF-11 y CTR-04 ("Sin campo de notas").
    columnas = {c.name for c in tablas.client_request.columns}
    assert not {n for n in columnas if re.search(r"note|comment|descr|text|message", n)}
    assert columnas - _COMUNES == {
        "client_alias",
        "items",
        "quantity",
        "accepted_conditions",
        "modality",
        "postal_code",
        "date",
    }


def test_hypertables_tab05_a_tab07():
    assert set(tablas.HYPERTABLES) == {
        "price_observation",
        "availability_observation",
        "amazon_listing_observation",
    }


# --- 2. Estáticas: URL, credenciales y saltos ------------------------------------------

_CREDENCIAL_EN_URL = re.compile(r"[a-z][a-z0-9+.-]*://[^\s/:@'\"`]+:[^\s/@'\"`]+@")


def test_sin_url_con_credenciales_en_el_repo():
    excluidos = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache"}
    hallazgos = []
    for ruta in RAIZ.rglob("*"):
        if excluidos & set(ruta.relative_to(RAIZ).parts) or not ruta.is_file():
            continue
        if ruta.suffix in {".png", ".jpg", ".ico", ".pdf", ".pyc"} or ruta.name == ".coverage":
            continue
        contenido = ruta.read_text(encoding="utf-8", errors="ignore")
        if _CREDENCIAL_EN_URL.search(contenido):
            hallazgos.append(str(ruta.relative_to(RAIZ)))
    assert hallazgos == []


def test_alembic_ini_y_env_sin_url_ni_contrasena():
    ini = (RAIZ / "alembic.ini").read_text(encoding="utf-8")
    assert not re.search(r"^\s*sqlalchemy\.url\s*=", ini, re.MULTILINE)
    assert "postgresql" not in ini.lower().replace("# ", "")  # solo en comentarios
    env = (RAIZ / "migrations" / "env.py").read_text(encoding="utf-8")
    assert "://" not in env
    assert not re.search(r"password\s*=", env, re.IGNORECASE)


def test_alembic_no_muestra_la_url_ni_la_contrasena_si_no_conecta(tmp_path):
    # RNF-8: "Nunca se registra la URL completa". Socket inexistente: no sale a la red.
    clave = "ClaveFalsa" + "T05x"
    url = "postgresql+psycopg://oip:" + clave + "@/oip_no_existe?host=" + str(tmp_path)
    entorno = {k: v for k, v in os.environ.items() if k not in {_VARIABLE}}
    entorno["OIP_DATABASE_URL"] = url
    salida = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=RAIZ,
        env=entorno,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert salida.returncode != 0
    assert clave not in salida.stdout + salida.stderr
    assert url not in salida.stdout + salida.stderr


def test_las_de_integracion_se_saltan_sin_la_variable():
    entorno = {k: v for k, v in os.environ.items() if k != _VARIABLE}
    salida = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-m",
            "integracion",
            "tests/test_migraciones_integracion.py",
            "tests/test_t05_tester.py",
        ],
        cwd=RAIZ,
        env=entorno,
        capture_output=True,
        text=True,
        timeout=300,
    )
    resumen = salida.stdout.strip().splitlines()[-1]
    assert salida.returncode == 0, salida.stdout[-2000:]
    assert "skipped" in resumen
    assert "passed" not in resumen and "failed" not in resumen and "error" not in resumen


# --- 3. Integración contra PostgreSQL (sin TimescaleDB) ---------------------------------


def _url():
    valor = os.environ.get(_VARIABLE, "").strip()
    if not valor:
        pytest.skip(f"sin {_VARIABLE}: las pruebas de integración se saltan (DEC-233)")
    url = make_url(valor)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    return url


def _limpiar(motor) -> None:
    nombres = ", ".join([*tablas.metadata.tables, "alembic_version"])
    with motor.begin() as conexion:
        conexion.execute(text("DROP VIEW IF EXISTS open_opportunity"))
        conexion.execute(text(f"DROP TABLE IF EXISTS {nombres} CASCADE"))


@pytest.fixture
def motor():
    motor = create_engine(_url())
    _limpiar(motor)
    try:
        yield motor
    finally:
        _limpiar(motor)
        motor.dispose()


def _alembic(motor, accion: str, revision: str) -> None:
    from alembic import command
    from alembic.config import Config

    with motor.begin() as conexion:
        config = Config(str(RAIZ / "alembic.ini"))
        config.attributes["connection"] = conexion
        getattr(command, accion)(config, revision)


def _con_timescale(motor) -> None:
    with motor.connect() as conexion:
        hay = conexion.execute(
            text("SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb'")
        ).first()
    if hay is None:
        pytest.fail("la base de OIP_TEST_DATABASE_URL no tiene la extensión timescaledb")


def _catalogo(motor) -> dict[str, list]:
    """Foto del catálogo de PostgreSQL de las tablas y la vista de OIP."""
    nombres = sorted(tablas.metadata.tables)
    with motor.connect() as c:
        columnas = c.execute(
            text(
                "SELECT a.attrelid::regclass::text, a.attname,"
                " format_type(a.atttypid, a.atttypmod), a.attnotnull,"
                " pg_get_expr(d.adbin, d.adrelid)"
                " FROM pg_attribute a LEFT JOIN pg_attrdef d"
                "  ON d.adrelid = a.attrelid AND d.adnum = a.attnum"
                " WHERE a.attrelid::regclass::text = ANY(:n) AND a.attnum > 0"
                "  AND NOT a.attisdropped ORDER BY 1, 2"
            ),
            {"n": [*nombres, "open_opportunity"]},
        ).all()
        restricciones = c.execute(
            text(
                "SELECT conrelid::regclass::text, conname, contype::text,"
                " pg_get_constraintdef(oid) FROM pg_constraint"
                " WHERE conrelid::regclass::text = ANY(:n) ORDER BY 1, 2"
            ),
            {"n": nombres},
        ).all()
        indices = c.execute(
            text(
                "SELECT tablename, indexname, indexdef FROM pg_indexes"
                " WHERE schemaname = current_schema() AND tablename = ANY(:n) ORDER BY 1, 2"
            ),
            {"n": nombres},
        ).all()
        vista = c.execute(text("SELECT pg_get_viewdef('open_opportunity'::regclass)")).all()
    return {
        "columnas": columnas,
        "restricciones": restricciones,
        "indices": indices,
        "vista": vista,
    }


@pytest.mark.integracion
def test_0001_y_el_modelo_dan_el_mismo_catalogo_de_postgresql(motor):
    # Independiente de autogenerate: compara también los CHECK y el índice con coalesce.
    _alembic(motor, "upgrade", "0001_esquema")
    migracion = _catalogo(motor)
    _alembic(motor, "downgrade", "base")
    with motor.begin() as conexion:
        # El modelo tal como lo deja 0001 (sin lo que agrega 0003_registro_de_rechazo).
        tablas.metadata_0001.create_all(conexion)
        conexion.execute(text(f"CREATE VIEW open_opportunity AS {tablas.SQL_OPEN_OPPORTUNITY}"))
    modelo = _catalogo(motor)
    for parte in migracion:
        assert migracion[parte] == modelo[parte], parte


@pytest.mark.integracion
def test_downgrade_base_no_deja_nada(motor):
    _alembic(motor, "upgrade", "0001_esquema")
    _alembic(motor, "downgrade", "base")
    with motor.connect() as c:
        quedan = (
            c.execute(
                text(
                    "SELECT relname FROM pg_class"
                    " WHERE relnamespace = current_schema()::regnamespace"
                    " AND relkind IN ('r', 'v', 'S', 'i') AND relname <> 'alembic_version'"
                    " AND relname NOT LIKE 'alembic_version%'"
                )
            )
            .scalars()
            .all()
        )
    assert quedan == []


@pytest.mark.integracion
def test_en_la_base_ninguna_columna_es_float_y_los_numeric_son_los_de_design(motor):
    _alembic(motor, "upgrade", "0001_esquema")
    with motor.connect() as c:
        filas = c.execute(
            text(
                "SELECT table_name, column_name, data_type, numeric_precision, numeric_scale"
                " FROM information_schema.columns WHERE table_schema = current_schema()"
                " AND table_name = ANY(:n)"
            ),
            {"n": list(tablas.metadata.tables)},
        ).all()
    assert not [f for f in filas if f.data_type in {"real", "double precision"}]
    numericas = {
        (f.table_name, f.column_name): (f.numeric_precision, f.numeric_scale)
        for f in filas
        if f.data_type == "numeric"
    }
    esperado = {
        **{k: (12, 2) for k in MONTOS},
        **{k: (14, 4) for k in CONVERSIONES},
        **{k: (None, None) for k in SIN_ESCALA},
    }
    assert numericas == esperado
    tiempos = {f.data_type for f in filas if "time" in f.data_type}
    assert tiempos == {"timestamp with time zone"}


@pytest.mark.integracion
def test_claves_primarias_e_indices_de_design_en_la_base(motor):
    _alembic(motor, "upgrade", "0001_esquema")
    with motor.connect() as c:
        claves = dict(
            c.execute(
                text(
                    "SELECT conrelid::regclass::text, pg_get_constraintdef(oid) FROM pg_constraint"
                    " WHERE contype = 'p' AND conrelid::regclass::text = ANY(:n)"
                ),
                {"n": list(CLAVES)},
            ).all()
        )
        definiciones = c.execute(
            text("SELECT tablename, indexdef FROM pg_indexes WHERE schemaname = current_schema()")
        ).all()
    for tabla, columnas in CLAVES.items():
        assert claves[tabla] == f"PRIMARY KEY ({', '.join(columnas)})", tabla
    presentes = set()
    for tabla, definicion in definiciones:
        cuerpo = re.sub(r"^CREATE (UNIQUE )?INDEX \S+ ON \S+ USING btree ", "", definicion)
        presentes.add((tabla, ("UNIQUE " if " UNIQUE " in f" {definicion} " else "") + cuerpo))
    faltan = {i for i in INDICES if i not in presentes}
    assert faltan == set()


# Filas mínimas válidas (sintéticas). Cada llamada da identificadores nuevos.


def _huella() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex


def _base(c) -> dict[str, object]:
    cv = c.execute(
        text(
            "INSERT INTO config_version (version, sha256, schema_version, content, source_file,"
            " loaded_at) VALUES ('2026-11-18.1', :h, '1', '{}', 'base.yaml', :t) RETURNING id"
        ),
        {"h": _huella(), "t": _T},
    ).scalar_one()
    carga, producto, publicacion, evaluacion = (uuid.uuid4() for _ in range(4))
    _insertar(
        c,
        "load_run",
        {
            "id": carga,
            "file_name": "capturas.jsonl",
            "file_sha256": _huella(),
            "format": "jsonl",
            "started_at": _T,
            "finished_at": _T,
            "loaded": 0,
            "rejected": 0,
            "duplicates": 0,
            "rejected_by_reason": {},
            "config_version_id": cv,
        },
    )
    _insertar(
        c,
        "product",
        {"id": producto, "brand": "Marca", "model": "M-1", "category": "tools", "created_at": _T},
    )
    _insertar(
        c,
        "listing",
        {
            "id": publicacion,
            "product_id": producto,
            "retailer_code": "comercio_x",
            "canonical_url": "https://example.com/p/1",
            "first_seen_at": _T,
        },
    )
    ids = {
        "cv": cv,
        "carga": carga,
        "producto": producto,
        "publicacion": publicacion,
        "evaluacion": evaluacion,
    }
    _insertar(c, "evaluation", _fila("evaluation", ids) | {"id": evaluacion})
    return ids


def _insertar(c, tabla: str, fila: dict[str, object]) -> None:
    c.execute(tablas.metadata.tables[tabla].insert().values(**fila))


def _captura(ids) -> dict[str, object]:
    return {
        "id": uuid.uuid4(),
        "load_run_id": ids["carga"],
        "idempotency_key": _huella(),
        "captured_at": _T,
    }


def _fila(tabla: str, ids) -> dict[str, object]:
    filas = {
        "load_run": lambda: {
            "id": uuid.uuid4(),
            "file_name": "local_comparable.csv",
            "file_sha256": _huella(),
            "format": "csv",
            "record_type": "local_comparable",
            "started_at": _T,
            "loaded": 0,
            "rejected": 0,
            "duplicates": 0,
            "rejected_by_reason": {},
            "config_version_id": ids["cv"],
        },
        "load_rejection": lambda: {
            "load_run_id": ids["carga"],
            "line_number": _renglon(),
            "record_type": "msrp",
            "reason": "PRECIO INVÁLIDO",
        },
        "product": lambda: {"id": uuid.uuid4(), "created_at": _T, "category": "tools"},
        "product_identifier": lambda: {
            "kind": "gtin",
            "value": uuid.uuid4().hex,
            "product_id": ids["producto"],
        },
        "price_observation": lambda: {
            "observation_id": uuid.uuid4(),
            "observed_at": _T,
            "listing_id": ids["publicacion"],
            "product_id": ids["producto"],
            "price": Decimal("29.00"),
            "seller": "comercio",
            "condition": "new",
            "purchase_mode": "envio",
            "category": "tools",
            "title": "Marca M-1",
            "identification": "confirmed",
            "schema_version": "3.1",
        },
        "availability_observation": lambda: {
            "observation_id": uuid.uuid4(),
            "observed_at": _T,
            "listing_id": ids["publicacion"],
            "state": "in_stock",
        },
        "ingest_receipt": lambda: {
            "idempotency_key": uuid.uuid4().hex,
            "observation_id": uuid.uuid4(),
            "source": "worker",
            "received_at": _T,
        },
        "local_comparable": lambda: (
            _captura(ids)
            | {
                "product_id": ids["producto"],
                "condition": "used",
                "asking_price": Decimal("50.00"),
                "currency": "USD",
                "price_usd": Decimal("50.0000"),
                "city": "tijuana",
                "date": _D,
                "sold": False,
            }
        ),
        "local_estimate": lambda: (
            _captura(ids)
            | {
                "product_id": ids["producto"],
                "price": Decimal("40.00"),
                "date": _D,
            }
        ),
        "local_demand": lambda: _captura(ids) | {"category": "tools", "level": "high", "date": _D},
        "store_visit": lambda: (
            _captura(ids)
            | {
                "store_code": "S1",
                "product_id": ids["producto"],
                "result": "found",
                "visited_at": _T,
            }
        ),
        "opportunity_outcome": lambda: (
            _captura(ids)
            | {
                "evaluation_id": uuid.uuid4(),
                "channel": "amazon",
                "units": 1,
                "purchase_price": Decimal("10.00"),
                "sale_price": Decimal("20.00"),
                "actual_costs": Decimal("1.00"),
                "purchased_on": _D,
                "sold_on": _D,
            }
        ),
        "client_request": lambda: (
            _captura(ids)
            | {
                "client_alias": "cliente-sintetico",
                "items": ["M-1"],
                "quantity": 1,
                "accepted_conditions": ["new"],
                "modality": "link_only",
                "date": _D,
            }
        ),
        "evaluation": lambda: {
            "id": uuid.uuid4(),
            "evaluated_at": _T,
            "offer_observation_id": uuid.uuid4(),
            "listing_id": ids["publicacion"],
            "product_id": ids["producto"],
            "config_version_id": ids["cv"],
            "rn_versions": {"RN-001": "1.0"},
            "result": "SIN_NIVEL",
            "reasons": [],
            "marks": [],
            "observations_used": [],
            "changed_references": [],
            "no_longer_recommended": False,
        },
        "evaluation_channel": lambda: {
            "evaluation_id": _evaluacion_nueva(ids),
            "channel": "amazon",
            "state": "DISPONIBLE",
            "closed_causes": [],
            "review_causes": [],
            "marks": [],
        },
    }
    return filas[tabla]()


_RENGLONES = iter(range(1, 10_000_000))


def _renglon() -> int:
    return next(_RENGLONES)


_CONEXION: list = []


def _evaluacion_nueva(ids) -> uuid.UUID:
    nueva = _fila("evaluation", ids)
    _insertar(_CONEXION[0], "evaluation", nueva)
    return nueva["id"]


def _acepta(c, tabla, ids, cambios) -> bool:
    fila = _fila(tabla, ids) | cambios
    try:
        with c.begin_nested():
            _insertar(c, tabla, fila)
    except IntegrityError:
        return False
    return True


def _ajustes(tabla: str, columna: str, valor) -> dict[str, object]:
    """Cambios mínimos para que solo la columna probada decida (invariantes de TAB-10)."""
    if tabla == "evaluation" and columna == "result":
        if valor == "RECHAZADA_VALIDACION":
            return {"rejection_reason": "PRECIO INVÁLIDO", "offer_observation_id": None}
        if valor == "NIVEL_ASIGNADO":
            return {
                "alert_level": "RECOMENDABLE",
                "alert_channel": "amazon",
                "chosen_channel": "amazon",
            }
    if tabla == "evaluation" and columna == "main_reason":
        return {"reasons": [valor]}
    if tabla == "evaluation" and columna == "reasons" and valor:
        return {"main_reason": valor[0]}
    if tabla == "evaluation" and columna == "rejection_reason":
        return {"result": "RECHAZADA_VALIDACION", "offer_observation_id": None}
    if tabla == "evaluation" and columna in {"alert_level", "alert_channel"}:
        otra = {"alert_level": "RECOMENDABLE", "alert_channel": "amazon"}
        otra.pop(columna)
        return {"result": "NIVEL_ASIGNADO", "chosen_channel": "amazon", **otra}
    if tabla == "evaluation" and columna == "changed_references":
        return {"previous_evaluation_id": None} if not valor else {}
    if tabla == "load_run" and columna == "format" and valor == "jsonl":
        return {"record_type": None}
    if tabla == "local_comparable" and columna == "currency" and valor == "MXN":
        return {"exchange_rate": Decimal("17.5")}
    return {}


#: (tabla, columna, catálogo, es arreglo). Fuentes: design.md §4, §9, CTR-04; arquitectura §8.
CATALOGOS = [
    ("price_observation", "seller", VENDEDORES, False),
    ("price_observation", "condition", CONDICIONES, False),
    ("price_observation", "purchase_mode", MODOS_COMPRA, False),
    ("price_observation", "category", CATEGORIAS, False),
    ("price_observation", "identification", IDENTIFICACIONES, False),
    ("price_observation", "schema_version", VERSIONES_CONTRATO, False),
    ("availability_observation", "state", ESTADOS_DISPONIBILIDAD, False),
    ("load_run", "format", FORMATOS, False),
    ("load_run", "record_type", TIPOS_REGISTRO, False),
    ("load_rejection", "record_type", TIPOS_REGISTRO, False),
    ("load_rejection", "reason", MOTIVOS_RECHAZO, False),
    ("product", "category", CATEGORIAS, False),
    ("product_identifier", "kind", CLASES_IDENTIFICADOR, False),
    ("ingest_receipt", "source", ("worker",), False),
    ("local_comparable", "condition", CONDICIONES, False),
    ("local_comparable", "currency", MONEDAS, False),
    ("local_estimate", "condition", CONDICIONES, False),
    ("local_demand", "category", CATEGORIAS, False),
    ("local_demand", "level", DEMANDAS_LOCALES, False),
    ("store_visit", "result", RESULTADOS_VISITA, False),
    ("opportunity_outcome", "channel", CANALES, False),
    ("client_request", "modality", MODALIDADES, False),
    ("client_request", "accepted_conditions", CONDICIONES, True),
    ("evaluation", "result", RESULTADOS, False),
    ("evaluation", "main_reason", MOTIVOS, False),
    ("evaluation", "reasons", MOTIVOS, True),
    ("evaluation", "rejection_reason", MOTIVOS_RECHAZO, False),
    ("evaluation", "price_quality", CALIDADES, False),
    ("evaluation", "confidence", CONFIANZAS, False),
    ("evaluation", "identification", IDENTIFICACIONES, False),
    ("evaluation", "chosen_channel", CANALES, False),
    ("evaluation", "alert_level", NIVELES, False),
    ("evaluation", "alert_channel", CANALES, False),
    ("evaluation", "changed_references", REFERENCIAS, True),
    ("evaluation_channel", "channel", CANALES, False),
    ("evaluation_channel", "state", ESTADOS_CANAL, False),
    ("evaluation_channel", "closed_causes", CAUSAS_CERRADO, True),
    ("evaluation_channel", "review_causes", CAUSAS_POR_REVISAR, True),
    ("evaluation_channel", "level", NIVELES, False),
    ("evaluation_channel", "calculated_level", NIVELES, False),
]


def _fuera(valor: str) -> list[str]:
    return sorted({"", " ", valor + " ", " " + valor, valor.swapcase(), "OTRO_CODIGO"} - {valor})


@pytest.mark.integracion
@pytest.mark.parametrize(
    ("tabla", "columna", "catalogo", "arreglo"),
    CATALOGOS,
    ids=[f"{t}.{c}" for t, c, _, _ in CATALOGOS],
)
def test_check_acepta_el_catalogo_y_rechaza_lo_de_fuera(motor, tabla, columna, catalogo, arreglo):
    _alembic(motor, "upgrade", "0001_esquema")
    with motor.begin() as c:
        _CONEXION[:] = [c]
        ids = _base(c)
        if tabla == "evaluation" and columna == "changed_references":
            ids_prev = {"previous_evaluation_id": ids["evaluacion"]}
        else:
            ids_prev = {}

        def caso(valor):
            return {columna: valor} | _ajustes(tabla, columna, valor) | (ids_prev if valor else {})

        rechazados_validos = []
        for valor in catalogo:
            v = [valor] if arreglo else valor
            if not _acepta(c, tabla, ids, caso(v)):
                rechazados_validos.append(valor)
        aceptados_invalidos = []
        for valor in catalogo:
            for malo in _fuera(valor):
                v = [catalogo[0], malo] if arreglo else malo
                if _acepta(c, tabla, ids, caso(v)):
                    aceptados_invalidos.append(malo)
        if arreglo:
            for malo in ([None], [catalogo[0], None]):
                if _acepta(c, tabla, ids, caso(malo)):
                    aceptados_invalidos.append(repr(malo))
        _CONEXION.clear()
    assert rechazados_validos == []
    assert aceptados_invalidos == []


@pytest.mark.integracion
def test_ingest_receipt_file_exige_la_carga(motor):
    _alembic(motor, "upgrade", "0001_esquema")
    with motor.begin() as c:
        ids = _base(c)
        assert not _acepta(c, "ingest_receipt", ids, {"source": "file"})
        assert _acepta(c, "ingest_receipt", ids, {"source": "file", "load_run_id": ids["carga"]})


@pytest.mark.integracion
def test_load_rejection_no_admite_valores_del_renglon(motor):
    # R-20: solo el nombre del campo; un valor (teléfono, nombre, texto) se rechaza.
    _alembic(motor, "upgrade", "0001_esquema")
    with motor.begin() as c:
        ids = _base(c)
        for campo in ("exchangeRate", "availability.state", "price.current", "condition"):
            assert _acepta(c, "load_rejection", ids, {"field": campo}), campo
        for valor in (
            "664 123 4567",
            "Juan Pérez",
            "precio: 29.00",
            "",
            " ",
            "https://example.com/p/1",
            "a@example.com",
        ):
            assert not _acepta(c, "load_rejection", ids, {"field": valor}), valor
        for motivo in (
            "CAMPO OBLIGATORIO FALTANTE",
            "CAMPO OBLIGATORIO FALTANTE ()",
            "CAMPO OBLIGATORIO FALTANTE (664 123 4567)",
            "PRECIO INVÁLIDO: 0.00",
            "precio inválido",
        ):
            assert not _acepta(c, "load_rejection", ids, {"reason": motivo}), motivo


@pytest.mark.integracion
def test_unicos_de_idempotencia_en_la_base(motor):
    _alembic(motor, "upgrade", "0001_esquema")
    with motor.begin() as c:
        ids = _base(c)
        recibo = _fila("ingest_receipt", ids)
        assert _acepta(c, "ingest_receipt", ids, recibo)
        assert not _acepta(c, "ingest_receipt", ids, {"idempotency_key": recibo["idempotency_key"]})
        for captura in (
            "local_comparable",
            "local_estimate",
            "local_demand",
            "store_visit",
            "opportunity_outcome",
            "client_request",
        ):
            huella = _huella()
            assert _acepta(c, captura, ids, {"idempotency_key": huella}), captura
            assert not _acepta(c, captura, ids, {"idempotency_key": huella}), captura
            # La huella es un sha256 en hexadecimal: otra cosa no se guarda.
            assert not _acepta(c, captura, ids, {"idempotency_key": "x" * 64}), captura
        # listing: una tienda nula cuenta como la misma publicación (coalesce).
        with pytest.raises(IntegrityError), c.begin_nested():
            _insertar(
                c,
                "listing",
                {
                    "id": uuid.uuid4(),
                    "product_id": ids["producto"],
                    "retailer_code": "comercio_x",
                    "canonical_url": "https://example.com/p/1",
                    "first_seen_at": _T,
                },
            )
        # La misma observación (id y hora) dos veces choca con su clave primaria.
        observacion = _fila("price_observation", ids)
        assert _acepta(c, "price_observation", ids, observacion)
        assert not _acepta(
            c,
            "price_observation",
            ids,
            {
                "observation_id": observacion["observation_id"],
                "observed_at": _T,
            },
        )


@pytest.mark.integracion
def test_montos_vuelven_como_decimal_exacto(motor):
    _alembic(motor, "upgrade", "0001_esquema")
    with motor.begin() as c:
        ids = _base(c)
        fila = _fila("price_observation", ids) | {
            "price": Decimal("76.61"),
            "was_price": Decimal("100.15"),
        }
        _insertar(c, "price_observation", fila)
        precio, antes = c.execute(
            text("SELECT price, was_price FROM price_observation WHERE observation_id = :o"),
            {"o": fila["observation_id"]},
        ).one()
    assert (precio, antes) == (Decimal("76.61"), Decimal("100.15"))
    assert type(precio) is Decimal


# --- 4. Integración que necesita TimescaleDB (pendiente de Jesús, DEC-233) --------------


@pytest.mark.integracion
def test_0002_revertida_deja_exactamente_lo_que_crea_0001(motor):
    _con_timescale(motor)
    _alembic(motor, "upgrade", "0001_esquema")
    antes = _catalogo(motor)
    _alembic(motor, "upgrade", "head")
    _alembic(motor, "downgrade", "0001_esquema")
    despues = _catalogo(motor)
    for parte in antes:
        assert antes[parte] == despues[parte], parte


@pytest.mark.integracion
def test_las_hypertables_conservan_los_check_y_la_clave(motor):
    _con_timescale(motor)
    _alembic(motor, "upgrade", "head")
    with motor.begin() as c:
        _CONEXION[:] = [c]
        ids = _base(c)
        observacion = _fila("price_observation", ids)
        assert _acepta(c, "price_observation", ids, observacion)
        assert not _acepta(
            c,
            "price_observation",
            ids,
            {
                "observation_id": observacion["observation_id"],
                "observed_at": _T,
            },
        )
        assert not _acepta(c, "price_observation", ids, {"seller": "OTRO_CODIGO"})
        assert not _acepta(c, "availability_observation", ids, {"state": "OTRO_CODIGO"})
        _CONEXION.clear()
