"""Pruebas independientes de oip-tester para T09 (precio habitual y episodio de liquidación).

Capacidad ``referencias-de-precio``; REQ-2026-0001 §3.2 paso 3 (precio habitual), §3.2 paso 4
(franja), §11 (liquidación escalonada) y B30 (base), (b), (c), (d) y (e); DEC-201, DEC-224 b,
DEC-226 a/b/c, DEC-232, DEC-234 (5); design.md §3, §8, §10 puntos 1 y 2, §12.

Los datos y los resultados esperados de los escenarios se copian del REQ (B30). Las pruebas
complementarias derivan sus números de las reglas del REQ, no del código.

Lectura de DEC-232 / design.md §12: en B30, ``SOLO_REFERENCIA`` (día −14) y ``MERCADO YA
BARATO`` (día 26) se verifican como la **franja** del descuento real (el motivo), no como el
resultado de la evaluación.

Fixtures sintéticos (DEC-194): día 0 = 2026-11-12 en ``America/Tijuana`` (PAR-01), así que la
serie de B30 (desde el 2026-10-18) cruza el cambio de horario del 2026-11-01. Las horas van en
hora de Tijuana y algunas caen en otro día en UTC. Las URL son de example.com y nadie las abre.
Sin reloj, sin red y sin depender de la zona de la máquina.
"""

from __future__ import annotations

import datetime as dt
import itertools
import re
import socket
import time
from decimal import Decimal
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from oip.catalogos import Motivo
from oip.configuracion import cargar_configuracion, cargar_configuracion_texto
from oip.dinero import formatear_porcentaje
from oip.entradas.contrato import leer_observacion
from oip.evaluacion import motor, referencias
from oip.evaluacion.contexto import ContextoEvaluacion, ObservacionRegistrada, RegistroEvaluacion

RAIZ = Path(__file__).resolve().parent
RUTA_CONFIG = RAIZ / "fixtures" / "config" / "base.yaml"
CONFIG = cargar_configuracion(RUTA_CONFIG)
SRC_EVALUACION = RAIZ.parent / "src" / "oip" / "evaluacion"

TIJUANA = ZoneInfo("America/Tijuana")
HOY = dt.date(2026, 11, 12)  # día 0
PRODUCTO = UUID(int=0x7090_0000)
PUB_A = UUID(int=0x7090_0001)  # la publicación de B30 (Home Depot Chula Vista)
PUB_B = UUID(int=0x7090_0002)

_ids = itertools.count(1)


def _fecha(dia: int) -> dt.date:
    return HOY + dt.timedelta(days=dia)


def _local(dia: int, hora: int = 12, minuto: int = 0) -> dt.datetime:
    f = _fecha(dia)
    return dt.datetime(f.year, f.month, f.day, hora, minuto, tzinfo=TIJUANA)


def _obs(
    momento: dt.datetime,
    precio: str,
    publicacion: UUID = PUB_A,
    *,
    seller: str = "comercio",
    condition: str = "new",
    blocked: bool = False,
    store: str = "hd-chula-vista",
) -> ObservacionRegistrada:
    datos = {
        "retailerCode": "homedepot",
        "storeCode": store,
        "productUrl": f"https://tienda.example.com/p/{publicacion.int:x}",
        "title": "Producto sintético T09",
        "brand": "MarcaT",
        "model": "T-09",
        "category": "tools",
        "price": {"current": precio, "currency": "USD"},
        "seller": seller,
        "condition": condition,
        "availability": {"state": "in_stock", "quantity": 3, "scope": "store"},
        "isClearance": True,
        "purchaseMode": "tienda",
        # En UTC: el contrato guarda el instante; el día lo pone PAR-01, no este texto.
        "extractedAt": momento.astimezone(dt.UTC).isoformat(),
        "blocked": blocked,
    }
    return ObservacionRegistrada(
        leer_observacion(datos), UUID(int=0x5000_0000 + next(_ids)), publicacion, PRODUCTO
    )


def _contexto(
    historial: list[ObservacionRegistrada],
    oferta: ObservacionRegistrada,
    instante: dt.datetime,
    config=CONFIG,
) -> ContextoEvaluacion:
    previas = tuple(o for o in historial if o.observacion.extracted_at <= instante)
    return ContextoEvaluacion(
        id_evaluacion=UUID(int=0x7090_FFFF),
        instante=instante,
        configuracion=config,
        id_version_configuracion=7,
        oferta=oferta,
        historial=previas,
    )


# --- B30: datos del REQ ---------------------------------------------------------------------


