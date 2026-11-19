"""Pruebas sin base de los metadatos de SQLAlchemy (CMP-19; design.md §4; tasks.md T05).

Lo que se puede comprobar sin PostgreSQL: que existen TAB-01 a TAB-12, las claves
primarias con el tiempo, los tipos ``numeric`` (sin ``float``), los ``CHECK`` derivados de
los catálogos cerrados, los únicos de idempotencia y que ninguna tabla guarda el contenido
de un renglón rechazado ni notas del cliente. Que la base los **aplica** lo prueban las
pruebas de integración (``tests/test_migraciones_integracion.py``).
"""

from __future__ import annotations

import re
from enum import StrEnum

import pytest
from sqlalchemy import CheckConstraint, Float, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex

from oip import catalogos as cat
from oip.entradas.capturas import Modalidad, Moneda, ResultadoVisita
from oip.persistencia import tablas

TABLAS_POR_ID = {
    "TAB-01": ("config_version",),
    "TAB-02": ("load_run", "load_rejection"),
    "TAB-03": ("product", "product_identifier"),
    "TAB-04": ("listing",),
    "TAB-05": ("price_observation",),
    "TAB-06": ("availability_observation",),
    "TAB-07": ("amazon_listing_observation",),
    "TAB-08": ("ingest_receipt",),
    "TAB-09": (
        "local_comparable",
        "local_estimate",
        "msrp_capture",
        "local_demand",
        "store_visit",
        "opportunity_outcome",
        "client_request",
    ),
    "TAB-10": ("evaluation",),
    "TAB-11": ("evaluation_channel",),
}
CAPTURAS = TABLAS_POR_ID["TAB-09"]
DIALECTO = postgresql.dialect()


def _tabla(nombre: str):
    return tablas.metadata.tables[nombre]


def _check(nombre_tabla: str, nombre: str) -> str:
    completo = f"ck_{nombre_tabla}_{nombre}"
    for restriccion in _tabla(nombre_tabla).constraints:
        if isinstance(restriccion, CheckConstraint) and restriccion.name == completo:
            return str(restriccion.sqltext)
    raise AssertionError(f"falta el CHECK {completo}")


def test_existen_tab01_a_tab11_y_nada_mas():
    esperadas = {t for nombres in TABLAS_POR_ID.values() for t in nombres}
    assert set(tablas.metadata.tables) == esperadas


def test_tab12_es_una_vista_fuera_de_los_metadatos_de_tablas():
    assert "open_opportunity" not in tablas.metadata.tables
    vista = tablas.metadata_vistas.tables["open_opportunity"]
    assert [c.name for c in vista.columns] == [c.name for c in tablas.evaluation.columns]
    sql = tablas.SQL_OPEN_OPPORTUNITY
    assert "DISTINCT ON (listing_id)" in sql
    assert "ORDER BY listing_id, evaluated_at DESC, id DESC" in sql
    # El código del resultado va escrito tal cual: debe ser el del catálogo.
    assert f"latest.result = '{cat.Resultado.NIVEL_ASIGNADO.value}'" in sql


@pytest.mark.parametrize("nombre", tablas.HYPERTABLES)
def test_hypertables_con_el_tiempo_en_la_clave_primaria(nombre):
    clave = [c.name for c in _tabla(nombre).primary_key.columns]
    assert clave == ["observation_id", "observed_at"]
    assert _tabla(nombre).c.observed_at.type.timezone is True


def test_las_hypertables_son_tab05_a_tab07_con_chunk_de_7_dias():
    assert tablas.HYPERTABLES == (
        "price_observation",
        "availability_observation",
        "amazon_listing_observation",
    )
    assert tablas.INTERVALO_CHUNK == "7 days"


def test_ninguna_columna_es_float_y_los_tiempos_llevan_zona():
    for tabla in tablas.metadata.tables.values():
        for columna in tabla.columns:
            assert not isinstance(columna.type, Float), f"{tabla.name}.{columna.name}"
            if isinstance(columna.type, Numeric):
                assert columna.type.asdecimal is True, f"{tabla.name}.{columna.name}"
            if columna.type.__class__.__name__ == "DateTime":
                assert columna.type.timezone is True, f"{tabla.name}.{columna.name}"


