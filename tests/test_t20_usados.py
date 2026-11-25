"""Pruebas de T20: compra a particular y usados (RN-014, RN-015, RN-008, RN-016; S-12, S-14,
S-31; DEC-263), con los escenarios B18 y B24 (a), (b) y (c) del REQ-2026-0001 v2.9.

Fixtures sintéticos: la publicación de B18 de ``tests/fixtures/observaciones`` (dominio solo
como texto) y comparables, estimados y demanda local armados aquí. Ninguna prueba abre una
URL. Instante explícito, sin reloj ni zona de la máquina.
"""

from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from oip.catalogos import (
    CalidadPrecio,
    Canal,
    CausaCanalCerrado,
    CausaCanalPorRevisar,
    EstadoCanal,
    Motivo,
    Resultado,
)
from oip.configuracion import cargar_configuracion, cargar_configuracion_texto
from oip.dinero import formatear_porcentaje
from oip.entradas.capturas import leer_captura
from oip.entradas.contrato import leer_observacion
from oip.evaluacion import canales, identificacion, motor, referencias
from oip.evaluacion.contexto import ContextoEvaluacion, EvaluacionCanal, ObservacionRegistrada

D = Decimal
FIXTURES = Path(__file__).parent / "fixtures"
BASE = FIXTURES / "config" / "base.yaml"
CONFIG = cargar_configuracion(BASE)
C = CONFIG.contenido
ZONA = ZoneInfo("America/Tijuana")
INSTANTE = dt.datetime(2026, 11, 16, 12, 0, tzinfo=ZONA)
PRODUCTO = UUID(int=2000)
PUBLICACION = UUID(int=2001)


def _b18(**cambios) -> dict:
    datos = json.loads((FIXTURES / "observaciones" / "b18_particular.json").read_text("utf-8"))
    datos.pop("_nota")
    for campo, valor in cambios.items():
        if valor is None:
            datos.pop(campo, None)
        else:
            datos[campo] = valor
    return datos


def _oferta(**cambios) -> ObservacionRegistrada:
    return ObservacionRegistrada(
        leer_observacion(_b18(**cambios)), UUID(int=2002), PUBLICACION, PRODUCTO
    )


def _comparable(precio: str, *, vendido: bool = False, ciudad: str = "san_diego", estado="used"):
    datos = {
        "brand": "DEWALT",
        "model": "DCF840",
        "condition": estado,
        "askingPrice": precio,
        "currency": "USD",
        "city": ciudad,
        "date": "2026-11-15",
        "sold": vendido,
    }
    return leer_captura("local_comparable", datos, zona=ZONA)


def _estimado(precio: str):
    datos = {"brand": "DEWALT", "model": "DCF840", "price": precio, "date": "2026-11-15"}
    return leer_captura("local_estimate", datos, zona=ZONA)


def _demanda_baja():
    datos = {"category": "tools", "level": "low", "date": "2026-11-15"}
    return leer_captura("local_demand", datos, zona=ZONA)


B18_COMPARABLES = (_comparable("120.00"), _comparable("130.00"), _comparable("140.00"))
B24_COMPARABLES = (_comparable("120.00"), _comparable("130.00"))


def _contexto(oferta=None, configuracion=CONFIG, **otros) -> ContextoEvaluacion:
    """Sin datos de Amazon (ni ficha ni mínimo de 60 días; DEC-215) ni historial."""
    return ContextoEvaluacion(
        id_evaluacion=UUID(int=20),
        instante=INSTANTE,
        configuracion=configuracion,
        id_version_configuracion=1,
        oferta=_oferta() if oferta is None else oferta,
        **otros,
    )


def _canal(registro, canal: Canal) -> EvaluacionCanal:
    return next(c for c in registro.canales if c.canal is canal)


# --- B18 ----------------------------------------------------------------------------------


@pytest.mark.scenario("B18")
def test_b18_particular_revision_con_inspeccion():
    registro = motor.evaluar(_contexto(comparables=B18_COMPARABLES))

    assert registro.referencias.valor_referencia_usados == D("110.50")  # 130 × 85%
    assert formatear_porcentaje(registro.descuento_real) == "36.7 %"
    assert registro.costo_compra == D("79.50")  # 70 + 9.50, sin impuesto (S-14)
    assert registro.calidad_precio is CalidadPrecio.NO_APLICA

    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.CERRADO
    assert CausaCanalCerrado.PRODUCTO_NO_NUEVO in amazon.causas_cerrado  # S-12

    local = _canal(registro, Canal.LOCAL)
    assert local.estado is EstadoCanal.DISPONIBLE
    assert local.precio_venta == D("99.45")  # mín(110.50, 120) × 90%
    assert local.margen_neto == D("10.45")
    assert local.castigo == D("9.95")  # 10% sin mínimo de 60 días (S-05)
    assert local.margen_ajustado == D("0.50")
    assert local.nivel is None

    assert registro.motivos == (Motivo.PARTICULAR, Motivo.RIESGO_DE_PROCEDENCIA)
    assert registro.resultado is Resultado.REVISION_MANUAL
    assert registro.motivo_principal is Motivo.PARTICULAR


