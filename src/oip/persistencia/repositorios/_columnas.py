"""Columnas: la normalización de cada valor como lo guarda y lo devuelve PostgreSQL (CMP-20).

La usan las dos implementaciones del repositorio antes de escribir (ver ``_filas``).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Integer,
    Numeric,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as TipoUUID

from oip.evaluacion._canonico import a_json, desde_json

Fila = dict[str, Any]

#: Columnas **derivadas** que el dominio no lee de vuelta: ``price_usd`` de un comparable se
#: recalcula de ``asking_price`` y ``exchange_rate`` (``ComparableLocal.price_usd``, sin
#: redondear, S-23). Su escala (numeric(14,4), design.md §4) la aplica la base; ver el
#: pendiente de T06 en el issue #34.
_DERIVADAS = frozenset({("local_comparable", "price_usd")})

# --- Normalización (la misma en memoria y en PostgreSQL) ----------------------------------


def _numeric(valor: Decimal, tipo: Numeric, ruta: str) -> Decimal:
    if not valor.is_finite():
        raise ValueError(f"{ruta}: número no finito")
    texto = format(valor, "f")
    if texto.startswith("-") and Decimal(texto) == 0:
        texto = texto[1:]  # numeric no tiene cero negativo
    entero, _, decimales = texto.lstrip("-").partition(".")
    escala, precision = tipo.scale, tipo.precision
    if escala is not None and precision is not None:
        if len(decimales) > escala:
            raise ValueError(
                f"{ruta}: más de {escala} decimales; el repositorio no redondea (DEC-207)"
            )
        if len(entero.lstrip("0")) > precision - escala:
            raise ValueError(f"{ruta}: no cabe en numeric({precision},{escala})")
        if escala and len(decimales) < escala:
            texto += ("" if decimales else ".") + "0" * (escala - len(decimales))
    return Decimal(texto)


def _texto(valor: Any, ruta: str) -> str:
    if type(valor) is not str:
        raise TypeError(f"{ruta}: se esperaba texto")
    if not valor.strip():
        raise ValueError(f"{ruta}: texto vacío; lo ausente es None (vacío = ausente)")
    if "\x00" in valor:
        raise ValueError(f"{ruta}: carácter nulo no admitido")
    return valor


def _valor(columna: Any, valor: Any, ruta: str) -> Any:
    tipo = columna.type
    if isinstance(valor, Enum):
        valor = valor.value
    if valor is None:
        return None
    if isinstance(valor, float):
        raise TypeError(f"{ruta}: float no admitido; use Decimal")
    if isinstance(tipo, Numeric):
        if type(valor) is int:
            valor = Decimal(valor)
        if not isinstance(valor, Decimal):
            raise TypeError(f"{ruta}: se esperaba Decimal")
        if (columna.table.name, columna.name) in _DERIVADAS:
            return valor
        return _numeric(valor, tipo, ruta)
    if isinstance(tipo, Integer | BigInteger):
        if type(valor) is not int:
            raise TypeError(f"{ruta}: se esperaba un entero")
        return valor
    if isinstance(tipo, Boolean):
        if type(valor) is not bool:
            raise TypeError(f"{ruta}: se esperaba un booleano")
        return valor
    if isinstance(tipo, DateTime):
        if not isinstance(valor, dt.datetime) or valor.utcoffset() is None:
            raise TypeError(f"{ruta}: se esperaba una fecha y hora con desfase")
        return valor.astimezone(dt.UTC)
    if isinstance(tipo, Date):
        if type(valor) is not dt.date:
            raise TypeError(f"{ruta}: se esperaba una fecha")
        return valor
    if isinstance(tipo, TipoUUID):
        if not isinstance(valor, UUID):
            raise TypeError(f"{ruta}: se esperaba un UUID")
        return valor
    if isinstance(tipo, ARRAY):
        if not isinstance(valor, list | tuple):
            raise TypeError(f"{ruta}: se esperaba una lista")
        return [
            _texto(e.value if isinstance(e, Enum) else e, f"{ruta}[{i}]")
            for i, e in enumerate(valor)
        ]
    if isinstance(tipo, JSONB):
        if type(valor) is not str:
            raise TypeError(f"{ruta}: se esperaba el texto JSON canónico")
        return valor
    if isinstance(tipo, Text | CHAR):
        return _texto(valor, ruta)
    raise TypeError(f"{ruta}: tipo de columna no admitido")  # pragma: no cover


def normalizar(tabla: Table, fila: Mapping[str, Any]) -> Fila:
    """La fila completa de ``tabla`` (las columnas que faltan, en ``None``) con cada valor
    como lo guarda y lo devuelve PostgreSQL. Levanta ``TypeError`` o ``ValueError`` (con la
    tabla y la columna, sin el valor) si un valor no cabe sin cambiarlo."""
    desconocidas = set(fila) - set(tabla.c.keys())
    if desconocidas:
        raise ValueError(f"{tabla.name}: columnas desconocidas {sorted(desconocidas)}")
    salida: Fila = {}
    for columna in tabla.columns:
        ruta = f"{tabla.name}.{columna.name}"
        valor = _valor(columna, fila.get(columna.name), ruta)
        if valor is None and not columna.nullable and columna.autoincrement is not True:
            raise ValueError(f"{ruta}: obligatorio")
        salida[columna.name] = valor
    return salida


def json_o_none(valor: Any, tipo: Any) -> str | None:
    return None if valor is None else a_json(valor, tipo)


def leer_json_o_none(texto: str | None, tipo: Any) -> Any:
    return None if texto is None else desde_json(texto, tipo)


def enum_o_none(enum: type[Enum], valor: str | None) -> Any:
    return None if valor is None else enum(valor)


def utc(valor: dt.datetime) -> dt.datetime:
    return valor.astimezone(dt.UTC)


def instante_utc(valor: dt.datetime, nombre: str = "instante") -> dt.datetime:
    """El instante de una lectura, en UTC. Siempre lo pasa quien llama (sin reloj)."""
    if not isinstance(valor, dt.datetime) or valor.utcoffset() is None:
        raise TypeError(f"{nombre}: se esperaba una fecha y hora con desfase")
    return valor.astimezone(dt.UTC)