MONTOS = {
    "price_observation": ("price", "was_price", "shipping_to_me", "msrp_value"),
    "amazon_listing_observation": ("buy_box_price",),
    "local_comparable": ("asking_price",),
    "local_estimate": ("price",),
    "msrp_capture": ("value",),
    "opportunity_outcome": ("purchase_price", "sale_price", "actual_costs"),
    "evaluation": ("purchase_cost",),
    "evaluation_channel": (
        "selling_cost",
        "net_margin",
        "returns_cost",
        "drop_penalty",
        "adjusted_margin",
        "total_profit",
    ),
}
CONVERSIONES = {"local_comparable": ("price_usd",), "evaluation_channel": ("sale_price",)}
SIN_REDONDEAR = {
    "evaluation": ("advertised_discount", "real_discount"),
    "evaluation_channel": (
        "net_margin_pct",
        "adjusted_margin_pct",
        "monthly_yield_pct",
        "days_to_recover",
    ),
    "local_comparable": ("exchange_rate",),
    "price_observation": ("weight_kg",),
}


def _pares(mapa):
    return [(t, c) for t, columnas in mapa.items() for c in columnas]


@pytest.mark.parametrize(("tabla", "columna"), _pares(MONTOS))
def test_montos_numeric_12_2(tabla, columna):
    tipo = _tabla(tabla).c[columna].type
    assert isinstance(tipo, Numeric)
    assert (tipo.precision, tipo.scale) == (12, 2)


@pytest.mark.parametrize(("tabla", "columna"), _pares(CONVERSIONES))
def test_conversiones_y_medianas_numeric_14_4(tabla, columna):
    tipo = _tabla(tabla).c[columna].type
    assert (tipo.precision, tipo.scale) == (14, 4)


@pytest.mark.parametrize(("tabla", "columna"), _pares(SIN_REDONDEAR))
def test_porcentajes_y_descuentos_numeric_sin_escala(tabla, columna):
    # Sin redondear (DEC-207): PostgreSQL no recorta un numeric sin precisión ni escala.
    tipo = _tabla(tabla).c[columna].type
    assert isinstance(tipo, Numeric)
    assert (tipo.precision, tipo.scale) == (None, None)


def test_toda_columna_numeric_esta_clasificada():
    clasificadas = set(_pares(MONTOS)) | set(_pares(CONVERSIONES)) | set(_pares(SIN_REDONDEAR))
    numericas = {
        (t.name, c.name)
        for t in tablas.metadata.tables.values()
        for c in t.columns
        if isinstance(c.type, Numeric)
    }
    assert numericas == clasificadas


# --- CHECK contra los catálogos (derivados de los enums) --------------------------------

CATALOGOS = [
    ("load_run", "format", tablas.FORMATOS_CARGA),
    ("load_run", "record_type", cat.TipoRegistro),
    ("load_rejection", "record_type", cat.TipoRegistro),
    ("product", "category", cat.Categoria),
    ("product_identifier", "kind", tablas.CLASES_IDENTIFICADOR),
    ("price_observation", "seller", cat.Vendedor),
    ("price_observation", "condition", cat.Condicion),
    ("price_observation", "purchase_mode", cat.ModoCompra),
    ("price_observation", "category", cat.Categoria),
    ("price_observation", "identification", cat.Identificacion),
    ("price_observation", "schema_version", ("3.1", "3.0")),
    ("availability_observation", "state", cat.EstadoDisponibilidad),
    ("ingest_receipt", "source", tablas.ORIGENES_RECIBO),
    ("local_comparable", "condition", cat.Condicion),
    ("local_comparable", "currency", Moneda),
    ("local_estimate", "condition", cat.Condicion),
    ("local_demand", "category", cat.Categoria),
    ("local_demand", "level", cat.DemandaLocal),
    ("store_visit", "result", ResultadoVisita),
    ("opportunity_outcome", "channel", cat.Canal),
    ("client_request", "modality", Modalidad),
    ("evaluation", "result", cat.Resultado),
    ("evaluation", "main_reason", cat.Motivo),
    ("evaluation", "price_quality", cat.CalidadPrecio),
    ("evaluation", "confidence", cat.Confianza),
    ("evaluation", "identification", cat.Identificacion),
    ("evaluation", "chosen_channel", cat.Canal),
    ("evaluation", "alert_level", cat.Nivel),
    ("evaluation", "alert_channel", cat.Canal),
    ("evaluation_channel", "channel", cat.Canal),
    ("evaluation_channel", "state", cat.EstadoCanal),
    ("evaluation_channel", "level", cat.Nivel),
    ("evaluation_channel", "calculated_level", cat.Nivel),
]
CATALOGOS_ARREGLO = [
    ("client_request", "accepted_conditions", cat.Condicion),
    ("evaluation", "reasons", cat.Motivo),
    ("evaluation", "changed_references", cat.ReferenciaPrecio),
    ("evaluation_channel", "closed_causes", cat.CausaCanalCerrado),
    ("evaluation_channel", "review_causes", cat.CausaCanalPorRevisar),
]