def _precios_b30(hasta: int = 0) -> dict[int, str]:
    """REQ B30: días −25 a −15 $129; −14 a −8 $99; −7 a −1 $65; hoy $35 (y en (b), $35 hasta
    el día ``hasta``)."""
    p = {d: "129.00" for d in range(-25, -14)}
    p |= {d: "99.00" for d in range(-14, -7)}
    p |= {d: "65.00" for d in range(-7, 0)}
    p |= {d: "35.00" for d in range(0, hasta + 1)}
    return p


def _historial_b30(
    precios: dict[int, str],
) -> tuple[dict[int, ObservacionRegistrada], list[ObservacionRegistrada]]:
    """Una observación por día (la oferta de ese día); el día −20 dos: $139 a las 10:00 y
    $129 a las 22:00 (22:00 de Tijuana = día siguiente en UTC). Devuelve día → la última y
    la lista completa."""
    por_dia: dict[int, ObservacionRegistrada] = {}
    todas: list[ObservacionRegistrada] = []
    for dia in sorted(precios):
        if dia == -20:
            todas.append(_obs(_local(dia, 10), "139.00"))
            ultima = _obs(_local(dia, 22), precios[dia])
        else:
            # Horas variadas: unas antes y otras después de la medianoche UTC.
            hora = 23 if dia % 3 == 0 else (0 if dia % 3 == 1 else 9)
            minuto = 30 if hora == 0 else 15
            ultima = _obs(_local(dia, hora, minuto), precios[dia])
        todas.append(ultima)
        por_dia[dia] = ultima
    return por_dia, todas


def _evaluar_b30(precios: dict[int, str], dia: int, extra=()) -> RegistroEvaluacion:
    por_dia, todas = _historial_b30(precios)
    todas = [*todas, *extra]
    oferta = por_dia[dia]
    instante = oferta.observacion.extracted_at + dt.timedelta(minutes=1)
    return motor.evaluar(_contexto(todas, oferta, instante))


def _franja(registro: RegistroEvaluacion) -> Motivo | None:
    franjas = {Motivo.MERCADO_YA_BARATO, Motivo.SOLO_REFERENCIA}
    encontradas = [m for m in registro.motivos if m in franjas]
    assert len(encontradas) <= 1
    return encontradas[0] if encontradas else None


def _real_esperado(habitual: str, precio: str) -> Decimal:
    h, p = Decimal(habitual), Decimal(precio)
    return (h - p) / h * 100


def _verificar(
    registro: RegistroEvaluacion,
    *,
    habitual: str,
    precio: str,
    mostrado: str,
    episodio_inicio: int | None,
    franja: Motivo | None = None,
):
    ref = registro.referencias
    assert ref is not None
    assert ref.precio_habitual == Decimal(habitual)
    assert ref.fuente_precio_habitual == "historial_propio"
    if episodio_inicio is None:
        assert ref.episodio is None
    else:
        assert ref.episodio is not None
        assert ref.episodio.inicio == _fecha(episodio_inicio)
        assert ref.episodio.valor_congelado == Decimal(habitual)
    assert isinstance(registro.descuento_real, Decimal)
    assert registro.descuento_real == _real_esperado(habitual, precio)  # sin redondear
    assert formatear_porcentaje(registro.descuento_real) == f"{mostrado} %"
    assert _franja(registro) is franja


# --- B30 (base) -----------------------------------------------------------------------------


@pytest.mark.scenario("B30 (base)")
def test_b30_base_habitual_129_con_historial_suficiente_el_dia_menos_20_cuenta_129():
    """Días −25 a −15: 11 observaciones a $129 (el −20 cuenta la última, $129) → $129."""
    por_dia, todas = _historial_b30(_precios_b30())
    oferta = por_dia[-14]
    ctx = _contexto(todas, oferta, oferta.observacion.extracted_at + dt.timedelta(minutes=1))
    diarias = [d for d in referencias.observaciones_diarias(ctx) if d.dia < _fecha(-14)]
    assert len(diarias) == 11
    assert {d.precio for d in diarias} == {Decimal("129.00")}
    assert [d.precio for d in diarias if d.dia == _fecha(-20)] == [Decimal("129.00")]
    assert referencias.precio_habitual_del_producto(
        referencias.observaciones_diarias(ctx), _fecha(-14), CONFIG.contenido.price_reference
    ) == Decimal("129")


@pytest.mark.scenario("B30 (base)")
@pytest.mark.parametrize(
    ("dia", "precio", "mostrado", "franja"),
    [
        (-14, "99.00", "23.3", Motivo.SOLO_REFERENCIA),
        (-7, "65.00", "49.6", None),
        (0, "35.00", "72.9", None),
    ],
)
def test_b30_base_episodio_desde_el_dia_menos_14_congelado_en_129(dia, precio, mostrado, franja):
    """El día −14 baja ($99 < $129) y queda bajo el habitual: episodio (día 1) congelado en
    $129; cada oferta del episodio se evalúa contra $129."""
    registro = _evaluar_b30(_precios_b30(), dia)
    _verificar(
        registro,
        habitual="129",
        precio=precio,
        mostrado=mostrado,
        episodio_inicio=-14,
        franja=franja,
    )


