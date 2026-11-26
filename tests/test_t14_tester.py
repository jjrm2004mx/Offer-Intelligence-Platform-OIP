"""Pruebas independientes de oip-tester para T14 (ranking, demanda, unidades y más de 6 kg:
B10 a y b, B12, B13, B26 a y b).

Capacidad ``canales-y-margen``; REQ-2026-0001 v2.9 §3.2 pasos 7 y 9, §3.2.1, §3.2.2
(``nivel_calculado``), §3.2.3, §3.2.4, §5 (configuración base), §11 y §13 S-06, S-30; RN-004
v2 §4, RN-005 v2 §4 y §11, RN-006 v2 §4.2, RN-009 v2, RN-018 v1 §4; design.md CMP-13 a CMP-15,
PAR-06, PAR-11, PAR-13, §8, §9 y §10 puntos 3, 8 y 15; DEC-206, DEC-259, DEC-266, DEC-267,
DEC-269, DEC-270.

Escritas por adelantado (DEC-252, etapa 2) **sin ver la implementación de T14**: solo con la
interfaz pública de main (firmas y tipos) y las fuentes. Los datos y los resultados esperados
se copian del REQ (precios, montos, porcentajes, niveles, resultado y canal), no del código.
Las pruebas de reglas que no son el escenario tal cual (bordes de la ventana del ranking, del
50% de RN-004, de los 6 kg y del 10% de RN-018) no llevan marcador de escenario.

Supuestos de fixtures (design.md §12, "Dado" parcial; DEC-232):

- Ventana del ranking (design.md §10 punto 3): la última ``rankMain`` de cada día de los 7
  días que terminan el día evaluado (incluido); "hace 30 días" = los 7 días que terminan 30
  días antes. B1 pone 6,000 en las dos ventanas ("hace 30 días 6,000").
- Las fichas de ranking de días anteriores no traen botón de compra, para no agregar
  observaciones al precio habitual (sigue en $119) ni cambiar el mínimo de 60 días ($109).
- B26: el peso de 8 kg va en la oferta, en el historial y en las fichas del producto. La
  cotización de B26 (b) es una entrada de ``shipping.quotes`` (PAR-06) en la configuración de
  estas pruebas, porque base.yaml trae ``quotes: []``.
- B10 (a): "sin ranking" = ninguna ficha con ``rankMain``; vendedores (5) y comprados (200)
  siguen en la ficha de hoy, como en B1.

Fixtures sintéticos (DEC-194): comercios ficticios con subdominios de example.com; ninguna
prueba abre una URL. Instante explícito en ``America/Tijuana`` (PAR-01), sin reloj, sin red,
sin aleatoriedad y sin depender de la zona de la máquina.
"""

from __future__ import annotations

import datetime as dt
import itertools
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from config_tienda_prueba import BASE, TIENDA_PRUEBA, con_tienda_prueba
from oip.catalogos import (
    Canal,
    Categoria,
    CausaCanalCerrado,
    CausaCanalPorRevisar,
    DemandaAmazon,
    EstadoCanal,
    Marca,
    Motivo,
    Nivel,
    Resultado,
    marca_estimado,
)
from oip.configuracion import cargar_configuracion_texto
from oip.dinero import formatear_porcentaje
from oip.entradas.contrato import leer_observacion
from oip.evaluacion import canales, eleccion, motor, rentabilidad
from oip.evaluacion.contexto import (
    ContextoEvaluacion,
    EvaluacionCanal,
    ObservacionRegistrada,
)

D = Decimal
TIJUANA = ZoneInfo("America/Tijuana")

# --- Configuración -------------------------------------------------------------------------
# ``tienda-prueba`` es "Home Depot" (la cadena de la oferta); ``ca`` y ``cb`` son dos cadenas
# más ("Walmart" y otra). La ficha de Amazon es el comercio ``amazon`` de la base, con URL
# sintética que nadie abre. ``tp-cv`` es la sucursal de la oferta ("Chula Vista").
_EXTRA_COMERCIOS = (
    "  ca: {chain: cadena-a, domains: [a.example.com], amazon_listing: false}\n"
    "  cb: {chain: cadena-b, domains: [b.example.com], amazon_listing: false}\n"
)
_EXTRA_SUCURSAL = "  tp-cv: {retailer: tienda-prueba}\n"
_DOMINIO = {
    TIENDA_PRUEBA: "tienda.example.com",
    "ca": "a.example.com",
    "cb": "b.example.com",
    "amazon": "amazon.example.com",
}

# Producto de B1 (sintético): UPC-A con dígito verificador válido.
GTIN_B1 = "012345678905"
MARCA_B1 = "MarcaS"
MODELO_B1 = "SC-14"
# Otro producto (para comprobar que una cotización no se aplica a otro producto).
GTIN_OTRO = "036000291452"

_SIN_COTIZACIONES = "  quotes: []\n"


def _cotizacion(gtin: str, monto: str) -> str:
    return (
        f'  quotes:\n    - {{product: {{gtin: "{gtin}"}}, shipping: {monto}, date: 2026-11-10}}\n'
    )


