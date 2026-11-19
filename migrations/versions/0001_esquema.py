"""0001_esquema: TAB-01 a TAB-12 de la parte B como tablas normales (CMP-19).

design.md §4: claves primarias que ya incluyen el tiempo, montos ``numeric(12,2)``,
conversiones y medianas ``numeric(14,4)``, códigos cerrados con ``CHECK``, huellas de
idempotencia únicas y la vista ``open_opportunity`` (TAB-12). Las hypertables (TAB-05 a
TAB-07) las convierte ``0002_hypertables``.

**Copia congelada** de ``oip.persistencia.tablas`` al crear la migración: los catálogos van
escritos aquí y no se importan, porque una migración aplicada no se edita ni cambia de
efecto (DEC-179, ADR-028). Un cambio del modelo va en una migración nueva; la prueba
``tests/test_migraciones.py`` comprueba que esta copia y el modelo coinciden.

Revision ID: 0001_esquema
Revises: (ninguna)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Text
from sqlalchemy.dialects import postgresql

revision = "0001_esquema"
down_revision = None
branch_labels = None
depends_on = None


def _lista(*valores: str) -> str:
    return ", ".join("'" + v.replace("'", "''") + "'" for v in valores)


# --- Catálogos congelados (CMP-03 y CTR-04 al crear la migración) ----------------------

_MOTIVOS = _lista(
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
_CATEGORIAS = _lista(
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
_CONDICIONES = _lista("new", "open_box", "refurbished", "used", "for_parts")
_VENDEDORES = _lista("comercio", "externo", "particular", "desconocido")
_MODOS_COMPRA = _lista("envio", "recoleccion", "tienda", "particular")
_IDENTIFICACIONES = _lista("confirmed", "unconfirmed")
_VERSIONES_CONTRATO = _lista("3.1", "3.0")
_ESTADOS_DISPONIBILIDAD = _lista(
    "in_stock_confirmed", "in_stock", "limited_stock", "unconfirmed", "out_of_stock", "listed"
)
_TIPOS_REGISTRO = _lista(
    "observation",
    "local_comparable",
    "local_estimate",
    "msrp",
    "local_demand",
    "store_visit",
    "actual_result",
    "client_request",
)
_MOTIVOS_RECHAZO_SIN_CAMPO = _lista(
    "TIPO DE REGISTRO DESCONOCIDO",
    "PRECIO INVÁLIDO",
    "DOMINIO NO AUTORIZADO",
    "CIUDAD NO CONFIGURADA",
)
_CALIDADES = _lista(
    "DESCUENTO_CUESTIONABLE",
    "OFERTA_EXCEPCIONAL",
    "BUENA_OFERTA",
    "PRECIO_COMPETITIVO",
    "PRECIO_NORMAL",
    "NO_APLICA",
)
_CONFIANZAS = _lista("ALTA", "MEDIA", "BAJA")
_CANALES = _lista("amazon", "local")
_NIVELES = _lista("COMPRAR_YA", "MUY_RECOMENDABLE", "RECOMENDABLE", "VIGILAR")
_REFERENCIAS = _lista(
    "precio_habitual", "precio_mercado_hoy", "minimo_60_dias_amazon", "precio_venta_amazon"
)
_ESTADOS_CANAL = _lista("CERRADO", "POR_REVISAR", "DISPONIBLE")
_CAUSAS_CERRADO = _lista(
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
_CAUSAS_POR_REVISAR = _lista("DEMANDA DESCONOCIDA", "SIN REFERENCIA DE USADOS")
_MONEDAS = _lista("USD", "MXN")
_RESULTADOS_VISITA = _lista("found", "not_found", "different_price", "confirmed_by_call")
_MODALIDADES = _lista("link_only", "buy_and_deliver")
_DEMANDAS_LOCALES = _lista("high", "medium", "low")
_RESULTADOS = _lista(
    "RECHAZADA_VALIDACION",
    "DESCARTADA",
    "SOLO_REFERENCIA",
    "REVISION_MANUAL",
    "SIN_NIVEL",
    "NIVEL_ASIGNADO",
)
_FORMATOS_CARGA = _lista("jsonl", "csv")
_CLASES_IDENTIFICADOR = _lista("gtin", "brand_model", "retailer_sku", "asin")
_ORIGENES_RECIBO = _lista("file", "worker")
_PATRON_CAMPO_FALTANTE = r"'^CAMPO OBLIGATORIO FALTANTE \([A-Za-z][A-Za-z0-9_.]*\)$'"


# --- Tablas ----------------------------------------------------------------------------


def _crear_config_version() -> None:
    op.create_table(
        "config_version",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=Text()), nullable=False),
        sa.Column("source_file", sa.Text(), nullable=False),
        sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "btrim(schema_version) <> ''", name=op.f("ck_config_version_schema_version_no_vacio")
        ),
        sa.CheckConstraint(
            "btrim(source_file) <> ''", name=op.f("ck_config_version_source_file_no_vacio")
        ),
        sa.CheckConstraint("btrim(version) <> ''", name=op.f("ck_config_version_version_no_vacio")),
        sa.CheckConstraint(
            "jsonb_typeof(content) = 'object'", name=op.f("ck_config_version_content_objeto")
        ),
        sa.CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_config_version_sha256_sha256")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_config_version")),
        sa.UniqueConstraint("sha256", name=op.f("uq_config_version_sha256")),
        sa.UniqueConstraint("version", name=op.f("uq_config_version_version")),
    )


def _crear_load_run() -> None:
    op.create_table(
        "load_run",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("file_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("format", sa.Text(), nullable=False),
        sa.Column("record_type", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("loaded", sa.Integer(), nullable=False),
        sa.Column("rejected", sa.Integer(), nullable=False),
        sa.Column("duplicates", sa.Integer(), nullable=False),
        sa.Column("rejected_by_reason", postgresql.JSONB(astext_type=Text()), nullable=False),
        sa.Column("config_version_id", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("btrim(file_name) <> ''", name=op.f("ck_load_run_file_name_no_vacio")),
        sa.CheckConstraint(
            "file_sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_load_run_file_sha256_sha256")
        ),
        sa.CheckConstraint(
            "format = 'csv' OR record_type IS NULL", name=op.f("ck_load_run_record_type_solo_csv")
        ),
        sa.CheckConstraint(
            f"format IN ({_FORMATOS_CARGA})", name=op.f("ck_load_run_format_catalogo")
        ),
        sa.CheckConstraint(
            "jsonb_typeof(rejected_by_reason) = 'object'",
            name=op.f("ck_load_run_rejected_by_reason_objeto"),
        ),
        sa.CheckConstraint(
            f"record_type IN ({_TIPOS_REGISTRO})", name=op.f("ck_load_run_record_type_catalogo")
        ),
        sa.CheckConstraint("finished_at >= started_at", name=op.f("ck_load_run_finished_at_orden")),
        sa.CheckConstraint(
            "loaded >= 0 AND rejected >= 0 AND duplicates >= 0",
            name=op.f("ck_load_run_conteos_no_negativos"),
        ),
        sa.ForeignKeyConstraint(
            ["config_version_id"],
            ["config_version.id"],
            name=op.f("fk_load_run_config_version_id_config_version"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_load_run")),
    )


def _crear_load_rejection() -> None:
    op.create_table(
        "load_rejection",
        sa.Column("load_run_id", sa.UUID(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("record_type", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("field", sa.Text(), nullable=True),
        sa.CheckConstraint("btrim(field) <> ''", name=op.f("ck_load_rejection_field_no_vacio")),
        sa.CheckConstraint(
            "field ~ '^[A-Za-z][A-Za-z0-9_.]*$'", name=op.f("ck_load_rejection_field_nombre")
        ),
        sa.CheckConstraint(
            f"reason IN ({_MOTIVOS_RECHAZO_SIN_CAMPO}) OR reason ~ {_PATRON_CAMPO_FALTANTE}",
            name=op.f("ck_load_rejection_reason_catalogo"),
        ),
        sa.CheckConstraint(
            f"record_type IN ({_TIPOS_REGISTRO})",
            name=op.f("ck_load_rejection_record_type_catalogo"),
        ),
        sa.CheckConstraint("line_number >= 1", name=op.f("ck_load_rejection_line_number_positivo")),
        sa.ForeignKeyConstraint(
            ["load_run_id"], ["load_run.id"], name=op.f("fk_load_rejection_load_run_id_load_run")
        ),
        sa.PrimaryKeyConstraint("load_run_id", "line_number", name=op.f("pk_load_rejection")),
    )


def _crear_product() -> None:
    op.create_table(
        "product",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("brand", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("btrim(brand) <> ''", name=op.f("ck_product_brand_no_vacio")),
        sa.CheckConstraint("btrim(content) <> ''", name=op.f("ck_product_content_no_vacio")),
        sa.CheckConstraint("btrim(model) <> ''", name=op.f("ck_product_model_no_vacio")),
        sa.CheckConstraint(
            f"category IN ({_CATEGORIAS})", name=op.f("ck_product_category_catalogo")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product")),
    )


def _crear_product_identifier() -> None:
    op.create_table(
        "product_identifier",
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.CheckConstraint("btrim(value) <> ''", name=op.f("ck_product_identifier_value_no_vacio")),
        sa.CheckConstraint(
            f"kind IN ({_CLASES_IDENTIFICADOR})", name=op.f("ck_product_identifier_kind_catalogo")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["product.id"], name=op.f("fk_product_identifier_product_id_product")
        ),
        sa.PrimaryKeyConstraint("kind", "value", name=op.f("pk_product_identifier")),
    )
    op.create_index(
        "ix_product_identifier_product_id", "product_identifier", ["product_id"], unique=False
    )


def _crear_listing() -> None:
    op.create_table(
        "listing",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("retailer_code", sa.Text(), nullable=False),
        sa.Column("store_code", sa.Text(), nullable=True),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=True),
        sa.Column("pickup_location", sa.Text(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "btrim(canonical_url) <> ''", name=op.f("ck_listing_canonical_url_no_vacio")
        ),
        sa.CheckConstraint(
            "btrim(pickup_location) <> ''", name=op.f("ck_listing_pickup_location_no_vacio")
        ),
        sa.CheckConstraint("btrim(platform) <> ''", name=op.f("ck_listing_platform_no_vacio")),
        sa.CheckConstraint(
            "btrim(retailer_code) <> ''", name=op.f("ck_listing_retailer_code_no_vacio")
        ),
        sa.CheckConstraint("btrim(store_code) <> ''", name=op.f("ck_listing_store_code_no_vacio")),
        sa.CheckConstraint(
            "retailer_code = 'particular' OR (platform IS NULL AND pickup_location IS NULL)",
            name=op.f("ck_listing_solo_particular"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["product.id"], name=op.f("fk_listing_product_id_product")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_listing")),
    )
    op.create_index("ix_listing_product_id", "listing", ["product_id"], unique=False)
    op.create_index(
        "uq_listing_retailer_url_store",
        "listing",
        ["retailer_code", "canonical_url", sa.literal_column("coalesce(store_code, '')")],
        unique=True,
    )


def _crear_price_observation() -> None:
    op.create_table(
        "price_observation",
        sa.Column("observation_id", sa.UUID(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("listing_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("was_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("currency", sa.Text(), nullable=True),
        sa.Column("seller", sa.Text(), nullable=False),
        sa.Column("condition", sa.Text(), nullable=True),
        sa.Column("purchase_mode", sa.Text(), nullable=False),
        sa.Column("is_clearance", sa.Boolean(), nullable=True),
        sa.Column("tax_location", sa.Text(), nullable=True),
        sa.Column("shipping_to_me", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("weight_kg", sa.Numeric(), nullable=True),
        sa.Column("dims_cm", postgresql.JSONB(astext_type=Text()), nullable=True),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("identification", sa.Text(), nullable=False),
        sa.Column("msrp_value", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("msrp_source", sa.Text(), nullable=True),
        sa.Column("msrp_date", sa.Date(), nullable=True),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=True),
        sa.Column("extraction_method", sa.Text(), nullable=True),
        sa.Column("load_run_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "btrim(currency) <> ''", name=op.f("ck_price_observation_currency_no_vacio")
        ),
        sa.CheckConstraint(
            "btrim(extraction_method) <> ''",
            name=op.f("ck_price_observation_extraction_method_no_vacio"),
        ),
        sa.CheckConstraint(
            "btrim(msrp_source) <> ''", name=op.f("ck_price_observation_msrp_source_no_vacio")
        ),
        sa.CheckConstraint(
            "btrim(source_type) <> ''", name=op.f("ck_price_observation_source_type_no_vacio")
        ),
        sa.CheckConstraint(
            "btrim(tax_location) <> ''", name=op.f("ck_price_observation_tax_location_no_vacio")
        ),
        sa.CheckConstraint("btrim(title) <> ''", name=op.f("ck_price_observation_title_no_vacio")),
        sa.CheckConstraint(
            f"category IN ({_CATEGORIAS})", name=op.f("ck_price_observation_category_catalogo")
        ),
        sa.CheckConstraint(
            f"condition IN ({_CONDICIONES})", name=op.f("ck_price_observation_condition_catalogo")
        ),
        sa.CheckConstraint(
            f"identification IN ({_IDENTIFICACIONES})",
            name=op.f("ck_price_observation_identification_catalogo"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(dims_cm) = 'object'", name=op.f("ck_price_observation_dims_cm_objeto")
        ),
        sa.CheckConstraint(
            f"purchase_mode IN ({_MODOS_COMPRA})",
            name=op.f("ck_price_observation_purchase_mode_catalogo"),
        ),
        sa.CheckConstraint(
            f"schema_version IN ({_VERSIONES_CONTRATO})",
            name=op.f("ck_price_observation_schema_version_catalogo"),
        ),
        sa.CheckConstraint(
            f"seller IN ({_VENDEDORES})", name=op.f("ck_price_observation_seller_catalogo")
        ),
        sa.CheckConstraint("price > 0", name=op.f("ck_price_observation_price_positivo")),
        sa.ForeignKeyConstraint(
            ["listing_id"], ["listing.id"], name=op.f("fk_price_observation_listing_id_listing")
        ),
        sa.ForeignKeyConstraint(
            ["load_run_id"], ["load_run.id"], name=op.f("fk_price_observation_load_run_id_load_run")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["product.id"], name=op.f("fk_price_observation_product_id_product")
        ),
        sa.PrimaryKeyConstraint("observation_id", "observed_at", name=op.f("pk_price_observation")),
    )
    op.create_index(
        "ix_price_observation_listing_id_observed_at",
        "price_observation",
        ["listing_id", sa.literal_column("observed_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_price_observation_product_id_observed_at",
        "price_observation",
        ["product_id", sa.literal_column("observed_at DESC")],
        unique=False,
    )


def _crear_availability_observation() -> None:
    op.create_table(
        "availability_observation",
        sa.Column("observation_id", sa.UUID(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("listing_id", sa.UUID(), nullable=False),
        sa.Column("store_code", sa.Text(), nullable=True),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("add_to_cart", sa.Boolean(), nullable=True),
        sa.CheckConstraint(
            "btrim(scope) <> ''", name=op.f("ck_availability_observation_scope_no_vacio")
        ),
        sa.CheckConstraint(
            "btrim(store_code) <> ''", name=op.f("ck_availability_observation_store_code_no_vacio")
        ),
        sa.CheckConstraint(
            "btrim(text) <> ''", name=op.f("ck_availability_observation_text_no_vacio")
        ),
        sa.CheckConstraint(
            f"state IN ({_ESTADOS_DISPONIBILIDAD})",
            name=op.f("ck_availability_observation_state_catalogo"),
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["listing.id"],
            name=op.f("fk_availability_observation_listing_id_listing"),
        ),
        sa.PrimaryKeyConstraint(
            "observation_id", "observed_at", name=op.f("pk_availability_observation")
        ),
    )
    op.create_index(
        "ix_availability_observation_listing_id_observed_at",
        "availability_observation",
        ["listing_id", sa.literal_column("observed_at DESC")],
        unique=False,
    )


def _crear_amazon_listing_observation() -> None:
    op.create_table(
        "amazon_listing_observation",
        sa.Column("observation_id", sa.UUID(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("listing_id", sa.UUID(), nullable=False),
        sa.Column("buy_box_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("sellers_new", sa.Integer(), nullable=True),
        sa.Column("rank_main", sa.Integer(), nullable=True),
        sa.Column("rank_sub", sa.Integer(), nullable=True),
        sa.Column("reviews", sa.Integer(), nullable=True),
        sa.Column("bought_last_month", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["listing.id"],
            name=op.f("fk_amazon_listing_observation_listing_id_listing"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["product.id"],
            name=op.f("fk_amazon_listing_observation_product_id_product"),
        ),
        sa.PrimaryKeyConstraint(
            "observation_id", "observed_at", name=op.f("pk_amazon_listing_observation")
        ),
    )
    op.create_index(
        "ix_amazon_listing_observation_product_id_observed_at",
        "amazon_listing_observation",
        ["product_id", sa.literal_column("observed_at DESC")],
        unique=False,
    )


def _crear_ingest_receipt() -> None:
    op.create_table(
        "ingest_receipt",
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("observation_id", sa.UUID(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("load_run_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "btrim(idempotency_key) <> ''", name=op.f("ck_ingest_receipt_idempotency_key_no_vacio")
        ),
        sa.CheckConstraint(
            "source <> 'file' OR load_run_id IS NOT NULL",
            name=op.f("ck_ingest_receipt_file_con_carga"),
        ),
        sa.CheckConstraint(
            f"source IN ({_ORIGENES_RECIBO})", name=op.f("ck_ingest_receipt_source_catalogo")
        ),
        sa.ForeignKeyConstraint(
            ["load_run_id"], ["load_run.id"], name=op.f("fk_ingest_receipt_load_run_id_load_run")
        ),
        sa.PrimaryKeyConstraint("idempotency_key", name=op.f("pk_ingest_receipt")),
    )


def _crear_local_comparable() -> None:
    op.create_table(
        "local_comparable",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("load_run_id", sa.UUID(), nullable=False),
        sa.Column("idempotency_key", sa.CHAR(length=64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("gtin", sa.Text(), nullable=True),
        sa.Column("brand", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("condition", sa.Text(), nullable=False),
        sa.Column("asking_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(), nullable=True),
        sa.Column("price_usd", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("city", sa.Text(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("sold", sa.Boolean(), nullable=False),
        sa.CheckConstraint("btrim(brand) <> ''", name=op.f("ck_local_comparable_brand_no_vacio")),
        sa.CheckConstraint("btrim(city) <> ''", name=op.f("ck_local_comparable_city_no_vacio")),
        sa.CheckConstraint("btrim(gtin) <> ''", name=op.f("ck_local_comparable_gtin_no_vacio")),
        sa.CheckConstraint("btrim(model) <> ''", name=op.f("ck_local_comparable_model_no_vacio")),
        sa.CheckConstraint(
            f"condition IN ({_CONDICIONES})", name=op.f("ck_local_comparable_condition_catalogo")
        ),
        sa.CheckConstraint(
            "currency <> 'MXN' OR exchange_rate IS NOT NULL",
            name=op.f("ck_local_comparable_mxn_con_tipo_de_cambio"),
        ),
        sa.CheckConstraint(
            f"currency IN ({_MONEDAS})", name=op.f("ck_local_comparable_currency_catalogo")
        ),
        sa.CheckConstraint(
            "idempotency_key ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_local_comparable_idempotency_key_sha256"),
        ),
        sa.CheckConstraint(
            "asking_price > 0", name=op.f("ck_local_comparable_asking_price_positivo")
        ),
        sa.CheckConstraint(
            "exchange_rate > 0", name=op.f("ck_local_comparable_exchange_rate_positivo")
        ),
        sa.ForeignKeyConstraint(
            ["load_run_id"], ["load_run.id"], name=op.f("fk_local_comparable_load_run_id_load_run")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["product.id"], name=op.f("fk_local_comparable_product_id_product")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_local_comparable")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_local_comparable_idempotency_key")),
    )
    op.create_index(
        "ix_local_comparable_product_id_condition",
        "local_comparable",
        ["product_id", "condition"],
        unique=False,
    )


def _crear_local_estimate() -> None:
    op.create_table(
        "local_estimate",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("load_run_id", sa.UUID(), nullable=False),
        sa.Column("idempotency_key", sa.CHAR(length=64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("gtin", sa.Text(), nullable=True),
        sa.Column("brand", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("condition", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.CheckConstraint("btrim(brand) <> ''", name=op.f("ck_local_estimate_brand_no_vacio")),
        sa.CheckConstraint("btrim(gtin) <> ''", name=op.f("ck_local_estimate_gtin_no_vacio")),
        sa.CheckConstraint("btrim(model) <> ''", name=op.f("ck_local_estimate_model_no_vacio")),
        sa.CheckConstraint(
            f"condition IN ({_CONDICIONES})", name=op.f("ck_local_estimate_condition_catalogo")
        ),
        sa.CheckConstraint(
            "idempotency_key ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_local_estimate_idempotency_key_sha256"),
        ),
        sa.ForeignKeyConstraint(
            ["load_run_id"], ["load_run.id"], name=op.f("fk_local_estimate_load_run_id_load_run")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["product.id"], name=op.f("fk_local_estimate_product_id_product")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_local_estimate")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_local_estimate_idempotency_key")),
    )
    op.create_index(
        "ix_local_estimate_product_id_condition",
        "local_estimate",
        ["product_id", "condition"],
        unique=False,
    )


def _crear_msrp_capture() -> None:
    op.create_table(
        "msrp_capture",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("load_run_id", sa.UUID(), nullable=False),
        sa.Column("idempotency_key", sa.CHAR(length=64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("gtin", sa.Text(), nullable=True),
        sa.Column("brand", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("value", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.CheckConstraint("btrim(brand) <> ''", name=op.f("ck_msrp_capture_brand_no_vacio")),
        sa.CheckConstraint("btrim(gtin) <> ''", name=op.f("ck_msrp_capture_gtin_no_vacio")),
        sa.CheckConstraint("btrim(model) <> ''", name=op.f("ck_msrp_capture_model_no_vacio")),
        sa.CheckConstraint("btrim(source) <> ''", name=op.f("ck_msrp_capture_source_no_vacio")),
        sa.CheckConstraint(
            "idempotency_key ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_msrp_capture_idempotency_key_sha256"),
        ),
        sa.ForeignKeyConstraint(
            ["load_run_id"], ["load_run.id"], name=op.f("fk_msrp_capture_load_run_id_load_run")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["product.id"], name=op.f("fk_msrp_capture_product_id_product")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_msrp_capture")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_msrp_capture_idempotency_key")),
    )


def _crear_local_demand() -> None:
    op.create_table(
        "local_demand",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("load_run_id", sa.UUID(), nullable=False),
        sa.Column("idempotency_key", sa.CHAR(length=64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.CheckConstraint(
            f"category IN ({_CATEGORIAS})", name=op.f("ck_local_demand_category_catalogo")
        ),
        sa.CheckConstraint(
            "idempotency_key ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_local_demand_idempotency_key_sha256"),
        ),
        sa.CheckConstraint(
            f"level IN ({_DEMANDAS_LOCALES})", name=op.f("ck_local_demand_level_catalogo")
        ),
        sa.ForeignKeyConstraint(
            ["load_run_id"], ["load_run.id"], name=op.f("fk_local_demand_load_run_id_load_run")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_local_demand")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_local_demand_idempotency_key")),
    )
    op.create_index(
        "ix_local_demand_category_date",
        "local_demand",
        ["category", sa.literal_column("date DESC")],
        unique=False,
    )


def _crear_store_visit() -> None:
    op.create_table(
        "store_visit",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("load_run_id", sa.UUID(), nullable=False),
        sa.Column("idempotency_key", sa.CHAR(length=64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("store_code", sa.Text(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("gtin", sa.Text(), nullable=True),
        sa.Column("brand", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("evaluation_id", sa.UUID(), nullable=True),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("visited_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("btrim(brand) <> ''", name=op.f("ck_store_visit_brand_no_vacio")),
        sa.CheckConstraint("btrim(gtin) <> ''", name=op.f("ck_store_visit_gtin_no_vacio")),
        sa.CheckConstraint("btrim(model) <> ''", name=op.f("ck_store_visit_model_no_vacio")),
        sa.CheckConstraint(
            "btrim(store_code) <> ''", name=op.f("ck_store_visit_store_code_no_vacio")
        ),
        sa.CheckConstraint(
            "idempotency_key ~ '^[0-9a-f]{64}$'", name=op.f("ck_store_visit_idempotency_key_sha256")
        ),
        sa.CheckConstraint(
            f"result IN ({_RESULTADOS_VISITA})", name=op.f("ck_store_visit_result_catalogo")
        ),
        sa.CheckConstraint(
            "product_id IS NOT NULL OR evaluation_id IS NOT NULL",
            name=op.f("ck_store_visit_producto_u_oportunidad"),
        ),
        sa.ForeignKeyConstraint(
            ["load_run_id"], ["load_run.id"], name=op.f("fk_store_visit_load_run_id_load_run")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["product.id"], name=op.f("fk_store_visit_product_id_product")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_store_visit")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_store_visit_idempotency_key")),
    )


def _crear_opportunity_outcome() -> None:
    op.create_table(
        "opportunity_outcome",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("load_run_id", sa.UUID(), nullable=False),
        sa.Column("idempotency_key", sa.CHAR(length=64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evaluation_id", sa.UUID(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("purchase_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("sale_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("actual_costs", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("purchased_on", sa.Date(), nullable=False),
        sa.Column("sold_on", sa.Date(), nullable=False),
        sa.CheckConstraint(
            f"channel IN ({_CANALES})", name=op.f("ck_opportunity_outcome_channel_catalogo")
        ),
        sa.CheckConstraint(
            "idempotency_key ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_opportunity_outcome_idempotency_key_sha256"),
        ),
        sa.ForeignKeyConstraint(
            ["load_run_id"],
            ["load_run.id"],
            name=op.f("fk_opportunity_outcome_load_run_id_load_run"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_opportunity_outcome")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_opportunity_outcome_idempotency_key")),
    )


def _crear_client_request() -> None:
    op.create_table(
        "client_request",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("load_run_id", sa.UUID(), nullable=False),
        sa.Column("idempotency_key", sa.CHAR(length=64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("client_alias", sa.Text(), nullable=False),
        sa.Column("items", postgresql.ARRAY(Text()), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("accepted_conditions", postgresql.ARRAY(Text()), nullable=False),
        sa.Column("modality", sa.Text(), nullable=False),
        sa.Column("postal_code", sa.Text(), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.CheckConstraint(
            f"accepted_conditions <@ ARRAY[{_CONDICIONES}]::text[]",
            name=op.f("ck_client_request_accepted_conditions_catalogo"),
        ),
        sa.CheckConstraint(
            "btrim(client_alias) <> ''", name=op.f("ck_client_request_client_alias_no_vacio")
        ),
        sa.CheckConstraint(
            "btrim(postal_code) <> ''", name=op.f("ck_client_request_postal_code_no_vacio")
        ),
        sa.CheckConstraint(
            "idempotency_key ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_client_request_idempotency_key_sha256"),
        ),
        sa.CheckConstraint(
            f"modality IN ({_MODALIDADES})", name=op.f("ck_client_request_modality_catalogo")
        ),
        sa.CheckConstraint(
            "cardinality(accepted_conditions) >= 1",
            name=op.f("ck_client_request_accepted_conditions_no_vacio"),
        ),
        sa.CheckConstraint(
            "cardinality(items) BETWEEN 1 AND 3", name=op.f("ck_client_request_items_de_1_a_3")
        ),
        sa.CheckConstraint("quantity >= 1", name=op.f("ck_client_request_quantity_positiva")),
        sa.ForeignKeyConstraint(
            ["load_run_id"], ["load_run.id"], name=op.f("fk_client_request_load_run_id_load_run")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_client_request")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_client_request_idempotency_key")),
    )


def _crear_evaluation() -> None:
    op.create_table(
        "evaluation",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("offer_observation_id", sa.UUID(), nullable=True),
        sa.Column("listing_id", sa.UUID(), nullable=True),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("config_version_id", sa.BigInteger(), nullable=False),
        sa.Column("rn_versions", postgresql.JSONB(astext_type=Text()), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("main_reason", sa.Text(), nullable=True),
        sa.Column("reasons", postgresql.ARRAY(Text()), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("marks", postgresql.ARRAY(Text()), nullable=False),
        sa.Column("price_quality", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Text(), nullable=True),
        sa.Column("identification", sa.Text(), nullable=True),
        sa.Column("references", postgresql.JSONB(astext_type=Text()), nullable=True),
        sa.Column("advertised_discount", sa.Numeric(), nullable=True),
        sa.Column("real_discount", sa.Numeric(), nullable=True),
        sa.Column("purchase_cost", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("chosen_channel", sa.Text(), nullable=True),
        sa.Column("alert_level", sa.Text(), nullable=True),
        sa.Column("alert_channel", sa.Text(), nullable=True),
        sa.Column("observations_used", postgresql.JSONB(astext_type=Text()), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(astext_type=Text()), nullable=True),
        sa.Column("previous_evaluation_id", sa.UUID(), nullable=True),
        sa.Column("changed_references", postgresql.ARRAY(Text()), nullable=False),
        sa.Column("no_longer_recommended", sa.Boolean(), nullable=False),
        sa.Column("load_run_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "(result = 'NIVEL_ASIGNADO') = (alert_level IS NOT NULL)"
            " AND (result = 'NIVEL_ASIGNADO') = (alert_channel IS NOT NULL)"
            " AND (result <> 'NIVEL_ASIGNADO' OR chosen_channel IS NOT NULL)",
            name=op.f("ck_evaluation_aviso_solo_con_nivel"),
        ),
        sa.CheckConstraint(
            "(result = 'RECHAZADA_VALIDACION') = (rejection_reason IS NOT NULL)",
            name=op.f("ck_evaluation_rechazo_con_motivo"),
        ),
        sa.CheckConstraint(
            f"alert_channel IN ({_CANALES})", name=op.f("ck_evaluation_alert_channel_catalogo")
        ),
        sa.CheckConstraint(
            f"alert_level IN ({_NIVELES})", name=op.f("ck_evaluation_alert_level_catalogo")
        ),
        sa.CheckConstraint(
            f"changed_references <@ ARRAY[{_REFERENCIAS}]::text[]",
            name=op.f("ck_evaluation_changed_references_catalogo"),
        ),
        sa.CheckConstraint(
            f"chosen_channel IN ({_CANALES})", name=op.f("ck_evaluation_chosen_channel_catalogo")
        ),
        sa.CheckConstraint(
            f"confidence IN ({_CONFIANZAS})", name=op.f("ck_evaluation_confidence_catalogo")
        ),
        sa.CheckConstraint(
            f"identification IN ({_IDENTIFICACIONES})",
            name=op.f("ck_evaluation_identification_catalogo"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(observations_used) = 'array'",
            name=op.f("ck_evaluation_observations_used_arreglo"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(rn_versions) = 'object'", name=op.f("ck_evaluation_rn_versions_objeto")
        ),
        sa.CheckConstraint(
            f"main_reason IN ({_MOTIVOS})", name=op.f("ck_evaluation_main_reason_catalogo")
        ),
        sa.CheckConstraint(
            f"price_quality IN ({_CALIDADES})", name=op.f("ck_evaluation_price_quality_catalogo")
        ),
        sa.CheckConstraint(
            f"reasons <@ ARRAY[{_MOTIVOS}]::text[]", name=op.f("ck_evaluation_reasons_catalogo")
        ),
        sa.CheckConstraint(
            f"rejection_reason IN ({_MOTIVOS_RECHAZO_SIN_CAMPO})"
            f" OR rejection_reason ~ {_PATRON_CAMPO_FALTANTE}",
            name=op.f("ck_evaluation_rejection_reason_catalogo"),
        ),
        sa.CheckConstraint(
            "result <> 'RECHAZADA_VALIDACION' OR offer_observation_id IS NULL",
            name=op.f("ck_evaluation_rechazo_sin_oferta"),
        ),
        sa.CheckConstraint(
            f"result IN ({_RESULTADOS})", name=op.f("ck_evaluation_result_catalogo")
        ),
        sa.CheckConstraint(
            "main_reason IS NOT DISTINCT FROM reasons[1]",
            name=op.f("ck_evaluation_motivo_principal"),
        ),
        sa.CheckConstraint(
            "previous_evaluation_id IS NOT NULL"
            " OR (cardinality(changed_references) = 0 AND NOT no_longer_recommended)",
            name=op.f("ck_evaluation_reevaluacion"),
        ),
        sa.ForeignKeyConstraint(
            ["config_version_id"],
            ["config_version.id"],
            name=op.f("fk_evaluation_config_version_id_config_version"),
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"], ["listing.id"], name=op.f("fk_evaluation_listing_id_listing")
        ),
        sa.ForeignKeyConstraint(
            ["load_run_id"], ["load_run.id"], name=op.f("fk_evaluation_load_run_id_load_run")
        ),
        sa.ForeignKeyConstraint(
            ["previous_evaluation_id"],
            ["evaluation.id"],
            name=op.f("fk_evaluation_previous_evaluation_id_evaluation"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["product.id"], name=op.f("fk_evaluation_product_id_product")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evaluation")),
    )
    op.create_index(
        "ix_evaluation_listing_id_evaluated_at",
        "evaluation",
        ["listing_id", sa.literal_column("evaluated_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_evaluation_product_id_result", "evaluation", ["product_id", "result"], unique=False
    )


def _crear_evaluation_channel() -> None:
    op.create_table(
        "evaluation_channel",
        sa.Column("evaluation_id", sa.UUID(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("closed_causes", postgresql.ARRAY(Text()), nullable=False),
        sa.Column("review_causes", postgresql.ARRAY(Text()), nullable=False),
        sa.Column("sale_price", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column("selling_cost", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("net_margin", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("net_margin_pct", sa.Numeric(), nullable=True),
        sa.Column("returns_cost", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("drop_penalty", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("adjusted_margin", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("adjusted_margin_pct", sa.Numeric(), nullable=True),
        sa.Column("units", sa.Integer(), nullable=True),
        sa.Column("days_to_recover", sa.Numeric(), nullable=True),
        sa.Column("monthly_yield_pct", sa.Numeric(), nullable=True),
        sa.Column("level", sa.Text(), nullable=True),
        sa.Column("calculated_level", sa.Text(), nullable=True),
        sa.Column("total_profit", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("marks", postgresql.ARRAY(Text()), nullable=False),
        sa.CheckConstraint(
            f"calculated_level IN ({_NIVELES})",
            name=op.f("ck_evaluation_channel_calculated_level_catalogo"),
        ),
        sa.CheckConstraint(
            f"channel IN ({_CANALES})", name=op.f("ck_evaluation_channel_channel_catalogo")
        ),
        sa.CheckConstraint(
            f"closed_causes <@ ARRAY[{_CAUSAS_CERRADO}]::text[]",
            name=op.f("ck_evaluation_channel_closed_causes_catalogo"),
        ),
        sa.CheckConstraint(
            f"level IN ({_NIVELES})", name=op.f("ck_evaluation_channel_level_catalogo")
        ),
        sa.CheckConstraint(
            f"review_causes <@ ARRAY[{_CAUSAS_POR_REVISAR}]::text[]",
            name=op.f("ck_evaluation_channel_review_causes_catalogo"),
        ),
        sa.CheckConstraint(
            f"state IN ({_ESTADOS_CANAL})", name=op.f("ck_evaluation_channel_state_catalogo")
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["evaluation.id"],
            name=op.f("fk_evaluation_channel_evaluation_id_evaluation"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("evaluation_id", "channel", name=op.f("pk_evaluation_channel")),
    )


#: TAB-05 a TAB-07: ``0002_hypertables`` las vuelve a crear así al revertir.
CREAR_HYPERTABLES = (
    _crear_price_observation,
    _crear_availability_observation,
    _crear_amazon_listing_observation,
)

#: TAB-12: la evaluación más reciente de cada publicación, si es NIVEL_ASIGNADO (§3.2.5).
SQL_OPEN_OPPORTUNITY = (
    "SELECT latest.* FROM ("
    "SELECT DISTINCT ON (listing_id) * FROM evaluation"
    " WHERE listing_id IS NOT NULL"
    " ORDER BY listing_id, evaluated_at DESC, id DESC"
    ") AS latest WHERE latest.result = 'NIVEL_ASIGNADO'"
)

#: Tablas en orden de creación (las referenciadas primero).
CREAR = (
    _crear_config_version,
    _crear_load_run,
    _crear_load_rejection,
    _crear_product,
    _crear_product_identifier,
    _crear_listing,
    *CREAR_HYPERTABLES,
    _crear_ingest_receipt,
    _crear_local_comparable,
    _crear_local_estimate,
    _crear_msrp_capture,
    _crear_local_demand,
    _crear_store_visit,
    _crear_opportunity_outcome,
    _crear_client_request,
    _crear_evaluation,
    _crear_evaluation_channel,
)

#: Tablas en orden de borrado (las que referencian primero).
TABLAS = (
    "config_version",
    "load_run",
    "load_rejection",
    "product",
    "product_identifier",
    "listing",
    "price_observation",
    "availability_observation",
    "amazon_listing_observation",
    "ingest_receipt",
    "local_comparable",
    "local_estimate",
    "msrp_capture",
    "local_demand",
    "store_visit",
    "opportunity_outcome",
    "client_request",
    "evaluation",
    "evaluation_channel",
)


def upgrade() -> None:
    for crear in CREAR:
        crear()
    op.execute(f"CREATE VIEW open_opportunity AS {SQL_OPEN_OPPORTUNITY}")


def downgrade() -> None:
    op.execute("DROP VIEW open_opportunity")
    for tabla in reversed(TABLAS):
        op.drop_table(tabla)