@pytest.mark.scenario("B30 (base)")
def test_b30_base_la_mediana_de_hoy_seria_99_y_sin_congelar_64_6():
    """La mediana incluye el episodio pero no el día evaluado: hoy $99 (25 observaciones,
    días −25 a −1). Sin congelar, el real de hoy sería 64.6%."""
    por_dia, todas = _historial_b30(_precios_b30())
    oferta = por_dia[0]
    ctx = _contexto(todas, oferta, oferta.observacion.extracted_at + dt.timedelta(minutes=1))
    diarias = referencias.observaciones_diarias(ctx)
    en_ventana = [d for d in diarias if d.dia < HOY]
    assert len(en_ventana) == 25
    normal = referencias.precio_habitual_del_producto(
        diarias, HOY, CONFIG.contenido.price_reference
    )
    assert normal == Decimal("99")
    assert formatear_porcentaje(_real_esperado("99", "35")) == "64.6 %"
    registro = motor.evaluar(ctx)
    assert registro.referencias.precio_habitual == Decimal("129")  # congelado, no 99


# --- B30 (b) --------------------------------------------------------------------------------


@pytest.mark.scenario("B30 (b)")
@pytest.mark.parametrize(
    ("dia", "habitual", "mostrado", "episodio", "franja"),
    [
        (15, "129", "72.9", -14, None),  # día 30 del episodio
        (16, "65", "46.2", None, None),  # día 31: mediana normal, 41 observaciones
        (25, "50", "30.0", None, None),  # 50 observaciones: par, promedio 35 y 65
        (26, "35", "0.0", None, Motivo.MERCADO_YA_BARATO),  # 51 observaciones
    ],
)
def test_b30_b_limite_de_30_dias_sin_episodio_nuevo(dia, habitual, mostrado, episodio, franja):
    registro = _evaluar_b30(_precios_b30(hasta=26), dia)
    _verificar(
        registro,
        habitual=habitual,
        precio="35.00",
        mostrado=mostrado,
        episodio_inicio=episodio,
        franja=franja,
    )


@pytest.mark.scenario("B30 (b)")
def test_b30_b_cuenta_de_observaciones_de_las_medianas():
    """41 (días −25 a 15), 50 (−25 a 24) y 51 (−25 a 25) observaciones diarias."""
    por_dia, todas = _historial_b30(_precios_b30(hasta=26))
    for dia, cuantas in ((16, 41), (25, 50), (26, 51)):
        oferta = por_dia[dia]
        ctx = _contexto(todas, oferta, oferta.observacion.extracted_at + dt.timedelta(minutes=1))
        en_ventana = [d for d in referencias.observaciones_diarias(ctx) if d.dia < _fecha(dia)]
        assert len(en_ventana) == cuantas, dia


# --- B30 (c) --------------------------------------------------------------------------------


@pytest.mark.scenario("B30 (c)")
def test_b30_c_vuelve_a_129_termina_el_episodio_y_mediana_normal_99():
    precios = _precios_b30(hasta=4) | {5: "129.00", 6: "129.00"}
    # Día 4, todavía en el episodio.
    _verificar(
        _evaluar_b30(precios, 4),
        habitual="129",
        precio="35.00",
        mostrado="72.9",
        episodio_inicio=-14,
    )
    # Día 5: termina; 30 observaciones (días −25 a 4) → $99.
    registro = _evaluar_b30(precios, 5)
    assert registro.referencias.episodio is None
    assert registro.referencias.precio_habitual == Decimal("99")
    assert registro.descuento_real == _real_esperado("99", "129.00")
    assert _franja(registro) is Motivo.MERCADO_YA_BARATO
    # "Desde ahí": el día 6 tampoco vuelve al episodio (31 observaciones → $99).
    registro6 = _evaluar_b30(precios, 6)
    assert registro6.referencias.episodio is None
    assert registro6.referencias.precio_habitual == Decimal("99")


# --- B30 (d) --------------------------------------------------------------------------------


