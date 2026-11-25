"""Lectura de los archivos de carga (CMP-08; design.md CTR-02 y CTR-03).

Convierte los bytes de un archivo en renglones (número de renglón y campos), sin validar
nada del contenido: eso lo hacen los esquemas (CMP-05, CMP-06) y la validación (CMP-07).

- **JSON Lines** (CTR-02): UTF-8, un objeto por renglón, leído con ``parse_float=Decimal``
  para que ningún número pase por ``float``; ``NaN`` e ``Infinity`` no son JSON válido aquí.
  Un renglón vacío no es un registro. Un renglón que no es un objeto JSON queda como
  ``None`` (el cargador lo rechaza).
- **CSV** (CTR-03): UTF-8, separador coma, encabezado obligatorio, un archivo por tipo; el
  tipo sale del nombre (``<recordType>.csv`` o ``<recordType>__<sufijo>.csv``). Los
  encabezados con punto son campos anidados (``price.current``); una celda vacía es un
  campo ausente; las listas van separadas por ``|``. Enteros y booleanos se convierten
  desde el texto al tipo del campo en el esquema (DEC-238): solo ``"true"``/``"false"`` y
  un entero decimal exacto; un texto que no se convierte llega como está y el esquema lo
  rechaza. Los montos quedan como texto: el esquema los lee como ``Decimal``. Una columna
  ``recordType`` es opcional; si viene, su celda llega tal cual (vacía o faltante como
  ``""``) para que el cargador la compare con el tipo del nombre (DEC-279).

Un problema del **archivo** (formato desconocido, CSV que no es UTF-8, encabezado
repetido) levanta ``ErrorDeArchivo`` antes de empezar la carga; un problema de un
**renglón** nunca levanta. Los mensajes no llevan contenido del archivo (R-20, DEC-181).
Sin reloj, sin red.
"""

from __future__ import annotations

import csv
import dataclasses
import io
import json
import re
import types
import typing
from collections.abc import Iterator, Mapping
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel

from oip.catalogos import TipoRegistro
from oip.entradas.capturas import ESQUEMAS_CAPTURA
from oip.entradas.contrato import Observacion

__all__ = [
    "CAMPO_TIPO",
    "ErrorDeArchivo",
    "Formato",
    "Renglon",
    "formato_de_nombre",
    "leer_csv",
    "leer_json_lines",
    "tipo_de_nombre_csv",
]

#: Campo del tipo de registro en cada renglón JSON Lines (DEC-227 a).
CAMPO_TIPO = "recordType"

Formato = Literal["jsonl", "csv"]

_EXTENSIONES: Mapping[str, Formato] = {".jsonl": "jsonl", ".csv": "csv"}
_SEPARADOR_LISTA = "|"
_SEPARADOR_SUFIJO = "__"
#: Entero decimal exacto, sin signo ``+`` ni ceros iniciales (DEC-238: solo lo que el texto
#: dice); ``03``, ``3.0``, ``1e3`` o ``٣`` llegan como texto y el esquema los rechaza.
_ENTERO = re.compile(r"-?(?:0|[1-9][0-9]*)")
_BOOLEANOS = {"true": True, "false": False}


class ErrorDeArchivo(ValueError):
    """El archivo no se puede leer como carga. Sin contenido del archivo en el mensaje."""


@dataclasses.dataclass(frozen=True, slots=True)
class Renglon:
    """Un registro del archivo: su número de renglón (desde 1) y sus campos, o ``None`` si
    el renglón no es un objeto JSON (CTR-02)."""

    numero: int
    datos: dict[str, Any] | None = dataclasses.field(repr=False)


def formato_de_nombre(nombre: str) -> Formato:
    """``jsonl`` o ``csv`` por la extensión del archivo (sin distinguir mayúsculas)."""
    for extension, formato in _EXTENSIONES.items():
        if nombre.lower().endswith(extension):
            return formato
    raise ErrorDeArchivo("formato de archivo desconocido: se espera .jsonl o .csv (CTR-02, CTR-03)")


def tipo_de_nombre_csv(nombre: str) -> TipoRegistro | None:
    """El ``recordType`` de un CSV por su nombre: ``<recordType>.csv`` o
    ``<recordType>__<sufijo>.csv`` (CTR-03). ``None`` si el nombre no trae un tipo conocido:
    entonces cada renglón se rechaza con ``TIPO DE REGISTRO DESCONOCIDO``."""
    base = nombre[: -len(".csv")] if nombre.lower().endswith(".csv") else nombre
    tipo = base.split(_SEPARADOR_SUFIJO, 1)[0]
    try:
        return TipoRegistro(tipo)
    except ValueError:
        return None


# --- JSON Lines (CTR-02) ------------------------------------------------------------------


def _sin_constantes(_: str) -> Any:
    raise ValueError("NaN e Infinity no son números de un monto")


def _objeto_json(linea: bytes) -> dict[str, Any] | None:
    try:
        texto = linea.decode("utf-8")
        datos = json.loads(texto, parse_float=Decimal, parse_constant=_sin_constantes)
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None
    return datos if isinstance(datos, dict) else None


