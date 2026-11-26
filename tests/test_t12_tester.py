"""Pruebas independientes de oip-tester para T12 (variantes de B2: B2 base, B15, B16, B17).

Capacidad ``canales-y-margen``; REQ-2026-0001 v2.9 §3.2 pasos 6 a 9, §3.2.1, §3.2.3, §5
(configuración base, redondeo y escenarios B2, B15, B16, B17) y §13 S-05 y S-06; RN-001 v2,
RN-005 v2 §4 y §11, RN-006 v2 §4.1, §4.2 y §11, RN-009 v2, RN-016 v1 §4 y §11 y RN-017 v1;
design.md CMP-13, CMP-14, PAR-06, PAR-09, PAR-11, PAR-12, §8, §9 y §10 (puntos 9 y 14);
DEC-260 (techo con activos y vendidos, provisional), DEC-266, DEC-267 y DEC-269.

Escritas por adelantado (DEC-252, etapa 2) **sin ver la implementación de T12**: con la
interfaz pública de main (firmas y tipos) y las fuentes. Los datos y resultados esperados se
copian del REQ y de las RN, no del código.

Fixtures sintéticos (DEC-194): ``tienda-prueba`` (la sucursal ``tp-cv`` es "Home Depot Chula
Vista" de B2) y ``tienda-prueba-2`` (en línea, es "Walmart" de B2), con dominios de
example.com; la ficha de Amazon es el comercio ``amazon`` de la base con una URL sintética que
nadie abre. Instante explícito en ``America/Tijuana`` (PAR-01), sin reloj, sin red y sin
aleatoriedad.

B15 tiene una contradicción abierta (issue #34, comentario 7177510987): con la lectura vigente
de ``minimo_60_dias_amazon`` (cuenta el botón de compra de hoy, como exigen B2 b y B9 b) y el
botón de compra de $149 de hoy, el mínimo de 60 días siempre existe. La regla S-05 se prueba
como unidad; el escenario de punta a punta queda en ``xfail(strict=True)`` hasta que Jesús
decida, sin debilitar la aserción.
"""

from __future__ import annotations

import datetime as dt
import itertools
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from config_tienda_prueba import (
    BASE,
    SUCURSAL_PRUEBA,
    TIENDA_PRUEBA,
    TIENDA_PRUEBA_2,
    con_sucursales_prueba,
)
from oip.catalogos import (
    CalidadPrecio,
    Canal,
    CausaCanalCerrado,
    Confianza,
    EstadoCanal,
    Marca,
    Motivo,
    Nivel,
    Resultado,
    marca_estimado,
)
from oip.configuracion import cargar_configuracion_texto
from oip.dinero import formatear_porcentaje
from oip.entradas.capturas import leer_captura
from oip.entradas.contrato import leer_observacion
from oip.evaluacion import canales, motor, referencias, rentabilidad
from oip.evaluacion.canales import CanalEvaluado
from oip.evaluacion.contexto import (
    ContextoEvaluacion,
    EvaluacionCanal,
    ObservacionRegistrada,
)

D = Decimal
TIJUANA = ZoneInfo("America/Tijuana")
INSTANTE = dt.datetime(2026, 11, 16, 14, 0, tzinfo=TIJUANA)  # día 0 de B2

URL_B15_34 = (
    "https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/issues/34"
    "#issuecomment-7177510987"
)

# --- Configuración: base de los escenarios + sucursales sintéticas ------------------------
# Para las pruebas del techo se agrega una ciudad FUERA de la zona de venta local (PAR-09,
# ``in_local_sale_zone: false``), como los comparables de Houston de RN-016 §5.
_CIUDAD_FUERA = "    houston: {pickup_km: 10, pickup_hours: 0.5, in_local_sale_zone: false}\n"
_ANCLA_CIUDADES = "  cities:                            # recogida B18: 10 km y 0.5 h = $9.50\n"


def _texto() -> str:
    texto = con_sucursales_prueba(BASE.read_text(encoding="utf-8"))
    assert texto.count(_ANCLA_CIUDADES) == 1
    return texto.replace(_ANCLA_CIUDADES, _ANCLA_CIUDADES + _CIUDAD_FUERA, 1)