@pytest.mark.scenario("B30 (d)")
def test_b30_d_se_congela_la_mediana_129_no_el_precio_del_dia_anterior_139():
    precios = _precios_b30() | {-15: "139.00"}
    registro = _evaluar_b30(precios, -14)
    _verificar(
        registro,
        habitual="129",
        precio="99.00",
        mostrado="23.3",
        episodio_inicio=-14,
        franja=Motivo.SOLO_REFERENCIA,
    )
    assert formatear_porcentaje(registro.descuento_real) != "28.8 %"
    assert formatear_porcentaje(_real_esperado("139", "99")) == "28.8 %"  # lo que no debe dar
    # Y el resto del episodio sigue contra $129.
    _verificar(
        _evaluar_b30(precios, 0),
        habitual="129",
        precio="35.00",
        mostrado="72.9",
        episodio_inicio=-14,
    )


# --- B30 (e) --------------------------------------------------------------------------------


@pytest.mark.scenario("B30 (e)")
@pytest.mark.parametrize(
    ("dia", "precio", "mostrado", "franja"),
    [(-14, "99.00", "23.3", Motivo.SOLO_REFERENCIA), (0, "35.00", "72.9", None)],
)
def test_b30_e_sin_observacion_del_dia_menos_15(dia, precio, mostrado, franja):
    """El día −15 no tiene observación: la baja se compara con los $129 del día −16; la
    mediana de los días −25 a −16 (10 observaciones) es $129."""
    precios = _precios_b30()
    del precios[-15]
    registro = _evaluar_b30(precios, dia)
    _verificar(
        registro,
        habitual="129",
        precio=precio,
        mostrado=mostrado,
        episodio_inicio=-14,
        franja=franja,
    )


@pytest.mark.scenario("B30 (e)")
def test_b30_e_consulta_bloqueada_el_dia_menos_15_no_cuenta():
    """Variante: la consulta del día −15 llegó como bloqueada. No es observación (REQ §3.1
    punto 5): ni para la baja ni para la mediana. Con un precio absurdo, si contara, el día
    −14 no sería baja ($99 > $1)."""
    precios = _precios_b30()
    del precios[-15]
    bloqueada = _obs(_local(-15, 12), "1.00", blocked=True)
    for dia, precio, mostrado in ((-14, "99.00", "23.3"), (0, "35.00", "72.9")):
        registro = _evaluar_b30(precios, dia, extra=(bloqueada,))
        _verificar(
            registro,
            habitual="129",
            precio=precio,
            mostrado=mostrado,
            episodio_inicio=-14,
            franja=Motivo.SOLO_REFERENCIA if dia == -14 else None,
        )


@pytest.mark.scenario("B30 (e)")
def test_b30_e_la_primera_observacion_no_es_baja():
    """Día −25: sin observación anterior no hay baja (DEC-226 c). Con una primera
    observación muy baja y un historial de otra publicación, no abre episodio."""
    otra = [_obs(_local(d, 12), "129.00", PUB_B, store="hd-national-city") for d in range(-10, 0)]
    primera = _obs(_local(0, 12), "35.00", PUB_A)
    registro = motor.evaluar(_contexto(otra, primera, _local(0, 13)))
    assert registro.referencias.episodio is None
    assert registro.referencias.precio_habitual == Decimal("129")
    # Y la serie de B30 no abre nada el día −25 (sin historial no hay habitual).
    r25 = _evaluar_b30(_precios_b30(), -25)
    assert r25.referencias.precio_habitual is None
    assert r25.referencias.episodio is None
    assert r25.descuento_real is None


# --- Mediana --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("valores", "esperada"),
    [
        (["35", "65"], "50"),
        (["99.99", "100.00"], "99.995"),  # sin redondear a centavos
        (["10.01", "10.02", "10.03", "10.04"], "10.025"),
        (["3", "1", "2"], "2"),
        (["129", "99", "65", "129", "35"], "99"),
        (["0.01"], "0.01"),
    ],
)
def test_mediana_par_e_impar_sin_redondear(valores, esperada):
    resultado = referencias.mediana([Decimal(v) for v in valores])
    assert resultado == Decimal(esperada)
    assert isinstance(resultado, Decimal)


def test_mediana_rechaza_float():
    with pytest.raises(TypeError):
        referencias.mediana([Decimal("1"), 2.5])  # type: ignore[list-item]


def test_mediana_par_en_el_registro_y_valor_congelado_sin_redondear():
    """Seis días a 99.99/100.00 → mediana 99.995; el día −4 baja a $50 → episodio congelado
    en 99.995 (no en $100.00, el precio del día anterior, ni en 100.00 redondeado). Hoy la
    mediana normal sería 99.99 (10 observaciones), pero sigue el congelado."""
    historial = [
        _obs(_local(d, 12), p, PUB_A)
        for d, p in zip(range(-10, -4), ["99.99"] * 3 + ["100.00"] * 3, strict=True)
    ]
    historial += [_obs(_local(d, 12), "50.00", PUB_A) for d in range(-4, 1)]
    baja = historial[6]
    r_baja = motor.evaluar(_contexto(historial, baja, _local(-4, 13)))
    assert r_baja.referencias.precio_habitual == Decimal("99.995")
    assert r_baja.referencias.episodio.valor_congelado == Decimal("99.995")
    assert r_baja.referencias.episodio.inicio == _fecha(-4)
    assert r_baja.descuento_real == _real_esperado("99.995", "50.00")
    hoy = historial[-1]
    r_hoy = motor.evaluar(_contexto(historial, hoy, _local(0, 13)))
    assert r_hoy.referencias.precio_habitual == Decimal("99.995")
    assert '"99.995"' in r_hoy.a_json()