@pytest.mark.scenario("B18")
def test_b18_usado_no_guarda_el_precio_habitual_dec_263():
    """DEC-263: en un usado, ``references.precio_habitual`` y su fuente quedan vacíos aunque
    haya historial suficiente de nuevos."""
    nuevos = tuple(
        ObservacionRegistrada(
            leer_observacion(
                {
                    "retailerCode": "tienda-prueba",
                    "productUrl": "https://tienda.example.com/p/b18",
                    "title": "DEWALT DCF840",
                    "brand": "DEWALT",
                    "model": "DCF840",
                    "category": "tools",
                    "price": {"current": "179.00", "currency": "USD"},
                    "seller": "comercio",
                    "condition": "new",
                    "availability": {"state": "in_stock_confirmed"},
                    "purchaseMode": "envio",
                    "extractedAt": (INSTANTE - dt.timedelta(days=d)).isoformat(),
                    "blocked": False,
                }
            ),
            UUID(int=3000 + d),
            UUID(int=2999),
            PRODUCTO,
        )
        for d in range(1, 11)
    )
    texto = BASE.read_text(encoding="utf-8").replace(
        "\nretailers:\n",
        "\nretailers:\n  tienda-prueba: {chain: tienda-prueba, domains: [tienda.example.com],"
        " amazon_listing: false}\n",
        1,
    )
    config = cargar_configuracion_texto(texto, origen="t20")
    contexto = _contexto(configuracion=config, historial=nuevos, comparables=B18_COMPARABLES)
    # Con la misma historia, una oferta nueva sí tiene precio habitual.
    nueva = _oferta(condition="new")
    assert (
        referencias.HistorialPropio().precio_habitual(
            _contexto(oferta=nueva, configuracion=config, historial=nuevos)
        )
        is not None
    )

    registro = motor.evaluar(contexto)
    assert registro.referencias.precio_habitual is None
    assert registro.referencias.fuente_precio_habitual is None
    assert registro.referencias.episodio is None
    assert registro.referencias.valor_referencia_usados == D("110.50")
    assert Motivo.SIN_HISTORIAL_SUFICIENTE not in registro.motivos


def test_recogida_sin_impuesto():
    costo = canales.costo_compra(_oferta().observacion, C)
    assert costo.recogida == D("9.50")  # 10 km × 0.20 + 0.5 h × 15.00
    assert costo.impuesto == D("0.00")
    assert costo.total == D("79.50")


def test_recogida_solo_con_particular():
    datos = _b18(pickupLocation="tijuana")
    assert canales.costo_recogida(leer_observacion(datos), C) == D("9.50")
    datos = _b18(pickupLocation="otra_ciudad")
    assert canales.costo_recogida(leer_observacion(datos), C) is None


def test_riesgo_de_procedencia_por_categoria_y_marca():
    oferta = _oferta().observacion
    assert identificacion.es_compra_a_particular(oferta)
    assert identificacion.riesgo_de_procedencia(oferta, C)
    sin_riesgo = _oferta(category="home_kitchen").observacion
    assert not identificacion.riesgo_de_procedencia(sin_riesgo, C)
    assert identificacion.motivos_de_particular(sin_riesgo, C) == (Motivo.PARTICULAR,)
    texto = BASE.read_text(encoding="utf-8").replace(
        "  provenance_risk_brands: []", "  provenance_risk_brands: [dewalt]", 1
    )
    por_marca = cargar_configuracion_texto(texto, origen="t20").contenido
    assert identificacion.riesgo_de_procedencia(sin_riesgo, por_marca)


# --- Valor de referencia de usados (RN-014 §4) --------------------------------------------


def test_valor_de_referencia_solo_con_comparables_del_estado_y_la_zona():
    comparables = (
        *B24_COMPARABLES,
        _comparable("50.00", estado="new"),
        _comparable("50.00", ciudad="ciudad_fuera"),
    )
    contexto = _contexto(comparables=comparables)
    assert len(referencias.comparables_de_usados(contexto)) == 2
    assert referencias.valor_referencia_usados(contexto) is None


def test_valor_de_referencia_con_ventas_concretadas():
    vendidos = tuple(_comparable(p, vendido=True) for p in ("100.00", "110.00", "125.00"))
    contexto = _contexto(comparables=(*vendidos, _comparable("200.00")))
    assert referencias.valor_referencia_usados(contexto) == D("110.00")  # sin factor


def test_valor_de_referencia_con_menos_ventas_que_el_minimo_es_provisional():
    """Lectura provisional (issue #34): con menos ventas que el mínimo, mediana de todos ×
    85%."""
    comparables = (_comparable("120.00", vendido=True), *B24_COMPARABLES[1:], _comparable("140"))
    contexto = _contexto(comparables=comparables)
    assert referencias.valor_referencia_usados(contexto) == D("110.50")