CONFIG = cargar_configuracion_texto(_texto(), origen="t12-tester")
PARAMS = CONFIG.contenido

_DOMINIO = {
    TIENDA_PRUEBA: "example.com",
    TIENDA_PRUEBA_2: "otra.example.com",
    "amazon": "amazon.example.com",
}

PRODUCTO = UUID(int=0x7120_0000)
PUB_OFERTA = UUID(int=0x7120_0001)  # la publicación de la sucursal tp-cv
ID_OFERTA = UUID(int=0x7120_0002)
PUB_AMAZON = UUID(int=0x7120_0003)
PUB_TP_LINEA = UUID(int=0x7120_0004)  # otra publicación de la misma cadena (en línea)
PUB_TP2 = UUID(int=0x7120_0005)  # "Walmart" en línea
GTIN_B2 = "036000291452"  # UPC-A con dígito verificador válido
MARCA_B2 = "MarcaT"
MODELO_B2 = "TL-12"
URL_OFERTA = "https://example.com/p/taladro-t12"

_ids = itertools.count(0x7120_1000)


def _uuid() -> UUID:
    return UUID(int=next(_ids))


def _hace(horas: float = 0, dias: int = 0) -> dt.datetime:
    return INSTANTE - dt.timedelta(days=dias, hours=horas)


def _cerca(valor: Decimal | None, esperado: Decimal) -> bool:
    """Porcentaje sin redondear igual al esperado (exacto salvo el último dígito del
    contexto decimal de 28 dígitos)."""
    assert isinstance(valor, Decimal), f"se esperaba Decimal, llegó {type(valor).__name__}"
    return abs(valor - esperado) < D("1e-20")


def _pct(valor: Decimal | None) -> str:
    assert isinstance(valor, Decimal)
    return formatear_porcentaje(valor)


# --- Observaciones --------------------------------------------------------------------------


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
    peso: str | None = "2.0",
    categoria: str = "tools",
    tax_location: str | None = None,
    ficha: dict | None = None,
    url: str | None = None,
) -> ObservacionRegistrada:
    price: dict = {"current": precio, "currency": "USD"}
    if was is not None:
        price["was"] = was
    availability: dict = {"state": estado}
    if cantidad is not None:
        availability["quantity"] = cantidad
    datos: dict = {
        "retailerCode": comercio,
        "productUrl": url or f"https://{_DOMINIO[comercio]}/p/taladro-t12",
        "title": "Taladro sintetico T12",
        "brand": MARCA_B2,
        "model": MODELO_B2,
        "gtin": GTIN_B2,
        "category": categoria,
        "condition": "new",
        "price": price,
        "seller": "comercio",
        "availability": availability,
        "purchaseMode": modo,
        "extractedAt": momento.isoformat(),
        "blocked": False,
        "isClearance": False,
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
        PRODUCTO,
    )


def _oferta_b2(*, peso: str | None = "2.0", categoria: str = "tools") -> ObservacionRegistrada:
    """B2: Home Depot Chula Vista (sucursal ``tp-cv``), no liquidación, 2 kg, código
    confirmado, vendida por el comercio, $79.00 con tachado $199.00, "4 disponibles" hace
    2 h; tasa de la tienda 7.75% (REQ §5)."""
    return _obs(
        "79.00",
        TIENDA_PRUEBA,
        momento=_hace(2),
        publicacion=PUB_OFERTA,
        ident=ID_OFERTA,
        was="199.00",
        estado="in_stock",
        cantidad=4,
        modo="tienda",
        tienda=SUCURSAL_PRUEBA,
        peso=peso,
        categoria=categoria,
        tax_location="tienda_prueba",
        url=URL_OFERTA,
    )