# --- Ventana de 60 días sin el día evaluado -------------------------------------------------


def _pub(n: int) -> UUID:
    return UUID(int=0x7091_0000 + n)


def test_ventana_de_60_dias_incluye_el_dia_menos_60_y_excluye_el_61_y_el_de_hoy():
    """Días −60 a −56 a $100 (5 en 5 días: justo suficiente). El día −61 y el día evaluado
    traen seis publicaciones a $10 cada uno: si entraran, la mediana sería $10."""
    historial = [_obs(_local(d, 12), "100.00", PUB_A) for d in range(-60, -55)]
    historial += [_obs(_local(-61, 12), "10.00", _pub(n)) for n in range(6)]
    historial += [_obs(_local(0, 8), "10.00", _pub(10 + n)) for n in range(6)]
    oferta = _obs(_local(0, 12), "90.00", PUB_B, store="hd-national-city")
    registro = motor.evaluar(_contexto(historial, oferta, _local(0, 13)))
    assert registro.referencias.precio_habitual == Decimal("100")
    assert registro.descuento_real == Decimal("10")
    assert _franja(registro) is Motivo.MERCADO_YA_BARATO


def test_sin_el_dia_menos_60_no_hay_historial_suficiente():
    """Solo 4 observaciones en la ventana (−59 a −56) → sin precio habitual (5 en 3 días)."""
    historial = [_obs(_local(d, 12), "100.00", PUB_A) for d in range(-59, -55)]
    historial += [_obs(_local(-61, 12), "100.00", _pub(n)) for n in range(6)]
    oferta = _obs(_local(0, 12), "50.00", PUB_B, store="hd-national-city")
    registro = motor.evaluar(_contexto(historial, oferta, _local(0, 13)))
    assert registro.referencias.precio_habitual is None
    assert registro.referencias.fuente_precio_habitual is None
    assert registro.descuento_real is None


def test_historial_suficiente_5_observaciones_en_3_dias():
    """5 observaciones en 3 días (dos publicaciones) sí; 5 en 2 días no; 4 en 4 no."""

    def evaluar(dias_pub_a, dias_pub_b):
        h = [_obs(_local(d, 12), "100.00", PUB_A) for d in dias_pub_a]
        h += [_obs(_local(d, 12), "100.00", _pub(1)) for d in dias_pub_b]
        oferta = _obs(_local(0, 12), "70.00", PUB_B, store="hd-national-city")
        return motor.evaluar(_contexto(h, oferta, _local(0, 13))).referencias.precio_habitual

    assert evaluar([-3, -2, -1], [-2, -1]) == Decimal("100")
    assert evaluar([-2, -1], [-2, -1]) is None  # 4 en 2 días
    assert evaluar([-2, -1, -1], [-2, -1]) is None  # el −1 repetido cuenta una vez
    assert evaluar([-4, -3, -2, -1], []) is None  # 4 en 4 días


def test_solo_cuentan_nuevo_y_vendido_por_el_comercio_para_la_mediana():
    """Design.md §10.1: un vendedor externo o un usado no entran a la mediana del producto."""
    h = [_obs(_local(d, 12), "100.00", PUB_A) for d in range(-5, 0)]
    h += [_obs(_local(d, 12), "1.00", _pub(1), seller="externo") for d in range(-5, 0)]
    h += [_obs(_local(d, 12), "1.00", _pub(2), condition="used") for d in range(-5, 0)]
    h += [_obs(_local(d, 12), "1.00", _pub(3), blocked=True) for d in range(-5, 0)]
    oferta = _obs(_local(0, 12), "70.00", PUB_B, store="hd-national-city")
    registro = motor.evaluar(_contexto(h, oferta, _local(0, 13)))
    assert registro.referencias.precio_habitual == Decimal("100")


# --- Día calendario en America/Tijuana ------------------------------------------------------


