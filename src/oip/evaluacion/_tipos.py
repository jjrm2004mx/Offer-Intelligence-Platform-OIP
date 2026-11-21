"""Tipos admitidos por la serialización canónica y su verificación estricta (CMP-09).

Apoyo de ``oip.evaluacion._canonico`` y de ``oip.evaluacion.contexto``: lee las anotaciones
de dataclasses y modelos de pydantic y comprueba, **sin convertir**, que un valor es del tipo
declarado (DEC-238): ni ``bool`` como entero, ni texto como número, ni ``float`` como monto,
ni lista donde va una tupla. Los mensajes citan la ruta y el tipo, nunca el valor (DEC-181).

Tipos admitidos: ``None``, ``bool``, ``int``, ``str``, ``Decimal`` finito, ``datetime`` con
desfase, ``date``, ``UUID``, enums, ``Literal``, uniones, ``tuple[X, ...]``, mapas,
dataclasses, modelos de pydantic y ``Any`` (solo valores de JSON y ``Decimal``).
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import types
import typing
from collections.abc import Mapping
from decimal import Decimal
from enum import Enum
from functools import cache
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel

__all__ = [
    "DECIMAL_ANY",
    "campos_dataclass",
    "campos_modelo",
    "elemento_de_tupla",
    "es_mapa",
    "es_union",
    "exigir_decimal",
    "exigir_entero",
    "ruta_de",
    "sin_annotated",
    "verificar_any",
    "verificar_dataclass",
    "verificar_escalar",
    "verificar_tipo",
]

#: Marca de un ``Decimal`` dentro de un campo ``Any`` (la forma de la huella de la
#: configuración, ``oip.configuracion``).
DECIMAL_ANY = "$decimal"


# --- Anotaciones ------------------------------------------------------------------------


#: Tipos de pydantic que en tiempo de ejecución no son la clase de Python que validan.
_EQUIVALENTES: dict[Any, type] = {AwareDatetime: dt.datetime}


def sin_annotated(tipo: Any) -> Any:
    while typing.get_origin(tipo) is typing.Annotated:
        tipo = typing.get_args(tipo)[0]
    return _EQUIVALENTES.get(tipo, tipo)


def es_union(origen: Any) -> bool:
    return origen is typing.Union or origen is types.UnionType


def es_mapa(origen: Any) -> bool:
    return isinstance(origen, type) and issubclass(origen, Mapping)


def elemento_de_tupla(tipo: Any) -> Any:
    """Tipo de los elementos de ``tuple[X, ...]``; solo se admiten tuplas de largo libre."""
    args = typing.get_args(tipo)
    if len(args) != 2 or args[1] is not Ellipsis:
        raise TypeError("solo se admiten tuplas tuple[X, ...] en la serialización canónica")
    return args[0]


@cache
def campos_dataclass(clase: type) -> tuple[tuple[str, Any], ...]:
    pistas = typing.get_type_hints(clase, include_extras=True)
    return tuple((campo.name, pistas[campo.name]) for campo in dataclasses.fields(clase))


@cache
def campos_modelo(clase: type[BaseModel]) -> tuple[tuple[str, str, Any], ...]:
    """(nombre en Python, nombre en el archivo, anotación) de cada campo del modelo."""
    return tuple(
        (nombre, info.alias or nombre, info.annotation)
        for nombre, info in clase.model_fields.items()
    )


def ruta_de(base: str, parte: str | int) -> str:
    if isinstance(parte, int):
        return f"{base}[{parte}]"
    return f"{base}.{parte}" if base else parte


# --- Verificación de tipos (al construir) --------------------------------------------------


def verificar_tipo(valor: Any, tipo: Any, ruta: str) -> None:
    """Comprueba sin convertir que ``valor`` es del ``tipo`` declarado (DEC-238).

    Las dataclasses y los modelos anidados solo se comprueban por su clase: cada uno se
    verifica al construirse. Levanta ``TypeError`` con la ruta y el tipo, sin el valor.
    """
    tipo = sin_annotated(tipo)
    origen = typing.get_origin(tipo)
    if tipo is Any:
        verificar_any(valor, ruta)
        return
    if tipo is None or tipo is types.NoneType:
        if valor is not None:
            raise TypeError(f"{ruta}: se esperaba None")
        return
    if es_union(origen):
        for miembro in typing.get_args(tipo):
            try:
                verificar_tipo(valor, miembro, ruta)
            except TypeError:
                continue
            return
        raise TypeError(f"{ruta}: el valor no es de ninguno de los tipos de la unión")
    if origen is Literal:
        if not any(type(valor) is type(a) and valor == a for a in typing.get_args(tipo)):
            raise TypeError(f"{ruta}: valor fuera de los permitidos")
        return
    if origen is tuple:
        if not isinstance(valor, tuple):
            raise TypeError(f"{ruta}: se esperaba una tupla")
        elemento_tipo = elemento_de_tupla(tipo)
        for i, elemento in enumerate(valor):
            verificar_tipo(elemento, elemento_tipo, ruta_de(ruta, i))
        return
    if es_mapa(origen):
        if not isinstance(valor, Mapping):
            raise TypeError(f"{ruta}: se esperaba un mapa")
        clave_tipo, valor_tipo = typing.get_args(tipo) or (Any, Any)
        for clave, elemento in valor.items():
            verificar_tipo(clave, clave_tipo, ruta_de(ruta, "<clave>"))
            verificar_tipo(elemento, valor_tipo, ruta_de(ruta, str(clave)))
        return
    if not isinstance(tipo, type):
        raise TypeError(f"{ruta}: tipo no admitido en la serialización canónica")
    verificar_escalar(valor, tipo, ruta)


def verificar_escalar(valor: Any, tipo: type, ruta: str) -> None:
    if tipo is bool:
        ok = type(valor) is bool
    elif tipo is int:
        ok = type(valor) is int
    elif tipo is str:
        ok = type(valor) is str
    elif tipo is Decimal:
        ok = isinstance(valor, Decimal) and valor.is_finite()
    elif tipo is dt.datetime:
        ok = isinstance(valor, dt.datetime) and valor.utcoffset() is not None
    elif tipo is dt.date:
        ok = type(valor) is dt.date
    elif issubclass(tipo, Enum):
        ok = isinstance(valor, tipo)
    else:
        ok = isinstance(valor, tipo)
    if not ok:
        raise TypeError(f"{ruta}: se esperaba {tipo.__name__}")


def verificar_dataclass(objeto: Any) -> None:
    """Verifica sin convertir cada campo de una dataclass contra su anotación (DEC-238). Para
    los tipos del motor que no se serializan (``__post_init__`` de CMP-13 a CMP-15)."""
    for nombre, tipo in campos_dataclass(type(objeto)):
        verificar_tipo(getattr(objeto, nombre), tipo, nombre)


def exigir_decimal(valor: Any, nombre: str) -> Decimal:
    """``valor`` si es un ``Decimal`` finito; si no (un ``float``, un entero, un texto),
    ``TypeError`` con el nombre del dato, sin el valor (DEC-181)."""
    if not isinstance(valor, Decimal) or not valor.is_finite():
        raise TypeError(f"{nombre} debe ser un Decimal finito")
    return valor


def exigir_entero(valor: Any, nombre: str, *, minimo: int = 0) -> int:
    """``valor`` si es un ``int`` (no ``bool``) ≥ ``minimo``; si no, ``TypeError``."""
    if type(valor) is not int or valor < minimo:
        raise TypeError(f"{nombre} debe ser un entero ≥ {minimo}")
    return valor


def verificar_any(valor: Any, ruta: str) -> None:
    if valor is None or type(valor) in (bool, int, str):
        return
    if isinstance(valor, Decimal):
        if not valor.is_finite():
            raise TypeError(f"{ruta}: número no finito")
        return
    if isinstance(valor, list | tuple):
        for i, elemento in enumerate(valor):
            verificar_any(elemento, ruta_de(ruta, i))
        return
    if isinstance(valor, Mapping):
        if len(valor) == 1 and DECIMAL_ANY in valor:
            raise TypeError(f"{ruta}: clave reservada {DECIMAL_ANY}")
        for clave, elemento in valor.items():
            if type(clave) is not str:
                raise TypeError(f"{ruta}: las claves deben ser texto")
            verificar_any(elemento, ruta_de(ruta, clave))
        return
    raise TypeError(f"{ruta}: tipo no admitido ({type(valor).__name__})")