def _historial_b2(categoria: str = "tools") -> list[ObservacionRegistrada]:
    """Precio típico de Home Depot en 60 días $149 con historial suficiente (5 observaciones
    de la misma cadena en 5 días, otra publicación: la de la oferta no tiene historial, así
    que no hay baja ni episodio); precio habitual $149 con 8 observaciones en 6 días (las 5
    de la cadena, $139 del botón de compra de Amazon del día −40, que va en las fichas, y
    "Walmart" $149 el día −30 y $155 el día −5): 139, 149 × 6, 155 → mediana 149. Hoy
    "Walmart" $152 hace 6 h, disponible confirmada."""
    tp = [
        _obs(
            "149.00",
            TIENDA_PRUEBA,
            momento=_hace(dias=d),
            publicacion=PUB_TP_LINEA,
            categoria=categoria,
        )
        for d in (50, 40, 30, 20, 10)
    ]
    otros = [
        _obs(
            "149.00",
            TIENDA_PRUEBA_2,
            momento=_hace(dias=30),
            publicacion=PUB_TP2,
            categoria=categoria,
        ),
        _obs(
            "155.00",
            TIENDA_PRUEBA_2,
            momento=_hace(dias=5),
            publicacion=PUB_TP2,
            categoria=categoria,
        ),
        _obs("152.00", TIENDA_PRUEBA_2, momento=_hace(6), publicacion=PUB_TP2, categoria=categoria),
    ]
    return tp + otros


def _ficha(
    momento: dt.datetime,
    *,
    buy_box: str | None = None,
    rank: int | None = 8500,
    vendedores: int | None = 9,
    comprados: int | None = 300,
    categoria: str = "tools",
) -> ObservacionRegistrada:
    ficha: dict = {"buyBoxPrice": buy_box}
    if rank is not None:
        ficha["rankMain"] = rank
    if vendedores is not None:
        ficha["sellersNew"] = vendedores
    if comprados is not None:
        ficha["boughtLastMonth"] = comprados
    return _obs(
        buy_box or "149.00",
        "amazon",
        momento=momento,
        publicacion=PUB_AMAZON,
        ficha=ficha,
        categoria=categoria,
    )


def _fichas_b2(*, con_minimo_139: bool = True, categoria: str = "tools") -> list:
    """Ficha de Amazon de B2: botón de compra hoy $149 (hace 2 h); mínimo de 60 días $139
    (botón de compra del día −40); ranking 8,500 (promedio de 7 días, días −6 a 0) y hace 30
    días 8,000 (días −36 a −30); 9 vendedores y 300 comprados en la ficha más reciente. Las
    fichas de ranking no traen botón de compra, para no sumar al precio habitual."""
    fichas = []
    if con_minimo_139:
        fichas.append(_ficha(_hace(dias=40), buy_box="139.00", rank=None, categoria=categoria))
    fichas += [_ficha(_hace(dias=d), rank=8000, categoria=categoria) for d in range(36, 29, -1)]
    fichas += [_ficha(_hace(dias=d), rank=8500, categoria=categoria) for d in range(6, 0, -1)]
    fichas.append(_ficha(_hace(2), buy_box="149.00", categoria=categoria))
    return fichas


def _comparable(
    precio: str,
    *,
    ciudad: str = "san_diego",
    condicion: str = "new",
    vendido: bool = False,
    modelo: str = MODELO_B2,
):
    datos = {
        "brand": MARCA_B2,
        "model": modelo,
        "condition": condicion,
        "askingPrice": precio,
        "currency": "USD",
        "city": ciudad,
        "date": "2026-11-10",
        "sold": vendido,
    }
    return leer_captura("local_comparable", datos, zona=TIJUANA)


def _estimado(precio: str):
    datos = {"brand": MARCA_B2, "model": MODELO_B2, "price": precio, "date": "2026-11-10"}
    return leer_captura("local_estimate", datos, zona=TIJUANA)


#: Comparables locales de B2: $135, $139 y $150, del mismo producto y estado (nuevo), en
#: San Diego (zona de venta local, PAR-09), activos.
COMPARABLES_B2 = ("135.00", "139.00", "150.00")


def _contexto(
    *,
    oferta: ObservacionRegistrada | None = None,
    categoria: str = "tools",
    fichas=None,
    comparables=None,
    estimados=None,
) -> ContextoEvaluacion:
    return ContextoEvaluacion(
        id_evaluacion=UUID(int=0x7120_00FF),
        instante=INSTANTE,
        configuracion=CONFIG,
        id_version_configuracion=1,
        oferta=_oferta_b2(categoria=categoria) if oferta is None else oferta,
        historial=tuple(_historial_b2(categoria)),
        fichas_amazon=tuple(_fichas_b2(categoria=categoria) if fichas is None else fichas),
        comparables=tuple(
            (_comparable(p) for p in COMPARABLES_B2) if comparables is None else comparables
        ),
        estimados=tuple((_estimado("129.00"),) if estimados is None else estimados),
    )


