"""Paso 10 de REQ §3.2: reunir los motivos y decidir el resultado (CMP-16; §3.2.3 y §3.2.4).

- ``reunir_motivos``: **todos** los motivos que aplican, sin repetidos y en el orden de
  §3.2.3 (el de ``oip.catalogos.Motivo``).
- ``decidir``: precedencia de §3.2.4. (1) Al menos un motivo que lleva a ``DESCARTADA`` →
  ``DESCARTADA``; (2) si no, ``SOLO REFERENCIA`` → ``SOLO_REFERENCIA``; (3) si no, al menos un
  motivo de ``REVISION_MANUAL`` → ``REVISION_MANUAL``; (4) si no, ``NIVEL_ASIGNADO`` si algún
  canal tiene nivel, o ``SIN_NIVEL``. El **motivo principal** es el primero de §3.2.3 que
  aplica; se guardan todos.

Como §3.2.3 ordena primero los motivos de descarte, luego ``SOLO REFERENCIA`` y luego los de
revisión, el "lleva a" del motivo principal coincide siempre con el resultado.

``RECHAZADA_VALIDACION`` no entra en la precedencia: la decide el paso 1 y termina la
evaluación. Este módulo no calcula números ni decide qué motivos aplican.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from oip.catalogos import Motivo, Resultado

__all__ = ["Decision", "decidir", "reunir_motivos"]

_ORDEN = {motivo: posicion for posicion, motivo in enumerate(Motivo)}

#: Pasos 1 a 3 de §3.2.4, en orden: el primer resultado que tenga un motivo gana.
_PRECEDENCIA = (Resultado.DESCARTADA, Resultado.SOLO_REFERENCIA, Resultado.REVISION_MANUAL)


@dataclass(frozen=True, slots=True)
class Decision:
    """Resultado, motivo principal y todos los motivos, en el orden de §3.2.3."""

    resultado: Resultado
    motivo_principal: Motivo | None
    motivos: tuple[Motivo, ...]


def reunir_motivos(*grupos: Iterable[Motivo]) -> tuple[Motivo, ...]:
    """Une los motivos de todos los pasos sin repetidos y en el orden de REQ §3.2.3.

    Estricto: un valor que no es ``Motivo`` (por ejemplo el texto ``"EVITAR"``) levanta
    ``TypeError``.
    """
    reunidos: set[Motivo] = set()
    for grupo in grupos:
        for motivo in grupo:
            if not isinstance(motivo, Motivo):
                raise TypeError("cada motivo debe ser un Motivo de oip.catalogos")
            reunidos.add(motivo)
    return tuple(sorted(reunidos, key=_ORDEN.__getitem__))


def decidir(motivos: Iterable[Motivo], hay_nivel: bool) -> Decision:
    """Aplica la precedencia de REQ §3.2.4.

    ``hay_nivel``: algún canal disponible tiene nivel (RN-009); decide entre
    ``NIVEL_ASIGNADO`` y ``SIN_NIVEL`` cuando no hay motivos.
    """
    if type(hay_nivel) is not bool:
        raise TypeError("hay_nivel debe ser bool")
    todos = reunir_motivos(motivos)
    for resultado in _PRECEDENCIA:
        if any(motivo.lleva_a is resultado for motivo in todos):
            # El principal es el primero de §3.2.3 que aplica.
            return Decision(resultado, todos[0], todos)
    resultado = Resultado.NIVEL_ASIGNADO if hay_nivel else Resultado.SIN_NIVEL
    return Decision(resultado, None, todos)
