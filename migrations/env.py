"""Entorno de Alembic de OIP (CMP-19; design.md §4, §5 y RNF-8).

- **Conexión:** la que pasa quien llama en ``config.attributes["connection"]`` (las pruebas
  de integración, con ``OIP_TEST_DATABASE_URL``); si no hay, la URL de ``OIP_DATABASE_URL``.
  La URL nunca está en el repo ni se escribe en los logs. La contraseña del ``podman
  secret`` la arma la conexión de T06 y el contenedor de migraciones de T23.
- **Modo sin conexión** (``alembic upgrade head --sql``): solo genera el SQL de PostgreSQL;
  no necesita URL.
"""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine, pool

from oip.persistencia.tablas import metadata

config = context.config
target_metadata = metadata

_VARIABLE_URL = "OIP_DATABASE_URL"


def _sin_conexion() -> None:
    context.configure(
        dialect_name="postgresql",
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _migrar(conexion) -> None:
    context.configure(connection=conexion, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def _con_conexion() -> None:
    conexion = config.attributes.get("connection")
    if conexion is not None:
        _migrar(conexion)
        return
    url = os.environ.get(_VARIABLE_URL, "").strip()
    if not url:
        raise RuntimeError(f"falta la variable de entorno {_VARIABLE_URL}")
    motor = create_engine(url, poolclass=pool.NullPool)
    try:
        with motor.connect() as conexion:
            _migrar(conexion)
    finally:
        motor.dispose()


if context.is_offline_mode():
    _sin_conexion()
else:
    _con_conexion()