def test_dia_calendario_de_tijuana_y_no_de_utc_con_instante_de_noche():
    """El instante es las 23:30 de Tijuana del día 0 (07:30 UTC del día 1): el día evaluado es
    el 0. Una observación de las 23:45 del día −1 (UTC: día 0) es del día −1 y sí cuenta."""
    h = [_obs(_local(d, 12), "100.00", PUB_A) for d in range(-5, -1)]
    h.append(_obs(_local(-1, 23, 45), "100.00", PUB_A))
    # Del día 0 en Tijuana (no cuentan), seis publicaciones a $10.
    h += [_obs(_local(0, 9), "10.00", _pub(20 + n)) for n in range(6)]
    oferta = _obs(_local(0, 23, 0), "80.00", PUB_B, store="hd-national-city")
    instante = _local(0, 23, 30)
    assert instante.astimezone(dt.UTC).date() == _fecha(1)
    ctx = _contexto(h, oferta, instante)
    assert referencias.dia_evaluado(ctx) == HOY
    registro = motor.evaluar(ctx)
    assert registro.referencias.precio_habitual == Decimal("100")
    assert registro.descuento_real == Decimal("20")
    assert _franja(registro) is Motivo.SOLO_REFERENCIA  # 20% exacto: de 20 a < 25


def test_dia_calendario_cruzando_el_cambio_de_horario_del_1_de_noviembre():
    """2026-11-01: PDT (−7) hasta las 02:00, luego PST (−8). 00:30 del 1 (PDT) y 23:30 del 1
    (PST) son del mismo día; las 23:30 del 31 de octubre (PDT) son del 31. Con un desfase
    fijo de −8, las 00:30 PDT caerían el 31."""
    zona = TIJUANA
    tarde_31 = dt.datetime(2026, 10, 31, 23, 30, tzinfo=zona)
    temprano_1 = dt.datetime(2026, 11, 1, 0, 30, tzinfo=zona)
    noche_1 = dt.datetime(2026, 11, 1, 23, 30, tzinfo=zona)
    assert temprano_1.utcoffset() == dt.timedelta(hours=-7)
    assert noche_1.utcoffset() == dt.timedelta(hours=-8)
    for m, dia in (
        (tarde_31, dt.date(2026, 10, 31)),
        (temprano_1, dt.date(2026, 11, 1)),
        (noche_1, dt.date(2026, 11, 1)),
    ):
        assert referencias.dia_calendario(m.astimezone(dt.UTC), zona) == dia
    # Por el motor: el 31 a $200; el 1 a $100 (00:30) y $150 (23:30, la última) → 150.
    h = [
        _obs(dt.datetime(2026, 10, 31, 12, tzinfo=zona), "200.00", PUB_A),
        _obs(temprano_1, "100.00", PUB_A),
        _obs(noche_1, "150.00", PUB_A),
        _obs(dt.datetime(2026, 11, 2, 12, tzinfo=zona), "150.00", PUB_A),
        _obs(dt.datetime(2026, 11, 3, 12, tzinfo=zona), "150.00", PUB_A),
    ]
    oferta = _obs(dt.datetime(2026, 11, 4, 12, tzinfo=zona), "150.00", PUB_A)
    ctx = _contexto(h, oferta, dt.datetime(2026, 11, 4, 13, tzinfo=zona))
    diarias = {d.dia: d.precio for d in referencias.observaciones_diarias(ctx)}
    assert diarias[dt.date(2026, 10, 31)] == Decimal("200.00")
    assert diarias[dt.date(2026, 11, 1)] == Decimal("150.00")
    assert len([d for d in diarias if d < dt.date(2026, 11, 4)]) == 4
    # 4 observaciones en 4 días: sin historial suficiente.
    assert motor.evaluar(ctx).referencias.precio_habitual is None


def _resumen(registro: RegistroEvaluacion):
    return (
        registro.referencias,
        registro.descuento_real,
        registro.motivos,
        registro.resultado,
        registro.evaluado_en,
    )


def test_el_resultado_no_depende_de_la_zona_de_la_maquina(monkeypatch):
    base = _resumen(_evaluar_b30(_precios_b30(), 0))
    for zona in ("Asia/Tokyo", "UTC", "Pacific/Kiritimati"):
        monkeypatch.setenv("TZ", zona)
        time.tzset()
        try:
            otro = _resumen(_evaluar_b30(_precios_b30(), 0))
        finally:
            monkeypatch.undo()
            time.tzset()
        assert otro == base, zona


# --- Límite del episodio desde PAR-08 -------------------------------------------------------


def _config_con(**cambios) -> object:
    texto = RUTA_CONFIG.read_text(encoding="utf-8")
    for clave, valor in cambios.items():
        texto, n = re.subn(rf"(\n  {clave}: )\d+", rf"\g<1>{valor}", texto)
        assert n == 1, clave
    return cargar_configuracion_texto(texto, origen="t09-tester.yaml")