def _texto(*reemplazos: tuple[str, str]) -> str:
    texto = con_tienda_prueba(BASE.read_text(encoding="utf-8"))
    assert texto.count("\nretailers:\n") == 1
    texto = texto.replace("\nretailers:\n", "\nretailers:\n" + _EXTRA_COMERCIOS, 1)
    assert texto.count("\nstores:\n") == 1
    texto = texto.replace("\nstores:\n", "\nstores:\n" + _EXTRA_SUCURSAL, 1)
    for viejo, nuevo in reemplazos:
        assert texto.count(viejo) == 1, viejo
        texto = texto.replace(viejo, nuevo)
    return texto


def _config(*reemplazos: tuple[str, str]):
    return cargar_configuracion_texto(_texto(*reemplazos), origen="t14-tester")


#: Configuración base de los escenarios (REQ §5), sin cotizaciones (B26 a).
CONFIG = _config()
#: B26 (b): "con cotización capturada de $22" para el producto de B1.
CONFIG_COTIZACION = _config((_SIN_COTIZACIONES, _cotizacion(GTIN_B1, "22.00")))
#: Cotización de $22 para **otro** producto: no vale para el de B1.
CONFIG_COTIZACION_OTRO = _config((_SIN_COTIZACIONES, _cotizacion(GTIN_OTRO, "22.00")))
PARAMS = CONFIG.contenido
#: Día 0 de los escenarios.
INSTANTE = dt.datetime(2026, 11, 16, 14, 0, tzinfo=TIJUANA)

_ids = itertools.count(0x7140_1000)


def _uuid() -> UUID:
    return UUID(int=next(_ids))


def _hace(horas: float = 0, dias: int = 0) -> dt.datetime:
    return INSTANTE - dt.timedelta(days=dias, hours=horas)


def _pct(valor: Decimal | None) -> str:
    assert isinstance(valor, Decimal), f"se esperaba Decimal, llegó {type(valor).__name__}"
    return formatear_porcentaje(valor)


def _canal(registro, canal: Canal) -> EvaluacionCanal:
    encontrados = [c for c in registro.canales if c.canal is canal]
    assert len(encontrados) == 1, f"se esperaba un canal {canal}: {registro.canales!r}"
    return encontrados[0]


def _todas_las_marcas(registro) -> list[str]:
    """Marcas del registro y de sus canales (DEC-267: cada una en un solo lugar)."""
    marcas = list(registro.marcas)
    for c in registro.canales:
        marcas.extend(c.marcas)
    return marcas


# --- Constructores de observaciones -------------------------------------------------------

PROD_B1 = UUID(int=0x7140_0100)
PUB_OFERTA = UUID(int=0x7140_0101)
ID_OFERTA = UUID(int=0x7140_0102)
PUB_AMAZON = UUID(int=0x7140_0103)
PUB_CA = UUID(int=0x7140_0104)  # "Walmart"
PUB_CB = UUID(int=0x7140_0105)

_B1 = {"producto": PROD_B1, "gtin": GTIN_B1, "marca": MARCA_B1, "modelo": MODELO_B1}


def _obs(
    precio: str,
    comercio: str,
    *,
    momento: dt.datetime,
    publicacion: UUID,
    producto: UUID,
    gtin: str,
    marca: str,
    modelo: str,
    categoria: str = "tools",
    ident: UUID | None = None,
    was: str | None = None,
    estado: str = "in_stock_confirmed",
    cantidad: int | None = None,
    modo: str = "envio",
    tienda: str | None = None,
    liquidacion: bool = False,
    peso: str | None = "4.0",
    tax_location: str | None = None,
    ficha: dict | None = None,
) -> ObservacionRegistrada:
    price: dict = {"current": precio, "currency": "USD"}
    if was is not None:
        price["was"] = was
    availability: dict = {"state": estado}
    if cantidad is not None:
        availability["quantity"] = cantidad
    datos: dict = {
        "retailerCode": comercio,
        "productUrl": f"https://{_DOMINIO[comercio]}/p/{modelo.lower()}",
        "title": f"Producto sintetico {modelo}",
        "brand": marca,
        "model": modelo,
        "gtin": gtin,
        "category": categoria,
        "condition": "new",
        "price": price,
        "seller": "comercio",
        "availability": availability,
        "purchaseMode": modo,
        "isClearance": liquidacion,
        "extractedAt": momento.isoformat(),
        "blocked": False,
    }
    if peso is not None:
        datos["weightKg"] = peso
    if tienda is not None:
        datos["storeCode"] = tienda
    if tax_location is not None:
        datos["taxLocation"] = tax_location
    if ficha is not None:
        datos["amazonListing"] = ficha
    return ObservacionRegistrada(
        leer_observacion(datos),
        _uuid() if ident is None else ident,
        publicacion,
        producto,
    )