def leer_json_lines(contenido: bytes) -> Iterator[Renglon]:
    """Los renglones de un archivo JSON Lines, en orden; los vacíos no son registros."""
    if contenido.startswith(b"\xef\xbb\xbf"):
        contenido = contenido[3:]
    for numero, linea in enumerate(contenido.split(b"\n"), start=1):
        linea = linea.removesuffix(b"\r")
        if not linea.strip():
            continue
        yield Renglon(numero, _objeto_json(linea))


# --- CSV (CTR-03) -------------------------------------------------------------------------

_Clase = Literal["int", "bool", "lista"]


def _clase(anotacion: object) -> _Clase | type[BaseModel] | None:
    """Qué conversión pide un campo: entero, booleano, lista o un modelo anidado."""
    origen = typing.get_origin(anotacion)
    if origen is Annotated:
        return _clase(typing.get_args(anotacion)[0])
    if origen is typing.Union or origen is types.UnionType:
        for arg in typing.get_args(anotacion):
            if arg is not type(None):
                clase = _clase(arg)
                if clase is not None:
                    return clase
        return None
    if origen in (tuple, list):
        return "lista"
    if anotacion is bool:
        return "bool"
    if anotacion is int:
        return "int"
    if isinstance(anotacion, type) and issubclass(anotacion, BaseModel):
        return anotacion
    return None


def _conversiones(modelo: type[BaseModel], prefijo: str = "") -> dict[str, _Clase]:
    """Campo (con punto en los anidados, como en el archivo) → conversión del texto."""
    salida: dict[str, _Clase] = {}
    for nombre, info in modelo.model_fields.items():
        campo = prefijo + (info.alias or nombre)
        clase = _clase(info.annotation)
        if isinstance(clase, type):
            salida.update(_conversiones(clase, campo + "."))
        elif clase is not None:
            salida[campo] = clase
    return salida


_CONVERSIONES: Mapping[TipoRegistro, Mapping[str, _Clase]] = {
    TipoRegistro.OBSERVATION: _conversiones(Observacion),
    **{tipo: _conversiones(esquema) for tipo, esquema in ESQUEMAS_CAPTURA.items()},
}


def _convertir(texto: str, clase: _Clase | None) -> object:
    """El texto de una celda en el tipo del campo; si no se convierte, el texto tal cual."""
    if clase == "lista":
        return [parte.strip() for parte in texto.split(_SEPARADOR_LISTA)]
    limpio = texto.strip()
    if clase == "bool":
        return _BOOLEANOS.get(limpio, texto)
    if clase == "int" and _ENTERO.fullmatch(limpio):
        return int(limpio)
    return texto


def _encabezado(columnas: list[str]) -> list[str]:
    nombres = [c.strip() for c in columnas]
    vistos: set[str] = set()
    for nombre in nombres:
        if nombre and nombre in vistos:
            raise ErrorDeArchivo("CSV: encabezado con una columna repetida")
        vistos.add(nombre)
    for nombre in vistos - {""}:
        if any(otro.startswith(nombre + ".") for otro in vistos):
            raise ErrorDeArchivo("CSV: una columna es a la vez campo y grupo de campos anidados")
    return nombres


def _anidar(campos: Mapping[str, object]) -> dict[str, Any]:
    datos: dict[str, Any] = {}
    for ruta, valor in campos.items():
        *grupos, hoja = ruta.split(".")
        actual = datos
        for grupo in grupos:
            actual = actual.setdefault(grupo, {})
        actual[hoja] = valor
    return datos


def leer_csv(contenido: bytes, tipo: TipoRegistro | None) -> Iterator[Renglon]:
    """Los renglones de un CSV con encabezado, en orden. Celda vacía = campo ausente; un
    renglón sin celdas no es un registro; las celdas de más (sin encabezado) se descartan.
    El tipo sale del nombre (CTR-03). La columna ``recordType``, si viene, queda en los
    campos con el texto de su celda, también vacía o faltante (``""``): el cargador la
    compara con el tipo del nombre y la quita (DEC-279).

    Levanta ``ErrorDeArchivo`` si el archivo no es UTF-8 o el encabezado no es válido."""
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ErrorDeArchivo("CSV: el archivo no es UTF-8 (CTR-03)") from None
    lector = csv.reader(io.StringIO(texto, newline=""))
    try:
        encabezado = _encabezado(next(lector))
    except StopIteration:
        return
    except csv.Error:
        raise ErrorDeArchivo("CSV: el encabezado no se puede leer") from None
    conversiones = _CONVERSIONES.get(tipo, {}) if tipo is not None else {}
    columna_tipo = encabezado.index(CAMPO_TIPO) if CAMPO_TIPO in encabezado else None
    while True:
        inicio = lector.line_num + 1
        try:
            celdas = next(lector)
        except StopIteration:
            return
        except csv.Error:
            raise ErrorDeArchivo("CSV: un renglón no se puede leer") from None
        if not celdas:
            continue
        campos = {
            nombre: _convertir(celda, conversiones.get(nombre))
            for nombre, celda in zip(encabezado, celdas, strict=False)
            if nombre and nombre != CAMPO_TIPO and celda.strip()
        }
        if columna_tipo is not None:
            # DEC-279: vacía o faltante también se compara (da TIPO DE REGISTRO DESCONOCIDO).
            campos[CAMPO_TIPO] = celdas[columna_tipo] if columna_tipo < len(celdas) else ""
        yield Renglon(inicio, _anidar(campos))