@pytest.mark.parametrize(
    ("limite", "ultimo_dia_congelado", "normal"),
    [(30, 15, "65"), (10, -5, "129"), (1, -14, "129")],
)
def test_el_limite_del_episodio_sale_de_par_08(limite, ultimo_dia_congelado, normal):
    """Con límite N, el día N del episodio (inicio −14) aún va contra $129; el N+1 va contra
    la mediana normal: con 30, el día 16 → $65 (B30 b); con 10, el día −4 → 21 observaciones
    (11 a $129, 7 a $99, 3 a $65) → $129; con 1, el día −13 → 12 observaciones → $129."""
    config = CONFIG if limite == 30 else _config_con(clearance_episode_max_days=limite)
    por_dia, todas = _historial_b30(_precios_b30(hasta=26))

    def evaluar(dia):
        oferta = por_dia[dia]
        ctx = _contexto(
            todas, oferta, oferta.observacion.extracted_at + dt.timedelta(minutes=1), config
        )
        return motor.evaluar(ctx).referencias

    dentro = evaluar(ultimo_dia_congelado)
    assert dentro.episodio is not None
    assert dentro.precio_habitual == Decimal("129")
    fuera = evaluar(ultimo_dia_congelado + 1)
    assert fuera.episodio is None
    assert fuera.precio_habitual == Decimal(normal)


def test_la_ventana_y_el_historial_suficiente_salen_de_par_08():
    """Con ``sufficient_history_observations: 6`` las 5 observaciones ya no alcanzan."""
    h = [_obs(_local(d, 12), "100.00", PUB_A) for d in range(-5, 0)]
    oferta = _obs(_local(0, 12), "70.00", PUB_B, store="hd-national-city")
    assert motor.evaluar(_contexto(h, oferta, _local(0, 13))).referencias.precio_habitual
    config = _config_con(sufficient_history_observations=6)
    r = motor.evaluar(_contexto(h, oferta, _local(0, 13), config))
    assert r.referencias.precio_habitual is None
    config = _config_con(usual_window_days=3)
    r = motor.evaluar(_contexto(h, oferta, _local(0, 13), config))
    assert r.referencias.precio_habitual is None  # 3 en 3 días


def test_ningun_numero_de_par_08_esta_fijo_en_referencias():
    texto = (SRC_EVALUACION / "referencias.py").read_text(encoding="utf-8")
    codigo = re.sub(r'"""[\s\S]*?"""|#.*', "", texto)
    for numero in ("60", "30", "90"):
        assert not re.search(rf"\b{numero}\b", codigo), numero
    assert not re.search(r"\b5\b|\b3\b", codigo)


# --- Episodio: más allá de B30 (derivado de las reglas del REQ) -----------------------------


def test_tras_el_limite_una_baja_nueva_abre_otro_episodio_en_la_mediana_de_ese_dia():
    """DEC-224 b: sin baja nueva no empieza otro; con baja nueva sí. B30 con $35 hasta el día
    19 y $20 el día 20: baja ($20 < $35) bajo el habitual del día (45 observaciones, días −25
    a 19 → la 23.ª ordenada = $65) → episodio nuevo desde el día 20, congelado en $65."""
    precios = _precios_b30(hasta=19) | {20: "20.00"}
    registro = _evaluar_b30(precios, 20)
    assert registro.referencias.episodio is not None
    assert registro.referencias.episodio.inicio == _fecha(20)
    assert registro.referencias.precio_habitual == Decimal("65")
    assert registro.descuento_real == _real_esperado("65", "20.00")


def test_el_episodio_es_de_la_publicacion_y_no_del_producto():
    """Otra publicación del mismo producto, a $129 estable, no hereda el episodio de B30."""
    precios = _precios_b30()
    por_dia, todas = _historial_b30(precios)
    todas += [_obs(_local(d, 12), "129.00", PUB_B, store="hd-national-city") for d in range(-25, 0)]
    oferta_b = _obs(_local(0, 12), "129.00", PUB_B, store="hd-national-city")
    registro = motor.evaluar(_contexto(todas, oferta_b, _local(0, 13)))
    assert registro.referencias.episodio is None
    # 50 observaciones: 7 a $65, 7 a $99 y 36 a $129 → la 25.ª y 26.ª, $129.
    assert registro.referencias.precio_habitual == Decimal("129")
    # La publicación de B30 conserva su episodio con el mismo historial.
    oferta_a = por_dia[0]
    r_a = motor.evaluar(
        _contexto(todas, oferta_a, oferta_a.observacion.extracted_at + dt.timedelta(minutes=1))
    )
    assert r_a.referencias.episodio is not None


# --- Dinero, reproducibilidad, sin reloj ni red ---------------------------------------------


