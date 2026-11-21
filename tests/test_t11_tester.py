"""Pruebas independientes de oip-tester para T11 (evaluación por canal de punta a punta, B1).

Capacidad ``canales-y-margen``; REQ-2026-0001 v2.9 §3.2 pasos 2 y 6 a 9, §3.2.1 (estado de
cada canal y concurrencia S-31), §3.2.2 (``nivel_calculado``), §3.2.3 (marcas), §5
(configuración base, redondeo y escenario B1) y §13 S-05, S-25, S-30, S-31 y S-33; RN-001 v2,
RN-004 v2, RN-005 v2 §4, RN-006 v2, RN-007 v2 §4.1 y §4.2, RN-009 v2 §4.2 y §4.3, RN-016 v1,
RN-017 v1 y RN-018 v1 §4; design.md §3, §8, §10.3, §10.6 y §11 (RNF-9).

Escritas por adelantado (DEC-252) **sin ver la implementación**: solo con la interfaz del
commit e9e024d (firmas, tipos y docstrings) y las fuentes. Los datos y los resultados
esperados se copian del REQ y de las RN (precios, montos, porcentajes, niveles y canal), no
del código. Las pruebas de reglas que no son el escenario B1 (bordes de la tabla de §5, S-31,
S-33, RNF-9) no llevan marcador de escenario.

Fixtures sintéticos (DEC-194): comercios ficticios con subdominios de example.com; ninguna
prueba abre una URL. Instante explícito en ``America/Tijuana`` (PAR-01), sin reloj, sin red,
sin aleatoriedad y sin depender de la zona de la máquina.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import itertools
import logging
import re
import sys
import tokenize
from decimal import Decimal
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

import oip.dinero
from config_tienda_prueba import BASE, TIENDA_PRUEBA, con_tienda_prueba
from oip.catalogos import (
    CalidadPrecio,
    Canal,
    Categoria,
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
from oip.dinero import TipoMonto, formatear_porcentaje
from oip.entradas.contrato import leer_observacion
from oip.evaluacion import (
    canales,
    eleccion,
    identificacion,
    motor,
    referencias,
    rentabilidad,
)
from oip.evaluacion.canales import CanalEvaluado
from oip.evaluacion.contexto import (
    ContextoEvaluacion,
    EvaluacionCanal,
    ObservacionRegistrada,
)

RAIZ = Path(__file__).resolve().parent
SRC_EVALUACION = RAIZ.parent / "src" / "oip" / "evaluacion"
D = Decimal

# --- Configuración: la base de los escenarios + tienda-prueba + comercios sintéticos -------
# ``cx`` y ``cy`` son dos cadenas más (en B1, "Walmart" es ``cx``); la ficha de Amazon es el
# comercio ``amazon`` de la base (cadena ``amazon``), con URL sintética que nadie abre.
# ``tp-cv`` es la sucursal de la oferta ("Home Depot Chula Vista" de B1), de la cadena
# ``tienda-prueba``, con la tasa de prueba de REQ §5 (7.75%, ``taxLocation: tienda_prueba``).
_EXTRA_COMERCIOS = (
    "  cx: {chain: cadena-x, domains: [x.example.com], amazon_listing: false}\n"
    "  cy: {chain: cadena-y, domains: [y.example.com], amazon_listing: false}\n"
)
_EXTRA_SUCURSAL = "  tp-cv: {retailer: tienda-prueba}\n"
_DOMINIO = {
    TIENDA_PRUEBA: "tienda.example.com",
    "cx": "x.example.com",
    "cy": "y.example.com",
    "amazon": "amazon.example.com",
}


def _texto(*reemplazos: tuple[str, str]) -> str:
    texto = con_tienda_prueba(BASE.read_text(encoding="utf-8"))
    texto = texto.replace("\nretailers:\n", "\nretailers:\n" + _EXTRA_COMERCIOS, 1)
    assert texto.count("\nstores:\n") == 1
    texto = texto.replace("\nstores:\n", "\nstores:\n" + _EXTRA_SUCURSAL, 1)
    for viejo, nuevo in reemplazos:
        assert texto.count(viejo) == 1, viejo
        texto = texto.replace(viejo, nuevo)
    return texto


def _config(*reemplazos: tuple[str, str]):
    return cargar_configuracion_texto(_texto(*reemplazos), origen="t11-tester")


CONFIG = _config()
PARAMS = CONFIG.contenido
TIJUANA = ZoneInfo("America/Tijuana")
INSTANTE = dt.datetime(2026, 11, 16, 14, 0, tzinfo=TIJUANA)  # día 0 de B1
PRODUCTO = UUID(int=0x7110_0000)
PUB_OFERTA = UUID(int=0x7110_0001)
ID_OFERTA = UUID(int=0x7110_0002)
PUB_AMAZON = UUID(int=0x7110_0003)
PUB_CX = UUID(int=0x7110_0004)
PUB_CY = UUID(int=0x7110_0005)
GTIN_B1 = "012345678905"  # UPC-A con dígito verificador válido
MARCA_B1 = "MarcaS"
MODELO_B1 = "SC-11"
URL_OFERTA = "https://tienda.example.com/p/sierra-t11"
TITULO_OFERTA = "Sierra circular sintetica T11"

_ids = itertools.count(0x7110_1000)


def _uuid() -> UUID:
    return UUID(int=next(_ids))


def _hace(horas: float = 0, dias: int = 0) -> dt.datetime:
    return INSTANTE - dt.timedelta(days=dias, hours=horas)


def _cerca(valor: Decimal | None, esperado: Decimal) -> bool:
    """Igualdad de porcentajes sin redondear, tolerando solo el último dígito del contexto
    decimal (28 dígitos): distintas formas de dividir pueden diferir ahí."""
    assert isinstance(valor, Decimal), f"se esperaba Decimal, llegó {type(valor).__name__}"
    return abs(valor - esperado) < D("1e-20")


def _pct(valor: Decimal | None) -> str:
    assert isinstance(valor, Decimal)
    return formatear_porcentaje(valor)


# --- Constructores de observaciones -------------------------------------------------------


def _obs(
    precio: str,
    comercio: str,
    *,
    momento: dt.datetime,
    publicacion: UUID,
    ident: UUID | None = None,
    was: str | None = None,
    estado: str = "in_stock_confirmed",
    cantidad: int | None = None,
    modo: str = "envio",
    tienda: str | None = None,
    liquidacion: bool | None = False,
    seller: str = "comercio",
    peso: str | None = "4.0",
    tax_location: str | None = None,
    ficha: dict | None = None,
    marca: str = MARCA_B1,
    url: str | None = None,
    titulo: str = TITULO_OFERTA,
    extra: dict | None = None,
) -> ObservacionRegistrada:
    price: dict = {"current": precio, "currency": "USD"}
    if was is not None:
        price["was"] = was
    availability: dict = {"state": estado}
    if cantidad is not None:
        availability["quantity"] = cantidad
    datos: dict = {
        "retailerCode": comercio,
        "productUrl": url or f"https://{_DOMINIO[comercio]}/p/sierra-t11",
        "title": titulo,
        "brand": marca,
        "model": MODELO_B1,
        "gtin": GTIN_B1,
        "category": "tools",
        "condition": "new",
        "price": price,
        "seller": seller,
        "availability": availability,
        "purchaseMode": modo,
        "extractedAt": momento.isoformat(),
        "blocked": False,
    }
    if liquidacion is not None:
        datos["isClearance"] = liquidacion
    if peso is not None:
        datos["weightKg"] = peso
    if tienda is not None:
        datos["storeCode"] = tienda
    if tax_location is not None:
        datos["taxLocation"] = tax_location
    if ficha is not None:
        datos["amazonListing"] = ficha
    if extra:
        datos.update(extra)
    return ObservacionRegistrada(
        leer_observacion(datos),
        _uuid() if ident is None else ident,
        publicacion,
        PRODUCTO,
    )


def _oferta_b1(**cambios) -> ObservacionRegistrada:
    """B1: Home Depot Chula Vista (sucursal ``tp-cv``), liquidación, herramientas, 4 kg,
    código confirmado, vendida por el comercio, $29.00 con tachado $129.00, "3 disponibles"
    hace 2 h; tasa de la tienda 7.75% (REQ §5)."""
    argumentos = {
        "momento": _hace(2),
        "publicacion": PUB_OFERTA,
        "ident": ID_OFERTA,
        "was": "129.00",
        "estado": "in_stock",
        "cantidad": 3,
        "modo": "tienda",
        "tienda": "tp-cv",
        "liquidacion": True,
        "tax_location": "tienda_prueba",
        "url": URL_OFERTA,
    }
    argumentos.update(cambios)
    precio = argumentos.pop("precio", "29.00")
    return _obs(precio, TIENDA_PRUEBA, **argumentos)


def _ficha(
    momento: dt.datetime,
    *,
    buy_box: str | None = None,
    rank: int | None = 6000,
    vendedores: int | None = 5,
    comprados: int | None = 200,
) -> ObservacionRegistrada:
    ficha: dict = {"buyBoxPrice": buy_box}
    if rank is not None:
        ficha["rankMain"] = rank
    if vendedores is not None:
        ficha["sellersNew"] = vendedores
    if comprados is not None:
        ficha["boughtLastMonth"] = comprados
    return _obs(
        buy_box or "119.00",
        "amazon",
        momento=momento,
        publicacion=PUB_AMAZON,
        ficha=ficha,
    )


def _historial_b1() -> list[ObservacionRegistrada]:
    """Precio habitual $119 con 8 observaciones en 6 días y 60 días de historial; la tienda
    de la oferta no tiene historial propio; hoy Walmart (``cx``) $124 hace 8 h.

    Las 8 observaciones diarias (la de $109 es el botón de compra de Amazon, en las fichas):
    109, 119 × 6, 129 → mediana 119 (promedio de las dos centrales, 119 y 119)."""
    return [
        _obs("119.00", "cx", momento=_hace(dias=60), publicacion=PUB_CX),
        _obs("119.00", "cy", momento=_hace(dias=60), publicacion=PUB_CY),
        _obs("119.00", "cx", momento=_hace(dias=40), publicacion=PUB_CX),
        _obs("119.00", "cx", momento=_hace(dias=20), publicacion=PUB_CX),
        _obs("129.00", "cy", momento=_hace(dias=20), publicacion=PUB_CY),
        _obs("119.00", "cx", momento=_hace(dias=10), publicacion=PUB_CX),
        _obs("119.00", "cy", momento=_hace(dias=3), publicacion=PUB_CY),
        # Hoy: Walmart $124 (hace 8 h), disponible confirmada.
        _obs("124.00", "cx", momento=_hace(8), publicacion=PUB_CX),
    ]


def _fichas_b1(
    *,
    rank_hoy: int | None = 6000,
    rank_hace_30: int | None = 6000,
    vendedores: int | None = 5,
    comprados: int | None = 200,
) -> list[ObservacionRegistrada]:
    """Ficha de Amazon de B1: botón de compra hoy $119 (hace 2 h); mínimo de 60 días $109
    (botón de compra del día −50); ranking 6,000 (promedio de 7 días, días −6 a 0) y hace 30
    días 6,000 (días −36 a −30); 5 vendedores y 200 comprados el mes pasado en la ficha más
    reciente. Las fichas de ranking de días anteriores no traen botón de compra, para no
    agregar observaciones al precio habitual."""
    fichas = [_ficha(_hace(dias=50), buy_box="109.00", rank=None)]
    fichas += [_ficha(_hace(dias=d), rank=rank_hace_30) for d in range(36, 29, -1)]
    fichas += [_ficha(_hace(dias=d), rank=rank_hoy) for d in range(6, 0, -1)]
    fichas.append(
        _ficha(
            _hace(2),
            buy_box="119.00",
            rank=rank_hoy,
            vendedores=vendedores,
            comprados=comprados,
        )
    )
    return fichas


def _contexto(
    oferta: ObservacionRegistrada | None = None,
    historial=None,
    fichas=None,
    configuracion=CONFIG,
    **extra,
) -> ContextoEvaluacion:
    return ContextoEvaluacion(
        id_evaluacion=UUID(int=0x7110_00FF),
        instante=INSTANTE,
        configuracion=configuracion,
        id_version_configuracion=1,
        oferta=_oferta_b1() if oferta is None else oferta,
        historial=tuple(_historial_b1() if historial is None else historial),
        fichas_amazon=tuple(_fichas_b1() if fichas is None else fichas),
        **extra,
    )


def _canal(registro, canal: Canal) -> EvaluacionCanal:
    encontrados = [c for c in registro.canales if c.canal is canal]
    assert len(encontrados) == 1, f"se esperaba un canal {canal}: {registro.canales!r}"
    return encontrados[0]


#: Descuento real de B1 sin redondear: (119 − 29) ÷ 119 × 100 = 75.6302…
REAL_B1 = (D("119") - D("29")) / D("119") * 100


# --- Insumos de B1 por canal (REQ §5 B1), para las pruebas de rentabilidad y elección ----


def _insumos_amazon_b1(**cambios) -> CanalEvaluado:
    valores = {
        "canal": Canal.AMAZON,
        "estado": EstadoCanal.DISPONIBLE,
        "causas_cerrado": (),
        "causas_por_revisar": (),
        "precio_venta": D("119.00"),
        "costo_venta": D("33.85"),
        "tasa_devolucion_pct": D("7"),
        "perdida_devolucion_pct": D("50"),
        "ventas_al_mes": 33,
        "dias_tabla": 7,
        "dias_por_unidad": None,
        "dias_pago": 30,
        "disponibles": 3,
        "limite_cliente": None,
        "ranking": D("6000"),
        "baja_por_competencia": False,
        "marcas": (Marca.MARGEN_ESTIMADO.value, Marca.EMPAQUE_POR_CONFIRMAR.value),
    }
    valores.update(cambios)
    return CanalEvaluado(**valores)


def _insumos_local_b1(**cambios) -> CanalEvaluado:
    valores = {
        "canal": Canal.LOCAL,
        "estado": EstadoCanal.DISPONIBLE,
        "causas_cerrado": (),
        "causas_por_revisar": (),
        "precio_venta": D("91.04"),
        "costo_venta": D("9.50"),
        "tasa_devolucion_pct": D("0"),
        "perdida_devolucion_pct": D("100"),
        "ventas_al_mes": 2,
        "dias_tabla": None,
        "dias_por_unidad": 14,
        "dias_pago": 0,
        "disponibles": 3,
        "limite_cliente": None,
        "ranking": D("6000"),
        "baja_por_competencia": False,
        "marcas": (Marca.SIN_COMPARABLES_LOCALES.value,),
    }
    valores.update(cambios)
    return CanalEvaluado(**valores)


def _canal_con_margenes_amazon_b1(**cambios) -> EvaluacionCanal:
    valores = {
        "canal": Canal.AMAZON,
        "estado": EstadoCanal.DISPONIBLE,
        "precio_venta": D("119.00"),
        "costo_venta": D("33.85"),
        "margen_neto": D("53.90"),
        "margen_neto_pct": D("172.48"),
        "costo_devoluciones": D("4.17"),
        "castigo": D("5.00"),
        "margen_ajustado": D("44.73"),
        "margen_ajustado_pct": D("143.136"),
        "marcas": (Marca.MARGEN_ESTIMADO.value, Marca.EMPAQUE_POR_CONFIRMAR.value),
    }
    valores.update(cambios)
    return EvaluacionCanal(**valores)


def _canal_con_margenes_local_b1(**cambios) -> EvaluacionCanal:
    valores = {
        "canal": Canal.LOCAL,
        "estado": EstadoCanal.DISPONIBLE,
        "precio_venta": D("91.04"),
        "costo_venta": D("9.50"),
        "margen_neto": D("50.29"),
        "margen_neto_pct": D("160.928"),
        "costo_devoluciones": D("0.00"),
        "castigo": D("0.00"),
        "margen_ajustado": D("50.29"),
        "margen_ajustado_pct": D("160.928"),
        "marcas": (Marca.SIN_COMPARABLES_LOCALES.value,),
    }
    valores.update(cambios)
    return EvaluacionCanal(**valores)


def _canal_final(
    canal: Canal,
    *,
    estado: EstadoCanal = EstadoCanal.DISPONIBLE,
    nivel: Nivel | None,
    nivel_calculado: Nivel | None = None,
    ganancia: str | None,
    rendimiento: str | None,
) -> EvaluacionCanal:
    """Canal con nivel, ganancia total y rendimiento, para la elección (RN-018) y el nivel
    del aviso (S-33)."""
    return EvaluacionCanal(
        canal=canal,
        estado=estado,
        nivel=nivel,
        nivel_calculado=nivel if nivel_calculado is None else nivel_calculado,
        ganancia_total=None if ganancia is None else D(ganancia),
        rendimiento_mensual_pct=None if rendimiento is None else D(rendimiento),
    )


# =========================================================================================
# B1 de punta a punta, por el motor (REQ §5 B1)
# =========================================================================================


@pytest.fixture(scope="module")
def registro_b1():
    return motor.evaluar(_contexto())


@pytest.mark.scenario("B1")
def test_b1_confianza_alta(registro_b1):
    # Confianza Alta (cantidad exacta en liquidación, 2 h ≤ 3 h).
    assert registro_b1.confianza is Confianza.ALTA


@pytest.mark.scenario("B1")
def test_b1_descuento_referencias_y_calidad(registro_b1):
    r = registro_b1
    # Anunciado 77.5%, real 75.6% (sigue). Marca DESCUENTO ANUNCIADO NO COMPROBADO.
    assert _pct(r.descuento_anunciado) == "77.5 %"
    assert _cerca(r.descuento_real, REAL_B1)
    assert _pct(r.descuento_real) == "75.6 %"
    assert Marca.DESCUENTO_ANUNCIADO_NO_COMPROBADO.value in r.marcas
    # Precio habitual $119; mercado hoy $119; mínimo de 60 días en Amazon $109; venta
    # esperada en Amazon = botón de compra $119.
    assert r.referencias is not None
    assert r.referencias.precio_habitual == D("119")
    assert r.referencias.precio_mercado_hoy == D("119")
    assert r.referencias.minimo_60_dias_amazon == D("109")
    assert r.referencias.precio_venta_amazon == D("119")
    # Competencia más barata: no (119 ≥ 101.15). Calidad Buena oferta.
    todas = set(r.marcas).union(*(c.marcas for c in r.canales))
    assert Marca.COMPETENCIA_MAS_BARATA.value not in todas
    assert r.calidad_precio is CalidadPrecio.BUENA_OFERTA


@pytest.mark.scenario("B1")
def test_b1_costo_de_compra(registro_b1):
    # Compra: impuesto $2.25 → $31.25.
    assert registro_b1.costo_compra == D("31.25")


@pytest.mark.scenario("B1")
def test_b1_canal_amazon(registro_b1):
    a = _canal(registro_b1, Canal.AMAZON)
    assert a.estado is EstadoCanal.DISPONIBLE
    assert a.causas_cerrado == () and a.causas_por_revisar == ()
    # Comisión $17.85, envío $14, empaque $2 → costo de venta $33.85.
    assert a.precio_venta == D("119.00")
    assert a.costo_venta == D("33.85")
    # Neto $53.90 (172.5%).
    assert a.margen_neto == D("53.90")
    assert _cerca(a.margen_neto_pct, D("172.48"))
    assert _pct(a.margen_neto_pct) == "172.5 %"
    # Devoluciones $4.17, castigo $5.00 → ajustado $44.73 (143.1%).
    assert a.costo_devoluciones == D("4.17")
    assert a.castigo == D("5.00")
    assert a.margen_ajustado == D("44.73")
    assert _cerca(a.margen_ajustado_pct, D("143.136"))
    assert _pct(a.margen_ajustado_pct) == "143.1 %"
    # Unidades mín(200 ÷ 6 = 33, 3 disponibles, tope 5) = 3; días 7 + 30 = 37.
    assert a.unidades == 3
    assert a.dias_para_recuperar == 37
    # Rendimiento 116.1%.
    assert _cerca(a.rendimiento_mensual_pct, D("143.136") * 30 / 37)
    assert _pct(a.rendimiento_mensual_pct) == "116.1 %"
    # Nivel Muy recomendable; ganancia total $134.19.
    assert a.nivel is Nivel.MUY_RECOMENDABLE
    assert a.nivel_calculado is Nivel.MUY_RECOMENDABLE
    assert a.ganancia_total == D("134.19")


@pytest.mark.scenario("B1")
def test_b1_canal_venta_local(registro_b1):
    loc = _canal(registro_b1, Canal.LOCAL)
    assert loc.estado is EstadoCanal.DISPONIBLE
    assert loc.causas_cerrado == () and loc.causas_por_revisar == ()
    # 119 × 85% = $101.15 → × 0.90 = $91.04.
    assert loc.precio_venta == D("91.04")
    # Neto $50.29 (160.9%) (entrega $9.50, REQ §5).
    assert loc.margen_neto == D("50.29")
    assert _cerca(loc.margen_neto_pct, D("160.928"))
    assert _pct(loc.margen_neto_pct) == "160.9 %"
    # Castigo $0 (91.04 < 109); devolución local 0% → ajustado = neto.
    assert loc.castigo == D("0")
    assert loc.costo_devoluciones in (None, D("0"))
    assert loc.margen_ajustado == D("50.29")
    assert _cerca(loc.margen_ajustado_pct, D("160.928"))
    # Unidades 2; días 30; rendimiento 160.9%.
    assert loc.unidades == 2
    assert loc.dias_para_recuperar == 30
    assert _cerca(loc.rendimiento_mensual_pct, D("160.928"))
    assert _pct(loc.rendimiento_mensual_pct) == "160.9 %"
    # Muy recomendable; total $100.58. Marca SIN COMPARABLES LOCALES.
    assert loc.nivel is Nivel.MUY_RECOMENDABLE
    assert loc.nivel_calculado is Nivel.MUY_RECOMENDABLE
    assert loc.ganancia_total == D("100.58")
    assert Marca.SIN_COMPARABLES_LOCALES.value in set(loc.marcas) | set(registro_b1.marcas)


@pytest.mark.scenario("B1")
def test_b1_eleccion_nivel_del_aviso_y_resultado(registro_b1):
    r = registro_b1
    # Diferencia (134.19 − 100.58) ÷ 134.19 = 25.0% → Amazon.
    diferencia = (D("134.19") - D("100.58")) / D("134.19") * 100
    assert formatear_porcentaje(diferencia) == "25.0 %"
    assert r.canal_elegido is Canal.AMAZON
    # Resultado NIVEL_ASIGNADO = Muy recomendable, Amazon (S-33: con empate de nivel, el del
    # canal elegido, design.md §10.6).
    assert r.resultado is Resultado.NIVEL_ASIGNADO
    assert r.motivos == ()
    assert r.motivo_principal is None
    assert r.nivel_aviso is Nivel.MUY_RECOMENDABLE
    assert r.canal_aviso is Canal.AMAZON


@pytest.mark.scenario("B1")
def test_b1_sin_marcas_que_el_escenario_no_da(registro_b1):
    """B1 no tiene competencia más barata, demanda a la baja, precio inflado, confianza baja,
    falta de oferta hoy ni datos estimados (peso, unidades, devolución)."""
    todas = set(registro_b1.marcas).union(*(c.marcas for c in registro_b1.canales))
    for marca in (
        Marca.COMPETENCIA_MAS_BARATA,
        Marca.DEMANDA_A_LA_BAJA,
        Marca.PRECIO_ANTES_INFLADO,
        Marca.CONFIANZA_BAJA,
        Marca.SIN_OFERTA_HOY,
        Marca.MATERIAL_PELIGROSO,
    ):
        assert marca.value not in todas
    assert not [m for m in todas if m.startswith(Marca.ESTIMADO.value + " (")]


# =========================================================================================
# B1 por componentes (REQ §5 B1): cada número con su función de la interfaz
# =========================================================================================


@pytest.mark.scenario("B1")
def test_b1_referencias_de_amazon():
    contexto = _contexto()
    assert referencias.minimo_60_dias_amazon(contexto) == D("109")
    assert referencias.precio_venta_amazon(contexto) == D("119")
    refs = referencias.calcular_referencias(contexto)
    assert refs.minimo_60_dias_amazon == D("109")
    assert refs.precio_venta_amazon == D("119")
    assert refs.precio_habitual == D("119")
    assert refs.precio_mercado_hoy == D("119")


@pytest.mark.scenario("B1")
def test_b1_confianza_por_componentes():
    oferta = _oferta_b1().observacion
    assert identificacion.es_tienda_fisica(oferta) is True
    assert identificacion.antiguedad_horas(INSTANTE, oferta.extracted_at) == D("2")
    conf = identificacion.confianza_disponibilidad(oferta, INSTANTE, PARAMS.levels.confidence)
    assert conf is Confianza.ALTA
    assert identificacion.confianza_permite_nivel(oferta, conf) is True


@pytest.mark.scenario("B1")
def test_b1_costo_de_compra_por_componentes():
    oferta = _oferta_b1().observacion
    assert canales.tasa_impuesto(oferta, PARAMS.taxes) == D("7.75")
    costo = canales.costo_compra(oferta, PARAMS)
    assert costo is not None
    # 29 × 7.75% = 2.2475 → $2.25; compra $31.25 (envío hacia mí $0).
    assert costo.precio == D("29.00")
    assert costo.tasa_impuesto_pct == D("7.75")
    assert costo.impuesto == D("2.25")
    assert costo.envio_hacia_mi == D("0")
    assert costo.total == D("31.25")


@pytest.mark.scenario("B1")
def test_b1_ranking_y_demanda():
    contexto = _contexto()
    ranking = canales.ranking_amazon(contexto)
    # Ranking 6,000 (promedio de 7 días; hace 30 días 6,000).
    assert ranking.promedio == D("6000")
    assert ranking.dias_con_datos == 7
    assert ranking.promedio_hace_30_dias == D("6000")
    ficha = canales.ficha_vigente(contexto)
    assert ficha is not None
    assert ficha.sellers_new == 5 and ficha.bought_last_month == 200
    demanda = canales.demanda_en_amazon(Categoria.TOOLS, ranking, ficha, PARAMS)
    # Demanda SUFICIENTE (6,000 ≤ 168,440 y 5 vendedores ≤ 20); sin empeoramiento.
    assert demanda.demanda is DemandaAmazon.SUFICIENTE
    assert demanda.a_la_baja is False
    assert demanda.empeoramiento_pct is not None and demanda.empeoramiento_pct == 0
    # 200 ÷ (5 + 1) = 33.3 → 33 ventas al mes para Jesús.
    assert canales.ventas_al_mes_amazon(ficha) == 33


@pytest.mark.scenario("B1")
def test_b1_comision_envio_devolucion_y_competencia():
    comision = PARAMS.categories["tools"].commission
    # Comisión 119 × 15% = $17.85.
    assert canales.comision_amazon(D("119.00"), comision) == D("17.85")
    # 4 kg → envío $14 y empaque $2.
    envio = canales.envio_amazon(_oferta_b1().observacion, PARAMS.shipping)
    assert envio is not None
    assert (envio.envio, envio.empaque, envio.peso_estimado) == (D("14.00"), D("2.00"), False)
    # Devolución en Amazon de herramientas: 7%, pérdida 50%, propia.
    tasa = canales.tasa_devolucion_amazon(Categoria.TOOLS, PARAMS)
    assert tasa is not None
    assert (tasa.tasa_pct, tasa.perdida_pct, tasa.estimada) == (D("7"), D("50"), False)
    # Competencia más barata: no (mercado hoy 119 ≥ 119 × 85% = 101.15).
    assert canales.competencia_mas_barata(D("119"), D("119"), D("15")) is False
    # Sin restricción ni material peligroso.
    oferta = _oferta_b1().observacion
    assert canales.restringido_en_amazon(oferta, PARAMS, INSTANTE.date()) is False
    assert canales.material_peligroso(oferta, PARAMS.lists) is False


@pytest.mark.scenario("B1")
def test_b1_evaluar_amazon():
    contexto = _contexto()
    refs = referencias.calcular_referencias(contexto)
    costo = canales.costo_compra(contexto.oferta.observacion, PARAMS)
    a = canales.evaluar_amazon(contexto, refs, costo)
    assert a.canal is Canal.AMAZON
    assert a.estado is EstadoCanal.DISPONIBLE
    assert a.causas_cerrado == () and a.causas_por_revisar == ()
    assert a.precio_venta == D("119.00")
    assert a.costo_venta == D("33.85")  # 17.85 + 14 + 2 (+ otros costos $0)
    assert (a.tasa_devolucion_pct, a.perdida_devolucion_pct) == (D("7"), D("50"))
    assert a.ventas_al_mes == 33
    assert a.dias_tabla == 7  # ranking < 10,000
    assert a.dias_pago == 30  # cuenta nueva
    assert a.disponibles == 3
    assert a.limite_cliente is None
    assert a.ranking == D("6000")
    assert a.baja_por_competencia is False
    assert Marca.MARGEN_ESTIMADO.value in a.marcas
    assert Marca.EMPAQUE_POR_CONFIRMAR.value in a.marcas


@pytest.mark.scenario("B1")
def test_b1_venta_local_por_componentes():
    contexto = _contexto()
    precio = canales.precio_venta_local(contexto, D("119"))
    # 119 × 85% × 90% = 91.035 → $91.04; sin comparables, sin techo.
    assert precio is not None
    assert precio.precio == D("91.04")
    assert precio.techo is None
    # Demanda media (la inicial de herramientas) → 14 días por unidad → 2 ventas al mes.
    demanda = canales.demanda_local(contexto)
    assert demanda is DemandaLocal.MEDIUM
    assert canales.dias_por_unidad_local(demanda, PARAMS.local_sale.demand) == 14
    assert canales.ventas_al_mes_local(demanda, PARAMS.local_sale.demand) == 2
    # Entrega 10 km y 0.5 h = $9.50.
    assert canales.costo_entrega(PARAMS.local_sale.transport) == D("9.50")


@pytest.mark.scenario("B1")
def test_b1_evaluar_local():
    contexto = _contexto()
    refs = referencias.calcular_referencias(contexto)
    costo = canales.costo_compra(contexto.oferta.observacion, PARAMS)
    loc = canales.evaluar_local(contexto, refs, costo)
    assert loc.canal is Canal.LOCAL
    assert loc.estado is EstadoCanal.DISPONIBLE
    assert loc.causas_cerrado == () and loc.causas_por_revisar == ()
    assert loc.precio_venta == D("91.04")
    assert loc.costo_venta == D("9.50")  # la entrega es el costo de venta local
    assert loc.tasa_devolucion_pct == D("0")
    assert loc.ventas_al_mes == 2
    assert loc.dias_por_unidad == 14
    assert loc.dias_pago == 0
    assert loc.disponibles == 3
    assert loc.ranking == D("6000")  # el mismo ranking decide el tope (DEC-206)
    assert loc.baja_por_competencia is False
    assert Marca.SIN_COMPARABLES_LOCALES.value in loc.marcas
    # RNF-9: las marcas de Amazon no van en la venta local.
    assert Marca.MARGEN_ESTIMADO.value not in loc.marcas
    assert Marca.EMPAQUE_POR_CONFIRMAR.value not in loc.marcas


@pytest.mark.scenario("B1")
def test_b1_formulas_de_margen():
    # Amazon: neto 119 − 31.25 − 33.85 = $53.90 (172.5%).
    assert rentabilidad.margen_neto(D("119.00"), D("31.25"), D("33.85")) == D("53.90")
    assert _cerca(rentabilidad.porcentaje_sobre_compra(D("53.90"), D("31.25")), D("172.48"))
    # Devoluciones 119 × 7% × 50% = 4.165 → $4.17.
    assert rentabilidad.costo_devoluciones(D("119.00"), D("7"), D("50")) == D("4.17")
    castigo = PARAMS.amazon.drop_penalty
    # Castigo (119 − 109) × 50% = $5.00; local (91.04 − 109) < 0 → $0.
    assert rentabilidad.castigo_por_baja(D("119.00"), D("109"), castigo) == D("5.00")
    assert rentabilidad.castigo_por_baja(D("91.04"), D("109"), castigo) == D("0")
    # Ajustado 53.90 − 4.17 − 5.00 = $44.73 (143.1%).
    assert rentabilidad.margen_ajustado(D("53.90"), D("4.17"), D("5.00")) == D("44.73")
    assert _cerca(rentabilidad.porcentaje_sobre_compra(D("44.73"), D("31.25")), D("143.136"))
    # Local: neto 91.04 − 31.25 − 9.50 = $50.29 (160.9%).
    assert rentabilidad.margen_neto(D("91.04"), D("31.25"), D("9.50")) == D("50.29")


@pytest.mark.scenario("B1")
def test_b1_calcular_margenes_por_canal():
    castigo = PARAMS.amazon.drop_penalty
    a = rentabilidad.calcular_margenes(_insumos_amazon_b1(), D("31.25"), D("109"), castigo)
    assert a is not None
    assert a.margen_neto == D("53.90")
    assert _cerca(a.margen_neto_pct, D("172.48"))
    assert a.costo_devoluciones == D("4.17")
    assert a.castigo == D("5.00")
    assert a.margen_ajustado == D("44.73")
    assert _cerca(a.margen_ajustado_pct, D("143.136"))
    loc = rentabilidad.calcular_margenes(_insumos_local_b1(), D("31.25"), D("109"), castigo)
    assert loc is not None
    assert loc.margen_neto == D("50.29")
    assert loc.costo_devoluciones == D("0")
    assert loc.castigo == D("0")
    assert loc.margen_ajustado == D("50.29")
    assert _cerca(loc.margen_ajustado_pct, D("160.928"))


@pytest.mark.scenario("B1")
def test_b1_nivel_tope_unidades_dias_y_rendimiento():
    umbrales = PARAMS.levels.thresholds
    # Mínimo por unidad mayor(10, 10% × 31.25 = 3.125) = $10.
    assert rentabilidad.minimo_por_unidad(D("31.25"), PARAMS.levels.min_per_unit) == D("10")
    # Real 75.6% y ajustado 143.1% → Muy recomendable (Comprar ya exige 80% de real).
    assert rentabilidad.nivel_por_umbrales(REAL_B1, D("143.136"), umbrales) is (
        Nivel.MUY_RECOMENDABLE
    )
    margenes = rentabilidad.Margenes(
        D("53.90"), D("172.48"), D("4.17"), D("5.00"), D("44.73"), D("143.136")
    )
    assert (
        rentabilidad.nivel_calculado(REAL_B1, margenes, D("31.25"), PARAMS, False)
        is Nivel.MUY_RECOMENDABLE
    )
    # Tope 5 (ranking 6,000 < 10,000 y Muy recomendable).
    tope = PARAMS.amazon.first_purchase_cap
    assert rentabilidad.tope_primera_compra(D("6000"), Nivel.MUY_RECOMENDABLE, tope) == 5
    # Amazon: mín(33, 3, tope 5) = 3; local: mín(2, 3, 5) = 2.
    assert rentabilidad.unidades_recomendadas(33, 3, None, 5, 2) == 3
    assert rentabilidad.unidades_recomendadas(2, 3, None, 5, 2) == 2
    # Días: Amazon 7 + 30 = 37; local mayor(14 × 2, 2 ÷ (2 ÷ 30)) = 30 + 0 = 30.
    assert rentabilidad.dias_para_recuperar(3, 33, 7, None, 30) == 37
    assert rentabilidad.dias_para_recuperar(2, 2, None, 14, 0) == 30
    # Rendimiento: 143.1% × 30 ÷ 37 = 116.1%; local 160.9% × 30 ÷ 30 = 160.9%.
    rend_a = rentabilidad.rendimiento_mensual(D("143.136"), 37)
    assert _cerca(rend_a, D("143.136") * 30 / 37) and _pct(rend_a) == "116.1 %"
    assert _cerca(rentabilidad.rendimiento_mensual(D("160.928"), 30), D("160.928"))
    # Ganancia total: 44.73 × 3 = $134.19; 50.29 × 2 = $100.58.
    assert rentabilidad.ganancia_total(D("44.73"), 3) == D("134.19")
    assert rentabilidad.ganancia_total(D("50.29"), 2) == D("100.58")


@pytest.mark.scenario("B1")
def test_b1_pasos_de_rentabilidad_del_motor():
    """``asignar_nivel`` y después ``calcular_unidades`` (design.md §3: nivel antes que las
    unidades) sobre los números de B1."""
    a = rentabilidad.asignar_nivel(
        _canal_con_margenes_amazon_b1(),
        _insumos_amazon_b1(),
        descuento_real=REAL_B1,
        costo_compra=D("31.25"),
        confianza_ok=True,
        configuracion=PARAMS,
    )
    assert isinstance(a, EvaluacionCanal)
    assert a.nivel is Nivel.MUY_RECOMENDABLE
    assert a.nivel_calculado is Nivel.MUY_RECOMENDABLE
    a = rentabilidad.calcular_unidades(
        a, _insumos_amazon_b1(), descuento_real=REAL_B1, configuracion=PARAMS
    )
    assert (a.unidades, a.dias_para_recuperar, a.ganancia_total) == (3, 37, D("134.19"))
    assert _pct(a.rendimiento_mensual_pct) == "116.1 %"
    # Los márgenes no cambian en estos pasos.
    assert a.margen_ajustado == D("44.73") and a.margen_neto == D("53.90")

    loc = rentabilidad.asignar_nivel(
        _canal_con_margenes_local_b1(),
        _insumos_local_b1(),
        descuento_real=REAL_B1,
        costo_compra=D("31.25"),
        confianza_ok=True,
        configuracion=PARAMS,
    )
    assert loc.nivel is Nivel.MUY_RECOMENDABLE
    loc = rentabilidad.calcular_unidades(
        loc, _insumos_local_b1(), descuento_real=REAL_B1, configuracion=PARAMS
    )
    assert (loc.unidades, loc.dias_para_recuperar, loc.ganancia_total) == (2, 30, D("100.58"))
    assert _pct(loc.rendimiento_mensual_pct) == "160.9 %"


@pytest.mark.scenario("B1")
def test_b1_eleccion_por_componentes():
    a = _canal_final(
        Canal.AMAZON,
        nivel=Nivel.MUY_RECOMENDABLE,
        ganancia="134.19",
        rendimiento=str(D("143.136") * 30 / 37),
    )
    loc = _canal_final(
        Canal.LOCAL, nivel=Nivel.MUY_RECOMENDABLE, ganancia="100.58", rendimiento="160.928"
    )
    assert eleccion.canal_elegido((a, loc), D("10")) is Canal.AMAZON
    assert eleccion.nivel_del_aviso((a, loc), Canal.AMAZON) == (
        Nivel.MUY_RECOMENDABLE,
        Canal.AMAZON,
    )
    resultado = eleccion.elegir((a, loc), D("10"))
    assert resultado == eleccion.Eleccion(Canal.AMAZON, Nivel.MUY_RECOMENDABLE, Canal.AMAZON)


# =========================================================================================
# Confianza de la disponibilidad (RN-007 v2 §4.1 y §4.2; S-25) — ejemplos de la RN y bordes
# =========================================================================================


def _confianza(**cambios) -> Confianza | None:
    oferta = _oferta_b1(**cambios).observacion
    return identificacion.confianza_disponibilidad(oferta, INSTANTE, PARAMS.levels.confidence)


@pytest.mark.parametrize(
    ("cambios", "esperada"),
    [
        # Ejemplo A: "3 disponibles" hace 2 h (normal) → Alta.
        ({"liquidacion": False}, Confianza.ALTA),
        # Ejemplo B: el mismo dato 8 h después → Media.
        ({"liquidacion": False, "momento": _hace(8)}, Confianza.MEDIA),
        # Normal: Alta hasta 6 h (incluido), Media hasta 24 h (incluido), después Baja.
        ({"liquidacion": False, "momento": _hace(6)}, Confianza.ALTA),
        ({"liquidacion": False, "momento": _hace(24)}, Confianza.MEDIA),
        ({"liquidacion": False, "momento": _hace(24.5)}, Confianza.BAJA),
        # Ejemplo C: liquidación, "5 disponibles" hace 4 h → Media (la Alta dura 3 h).
        ({"cantidad": 5, "momento": _hace(4)}, Confianza.MEDIA),
        # Liquidación: Alta hasta 3 h (incluido), Media hasta 12 h, después Baja.
        ({"momento": _hace(3)}, Confianza.ALTA),
        ({"momento": _hace(12)}, Confianza.MEDIA),
        ({"momento": _hace(12.5)}, Confianza.BAJA),
        # "En existencia" sin número: normal Media hasta 12 h, después Baja; liquidación 6 h.
        ({"liquidacion": False, "cantidad": None, "momento": _hace(12)}, Confianza.MEDIA),
        ({"liquidacion": False, "cantidad": None, "momento": _hace(13)}, Confianza.BAJA),
        ({"cantidad": None, "momento": _hace(6)}, Confianza.MEDIA),
        ({"cantidad": None, "momento": _hace(7)}, Confianza.BAJA),
        # Ejemplo D: "existencia limitada" hace 1 h → Media; hace 3 h → Baja (2 h, igual en
        # liquidación).
        ({"estado": "limited_stock", "cantidad": None, "momento": _hace(1)}, Confianza.MEDIA),
        ({"estado": "limited_stock", "cantidad": None, "momento": _hace(2)}, Confianza.MEDIA),
        ({"estado": "limited_stock", "cantidad": None, "momento": _hace(3)}, Confianza.BAJA),
        # Agotado → Baja.
        ({"estado": "out_of_stock", "cantidad": None}, Confianza.BAJA),
    ],
)
def test_confianza_en_tienda_fisica(cambios, esperada):
    assert _confianza(**cambios) is esperada


def test_confianza_sin_dato_de_liquidacion_usa_las_ventanas_normales():
    """RN-007 §11 (interfaz): ``isClearance`` ausente = ventanas normales (5 h → Alta)."""
    assert _confianza(liquidacion=None, momento=_hace(5)) is Confianza.ALTA


@pytest.mark.parametrize("modo", ["envio", "recoleccion"])
def test_confianza_en_linea_y_recoger_disponible_confirmada_es_alta(modo):
    """RN-007 §4.2 y S-25: "disponible confirmada" cuenta como Alta, aunque sea vieja."""
    conf = _confianza(
        modo=modo,
        estado="in_stock_confirmed",
        cantidad=None,
        liquidacion=False,
        momento=_hace(30),
    )
    assert conf is Confianza.ALTA
    oferta = _oferta_b1(modo=modo, estado="in_stock_confirmed", cantidad=None).observacion
    assert identificacion.es_tienda_fisica(oferta) is False


@pytest.mark.parametrize("estado", ["limited_stock", "unconfirmed", "out_of_stock"])
def test_confianza_en_linea_otro_estado_no_tiene_confianza(estado):
    """Interfaz de CMP-10 (RN-007 §4.2 solo dice que no cuentan como disponibles)."""
    assert _confianza(modo="envio", estado=estado, cantidad=None) is None


def test_confianza_permite_nivel():
    tienda = _oferta_b1().observacion
    en_linea = _oferta_b1(modo="envio", estado="in_stock_confirmed").observacion
    # RN-009 §4.2: en tienda física, Alta o Media; Baja no.
    assert identificacion.confianza_permite_nivel(tienda, Confianza.ALTA) is True
    assert identificacion.confianza_permite_nivel(tienda, Confianza.MEDIA) is True
    assert identificacion.confianza_permite_nivel(tienda, Confianza.BAJA) is False
    # En las demás compras la confianza no es requisito.
    assert identificacion.confianza_permite_nivel(en_linea, None) is True
    assert identificacion.confianza_permite_nivel(en_linea, Confianza.ALTA) is True


def test_antiguedad_horas_exacta_y_sin_float():
    horas = identificacion.antiguedad_horas(INSTANTE, INSTANTE - dt.timedelta(minutes=90))
    assert isinstance(horas, Decimal) and horas == D("1.5")
    assert identificacion.antiguedad_horas(INSTANTE, INSTANTE) == 0
    # Misma hora en otra zona: la antigüedad no depende de la zona.
    utc = (INSTANTE - dt.timedelta(hours=2)).astimezone(dt.UTC)
    assert identificacion.antiguedad_horas(INSTANTE, utc) == D("2")


def test_antiguedad_horas_rechaza_dato_futuro_o_sin_desfase():
    with pytest.raises(ValueError):
        identificacion.antiguedad_horas(INSTANTE, INSTANTE + dt.timedelta(minutes=1))
    with pytest.raises((ValueError, TypeError)):
        identificacion.antiguedad_horas(INSTANTE, dt.datetime(2026, 11, 16, 12, 0))  # noqa: DTZ001


def test_confianza_de_un_particular_no_existe():
    particular = leer_observacion(
        {
            "retailerCode": "particular",
            "productUrl": "https://offerup.example.com/item/detail/t11",
            "title": "MarcaS SC-11",
            "brand": MARCA_B1,
            "model": MODELO_B1,
            "category": "tools",
            "condition": "used",
            "price": {"current": "70.00", "currency": "USD"},
            "seller": "particular",
            "availability": {"state": "listed"},
            "purchaseMode": "particular",
            "pickupLocation": "san_diego",
            "extractedAt": _hace(2).isoformat(),
            "blocked": False,
        }
    )
    conf = identificacion.confianza_disponibilidad(particular, INSTANTE, PARAMS.levels.confidence)
    assert conf is None
    # S-14: la compra a un particular no lleva impuesto.
    assert canales.tasa_impuesto(particular, PARAMS.taxes) == 0


# =========================================================================================
# Costo de compra, comisión, envío y competencia (REQ §5, RN-001, RN-006; DEC-217, DEC-220)
# =========================================================================================


@pytest.mark.parametrize("tax_location", [None, "ubicacion_sin_cargar"])
def test_impuesto_de_respaldo_sin_ubicacion_cargada(tax_location):
    """DEC-220: sin ubicación cargada (ausente o fuera de la tabla), 7.75% de respaldo."""
    oferta = _oferta_b1(tax_location=tax_location).observacion
    assert canales.tasa_impuesto(oferta, PARAMS.taxes) == D("7.75")
    costo = canales.costo_compra(oferta, PARAMS)
    assert costo is not None and costo.total == D("31.25")


def test_respaldo_sale_de_la_configuracion_no_del_codigo():
    config = _config(("  fallback_rate_pct: 7.75\n", "  fallback_rate_pct: 10\n"))
    oferta = _oferta_b1(tax_location=None).observacion
    assert canales.tasa_impuesto(oferta, config.contenido.taxes) == D("10")
    costo = canales.costo_compra(oferta, config.contenido)
    # 29 × 10% = $2.90 → $31.90.
    assert costo is not None and (costo.impuesto, costo.total) == (D("2.90"), D("31.90"))


def test_costo_de_compra_suma_el_envio_hacia_mi_del_contrato():
    oferta = _oferta_b1(extra={"shipping": {"toMeCost": "5.00"}}).observacion
    costo = canales.costo_compra(oferta, PARAMS)
    assert costo is not None
    assert costo.envio_hacia_mi == D("5.00")
    assert costo.total == D("36.25")  # 29 + 2.25 + 5


def test_costo_de_compra_envio_vacio_es_el_de_la_configuracion():
    """Vacío = ausente: ``shipping`` sin ``toMeCost`` usa ``shipping_to_me_default`` ($0)."""
    oferta = _oferta_b1(extra={"shipping": {}}).observacion
    costo = canales.costo_compra(oferta, PARAMS)
    assert costo is not None and costo.envio_hacia_mi == 0 and costo.total == D("31.25")


@pytest.mark.parametrize(
    ("categoria", "precio", "esperada"),
    [
        ("tools", "1.00", "0.30"),  # 15% = 0.15 → mínimo $0.30 por unidad
        ("tools", "2.00", "0.30"),  # 0.30 exacto
        ("tools", "2.03", "0.30"),  # 0.3045 → 0.30
        ("tools", "2.10", "0.32"),  # 0.315 → 0.32 (medio centavo arriba)
        ("beauty", "10.00", "0.80"),  # "8% del total si es de $10 o menos"
        ("beauty", "10.01", "1.50"),  # 15% del total: 1.5015 → 1.50
        ("beauty", "88.00", "13.20"),
        ("watches", "1500.00", "240.00"),  # 16% de la parte hasta $1,500
        ("watches", "2000.00", "255.00"),  # 240 + 3% × 500
        ("jewelry", "300.00", "52.50"),  # 20% × 250 + 5% × 50
    ],
)
def test_comision_flat_umbral_y_tramos(categoria, precio, esperada):
    """REQ §5 (tabla por categoría y "Comisiones con umbral y por tramos"); DEC-217."""
    comision = PARAMS.categories[categoria].commission
    assert canales.comision_amazon(D(precio), comision) == D(esperada)


@pytest.mark.parametrize(
    ("peso", "envio", "empaque"),
    [
        ("0.8", "8.00", "1.00"),
        ("1", "8.00", "1.00"),  # ≤ 1 kg
        ("1.01", "12.00", "2.00"),  # > 1 y ≤ 3 kg; empaque > 1 kg $2
        ("3", "12.00", "2.00"),
        ("3.5", "14.00", "2.00"),
        ("6", "14.00", "2.00"),  # ≤ 6 kg
    ],
)
def test_envio_y_empaque_por_peso(peso, envio, empaque):
    """REQ §5: envío FBM ≤ 1 kg $8 · > 1 y ≤ 3 kg $12 · > 3 y ≤ 6 kg $14; empaque ≤ 1 kg $1
    · > 1 kg $2."""
    resultado = canales.envio_amazon(_oferta_b1(peso=peso).observacion, PARAMS.shipping)
    assert resultado is not None
    assert (resultado.envio, resultado.empaque, resultado.peso_estimado) == (
        D(envio),
        D(empaque),
        False,
    )


@pytest.mark.parametrize(
    ("mercado", "esperado"),
    [("119", False), ("101.15", False), ("101.14", True), ("99", True)],
)
def test_competencia_mas_barata_es_estricta(mercado, esperado):
    """RN-002 §4.3 y REQ B1/B9: mercado hoy < venta en Amazon × 85% (119 ≥ 101.15 → no)."""
    assert canales.competencia_mas_barata(D(mercado), D("119"), D("15")) is esperado


@pytest.mark.parametrize(("mercado", "venta"), [(None, "119"), ("119", None), (None, None)])
def test_competencia_mas_barata_sin_precio_no_se_evalua(mercado, venta):
    m = None if mercado is None else D(mercado)
    v = None if venta is None else D(venta)
    assert canales.competencia_mas_barata(m, v, D("15")) is False


def test_ranking_usa_la_ultima_del_dia():
    """design.md §10.3: el promedio usa la última ``rankMain`` de cada día."""
    fichas = _fichas_b1()
    fichas.append(_ficha(_hace(dias=2, horas=3), rank=90000))  # antes, el mismo día −2
    ranking = canales.ranking_amazon(_contexto(fichas=fichas))
    assert ranking.promedio == D("6000")
    assert ranking.dias_con_datos == 7


def test_ranking_sin_fichas():
    ranking = canales.ranking_amazon(_contexto(fichas=[]))
    assert ranking.promedio is None and ranking.dias_con_datos == 0
    assert canales.ficha_vigente(_contexto(fichas=[])) is None


def test_ventas_al_mes_vacio_es_ausente():
    """Una ficha sin "comprados el mes pasado" no da ventas al mes (no es 0)."""
    contexto = _contexto(fichas=_fichas_b1(comprados=None))
    assert canales.ventas_al_mes_amazon(canales.ficha_vigente(contexto)) is None
    assert canales.ventas_al_mes_amazon(None) is None


def test_demanda_local_vacia_es_la_inicial_de_la_categoria():
    """Sin captura de demanda local (``demanda_local=()``), la inicial de PAR-04."""
    assert canales.demanda_local(_contexto(demanda_local=())) is DemandaLocal.MEDIUM
    config = _config(
        (
            "    initial_local_demand: medium\n    provenance_risk: true            # RN-015 §4\n"
            "  home_lighting:",
            "    initial_local_demand: high\n    provenance_risk: true            # RN-015 §4\n"
            "  home_lighting:",
        )
    )
    assert canales.demanda_local(_contexto(configuracion=config)) is DemandaLocal.HIGH
    assert canales.dias_por_unidad_local(DemandaLocal.HIGH, PARAMS.local_sale.demand) == 7
    assert canales.ventas_al_mes_local(DemandaLocal.HIGH, PARAMS.local_sale.demand) == 4
    assert canales.dias_por_unidad_local(DemandaLocal.LOW, PARAMS.local_sale.demand) is None
    assert canales.ventas_al_mes_local(DemandaLocal.LOW, PARAMS.local_sale.demand) is None


def test_precio_local_sin_estimado_ni_mercado_no_existe():
    assert canales.precio_venta_local(_contexto(), None) is None


# =========================================================================================
# Estado del canal y concurrencia cerrado / por revisar (REQ §3.2.1; S-31)
# =========================================================================================


@pytest.mark.parametrize(
    ("cerrado", "por_revisar", "esperado"),
    [
        ((), (), EstadoCanal.DISPONIBLE),
        ((), (CausaCanalPorRevisar.DEMANDA_DESCONOCIDA,), EstadoCanal.POR_REVISAR),
        ((), (CausaCanalPorRevisar.SIN_REFERENCIA_DE_USADOS,), EstadoCanal.POR_REVISAR),
        ((CausaCanalCerrado.DEMANDA_INSUFICIENTE_EN_AMAZON,), (), EstadoCanal.CERRADO),
        # Concurrencia (S-31): una causa de cerrado prevalece sobre una de por revisar.
        (
            (CausaCanalCerrado.SIN_PRECIO_DE_VENTA_EN_AMAZON,),
            (CausaCanalPorRevisar.DEMANDA_DESCONOCIDA,),
            EstadoCanal.CERRADO,
        ),
        (
            (CausaCanalCerrado.NO_VENDIBLE_EN_AMAZON,),
            (CausaCanalPorRevisar.DEMANDA_DESCONOCIDA,),
            EstadoCanal.CERRADO,
        ),
        (
            (CausaCanalCerrado.DEMANDA_LOCAL_BAJA,),
            (CausaCanalPorRevisar.SIN_REFERENCIA_DE_USADOS,),
            EstadoCanal.CERRADO,
        ),
        (
            (CausaCanalCerrado.SIN_ROTACION,),
            (CausaCanalPorRevisar.SIN_REFERENCIA_DE_USADOS,),
            EstadoCanal.CERRADO,
        ),
        (
            (CausaCanalCerrado.ENVIO_POR_COTIZAR, CausaCanalCerrado.COMISION_DESCONOCIDA),
            (CausaCanalPorRevisar.DEMANDA_DESCONOCIDA,),
            EstadoCanal.CERRADO,
        ),
    ],
)
def test_estado_del_canal_s31(cerrado, por_revisar, esperado):
    assert canales.estado_del_canal(cerrado, por_revisar) is esperado


def _amazon_de(contexto: ContextoEvaluacion) -> CanalEvaluado:
    refs = referencias.calcular_referencias(contexto)
    costo = canales.costo_compra(contexto.oferta.observacion, contexto.configuracion.contenido)
    return canales.evaluar_amazon(contexto, refs, costo)


def _sin_ranking() -> list[ObservacionRegistrada]:
    return _fichas_b1(rank_hoy=None, rank_hace_30=None)


_MARCA_RESTRINGIDA = (
    "  amazon_restricted_brands: []\n",
    f"  amazon_restricted_brands: [{MARCA_B1}]\n",
)


def test_amazon_sin_ranking_queda_por_revisar():
    """REQ §3.2.1 y DEC-206: 0 días de ranking → Amazon por revisar, ``DEMANDA DESCONOCIDA``."""
    a = _amazon_de(_contexto(fichas=_sin_ranking()))
    assert a.estado is EstadoCanal.POR_REVISAR
    assert a.causas_cerrado == ()
    assert a.causas_por_revisar == (CausaCanalPorRevisar.DEMANDA_DESCONOCIDA,)


def test_concurrencia_en_amazon_cerrado_prevalece_sobre_por_revisar():
    """S-31 (REQ §3.2.1 "Concurrencia"): sin ranking (por revisar) y marca restringida
    (cerrado) → Amazon **cerrado**; sin ``nivel_calculado`` (DEC-224 a)."""
    config = _config(_MARCA_RESTRINGIDA)
    a = _amazon_de(_contexto(fichas=_sin_ranking(), configuracion=config))
    assert a.estado is EstadoCanal.CERRADO
    assert CausaCanalCerrado.NO_VENDIBLE_EN_AMAZON in a.causas_cerrado
    # El canal cerrado no tiene nivel ni nivel_calculado.
    canal = _canal_con_margenes_amazon_b1(
        estado=EstadoCanal.CERRADO,
        causas_cerrado=a.causas_cerrado,
        causas_por_revisar=a.causas_por_revisar,
        costo_devoluciones=None,
        castigo=None,
        margen_ajustado=None,
        margen_ajustado_pct=None,
    )
    asignado = rentabilidad.asignar_nivel(
        canal,
        a,
        descuento_real=REAL_B1,
        costo_compra=D("31.25"),
        confianza_ok=True,
        configuracion=config.contenido,
    )
    assert asignado.nivel is None and asignado.nivel_calculado is None


def test_concurrencia_por_el_motor_no_da_demanda_desconocida():
    """S-31 por el motor: con Amazon cerrado (restringido) aunque falte el ranking, no hay
    ``DEMANDA DESCONOCIDA`` ni revisión manual; la venta local de B1 sigue con su nivel."""
    config = _config(_MARCA_RESTRINGIDA)
    r = motor.evaluar(_contexto(fichas=_sin_ranking(), configuracion=config))
    a = _canal(r, Canal.AMAZON)
    assert a.estado is EstadoCanal.CERRADO
    assert a.nivel is None and a.nivel_calculado is None
    assert a.unidades is None and a.rendimiento_mensual_pct is None
    assert r.motivos == ()
    assert r.resultado is Resultado.NIVEL_ASIGNADO
    assert r.canal_elegido is Canal.LOCAL
    assert r.nivel_aviso is Nivel.MUY_RECOMENDABLE and r.canal_aviso is Canal.LOCAL


# =========================================================================================
# RNF-9: todo cálculo de Amazon lleva MARGEN ESTIMADO y EMPAQUE POR CONFIRMAR (RN-001 §11)
# =========================================================================================

_RNF9 = (Marca.MARGEN_ESTIMADO.value, Marca.EMPAQUE_POR_CONFIRMAR.value)


@pytest.mark.parametrize(
    ("fichas", "reemplazos", "estado"),
    [
        (None, (), EstadoCanal.DISPONIBLE),
        (_sin_ranking(), (), EstadoCanal.POR_REVISAR),
        (None, (_MARCA_RESTRINGIDA,), EstadoCanal.CERRADO),  # neto informativo
    ],
    ids=["disponible", "por-revisar", "cerrado-con-neto"],
)
def test_rnf9_marcas_de_amazon_en_todo_calculo(fichas, reemplazos, estado):
    a = _amazon_de(_contexto(fichas=fichas, configuracion=_config(*reemplazos)))
    assert a.estado is estado
    assert a.precio_venta is not None and a.costo_venta is not None  # hay cálculo
    for marca in _RNF9:
        assert marca in a.marcas
    assert len(set(a.marcas)) == len(a.marcas)


def test_rnf9_en_el_registro_y_solo_en_amazon(registro_b1):
    a = _canal(registro_b1, Canal.AMAZON)
    loc = _canal(registro_b1, Canal.LOCAL)
    for marca in _RNF9:
        assert marca in set(a.marcas) | set(registro_b1.marcas)
        assert marca not in loc.marcas


# =========================================================================================
# nivel_calculado y nivel por estado del canal (REQ §3.2.1, §3.2.2; S-30; DEC-202, DEC-224)
# =========================================================================================


def _asignar(canal: EvaluacionCanal, insumos: CanalEvaluado, **cambios) -> EvaluacionCanal:
    argumentos = {
        "descuento_real": REAL_B1,
        "costo_compra": D("31.25"),
        "confianza_ok": True,
        "configuracion": PARAMS,
    }
    argumentos.update(cambios)
    return rentabilidad.asignar_nivel(canal, insumos, **argumentos)


def test_nivel_por_revisar_solo_nivel_calculado():
    """S-30: en un canal por revisar el nivel es ``nivel_calculado`` informativo."""
    por_revisar = {
        "estado": EstadoCanal.POR_REVISAR,
        "causas_por_revisar": (CausaCanalPorRevisar.DEMANDA_DESCONOCIDA,),
    }
    canal = _asignar(
        _canal_con_margenes_amazon_b1(**por_revisar), _insumos_amazon_b1(**por_revisar)
    )
    assert canal.nivel is None
    assert canal.nivel_calculado is Nivel.MUY_RECOMENDABLE
    # Sin unidades, días ni rendimiento.
    canal = rentabilidad.calcular_unidades(
        canal, _insumos_amazon_b1(**por_revisar), descuento_real=REAL_B1, configuracion=PARAMS
    )
    assert canal.unidades is None and canal.dias_para_recuperar is None
    assert canal.rendimiento_mensual_pct is None and canal.ganancia_total is None


def test_nivel_exige_confianza_pero_nivel_calculado_no():
    """DEC-202: ``nivel_calculado`` no usa la confianza; el nivel del canal sí (RN-009 §4.2)."""
    canal = _asignar(_canal_con_margenes_amazon_b1(), _insumos_amazon_b1(), confianza_ok=False)
    assert canal.nivel is None
    assert canal.nivel_calculado is Nivel.MUY_RECOMENDABLE


@pytest.mark.parametrize("real", [None, D("24.99"), D("20")])
def test_sin_descuento_real_suficiente_no_hay_nivel_calculado(real):
    """REQ §3.2.2: ``nivel_calculado`` exige descuento real ≥ 25%."""
    canal = _asignar(_canal_con_margenes_amazon_b1(), _insumos_amazon_b1(), descuento_real=real)
    assert canal.nivel is None and canal.nivel_calculado is None
    canal = rentabilidad.calcular_unidades(
        canal, _insumos_amazon_b1(), descuento_real=real, configuracion=PARAMS
    )
    assert canal.unidades is None and canal.rendimiento_mensual_pct is None
    # El margen ajustado de un canal disponible se conserva (EXT-004).
    assert canal.margen_ajustado == D("44.73")


def test_competencia_mas_barata_baja_un_nivel_en_amazon():
    """RN-002 §4.3 y DEC-202: la baja por competencia entra en ``nivel_calculado``."""
    insumos = _insumos_amazon_b1(baja_por_competencia=True)
    canal = _asignar(_canal_con_margenes_amazon_b1(), insumos)
    assert canal.nivel_calculado is Nivel.RECOMENDABLE
    assert canal.nivel is Nivel.RECOMENDABLE
    margenes = rentabilidad.Margenes(
        D("53.90"), D("172.48"), D("4.17"), D("5.00"), D("44.73"), D("143.136")
    )
    assert rentabilidad.nivel_calculado(REAL_B1, margenes, D("31.25"), PARAMS, True) is (
        Nivel.RECOMENDABLE
    )


@pytest.mark.parametrize(
    ("ajustado", "pct", "esperado"),
    [
        ("10.00", "40", Nivel.MUY_RECOMENDABLE),  # = $10: alcanza el mínimo por unidad
        ("9.99", "40", None),  # < $10 → sin nivel
    ],
)
def test_minimo_por_unidad_en_el_nivel(ajustado, pct, esperado):
    """RN-009 §4.2: margen ajustado ≥ mayor($10, 10% del costo de compra)."""
    margenes = rentabilidad.Margenes(D("20"), D("64"), D("0"), D("0"), D(ajustado), D(pct))
    assert rentabilidad.nivel_calculado(REAL_B1, margenes, D("31.25"), PARAMS, False) is esperado


def test_minimo_por_unidad_porcentaje_del_costo():
    # Con costo de compra $150, 10% = $15 > $10.
    assert rentabilidad.minimo_por_unidad(D("150"), PARAMS.levels.min_per_unit) == D("15")


@pytest.mark.parametrize(
    ("real", "pct", "esperado"),
    [
        (D("80"), D("50"), Nivel.COMPRAR_YA),
        (D("79.99"), D("200"), Nivel.MUY_RECOMENDABLE),
        (D("70"), D("40"), Nivel.MUY_RECOMENDABLE),
        (D("70"), D("39.99"), Nivel.RECOMENDABLE),
        (D("50"), D("30"), Nivel.RECOMENDABLE),
        (D("25"), D("25"), Nivel.VIGILAR),
        (D("24.99"), D("200"), None),
        (D("90"), D("24.99"), None),
    ],
)
def test_nivel_por_umbrales_bordes(real, pct, esperado):
    """RN-009 §4.3 (tabla de PAR-13): el nivel más alto cuyos dos mínimos se cumplen."""
    assert rentabilidad.nivel_por_umbrales(real, pct, PARAMS.levels.thresholds) is esperado


# =========================================================================================
# Nivel antes que unidades: el tope depende del nivel (design.md §3; RN-005 §4; REQ §5)
# =========================================================================================


@pytest.mark.parametrize(
    ("ranking", "nivel", "tope"),
    [
        (D("6000"), Nivel.MUY_RECOMENDABLE, 5),
        (D("6000"), Nivel.COMPRAR_YA, 5),
        (D("9999.99"), Nivel.COMPRAR_YA, 5),
        (D("6000"), Nivel.RECOMENDABLE, 3),
        (D("6000"), Nivel.VIGILAR, 3),
        (D("6000"), None, 3),
        (D("10000"), Nivel.MUY_RECOMENDABLE, 3),  # 10,000 no es < 10,000
        (None, Nivel.MUY_RECOMENDABLE, 3),
    ],
)
def test_tope_de_primera_compra(ranking, nivel, tope):
    parametros = PARAMS.amazon.first_purchase_cap
    assert rentabilidad.tope_primera_compra(ranking, nivel, parametros) == tope


def test_unidades_usan_el_nivel_ya_asignado():
    """Con 10 disponibles y 33 ventas al mes, las unidades son el tope: 5 si el canal ya
    tiene Muy recomendable (ranking 6,000), 3 si la competencia lo baja a Recomendable."""
    insumos = _insumos_amazon_b1(disponibles=10)
    con_nivel = _asignar(_canal_con_margenes_amazon_b1(), insumos)
    assert con_nivel.nivel is Nivel.MUY_RECOMENDABLE
    canal = rentabilidad.calcular_unidades(
        con_nivel, insumos, descuento_real=REAL_B1, configuracion=PARAMS
    )
    assert canal.unidades == 5
    assert canal.ganancia_total == D("223.65")  # 44.73 × 5

    insumos = _insumos_amazon_b1(disponibles=10, baja_por_competencia=True)
    bajado = _asignar(_canal_con_margenes_amazon_b1(), insumos)
    canal = rentabilidad.calcular_unidades(
        bajado, insumos, descuento_real=REAL_B1, configuracion=PARAMS
    )
    assert bajado.nivel is Nivel.RECOMENDABLE and canal.unidades == 3


def test_el_motor_asigna_el_nivel_antes_que_las_unidades():
    pasos = list(motor.PASOS)
    assert pasos.index(motor.asignar_nivel) < pasos.index(motor.calcular_unidades_y_rendimiento)
    assert pasos.index(motor.evaluar_canales) < pasos.index(motor.asignar_nivel)
    assert pasos.index(motor.calcular_unidades_y_rendimiento) < pasos.index(motor.elegir_canal)


@pytest.mark.parametrize(
    ("ventas", "disponibles", "limite", "tope", "esperado"),
    [
        (33, 3, None, 5, 3),
        (33, None, None, 5, 5),  # sin dato de disponibles no limita
        (33, 10, 2, 5, 2),  # límite por cliente
        (None, 10, None, 5, 2),  # sin ventas al mes: máximo 2
        (1, 10, None, 5, 1),
        (0, 10, None, 5, 0),
    ],
)
def test_unidades_recomendadas(ventas, disponibles, limite, tope, esperado):
    assert rentabilidad.unidades_recomendadas(ventas, disponibles, limite, tope, 2) == esperado


def test_dias_para_recuperar_sin_unidades():
    assert rentabilidad.dias_para_recuperar(0, 33, 7, None, 30) is None


def test_dias_para_recuperar_por_ritmo_de_ventas():
    # Amazon con 5 unidades y 3 ventas al mes: 5 ÷ (3 ÷ 30) = 50 > 7 → 50 + 30 = 80.
    assert rentabilidad.dias_para_recuperar(5, 3, 7, None, 30) == 80
    # 4 ÷ (3 ÷ 30) = 40; 3 ÷ (7 ÷ 30) = 12.86 → 13 (hacia arriba) > 7 → 13 + 30.
    assert rentabilidad.dias_para_recuperar(3, 7, 7, None, 30) == 43


# =========================================================================================
# Elección del canal (RN-018 §4; DEC-170) y nivel del aviso (S-33; DEC-219, DEC-221)
# =========================================================================================


def test_eleccion_diferencia_de_10_no_desempata():
    """RN-018 §4: desempata el rendimiento solo si la diferencia es **menor** de 10%."""
    a = _canal_final(Canal.AMAZON, nivel=Nivel.VIGILAR, ganancia="100.00", rendimiento="30")
    loc = _canal_final(Canal.LOCAL, nivel=Nivel.VIGILAR, ganancia="90.00", rendimiento="90")
    assert eleccion.canal_elegido((a, loc), D("10")) is Canal.AMAZON


def test_eleccion_diferencia_menor_de_10_desempata_el_rendimiento():
    a = _canal_final(Canal.AMAZON, nivel=Nivel.VIGILAR, ganancia="100.00", rendimiento="30")
    loc = _canal_final(Canal.LOCAL, nivel=Nivel.VIGILAR, ganancia="90.01", rendimiento="90")
    assert eleccion.canal_elegido((a, loc), D("10")) is Canal.LOCAL


def test_eleccion_se_mide_contra_la_ganancia_mayor():
    """(100 − 90.5) ÷ 100 = 9.5% < 10% (contra la mayor); contra la menor sería 10.5%."""
    a = _canal_final(Canal.AMAZON, nivel=Nivel.VIGILAR, ganancia="90.50", rendimiento="90")
    loc = _canal_final(Canal.LOCAL, nivel=Nivel.VIGILAR, ganancia="100.00", rendimiento="30")
    assert eleccion.canal_elegido((a, loc), D("10")) is Canal.AMAZON


def test_eleccion_solo_entre_canales_disponibles_con_nivel():
    """S-30: un canal por revisar no entra en la elección, aunque tenga ``nivel_calculado``
    y más ganancia; sin canales con nivel no hay elección."""
    por_revisar = _canal_final(
        Canal.AMAZON,
        estado=EstadoCanal.POR_REVISAR,
        nivel=None,
        nivel_calculado=Nivel.COMPRAR_YA,
        ganancia=None,
        rendimiento=None,
    )
    loc = _canal_final(
        Canal.LOCAL, nivel=Nivel.MUY_RECOMENDABLE, ganancia="100.58", rendimiento="160.928"
    )
    assert eleccion.canal_elegido((por_revisar, loc), D("10")) is Canal.LOCAL
    assert eleccion.nivel_del_aviso((por_revisar, loc), Canal.LOCAL) == (
        Nivel.MUY_RECOMENDABLE,
        Canal.LOCAL,
    )
    sin_nivel = _canal_final(Canal.LOCAL, nivel=None, ganancia=None, rendimiento=None)
    assert eleccion.canal_elegido((por_revisar, sin_nivel), D("10")) is None
    assert eleccion.nivel_del_aviso((por_revisar, sin_nivel), None) == (None, None)
    assert eleccion.elegir((por_revisar, sin_nivel), D("10")) == eleccion.Eleccion(None, None, None)


def test_s33_el_aviso_usa_el_nivel_mas_alto_aunque_el_elegido_sea_otro():
    """S-33: el elegido (mayor ganancia) es Amazon en Recomendable; el aviso usa Muy
    recomendable, de la venta local."""
    a = _canal_final(Canal.AMAZON, nivel=Nivel.RECOMENDABLE, ganancia="134.19", rendimiento="100")
    loc = _canal_final(
        Canal.LOCAL, nivel=Nivel.MUY_RECOMENDABLE, ganancia="69.98", rendimiento="112"
    )
    assert eleccion.elegir((a, loc), D("10")) == eleccion.Eleccion(
        Canal.AMAZON, Nivel.MUY_RECOMENDABLE, Canal.LOCAL
    )


def test_s33_empate_de_nivel_usa_el_canal_elegido():
    """design.md §10.6: con empate, el del canal elegido (aquí la venta local, por
    rendimiento con diferencia < 10%)."""
    a = _canal_final(
        Canal.AMAZON, nivel=Nivel.MUY_RECOMENDABLE, ganancia="110.19", rendimiento="95.3"
    )
    loc = _canal_final(
        Canal.LOCAL, nivel=Nivel.MUY_RECOMENDABLE, ganancia="100.58", rendimiento="160.9"
    )
    assert eleccion.elegir((a, loc), D("10")) == eleccion.Eleccion(
        Canal.LOCAL, Nivel.MUY_RECOMENDABLE, Canal.LOCAL
    )


def test_eleccion_no_depende_del_orden_de_los_canales():
    a = _canal_final(
        Canal.AMAZON, nivel=Nivel.MUY_RECOMENDABLE, ganancia="134.19", rendimiento="116"
    )
    loc = _canal_final(
        Canal.LOCAL, nivel=Nivel.MUY_RECOMENDABLE, ganancia="100.58", rendimiento="160"
    )
    assert eleccion.elegir((a, loc), D("10")) == eleccion.elegir((loc, a), D("10"))


def test_desempate_sale_de_la_configuracion():
    """PAR-13 ``channel_tiebreak_pct``: con 30%, la diferencia de 25.0% de B1 desempata por
    rendimiento y gana la venta local."""
    config = _config(("  channel_tiebreak_pct: 10\n", "  channel_tiebreak_pct: 30\n"))
    r = motor.evaluar(_contexto(configuracion=config))
    assert r.canal_elegido is Canal.LOCAL
    assert r.nivel_aviso is Nivel.MUY_RECOMENDABLE and r.canal_aviso is Canal.LOCAL


# =========================================================================================
# Dinero: Decimal sin float y redondeo una sola vez (design.md §8; DEC-207, DEC-222)
# =========================================================================================


# ``canales`` es un subpaquete desde la implementación (mismas firmas públicas).
_MODULOS_T11 = (
    "identificacion.py",
    "canales",
    "rentabilidad.py",
    "eleccion.py",
)


def _codigo(archivo: str) -> str:
    """El código de un módulo o subpaquete de ``evaluacion/``, con los comentarios y los
    textos en blanco (un docstring o un comentario que nombra ``total_seconds`` no es un
    uso). Conserva la disposición del código, para que las expresiones regulares valgan."""
    ruta = SRC_EVALUACION / archivo
    rutas = sorted(ruta.glob("*.py")) if ruta.is_dir() else [ruta]
    partes = []
    for fichero in rutas:
        lineas = fichero.read_text(encoding="utf-8").splitlines(keepends=True)
        with fichero.open("rb") as f:
            tokens = list(tokenize.tokenize(f.readline))
        for token in reversed(tokens):
            if token.type not in (tokenize.COMMENT, tokenize.STRING):
                continue
            (fila_i, col_i), (fila_f, col_f) = token.start, token.end
            if fila_i == fila_f:
                linea = lineas[fila_i - 1]
                lineas[fila_i - 1] = linea[:col_i] + " " * (col_f - col_i) + linea[col_f:]
            else:
                lineas[fila_i - 1] = lineas[fila_i - 1][:col_i] + "\n"
                for fila in range(fila_i, fila_f - 1):
                    lineas[fila] = "\n"
                lineas[fila_f - 1] = " " * col_f + lineas[fila_f - 1][col_f:]
        partes.append("".join(lineas))
    return "\n".join(partes)


@pytest.mark.parametrize("archivo", _MODULOS_T11)
def test_ningun_modulo_redondea_por_su_cuenta_ni_usa_float(archivo):
    """design.md §8: ``dinero.redondear`` es la única que redondea; nunca ``float``."""
    fuente = _codigo(archivo)
    assert not re.search(r"\.quantize\(|\bround\(|\bfloat\(|ROUND_", fuente)
    assert not re.search(r"\.total_seconds\(", fuente)  # da float


@pytest.mark.parametrize("archivo", _MODULOS_T11)
def test_modulos_puros_sin_reloj_ni_red(archivo):
    """design.md §14: sin reloj, sin I/O, sin red, sin aleatoriedad."""
    fuente = _codigo(archivo)
    for patron in (
        r"\.now\(",
        r"\.today\(",
        r"\butcnow\(",
        r"\bimport random\b",
        r"\bimport time\b",
        r"\bopen\(",
        r"\bsocket\b",
        r"\burllib\b",
        r"\bhttpx\b",
        r"\brequests\b",
        r"oip\.persistencia",
    ):
        assert not re.search(patron, fuente), patron


@pytest.fixture
def espia_redondeo(monkeypatch):
    """Registra cada llamada a ``dinero.redondear`` (sin cambiar su resultado), donde sea que
    los módulos de T11 la hayan importado."""
    original = oip.dinero.redondear
    llamadas: list[tuple[TipoMonto, Decimal]] = []

    def espia(tipo, valor):
        llamadas.append((tipo, valor))
        return original(tipo, valor)

    monkeypatch.setattr(oip.dinero, "redondear", espia)
    # También en los submódulos (``canales`` es un subpaquete): todo módulo de ``oip``.
    for nombre_modulo, modulo in list(sys.modules.items()):
        if modulo is None or not nombre_modulo.startswith("oip."):
            continue
        for nombre, valor in list(vars(modulo).items()):
            if valor is original:
                monkeypatch.setattr(modulo, nombre, espia)
    return llamadas


def _hubo(llamadas, tipo: TipoMonto, valor: str) -> bool:
    return any(t is tipo and v == D(valor) for t, v in llamadas)


def test_b1_cada_monto_se_redondea_una_vez_al_final(espia_redondeo):
    """Cada monto de la lista cerrada se redondea con ``dinero.redondear`` sobre su fórmula
    completa (REQ §5 "Redondeo", B33; design.md §8)."""
    motor.evaluar(_contexto())
    llamadas = espia_redondeo
    assert llamadas, "nadie llamó a dinero.redondear"
    for tipo, valor in llamadas:
        assert isinstance(tipo, TipoMonto)
        assert isinstance(valor, Decimal) and not isinstance(valor, bool)
    assert _hubo(llamadas, TipoMonto.IMPUESTO, "2.2475")  # 29 × 7.75%
    assert _hubo(llamadas, TipoMonto.COMISION, "17.85")  # 119 × 15%
    assert _hubo(llamadas, TipoMonto.DEVOLUCIONES, "4.165")  # 119 × 7% × 50%
    # Venta local = mercado hoy × 85% × 90% en una sola fórmula: 91.035, nunca 101.15.
    assert _hubo(llamadas, TipoMonto.PRECIO_VENTA_LOCAL, "91.035")
    assert not _hubo(llamadas, TipoMonto.PRECIO_VENTA_LOCAL, "101.15")
    assert not any(v == D("101.15") for _, v in llamadas)
    # Entrega 10 × 0.20 + 0.5 × 15 = 9.5.
    assert _hubo(llamadas, TipoMonto.TRASLADO_ENTREGA, "9.5")


def test_b1_los_montos_combinados_usan_los_ya_redondeados(espia_redondeo):
    """design.md §8: neto, ajustado y ganancia usan los montos ya redondeados. Con los sin
    redondear, el costo de compra sería 31.2475 y la ganancia 44.735 × 3 = 134.205."""
    motor.evaluar(_contexto())
    llamadas = espia_redondeo
    assert _hubo(llamadas, TipoMonto.COSTO_COMPRA, "31.25")
    assert _hubo(llamadas, TipoMonto.MARGEN_NETO, "53.90")
    assert _hubo(llamadas, TipoMonto.MARGEN_AJUSTADO, "44.73")
    assert _hubo(llamadas, TipoMonto.GANANCIA_TOTAL, "134.19")
    assert _hubo(llamadas, TipoMonto.GANANCIA_TOTAL, "100.58")
    assert not any(v in (D("31.2475"), D("44.735"), D("134.205")) for _, v in llamadas)


@pytest.mark.parametrize(
    "llamada",
    [
        lambda: rentabilidad.margen_neto(119.0, D("31.25"), D("33.85")),
        lambda: rentabilidad.costo_devoluciones(D("119"), 7.0, D("50")),
        lambda: rentabilidad.castigo_por_baja(119.0, D("109"), PARAMS.amazon.drop_penalty),
        lambda: rentabilidad.margen_ajustado(D("53.90"), 4.17, D("5.00")),
        lambda: rentabilidad.ganancia_total(44.73, 3),
        lambda: rentabilidad.porcentaje_sobre_compra(D("44.73"), 31.25),
        lambda: canales.comision_amazon(119.0, PARAMS.categories["tools"].commission),
    ],
)
def test_montos_float_se_rechazan(llamada):
    with pytest.raises(TypeError):
        llamada()


def test_registro_b1_sin_float_y_con_tipos_estrictos(registro_b1):
    """DEC-238 y design.md §8: montos y porcentajes ``Decimal``; unidades y días ``int``."""
    for canal in registro_b1.canales:
        for campo in dataclasses.fields(canal):
            valor = getattr(canal, campo.name)
            assert not isinstance(valor, float), campo.name
        for campo in ("unidades", "dias_para_recuperar"):
            valor = getattr(canal, campo)
            assert valor is None or (type(valor) is int), campo
    assert type(registro_b1.costo_compra) is Decimal
    with pytest.raises(TypeError):
        EvaluacionCanal(canal=Canal.AMAZON, estado=EstadoCanal.DISPONIBLE, margen_neto=53.9)
    with pytest.raises(TypeError):
        EvaluacionCanal(canal=Canal.AMAZON, estado=EstadoCanal.DISPONIBLE, unidades=True)


# =========================================================================================
# Reproducible, sin datos personales en logs ni errores (RNF-3; DEC-181; R-20)
# =========================================================================================


def test_b1_reproducible(registro_b1):
    """El mismo contexto (también leído de su JSON canónico) da el mismo registro."""
    contexto = _contexto()
    primera = motor.evaluar(contexto)
    assert motor.evaluar(contexto).a_json() == primera.a_json()
    leido = ContextoEvaluacion.desde_json(contexto.a_json())
    assert motor.evaluar(leido).a_json() == primera.a_json()
    # Otro contexto con los mismos datos (otros ids de observación) da los mismos números.
    assert primera.canales == registro_b1.canales
    assert primera.canales, "B1 debe tener sus dos canales"


def test_b1_no_depende_del_orden_del_historial(registro_b1):
    contexto = _contexto(
        historial=list(reversed(_historial_b1())), fichas=list(reversed(_fichas_b1()))
    )
    r = motor.evaluar(contexto)
    assert r.canales == registro_b1.canales
    assert (r.resultado, r.canal_elegido, r.nivel_aviso) == (
        registro_b1.resultado,
        registro_b1.canal_elegido,
        registro_b1.nivel_aviso,
    )


def test_b1_los_logs_no_llevan_contenido_de_la_oferta(caplog):
    """DEC-181: los logs solo llevan identificadores, conteos y tiempos (ni el enlace ni el
    título de la publicación). El contexto no tiene ningún campo de cliente: el alias de un
    cliente no puede llegar al motor (R-20)."""
    with caplog.at_level(logging.DEBUG):
        motor.evaluar(_contexto())
    for registro in caplog.records:
        texto = registro.getMessage() + repr(registro.args)
        assert URL_OFERTA not in texto and TITULO_OFERTA not in texto
        assert MARCA_B1 not in texto
    nombres = {c.name for c in dataclasses.fields(ContextoEvaluacion)}
    assert not {n for n in nombres if "alias" in n or "cliente" in n}


def test_errores_de_entrada_no_repiten_el_contenido():
    """Un dato posterior al instante levanta ``ValueError`` sin copiar datos de la oferta."""
    with pytest.raises(ValueError) as error:
        identificacion.antiguedad_horas(INSTANTE, INSTANTE + dt.timedelta(hours=1))
    assert URL_OFERTA not in str(error.value) and MARCA_B1 not in str(error.value)