def _literales(valores) -> str:
    return ", ".join(
        "'" + (v.value if isinstance(v, StrEnum) else v).replace("'", "''") + "'" for v in valores
    )


@pytest.mark.parametrize(("tabla", "columna", "catalogo"), CATALOGOS)
def test_check_de_catalogo(tabla, columna, catalogo):
    assert _check(tabla, f"{columna}_catalogo") == f"{columna} IN ({_literales(catalogo)})"


@pytest.mark.parametrize(("tabla", "columna", "catalogo"), CATALOGOS_ARREGLO)
def test_check_de_catalogo_en_arreglos(tabla, columna, catalogo):
    esperado = f"{columna} <@ ARRAY[{_literales(catalogo)}]::text[]"
    assert _check(tabla, f"{columna}_catalogo") == esperado


def test_check_de_catalogo_en_cada_columna_de_codigo():
    # Toda columna con nombre de código cerrado tiene su CHECK (ninguna se quedó sin él).
    con_check = {(t, c) for t, c, _ in CATALOGOS + CATALOGOS_ARREGLO}
    codigos = {
        "seller",
        "condition",
        "purchase_mode",
        "category",
        "identification",
        "state",
        "result",
        "channel",
        "level",
        "calculated_level",
        "format",
        "record_type",
        "kind",
        "source",
        "currency",
        "modality",
    }
    sin_check = {
        (t.name, c.name)
        for t in tablas.metadata.tables.values()
        for c in t.columns
        if c.name in codigos and (t.name, c.name) not in con_check
    }
    # Texto libre que no es un catálogo cerrado del REQ ni del contrato.
    assert sin_check == {("price_observation", "currency"), ("msrp_capture", "source")}


@pytest.mark.parametrize("tabla", ["load_rejection", "evaluation"])
def test_motivo_de_rechazo_con_el_campo_en_el_archivo(tabla):
    columna = "reason" if tabla == "load_rejection" else "rejection_reason"
    sql = _check(tabla, f"{columna}_catalogo")
    patron = re.search(r"~ '(.+)'$", sql).group(1)
    base = cat.MotivoRechazo.CAMPO_OBLIGATORIO_FALTANTE
    assert re.fullmatch(patron, cat.motivo_campo_faltante("exchangeRate"))
    assert re.fullmatch(patron, cat.motivo_campo_faltante("price.current"))
    assert not re.fullmatch(patron, base.value)
    assert not re.fullmatch(patron, f"{base.value} ()")
    for motivo in cat.MotivoRechazo:
        if motivo is not base:
            assert f"'{motivo.value}'" in sql


def test_texto_libre_sin_vacios():
    # Vacío = ausente: cada columna text sin catálogo rechaza '' y solo espacios.
    for tabla in tablas.metadata.tables.values():
        nombres = {r.name for r in tabla.constraints if isinstance(r, CheckConstraint)}
        for columna in tabla.columns:
            if type(columna.type) is Text:
                assert (
                    f"ck_{tabla.name}_{columna.name}_no_vacio" in nombres
                    or f"ck_{tabla.name}_{columna.name}_catalogo" in nombres
                ), f"{tabla.name}.{columna.name}"


# --- Idempotencia y claves --------------------------------------------------------------


def test_ingest_receipt_tiene_la_clave_de_idempotencia_como_primaria():
    assert [c.name for c in tablas.ingest_receipt.primary_key.columns] == ["idempotency_key"]


@pytest.mark.parametrize("nombre", CAPTURAS)
def test_cada_captura_tiene_huella_sha256_unica(nombre):
    tabla = _tabla(nombre)
    unicos = [
        [c.name for c in r.columns] for r in tabla.constraints if isinstance(r, UniqueConstraint)
    ]
    assert ["idempotency_key"] in unicos
    assert tabla.c.idempotency_key.type.length == 64
    assert not tabla.c.idempotency_key.nullable
    assert _check(nombre, "idempotency_key_sha256") == "idempotency_key ~ '^[0-9a-f]{64}$'"
    for columna in ("id", "load_run_id", "captured_at"):
        assert not tabla.c[columna].nullable


def test_config_version_unica_por_version_y_huella():
    unicos = {
        tuple(c.name for c in r.columns)
        for r in tablas.config_version.constraints
        if isinstance(r, UniqueConstraint)
    }
    assert unicos == {("version",), ("sha256",)}


def test_listing_unico_por_comercio_url_y_tienda():
    indice = next(i for i in tablas.listing.indexes if i.name == "uq_listing_retailer_url_store")
    assert indice.unique
    sql = str(CreateIndex(indice).compile(dialect=DIALECTO))
    assert "(retailer_code, canonical_url, coalesce(store_code, ''))" in sql