def test_sin_float_y_sin_redondeo_en_referencias_y_descuento():
    """Design.md §8: solo ``dinero.py`` redondea; el habitual, las medianas y los porcentajes
    no se redondean. T09 no calcula montos de la lista cerrada."""
    for nombre in ("referencias.py", "descuento.py"):
        texto = (SRC_EVALUACION / nombre).read_text(encoding="utf-8")
        codigo = re.sub(r'"""[\s\S]*?"""|#.*', "", texto)
        assert "quantize" not in codigo, nombre
        assert "round(" not in codigo, nombre
        assert "float" not in codigo, nombre
    registro = _evaluar_b30(_precios_b30(), -14)
    assert registro.costo_compra is None
    assert registro.descuento_real == Decimal(30) / Decimal(129) * 100
    assert registro.descuento_real != Decimal("23.3")
    datos = registro.a_json()
    assert "23.2558" in datos  # sin redondear en el registro


def test_sin_reloj_ni_red_en_evaluacion(monkeypatch):
    for nombre in ("referencias.py", "descuento.py", "motor.py"):
        texto = (SRC_EVALUACION / nombre).read_text(encoding="utf-8")
        assert not re.search(
            r"\.now\(|\.today\(|utcnow|time\.time|import (requests|httpx|"
            r"urllib|socket|aiohttp)",
            texto,
        ), nombre

    def prohibido(*_a, **_k):
        raise AssertionError("la evaluación intentó abrir una conexión")

    monkeypatch.setattr(socket.socket, "connect", prohibido)
    monkeypatch.setattr(socket, "create_connection", prohibido)
    assert _evaluar_b30(_precios_b30(), 0).referencias.precio_habitual == Decimal("129")


def test_reproducible_el_mismo_contexto_da_el_mismo_registro():
    por_dia, todas = _historial_b30(_precios_b30())
    oferta = por_dia[0]
    ctx = _contexto(todas, oferta, oferta.observacion.extracted_at + dt.timedelta(minutes=1))
    primero = motor.evaluar(ctx).a_json()
    assert motor.evaluar(ctx).a_json() == primero
    # Desde el input_snapshot (ida y vuelta del contexto) sale el mismo registro.
    leido = ContextoEvaluacion.desde_json(ctx.a_json())
    assert motor.evaluar(leido).a_json() == primero
    # El orden del historial no cambia nada.
    al_reves = _contexto(list(reversed(todas)), oferta, ctx.instante)
    assert motor.evaluar(al_reves).referencias == motor.evaluar(ctx).referencias
    assert motor.evaluar(al_reves).descuento_real == motor.evaluar(ctx).descuento_real


def test_el_registro_guarda_referencia_fuente_inicio_y_valor_congelado():
    registro = _evaluar_b30(_precios_b30(), -7)
    leido = RegistroEvaluacion.desde_json(registro.a_json())
    assert leido.referencias == registro.referencias
    ref = leido.referencias
    assert ref.precio_habitual == Decimal("129")
    assert ref.fuente_precio_habitual == "historial_propio"
    assert ref.episodio.inicio == _fecha(-14)
    assert ref.episodio.valor_congelado == Decimal("129")
    datos = registro.a_json()
    assert "historial_propio" in datos
    assert _fecha(-14).isoformat() in datos
    # Sin episodio: la referencia y la fuente, sin inicio ni valor congelado.
    sin = _evaluar_b30(_precios_b30(hasta=16), 16)
    assert sin.referencias.episodio is None
    assert sin.referencias.fuente_precio_habitual == "historial_propio"


@pytest.mark.parametrize(
    ("precio", "franja"),
    [
        ("80.01", Motivo.MERCADO_YA_BARATO),  # 19.99%
        ("80.00", Motivo.SOLO_REFERENCIA),  # 20% exacto
        ("75.01", Motivo.SOLO_REFERENCIA),  # 24.99%
        ("75.00", None),  # 25% exacto: sigue
        ("100.00", Motivo.MERCADO_YA_BARATO),  # 0%
        ("120.00", Motivo.MERCADO_YA_BARATO),  # negativo
    ],
)
def test_franja_con_los_cortes_de_par_10_sin_redondear(precio, franja):
    """RN-003 v2: < 20% descarta; de 20% a < 25% solo referencia; ≥ 25% sigue."""
    h = [_obs(_local(d, 12), "100.00", PUB_A) for d in range(-5, 0)]
    oferta = _obs(_local(0, 12), precio, PUB_B, store="hd-national-city")
    registro = motor.evaluar(_contexto(h, oferta, _local(0, 13)))
    assert registro.descuento_real == _real_esperado("100", precio)
    assert _franja(registro) is franja