def _oferta_b1(*, peso: str = "4.0", cantidad: int = 3) -> ObservacionRegistrada:
    """B1: Home Depot Chula Vista (``tp-cv``), liquidación, herramientas, código confirmado,
    vendida por el comercio, $29.00 con tachado $129.00, "3 disponibles" hace 2 h; tasa de la
    tienda 7.75% (REQ §5)."""
    return _obs(
        "29.00",
        TIENDA_PRUEBA,
        momento=_hace(2),
        publicacion=PUB_OFERTA,
        ident=ID_OFERTA,
        was="129.00",
        estado="in_stock",
        cantidad=cantidad,
        modo="tienda",
        tienda="tp-cv",
        liquidacion=True,
        tax_location="tienda_prueba",
        peso=peso,
        **_B1,
    )


def _historial_b1(peso: str = "4.0") -> list[ObservacionRegistrada]:
    """Precio habitual $119 (8 observaciones en 6 días, 60 días de historial; la de $109 es el
    botón de compra de Amazon del día −50, en las fichas): 109, 119 × 6, 129 → mediana 119.
    La tienda de la oferta no tiene historial propio. Hoy "Walmart" (``ca``) $124 hace 8 h."""
    c = {"peso": peso, **_B1}
    return [
        _obs("119.00", "ca", momento=_hace(dias=60), publicacion=PUB_CA, **c),
        _obs("119.00", "cb", momento=_hace(dias=60), publicacion=PUB_CB, **c),
        _obs("119.00", "ca", momento=_hace(dias=40), publicacion=PUB_CA, **c),
        _obs("119.00", "ca", momento=_hace(dias=20), publicacion=PUB_CA, **c),
        _obs("129.00", "cb", momento=_hace(dias=20), publicacion=PUB_CB, **c),
        _obs("119.00", "ca", momento=_hace(dias=10), publicacion=PUB_CA, **c),
        _obs("119.00", "cb", momento=_hace(dias=3), publicacion=PUB_CB, **c),
        _obs("124.00", "ca", momento=_hace(8), publicacion=PUB_CA, **c),
    ]


def _ficha(
    momento: dt.datetime,
    *,
    buy_box: str | None,
    rank: int | None = None,
    vendedores: int | None = None,
    comprados: int | None = None,
    peso: str = "4.0",
) -> ObservacionRegistrada:
    ficha: dict = {"buyBoxPrice": buy_box}
    if rank is not None:
        ficha["rankMain"] = rank
    if vendedores is not None:
        ficha["sellersNew"] = vendedores
    if comprados is not None:
        ficha["boughtLastMonth"] = comprados
    return _obs(
        buy_box or "100.00",
        "amazon",
        momento=momento,
        publicacion=PUB_AMAZON,
        ficha=ficha,
        peso=peso,
        **_B1,
    )


#: Ranking de B1: 6,000 en los 7 días que terminan hoy y en los 7 que terminan hace 30 días.
RANKING_B1 = {**{d: 6000 for d in range(36, 29, -1)}, **{d: 6000 for d in range(6, -1, -1)}}


def _fichas(
    ranking: dict[int, int],
    *,
    vendedores: int | None = 5,
    comprados: int | None = 200,
    peso: str = "4.0",
    extra: tuple[ObservacionRegistrada, ...] = (),
) -> list[ObservacionRegistrada]:
    """Fichas de Amazon: mínimo de 60 días $109 (día −50); ``ranking`` = {días atrás: rank}
    (día 0 = hoy); la ficha de hoy (hace 2 h) trae el botón de compra $119, el rank de hoy si
    lo hay, ``vendedores`` y ``comprados``. Las de días anteriores, sin botón de compra."""
    fichas = [_ficha(_hace(dias=50), buy_box="109.00", peso=peso)]
    fichas += [
        _ficha(_hace(dias=d), buy_box=None, rank=r, peso=peso)
        for d, r in sorted(ranking.items(), reverse=True)
        if d > 0
    ]
    fichas.append(
        _ficha(
            _hace(2),
            buy_box="119.00",
            rank=ranking.get(0),
            vendedores=vendedores,
            comprados=comprados,
            peso=peso,
        )
    )
    return [*fichas, *extra]


def _contexto(
    *,
    ranking: dict[int, int] = RANKING_B1,
    vendedores: int | None = 5,
    comprados: int | None = 200,
    peso: str = "4.0",
    cantidad: int = 3,
    configuracion=CONFIG,
    fichas_extra: tuple[ObservacionRegistrada, ...] = (),
) -> ContextoEvaluacion:
    return ContextoEvaluacion(
        id_evaluacion=UUID(int=0x7140_00FF),
        instante=INSTANTE,
        configuracion=configuracion,
        id_version_configuracion=1,
        oferta=_oferta_b1(peso=peso, cantidad=cantidad),
        historial=tuple(_historial_b1(peso)),
        fichas_amazon=tuple(
            _fichas(
                ranking,
                vendedores=vendedores,
                comprados=comprados,
                peso=peso,
                extra=fichas_extra,
            )
        ),
    )


def _demanda(contexto: ContextoEvaluacion):
    return canales.demanda_en_amazon(
        Categoria.TOOLS,
        canales.ranking_amazon(contexto),
        canales.ficha_vigente(contexto),
        contexto.configuracion.contenido,
    )