@pytest.mark.parametrize(
    ("tabla", "columnas"),
    [
        ("price_observation", "product_id, observed_at DESC"),
        ("price_observation", "listing_id, observed_at DESC"),
        ("availability_observation", "listing_id, observed_at DESC"),
        ("amazon_listing_observation", "product_id, observed_at DESC"),
        ("evaluation", "listing_id, evaluated_at DESC"),
        ("evaluation", "product_id, result"),
        ("local_comparable", "product_id, condition"),
        ("local_estimate", "product_id, condition"),
        ("local_demand", "category, date DESC"),
    ],
)
def test_indices_de_design(tabla, columnas):
    nombre = f"ix_{tabla}_" + "_".join(c.split()[0] for c in columnas.split(", "))
    encontrado = next(i for i in _tabla(tabla).indexes if i.name == nombre)
    assert f"({columnas})" in str(CreateIndex(encontrado).compile(dialect=DIALECTO))


def test_claves_compuestas():
    assert [c.name for c in tablas.load_rejection.primary_key.columns] == [
        "load_run_id",
        "line_number",
    ]
    assert [c.name for c in tablas.evaluation_channel.primary_key.columns] == [
        "evaluation_id",
        "channel",
    ]
    assert [c.name for c in tablas.product_identifier.primary_key.columns] == ["kind", "value"]


# --- Sin contenido de renglones ni datos personales -------------------------------------


def test_load_rejection_no_guarda_el_contenido_del_renglon():
    # R-20, DEC-181: solo carga, renglón, tipo, motivo y nombre del campo.
    assert [c.name for c in tablas.load_rejection.columns] == [
        "load_run_id",
        "line_number",
        "record_type",
        "reason",
        "field",
    ]
    assert _check("load_rejection", "field_nombre") == "field ~ '^[A-Za-z][A-Za-z0-9_.]*$'"


def test_load_run_no_guarda_renglones():
    assert {c.name for c in tablas.load_run.columns} == {
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
    }


def test_client_request_sin_notas_ni_texto_libre():
    # RNF-11: campos de CTR-04 más los comunes de TAB-09; sin notas.
    assert {c.name for c in tablas.client_request.columns} == {
        "id",
        "load_run_id",
        "idempotency_key",
        "captured_at",
        "client_alias",
        "items",
        "quantity",
        "accepted_conditions",
        "modality",
        "postal_code",
        "date",
    }


def test_ninguna_tabla_tiene_columnas_de_texto_libre_del_renglon():
    prohibidas = {"notes", "note", "description", "raw", "line", "payload", "evidence", "row"}
    for tabla in tablas.metadata.tables.values():
        assert not prohibidas & {c.name for c in tabla.columns}, tabla.name


def test_el_particular_es_un_listing_sin_tabla_propia():
    # DEC-223: retailer_code = 'particular'; sin private_listing.
    assert "private_listing" not in tablas.metadata.tables
    assert _check("listing", "solo_particular") == (
        f"retailer_code = '{cat.Vendedor.PARTICULAR.value}'"
        " OR (platform IS NULL AND pickup_location IS NULL)"
    )


# --- Invariantes del registro de evaluación (las de RegistroEvaluacion, T04) ------------


def test_invariantes_del_registro_de_evaluacion():
    rechazada = cat.Resultado.RECHAZADA_VALIDACION.value
    asignado = cat.Resultado.NIVEL_ASIGNADO.value
    assert _check("evaluation", "motivo_principal") == (
        "main_reason IS NOT DISTINCT FROM reasons[1]"
    )
    assert _check("evaluation", "rechazo_con_motivo") == (
        f"(result = '{rechazada}') = (rejection_reason IS NOT NULL)"
    )
    assert _check("evaluation", "rechazo_sin_oferta") == (
        f"result <> '{rechazada}' OR offer_observation_id IS NULL"
    )
    assert f"(result = '{asignado}') = (alert_level IS NOT NULL)" in _check(
        "evaluation", "aviso_solo_con_nivel"
    )


def test_evaluation_guarda_el_registro_de_req_7():
    columnas = {c.name for c in tablas.evaluation.columns}
    assert {
        "id",
        "evaluated_at",
        "observations_used",
        "price_quality",
        "marks",
        "reasons",
        "main_reason",
        "chosen_channel",
        "alert_level",
        "alert_channel",
        "result",
        "rn_versions",
        "config_version_id",
        "previous_evaluation_id",
        "changed_references",
        "no_longer_recommended",
        "input_snapshot",
    } <= columnas
    assert {"state", "closed_causes", "review_causes", "calculated_level"} <= {
        c.name for c in tablas.evaluation_channel.columns
    }
