"""Tablas de la parte B en SQLAlchemy Core (CMP-19; design.md §4).

Esquema de PostgreSQL + TimescaleDB: TAB-01 a TAB-12. Las migraciones versionadas viven en
``migrations/`` (Alembic, en la raíz del repo): ``0001_esquema`` crea estas tablas como
tablas normales, ``0002_hypertables`` convierte TAB-05 a TAB-07 en hypertables
(ADR-013, ADR-028, DEC-179) y ``0003_registro_de_rechazo`` agrega a TAB-10 el renglón del
rechazo de validación (DEC-250). ``metadata`` es el modelo de ``head``; ``metadata_0001``,
el de ``0001_esquema``. Este módulo es la **fuente** de los metadatos; las
migraciones guardan su copia congelada (nunca se edita una migración aplicada) y una
prueba comprueba que coinciden.

Reglas (design.md §4, §5, §11, §16):

- Nombres de tablas y columnas en inglés (arquitectura §7.1); tiempos ``timestamptz``.
- **Montos** ``numeric(12,2)``; precios convertidos de MXN y medianas, sin redondear,
  ``numeric(14,4)``; porcentajes y descuentos, ``numeric`` sin escala (sin redondear,
  DEC-207). Ningún monto es ``float``: las columnas devuelven ``Decimal``.
- **Códigos cerrados** como ``text`` con ``CHECK`` contra el catálogo de ``oip.catalogos``
  y de ``oip.entradas`` (CMP-03; design.md §9): los valores se derivan de los enums, no se
  copian a mano.
- **Vacío = ausente:** ninguna columna ``text`` admite texto vacío o solo espacios; lo
  ausente es ``NULL``.
- Las hypertables (TAB-05 a TAB-07) tienen la columna de tiempo en la clave primaria.
- **Idempotencia** (design.md §5; arquitectura §8): TAB-08 con ``idempotency_key`` como
  clave; cada captura de TAB-09 con su huella ``sha256`` única.
- **Sin el contenido de un renglón rechazado** (R-20, DEC-181): ``load_rejection`` guarda
  solo carga, renglón, tipo, motivo y nombre del campo.
- **Clientes solo por alias** (RNF-11): ``client_request`` no tiene columna de notas ni de
  texto libre.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    Numeric,
    PrimaryKeyConstraint,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

from oip.catalogos import (
    CalidadPrecio,
    Canal,
    Categoria,
    CausaCanalCerrado,
    CausaCanalPorRevisar,
    Condicion,
    Confianza,
    DemandaLocal,
    EstadoCanal,
    EstadoDisponibilidad,
    Identificacion,
    ModoCompra,
    Motivo,
    MotivoRechazo,
    Nivel,
    ReferenciaPrecio,
    Resultado,
    TipoRegistro,
    Vendedor,
)
from oip.entradas.capturas import Modalidad, Moneda, ResultadoVisita
from oip.entradas.contrato import VERSIONES_ACEPTADAS

__all__ = [
    "CAMBIOS_0004",
    "CLASES_IDENTIFICADOR",
    "COLUMNAS_0003",
    "FORMATOS_CARGA",
    "HYPERTABLES",
    "INTERVALO_CHUNK",
    "ORIGENES_RECIBO",
    "RESTRICCIONES_0003",
    "SQL_OPEN_OPPORTUNITY",
    "amazon_listing_observation",
    "availability_observation",
    "client_request",
    "config_version",
    "evaluation",
    "evaluation_channel",
    "ingest_receipt",
    "listing",
    "load_rejection",
    "load_run",
    "local_comparable",
    "local_demand",
    "local_estimate",
    "metadata",
    "metadata_0001",
    "metadata_vistas",
    "msrp_capture",
    "open_opportunity",
    "opportunity_outcome",
    "price_observation",
    "product",
    "product_identifier",
    "store_visit",
]

#: Nombres de las restricciones: estables, para que la migración y las pruebas los citen.
CONVENCION_NOMBRES = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=CONVENCION_NOMBRES)

#: Vistas (TAB-12): fuera de ``metadata`` para que ``create_all`` no las cree como tablas.
metadata_vistas = MetaData()

# --- Tipos ---------------------------------------------------------------------------

#: Montos en USD (design.md §4): los de la lista cerrada ya redondeados y los precios leídos.
MONTO = Numeric(12, 2)
#: Precios convertidos de MXN y medianas, sin redondear (design.md §4; S-23, DEC-226 b).
CONVERSION = Numeric(14, 4)
#: Porcentajes, descuentos y cantidades no monetarias sin redondear (DEC-207).
SIN_REDONDEAR = Numeric()
TIEMPO = DateTime(timezone=True)
HUELLA = CHAR(64)
ID = UUID(as_uuid=True)
TEXTOS = ARRAY(Text)

# --- Catálogos propios del modelo (no están en CMP-03) ---------------------------------

#: ``load_run.format`` (TAB-02).
FORMATOS_CARGA = ("jsonl", "csv")
#: ``product_identifier.kind`` (TAB-03; arquitectura §7.1).
CLASES_IDENTIFICADOR = ("gtin", "brand_model", "retailer_sku", "asin")
#: ``ingest_receipt.source`` (TAB-08).
ORIGENES_RECIBO = ("file", "worker")

#: Hypertables (TAB-05 a TAB-07) y su intervalo de chunk, que fija ``0002_hypertables``.
HYPERTABLES = ("price_observation", "availability_observation", "amazon_listing_observation")
INTERVALO_CHUNK = "7 days"

_PARTICULAR = Vendedor.PARTICULAR.value

# --- Ayudas para los CHECK -------------------------------------------------------------


def _valores(catalogo: type[StrEnum] | Iterable[str]) -> tuple[str, ...]:
    return tuple(str(v.value) if isinstance(v, StrEnum) else str(v) for v in catalogo)


def _lista(catalogo: type[StrEnum] | Iterable[str]) -> str:
    return ", ".join("'" + v.replace("'", "''") + "'" for v in _valores(catalogo))


def _en(columna: str, catalogo: type[StrEnum] | Iterable[str]) -> CheckConstraint:
    """``columna`` dentro del catálogo (``NULL`` pasa: lo decide la nulabilidad)."""
    return CheckConstraint(f"{columna} IN ({_lista(catalogo)})", name=f"{columna}_catalogo")


def _todos_en(columna: str, catalogo: type[StrEnum] | Iterable[str]) -> CheckConstraint:
    """Cada elemento del arreglo ``columna`` dentro del catálogo."""
    return CheckConstraint(
        f"{columna} <@ ARRAY[{_lista(catalogo)}]::text[]", name=f"{columna}_catalogo"
    )


def _hex64(columna: str) -> CheckConstraint:
    """Huella ``sha256`` en hexadecimal (64 caracteres en minúscula)."""
    return CheckConstraint(f"{columna} ~ '^[0-9a-f]{{64}}$'", name=f"{columna}_sha256")


def _objeto(columna: str) -> CheckConstraint:
    return CheckConstraint(f"jsonb_typeof({columna}) = 'object'", name=f"{columna}_objeto")


#: Motivo de rechazo completo (design.md §6): un código base o
#: ``CAMPO OBLIGATORIO FALTANTE (<campo>)`` con el nombre del campo en el archivo.
_CAMPO = "[A-Za-z][A-Za-z0-9_.]*"
_MOTIVOS_SIN_CAMPO = tuple(
    m for m in _valores(MotivoRechazo) if m != MotivoRechazo.CAMPO_OBLIGATORIO_FALTANTE.value
)


def _motivo_rechazo(columna: str) -> CheckConstraint:
    base = MotivoRechazo.CAMPO_OBLIGATORIO_FALTANTE.value
    return CheckConstraint(
        f"{columna} IN ({_lista(_MOTIVOS_SIN_CAMPO)}) OR {columna} ~ '^{base} \\({_CAMPO}\\)$'",
        name=f"{columna}_catalogo",
    )


def _tabla(nombre: str, *elementos: object, md: MetaData | None = None) -> Table:
    """``Table`` con un ``CHECK`` de "vacío = ausente" en cada columna ``text`` libre (las de
    un catálogo ya excluyen el texto vacío con su propio ``CHECK``)."""
    tabla = Table(nombre, metadata if md is None else md, *elementos)
    con_catalogo = {
        str(r.name).removeprefix(f"ck_{nombre}_").removesuffix("_catalogo")
        for r in tabla.constraints
        if isinstance(r, CheckConstraint) and str(r.name).endswith("_catalogo")
    }
    for columna in tabla.columns:
        if type(columna.type) is Text and columna.name not in con_catalogo:
            tabla.append_constraint(
                CheckConstraint(f"btrim({columna.name}) <> ''", name=f"{columna.name}_no_vacio")
            )
    return tabla


# --- TAB-01 config_version -------------------------------------------------------------

config_version = _tabla(
    "config_version",
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("version", Text, nullable=False),
    Column("sha256", HUELLA, nullable=False),
    Column("schema_version", Text, nullable=False),
    Column("content", JSONB, nullable=False),
    Column("source_file", Text, nullable=False),
    Column("loaded_at", TIEMPO, nullable=False),
    UniqueConstraint("version"),
    UniqueConstraint("sha256"),
    _hex64("sha256"),
    _objeto("content"),
)

# --- TAB-02 load_run y load_rejection --------------------------------------------------

load_run = _tabla(
    "load_run",
    Column("id", ID, primary_key=True),
    Column("file_name", Text, nullable=False),
    Column("file_sha256", HUELLA, nullable=False),
    Column("format", Text, nullable=False),
    Column("record_type", Text),
    Column("started_at", TIEMPO, nullable=False),
    Column("finished_at", TIEMPO),
    Column("loaded", Integer, nullable=False),
    Column("rejected", Integer, nullable=False),
    Column("duplicates", Integer, nullable=False),
    Column("rejected_by_reason", JSONB, nullable=False),
    Column("config_version_id", BigInteger, ForeignKey("config_version.id"), nullable=False),
    _hex64("file_sha256"),
    _en("format", FORMATOS_CARGA),
    _en("record_type", TipoRegistro),
    # El tipo del archivo solo existe en CSV (design.md CTR-03).
    CheckConstraint("format = 'csv' OR record_type IS NULL", name="record_type_solo_csv"),
    CheckConstraint("finished_at >= started_at", name="finished_at_orden"),
    CheckConstraint(
        "loaded >= 0 AND rejected >= 0 AND duplicates >= 0", name="conteos_no_negativos"
    ),
    _objeto("rejected_by_reason"),
)

load_rejection = _tabla(
    "load_rejection",
    Column("load_run_id", ID, ForeignKey("load_run.id"), nullable=False),
    Column("line_number", Integer, nullable=False),
    Column("record_type", Text),
    Column("reason", Text, nullable=False),
    Column("field", Text),
    PrimaryKeyConstraint("load_run_id", "line_number"),
    CheckConstraint("line_number >= 1", name="line_number_positivo"),
    _en("record_type", TipoRegistro),
    _motivo_rechazo("reason"),
    # Solo el nombre del campo, nunca un valor del renglón (R-20).
    CheckConstraint(f"field ~ '^{_CAMPO}$'", name="field_nombre"),
)

# --- TAB-03 product y product_identifier -----------------------------------------------

product = _tabla(
    "product",
    Column("id", ID, primary_key=True),
    Column("brand", Text),
    Column("model", Text),
    Column("content", Text),
    Column("category", Text),
    Column("created_at", TIEMPO, nullable=False),
    _en("category", Categoria),
)

product_identifier = _tabla(
    "product_identifier",
    Column("kind", Text, nullable=False),
    Column("value", Text, nullable=False),
    Column("product_id", ID, ForeignKey("product.id"), nullable=False),
    PrimaryKeyConstraint("kind", "value"),
    _en("kind", CLASES_IDENTIFICADOR),
    Index("ix_product_identifier_product_id", "product_id"),
)

# --- TAB-04 listing --------------------------------------------------------------------

listing = _tabla(
    "listing",
    Column("id", ID, primary_key=True),
    Column("product_id", ID, ForeignKey("product.id"), nullable=False),
    Column("retailer_code", Text, nullable=False),
    Column("store_code", Text),
    Column("canonical_url", Text, nullable=False),
    Column("platform", Text),
    Column("pickup_location", Text),
    Column("first_seen_at", TIEMPO, nullable=False),
    # Plataforma y ciudad de recogida solo en la publicación de un particular (DEC-223).
    CheckConstraint(
        f"retailer_code = '{_PARTICULAR}' OR (platform IS NULL AND pickup_location IS NULL)",
        name="solo_particular",
    ),
    Index("ix_listing_product_id", "product_id"),
)
Index(
    "uq_listing_retailer_url_store",
    listing.c.retailer_code,
    listing.c.canonical_url,
    func.coalesce(listing.c.store_code, ""),
    unique=True,
)

# --- TAB-05 a TAB-07: hypertables (las convierte 0002) ---------------------------------

price_observation = _tabla(
    "price_observation",
    Column("observation_id", ID, nullable=False),
    Column("observed_at", TIEMPO, nullable=False),
    Column("listing_id", ID, ForeignKey("listing.id"), nullable=False),
    Column("product_id", ID, ForeignKey("product.id"), nullable=False),
    Column("price", MONTO, nullable=False),
    Column("was_price", MONTO),
    Column("currency", Text),
    Column("seller", Text, nullable=False),
    Column("condition", Text),
    Column("purchase_mode", Text, nullable=False),
    Column("is_clearance", Boolean),
    Column("tax_location", Text),
    Column("shipping_to_me", MONTO),
    Column("weight_kg", SIN_REDONDEAR),
    Column("dims_cm", JSONB),
    Column("category", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("identification", Text, nullable=False),
    Column("msrp_value", MONTO),
    Column("msrp_source", Text),
    Column("msrp_date", Date),
    Column("schema_version", Text, nullable=False),
    # Se conservan del contrato 3.1 (design.md RNF-7).
    Column("source_type", Text),
    Column("extraction_method", Text),
    Column("load_run_id", ID, ForeignKey("load_run.id")),
    PrimaryKeyConstraint("observation_id", "observed_at"),
    CheckConstraint("price > 0", name="price_positivo"),
    _en("seller", Vendedor),
    _en("condition", Condicion),
    _en("purchase_mode", ModoCompra),
    _en("category", Categoria),
    _en("identification", Identificacion),
    _en("schema_version", VERSIONES_ACEPTADAS),
    _objeto("dims_cm"),
)
Index(
    "ix_price_observation_product_id_observed_at",
    price_observation.c.product_id,
    price_observation.c.observed_at.desc(),
)
Index(
    "ix_price_observation_listing_id_observed_at",
    price_observation.c.listing_id,
    price_observation.c.observed_at.desc(),
)

availability_observation = _tabla(
    "availability_observation",
    Column("observation_id", ID, nullable=False),
    Column("observed_at", TIEMPO, nullable=False),
    Column("listing_id", ID, ForeignKey("listing.id"), nullable=False),
    Column("store_code", Text),
    Column("state", Text, nullable=False),
    Column("quantity", Integer),
    Column("text", Text),
    Column("scope", Text),
    Column("add_to_cart", Boolean),
    PrimaryKeyConstraint("observation_id", "observed_at"),
    _en("state", EstadoDisponibilidad),
)
Index(
    "ix_availability_observation_listing_id_observed_at",
    availability_observation.c.listing_id,
    availability_observation.c.observed_at.desc(),
)

amazon_listing_observation = _tabla(
    "amazon_listing_observation",
    Column("observation_id", ID, nullable=False),
    Column("observed_at", TIEMPO, nullable=False),
    Column("product_id", ID, ForeignKey("product.id"), nullable=False),
    Column("listing_id", ID, ForeignKey("listing.id"), nullable=False),
    Column("buy_box_price", MONTO),
    Column("sellers_new", Integer),
    Column("rank_main", Integer),
    Column("rank_sub", Integer),
    Column("reviews", Integer),
    Column("bought_last_month", Integer),
    PrimaryKeyConstraint("observation_id", "observed_at"),
)
Index(
    "ix_amazon_listing_observation_product_id_observed_at",
    amazon_listing_observation.c.product_id,
    amazon_listing_observation.c.observed_at.desc(),
)

# --- TAB-08 ingest_receipt -------------------------------------------------------------

ingest_receipt = _tabla(
    "ingest_receipt",
    Column("idempotency_key", Text, primary_key=True),
    Column("observation_id", ID, nullable=False),
    Column("source", Text, nullable=False),
    Column("received_at", TIEMPO, nullable=False),
    Column("load_run_id", ID, ForeignKey("load_run.id")),
    _en("source", ORIGENES_RECIBO),
    CheckConstraint("source <> 'file' OR load_run_id IS NOT NULL", name="file_con_carga"),
)

# --- TAB-09 capturas (CTR-04) ----------------------------------------------------------


def _comunes_captura() -> tuple[object, ...]:
    """``id``, carga, huella de idempotencia (sha256, única) y hora de la captura."""
    return (
        Column("id", ID, primary_key=True),
        Column("load_run_id", ID, ForeignKey("load_run.id"), nullable=False),
        Column("idempotency_key", HUELLA, nullable=False),
        Column("captured_at", TIEMPO, nullable=False),
        UniqueConstraint("idempotency_key"),
        _hex64("idempotency_key"),
    )


def _producto_captura(obligatorio: bool) -> tuple[object, ...]:
    """``gtin``, ``brand``, ``model`` (CTR-04) y el producto identificado."""
    return (
        Column("product_id", ID, ForeignKey("product.id"), nullable=not obligatorio),
        Column("gtin", Text),
        Column("brand", Text),
        Column("model", Text),
    )


local_comparable = _tabla(
    "local_comparable",
    *_comunes_captura(),
    *_producto_captura(obligatorio=True),
    Column("condition", Text, nullable=False),
    Column("asking_price", MONTO, nullable=False),
    Column("currency", Text, nullable=False),
    Column("exchange_rate", SIN_REDONDEAR),
    Column("price_usd", CONVERSION, nullable=False),
    Column("city", Text, nullable=False),
    Column("date", Date, nullable=False),
    Column("sold", Boolean, nullable=False),
    _en("condition", Condicion),
    _en("currency", Moneda),
    CheckConstraint("asking_price > 0", name="asking_price_positivo"),
    CheckConstraint("exchange_rate > 0", name="exchange_rate_positivo"),
    CheckConstraint(
        f"currency <> '{Moneda.MXN.value}' OR exchange_rate IS NOT NULL",
        name="mxn_con_tipo_de_cambio",
    ),
    Index("ix_local_comparable_product_id_condition", "product_id", "condition"),
)

local_estimate = _tabla(
    "local_estimate",
    *_comunes_captura(),
    *_producto_captura(obligatorio=True),
    Column("condition", Text),
    Column("price", MONTO, nullable=False),
    Column("date", Date, nullable=False),
    _en("condition", Condicion),
    Index("ix_local_estimate_product_id_condition", "product_id", "condition"),
)

msrp_capture = _tabla(
    "msrp_capture",
    *_comunes_captura(),
    *_producto_captura(obligatorio=True),
    Column("value", MONTO, nullable=False),
    Column("source", Text, nullable=False),
    Column("date", Date, nullable=False),
)

local_demand = _tabla(
    "local_demand",
    *_comunes_captura(),
    Column("category", Text, nullable=False),
    Column("level", Text, nullable=False),
    Column("date", Date, nullable=False),
    _en("category", Categoria),
    _en("level", DemandaLocal),
)
Index("ix_local_demand_category_date", local_demand.c.category, local_demand.c.date.desc())

store_visit = _tabla(
    "store_visit",
    *_comunes_captura(),
    Column("store_code", Text, nullable=False),
    *_producto_captura(obligatorio=False),
    Column("evaluation_id", ID),
    Column("result", Text, nullable=False),
    Column("visited_at", TIEMPO, nullable=False),
    _en("result", ResultadoVisita),
    CheckConstraint(
        "product_id IS NOT NULL OR evaluation_id IS NOT NULL", name="producto_u_oportunidad"
    ),
)

opportunity_outcome = _tabla(
    "opportunity_outcome",
    *_comunes_captura(),
    Column("evaluation_id", ID, nullable=False),
    Column("channel", Text, nullable=False),
    Column("units", Integer, nullable=False),
    Column("purchase_price", MONTO, nullable=False),
    Column("sale_price", MONTO, nullable=False),
    Column("actual_costs", MONTO, nullable=False),
    Column("purchased_on", Date, nullable=False),
    Column("sold_on", Date, nullable=False),
    _en("channel", Canal),
)

client_request = _tabla(
    "client_request",
    *_comunes_captura(),
    Column("client_alias", Text, nullable=False),
    Column("items", TEXTOS, nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("accepted_conditions", TEXTOS, nullable=False),
    Column("modality", Text, nullable=False),
    Column("postal_code", Text),
    Column("date", Date, nullable=False),
    CheckConstraint("cardinality(items) BETWEEN 1 AND 3", name="items_de_1_a_3"),
    CheckConstraint("quantity >= 1", name="quantity_positiva"),
    CheckConstraint("cardinality(accepted_conditions) >= 1", name="accepted_conditions_no_vacio"),
    _todos_en("accepted_conditions", Condicion),
    _en("modality", Modalidad),
)

# --- TAB-10 evaluation -----------------------------------------------------------------

_RECHAZADA = Resultado.RECHAZADA_VALIDACION.value
_ASIGNADO = Resultado.NIVEL_ASIGNADO.value

#: Lo que agrega ``0003_registro_de_rechazo`` a TAB-10 (DEC-250): el número de renglón del
#: rechazo de una carga por archivo, que con ``load_run_id`` lo liga a ``load_rejection``
#: (TAB-02), y que un rechazo no guarde ``input_snapshot`` (ni nada del renglón).
COLUMNAS_0003 = {"evaluation": ("line_number",)}
RESTRICCIONES_0003 = {
    "evaluation": (
        "ck_evaluation_line_number_positivo",
        "ck_evaluation_renglon_del_rechazo",
        "ck_evaluation_rechazo_sin_entrada",
        "fk_evaluation_load_run_id_line_number_load_rejection",
    )
}


#: Columnas cuyo tipo cambia ``0004_price_usd_sin_escala`` (DEC-258): ``price_usd`` de
#: ``local_comparable`` pasa de ``numeric(14,4)`` a ``numeric`` sin escala.
CAMBIOS_0004 = {"local_comparable": ("price_usd",)}


def _evaluation(md: MetaData, *, con_0003: bool) -> Table:
    """TAB-10 en ``md``; ``con_0003`` agrega lo de ``0003_registro_de_rechazo``."""
    agregados_0003: tuple[object, ...] = (
        Column("line_number", Integer),
        CheckConstraint("line_number >= 1", name="line_number_positivo"),
        # Renglón solo y siempre en el rechazo de una carga por archivo (DEC-250).
        CheckConstraint(
            f"(result = '{_RECHAZADA}' AND load_run_id IS NOT NULL) = (line_number IS NOT NULL)",
            name="renglon_del_rechazo",
        ),
        # Un rechazo no guarda nada del renglón: sin ``input_snapshot`` (DEC-250, CTR-06).
        CheckConstraint(
            f"result <> '{_RECHAZADA}' OR input_snapshot IS NULL", name="rechazo_sin_entrada"
        ),
        ForeignKeyConstraint(
            ["load_run_id", "line_number"],
            ["load_rejection.load_run_id", "load_rejection.line_number"],
        ),
    )
    tabla = _tabla(
        "evaluation",
        Column("id", ID, primary_key=True),
        Column("evaluated_at", TIEMPO, nullable=False),
        Column("offer_observation_id", ID),
        Column("listing_id", ID, ForeignKey("listing.id")),
        Column("product_id", ID, ForeignKey("product.id")),
        Column("config_version_id", BigInteger, ForeignKey("config_version.id"), nullable=False),
        Column("rn_versions", JSONB, nullable=False),
        Column("result", Text, nullable=False),
        Column("main_reason", Text),
        Column("reasons", TEXTOS, nullable=False),
        Column("rejection_reason", Text),
        Column("marks", TEXTOS, nullable=False),
        Column("price_quality", Text),
        Column("confidence", Text),
        Column("identification", Text),
        Column("references", JSONB),
        Column("advertised_discount", SIN_REDONDEAR),
        Column("real_discount", SIN_REDONDEAR),
        Column("purchase_cost", MONTO),
        Column("chosen_channel", Text),
        Column("alert_level", Text),
        Column("alert_channel", Text),
        Column("observations_used", JSONB, nullable=False),
        Column("input_snapshot", JSONB),
        Column("previous_evaluation_id", ID, ForeignKey("evaluation.id")),
        Column("changed_references", TEXTOS, nullable=False),
        Column("no_longer_recommended", Boolean, nullable=False),
        Column("load_run_id", ID, ForeignKey("load_run.id")),
        _objeto("rn_versions"),
        _en("result", Resultado),
        _en("main_reason", Motivo),
        _todos_en("reasons", Motivo),
        _motivo_rechazo("rejection_reason"),
        _en("price_quality", CalidadPrecio),
        _en("confidence", Confianza),
        _en("identification", Identificacion),
        _en("chosen_channel", Canal),
        _en("alert_level", Nivel),
        _en("alert_channel", Canal),
        _todos_en("changed_references", ReferenciaPrecio),
        CheckConstraint(
            "jsonb_typeof(observations_used) = 'array'", name="observations_used_arreglo"
        ),
        # Invariantes del registro (REQ §3.2.2 a §3.2.4; RegistroEvaluacion de T04).
        CheckConstraint("main_reason IS NOT DISTINCT FROM reasons[1]", name="motivo_principal"),
        CheckConstraint(
            f"(result = '{_RECHAZADA}') = (rejection_reason IS NOT NULL)", name="rechazo_con_motivo"
        ),
        CheckConstraint(
            f"result <> '{_RECHAZADA}' OR offer_observation_id IS NULL", name="rechazo_sin_oferta"
        ),
        CheckConstraint(
            f"(result = '{_ASIGNADO}') = (alert_level IS NOT NULL)"
            f" AND (result = '{_ASIGNADO}') = (alert_channel IS NOT NULL)"
            f" AND (result <> '{_ASIGNADO}' OR chosen_channel IS NOT NULL)",
            name="aviso_solo_con_nivel",
        ),
        CheckConstraint(
            "previous_evaluation_id IS NOT NULL"
            " OR (cardinality(changed_references) = 0 AND NOT no_longer_recommended)",
            name="reevaluacion",
        ),
        *(agregados_0003 if con_0003 else ()),
        md=md,
    )
    Index(
        "ix_evaluation_listing_id_evaluated_at",
        tabla.c.listing_id,
        tabla.c.evaluated_at.desc(),
    )
    Index("ix_evaluation_product_id_result", tabla.c.product_id, tabla.c.result)
    return tabla


evaluation = _evaluation(metadata, con_0003=True)

# --- TAB-11 evaluation_channel ---------------------------------------------------------

evaluation_channel = _tabla(
    "evaluation_channel",
    Column("evaluation_id", ID, ForeignKey("evaluation.id", ondelete="CASCADE"), nullable=False),
    Column("channel", Text, nullable=False),
    Column("state", Text, nullable=False),
    Column("closed_causes", TEXTOS, nullable=False),
    Column("review_causes", TEXTOS, nullable=False),
    # Amazon: el botón de compra o, sin oferta hoy, el habitual en Amazon (una mediana).
    Column("sale_price", CONVERSION),
    Column("selling_cost", MONTO),
    Column("net_margin", MONTO),
    Column("net_margin_pct", SIN_REDONDEAR),
    Column("returns_cost", MONTO),
    Column("drop_penalty", MONTO),
    Column("adjusted_margin", MONTO),
    Column("adjusted_margin_pct", SIN_REDONDEAR),
    Column("units", Integer),
    Column("days_to_recover", SIN_REDONDEAR),
    Column("monthly_yield_pct", SIN_REDONDEAR),
    Column("level", Text),
    Column("calculated_level", Text),
    Column("total_profit", MONTO),
    Column("marks", TEXTOS, nullable=False),
    PrimaryKeyConstraint("evaluation_id", "channel"),
    _en("channel", Canal),
    _en("state", EstadoCanal),
    _todos_en("closed_causes", CausaCanalCerrado),
    _todos_en("review_causes", CausaCanalPorRevisar),
    _en("level", Nivel),
    _en("calculated_level", Nivel),
)

# --- TAB-12 vista open_opportunity -----------------------------------------------------

#: La evaluación más reciente de cada publicación, si es ``NIVEL_ASIGNADO`` (REQ §3.2.5).
#: Recorre el índice (``listing_id``, ``evaluated_at`` desc) de TAB-10; ``id`` desempata.
#: Texto fijo (sin formatear): una prueba comprueba que el código es el de ``Resultado``.
SQL_OPEN_OPPORTUNITY = (
    "SELECT latest.* FROM ("
    "SELECT DISTINCT ON (listing_id) * FROM evaluation"
    " WHERE listing_id IS NOT NULL"
    " ORDER BY listing_id, evaluated_at DESC, id DESC"
    ") AS latest WHERE latest.result = 'NIVEL_ASIGNADO'"
)

open_opportunity = Table(
    "open_opportunity",
    metadata_vistas,
    *(Column(c.name, c.type, nullable=c.nullable) for c in evaluation.columns),
)

# --- El modelo de 0001_esquema ----------------------------------------------------------


def _modelo_0001() -> MetaData:
    """Metadatos de TAB-01 a TAB-11 como los deja ``0001_esquema`` (sin lo de 0003). Las
    pruebas comparan con ellos la copia congelada de esa migración (DEC-179)."""
    md = MetaData(naming_convention=CONVENCION_NOMBRES)
    for tabla in metadata.sorted_tables:
        if tabla.name != "evaluation":
            tabla.to_metadata(md)
    _evaluation(md, con_0003=False)
    return md


#: TAB-01 a TAB-11 en ``0001_esquema``. ``metadata`` es el modelo vigente (``head``).
metadata_0001 = _modelo_0001()
