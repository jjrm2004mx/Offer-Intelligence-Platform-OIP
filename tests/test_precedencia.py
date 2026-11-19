"""Pruebas de T04 4.2: precedencia de REQ §3.2.4 (CMP-16) y esqueleto del motor (CMP-17).

Tabla de precedencia de design.md §9 y §12. El "lleva a" de cada motivo está copiado aquí
a mano de REQ §3.2.3, no del catálogo, para que la prueba no dependa del código bajo
prueba. Sin escenarios propios: la precedencia la verifican también B3 y B29 (T18).
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import itertools

import pytest

from oip.catalogos import Canal, EstadoCanal, Motivo, Nivel, Resultado
from oip.evaluacion import motor
from oip.evaluacion.contexto import ContextoEvaluacion, EvaluacionCanal
from oip.evaluacion.resultado import Decision, decidir, reunir_motivos
from test_contexto import _contexto

# REQ §3.2.3, en orden: (código, lleva a).
_TABLA_REQ = (
    ("EVITAR", "DESCARTADA"),
    ("MERCADO YA BARATO", "DESCARTADA"),
    ("SIN CANAL DISPONIBLE", "DESCARTADA"),
    ("MARGEN NEGATIVO", "DESCARTADA"),
    ("SOLO REFERENCIA", "SOLO_REFERENCIA"),
    ("SIN HISTORIAL SUFICIENTE", "REVISION_MANUAL"),
    ("SIN REFERENCIA DE USADOS", "REVISION_MANUAL"),
    ("COINCIDENCIA NO CONFIRMADA", "REVISION_MANUAL"),
    ("VENDEDOR EXTERNO", "REVISION_MANUAL"),
    ("PARTICULAR", "REVISION_MANUAL"),
    ("RIESGO DE PROCEDENCIA", "REVISION_MANUAL"),
    ("DEMANDA DESCONOCIDA", "REVISION_MANUAL"),
)
_ORDEN_REQ = [codigo for codigo, _ in _TABLA_REQ]
_LLEVA_A_REQ = dict(_TABLA_REQ)


def _esperado(codigos: set[str], hay_nivel: bool) -> tuple[str, str | None]:
    """§3.2.4 escrito a partir del REQ: (resultado, motivo principal)."""
    ordenados = [c for c in _ORDEN_REQ if c in codigos]
    for resultado in ("DESCARTADA", "SOLO_REFERENCIA", "REVISION_MANUAL"):
        if any(_LLEVA_A_REQ[c] == resultado for c in ordenados):
            return resultado, ordenados[0]
    return ("NIVEL_ASIGNADO" if hay_nivel else "SIN_NIVEL"), None


def test_el_catalogo_tiene_el_orden_y_el_lleva_a_de_req():
    assert [m.value for m in Motivo] == _ORDEN_REQ
    assert {m.value: m.lleva_a.value for m in Motivo} == _LLEVA_A_REQ


@pytest.mark.parametrize("hay_nivel", [False, True])
def test_precedencia_en_todas_las_combinaciones_de_motivos(hay_nivel):
    # 2^12 combinaciones: la tabla completa de §3.2.4.
    todos = list(Motivo)
    for n in range(len(todos) + 1):
        for combinacion in itertools.combinations(todos, n):
            decision = decidir(combinacion, hay_nivel)
            resultado, principal = _esperado({m.value for m in combinacion}, hay_nivel)
            assert decision.resultado.value == resultado
            assert (decision.motivo_principal.value if decision.motivo_principal else None) == (
                principal
            )
            assert [m.value for m in decision.motivos] == [
                c for c in _ORDEN_REQ if c in {m.value for m in combinacion}
            ]


@pytest.mark.parametrize(
    ("motivos", "hay_nivel", "resultado", "principal"),
    [
        # 1. Cualquier motivo de descarte → DESCARTADA, aunque haya nivel.
        ([Motivo.MARGEN_NEGATIVO], True, Resultado.DESCARTADA, Motivo.MARGEN_NEGATIVO),
        (
            [Motivo.DEMANDA_DESCONOCIDA, Motivo.SOLO_REFERENCIA, Motivo.SIN_CANAL_DISPONIBLE],
            True,
            Resultado.DESCARTADA,
            Motivo.SIN_CANAL_DISPONIBLE,
        ),
        # 2. Si no, SOLO REFERENCIA → SOLO_REFERENCIA, aunque haya motivos de revisión.
        (
            [Motivo.PARTICULAR, Motivo.SOLO_REFERENCIA],
            False,
            Resultado.SOLO_REFERENCIA,
            Motivo.SOLO_REFERENCIA,
        ),
        # 3. Si no, revisión → REVISION_MANUAL.
        (
            [Motivo.DEMANDA_DESCONOCIDA, Motivo.COINCIDENCIA_NO_CONFIRMADA],
            True,
            Resultado.REVISION_MANUAL,
            Motivo.COINCIDENCIA_NO_CONFIRMADA,
        ),
        # 4. Sin motivos: nivel o sin nivel.
        ([], True, Resultado.NIVEL_ASIGNADO, None),
        ([], False, Resultado.SIN_NIVEL, None),
    ],
)
def test_tabla_de_precedencia(motivos, hay_nivel, resultado, principal):
    decision = decidir(motivos, hay_nivel)
    assert decision.resultado is resultado
    assert decision.motivo_principal is principal


def test_se_guardan_todos_los_motivos_sin_repetidos_y_en_orden():
    decision = decidir(
        [Motivo.PARTICULAR, Motivo.EVITAR, Motivo.PARTICULAR, Motivo.MERCADO_YA_BARATO], False
    )
    assert decision.motivos == (Motivo.EVITAR, Motivo.MERCADO_YA_BARATO, Motivo.PARTICULAR)
    assert decision.motivo_principal is Motivo.EVITAR


def test_reunir_motivos_de_varios_pasos():
    assert reunir_motivos([Motivo.DEMANDA_DESCONOCIDA], (), iter([Motivo.EVITAR])) == (
        Motivo.EVITAR,
        Motivo.DEMANDA_DESCONOCIDA,
    )
    assert reunir_motivos() == ()


@pytest.mark.parametrize("valor", ["EVITAR", None, 1])
def test_reunir_motivos_es_estricto(valor):
    with pytest.raises(TypeError):
        reunir_motivos([valor])


@pytest.mark.parametrize("hay_nivel", [1, 0, "true", None])
def test_decidir_exige_un_booleano(hay_nivel):
    with pytest.raises(TypeError):
        decidir([], hay_nivel)


# --- Esqueleto del motor (CMP-17; design.md §3) ---------------------------------------------


def test_los_pasos_siguen_el_orden_interno_de_design_3():
    assert [paso.__name__ for paso in motor.PASOS] == [
        "validar",
        "identificar",
        "calcular_referencias",
        "calcular_descuento",
        "calcular_calidad",
        "calcular_costo_compra",
        "evaluar_canales",
        "asignar_nivel",
        "calcular_unidades_y_rendimiento",
        "elegir_canal",
        "decidir_resultado",
    ]


def test_evaluar_es_puro_y_reproducible_byte_a_byte():
    contexto = _contexto()
    primero = motor.evaluar(contexto)
    segundo = motor.evaluar(ContextoEvaluacion.desde_json(contexto.a_json()))
    assert primero == segundo
    assert primero.a_json() == segundo.a_json()
    assert primero.entrada == contexto
    assert primero.id == contexto.id_evaluacion
    assert primero.evaluado_en == contexto.instante
    assert primero.id_version_configuracion == contexto.id_version_configuracion
    assert dict(primero.versiones_rn) == dict(contexto.versiones_rn)
    assert primero.id_observacion_oferta == contexto.oferta.id
    assert primero.id_evaluacion_anterior == contexto.id_evaluacion_anterior
    assert primero.referencias_cambiadas == contexto.referencias_cambiadas
    assert primero.id_carga == contexto.id_carga


def _con_pasos(monkeypatch, **reemplazos):
    pasos = tuple(reemplazos.get(p.__name__, p) for p in motor.PASOS)
    monkeypatch.setattr(motor, "PASOS", pasos)


def _sin_cambios(contexto, avance):
    return avance


def test_sin_motivos_de_los_pasos_no_hay_motivos_ni_nivel(monkeypatch):
    # Desde T10 el paso 4 da SIN HISTORIAL SUFICIENTE a una oferta nueva sin precio
    # habitual (este contexto no trae historial): se deja sin efecto para probar la
    # precedencia sin motivos.
    _con_pasos(monkeypatch, calcular_descuento=_sin_cambios)
    registro = motor.evaluar(_contexto())
    assert registro.resultado is Resultado.SIN_NIVEL
    assert registro.motivos == ()
    assert registro.motivo_principal is None


def test_sin_historial_el_paso_4_da_revision_manual():
    registro = motor.evaluar(_contexto())
    assert registro.resultado is Resultado.REVISION_MANUAL
    assert registro.motivos == (Motivo.SIN_HISTORIAL_SUFICIENTE,)


def test_el_motor_aplica_la_precedencia_a_los_motivos_de_los_pasos(monkeypatch):
    def identificar(contexto, avance):
        return dataclasses.replace(avance, motivos=(*avance.motivos, Motivo.PARTICULAR))

    def calcular_descuento(contexto, avance):
        return dataclasses.replace(avance, motivos=(*avance.motivos, Motivo.MERCADO_YA_BARATO))

    _con_pasos(monkeypatch, identificar=identificar, calcular_descuento=calcular_descuento)
    registro = motor.evaluar(_contexto())
    assert registro.resultado is Resultado.DESCARTADA
    assert registro.motivo_principal is Motivo.MERCADO_YA_BARATO
    assert registro.motivos == (Motivo.MERCADO_YA_BARATO, Motivo.PARTICULAR)


def test_nivel_asignado_solo_con_un_canal_disponible_con_nivel(monkeypatch):
    def evaluar_canales(contexto, avance):
        canales = (
            EvaluacionCanal(Canal.AMAZON, EstadoCanal.POR_REVISAR, nivel_calculado=Nivel.VIGILAR),
            EvaluacionCanal(Canal.LOCAL, EstadoCanal.DISPONIBLE, nivel=Nivel.RECOMENDABLE),
        )
        return dataclasses.replace(avance, canales=canales)

    def elegir_canal(contexto, avance):
        return dataclasses.replace(
            avance,
            canal_elegido=Canal.LOCAL,
            nivel_aviso=Nivel.RECOMENDABLE,
            canal_aviso=Canal.LOCAL,
        )

    _con_pasos(
        monkeypatch,
        calcular_descuento=_sin_cambios,
        evaluar_canales=evaluar_canales,
        elegir_canal=elegir_canal,
    )
    registro = motor.evaluar(_contexto())
    assert registro.resultado is Resultado.NIVEL_ASIGNADO
    assert registro.nivel_aviso is Nivel.RECOMENDABLE
    assert registro.canal_aviso is Canal.LOCAL


def test_un_canal_por_revisar_con_nivel_calculado_no_da_nivel(monkeypatch):
    def evaluar_canales(contexto, avance):
        canal = EvaluacionCanal(Canal.AMAZON, EstadoCanal.POR_REVISAR, nivel=Nivel.COMPRAR_YA)
        return dataclasses.replace(avance, canales=(canal,))

    _con_pasos(monkeypatch, calcular_descuento=_sin_cambios, evaluar_canales=evaluar_canales)
    assert motor.evaluar(_contexto()).resultado is Resultado.SIN_NIVEL


def test_sin_nivel_asignado_no_hay_nivel_del_aviso(monkeypatch):
    def elegir_canal(contexto, avance):
        return dataclasses.replace(
            avance, canal_elegido=Canal.LOCAL, nivel_aviso=Nivel.VIGILAR, canal_aviso=Canal.LOCAL
        )

    def identificar(contexto, avance):
        return dataclasses.replace(avance, motivos=(Motivo.VENDEDOR_EXTERNO,))

    _con_pasos(monkeypatch, elegir_canal=elegir_canal, identificar=identificar)
    registro = motor.evaluar(_contexto())
    assert registro.resultado is Resultado.REVISION_MANUAL
    assert registro.nivel_aviso is None
    assert registro.canal_aviso is None


def test_un_rechazo_de_validacion_termina_la_evaluacion(monkeypatch):
    corridos = []

    def validar(contexto, avance):
        return dataclasses.replace(avance, motivo_rechazo="PRECIO INVÁLIDO")

    def identificar(contexto, avance):
        corridos.append("identificar")
        return avance

    _con_pasos(monkeypatch, validar=validar, identificar=identificar)
    registro = motor.evaluar(_contexto())
    assert corridos == []
    assert registro.resultado is Resultado.RECHAZADA_VALIDACION
    assert registro.motivo_rechazo == "PRECIO INVÁLIDO"
    assert registro.id_observacion_oferta is None
    assert registro.motivos == ()
    assert _ida_y_vuelta(registro)


def _ida_y_vuelta(registro) -> bool:
    leido = type(registro).desde_json(registro.a_json())
    return leido == registro and leido.a_json() == registro.a_json()


def test_evaluar_exige_un_contexto():
    with pytest.raises(TypeError):
        motor.evaluar({"instante": dt.datetime(2026, 1, 1, tzinfo=dt.UTC)})  # type: ignore[arg-type]


def test_decision_es_inmutable():
    decision = decidir([], False)
    assert isinstance(decision, Decision)
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.resultado = Resultado.DESCARTADA  # type: ignore[misc]
