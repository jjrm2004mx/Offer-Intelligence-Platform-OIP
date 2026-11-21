"""Piezas comunes del contrato 3.1 (CMP-05) y de las capturas (CMP-06).

- ``RegistroInvalido``: el registro no cumple su esquema. Lleva solo el **motivo** y el
  **nombre del campo** tal como va en el archivo; nunca el valor ni el contenido del
  registro (R-20, DEC-181: el alias de un cliente no llega a un log ni a un mensaje).
- ``validar_esquema``: valida un registro con un modelo pydantic y, si falla, devuelve el
  **primer** problema en el orden de los obligatorios de su tipo (design.md §6). Un campo
  ausente, vacío o con un valor que no es válido para su tipo o su tabla cerrada da
  ``CAMPO OBLIGATORIO FALTANTE (<campo>)`` (design.md §6; DEC-234 punto 2).
- Los campos desconocidos se descartan sin guardarlos (design.md §6, RNF-7, RNF-11).
- Los montos se leen como ``Decimal`` sin pasar por ``float`` (DEC-060, design.md §8).
  ``Monto`` además rechaza más de 2 decimales al leer (DEC-257): el rechazo del repositorio
  (``numeric(12,2)``, T06) queda como última barrera.
- ``CONTEXTO_DIA_DE_CARGA``: el día de la carga, que llega como dato (nunca el reloj), para
  rechazar una fecha de captura posterior (DEC-257).
- Enteros y booleanos **estrictos** (``Entero``, ``Booleano``; DEC-238): ``true`` no se lee
  como 1, ni ``"false"`` o ``0`` como ``False``. Convertir el texto de un CSV es del cargador
  (T08).
- ``FechaHoraCaptura``: fecha y hora de una captura de Jesús; sin desfase se toma en la zona
  que pasa el llamador (``general.timezone`` de PAR-01; DEC-240). En las observaciones se
  sigue exigiendo el desfase (``AwareDatetime``).
"""

from __future__ import annotations

import datetime as dt
import types
import typing
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    StrictBool,
    StrictInt,
    ValidationError,
    ValidationInfo,
)
from pydantic.alias_generators import to_camel

from oip.catalogos import MotivoRechazo, motivo_campo_faltante
from oip.dinero import leer_monto

__all__ = [
    "CONTEXTO_DIA_DE_CARGA",
    "CONTEXTO_ZONA",
    "Booleano",
    "Dec",
    "Entero",
    "Esquema",
    "FechaHoraCaptura",
    "Monto",
    "RegistroInvalido",
    "a_decimal",
    "ausente",
    "decimal_o_none",
    "faltantes_de_producto",
    "mas_de_2_decimales",
    "obtener",
    "validar_esquema",
]


class RegistroInvalido(ValueError):
    """Un registro no cumple su esquema.

    ``motivo`` es el código completo (``CAMPO OBLIGATORIO FALTANTE (exchangeRate)``) y
    ``campo`` el nombre del campo en el archivo (o ``None``). El mensaje es solo el motivo:
    sin valores ni contenido del registro.
    """

    def __init__(self, motivo: str, campo: str | None = None) -> None:
        self.motivo = motivo
        self.campo = campo
        super().__init__(motivo)

    @classmethod
    def campo_faltante(cls, campo: str) -> RegistroInvalido:
        return cls(motivo_campo_faltante(campo), campo)

    @classmethod
    def tipo_desconocido(cls) -> RegistroInvalido:
        return cls(MotivoRechazo.TIPO_DE_REGISTRO_DESCONOCIDO.value)