def test_una_oferta_nueva_no_tiene_valor_de_referencia_de_usados():
    contexto = _contexto(oferta=_oferta(condition="new"), comparables=B18_COMPARABLES)
    assert referencias.comparables_de_usados(contexto) == ()
    assert referencias.calcular_referencias(contexto).valor_referencia_usados is None


# --- B24 ----------------------------------------------------------------------------------


@pytest.mark.scenario("B24 (a)")
def test_b24_a_usado_sin_referencia_revision_manual():
    registro = motor.evaluar(_contexto(comparables=B24_COMPARABLES))

    assert registro.referencias.valor_referencia_usados is None
    assert registro.descuento_real is None
    assert registro.costo_compra == D("79.50")
    assert registro.calidad_precio is CalidadPrecio.NO_APLICA
    assert Motivo.MERCADO_YA_BARATO not in registro.motivos
    assert Motivo.SOLO_REFERENCIA not in registro.motivos

    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.CERRADO
    assert CausaCanalCerrado.PRODUCTO_NO_NUEVO in amazon.causas_cerrado

    local = _canal(registro, Canal.LOCAL)
    assert local.estado is EstadoCanal.POR_REVISAR
    assert local.causas_cerrado == ()
    assert local.causas_por_revisar == (CausaCanalPorRevisar.SIN_REFERENCIA_DE_USADOS,)
    assert local.precio_venta is None
    assert local.margen_neto is None and local.margen_ajustado is None
    assert local.nivel_calculado is None

    assert registro.motivos == (
        Motivo.SIN_REFERENCIA_DE_USADOS,
        Motivo.PARTICULAR,
        Motivo.RIESGO_DE_PROCEDENCIA,
    )
    assert registro.resultado is Resultado.REVISION_MANUAL
    assert registro.motivo_principal is Motivo.SIN_REFERENCIA_DE_USADOS


@pytest.mark.scenario("B24 (b)")
def test_b24_b_demanda_local_baja_prevalece_cerrado():
    registro = motor.evaluar(
        _contexto(comparables=B24_COMPARABLES, demanda_local=(_demanda_baja(),))
    )
    local = _canal(registro, Canal.LOCAL)
    assert local.estado is EstadoCanal.CERRADO  # S-31: la causa de cerrado prevalece
    assert local.causas_cerrado == (CausaCanalCerrado.DEMANDA_LOCAL_BAJA,)
    assert local.causas_por_revisar == (CausaCanalPorRevisar.SIN_REFERENCIA_DE_USADOS,)
    assert local.nivel_calculado is None
    assert _canal(registro, Canal.AMAZON).estado is EstadoCanal.CERRADO
    # Los motivos de revisión se guardan.
    for motivo in (
        Motivo.SIN_REFERENCIA_DE_USADOS,
        Motivo.PARTICULAR,
        Motivo.RIESGO_DE_PROCEDENCIA,
    ):
        assert motivo in registro.motivos


@pytest.mark.scenario("B24 (b)")
@pytest.mark.xfail(
    strict=True,
    reason="SIN CANAL DISPONIBLE es de T18 (REQ §3.2.3); T20 no depende de T18 (issue #34)",
)
def test_b24_b_sin_canal_disponible_descartada():
    registro = motor.evaluar(
        _contexto(comparables=B24_COMPARABLES, demanda_local=(_demanda_baja(),))
    )
    assert registro.resultado is Resultado.DESCARTADA
    assert registro.motivo_principal is Motivo.SIN_CANAL_DISPONIBLE


@pytest.mark.scenario("B24 (c)")
def test_b24_c_estimado_de_jesus_margenes_informativos():
    registro = motor.evaluar(
        _contexto(comparables=B24_COMPARABLES, estimados=(_estimado("115.00"),))
    )
    local = _canal(registro, Canal.LOCAL)
    assert local.estado is EstadoCanal.POR_REVISAR
    assert local.causas_por_revisar == (CausaCanalPorRevisar.SIN_REFERENCIA_DE_USADOS,)
    assert local.precio_venta == D("103.50")  # mín(115, techo 120) × 90%
    assert local.margen_neto == D("14.50")
    assert formatear_porcentaje(local.margen_neto_pct) == "18.2 %"
    assert local.castigo == D("10.35")
    assert local.margen_ajustado == D("4.15")
    assert formatear_porcentaje(local.margen_ajustado_pct) == "5.2 %"
    assert local.nivel_calculado is None  # sin descuento real
    assert local.nivel is None
    assert registro.descuento_real is None
    assert registro.resultado is Resultado.REVISION_MANUAL
    assert registro.motivo_principal is Motivo.SIN_REFERENCIA_DE_USADOS