def _local_como_b1(registro) -> None:
    """Venta local de B1: $91.04; neto $50.29 (160.9%); castigo $0; 2 unidades; 30 días;
    rendimiento 160.9%; Muy recomendable; total $100.58."""
    local = _canal(registro, Canal.LOCAL)
    assert local.estado is EstadoCanal.DISPONIBLE
    assert local.precio_venta == D("91.04")
    assert local.margen_neto == D("50.29")
    assert local.castigo == D("0.00")
    assert local.margen_ajustado == D("50.29")
    assert _pct(local.margen_ajustado_pct) == "160.9 %"
    assert local.unidades == 2
    assert local.dias_para_recuperar == 30
    assert _pct(local.rendimiento_mensual_pct) == "160.9 %"
    assert local.nivel is Nivel.MUY_RECOMENDABLE
    assert local.ganancia_total == D("100.58")


def _amazon_por_unidad_b1(amazon: EvaluacionCanal, *, costo_venta: str = "33.85") -> None:
    """Por unidad, Amazon como B1: venta $119, comisión $17.85 + envío + empaque, devoluciones
    $4.17 (119 × 7% × 50% = 4.165), castigo $5.00 (50% × (119 − 109))."""
    assert amazon.precio_venta == D("119.00")
    assert amazon.costo_venta == D(costo_venta)
    assert amazon.costo_devoluciones == D("4.17")
    assert amazon.castigo == D("5.00")


# =========================================================================================
# B10 (a) — Sin ranking (0 días): Amazon por revisar, nivel en venta local
# =========================================================================================


@pytest.fixture(scope="module")
def contexto_b10a():
    return _contexto(ranking={})


@pytest.fixture(scope="module")
def registro_b10a(contexto_b10a):
    return motor.evaluar(contexto_b10a)


@pytest.mark.scenario("B10 (a)")
def test_b10a_ranking_sin_datos_y_demanda_desconocida(contexto_b10a):
    """0 días de datos → sin ranking (DEC-206); con 5 vendedores y sin ranking, la demanda es
    DESCONOCIDA, no INSUFICIENTE (DEC-270; design.md §10 punto 15)."""
    ranking = canales.ranking_amazon(contexto_b10a)
    assert ranking.dias_con_datos == 0
    assert ranking.promedio is None
    demanda = _demanda(contexto_b10a)
    assert demanda.demanda is DemandaAmazon.DESCONOCIDA
    assert demanda.a_la_baja is False
    assert demanda.empeoramiento_pct is None