def _canal(registro, canal: Canal) -> EvaluacionCanal:
    encontrados = [c for c in registro.canales if c.canal is canal]
    assert len(encontrados) == 1, f"se esperaba un canal {canal}: {registro.canales!r}"
    return encontrados[0]


#: Costo de compra de B2: 79 + 79 × 7.75% (6.1225 → 6.12) = $85.12.
COMPRA_B2 = D("85.12")
#: Descuento real de B2 sin redondear: (149 − 79) ÷ 149 × 100 = 46.979…
REAL_B2 = (D("149") - D("79")) / D("149") * 100


def _pct_compra(monto: str) -> Decimal:
    return D(monto) / COMPRA_B2 * 100


def _verificar_local_b2(loc: EvaluacionCanal) -> None:
    """Venta local de B2 (REQ §5 B2): techo $135 → pedido $129 → venta $116.10; entrega
    $9.50; neto $21.48 (25.2%); castigo $0 (116.10 < 139); 2 unidades; 30 días; rendimiento
    25.2%; mínimo mayor(10, 8.51) = $10 ✓ → Vigilar; total $42.96."""
    assert loc.estado is EstadoCanal.DISPONIBLE
    assert loc.causas_cerrado == () and loc.causas_por_revisar == ()
    assert loc.precio_venta == D("116.10")
    assert loc.costo_venta == D("9.50")
    assert loc.margen_neto == D("21.48")
    assert _cerca(loc.margen_neto_pct, _pct_compra("21.48"))
    assert _pct(loc.margen_neto_pct) == "25.2 %"
    assert loc.castigo == D("0")
    assert loc.margen_ajustado == D("21.48")
    assert _cerca(loc.margen_ajustado_pct, _pct_compra("21.48"))
    assert loc.unidades == 2
    assert loc.dias_para_recuperar == 30
    assert _cerca(loc.rendimiento_mensual_pct, _pct_compra("21.48"))
    assert _pct(loc.rendimiento_mensual_pct) == "25.2 %"
    assert loc.nivel is Nivel.VIGILAR
    assert loc.ganancia_total == D("42.96")
    # Hay comparables en la zona: no lleva SIN COMPARABLES LOCALES (RN-016 §11).
    assert Marca.SIN_COMPARABLES_LOCALES.value not in loc.marcas


def _verificar_resultado_vigilar_local(registro) -> None:
    assert registro.resultado is Resultado.NIVEL_ASIGNADO
    assert registro.canal_elegido is Canal.LOCAL
    assert registro.nivel_aviso is Nivel.VIGILAR
    assert registro.canal_aviso is Canal.LOCAL
    assert registro.motivos == ()
    assert registro.motivo_principal is None


# =============================================================================================
# B2 (base) — Taladro → venta local, Vigilar
# =============================================================================================


