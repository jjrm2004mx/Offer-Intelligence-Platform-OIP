"""Escenarios B30 (base) y B30 (b) a (e): precio habitual con observaciones diarias y
episodio de liquidación (T09; capacidad ``referencias-de-precio``; RN-002 v2, RN-003 v2;
DEC-201, DEC-224, DEC-226).

"Dado" parcial (design.md §12, DEC-232): el producto solo lo vende Home Depot Chula Vista y
no tiene canal con precio, así que las anotaciones ``SOLO_REFERENCIA`` (día −14) y
``MERCADO YA BARATO`` (día 26) se verifican como la **franja** del descuento real (el
motivo), no como el resultado. Las pruebas entran por el motor con un ``ContextoEvaluacion``.

Fixtures sintéticos: día 0 = 2026-11-18 en ``America/Tijuana`` (PAR-01); las horas van en
hora local, así que el cambio de horario del 2026-11-01 y la observación de las 22:00 del
día −20 (06:00 UTC del día siguiente) prueban que el día calendario es el de Tijuana. Las
URL son de example.com y ninguna prueba las abre.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from oip.catalogos import Motivo
from oip.configuracion import cargar_configuracion
from oip.dinero import formatear_porcentaje
from oip.entradas.contrato import leer_observacion
from oip.evaluacion import motor, referencias
from oip.evaluacion.contexto import ContextoEvaluacion, ObservacionRegistrada
from oip.evaluacion.descuento import descuento_real

CONFIG = cargar_configuracion(Path(__file__).parent / "fixtures" / "config" / "base.yaml")
ZONA = ZoneInfo("America/Tijuana")
HOY = dt.date(2026, 11, 18)
PRODUCTO = UUID(int=900)
PUBLICACION = UUID(int=901)


def contexto_dia(dia: int) -> dt.date:
    return HOY + dt.timedelta(days=dia)


def _momento(dia: int, hora: int = 12) -> dt.datetime:
    fecha = HOY + dt.timedelta(days=dia)
    return dt.datetime(fecha.year, fecha.month, fecha.day, hora, tzinfo=ZONA)


def _observacion(dia: int, precio: str, hora: int = 12) -> ObservacionRegistrada:
    datos = {
        "retailerCode": "homedepot",
        "storeCode": "hd-chula-vista",
        "productUrl": "https://tienda.example.com/p/b30",
        "title": "Producto B30",
        "brand": "MarcaB",
        "model": "B-30",
        "category": "tools",
        "price": {"current": precio, "currency": "USD"},
        "seller": "comercio",
        "condition": "new",
        "availability": {"state": "in_stock", "quantity": 5, "scope": "store"},
        "isClearance": True,
        "purchaseMode": "tienda",
        "extractedAt": _momento(dia, hora).isoformat(),
        "blocked": False,
    }
    # Un id distinto y estable por día y hora.
    ident = UUID(int=10_000 + (dia + 100) * 100 + hora)
    return ObservacionRegistrada(leer_observacion(datos), ident, PUBLICACION, PRODUCTO)


def _precios_base() -> dict[int, str]:
    """Días −25 a −15 $129, −14 a −8 $99, −7 a −1 $65 y hoy $35 (REQ B30)."""
    precios = {d: "129.00" for d in range(-25, -14)}
    precios |= {d: "99.00" for d in range(-14, -7)}
    precios |= {d: "65.00" for d in range(-7, 0)}
    precios[0] = "35.00"
    return precios


def _historial(precios: dict[int, str]) -> list[ObservacionRegistrada]:
    observaciones = []
    for dia in sorted(precios):
        if dia == -20:
            # El día −20 hay dos: $139 a las 10:00 y $129 a las 22:00; cuenta la última.
            observaciones.append(_observacion(dia, "139.00", hora=10))
            observaciones.append(_observacion(dia, precios[dia], hora=22))
        else:
            observaciones.append(_observacion(dia, precios[dia]))
    return observaciones


def _evaluar(precios: dict[int, str], dia: int):
    """Evalúa la oferta del ``dia`` con todo lo observado hasta ese instante."""
    instante = _momento(dia, hora=13)
    historial = [o for o in _historial(precios) if o.observacion.extracted_at <= instante]
    oferta = next(
        o
        for o in reversed(historial)
        if referencias.dia_calendario(o.observacion.extracted_at, ZONA) == HOY + dt.timedelta(dia)
    )
    contexto = ContextoEvaluacion(
        id_evaluacion=UUID(int=1),
        instante=instante,
        configuracion=CONFIG,
        id_version_configuracion=1,
        oferta=oferta,
        historial=tuple(historial),
    )
    return contexto, motor.evaluar(contexto)


def _pct(registro) -> str:
    return formatear_porcentaje(registro.descuento_real)


def _mediana_normal(contexto) -> Decimal | None:
    return referencias.precio_habitual_del_producto(
        referencias.observaciones_diarias(contexto),
        referencias.dia_evaluado(contexto),
        CONFIG.contenido.price_reference,
    )


# --- B30 (base) ---------------------------------------------------------------------------


@pytest.mark.scenario("B30 (base)")
def test_b30_base_una_observacion_por_dia_y_habitual_129_con_historial_suficiente():
    contexto, registro = _evaluar(_precios_base(), -15)
    diarias = referencias.observaciones_diarias(contexto)
    # El día −20 cuenta la última del día ($129 a las 22:00 de Tijuana, no los $139).
    del_dia_20 = [d for d in diarias if d.dia == HOY - dt.timedelta(days=20)]
    assert [d.precio for d in del_dia_20] == [Decimal("129.00")]
    # Días −25 a −15: 11 observaciones a $129 → habitual $129, con historial suficiente.
    contexto_14, _ = _evaluar(_precios_base(), -14)
    ventana = [
        d for d in referencias.observaciones_diarias(contexto_14) if d.dia < HOY - dt.timedelta(14)
    ]
    assert len(ventana) == 11
    assert referencias.historial_suficiente(ventana, CONFIG.contenido.price_reference)
    assert _mediana_normal(contexto_14) == Decimal("129")
    assert registro.referencias.fuente_precio_habitual == "historial_propio"


@pytest.mark.scenario("B30 (base)")
def test_b30_base_la_baja_del_dia_menos_14_abre_el_episodio_congelado_en_129():
    _, registro = _evaluar(_precios_base(), -14)
    episodio = registro.referencias.episodio
    assert episodio is not None
    assert episodio.inicio == HOY - dt.timedelta(days=14)
    assert episodio.valor_congelado == Decimal("129")
    assert registro.referencias.precio_habitual == Decimal("129")
    assert registro.referencias.fuente_precio_habitual == "historial_propio"
    # Día −14, $99 → real 23.3% → franja SOLO_REFERENCIA (DEC-232).
    assert _pct(registro) == "23.3 %"
    assert Motivo.SOLO_REFERENCIA in registro.motivos


@pytest.mark.parametrize(("dia", "real"), [(-7, "49.6 %"), (0, "72.9 %")])
@pytest.mark.scenario("B30 (base)")
def test_b30_base_cada_oferta_del_episodio_se_evalua_contra_129(dia, real):
    _, registro = _evaluar(_precios_base(), dia)
    assert registro.referencias.precio_habitual == Decimal("129")
    assert registro.referencias.episodio.inicio == HOY - dt.timedelta(days=14)
    assert _pct(registro) == real
    assert Motivo.SOLO_REFERENCIA not in registro.motivos
    assert Motivo.MERCADO_YA_BARATO not in registro.motivos


@pytest.mark.scenario("B30 (base)")
def test_b30_base_la_mediana_incluye_el_episodio_pero_no_el_dia_evaluado():
    contexto, _ = _evaluar(_precios_base(), 0)
    ventana = [d for d in referencias.observaciones_diarias(contexto) if d.dia < HOY]
    assert len(ventana) == 25  # días −25 a −1
    normal = _mediana_normal(contexto)
    assert normal == Decimal("99")
    # Sin congelar, el real de hoy sería 64.6%.
    assert formatear_porcentaje(descuento_real(normal, Decimal("35.00"))) == "64.6 %"


# --- B30 (b) ------------------------------------------------------------------------------


def _precios_b() -> dict[int, str]:
    precios = _precios_base()
    precios |= {d: "35.00" for d in range(0, 27)}
    return precios


@pytest.mark.scenario("B30 (b)")
def test_b30_b_el_dia_15_dia_30_del_episodio_todavia_contra_129():
    _, registro = _evaluar(_precios_b(), 15)
    assert registro.referencias.episodio is not None
    assert registro.referencias.precio_habitual == Decimal("129")
    assert _pct(registro) == "72.9 %"


@pytest.mark.scenario("B30 (b)")
def test_b30_b_el_dia_16_dia_31_contra_la_mediana_normal_65():
    contexto, registro = _evaluar(_precios_b(), 16)
    ventana = [d for d in referencias.observaciones_diarias(contexto) if d.dia < contexto_dia(16)]
    assert len(ventana) == 41  # días −25 a 15
    assert registro.referencias.episodio is None
    assert registro.referencias.precio_habitual == Decimal("65")
    assert _pct(registro) == "46.2 %"


@pytest.mark.parametrize(
    ("dia", "observaciones", "habitual", "real"),
    [(25, 50, Decimal("50"), "30.0 %"), (26, 51, Decimal("35"), "0.0 %")],
)
@pytest.mark.scenario("B30 (b)")
def test_b30_b_sin_baja_nueva_no_empieza_otro_episodio_y_la_mediana_baja(
    dia, observaciones, habitual, real
):
    contexto, registro = _evaluar(_precios_b(), dia)
    ventana = [d for d in referencias.observaciones_diarias(contexto) if d.dia < contexto_dia(dia)]
    assert len(ventana) == observaciones
    assert registro.referencias.episodio is None
    assert registro.referencias.precio_habitual == habitual
    assert _pct(registro) == real


@pytest.mark.scenario("B30 (b)")
def test_b30_b_el_dia_25_mediana_par_es_el_promedio_sin_redondear():
    _, registro = _evaluar(_precios_b(), 25)
    # (35 + 65) / 2 = 50, sin pasar por la lista cerrada de montos (DEC-226 b).
    assert registro.referencias.precio_habitual == Decimal("50")
    assert Motivo.MERCADO_YA_BARATO not in registro.motivos
    assert Motivo.SOLO_REFERENCIA not in registro.motivos


@pytest.mark.scenario("B30 (b)")
def test_b30_b_el_dia_26_real_0_es_mercado_ya_barato():
    _, registro = _evaluar(_precios_b(), 26)
    # Franja < 20% → MERCADO YA BARATO (lectura de DEC-232).
    assert Motivo.MERCADO_YA_BARATO in registro.motivos
    assert registro.motivo_principal is Motivo.MERCADO_YA_BARATO


# --- B30 (c) ------------------------------------------------------------------------------


def _precios_c() -> dict[int, str]:
    precios = _precios_base()
    precios |= {d: "35.00" for d in range(0, 5)}
    precios[5] = "129.00"
    return precios


@pytest.mark.scenario("B30 (c)")
def test_b30_c_el_precio_vuelve_al_valor_congelado_y_termina_el_episodio():
    _, antes = _evaluar(_precios_c(), 4)
    assert antes.referencias.episodio is not None  # todavía en el episodio
    contexto, registro = _evaluar(_precios_c(), 5)
    assert registro.referencias.episodio is None
    ventana = [d for d in referencias.observaciones_diarias(contexto) if d.dia < contexto_dia(5)]
    assert len(ventana) == 30  # días −25 a 4
    assert registro.referencias.precio_habitual == Decimal("99")


# --- B30 (d) ------------------------------------------------------------------------------


@pytest.mark.scenario("B30 (d)")
def test_b30_d_se_congela_la_mediana_no_el_precio_del_dia_anterior():
    precios = _precios_base()
    precios[-15] = "139.00"
    _, registro = _evaluar(precios, -14)
    episodio = registro.referencias.episodio
    assert episodio is not None and episodio.inicio == contexto_dia(-14)
    # Mediana de los días −25 a −15 (diez a $129 y una a $139) = $129, no $139.
    assert episodio.valor_congelado == Decimal("129")
    assert _pct(registro) == "23.3 %"  # no 28.8%
    assert Motivo.SOLO_REFERENCIA in registro.motivos


# --- B30 (e) ------------------------------------------------------------------------------


def _precios_e() -> dict[int, str]:
    precios = _precios_base()
    del precios[-15]  # consulta bloqueada: sin observación
    return precios


@pytest.mark.scenario("B30 (e)")
def test_b30_e_baja_contra_la_ultima_observacion_anterior():
    contexto, registro = _evaluar(_precios_e(), -14)
    ventana = [d for d in referencias.observaciones_diarias(contexto) if d.dia < contexto_dia(-14)]
    assert len(ventana) == 10  # días −25 a −16
    episodio = registro.referencias.episodio
    assert episodio is not None and episodio.inicio == contexto_dia(-14)
    assert episodio.valor_congelado == Decimal("129")
    assert _pct(registro) == "23.3 %"
    assert Motivo.SOLO_REFERENCIA in registro.motivos


@pytest.mark.scenario("B30 (e)")
def test_b30_e_hoy_72_9():
    _, registro = _evaluar(_precios_e(), 0)
    assert registro.referencias.episodio.valor_congelado == Decimal("129")
    assert _pct(registro) == "72.9 %"


@pytest.mark.scenario("B30 (e)")
def test_b30_e_la_primera_observacion_no_es_baja():
    # El día −25 no tiene observación anterior: no es baja (y tampoco hay habitual).
    serie = ((contexto_dia(-25), Decimal("129.00")),)
    habitual = {contexto_dia(-25): Decimal("200")}
    assert referencias.episodio_vigente(serie, habitual, CONFIG.contenido.price_reference) is None