class Esquema(BaseModel):
    """Base de los esquemas de entrada: campos en camelCase en el archivo (``alias``),
    inmutables, campos desconocidos descartados y sin el valor de entrada en los errores."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=False,
        extra="ignore",
        frozen=True,
        str_strip_whitespace=True,
        hide_input_in_errors=True,
    )


# --- Valores --------------------------------------------------------------------------


def a_decimal(valor: object) -> Decimal:
    """Decimal desde texto, ``Decimal`` o entero; nunca desde ``float`` (design.md §8)."""
    if isinstance(valor, bool) or isinstance(valor, float):
        raise ValueError("se esperaba un número decimal en texto")
    if isinstance(valor, int):
        return Decimal(valor)
    if isinstance(valor, str | Decimal):
        try:
            return leer_monto(valor)
        except (TypeError, ValueError):
            raise ValueError("se esperaba un número decimal") from None
    raise ValueError("se esperaba un número decimal")


def decimal_o_none(valor: object) -> Decimal | None:
    """Como ``a_decimal``, pero un valor que no es un número da ``None`` en lugar de un error.

    Se usa en los precios que se marcan para ``PRECIO INVÁLIDO`` en lugar de rechazarse
    por campo faltante (tasks.md T03)."""
    if valor is None:
        return None
    try:
        return a_decimal(valor)
    except ValueError:
        return None


Dec = Annotated[Decimal, BeforeValidator(a_decimal)]
"""``Decimal`` leído sin ``float``."""


def mas_de_2_decimales(valor: Decimal) -> bool:
    """``True`` si ``valor`` no es un número entero de centavos (``29.001``); ``29.000`` y
    ``29.5`` no lo son (se compara el valor, no los ceros finales). DEC-257.

    No redondea (solo ``dinero.py`` redondea): compara el valor por 100 con su parte
    entera."""
    if not isinstance(valor, Decimal) or not valor.is_finite():
        raise TypeError("se esperaba un Decimal finito")
    centavos = valor * 100
    return centavos != centavos.to_integral_value()


def _a_lo_mas_2_decimales(valor: Decimal) -> Decimal:
    if mas_de_2_decimales(valor):
        raise ValueError("el monto tiene más de 2 decimales")
    return valor


Monto = Annotated[Decimal, BeforeValidator(a_decimal), AfterValidator(_a_lo_mas_2_decimales)]
"""Monto en USD leído sin ``float`` y con 2 decimales como máximo: si tiene más, el campo
no es válido y da ``CAMPO OBLIGATORIO FALTANTE (<campo>)`` (DEC-257, DEC-244)."""

Entero = StrictInt
"""Entero estricto: ni ``bool`` ni texto ni ``Decimal`` (DEC-238)."""

Booleano = StrictBool
"""Booleano estricto: ni ``0``/``1`` ni ``"true"``/``"false"`` (DEC-238)."""

#: Clave del contexto de validación con la zona de las capturas (``tzinfo`` o ``None``).
CONTEXTO_ZONA = "zona"

#: Clave del contexto de validación con el día de la carga (``datetime.date`` o ``None``):
#: ninguna fecha de una captura puede ser posterior a él (DEC-257). Llega como dato.
CONTEXTO_DIA_DE_CARGA = "dia_de_carga"


def _localizar(valor: object, info: ValidationInfo) -> object:
    """Fecha y hora sin desfase → la misma hora en la zona del contexto (DEC-240).

    Solo toca una fecha **con hora** sin desfase; una fecha sola, un texto que no es ISO 8601
    o un valor con desfase pasan tal cual (``AwareDatetime`` decide). Sin zona en el
    contexto, la fecha y hora sin desfase se rechaza como antes. En el cambio de horario,
    una hora ambigua toma la primera (``fold=0``) y una inexistente, el desfase anterior."""
    contexto = info.context if isinstance(info.context, Mapping) else {}
    zona = contexto.get(CONTEXTO_ZONA)
    if not isinstance(zona, dt.tzinfo):
        return valor
    fecha_hora: dt.datetime | None = None
    if isinstance(valor, dt.datetime):
        fecha_hora = valor
    elif isinstance(valor, str):
        texto = valor.strip()
        if len(texto) > 10 and texto[10] in "T ":
            try:
                fecha_hora = dt.datetime.fromisoformat(texto)
            except ValueError:
                return valor
    if fecha_hora is None or fecha_hora.tzinfo is not None:
        return valor
    return fecha_hora.replace(tzinfo=zona)


FechaHoraCaptura = Annotated[AwareDatetime, BeforeValidator(_localizar)]
"""Fecha y hora de una captura de Jesús: sin desfase, en la zona de PAR-01 (DEC-240)."""


def ausente(valor: object) -> bool:
    """Un campo falta si no viene, es ``null`` o es texto vacío (CTR-03: celda vacía)."""
    return valor is None or (isinstance(valor, str) and not valor.strip())


def obtener(datos: Mapping[str, Any], ruta: str) -> object:
    """Valor de una ruta con punto (``price.current``); ``None`` si no existe."""
    actual: object = datos
    for parte in ruta.split("."):
        if not isinstance(actual, Mapping):
            return None
        actual = actual.get(parte)
    return actual


def faltantes_de_producto(datos: Mapping[str, Any]) -> list[str]:
    """Producto = ``gtin``, o ``brand`` y ``model`` (design.md §6). Si falta, se cita ``gtin``
    cuando no hay ``brand`` ni ``model``; si no, el que falte de los dos."""
    if not ausente(datos.get("gtin")):
        return []
    sin_marca, sin_modelo = ausente(datos.get("brand")), ausente(datos.get("model"))
    if sin_marca and sin_modelo:
        return ["gtin"]
    return ["brand"] if sin_marca else (["model"] if sin_modelo else [])


# --- Validación -----------------------------------------------------------------------


def _sin_vacios(valor: object) -> object:
    """Quita los textos vacíos (cuentan como campo ausente) en todos los niveles."""
    if isinstance(valor, Mapping):
        return {
            k: _sin_vacios(v)
            for k, v in valor.items()
            if not (isinstance(v, str) and not v.strip())
        }
    return valor


def _modelo_anidado(anotacion: object) -> type[BaseModel] | None:
    if isinstance(anotacion, type) and issubclass(anotacion, BaseModel):
        return anotacion
    origen = typing.get_origin(anotacion)
    if origen is typing.Union or origen is types.UnionType or origen is Annotated:
        for arg in typing.get_args(anotacion):
            modelo = _modelo_anidado(arg)
            if modelo is not None:
                return modelo
    return None


def _campo_de_error(modelo: type[BaseModel], loc: Sequence[int | str]) -> str | None:
    """Nombre del campo en el archivo para un error de pydantic, con punto en los anidados.

    Solo usa nombres declarados en el esquema: una clave del archivo (por ejemplo dentro de
    ``evidence``) nunca llega al motivo."""
    partes: list[str] = []
    actual: type[BaseModel] | None = modelo
    for elemento in loc:
        if actual is None or not isinstance(elemento, str):
            break
        por_alias = {(info.alias or nombre): info for nombre, info in actual.model_fields.items()}
        info = por_alias.get(elemento)
        if info is None:
            break
        partes.append(elemento)
        actual = _modelo_anidado(info.annotation)
    return ".".join(partes) or None


def _clave_de_orden(campo: str, orden: Sequence[str], declarados: Sequence[str]) -> float:
    if campo in orden:
        return orden.index(campo)
    for i, obligatorio in enumerate(orden):
        # Un anidado de un obligatorio (availability.state) va justo después de él; un padre
        # de un obligatorio (price de price.current) va en su lugar.
        if campo.startswith(obligatorio + "."):
            return i + 0.5
        if obligatorio.startswith(campo + "."):
            return i
    raiz = campo.split(".", 1)[0]
    posicion = declarados.index(raiz) if raiz in declarados else len(declarados)
    return len(orden) + posicion


def validar_esquema[M: BaseModel](
    modelo: type[M],
    datos: Mapping[str, Any],
    orden: Sequence[str],
    obligatorios: Sequence[str] | None = None,
    faltan: Iterable[str] = (),
    ignorar: Iterable[str] = (),
    contexto: Mapping[str, Any] | None = None,
) -> M:
    """Valida ``datos`` con ``modelo`` o levanta ``RegistroInvalido`` con el primer problema.

    ``orden`` es el orden de los obligatorios del tipo (design.md §6), incluidos los que
    dependen de otros campos; ``obligatorios``, los que siempre deben venir (por defecto,
    todos los de ``orden``), cuya ausencia se detecta aquí; ``faltan``, los que el llamador
    ya sabe que faltan o no son válidos (producto, tipo de cambio); ``ignorar``, los que no
    se reportan. Los demás errores (tipo, tabla cerrada, rango) se ordenan según ``orden`` y
    después en el orden de declaración del esquema. ``contexto`` llega a los validadores
    (por ejemplo, la zona de las capturas en ``CONTEXTO_ZONA``).
    """
    if not isinstance(datos, Mapping):
        raise TypeError("el registro debe ser un mapa de campos")
    ignorados = set(ignorar)
    siempre = orden if obligatorios is None else obligatorios
    problemas = [c for c in siempre if ausente(obtener(datos, c))]
    problemas.extend(faltan)
    try:
        resultado = modelo.model_validate(
            _sin_vacios(datos), context=dict(contexto) if contexto is not None else None
        )
    except ValidationError as error:
        for detalle in error.errors(include_url=False, include_context=False, include_input=False):
            campo = _campo_de_error(modelo, detalle["loc"])
            if campo is not None:
                problemas.append(campo)
        resultado = None
    problemas = [c for c in problemas if c not in ignorados]
    if not problemas and resultado is not None:
        return resultado
    if not problemas:
        # Un error sin campo declarado (no debería pasar con los esquemas de este paquete).
        raise RegistroInvalido.campo_faltante(orden[0] if orden else "registro")
    declarados = [info.alias or nombre for nombre, info in modelo.model_fields.items()]
    primero = min(problemas, key=lambda c: _clave_de_orden(c, orden, declarados))
    raise RegistroInvalido.campo_faltante(primero)
