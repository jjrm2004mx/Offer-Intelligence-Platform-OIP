"""0004_price_usd_sin_escala: ``local_comparable.price_usd`` en ``numeric`` sin escala (CMP-19).

DEC-258 (decisión 3 del #34): ``price_usd`` es ``askingPrice ÷ exchangeRate`` **sin
redondear** (CTR-04, S-23, DEC-226 b). ``numeric(14,4)`` de ``0001_esquema`` lo redondeaba
a 4 decimales en la base, mientras la memoria guardaba el valor exacto; con ``numeric`` sin
escala las dos guardan el mismo valor. Cambiar de ``numeric(14,4)`` a ``numeric`` no cambia
ningún valor guardado.

Copia congelada (DEC-179): los nombres van escritos aquí y no se importan;
``tests/test_migraciones.py`` comprueba que coincide con ``oip.persistencia.tablas``
(``CAMBIOS_0004``). ``0001`` a ``0003`` no se editan (DEC-272).

**Reversión:** vuelve a ``numeric(14,4)`` solo si ningún valor cambia. Si un ``price_usd``
tiene más de 4 decimales o no cabe en ``numeric(14,4)``, ``downgrade`` se detiene sin tocar
nada (PostgreSQL lo redondearía en silencio, y el repositorio no redondea, DEC-207); para
volver atrás con esos datos se restaura el respaldo.

Revision ID: 0004_price_usd_sin_escala
Revises: 0003_registro_de_rechazo
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_price_usd_sin_escala"
down_revision = "0003_registro_de_rechazo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "local_comparable",
        "price_usd",
        type_=sa.Numeric(),
        existing_type=sa.Numeric(precision=14, scale=4),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN"
        " IF EXISTS (SELECT 1 FROM local_comparable"
        " WHERE price_usd <> round(price_usd, 4) OR abs(price_usd) >= 10000000000) THEN"
        " RAISE EXCEPTION '0004_price_usd_sin_escala no se revierte si un price_usd"
        " cambiaría: restaure el respaldo';"
        " END IF;"
        " END $$"
    )
    op.alter_column(
        "local_comparable",
        "price_usd",
        type_=sa.Numeric(precision=14, scale=4),
        existing_type=sa.Numeric(),
        existing_nullable=False,
    )
