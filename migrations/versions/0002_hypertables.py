"""0002_hypertables: TAB-05 a TAB-07 como hypertables de TimescaleDB (CMP-19).

design.md §4 (ADR-013, ADR-028, DEC-179): ``create_hypertable`` sobre ``observed_at`` con
**chunks de 7 días**, fijados aquí. Sin compresión, agregados continuos ni retención: llegan
con la parte A (Pendiente 8). Esta migración pasa por la **PoC** de DEC-179 en T23 antes de
producción.

**Reversión** (Migration Plan): solo sin datos. Si alguna de las tres tablas tiene renglones,
``downgrade`` se detiene sin tocar nada (el historial de precios es un activo de OIP,
DEC-123); para volver atrás con datos se restaura el respaldo. Sin datos, borra las
hypertables y las vuelve a crear como tablas normales con la misma definición de
``0001_esquema``. La extensión ``timescaledb`` se queda instalada.

Revision ID: 0002_hypertables
Revises: 0001_esquema
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from alembic import op

revision = "0002_hypertables"
down_revision = "0001_esquema"
branch_labels = None
depends_on = None

#: Hypertables (TAB-05 a TAB-07), en orden de creación.
HYPERTABLES = ("price_observation", "availability_observation", "amazon_listing_observation")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    op.execute(
        "SELECT create_hypertable('price_observation', 'observed_at',"
        " chunk_time_interval => INTERVAL '7 days')"
    )
    op.execute(
        "SELECT create_hypertable('availability_observation', 'observed_at',"
        " chunk_time_interval => INTERVAL '7 days')"
    )
    op.execute(
        "SELECT create_hypertable('amazon_listing_observation', 'observed_at',"
        " chunk_time_interval => INTERVAL '7 days')"
    )


def _esquema() -> ModuleType:
    """``0001_esquema``, para volver a crear las tablas con su definición congelada."""
    ruta = Path(__file__).with_name("0001_esquema.py")
    spec = importlib.util.spec_from_file_location("oip_migracion_0001_esquema", ruta)
    if spec is None or spec.loader is None:
        raise RuntimeError("no se encontró la migración 0001_esquema")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN"
        " IF EXISTS (SELECT 1 FROM price_observation)"
        " OR EXISTS (SELECT 1 FROM availability_observation)"
        " OR EXISTS (SELECT 1 FROM amazon_listing_observation) THEN"
        " RAISE EXCEPTION '0002_hypertables solo se revierte sin datos: restaure el respaldo';"
        " END IF;"
        " END $$"
    )
    for tabla in reversed(HYPERTABLES):
        op.drop_table(tabla)
    for crear in _esquema().CREAR_HYPERTABLES:
        crear()