@pytest.mark.scenario("B2 (base)")
def test_b2_base_de_punta_a_punta():
    """REQ §5 B2: resultado NIVEL_ASIGNADO = Vigilar, venta local, con las cuentas por canal."""
    registro = motor.evaluar(_contexto())

    # Referencias, descuento y calidad.
    refs = registro.referencias
    assert refs is not None
    assert refs.precio_habitual == D("149")
    assert refs.precio_mercado_hoy == D("149")
    assert refs.minimo_60_dias_amazon == D("139")
    assert refs.precio_venta_amazon == D("149")
    assert refs.episodio is None
    assert _cerca(registro.descuento_anunciado, (D("199") - D("79")) / D("199") * 100)
    assert _pct(registro.descuento_anunciado) == "60.3 %"
    assert _cerca(registro.descuento_real, REAL_B2)
    assert _pct(registro.descuento_real) == "47.0 %"
    # No inflado: 199 ≤ 1.5 × 149 = 223.50.
    assert Marca.PRECIO_ANTES_INFLADO.value not in registro.marcas
    assert registro.calidad_precio is CalidadPrecio.BUENA_OFERTA
    assert registro.confianza is Confianza.ALTA
    assert registro.costo_compra == COMPRA_B2

    # Amazon: comisión $22.35 + envío $12 + empaque $2 = $36.35; neto $27.53 (32.3%);
    # devoluciones 149 × 7% × 50% = 5.215 → $5.22; castigo 50% × (149 − 139) = $5.00;
    # ajustado $17.31 (20.3%); 3 unidades; 37 días; rendimiento 16.5%; sin nivel.
    a = _canal(registro, Canal.AMAZON)
    assert a.estado is EstadoCanal.DISPONIBLE
    assert a.causas_cerrado == () and a.causas_por_revisar == ()
    assert a.precio_venta == D("149.00")
    assert a.costo_venta == D("36.35")
    assert a.margen_neto == D("27.53")
    assert _cerca(a.margen_neto_pct, _pct_compra("27.53"))
    assert _pct(a.margen_neto_pct) == "32.3 %"
    assert a.costo_devoluciones == D("5.22")
    assert a.castigo == D("5.00")
    assert a.margen_ajustado == D("17.31")
    assert _cerca(a.margen_ajustado_pct, _pct_compra("17.31"))
    assert _pct(a.margen_ajustado_pct) == "20.3 %"
    assert a.unidades == 3
    assert a.dias_para_recuperar == 37
    assert _cerca(a.rendimiento_mensual_pct, _pct_compra("17.31") * 30 / 37)
    assert _pct(a.rendimiento_mensual_pct) == "16.5 %"
    assert a.nivel is None
    assert a.nivel_calculado is None  # Vigilar exige 25% de margen ajustado
    # Demanda SUFICIENTE: empeoró 6.25%, sin advertencia; peso conocido.
    assert Marca.DEMANDA_A_LA_BAJA.value not in a.marcas
    assert marca_estimado("peso") not in a.marcas
    assert Marca.MARGEN_ESTIMADO.value in a.marcas
    assert Marca.EMPAQUE_POR_CONFIRMAR.value in a.marcas

    _verificar_local_b2(_canal(registro, Canal.LOCAL))
    _verificar_resultado_vigilar_local(registro)


@pytest.mark.scenario("B2 (base)")
def test_b2_base_precio_local_con_estimado_y_techo():
    """RN-016 §4 y §5: Jesús estima $129; comparables $135, $139, $150 → techo $135 →
    pedido mín(129, 135) = $129 → × (1 − 10%) = $116.10."""
    precio = canales.precio_venta_local(_contexto(), D("149"))
    assert precio is not None
    assert precio.techo == D("135.00")
    assert precio.precio == D("116.10")


@pytest.mark.scenario("B2 (base)")
def test_b2_base_amazon_por_componentes():
    """RN-006 §5 (ejemplo del taladro): comisión 149 × 15% = $22.35; 2 kg → envío $12 y
    empaque $2 (REQ §5); peso conocido, sin ESTIMADO (peso)."""
    assert canales.comision_amazon(D("149.00"), PARAMS.categories["tools"].commission) == D("22.35")
    envio = canales.envio_amazon(_oferta_b2().observacion, PARAMS.shipping)
    assert envio is not None
    assert (envio.envio, envio.empaque, envio.peso_estimado) == (D("12.00"), D("2.00"), False)
    assert rentabilidad.costo_devoluciones(D("149.00"), D("7"), D("50")) == D("5.22")
    castigo = PARAMS.amazon.drop_penalty
    assert rentabilidad.castigo_por_baja(D("149.00"), D("139"), castigo) == D("5.00")
    assert rentabilidad.castigo_por_baja(D("116.10"), D("139"), castigo) == D("0")


# --- Techo local: solo el mismo producto, el mismo estado y la zona de venta local ----------


