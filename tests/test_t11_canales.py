"""Pruebas de T11: confianza (RN-007), costo de compra, canal Amazon, venta local,
rentabilidad, nivel, elección y nivel del aviso (CMP-10, CMP-13, CMP-14, CMP-15), con el
escenario B1, RNF-9 (``MARGEN ESTIMADO`` y ``EMPAQUE POR CONFIRMAR``) y la concurrencia
cerrado / por revisar (S-31).

Fixtures sintéticos: comercios ficticios con dominios reservados (example.com, example.net);
ninguna prueba abre una URL. Instante explícito, sin reloj ni zona de la máquina.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from config_tienda_prueba import BASE, TIENDA_PRUEBA, con_tienda_prueba
from oip.catalogos import (
    CalidadPrecio,
    Canal,
    CausaCanalCerrado,
    CausaCanalPorRevisar,
    Confianza,
    DemandaAmazon,
    DemandaLocal,
    EstadoCanal,
    Marca,
    Nivel,
    Resultado,
)
from oip.configuracion import cargar_configuracion_texto
from oip.dinero import formatear_porcentaje
from oip.entradas.capturas import leer_captura
from oip.entradas.contrato import leer_observacion
from oip.evaluacion import canales, eleccion, identificacion, motor, referencias, rentabilidad
from oip.evaluacion.contexto import ContextoEvaluacion, EvaluacionCanal, ObservacionRegistrada

# --- Configuración y fixtures -------------------------------------------------------------

_EXTRA = "  tienda-b: {chain: cadena-b, domains: [example.net], amazon_listing: false}\n"


def _config(*reemplazos: tuple[str, str]):
    texto = con_tienda_prueba(BASE.read_text(encoding="utf-8"))
    texto = texto.replace("\nretailers:\n", "\nretailers:\n" + _EXTRA, 1)
    for viejo, nuevo in reemplazos:
        assert texto.count(viejo) == 1, viejo
        texto = texto.replace(viejo, nuevo)
    return cargar_configuracion_texto(texto, origen="t11")


CONFIG = _config()
C = CONFIG.contenido
ZONA = ZoneInfo("America/Tijuana")
HOY = dt.date(2026, 10, 14)  # fuera de la temporada de juguetes (S-10)
INSTANTE = dt.datetime(2026, 10, 14, 13, 0, tzinfo=ZONA)
PRODUCTO = UUID(int=900)
PUB_OFERTA = UUID(int=901)
PUB_AMAZON = UUID(int=902)
PUB_WALMART = UUID(int=903)

_contador = iter(range(20_000, 20_000_000))
_URL = {
    TIENDA_PRUEBA: "https://tienda.example.com/p/1",
    "tienda-b": "https://example.net/p/1",
    "amazon": "https://amazon.example.com/dp/X",
}


def _momento(dias: int = 0, horas_antes: int = 0) -> dt.datetime:
    return INSTANTE + dt.timedelta(days=dias) - dt.timedelta(hours=horas_antes)


def _obs(precio: str, *, comercio: str, publicacion: UUID, momento: dt.datetime, **cambios):
    datos = {
        "retailerCode": comercio,
        "productUrl": _URL[comercio],
        "title": "Sierra circular de prueba",
        "brand": "MarcaP",
        "model": "SC-1",
        "category": "tools",
        "price": {"current": precio, "currency": "USD"},
        "seller": "comercio",
        "condition": "new",
        "availability": {"state": "in_stock_confirmed"},
        "purchaseMode": "envio",
        "extractedAt": momento.isoformat(),
        "blocked": False,
    }
    datos.update(cambios)
    return ObservacionRegistrada(
        leer_observacion(datos), UUID(int=next(_contador)), publicacion, PRODUCTO
    )


def _oferta_b1(**cambios) -> ObservacionRegistrada:
    """B1: tienda física en liquidación, herramientas, 4 kg, $29.00 con tachado $129.00,
    "3 disponibles" hace 2 h, tienda a 7.75%."""
    datos = {
        "storeCode": "hd-chula-vista",
        "gtin": "036000291452",
        "weightKg": "4",
        "price": {"current": "29.00", "was": "129.00", "currency": "USD"},
        "availability": {"state": "in_stock", "quantity": 3},
        "isClearance": True,
        "purchaseMode": "tienda",
        "taxLocation": "tienda_prueba",
    }
    datos.update(cambios)
    return _obs(
        "29.00",
        comercio=TIENDA_PRUEBA,
        publicacion=PUB_OFERTA,
        momento=_momento(horas_antes=2),
        **datos,
    )


def _ficha(buy_box: str | None, momento: dt.datetime, **listing):
    datos = {"buyBoxPrice": buy_box, **listing}
    return _obs(
        "999.00",
        comercio="amazon",
        publicacion=PUB_AMAZON,
        momento=momento,
        amazonListing=datos,
    )


def _fichas_b1(*, rank: int | None = 6000, vendidos: int | None = 200, vendedores: int = 5):
    """Ranking 6,000 los 7 días que terminan hoy y hace 30 días; botón de compra $119 hoy y
    los 6 días anteriores; mínimo de 60 días $109 (hace 20 días)."""
    hoy = {"rankMain": rank, "sellersNew": vendedores}
    if vendidos is not None:
        hoy["boughtLastMonth"] = vendidos
    fichas = [_ficha("119.00", _momento(horas_antes=2), **hoy)]
    fichas += [
        _ficha("119.00", _momento(-d), rankMain=rank, sellersNew=vendedores) for d in range(1, 7)
    ]
    fichas += [
        _ficha(None, _momento(-d), rankMain=rank, sellersNew=vendedores) for d in range(30, 37)
    ]
    fichas.append(_ficha("109.00", _momento(-20), sellersNew=vendedores))
    return fichas


def _historial_b1():
    """Walmart en línea: $124 hoy (hace 8 h) y $124 hace 60 días (60 días de historial)."""
    return [
        _obs("124.00", comercio="tienda-b", publicacion=PUB_WALMART, momento=_momento(-60)),
        _obs(
            "124.00", comercio="tienda-b", publicacion=PUB_WALMART, momento=_momento(horas_antes=8)
        ),
    ]


def _contexto(oferta=None, historial=None, fichas=None, configuracion=CONFIG, **otros):
    return ContextoEvaluacion(
        id_evaluacion=UUID(int=1),
        instante=INSTANTE,
        configuracion=configuracion,
        id_version_configuracion=1,
        oferta=_oferta_b1() if oferta is None else oferta,
        historial=tuple(_historial_b1() if historial is None else historial),
        fichas_amazon=tuple(_fichas_b1() if fichas is None else fichas),
        **otros,
    )


def _canal(registro, canal: Canal) -> EvaluacionCanal:
    return next(c for c in registro.canales if c.canal is canal)


D = Decimal


# --- B1 de punta a punta ------------------------------------------------------------------


@pytest.mark.scenario("B1")
def test_b1_sierra_circular_amazon_muy_recomendable():
    registro = motor.evaluar(_contexto())

    assert registro.confianza is Confianza.ALTA
    assert formatear_porcentaje(registro.descuento_anunciado) == "77.5 %"
    assert formatear_porcentaje(registro.descuento_real) == "75.6 %"
    assert Marca.DESCUENTO_ANUNCIADO_NO_COMPROBADO.value in registro.marcas
    assert registro.referencias.precio_habitual == D("119.00")
    assert registro.referencias.precio_mercado_hoy == D("119.00")
    assert registro.referencias.minimo_60_dias_amazon == D("109.00")
    assert registro.referencias.precio_venta_amazon == D("119.00")
    assert Marca.COMPETENCIA_MAS_BARATA.value not in registro.marcas
    assert registro.calidad_precio is CalidadPrecio.BUENA_OFERTA
    assert registro.costo_compra == D("31.25")

    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.DISPONIBLE
    assert amazon.costo_venta == D("33.85")
    assert amazon.margen_neto == D("53.90")
    assert formatear_porcentaje(amazon.margen_neto_pct) == "172.5 %"
    assert amazon.costo_devoluciones == D("4.17")
    assert amazon.castigo == D("5.00")
    assert amazon.margen_ajustado == D("44.73")
    assert formatear_porcentaje(amazon.margen_ajustado_pct) == "143.1 %"
    assert amazon.unidades == 3
    assert amazon.dias_para_recuperar == 37
    assert formatear_porcentaje(amazon.rendimiento_mensual_pct) == "116.1 %"
    assert amazon.nivel is Nivel.MUY_RECOMENDABLE
    assert amazon.nivel_calculado is Nivel.MUY_RECOMENDABLE
    assert amazon.ganancia_total == D("134.19")

    local = _canal(registro, Canal.LOCAL)
    assert local.estado is EstadoCanal.DISPONIBLE
    assert local.precio_venta == D("91.04")
    assert local.margen_neto == D("50.29")
    assert formatear_porcentaje(local.margen_neto_pct) == "160.9 %"
    assert local.castigo == D("0.00")
    assert local.unidades == 2
    assert local.dias_para_recuperar == 30
    assert formatear_porcentaje(local.rendimiento_mensual_pct) == "160.9 %"
    assert local.nivel is Nivel.MUY_RECOMENDABLE
    assert local.ganancia_total == D("100.58")
    assert Marca.SIN_COMPARABLES_LOCALES.value in local.marcas
    # Las marcas de la oferta van en el registro (TAB-10); las de cada canal, en el canal.
    assert registro.marcas == (Marca.DESCUENTO_ANUNCIADO_NO_COMPROBADO.value,)

    diferencia = (amazon.ganancia_total - local.ganancia_total) / amazon.ganancia_total * 100
    assert formatear_porcentaje(diferencia) == "25.0 %"
    assert registro.canal_elegido is Canal.AMAZON
    assert registro.resultado is Resultado.NIVEL_ASIGNADO
    assert registro.motivos == ()
    assert registro.nivel_aviso is Nivel.MUY_RECOMENDABLE
    assert registro.canal_aviso is Canal.AMAZON


def test_b1_cuentas_de_amazon_paso_a_paso():
    """11.1: confianza, costo de compra y canal Amazon de B1 con las funciones de CMP-13."""
    contexto = _contexto()
    oferta = contexto.oferta.observacion
    costo = canales.costo_compra(oferta, C)
    assert (costo.tasa_impuesto_pct, costo.impuesto, costo.total) == (
        D("7.75"),
        D("2.25"),
        D("31.25"),
    )
    ranking = canales.ranking_amazon(contexto)
    assert (ranking.promedio, ranking.dias_con_datos, ranking.promedio_hace_30_dias) == (
        D(6000),
        7,
        D(6000),
    )
    demanda = canales.demanda_en_amazon(
        oferta.category, ranking, canales.ficha_vigente(contexto), C
    )
    assert demanda.demanda is DemandaAmazon.SUFICIENTE and not demanda.a_la_baja
    assert canales.comision_amazon(D("119"), C.categories[oferta.category].commission) == D("17.85")
    envio = canales.envio_amazon(oferta, C.shipping)
    assert (envio.envio, envio.empaque, envio.peso_estimado) == (D("14.00"), D("2.00"), False)
    assert canales.ventas_al_mes_amazon(canales.ficha_vigente(contexto)) == 33


# --- RNF-9: todo cálculo de Amazon es estimado -------------------------------------------


def _marcas_amazon(**cambios):
    return _canal(motor.evaluar(_contexto(**cambios)), Canal.AMAZON)


@pytest.mark.parametrize(
    "contexto",
    [
        {},  # disponible (B1)
        {"fichas": _fichas_b1(rank=None)},  # por revisar: demanda desconocida
        {"fichas": _fichas_b1(rank=420_000)},  # cerrado con neto informativo
    ],
    ids=["disponible", "por_revisar", "cerrado_con_neto"],
)
def test_rnf9_todo_calculo_de_amazon_lleva_margen_estimado_y_empaque(contexto):
    amazon = _marcas_amazon(**contexto)
    assert amazon.margen_neto is not None
    assert Marca.MARGEN_ESTIMADO.value in amazon.marcas
    assert Marca.EMPAQUE_POR_CONFIRMAR.value in amazon.marcas


def test_rnf9_sin_calculo_de_amazon_no_hay_marcas_de_estimado():
    """Sin precio de venta en Amazon no hay margen de Amazon (REQ §3.2.1) ni sus marcas."""
    sin_oferta = [f for f in _fichas_b1() if f.observacion.amazon_listing.buy_box_price is None]
    amazon = _marcas_amazon(fichas=sin_oferta)
    assert amazon.estado is EstadoCanal.CERRADO
    assert amazon.margen_neto is None
    assert Marca.MARGEN_ESTIMADO.value not in amazon.marcas
    assert Marca.EMPAQUE_POR_CONFIRMAR.value not in amazon.marcas


def test_la_venta_local_no_lleva_las_marcas_de_amazon():
    local = _canal(motor.evaluar(_contexto()), Canal.LOCAL)
    assert Marca.MARGEN_ESTIMADO.value not in local.marcas
    assert Marca.EMPAQUE_POR_CONFIRMAR.value not in local.marcas


# --- S-31: concurrencia cerrado / por revisar ---------------------------------------------


@pytest.mark.parametrize(
    ("cerrado", "por_revisar", "estado"),
    [
        ((), (), EstadoCanal.DISPONIBLE),
        ((), (CausaCanalPorRevisar.DEMANDA_DESCONOCIDA,), EstadoCanal.POR_REVISAR),
        ((CausaCanalCerrado.SIN_ROTACION,), (), EstadoCanal.CERRADO),
        (
            (CausaCanalCerrado.DEMANDA_LOCAL_BAJA,),
            (CausaCanalPorRevisar.SIN_REFERENCIA_DE_USADOS,),
            EstadoCanal.CERRADO,
        ),
    ],
)
def test_s31_cerrado_prevalece_sobre_por_revisar(cerrado, por_revisar, estado):
    assert canales.estado_del_canal(cerrado, por_revisar) is estado


def test_s31_en_el_motor_amazon_cerrado_aunque_falte_el_ranking():
    """Sin ranking (por revisar) y comisión desconocida (cerrado) → cerrado (S-31), sin
    nivel_calculado (DEC-224 a)."""
    config = _config(
        (
            "    commission: {type: flat, rate_pct: 15, min_per_unit: 0.30}\n"
            "    return_rate: {source: own, rate_pct: 7}\n",
            "    return_rate: {source: own, rate_pct: 7}\n",
        ),
    )
    amazon = _marcas_amazon(fichas=_fichas_b1(rank=None), configuracion=config)
    assert amazon.estado is EstadoCanal.CERRADO
    assert amazon.causas_cerrado == (CausaCanalCerrado.COMISION_DESCONOCIDA,)
    assert amazon.causas_por_revisar == (CausaCanalPorRevisar.DEMANDA_DESCONOCIDA,)
    assert amazon.nivel_calculado is None and amazon.nivel is None
    assert CausaCanalCerrado.COMISION_DESCONOCIDA.value in amazon.marcas


def test_por_revisar_tiene_nivel_calculado_sin_unidades_y_no_se_elige():
    """S-30: por revisar → márgenes y nivel_calculado; sin unidades, días ni rendimiento."""
    registro = motor.evaluar(_contexto(fichas=_fichas_b1(rank=None)))
    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.POR_REVISAR
    assert amazon.margen_ajustado == D("44.73")
    assert amazon.nivel_calculado is Nivel.MUY_RECOMENDABLE
    assert amazon.nivel is None
    assert (amazon.unidades, amazon.dias_para_recuperar, amazon.ganancia_total) == (None,) * 3
    assert registro.canal_elegido is Canal.LOCAL


# --- Confianza RN-007 ---------------------------------------------------------------------


_P = C.levels.confidence


def _conf(horas: str, **cambios):
    oferta = _oferta_b1(**cambios).observacion
    instante = oferta.extracted_at + dt.timedelta(minutes=int(D(horas) * 60))
    return identificacion.confianza_disponibilidad(oferta, instante, _P)


@pytest.mark.parametrize(
    ("horas", "liquidacion", "esperada"),
    [
        ("2", True, Confianza.ALTA),  # B1: 2 h ≤ 3 h
        ("3", True, Confianza.ALTA),
        ("4", True, Confianza.MEDIA),  # RN-007 ejemplo C
        ("12", True, Confianza.MEDIA),
        ("12.5", True, Confianza.BAJA),
        ("6", False, Confianza.ALTA),
        ("8", False, Confianza.MEDIA),  # RN-007 ejemplo B
        ("24", False, Confianza.MEDIA),
        ("25", False, Confianza.BAJA),
    ],
)
def test_confianza_cantidad_exacta(horas, liquidacion, esperada):
    assert _conf(horas, isClearance=liquidacion) is esperada


@pytest.mark.parametrize(
    ("horas", "estado", "esperada"),
    [
        ("12", "in_stock", Confianza.MEDIA),
        ("13", "in_stock", Confianza.BAJA),
        ("2", "limited_stock", Confianza.MEDIA),  # RN-007 ejemplo D
        ("3", "limited_stock", Confianza.BAJA),
        ("1", "out_of_stock", Confianza.BAJA),
    ],
)
def test_confianza_sin_numero_y_pocas_unidades(horas, estado, esperada):
    disponibilidad = {"state": estado}
    assert _conf(horas, isClearance=False, availability=disponibilidad) is esperada


def test_confianza_sin_saber_si_es_liquidacion_usa_las_ventanas_normales():
    assert _conf("5", isClearance=None) is Confianza.ALTA


def test_confianza_en_linea_y_recoger_en_tienda():
    """S-25: disponible confirmada cuenta como Alta; los demás estados en línea, sin confianza."""
    confirmada = {"state": "in_stock_confirmed"}
    assert _conf("30", purchaseMode="envio", availability=confirmada) is Confianza.ALTA
    assert _conf("30", purchaseMode="recoleccion", availability=confirmada) is Confianza.ALTA
    assert _conf("1", purchaseMode="envio", availability={"state": "limited_stock"}) is None


def test_confianza_baja_en_tienda_marca_y_deja_sin_nivel():
    oferta = _oferta_b1(
        availability={"state": "limited_stock"},
        extractedAt=_momento(horas_antes=3).isoformat(),  # B21: más de 2 h
    )
    registro = motor.evaluar(_contexto(oferta=oferta))
    assert registro.confianza is Confianza.BAJA
    assert Marca.CONFIANZA_BAJA.value in registro.marcas
    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.nivel is None and amazon.nivel_calculado is Nivel.MUY_RECOMENDABLE
    assert registro.resultado is Resultado.SIN_NIVEL


def test_antiguedad_sin_float_y_sin_zona_de_la_maquina():
    antes = dt.datetime(2026, 10, 14, 11, 30, tzinfo=dt.UTC)
    assert identificacion.antiguedad_horas(antes + dt.timedelta(hours=2), antes) == D("2")
    with pytest.raises(ValueError):
        identificacion.antiguedad_horas(antes, antes + dt.timedelta(seconds=1))
    with pytest.raises(ValueError):
        identificacion.antiguedad_horas(dt.datetime(2026, 10, 14, 12), antes)  # noqa: DTZ001


# --- Costo de compra e impuesto -----------------------------------------------------------


def test_tasa_de_respaldo_y_particular_sin_impuesto():
    sin_ubicacion = _oferta_b1(taxLocation=None).observacion
    assert canales.tasa_impuesto(sin_ubicacion, C.taxes) == D("7.75")
    chula = _oferta_b1(taxLocation="chula_vista").observacion
    assert canales.tasa_impuesto(chula, C.taxes) == D("8.75")


def test_costo_de_compra_redondea_el_impuesto_una_vez():
    oferta = _oferta_b1(price={"current": "79.00", "currency": "USD"}).observacion
    costo = canales.costo_compra(oferta, C)
    assert (costo.impuesto, costo.total) == (D("6.12"), D("85.12"))  # RN-001 ejemplo A


# --- Comisiones, envío y tasa de devolución -----------------------------------------------


def test_comisiones_con_umbral_y_por_tramos():
    belleza = C.categories["beauty"].commission
    assert canales.comision_amazon(D("10.00"), belleza) == D("0.80")
    assert canales.comision_amazon(D("10.01"), belleza) == D("1.50")
    joyeria = C.categories["jewelry"].commission
    assert canales.comision_amazon(D("300"), joyeria) == D("52.50")  # RN-006 ejemplo E
    relojes = C.categories["watches"].commission
    assert canales.comision_amazon(D("200"), relojes) == D("32.00")  # RN-006 ejemplo D
    assert canales.comision_amazon(D("1.00"), C.categories["tools"].commission) == D("0.30")


@pytest.mark.parametrize(
    ("peso", "envio", "empaque"),
    [("1", "8.00", "1.00"), ("2", "12.00", "2.00"), ("6", "14.00", "2.00")],
)
def test_envio_por_peso(peso, envio, empaque):
    resultado = canales.envio_amazon(_oferta_b1(weightKg=peso).observacion, C.shipping)
    assert (resultado.envio, resultado.empaque) == (D(envio), D(empaque))


def test_sin_peso_estimado_y_mas_de_6_kg_por_cotizar():
    sin_peso = canales.envio_amazon(_oferta_b1(weightKg=None).observacion, C.shipping)
    assert sin_peso.peso_estimado and (sin_peso.envio, sin_peso.empaque) == (D(14), D(2))
    assert canales.envio_amazon(_oferta_b1(weightKg="8").observacion, C.shipping) is None


def test_tasa_de_devolucion_propia_asignada_y_desconocida():
    assert canales.tasa_devolucion_amazon("tools", C).tasa_pct == D(7)
    asignada = canales.tasa_devolucion_amazon("video_games", C)
    assert asignada.tasa_pct == D(11) and asignada.estimada
    assert canales.tasa_devolucion_amazon("toys", C) is None


# --- Venta local --------------------------------------------------------------------------


def _comparable(precio: str, ciudad: str = "san_diego", vendido: bool = False):
    datos = {
        "brand": "MarcaP",
        "model": "SC-1",
        "condition": "new",
        "askingPrice": precio,
        "currency": "USD",
        "city": ciudad,
        "date": "2026-10-10",
        "sold": vendido,
    }
    return leer_captura("local_comparable", datos, zona=ZONA)


def _estimado(precio: str):
    datos = {"brand": "MarcaP", "model": "SC-1", "price": precio, "date": "2026-10-10"}
    return leer_captura("local_estimate", datos, zona=ZONA)


def test_precio_local_con_estimado_y_techo():
    """RN-016 ejemplo A: estimado $129, techo $135 → pedido $129 → $116.10."""
    contexto = _contexto(
        comparables=(_comparable("135"), _comparable("139"), _comparable("150")),
        estimados=(_estimado("129"),),
    )
    precio = canales.precio_venta_local(contexto, D("149"))
    assert (precio.precio, precio.techo) == (D("116.10"), D("135"))


def test_precio_local_sin_estimado_redondea_una_vez():
    """B33: 100.15 × 85% × 90% = 76.614750 → 76.61 (no 76.62)."""
    precio = canales.precio_venta_local(_contexto(), D("100.15"))
    assert precio.precio == D("76.61") and precio.techo is None


def test_comparables_fuera_de_la_zona_no_cuentan():
    contexto = _contexto(comparables=(_comparable("50", ciudad="otra"),))
    assert canales.precio_venta_local(contexto, D("119")).techo is None


def test_sin_estimado_ni_mercado_hoy_no_hay_precio_local():
    assert canales.precio_venta_local(_contexto(), None) is None


def test_demanda_local_baja_cierra_y_competencia_baja_un_nivel():
    baja = leer_captura(
        "local_demand", {"category": "tools", "level": "low", "date": "2026-10-01"}, zona=ZONA
    )
    registro = motor.evaluar(_contexto(demanda_local=(baja,)))
    local = _canal(registro, Canal.LOCAL)
    assert local.estado is EstadoCanal.CERRADO
    assert local.causas_cerrado == (CausaCanalCerrado.DEMANDA_LOCAL_BAJA,)
    assert local.margen_neto == D("50.29") and local.margen_ajustado is None
    muchos = tuple(_comparable(str(200 + i)) for i in range(11))
    assert canales.demanda_local(_contexto(comparables=muchos)) is DemandaLocal.LOW


def test_entrega_por_defecto():
    assert canales.costo_entrega(C.local_sale.transport) == D("9.50")


# --- Rentabilidad -------------------------------------------------------------------------


def test_devoluciones_y_castigo_redondeados_una_vez():
    assert rentabilidad.costo_devoluciones(D("149"), D(7), D(50)) == D("5.22")
    castigo = C.amazon.drop_penalty
    assert rentabilidad.castigo_por_baja(D("149"), D("139"), castigo) == D("5.00")
    assert rentabilidad.castigo_por_baja(D("116.10"), D("139"), castigo) == D("0.00")
    assert rentabilidad.castigo_por_baja(D("149"), None, castigo) == D("14.90")  # B15


def test_nivel_por_umbrales_y_minimo_por_unidad():
    umbrales = C.levels.thresholds
    assert rentabilidad.nivel_por_umbrales(D("82"), D("35"), umbrales) is Nivel.RECOMENDABLE
    assert rentabilidad.nivel_por_umbrales(D("47"), D("20.3"), umbrales) is None
    minimo = C.levels.min_per_unit
    assert rentabilidad.minimo_por_unidad(D("85.12"), minimo) == D("10.00")
    assert rentabilidad.minimo_por_unidad(D("200"), minimo) == D("20")


def test_nivel_calculado_con_minimo_y_competencia():
    margenes = rentabilidad.Margenes(D("15"), D("50"), D(0), D(0), D("9.99"), D("45"))
    assert rentabilidad.nivel_calculado(D("75"), margenes, D("20"), C, False) is None
    margenes = dataclasses.replace(margenes, margen_ajustado=D("10.00"))
    nivel = rentabilidad.nivel_calculado(D("75"), margenes, D("20"), C, False)
    assert nivel is Nivel.MUY_RECOMENDABLE
    assert rentabilidad.nivel_calculado(D("75"), margenes, D("20"), C, True) is Nivel.RECOMENDABLE
    assert rentabilidad.nivel_calculado(D("24.99"), margenes, D("20"), C, False) is None


def test_tope_unidades_dias_y_rendimiento():
    tope = C.amazon.first_purchase_cap
    assert rentabilidad.tope_primera_compra(D(6000), Nivel.MUY_RECOMENDABLE, tope) == 5
    assert rentabilidad.tope_primera_compra(D(6000), Nivel.RECOMENDABLE, tope) == 3
    assert rentabilidad.tope_primera_compra(D(10000), Nivel.COMPRAR_YA, tope) == 3
    assert rentabilidad.tope_primera_compra(None, Nivel.COMPRAR_YA, tope) == 3
    assert rentabilidad.unidades_recomendadas(33, 3, None, 5, 2) == 3
    assert rentabilidad.unidades_recomendadas(None, 3, None, 5, 2) == 2  # B12
    assert rentabilidad.unidades_recomendadas(30, None, 1, 3, 2) == 1
    assert rentabilidad.dias_para_recuperar(3, 33, 7, None, 30) == 37
    assert rentabilidad.dias_para_recuperar(2, 2, None, 14, 0) == 30
    assert rentabilidad.dias_para_recuperar(3, 2, 7, None, 30) == 75  # 45 días: hacia arriba
    assert rentabilidad.dias_para_recuperar(0, 2, None, 14, 0) is None
    pct = D("44.73") / D("31.25") * 100
    assert formatear_porcentaje(rentabilidad.rendimiento_mensual(pct, 37)) == "116.1 %"
    assert rentabilidad.ganancia_total(D("44.73"), 3) == D("134.19")


def test_sin_ventas_al_mes_maximo_2_y_marca_estimado():
    amazon = _marcas_amazon(fichas=_fichas_b1(vendidos=None))
    assert amazon.unidades == 2
    assert "ESTIMADO (unidades)" in amazon.marcas
    assert amazon.ganancia_total == D("89.46")  # B12


def test_sin_rotacion_cierra_amazon():
    """S-08 (B25): 10 ÷ (15 + 1) = 0.625 → 0 → cerrado."""
    amazon = _marcas_amazon(fichas=_fichas_b1(vendidos=10, vendedores=15))
    assert amazon.causas_cerrado == (CausaCanalCerrado.SIN_ROTACION,)
    assert amazon.unidades is None and amazon.nivel_calculado is None


def test_competencia_mas_barata_baja_un_nivel_en_amazon():
    assert canales.competencia_mas_barata(D("99"), D("119"), D("15"))
    assert not canales.competencia_mas_barata(D("101.15"), D("119"), D("15"))
    assert not canales.competencia_mas_barata(None, D("119"), D("15"))


def test_sin_descuento_real_suficiente_no_hay_nivel_ni_unidades():
    """REQ §3.2.1: en un canal disponible el margen ajustado siempre; sin descuento real ≥
    25%, ni nivel ni unidades."""
    canal = EvaluacionCanal(
        canal=Canal.LOCAL,
        estado=EstadoCanal.DISPONIBLE,
        precio_venta=D("50"),
        costo_venta=D("9.50"),
        margen_neto=D("20"),
        margen_neto_pct=D("100"),
        costo_devoluciones=D(0),
        castigo=D(0),
        margen_ajustado=D("20"),
        margen_ajustado_pct=D("100"),
    )
    insumos = canales.evaluar_local(
        _contexto(), referencias.calcular_referencias(_contexto()), None
    )
    sin = rentabilidad.asignar_nivel(
        canal,
        insumos,
        descuento_real=D("24"),
        costo_compra=D("20"),
        confianza_ok=True,
        configuracion=C,
    )
    assert sin.nivel is None and sin.nivel_calculado is None
    unidades = rentabilidad.calcular_unidades(sin, insumos, descuento_real=D("24"), configuracion=C)
    assert unidades == sin


def test_rentabilidad_rechaza_float():
    with pytest.raises(TypeError):
        rentabilidad.margen_neto(119.0, D("31.25"), D("33.85"))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        canales.comision_amazon(119.0, C.categories["tools"].commission)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        rentabilidad.unidades_recomendadas(True, 3, None, 5, 2)  # bool no es entero


# --- Elección y nivel del aviso -----------------------------------------------------------


def _con_nivel(canal: Canal, nivel: Nivel | None, total: str, rendimiento: str, estado=None):
    return EvaluacionCanal(
        canal=canal,
        estado=EstadoCanal.DISPONIBLE if estado is None else estado,
        nivel=nivel,
        nivel_calculado=nivel,
        ganancia_total=D(total),
        rendimiento_mensual_pct=D(rendimiento),
    )


def test_eleccion_por_ganancia_y_desempate_por_rendimiento():
    diez = C.levels.channel_tiebreak_pct
    amazon = _con_nivel(Canal.AMAZON, Nivel.MUY_RECOMENDABLE, "134.19", "116.1")
    local = _con_nivel(Canal.LOCAL, Nivel.MUY_RECOMENDABLE, "100.58", "160.9")
    assert eleccion.canal_elegido((amazon, local), diez) is Canal.AMAZON  # 25.0%
    # RN-018 ejemplo C: 100 contra 105 (4.8%) → el de mayor rendimiento.
    amazon = _con_nivel(Canal.AMAZON, Nivel.RECOMENDABLE, "100.00", "40.0")
    local = _con_nivel(Canal.LOCAL, Nivel.RECOMENDABLE, "105.00", "60.0")
    assert eleccion.canal_elegido((amazon, local), diez) is Canal.LOCAL
    # B26 (b): 8.7% < 10% → el rendimiento (local), aunque Amazon gane más.
    amazon = _con_nivel(Canal.AMAZON, Nivel.MUY_RECOMENDABLE, "110.19", "95.3")
    local = _con_nivel(Canal.LOCAL, Nivel.MUY_RECOMENDABLE, "100.58", "160.9")
    assert eleccion.canal_elegido((amazon, local), diez) is Canal.LOCAL


def test_eleccion_solo_con_canales_disponibles_con_nivel():
    diez = C.levels.channel_tiebreak_pct
    revisar = _con_nivel(
        Canal.AMAZON, Nivel.COMPRAR_YA, "500", "500", estado=EstadoCanal.POR_REVISAR
    )
    local = _con_nivel(Canal.LOCAL, Nivel.VIGILAR, "10", "1")
    assert eleccion.elegir((revisar, local), diez) == eleccion.Eleccion(
        Canal.LOCAL, Nivel.VIGILAR, Canal.LOCAL
    )
    sin = _con_nivel(Canal.LOCAL, None, "10", "1")
    assert eleccion.elegir((sin,), diez) == eleccion.Eleccion(None, None, None)


def test_nivel_del_aviso_el_mas_alto_y_empate_con_el_elegido():
    """S-33 (B9): gana Amazon en Recomendable, el aviso va con Muy recomendable (local)."""
    amazon = _con_nivel(Canal.AMAZON, Nivel.RECOMENDABLE, "134.19", "116.1")
    local = _con_nivel(Canal.LOCAL, Nivel.MUY_RECOMENDABLE, "69.98", "112.0")
    resultado = eleccion.elegir((amazon, local), C.levels.channel_tiebreak_pct)
    assert resultado == eleccion.Eleccion(Canal.AMAZON, Nivel.MUY_RECOMENDABLE, Canal.LOCAL)
    # Empate de nivel: el del canal elegido (design.md §10.6).
    local = _con_nivel(Canal.LOCAL, Nivel.RECOMENDABLE, "69.98", "112.0")
    assert eleccion.nivel_del_aviso((amazon, local), Canal.LOCAL) == (
        Nivel.RECOMENDABLE,
        Canal.LOCAL,
    )


def test_tipos_estrictos():
    with pytest.raises(TypeError):
        canales.CostoCompra(D(1), D(1), D(1), D(1), 1.0)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        eleccion.Eleccion("amazon", None, None)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        eleccion.Eleccion(Canal.AMAZON, None, None)


def test_sin_reloj_reproducible():
    """El mismo contexto da el mismo registro, byte a byte (RNF-3)."""
    contexto = _contexto()
    assert motor.evaluar(contexto).a_json() == motor.evaluar(contexto).a_json()
