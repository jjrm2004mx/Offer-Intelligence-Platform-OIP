"""0003_registro_de_rechazo: el registro de un rechazo de validación sin el renglón (CMP-19).

DEC-250: una observación que falla el paso 1 (``RECHAZADA_VALIDACION``, B20) deja un registro
en TAB-10 que **no guarda nada del renglón** y lleva su origen. Esta migración agrega a
``evaluation``:

- ``line_number`` (entero, nulo): el número de renglón del rechazo en una carga por archivo.
  Con ``load_run_id`` lo liga a ``load_rejection`` (TAB-02) por una clave foránea compuesta.
- ``ck_evaluation_line_number_positivo``: el renglón empieza en 1, como en ``load_rejection``.
- ``ck_evaluation_renglon_del_rechazo``: hay renglón solo y siempre en el rechazo de una
  carga por archivo (``RECHAZADA_VALIDACION`` con ``load_run_id``).
- ``ck_evaluation_rechazo_sin_entrada``: un rechazo no lleva ``input_snapshot`` (CTR-06;
  RNF-3 no aplica a un rechazo). Solo en ese sentido, como lo pide DEC-250: que una
  evaluación lleve su ``input_snapshot`` lo garantiza el repositorio (CMP-20), no un
  ``CHECK``, para no invalidar las filas que ya escriben las pruebas de ``0001``.

La vista ``open_opportunity`` (TAB-12) se vuelve a crear para que tenga la columna nueva
(``SELECT *`` se expande al crear la vista). Copia congelada (DEC-179): los códigos van
escritos aquí y no se importan; ``tests/test_migraciones.py`` comprueba que coincide con
``oip.persistencia.tablas``. ``0001`` y ``0002`` no se editan.

**Reversión:** borra la vista, las restricciones y la columna, y vuelve a crear la vista
como la deja ``0001_esquema``. Se pierde el número de renglón de los rechazos guardados.
Las restricciones se validan sobre los registros que ya existan: se aplica antes de que haya
rechazos o evaluaciones guardados (no hay datos de producción antes de T23).

Revision ID: 0003_registro_de_rechazo
Revises: 0002_hypertables
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_registro_de_rechazo"
down_revision = "0002_hypertables"
branch_labels = None
depends_on = None

_RECHAZADA = "RECHAZADA_VALIDACION"

#: TAB-12, mismo texto que ``0001_esquema``.
SQL_OPEN_OPPORTUNITY = (
    "SELECT latest.* FROM ("
    "SELECT DISTINCT ON (listing_id) * FROM evaluation"
    " WHERE listing_id IS NOT NULL"
    " ORDER BY listing_id, evaluated_at DESC, id DESC"
    ") AS latest WHERE latest.result = 'NIVEL_ASIGNADO'"
)


def upgrade() -> None:
    op.add_column("evaluation", sa.Column("line_number", sa.Integer(), nullable=True))
    op.create_check_constraint(
        op.f("ck_evaluation_line_number_positivo"), "evaluation", "line_number >= 1"
    )
    op.create_check_constraint(
        op.f("ck_evaluation_renglon_del_rechazo"),
        "evaluation",
        f"(result = '{_RECHAZADA}' AND load_run_id IS NOT NULL) = (line_number IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_evaluation_rechazo_sin_entrada"),
        "evaluation",
        f"result <> '{_RECHAZADA}' OR input_snapshot IS NULL",
    )
    op.create_foreign_key(
        op.f("fk_evaluation_load_run_id_line_number_load_rejection"),
        "evaluation",
        "load_rejection",
        ["load_run_id", "line_number"],
        ["load_run_id", "line_number"],
    )
    op.execute("DROP VIEW open_opportunity")
    op.execute(f"CREATE VIEW open_opportunity AS {SQL_OPEN_OPPORTUNITY}")


def downgrade() -> None:
    op.execute("DROP VIEW open_opportunity")
    op.drop_constraint(
        op.f("fk_evaluation_load_run_id_line_number_load_rejection"),
        "evaluation",
        type_="foreignkey",
    )
    op.drop_constraint(op.f("ck_evaluation_rechazo_sin_entrada"), "evaluation", type_="check")
    op.drop_constraint(op.f("ck_evaluation_renglon_del_rechazo"), "evaluation", type_="check")
    op.drop_constraint(op.f("ck_evaluation_line_number_positivo"), "evaluation", type_="check")
    op.drop_column("evaluation", "line_number")
    op.execute(f"CREATE VIEW open_opportunity AS {SQL_OPEN_OPPORTUNITY}")