def test_techo_ignora_otro_estado_y_fuera_de_zona():
    """Guía de T12 y RN-016 §4 y §5 (los de Houston no cuentan): un comparable usado y uno
    de una ciudad fuera de la zona (PAR-09 ``in_local_sale_zone: false``), los dos más
    baratos, no bajan el techo de $135.

    "Mismo producto" no se prueba aquí: el contexto trae solo los comparables del producto
    (los arma quien lee la base por ``product_id``, design.md §3 y TAB-09), así que un
    comparable de otro producto en el contexto no es una entrada válida del motor."""
    comparables = [_comparable(p) for p in COMPARABLES_B2] + [
        _comparable("100.00", condicion="used"),
        _comparable("110.00", ciudad="houston"),
    ]
    precio = canales.precio_venta_local(_contexto(comparables=comparables), D("149"))
    assert precio is not None
    assert precio.techo == D("135.00")
    assert precio.precio == D("116.10")


def test_techo_corta_un_estimado_mas_alto():
    """RN-016 §4: precio pedido = el menor entre estimado y techo. Estimado $140, techo
    $135 → pedido $135 → venta 135 × 90% = $121.50."""
    contexto = _contexto(estimados=(_estimado("140.00"),))
    precio = canales.precio_venta_local(contexto, D("149"))
    assert precio is not None
    assert (precio.techo, precio.precio) == (D("135.00"), D("121.50"))


def test_techo_sin_estimado_corta_el_85_del_mercado():
    """RN-016 §4: sin estimado de Jesús, 85% del mercado hoy, con el mismo techo.
    149 × 85% = 126.65 < 135 → 149 × 85% × 90% = 113.985 → $113.99 (una vez al final);
    con un comparable de $120 → pedido $120 → $108.00."""
    precio = canales.precio_venta_local(_contexto(estimados=()), D("149"))
    assert precio is not None
    assert (precio.techo, precio.precio) == (D("135.00"), D("113.99"))
    comparables = [_comparable("120.00")]
    precio = canales.precio_venta_local(_contexto(estimados=(), comparables=comparables), D("149"))
    assert precio is not None
    assert (precio.techo, precio.precio) == (D("120.00"), D("108.00"))


def test_techo_cuenta_comparables_vendidos_dec_260_provisional():
    """DEC-260 (provisional, la decide el experto en la sesión 3): el techo usa los
    comparables activos **y vendidos** del mismo estado en la zona. Vendido $130 en Tijuana
    → techo $130; estimado $140 → pedido $130 → $117.00."""
    comparables = [_comparable(p) for p in COMPARABLES_B2] + [
        _comparable("130.00", ciudad="tijuana", vendido=True)
    ]
    contexto = _contexto(estimados=(_estimado("140.00"),), comparables=comparables)
    precio = canales.precio_venta_local(contexto, D("149"))
    assert precio is not None
    assert (precio.techo, precio.precio) == (D("130.00"), D("117.00"))


def test_solo_comparables_fuera_de_zona_es_sin_techo_y_marca():
    """RN-016 §11: sin comparables en la zona, sin techo; se usa el estimado ($129 →
    $116.10) y se marca SIN COMPARABLES LOCALES en el canal local (DEC-267)."""
    comparables = [_comparable("110.00", ciudad="houston")]
    contexto = _contexto(comparables=comparables)
    precio = canales.precio_venta_local(contexto, D("149"))
    assert precio is not None
    assert (precio.techo, precio.precio) == (None, D("116.10"))
    refs = referencias.calcular_referencias(contexto)
    costo = canales.costo_compra(contexto.oferta.observacion, PARAMS)
    loc = canales.evaluar_local(contexto, refs, costo)
    assert Marca.SIN_COMPARABLES_LOCALES.value in loc.marcas


# =============================================================================================
# B15 — Sin mínimo de 60 días → sin nivel (S-05)
# =============================================================================================


def _insumos(canal: Canal, precio: str, costo_venta: str, tasa: str, perdida: str):
    return CanalEvaluado(
        canal=canal,
        estado=EstadoCanal.DISPONIBLE,
        causas_cerrado=(),
        causas_por_revisar=(),
        precio_venta=D(precio),
        costo_venta=D(costo_venta),
        tasa_devolucion_pct=D(tasa),
        perdida_devolucion_pct=D(perdida),
        ventas_al_mes=30 if canal is Canal.AMAZON else 2,
        dias_tabla=7 if canal is Canal.AMAZON else None,
        dias_por_unidad=None if canal is Canal.AMAZON else 14,
        dias_pago=30 if canal is Canal.AMAZON else 0,
        disponibles=4,
        limite_cliente=None,
        ranking=D("8500"),
        baja_por_competencia=False,
        marcas=(
            (Marca.MARGEN_ESTIMADO.value, Marca.EMPAQUE_POR_CONFIRMAR.value)
            if canal is Canal.AMAZON
            else ()
        ),
    )


