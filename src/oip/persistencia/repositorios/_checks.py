"""Los ``CHECK`` de ``oip.persistencia.tablas`` evaluados en memoria (CMP-20).

``RepositorioMemoria`` debe rechazar lo mismo que PostgreSQL (design.md §5: la misma batería
pasa con las dos implementaciones). Para que las reglas no se copien a mano ni diverjan, este
módulo **lee el texto SQL de cada ``CheckConstraint`` de los metadatos** y lo evalúa sobre la
fila con la lógica de tres valores de SQL: un ``CHECK`` se cumple si da verdadero **o nulo**
y se viola solo si da falso, como en PostgreSQL.

Entiende el subconjunto de SQL que usan los ``CHECK`` del esquema: ``AND``, ``OR``, ``NOT``,
``=``, ``<>``, ``<``, ``<=``, ``>``, ``>=``, ``~`` (expresión regular), ``IN (...)``,
``BETWEEN``, ``IS [NOT] NULL``, ``IS [NOT] DISTINCT FROM``, ``<@ ARRAY[...]::text[]``,
subíndices (``reasons[1]``, desde 1) y las funciones ``btrim``, ``cardinality`` y
``jsonb_typeof``. Un ``CHECK`` con otra forma levanta ``NotImplementedError`` al importar el
módulo: así una regla nueva del esquema no queda sin aplicar en memoria sin que nadie lo note.
En particular (decisión 19 del #34), al importar:

- el único cast admitido es ``::text[]``; cualquier otro (``::integer``, ``::text``) cambia
  la semántica y no se ignora;
- cada identificador debe ser una columna de la tabla del ``CHECK``; ``TRUE`` y ``FALSE``
  no se admiten (no son columnas y no se tratan como literales);
- el patrón de ``~`` debe ser un literal y estar en el subconjunto común de ``re`` y de las
  ARE de PostgreSQL: se rechazan las clases POSIX y sus parientes (``[:``, ``[.``, ``[=``),
  las opciones incrustadas (``(?``), el director ``***`` y los escapes alfabéticos
  (``\\y``, ``\\m``, ``\\b``, ``\\d``…), que significan otra cosa en cada motor. Los
  patrones se validan y se traducen al importar, no en la primera fila.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, Table

from oip.persistencia import tablas

__all__ = ["CHECKS", "violado"]

Expr = Callable[[Mapping[str, Any]], Any]

_TOKEN = re.compile(
    r"\s*(?:(?P<texto>'(?:[^']|'')*')|(?P<numero>\d+(?:\.\d+)?)"
    r"|(?P<nombre>[A-Za-z_][A-Za-z0-9_]*)|(?P<op><@|<>|>=|<=|::|[=<>~()\[\],]))"
)
_PALABRAS = {"AND", "OR", "NOT", "IS", "NULL", "IN", "BETWEEN", "DISTINCT", "FROM", "ARRAY"}


def _tokens(texto: str) -> list[tuple[str, Any]]:
    salida: list[tuple[str, Any]] = []
    posicion = 0
    texto = texto.rstrip()
    while posicion < len(texto):
        m = _TOKEN.match(texto, posicion)
        if m is None or m.end() == posicion:
            raise NotImplementedError(f"CHECK no admitido en memoria: {texto[posicion:]!r}")
        posicion = m.end()
        if m["texto"] is not None:
            salida.append(("lit", m["texto"][1:-1].replace("''", "'")))
        elif m["numero"] is not None:
            salida.append(("lit", Decimal(m["numero"])))
        elif m["nombre"] is not None:
            nombre = m["nombre"]
            if nombre.upper() in _PALABRAS:
                salida.append(("kw", nombre.upper()))
            else:
                salida.append(("id", nombre))
        else:
            salida.append(("op", m["op"]))
    return salida


# --- Lógica de tres valores ---------------------------------------------------------------


def _y(a: Any, b: Any) -> Any:
    if a is False or b is False:
        return False
    return None if a is None or b is None else True


def _o(a: Any, b: Any) -> Any:
    if a is True or b is True:
        return True
    return None if a is None or b is None else False


#: Formas de una ARE que ``re`` no entiende igual (decisión 19 del #34).
_FORMAS_SIN_EQUIVALENTE = ("[:", "[.", "[=", "(?", "***")


def _patron_are(patron: str) -> str:
    """Una expresión regular de PostgreSQL (ARE, modo por defecto) como patrón de ``re``.

    Levanta ``NotImplementedError`` ante una forma fuera del subconjunto común de los dos
    motores: ``[:``, ``[.``, ``[=``, ``(?``, ``***`` o un escape alfabético (``\\y``).

    En una ARE ``$`` solo coincide al final del texto; en ``re`` también antes de un salto de
    línea final (``'a\\n'`` cumpliría ``'^a$'``). Por eso cada ``$`` sin escapar y fuera de
    ``[...]`` pasa a ``\\Z``. La otra diferencia del modo por defecto, que ``.`` coincide con
    un salto de línea, la cubre ``re.DOTALL`` en ``_comparar``."""
    for forma in _FORMAS_SIN_EQUIVALENTE:
        if forma in patron:
            raise NotImplementedError(f"expresión regular no admitida en memoria: {forma!r}")
    salida: list[str] = []
    i = 0
    en_clase = False
    while i < len(patron):
        c = patron[i]
        if c == "\\" and i + 1 < len(patron):
            if patron[i + 1].isalpha():
                raise NotImplementedError(f"escape no admitido en memoria: {patron[i : i + 2]!r}")
            salida.append(patron[i : i + 2])
            i += 2
            continue
        if en_clase:
            en_clase = c != "]"
        elif c == "[":
            # Un ']' justo tras '[' o '[^' es un carácter de la clase, no su cierre.
            en_clase = True
            salida.append(c)
            i += 1
            if i < len(patron) and patron[i] == "^":
                salida.append("^")
                i += 1
            if i < len(patron) and patron[i] == "]":
                salida.append("]")
                i += 1
            continue
        elif c == "$":
            salida.append(r"\Z")
            i += 1
            continue
        salida.append(c)
        i += 1
    return "".join(salida)


def _comparar(op: str, a: Any, b: Any) -> Any:
    if a is None or b is None:
        return None
    if op == "=":
        return a == b
    if op == "<>":
        return a != b
    if op == "<":
        return a < b
    if op == "<=":
        return a <= b
    if op == ">":
        return a > b
    if op == ">=":
        return a >= b
    if op == "~":
        return re.search(_patron_are(b), a, re.DOTALL) is not None
    raise NotImplementedError(op)  # pragma: no cover


def _jsonb_typeof(valor: Any) -> Any:
    if valor is None:
        return None
    dato = json.loads(valor, parse_float=Decimal)
    if isinstance(dato, dict):
        return "object"
    if isinstance(dato, list):
        return "array"
    if isinstance(dato, str):
        return "string"
    if isinstance(dato, bool):
        return "boolean"
    return "null" if dato is None else "number"


_FUNCIONES: Mapping[str, Callable[[Any], Any]] = {
    "btrim": lambda v: None if v is None else v.strip(" "),
    "cardinality": lambda v: None if v is None else len(v),
    "jsonb_typeof": _jsonb_typeof,
}


# --- Analizador ---------------------------------------------------------------------------


class _Analizador:
    def __init__(self, texto: str, columnas: frozenset[str] | None = None) -> None:
        """``columnas``: las de la tabla del ``CHECK``; con ``None`` no se comprueban los
        identificadores (solo para analizar un texto suelto; ``_compilar`` siempre las da)."""
        self.texto = texto
        self.columnas = columnas
        self.t = _tokens(texto)
        self.i = 0

    def _no_admitido(self, detalle: str) -> NotImplementedError:
        return NotImplementedError(f"CHECK no admitido en memoria ({detalle}): {self.texto!r}")

    def _ver(self) -> tuple[str, Any] | None:
        return self.t[self.i] if self.i < len(self.t) else None

    def _es(self, clase: str, valor: Any = None) -> bool:
        actual = self._ver()
        return actual is not None and actual[0] == clase and (valor is None or actual[1] == valor)

    def _tomar(self, clase: str, valor: Any = None) -> Any:
        if not self._es(clase, valor):
            raise NotImplementedError(f"CHECK no admitido en memoria: {self.texto!r}")
        actual = self.t[self.i]
        self.i += 1
        return actual[1]

    def todo(self) -> Expr:
        expr = self._o()
        if self._ver() is not None:
            raise NotImplementedError(f"CHECK no admitido en memoria: {self.texto!r}")
        return expr

    def _o(self) -> Expr:
        izq = self._y()
        while self._es("kw", "OR"):
            self.i += 1
            der = self._y()
            izq = (lambda a, b: lambda f: _o(a(f), b(f)))(izq, der)
        return izq

    def _y(self) -> Expr:
        izq = self._no()
        while self._es("kw", "AND"):
            self.i += 1
            der = self._no()
            izq = (lambda a, b: lambda f: _y(a(f), b(f)))(izq, der)
        return izq

    def _no(self) -> Expr:
        if self._es("kw", "NOT"):
            self.i += 1
            interior = self._no()
            return lambda f: None if (v := interior(f)) is None else not v
        return self._comparacion()

    def _comparacion(self) -> Expr:
        izq = self._valor()
        if self._es("op", "~"):
            self.i += 1
            if not (self._es("lit") and isinstance(self._ver()[1], str)):  # type: ignore[index]
                raise self._no_admitido("el patrón de ~ debe ser un texto literal")
            # Se valida y se traduce al importar (decisión 19 del #34), no en la primera fila.
            patron = _patron_are(self._tomar("lit"))
            return lambda f: (
                None if (v := izq(f)) is None else re.search(patron, v, re.DOTALL) is not None
            )
        if self._es("op") and self._ver()[1] in ("=", "<>", "<", "<=", ">", ">="):  # type: ignore[index]
            op = self._tomar("op")
            der = self._valor()
            return lambda f: _comparar(op, izq(f), der(f))
        if self._es("op", "<@"):
            self.i += 1
            der = self._valor()
            return lambda f: (
                None if (a := izq(f)) is None or (b := der(f)) is None else all(e in b for e in a)
            )
        if self._es("kw", "IN"):
            self.i += 1
            self._tomar("op", "(")
            opciones = [self._valor()]
            while self._es("op", ","):
                self.i += 1
                opciones.append(self._valor())
            self._tomar("op", ")")
            return lambda f: None if (v := izq(f)) is None else v in [o(f) for o in opciones]
        if self._es("kw", "BETWEEN"):
            self.i += 1
            bajo = self._valor()
            self._tomar("kw", "AND")
            alto = self._valor()
            return lambda f: _y(_comparar(">=", izq(f), bajo(f)), _comparar("<=", izq(f), alto(f)))
        if self._es("kw", "IS"):
            self.i += 1
            negado = self._es("kw", "NOT")
            if negado:
                self.i += 1
            if self._es("kw", "NULL"):
                self.i += 1
                return lambda f: (izq(f) is None) != negado
            self._tomar("kw", "DISTINCT")
            self._tomar("kw", "FROM")
            der = self._valor()
            # IS DISTINCT FROM: nunca nulo; dos nulos no son distintos.
            return lambda f: (izq(f) != der(f)) != negado
        return izq

    def _valor(self) -> Expr:
        expr = self._primario()
        while self._es("op", "[") or self._es("op", "::"):
            if self._es("op", "["):
                self.i += 1
                indice = self._tomar("lit")
                self._tomar("op", "]")
                n = int(indice)
                base = expr
                expr = (
                    lambda b, k: (
                        lambda f: None if (v := b(f)) is None or not 1 <= k <= len(v) else v[k - 1]
                    )
                )(base, n)
            else:  # ::text[]: los valores de memoria ya son listas de texto
                self.i += 1
                tipo = self._tomar("id")
                if str(tipo).lower() != "text" or not self._es("op", "["):
                    raise self._no_admitido("solo se admite el cast ::text[]")
                self.i += 1
                self._tomar("op", "]")
        return expr

    def _primario(self) -> Expr:
        if self._es("lit"):
            valor = self._tomar("lit")
            return lambda f: valor
        if self._es("op", "("):
            self.i += 1
            interior = self._o()
            self._tomar("op", ")")
            return interior
        if self._es("kw", "ARRAY"):
            self.i += 1
            self._tomar("op", "[")
            elementos = [self._valor()]
            while self._es("op", ","):
                self.i += 1
                elementos.append(self._valor())
            self._tomar("op", "]")
            return lambda f: [e(f) for e in elementos]
        if self._es("kw", "NULL"):
            self.i += 1
            return lambda f: None
        nombre = self._tomar("id")
        if self._es("op", "("):
            if nombre not in _FUNCIONES:
                raise NotImplementedError(f"función no admitida en memoria: {nombre}")
            self.i += 1
            argumento = self._o()
            self._tomar("op", ")")
            funcion = _FUNCIONES[nombre]
            return lambda f: funcion(argumento(f))
        if nombre.upper() in ("TRUE", "FALSE"):
            raise self._no_admitido("TRUE y FALSE no se admiten")
        if self.columnas is not None and nombre not in self.columnas:
            raise self._no_admitido(f"{nombre} no es una columna de la tabla")
        return lambda f: f[nombre]


def _compilar(tabla: Table) -> tuple[tuple[str, Expr], ...]:
    columnas = frozenset(tabla.c.keys())
    return tuple(
        (str(r.name), _Analizador(str(r.sqltext), columnas).todo())
        for r in sorted(tabla.constraints, key=lambda r: str(r.name))
        if isinstance(r, CheckConstraint)
    )


#: Los ``CHECK`` de cada tabla de ``tablas.metadata``, compilados, con su nombre.
CHECKS: Mapping[str, tuple[tuple[str, Expr], ...]] = {
    nombre: _compilar(tabla) for nombre, tabla in tablas.metadata.tables.items()
}


def violado(tabla: str, fila: Mapping[str, Any]) -> str | None:
    """El nombre del primer ``CHECK`` que ``fila`` viola (da falso), o ``None``."""
    for nombre, expr in CHECKS[tabla]:
        if expr(fila) is False:
            return nombre
    return None
