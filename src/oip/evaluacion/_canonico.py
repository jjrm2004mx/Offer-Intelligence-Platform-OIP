"""JSON canónico de los tipos del dominio (CTR-06; design.md §6, RNF-3).

Codificador y decodificador guiados por el **tipo declarado** de cada campo (dataclasses
congeladas y modelos de pydantic), para que una ida y vuelta dé un objeto igual y el texto
salga igual byte a byte:

- Claves ordenadas, separadores fijos (``,`` y ``:``), UTF-8 sin escapar (``ensure_ascii``
  falso). Un campo ``None`` va como ``null``: todos los campos salen siempre.
- Montos y porcentajes (``Decimal``) como **texto decimal** en notación fija, sin redondear
  (``Decimal("29.00")`` → ``"29.00"``). Nunca un número JSON con punto: al leer, un número
  con punto o exponente se rechaza (``parse_float``), igual que ``NaN`` e ``Infinity``.
- Fechas y horas en ISO 8601 **en UTC** con ``Z``; fechas solas en ``AAAA-MM-DD``.
- Enums por su código; ``UUID`` en texto; tuplas como listas; mapas con claves de texto.
- Tipos estrictos (DEC-238): al leer no hay conversiones implícitas; un booleano no es un
  entero, un texto no es un número y ``3.0`` no es un entero. Al escribir, un ``float`` en
  cualquier lugar levanta ``TypeError`` (design.md §8).
- Un campo ``Any`` (``evidence`` de la observación) se escribe sin perder el tipo: sus
  ``Decimal`` van como ``{"$decimal": "<texto>"}``, la misma forma de la huella de la
  configuración (``oip.configuracion``).

Puro: sin reloj, sin I/O, sin estado global mutable. Los mensajes de error citan la ruta del
campo y el tipo, nunca el valor (DEC-181).
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import types
import typing
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

from oip.evaluacion._tipos import (
    DECIMAL_ANY,
    campos_dataclass,
    campos_modelo,
    elemento_de_tupla,
    es_mapa,
    es_union,
    ruta_de,
    sin_annotated,
    verificar_any,
    verificar_escalar,
    verificar_tipo,
)

__all__ = ["ErrorSerializacion", "a_json", "desde_json"]


class ErrorSerializacion(ValueError):
    """El JSON no corresponde al tipo esperado. El mensaje lleva la ruta, no el valor."""


def _falla(ruta: str, esperado: str) -> ErrorSerializacion:
    return ErrorSerializacion(f"{ruta or '(raíz)'}: se esperaba {esperado}")


# --- Escritura ----------------------------------------------------------------------------


def _texto_decimal(valor: Decimal) -> str:
    # Notación fija, sin exponente y sin redondear: conserva los ceros a la derecha.
    return format(valor, "f")


def _texto_fecha_hora(valor: dt.datetime) -> str:
    texto = valor.astimezone(dt.UTC).isoformat()
    return texto.removesuffix("+00:00") + "Z"


def _codificar(valor: Any, tipo: Any, ruta: str) -> Any:
    tipo = sin_annotated(tipo)
    if isinstance(valor, float):
        raise TypeError(f"{ruta}: float no admitido; use Decimal")
    if tipo is Any:
        verificar_any(valor, ruta)
        return _codificar_any(valor)
    origen = typing.get_origin(tipo)
    if valor is None:
        verificar_tipo(valor, tipo, ruta)
        return None
    if es_union(origen):
        for miembro in typing.get_args(tipo):
            try:
                verificar_tipo(valor, miembro, ruta)
            except TypeError:
                continue
            return _codificar(valor, miembro, ruta)
        raise TypeError(f"{ruta}: el valor no es de ninguno de los tipos de la unión")
    if origen is Literal:
        verificar_tipo(valor, tipo, ruta)
        return valor.value if isinstance(valor, Enum) else valor
    if origen is tuple:
        if not isinstance(valor, tuple):
            raise TypeError(f"{ruta}: se esperaba una tupla")
        elemento_tipo = elemento_de_tupla(tipo)
        return [_codificar(e, elemento_tipo, ruta_de(ruta, i)) for i, e in enumerate(valor)]
    if es_mapa(origen):
        if not isinstance(valor, Mapping):
            raise TypeError(f"{ruta}: se esperaba un mapa")
        clave_tipo, valor_tipo = typing.get_args(tipo)
        salida: dict[str, Any] = {}
        for clave, elemento in valor.items():
            verificar_tipo(clave, clave_tipo, ruta_de(ruta, "<clave>"))
            texto = clave.value if isinstance(clave, Enum) else clave
            if type(texto) is not str:
                raise TypeError(f"{ruta}: las claves deben ser texto o enums de texto")
            salida[texto] = _codificar(elemento, valor_tipo, ruta_de(ruta, texto))
        return salida
    if isinstance(tipo, type) and dataclasses.is_dataclass(tipo):
        if not isinstance(valor, tipo):
            raise TypeError(f"{ruta}: se esperaba {tipo.__name__}")
        return {
            nombre: _codificar(getattr(valor, nombre), anotacion, ruta_de(ruta, nombre))
            for nombre, anotacion in campos_dataclass(type(valor))
        }
    if isinstance(tipo, type) and issubclass(tipo, BaseModel):
        if not isinstance(valor, tipo):
            raise TypeError(f"{ruta}: se esperaba {tipo.__name__}")
        return {
            alias: _codificar(getattr(valor, nombre), anotacion, ruta_de(ruta, alias))
            for nombre, alias, anotacion in campos_modelo(type(valor))
        }
    if not isinstance(tipo, type):
        raise TypeError(f"{ruta}: tipo no admitido en la serialización canónica")
    verificar_escalar(valor, tipo, ruta)
    if isinstance(valor, Enum):
        return valor.value
    if isinstance(valor, Decimal):
        return _texto_decimal(valor)
    if isinstance(valor, dt.datetime):
        return _texto_fecha_hora(valor)
    if isinstance(valor, dt.date):
        return valor.isoformat()
    if isinstance(valor, UUID):
        return str(valor)
    if type(valor) in (bool, int, str):
        return valor
    raise TypeError(f"{ruta}: tipo no admitido ({tipo.__name__})")


def _codificar_any(valor: Any) -> Any:
    if isinstance(valor, Decimal):
        return {DECIMAL_ANY: _texto_decimal(valor)}
    if isinstance(valor, list | tuple):
        return [_codificar_any(e) for e in valor]
    if isinstance(valor, Mapping):
        return {clave: _codificar_any(e) for clave, e in valor.items()}
    return valor


def a_json(valor: Any, tipo: Any) -> str:
    """Texto JSON canónico de ``valor`` según su ``tipo`` declarado (CTR-06)."""
    estructura = _codificar(valor, tipo, "")
    return json.dumps(estructura, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


# --- Lectura ------------------------------------------------------------------------------


def _rechazar_numero(texto: str) -> Any:
    raise ErrorSerializacion("número JSON con punto, exponente o no finito: use texto decimal")


def _decodificar(dato: Any, tipo: Any, ruta: str) -> Any:
    tipo = sin_annotated(tipo)
    if tipo is Any:
        return _decodificar_any(dato, ruta)
    origen = typing.get_origin(tipo)
    if tipo is None or tipo is types.NoneType:
        if dato is not None:
            raise _falla(ruta, "null")
        return None
    if es_union(origen):
        miembros = typing.get_args(tipo)
        if dato is None:
            if types.NoneType in miembros:
                return None
            raise _falla(ruta, "un valor")
        for miembro in miembros:
            if miembro is types.NoneType:
                continue
            try:
                return _decodificar(dato, miembro, ruta)
            except (ErrorSerializacion, ValueError, TypeError):
                continue
        raise _falla(ruta, "un valor de uno de los tipos de la unión")
    if dato is None:
        raise _falla(ruta, "un valor")
    if origen is Literal:
        for permitido in typing.get_args(tipo):
            codigo = permitido.value if isinstance(permitido, Enum) else permitido
            if type(dato) is type(codigo) and dato == codigo:
                return permitido
        raise _falla(ruta, "un valor permitido")
    if origen is tuple:
        if not isinstance(dato, list):
            raise _falla(ruta, "una lista")
        elemento_tipo = elemento_de_tupla(tipo)
        return tuple(_decodificar(e, elemento_tipo, ruta_de(ruta, i)) for i, e in enumerate(dato))
    if es_mapa(origen):
        if not isinstance(dato, dict):
            raise _falla(ruta, "un objeto")
        clave_tipo, valor_tipo = typing.get_args(tipo)
        return {
            _decodificar(clave, clave_tipo, ruta_de(ruta, "<clave>")): _decodificar(
                elemento, valor_tipo, ruta_de(ruta, clave)
            )
            for clave, elemento in dato.items()
        }
    if isinstance(tipo, type) and dataclasses.is_dataclass(tipo):
        campos = campos_dataclass(tipo)
        _exigir_claves(dato, [n for n, _ in campos], ruta)
        valores = {n: _decodificar(dato[n], a, ruta_de(ruta, n)) for n, a in campos}
        try:
            return tipo(**valores)
        except (TypeError, ValueError) as error:
            raise ErrorSerializacion(f"{ruta or '(raíz)'}: {error}") from None
    if isinstance(tipo, type) and issubclass(tipo, BaseModel):
        campos_m = campos_modelo(tipo)
        _exigir_claves(dato, [alias for _, alias, _ in campos_m], ruta)
        valores = {
            alias: _decodificar(dato[alias], a, ruta_de(ruta, alias)) for _, alias, a in campos_m
        }
        try:
            return tipo.model_validate(valores)
        except ValueError:
            # Sin el detalle de pydantic: podría citar el valor.
            raise _falla(ruta, f"un {tipo.__name__} válido") from None
    if not isinstance(tipo, type):
        raise _falla(ruta, "un tipo admitido")
    return _decodificar_escalar(dato, tipo, ruta)


def _exigir_claves(dato: Any, claves: list[str], ruta: str) -> None:
    if not isinstance(dato, dict):
        raise _falla(ruta, "un objeto")
    if set(dato) != set(claves):
        faltan = sorted(set(claves) - set(dato))
        sobran = sorted(set(dato) - set(claves))
        raise ErrorSerializacion(
            f"{ruta or '(raíz)'}: claves distintas del tipo (faltan {faltan}, sobran {sobran})"
        )


def _decodificar_escalar(dato: Any, tipo: type, ruta: str) -> Any:
    if tipo is bool:
        if type(dato) is not bool:
            raise _falla(ruta, "un booleano")
        return dato
    if tipo is int:
        if type(dato) is not int:
            raise _falla(ruta, "un entero")
        return dato
    if tipo is str:
        if type(dato) is not str:
            raise _falla(ruta, "un texto")
        return dato
    if type(dato) is not str:
        raise _falla(ruta, f"texto con {tipo.__name__}")
    if tipo is Decimal:
        return _leer_decimal(dato, ruta)
    if tipo is dt.datetime:
        if not dato.endswith("Z"):
            raise _falla(ruta, "fecha y hora ISO 8601 en UTC (Z)")
        try:
            return dt.datetime.fromisoformat(dato)
        except ValueError:
            raise _falla(ruta, "fecha y hora ISO 8601") from None
    if tipo is dt.date:
        try:
            if len(dato) != 10:
                raise ValueError
            return dt.date.fromisoformat(dato)
        except ValueError:
            raise _falla(ruta, "fecha AAAA-MM-DD") from None
    if tipo is UUID:
        try:
            valor = UUID(dato)
        except ValueError:
            raise _falla(ruta, "un UUID") from None
        if str(valor) != dato:
            raise _falla(ruta, "un UUID en forma canónica")
        return valor
    if issubclass(tipo, Enum):
        try:
            return tipo(dato)
        except ValueError:
            raise _falla(ruta, f"un código de {tipo.__name__}") from None
    raise _falla(ruta, "un tipo admitido")


def _leer_decimal(dato: str, ruta: str) -> Decimal:
    if dato != dato.strip() or not dato:
        raise _falla(ruta, "texto decimal")
    try:
        valor = Decimal(dato)
    except InvalidOperation:
        raise _falla(ruta, "texto decimal") from None
    if not valor.is_finite() or _texto_decimal(valor) != dato:
        raise _falla(ruta, "texto decimal en notación fija")
    return valor


def _decodificar_any(dato: Any, ruta: str) -> Any:
    if isinstance(dato, dict):
        if len(dato) == 1 and DECIMAL_ANY in dato:
            texto = dato[DECIMAL_ANY]
            if type(texto) is not str:
                raise _falla(ruta, "texto decimal")
            return _leer_decimal(texto, ruta)
        return {clave: _decodificar_any(e, ruta_de(ruta, clave)) for clave, e in dato.items()}
    if isinstance(dato, list):
        return [_decodificar_any(e, ruta_de(ruta, i)) for i, e in enumerate(dato)]
    return dato


def desde_json(texto: str | bytes, tipo: Any) -> Any:
    """Lee el JSON canónico de ``a_json`` como un valor del ``tipo`` (CTR-06).

    Estricto (DEC-238): rechaza claves que falten o sobren, números con punto, booleanos
    como enteros, textos como números y fechas sin UTC. Levanta ``ErrorSerializacion``.
    """
    if isinstance(texto, bytes):
        texto = texto.decode("utf-8")
    if not isinstance(texto, str):
        raise TypeError("el JSON debe ser texto o bytes UTF-8")
    try:
        datos = json.loads(
            texto,
            parse_float=_rechazar_numero,
            parse_constant=_rechazar_numero,
            object_pairs_hook=_sin_repetidas,
        )
    except json.JSONDecodeError:
        raise ErrorSerializacion("el texto no es JSON válido") from None
    return _decodificar(datos, tipo, "")


def _sin_repetidas(pares: list[tuple[str, Any]]) -> dict[str, Any]:
    salida: dict[str, Any] = {}
    for clave, valor in pares:
        if clave in salida:
            raise ErrorSerializacion("clave repetida en el JSON")
        salida[clave] = valor
    return salida