@pytest.mark.scenario("B15")
def test_b15_castigo_sin_minimo_es_10_por_ciento_del_precio_del_canal():
    """S-05 y RN-005 §11: sin mínimo de 60 días, castigo = 10% del precio de venta del
    canal (PAR-11 ``without_minimum_pct``). B15: 10% × 149 = $14.90; 10% × 116.10 =
    11.61 → $11.61."""
    castigo = PARAMS.amazon.drop_penalty
    assert castigo.without_minimum_pct == D("10")
    assert rentabilidad.castigo_por_baja(D("149.00"), None, castigo) == D("14.90")
    assert rentabilidad.castigo_por_baja(D("116.10"), None, castigo) == D("11.61")


@pytest.mark.scenario("B15")
def test_b15_margenes_sin_minimo_por_canal():
    """B15 con los insumos de B2 y sin mínimo: Amazon ajustado 27.53 − 5.22 − 14.90 =
    $7.41; local 21.48 − 0 − 11.61 = $9.87 (11.6%). Los dos < $10 (mínimo por unidad)."""
    castigo = PARAMS.amazon.drop_penalty
    a = rentabilidad.calcular_margenes(
        _insumos(Canal.AMAZON, "149.00", "36.35", "7", "50"), COMPRA_B2, None, castigo
    )
    assert a is not None
    assert (a.margen_neto, a.costo_devoluciones, a.castigo, a.margen_ajustado) == (
        D("27.53"),
        D("5.22"),
        D("14.90"),
        D("7.41"),
    )
    loc = rentabilidad.calcular_margenes(
        _insumos(Canal.LOCAL, "116.10", "9.50", "0", "100"), COMPRA_B2, None, castigo
    )
    assert loc is not None
    assert (loc.margen_neto, loc.castigo, loc.margen_ajustado) == (
        D("21.48"),
        D("11.61"),
        D("9.87"),
    )
    assert _cerca(loc.margen_ajustado_pct, _pct_compra("9.87"))
    assert _pct(loc.margen_ajustado_pct) == "11.6 %"
    minimo = rentabilidad.minimo_por_unidad(COMPRA_B2, PARAMS.levels.min_per_unit)
    assert minimo == D("10.00")
    assert a.margen_ajustado < minimo and loc.margen_ajustado < minimo


@pytest.mark.scenario("B15")
@pytest.mark.xfail(
    strict=True,
    reason=(
        "Contradicción abierta en B15 (#34): con el botón de compra de $149 de hoy, la "
        "lectura vigente de minimo_60_dias_amazon (B2 b, B9 b) siempre da mínimo y el "
        "castigo sale $0; Jesús decide entre tres opciones. " + URL_B15_34
    ),
)
def test_b15_de_punta_a_punta():
    """REQ §5 B15: "los datos de B2, sin mínimo de 60 días en Amazon". Fixture coherente con
    la lectura vigente: se quita el botón de compra de $139 del día −40 (el único dato del
    mínimo en los 60 días anteriores) y se conserva el de hoy ($149), que B2 necesita para la
    venta esperada y el mercado hoy. Esperado del REQ: Amazon castigo $14.90, ajustado $7.41;
    local castigo $11.61, ajustado $9.87 (11.6%); los dos < $10 → SIN_NIVEL."""
    registro = motor.evaluar(_contexto(fichas=_fichas_b2(con_minimo_139=False)))
    assert registro.referencias is not None
    assert registro.referencias.minimo_60_dias_amazon is None
    a = _canal(registro, Canal.AMAZON)
    assert a.castigo == D("14.90")
    assert a.margen_ajustado == D("7.41")
    loc = _canal(registro, Canal.LOCAL)
    assert loc.castigo == D("11.61")
    assert loc.margen_ajustado == D("9.87")
    assert _pct(loc.margen_ajustado_pct) == "11.6 %"
    assert a.nivel is None and loc.nivel is None
    assert registro.resultado is Resultado.SIN_NIVEL