@pytest.mark.scenario("B10 (a)")
def test_b10a_amazon_por_revisar_con_margen_y_nivel_calculado(registro_b10a):
    """Amazon **por revisar** (`DEMANDA DESCONOCIDA`). En un canal por revisar: margen neto,
    margen ajustado y `nivel_calculado` informativo; sin unidades, días ni rendimiento
    (REQ §3.2 paso 7, §3.2.1, S-30). Los números por unidad son los de B1 ($44.73, 143.1%,
    Muy recomendable, como dice B11 con los mismos datos)."""
    amazon = _canal(registro_b10a, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.POR_REVISAR
    assert amazon.causas_por_revisar == (CausaCanalPorRevisar.DEMANDA_DESCONOCIDA,)
    assert amazon.causas_cerrado == ()
    _amazon_por_unidad_b1(amazon)
    assert amazon.margen_neto == D("53.90")
    assert _pct(amazon.margen_neto_pct) == "172.5 %"
    assert amazon.margen_ajustado == D("44.73")
    assert _pct(amazon.margen_ajustado_pct) == "143.1 %"
    assert amazon.nivel_calculado is Nivel.MUY_RECOMENDABLE
    assert amazon.nivel is None
    assert amazon.unidades is None
    assert amazon.dias_para_recuperar is None
    assert amazon.rendimiento_mensual_pct is None
    assert amazon.ganancia_total is None
    # DEC-266: una causa de por revisar no es marca.
    assert CausaCanalPorRevisar.DEMANDA_DESCONOCIDA.value not in _todas_las_marcas(registro_b10a)


@pytest.mark.scenario("B10 (a)")
def test_b10a_venta_local_tope_3_dos_unidades(registro_b10a):
    """Local: tope 3 → 2 unidades, $50.29 por unidad, total **$100.58**, Muy recomendable."""
    _local_como_b1(registro_b10a)
    # Sin ranking, el tope es el normal (3): el aumento a 5 exige ranking < 10,000.
    assert (
        rentabilidad.tope_primera_compra(
            None, Nivel.MUY_RECOMENDABLE, PARAMS.amazon.first_purchase_cap
        )
        == 3
    )


@pytest.mark.scenario("B10 (a)")
def test_b10a_resultado_nivel_asignado_venta_local(registro_b10a):
    """`DEMANDA DESCONOCIDA` **no es motivo** porque el otro canal tiene nivel (§3.2.3);
    resultado `NIVEL_ASIGNADO` = **Muy recomendable, venta local**; Amazon "por revisar" no
    entra en la elección (S-30) ni en el nivel del aviso (S-33: canales con nivel)."""
    assert registro_b10a.resultado is Resultado.NIVEL_ASIGNADO
    assert Motivo.DEMANDA_DESCONOCIDA not in registro_b10a.motivos
    assert registro_b10a.motivos == ()
    assert registro_b10a.motivo_principal is None
    assert registro_b10a.canal_elegido is Canal.LOCAL
    assert registro_b10a.nivel_aviso is Nivel.MUY_RECOMENDABLE
    assert registro_b10a.canal_aviso is Canal.LOCAL


# =========================================================================================
# B10 (b) — Ranking con 3 días: 9,000, 12,000 y 15,000 → promedio 12,000
# =========================================================================================


@pytest.fixture(scope="module")
def contexto_b10b():
    return _contexto(ranking={2: 9000, 1: 12000, 0: 15000})


@pytest.fixture(scope="module")
def registro_b10b(contexto_b10b):
    return motor.evaluar(contexto_b10b)


@pytest.mark.scenario("B10 (b)")
def test_b10b_promedio_de_los_dias_disponibles(contexto_b10b):
    """1 a 6 días → promedio de los disponibles: (9,000 + 12,000 + 15,000) ÷ 3 = **12,000**;
    umbral: 12,000 ≤ 168,440 → SUFICIENTE; sin dato de hace 30 días no se evalúa
    `DEMANDA A LA BAJA`."""
    ranking = canales.ranking_amazon(contexto_b10b)
    assert ranking.dias_con_datos == 3
    assert ranking.promedio == D(12000)
    assert ranking.promedio_hace_30_dias is None
    demanda = _demanda(contexto_b10b)
    assert demanda.demanda is DemandaAmazon.SUFICIENTE
    assert demanda.a_la_baja is False
    assert demanda.empeoramiento_pct is None


@pytest.mark.scenario("B10 (b)")
def test_b10b_mismo_ranking_para_dias_y_tope(registro_b10b):
    """Días de venta (10,000 a 50,000 → 21; 21 + 30 = 51) y tope (12,000 no es < 10,000 →
    tope 3) con el mismo promedio. Amazon: ajustado $44.73 (143.1%); unidades mín(33, 3, 3)
    = **3**; rendimiento 143.1% × 30 ÷ 51 = **84.2%**; Muy recomendable; total **$134.19**."""
    amazon = _canal(registro_b10b, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.DISPONIBLE
    _amazon_por_unidad_b1(amazon)
    assert amazon.margen_neto == D("53.90")
    assert amazon.margen_ajustado == D("44.73")
    assert _pct(amazon.margen_ajustado_pct) == "143.1 %"
    assert amazon.unidades == 3
    assert amazon.dias_para_recuperar == 51
    assert _pct(amazon.rendimiento_mensual_pct) == "84.2 %"
    # Sin redondear (DEC-060): exactamente margen ajustado % × 30 ÷ 51.
    assert amazon.rendimiento_mensual_pct == amazon.margen_ajustado_pct * 30 / 51
    assert amazon.nivel is Nivel.MUY_RECOMENDABLE
    assert amazon.ganancia_total == D("134.19")
    assert (
        rentabilidad.tope_primera_compra(
            D(12000), Nivel.MUY_RECOMENDABLE, PARAMS.amazon.first_purchase_cap
        )
        == 3
    )
    assert Marca.DEMANDA_A_LA_BAJA.value not in _todas_las_marcas(registro_b10b)


@pytest.mark.scenario("B10 (b)")
def test_b10b_resultado_amazon(registro_b10b):
    """Local como B1 ($100.58). Diferencia (134.19 − 100.58) ÷ 134.19 = 25.0% → resultado
    `NIVEL_ASIGNADO` = **Muy recomendable, Amazon**."""
    _local_como_b1(registro_b10b)
    assert registro_b10b.resultado is Resultado.NIVEL_ASIGNADO
    assert registro_b10b.motivos == ()
    assert registro_b10b.canal_elegido is Canal.AMAZON
    assert registro_b10b.nivel_aviso is Nivel.MUY_RECOMENDABLE


# =========================================================================================
# B12 — Sin ventas al mes: cambia el canal
# =========================================================================================


@pytest.fixture(scope="module")
def registro_b12():
    return motor.evaluar(_contexto(comprados=None))


@pytest.mark.scenario("B12")
def test_b12_amazon_dos_unidades_estimadas(registro_b12):
    """Amazon: unidades mín(2, 3, 5) = **2**, marca `ESTIMADO (unidades)`, días 7 + 30,
    rendimiento 116.1%, total $89.46 (RN-005 §11: sin ventas al mes, máximo 2)."""
    amazon = _canal(registro_b12, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.DISPONIBLE
    _amazon_por_unidad_b1(amazon)
    assert amazon.margen_ajustado == D("44.73")
    assert amazon.unidades == 2
    assert amazon.dias_para_recuperar == 37
    assert _pct(amazon.rendimiento_mensual_pct) == "116.1 %"
    assert amazon.nivel is Nivel.MUY_RECOMENDABLE
    assert amazon.ganancia_total == D("89.46")
    assert marca_estimado("unidades") in amazon.marcas
    # DEC-267: una marca en un solo lugar; la venta local sí tiene ventas al mes (RN-017).
    assert _todas_las_marcas(registro_b12).count(marca_estimado("unidades")) == 1
    # Con ranking 6,000 y Muy recomendable el tope es 5: limita el máximo sin ventas (2).
    assert (
        rentabilidad.tope_primera_compra(
            D(6000), Nivel.MUY_RECOMENDABLE, PARAMS.amazon.first_purchase_cap
        )
        == 5
    )
    assert rentabilidad.unidades_recomendadas(None, 3, None, 5, 2) == 2


@pytest.mark.scenario("B12")
def test_b12_resultado_venta_local(registro_b12):
    """Local total $100.58; diferencia (100.58 − 89.46) ÷ 100.58 = 11.1% → **venta local**;
    resultado `NIVEL_ASIGNADO` = **Muy recomendable, venta local**."""
    _local_como_b1(registro_b12)
    assert registro_b12.resultado is Resultado.NIVEL_ASIGNADO
    assert registro_b12.motivos == ()
    assert registro_b12.canal_elegido is Canal.LOCAL
    assert registro_b12.nivel_aviso is Nivel.MUY_RECOMENDABLE
    # Empate de nivel entre los canales: el del canal elegido (design.md §10 punto 6).
    assert registro_b12.canal_aviso is Canal.LOCAL


# =========================================================================================
# B13 — Demanda a la baja: hoy 30,000, hace 30 días 18,000, 10 vendedores
# =========================================================================================

RANKING_B13 = {**{d: 18000 for d in range(36, 29, -1)}, **{d: 30000 for d in range(6, -1, -1)}}


@pytest.fixture(scope="module")
def contexto_b13():
    return _contexto(ranking=RANKING_B13, vendedores=10)


@pytest.fixture(scope="module")
def registro_b13(contexto_b13):
    return motor.evaluar(contexto_b13)


@pytest.mark.scenario("B13")
def test_b13_suficiente_con_demanda_a_la_baja(contexto_b13, registro_b13):
    """SUFICIENTE con `DEMANDA A LA BAJA` (66.7%): (30,000 − 18,000) ÷ 18,000 > 50%
    (RN-004 §4, ejemplo D)."""
    ranking = canales.ranking_amazon(contexto_b13)
    assert ranking.promedio == D(30000)
    assert ranking.dias_con_datos == 7
    assert ranking.promedio_hace_30_dias == D(18000)
    demanda = _demanda(contexto_b13)
    assert demanda.demanda is DemandaAmazon.SUFICIENTE
    assert demanda.a_la_baja is True
    assert _pct(demanda.empeoramiento_pct) == "66.7 %"
    assert D("66.66") < demanda.empeoramiento_pct < D("66.67")
    marcas = _todas_las_marcas(registro_b13)
    assert marcas.count(Marca.DEMANDA_A_LA_BAJA.value) == 1
    # Advertencia, no descarta: Amazon sigue disponible.
    assert _canal(registro_b13, Canal.AMAZON).estado is EstadoCanal.DISPONIBLE


@pytest.mark.scenario("B13")
def test_b13_unidades_dias_y_rendimiento(registro_b13):
    """Unidades mín(200 ÷ 11 = 18, 3, tope 3) = 3; días 21 + 30 = 51; rendimiento
    **84.2%**."""
    amazon = _canal(registro_b13, Canal.AMAZON)
    _amazon_por_unidad_b1(amazon)
    assert amazon.margen_ajustado == D("44.73")
    assert amazon.unidades == 3
    assert amazon.dias_para_recuperar == 51
    assert _pct(amazon.rendimiento_mensual_pct) == "84.2 %"
    assert amazon.nivel is Nivel.MUY_RECOMENDABLE
    assert amazon.ganancia_total == D("134.19")


@pytest.mark.scenario("B13")
def test_b13_resultado_amazon(registro_b13):
    """Resultado `NIVEL_ASIGNADO` = **Muy recomendable, Amazon** (134.19 contra 100.58)."""
    _local_como_b1(registro_b13)
    assert registro_b13.resultado is Resultado.NIVEL_ASIGNADO
    assert registro_b13.motivos == ()
    assert registro_b13.canal_elegido is Canal.AMAZON
    assert registro_b13.nivel_aviso is Nivel.MUY_RECOMENDABLE


# =========================================================================================
# B26 — Más de 6 kg: (a) sin cotización; (b) con cotización capturada de $22
# =========================================================================================


@pytest.fixture(scope="module")
def registro_b26a():
    return motor.evaluar(_contexto(peso="8.0"))


@pytest.fixture(scope="module")
def registro_b26b():
    return motor.evaluar(_contexto(peso="8.0", configuracion=CONFIG_COTIZACION))


@pytest.mark.scenario("B26 (a)")
def test_b26a_amazon_cerrado_envio_por_cotizar(registro_b26a):
    """(a) Amazon cerrado (`ENVÍO POR COTIZAR`): sin RN-005 ni nivel; un canal cerrado no
    tiene `nivel_calculado` (§3.2.1, §3.2.2; DEC-224 a). La causa se registra también como
    marca (§3.2.3), en un solo lugar (DEC-267)."""
    amazon = _canal(registro_b26a, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.CERRADO
    assert amazon.causas_cerrado == (CausaCanalCerrado.ENVIO_POR_COTIZAR,)
    assert amazon.causas_por_revisar == ()
    assert amazon.nivel is None
    assert amazon.nivel_calculado is None
    assert amazon.unidades is None
    assert amazon.rendimiento_mensual_pct is None
    assert amazon.ganancia_total is None
    assert amazon.margen_ajustado is None
    marcas = _todas_las_marcas(registro_b26a)
    assert marcas.count(CausaCanalCerrado.ENVIO_POR_COTIZAR.value) == 1


@pytest.mark.scenario("B26 (a)")
def test_b26a_resultado_venta_local(registro_b26a):
    """→ `NIVEL_ASIGNADO` = **Muy recomendable, venta local**."""
    _local_como_b1(registro_b26a)
    assert registro_b26a.resultado is Resultado.NIVEL_ASIGNADO
    assert registro_b26a.motivos == ()
    assert registro_b26a.canal_elegido is Canal.LOCAL
    assert registro_b26a.nivel_aviso is Nivel.MUY_RECOMENDABLE
    assert registro_b26a.canal_aviso is Canal.LOCAL


@pytest.mark.scenario("B26 (b)")
def test_b26b_amazon_con_cotizacion(registro_b26b):
    """(b) costo de venta 17.85 + 22 + 2 = $41.85; neto $45.90; ajustado **$36.73 (117.5%)**;
    3 unidades, total **$110.19**, rendimiento 95.3%."""
    amazon = _canal(registro_b26b, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.DISPONIBLE
    assert amazon.causas_cerrado == ()
    _amazon_por_unidad_b1(amazon, costo_venta="41.85")
    assert amazon.margen_neto == D("45.90")
    assert amazon.margen_ajustado == D("36.73")
    assert _pct(amazon.margen_ajustado_pct) == "117.5 %"
    assert amazon.unidades == 3
    assert amazon.dias_para_recuperar == 37
    assert _pct(amazon.rendimiento_mensual_pct) == "95.3 %"
    assert amazon.nivel is Nivel.MUY_RECOMENDABLE
    assert amazon.ganancia_total == D("110.19")
    assert CausaCanalCerrado.ENVIO_POR_COTIZAR.value not in _todas_las_marcas(registro_b26b)
    # La cotización capturada no es un peso estimado (S-06).
    assert marca_estimado("peso") not in _todas_las_marcas(registro_b26b)


@pytest.mark.scenario("B26 (b)")
def test_b26b_desempate_por_rendimiento_venta_local(registro_b26b):
    """Local $100.58, rendimiento 160.9%; diferencia (110.19 − 100.58) ÷ 110.19 = 8.7% < 10%
    → desempata el rendimiento → **venta local, Muy recomendable** (RN-018 §4, DEC-170)."""
    _local_como_b1(registro_b26b)
    amazon = _canal(registro_b26b, Canal.AMAZON)
    local = _canal(registro_b26b, Canal.LOCAL)
    diferencia = (amazon.ganancia_total - local.ganancia_total) / amazon.ganancia_total * 100
    assert _pct(diferencia) == "8.7 %"
    assert registro_b26b.resultado is Resultado.NIVEL_ASIGNADO
    assert registro_b26b.motivos == ()
    assert registro_b26b.canal_elegido is Canal.LOCAL
    assert registro_b26b.nivel_aviso is Nivel.MUY_RECOMENDABLE
    assert registro_b26b.canal_aviso is Canal.LOCAL


@pytest.mark.scenario("B26 (b)")
def test_b26b_envio_con_la_cotizacion_del_producto():
    """`envio_amazon`: con más de 6 kg usa la cotización capturada del producto ($22) y el
    empaque de más de 1 kg ($2, REQ §5)."""
    oferta = _oferta_b1(peso="8.0").observacion
    envio = canales.envio_amazon(oferta, CONFIG_COTIZACION.contenido.shipping)
    assert envio is not None
    assert envio.envio == D("22.00")
    assert envio.empaque == D("2.00")
    assert envio.peso_estimado is False
    assert canales.envio_amazon(oferta, CONFIG.contenido.shipping) is None


# =========================================================================================
# Bordes de las reglas (sin marcador de escenario)
# =========================================================================================


def test_ranking_ventana_de_7_dias_que_terminan_hoy():
    """design.md §10 punto 3: la ventana son los 7 días que terminan el día evaluado
    (incluido). Un rank del día −7 queda fuera y no mueve el promedio de B1 (6,000)."""
    contexto = _contexto(ranking={**RANKING_B1, 7: 500000})
    ranking = canales.ranking_amazon(contexto)
    assert ranking.dias_con_datos == 7
    assert ranking.promedio == D(6000)


def test_ranking_cuenta_la_ultima_del_dia():
    """Una observación por día, la última (design.md §10 punto 3): una ficha de hoy más
    temprana con rank 90,000 no cuenta; la de hace 2 h (6,000) sí."""
    temprana = _ficha(_hace(10), buy_box=None, rank=90000)
    contexto = _contexto(fichas_extra=(temprana,))
    ranking = canales.ranking_amazon(contexto)
    assert ranking.dias_con_datos == 7
    assert ranking.promedio == D(6000)


def test_ranking_ventana_hace_30_dias():
    """'Hace 30 días' = los 7 días que terminan 30 días antes (días −36 a −30). Un rank del
    día −37 o del día −29 no cuenta."""
    contexto = _contexto(ranking={**RANKING_B13, 37: 1, 29: 1})
    ranking = canales.ranking_amazon(contexto)
    assert ranking.promedio_hace_30_dias == D(18000)


def test_demanda_a_la_baja_exige_mas_de_50_por_ciento():
    """RN-004 §4: "empeoró **más de** 50%". 27,000 contra 18,000 = 50.0% exacto → sin
    advertencia."""
    ranking = {**{d: 18000 for d in range(36, 29, -1)}, **{d: 27000 for d in range(6, -1, -1)}}
    demanda = _demanda(_contexto(ranking=ranking))
    assert demanda.empeoramiento_pct == D(50)
    assert demanda.a_la_baja is False
    assert demanda.demanda is DemandaAmazon.SUFICIENTE


def test_ranking_que_mejora_no_es_demanda_a_la_baja():
    """Un ranking menor es mejor: 6,000 hoy contra 18,000 hace 30 días no es a la baja."""
    ranking = {**{d: 18000 for d in range(36, 29, -1)}, **{d: 6000 for d in range(6, -1, -1)}}
    demanda = _demanda(_contexto(ranking=ranking))
    assert demanda.a_la_baja is False


def test_envio_6_kg_exactos_usa_la_tabla():
    """REQ §5: "> 3 y ≤ 6 kg $14"; con 6 kg exactos no hace falta cotización (S-06)."""
    oferta = _oferta_b1(peso="6.0").observacion
    envio = canales.envio_amazon(oferta, CONFIG.contenido.shipping)
    assert envio is not None
    assert envio.envio == D("14.00")
    assert envio.empaque == D("2.00")


def test_envio_mas_de_6_kg_sin_cotizacion_del_producto():
    """Una cotización de **otro** producto no vale: más de 6 kg sigue sin envío."""
    oferta = _oferta_b1(peso="6.01").observacion
    assert canales.envio_amazon(oferta, CONFIG_COTIZACION_OTRO.contenido.shipping) is None
    registro = motor.evaluar(_contexto(peso="6.01", configuracion=CONFIG_COTIZACION_OTRO))
    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.causas_cerrado == (CausaCanalCerrado.ENVIO_POR_COTIZAR,)


def _canal_con(canal: Canal, ganancia: str, rendimiento: str, unidades: int = 3):
    return EvaluacionCanal(
        canal=canal,
        estado=EstadoCanal.DISPONIBLE,
        precio_venta=D("100.00"),
        costo_venta=D("10.00"),
        margen_neto=D("50.00"),
        margen_neto_pct=D("100"),
        costo_devoluciones=D("0.00"),
        castigo=D("0.00"),
        margen_ajustado=D("50.00"),
        margen_ajustado_pct=D("100"),
        unidades=unidades,
        dias_para_recuperar=30,
        rendimiento_mensual_pct=D(rendimiento),
        nivel=Nivel.MUY_RECOMENDABLE,
        nivel_calculado=Nivel.MUY_RECOMENDABLE,
        ganancia_total=D(ganancia),
    )


def test_desempate_con_diferencia_de_10_por_ciento_exacto_gana_la_ganancia():
    """RN-018 §4: desempata el rendimiento si la diferencia es **menor de** 10%. Con 10.0%
    exacto (100 contra 90) gana la mayor ganancia total, aunque tenga menos rendimiento."""
    amazon = _canal_con(Canal.AMAZON, "100.00", "50")
    local = _canal_con(Canal.LOCAL, "90.00", "150")
    desempate = PARAMS.levels.channel_tiebreak_pct
    assert eleccion.canal_elegido((amazon, local), desempate) is Canal.AMAZON
    # Con 9.9% (100 contra 90.10) desempata el rendimiento.
    local_cerca = _canal_con(Canal.LOCAL, "90.10", "150")
    assert eleccion.canal_elegido((amazon, local_cerca), desempate) is Canal.LOCAL


# --- Riesgo señalado por el developer: 0 unidades (DEC-259) con dos canales con nivel -------


@pytest.mark.xfail(
    strict=True,
    raises=ValueError,
    reason=(
        "Riesgo DEC-259: con 0 unidades un canal con nivel queda sin rendimiento; con dos "
        "canales con nivel y ganancia 0 el desempate de RN-018 lanza ValueError"
    ),
)
def test_cero_disponibles_no_rompe_la_evaluacion():
    """B1 con "0 disponibles" en la tienda (dato válido del contrato: ``quantity`` ≥ 0).
    Las unidades de los dos canales son mín(…, 0, …) = 0; con 0 unidades no hay días ni
    rendimiento (DEC-259) y la ganancia total es $0.00 en los dos. Ninguna fuente dice que
    eso detenga la evaluación: el motor debe dar un registro."""
    registro = motor.evaluar(_contexto(cantidad=0))
    assert registro.resultado is not None