# =============================================================================================
# B16 — Peso desconocido (S-06)
# =============================================================================================


@pytest.mark.scenario("B16")
def test_b16_envio_sin_peso():
    """S-06 y PAR-06 ``unknown_weight``: sin peso, envío $14 y empaque $2, estimado."""
    envio = canales.envio_amazon(_oferta_b2(peso=None).observacion, PARAMS.shipping)
    assert envio is not None
    assert (envio.envio, envio.empaque, envio.peso_estimado) == (D("14.00"), D("2.00"), True)


@pytest.mark.scenario("B16")
def test_b16_de_punta_a_punta():
    """REQ §5 B16: envío $14 y empaque $2 (ESTIMADO (peso)); costo de venta $38.35; neto
    $25.53; ajustado $15.31 (18.0%) → Amazon sin nivel; local igual que B2 → Vigilar,
    venta local."""
    registro = motor.evaluar(_contexto(oferta=_oferta_b2(peso=None)))
    a = _canal(registro, Canal.AMAZON)
    assert a.estado is EstadoCanal.DISPONIBLE
    assert a.costo_venta == D("38.35")  # 22.35 + 14 + 2
    assert a.margen_neto == D("25.53")  # 149 − 85.12 − 38.35
    assert a.costo_devoluciones == D("5.22")
    assert a.castigo == D("5.00")
    assert a.margen_ajustado == D("15.31")
    assert _cerca(a.margen_ajustado_pct, _pct_compra("15.31"))
    assert _pct(a.margen_ajustado_pct) == "18.0 %"
    assert a.nivel is None
    # DEC-267: la marca del cálculo del canal va solo en el canal, no en el registro.
    assert marca_estimado("peso") in a.marcas
    assert marca_estimado("peso") not in registro.marcas
    assert marca_estimado("peso") not in _canal(registro, Canal.LOCAL).marcas
    _verificar_local_b2(_canal(registro, Canal.LOCAL))
    _verificar_resultado_vigilar_local(registro)


# =============================================================================================
# B17 — Comisión desconocida
# =============================================================================================


@pytest.mark.scenario("B17")
@pytest.mark.parametrize("categoria", ["home_kitchen", "electronics"])
def test_b17_de_punta_a_punta(categoria):
    """REQ §5 B17: los datos de B2 en una categoría de la tabla de §5 sin comisión (con tasa
    de devolución, para que la causa de cierre sea solo la comisión) → Amazon cerrado con
    COMISIÓN DESCONOCIDA (RN-006 §11); local igual que B2 → Vigilar, venta local.

    Esas categorías tampoco tienen umbral de demanda (DEMANDA DESCONOCIDA, por revisar):
    la causa de cerrado prevalece (S-31), así que Amazon no queda por revisar y no hay
    motivo DEMANDA DESCONOCIDA."""
    assert "commission" not in _texto().split(f"\n  {categoria}:", 1)[1].split("\n  ", 1)[0]
    registro = motor.evaluar(_contexto(categoria=categoria))
    a = _canal(registro, Canal.AMAZON)
    assert a.estado is EstadoCanal.CERRADO
    assert a.causas_cerrado == (CausaCanalCerrado.COMISION_DESCONOCIDA,)
    # La causa de cierre también es marca del canal (REQ §3.2.3; DEC-267).
    assert CausaCanalCerrado.COMISION_DESCONOCIDA.value in a.marcas
    assert CausaCanalCerrado.COMISION_DESCONOCIDA.value not in registro.marcas
    # Cerrado: sin RN-005 ni nivel; sin comisión no hay costo de venta ni margen neto.
    assert a.costo_venta is None and a.margen_neto is None
    assert a.margen_ajustado is None and a.castigo is None
    assert a.unidades is None and a.rendimiento_mensual_pct is None
    assert a.nivel is None and a.nivel_calculado is None
    assert Motivo.DEMANDA_DESCONOCIDA not in registro.motivos
    _verificar_local_b2(_canal(registro, Canal.LOCAL))
    _verificar_resultado_vigilar_local(registro)
