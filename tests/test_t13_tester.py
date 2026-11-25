"""Pruebas independientes de oip-tester para T13 (restricción, competencia más barata,
confianza baja y sin rotación: B4, B9 base, B21 y B25).

Capacidad ``canales-y-margen``; REQ-2026-0001 v2.9 §3.2 pasos 7 a 9, §3.2.1, §3.2.2
(``nivel_calculado``), §3.2.3 (marcas), §3.2.4, §3.3 punto 4 y §13 S-07, S-08, S-09, S-10 y
S-33; design.md CMP-13 a CMP-15, PAR-05, PAR-13 y §10 puntos 4 y 6; DEC-224 (a), DEC-261,
DEC-266, DEC-267 y DEC-269.

Escritas por adelantado (DEC-252, etapa 2) **sin ver la implementación de T13**: solo con la
interfaz pública de main (firmas y tipos) y las fuentes. Los datos y los resultados esperados
se copian del REQ (precios, montos, porcentajes, niveles, resultado y canal), no del código.
Las pruebas de reglas que no son el escenario tal cual (bordes de S-07, S-09, S-10, de la
competencia y del empate del nivel del aviso) no llevan marcador de escenario.

"Dado" parcial (DEC-232, design.md §12): B4 y B21/B25 no dan algunos datos (ranking del
perfume, días de historial); el fixture los completa con valores neutros que no agregan
motivos de mayor precedencia. El material peligroso del perfume va en la configuración de
estas pruebas (``lists.hazmat_products``), porque "perfumes" no es código de ``category``
(design.md Open Questions 7) y base.yaml trae la lista vacía.

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
    CalidadPrecio,
    Canal,
    CausaCanalCerrado,
    Confianza,
    EstadoCanal,
    Marca,
    Nivel,
    Resultado,
)
from oip.configuracion import cargar_configuracion_texto
from oip.dinero import formatear_porcentaje
from oip.entradas.capturas import leer_captura
from oip.entradas.contrato import leer_observacion
from oip.evaluacion import canales, eleccion, identificacion, motor, rentabilidad
from oip.evaluacion.contexto import (
    ContextoEvaluacion,
    EvaluacionCanal,
    ObservacionRegistrada,
)

D = Decimal
TIJUANA = ZoneInfo("America/Tijuana")

# --- Configuración: base de los escenarios + tienda-prueba + cadenas sintéticas -----------
# ``tienda-prueba`` es la cadena de la oferta ("Home Depot" en B1, B2, B9, B21, B25; "Walmart
# en línea" en B4). ``ca`` y ``cb`` son dos cadenas más (Walmart / Target, según el
# escenario), ``ct`` es la de "Target" en B9. La ficha de Amazon es el comercio ``amazon`` de
# la base, con URL sintética que nadie abre. ``tp-cv`` es la sucursal de la oferta.
_EXTRA_COMERCIOS = (
    "  ca: {chain: cadena-a, domains: [a.example.com], amazon_listing: false}\n"
    "  cb: {chain: cadena-b, domains: [b.example.com], amazon_listing: false}\n"
    "  ct: {chain: cadena-t, domains: [t.example.com], amazon_listing: false}\n"
)
_EXTRA_SUCURSAL = "  tp-cv: {retailer: tienda-prueba}\n"
_DOMINIO = {
    TIENDA_PRUEBA: "tienda.example.com",
    "ca": "a.example.com",
    "cb": "b.example.com",
    "ct": "t.example.com",
    "amazon": "amazon.example.com",
}

# Perfume de B4 (sintético): UPC-A con dígito verificador válido.
GTIN_PERFUME = "036000291452"
MARCA_PERFUME = "MarcaP"
MODELO_PERFUME = "EDP-50"
# Producto de B1/B2 (sintético).
GTIN_B1 = "012345678905"
MARCA_B1 = "MarcaS"
MODELO_B1 = "SC-13"
GTIN_B2 = "042100005264"
MODELO_B2 = "TL-13"

_LISTA_HAZMAT_VACIA = "  hazmat_products: []\n"
_LISTA_HAZMAT_PERFUME = f'  hazmat_products: [{{gtin: "{GTIN_PERFUME}"}}]\n'


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
    return cargar_configuracion_texto(_texto(*reemplazos), origen="t13-tester")


#: Configuración de estas pruebas: la base + el perfume de B4 como material peligroso.
CONFIG = _config((_LISTA_HAZMAT_VACIA, _LISTA_HAZMAT_PERFUME))
PARAMS = CONFIG.contenido
#: Día 0 de los escenarios (en temporada de juguetes por base.yaml: 1-nov a 31-dic; ningún
#: producto de B1, B2 o B4 es juguete, así que no importa para ellos).
INSTANTE = dt.datetime(2026, 11, 16, 14, 0, tzinfo=TIJUANA)

_ids = itertools.count(0x7130_1000)


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
    categoria: str,
    ident: UUID | None = None,
    was: str | None = None,
    estado: str = "in_stock_confirmed",
    cantidad: int | None = None,
    modo: str = "envio",
    tienda: str | None = None,
    liquidacion: bool = False,
    peso: str | None = None,
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
        "productUrl": url or f"https://{_DOMINIO[comercio]}/p/{modelo.lower()}",
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


def _ficha_amazon(
    momento: dt.datetime,
    *,
    publicacion: UUID,
    producto: UUID,
    gtin: str,
    marca: str,
    modelo: str,
    categoria: str,
    buy_box: str | None,
    rank: int | None = None,
    vendedores: int | None = None,
    comprados: int | None = None,
    peso: str | None = None,
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
        publicacion=publicacion,
        producto=producto,
        gtin=gtin,
        marca=marca,
        modelo=modelo,
        categoria=categoria,
        ficha=ficha,
        peso=peso,
    )


def _contexto(
    oferta, historial, fichas, *, instante=INSTANTE, configuracion=CONFIG, **extra
) -> ContextoEvaluacion:
    return ContextoEvaluacion(
        id_evaluacion=UUID(int=0x7130_00FF),
        instante=instante,
        configuracion=configuracion,
        id_version_configuracion=1,
        oferta=oferta,
        historial=tuple(historial),
        fichas_amazon=tuple(fichas),
        **extra,
    )


# =========================================================================================
# B1 (base de B9 y B25): Home Depot Chula Vista, liquidación, herramientas, 4 kg
# =========================================================================================

PROD_B1 = UUID(int=0x7130_0100)
PUB_B1_OFERTA = UUID(int=0x7130_0101)
ID_B1_OFERTA = UUID(int=0x7130_0102)
PUB_B1_AMAZON = UUID(int=0x7130_0103)
PUB_B1_CA = UUID(int=0x7130_0104)  # "Walmart"
PUB_B1_CB = UUID(int=0x7130_0105)
PUB_B1_TARGET = UUID(int=0x7130_0106)  # "Target" de B9

_B1 = {"producto": PROD_B1, "gtin": GTIN_B1, "marca": MARCA_B1, "modelo": MODELO_B1}


def _oferta_b1(**cambios) -> ObservacionRegistrada:
    """B1: Home Depot Chula Vista (sucursal ``tp-cv``), liquidación, herramientas, 4 kg,
    código confirmado, vendida por el comercio, $29.00 con tachado $129.00, "3 disponibles"
    hace 2 h; tasa de la tienda 7.75% (REQ §5)."""
    argumentos = {
        "momento": _hace(2),
        "publicacion": PUB_B1_OFERTA,
        "ident": ID_B1_OFERTA,
        "was": "129.00",
        "estado": "in_stock",
        "cantidad": 3,
        "modo": "tienda",
        "tienda": "tp-cv",
        "liquidacion": True,
        "tax_location": "tienda_prueba",
        "peso": "4.0",
        "categoria": "tools",
        **_B1,
    }
    argumentos.update(cambios)
    precio = argumentos.pop("precio", "29.00")
    return _obs(precio, TIENDA_PRUEBA, **argumentos)


def _historial_b1() -> list[ObservacionRegistrada]:
    """Precio habitual $119 (8 observaciones en 6 días, 60 días de historial; la de $109 es
    el botón de compra de Amazon del día −50, en las fichas): 109, 119 × 6, 129 → 119. La
    tienda de la oferta no tiene historial propio. Hoy "Walmart" (``ca``) $124 hace 8 h."""
    comunes = {"categoria": "tools", "peso": "4.0", **_B1}
    return [
        _obs("119.00", "ca", momento=_hace(dias=60), publicacion=PUB_B1_CA, **comunes),
        _obs("119.00", "cb", momento=_hace(dias=60), publicacion=PUB_B1_CB, **comunes),
        _obs("119.00", "ca", momento=_hace(dias=40), publicacion=PUB_B1_CA, **comunes),
        _obs("119.00", "ca", momento=_hace(dias=20), publicacion=PUB_B1_CA, **comunes),
        _obs("129.00", "cb", momento=_hace(dias=20), publicacion=PUB_B1_CB, **comunes),
        _obs("119.00", "ca", momento=_hace(dias=10), publicacion=PUB_B1_CA, **comunes),
        _obs("119.00", "cb", momento=_hace(dias=3), publicacion=PUB_B1_CB, **comunes),
        _obs("124.00", "ca", momento=_hace(8), publicacion=PUB_B1_CA, **comunes),
    ]


def _target_99() -> ObservacionRegistrada:
    """B9: "Target la vende hoy a $99 (hace 10 h)", disponible confirmada, por el comercio."""
    return _obs(
        "99.00",
        "ct",
        momento=_hace(10),
        publicacion=PUB_B1_TARGET,
        categoria="tools",
        peso="4.0",
        **_B1,
    )


def _fichas_b1(*, vendedores: int = 5, comprados: int = 200) -> list[ObservacionRegistrada]:
    """Ficha de Amazon de B1: botón de compra hoy $119 (hace 2 h); mínimo de 60 días $109
    (día −50); ranking 6,000 hoy y hace 30 días (promedio de 7 días); ``vendedores`` y
    ``comprados`` en la ficha más reciente. Las fichas de ranking de días anteriores no traen
    botón de compra, para no agregar observaciones al precio habitual."""
    comunes = {
        "publicacion": PUB_B1_AMAZON,
        "categoria": "tools",
        "peso": "4.0",
        **_B1,
    }
    fichas = [_ficha_amazon(_hace(dias=50), buy_box="109.00", **comunes)]
    fichas += [
        _ficha_amazon(_hace(dias=d), buy_box=None, rank=6000, **comunes) for d in range(36, 29, -1)
    ]
    fichas += [
        _ficha_amazon(_hace(dias=d), buy_box=None, rank=6000, **comunes) for d in range(6, 0, -1)
    ]
    fichas.append(
        _ficha_amazon(
            _hace(2),
            buy_box="119.00",
            rank=6000,
            vendedores=vendedores,
            comprados=comprados,
            **comunes,
        )
    )
    return fichas


def _contexto_b1(*extra_historial, fichas=None, oferta=None, **otros) -> ContextoEvaluacion:
    return _contexto(
        _oferta_b1() if oferta is None else oferta,
        [*_historial_b1(), *extra_historial],
        _fichas_b1() if fichas is None else fichas,
        **otros,
    )


# =========================================================================================
# B2 (base de B21): Home Depot Chula Vista, no liquidación, herramientas, 2 kg
# =========================================================================================

PROD_B2 = UUID(int=0x7130_0200)
PUB_B2_OFERTA = UUID(int=0x7130_0201)
ID_B2_OFERTA = UUID(int=0x7130_0202)
PUB_B2_AMAZON = UUID(int=0x7130_0203)
PUB_B2_CA = UUID(int=0x7130_0204)  # "Walmart"
PUB_B2_CB = UUID(int=0x7130_0205)

_B2 = {"producto": PROD_B2, "gtin": GTIN_B2, "marca": MARCA_B1, "modelo": MODELO_B2}


def _oferta_b2(**cambios) -> ObservacionRegistrada:
    """B2: Home Depot Chula Vista (``tp-cv``), no liquidación, herramientas, 2 kg, código
    confirmado, $79.00 con tachado $199.00, "4 disponibles" hace 2 h; tasa 7.75%."""
    argumentos = {
        "momento": _hace(2),
        "publicacion": PUB_B2_OFERTA,
        "ident": ID_B2_OFERTA,
        "was": "199.00",
        "estado": "in_stock",
        "cantidad": 4,
        "modo": "tienda",
        "tienda": "tp-cv",
        "liquidacion": False,
        "tax_location": "tienda_prueba",
        "peso": "2.0",
        "categoria": "tools",
        **_B2,
    }
    argumentos.update(cambios)
    precio = argumentos.pop("precio", "79.00")
    return _obs(precio, TIENDA_PRUEBA, **argumentos)


def _historial_b2() -> list[ObservacionRegistrada]:
    """B2: precio típico de Home Depot en 60 días $149 con historial suficiente (5
    observaciones de la publicación de la oferta en 5 días); precio habitual $149 con 8
    observaciones en 6 días: 139 (botón de compra de Amazon del día −50, en las fichas),
    149 × 6 y 159 → mediana 149. Hoy "Walmart" (``ca``) $152 hace 6 h."""
    comunes = {"categoria": "tools", "peso": "2.0", **_B2}
    propia = {"publicacion": PUB_B2_OFERTA, "tienda": "tp-cv", "modo": "tienda", "cantidad": 4}
    historial = [
        _obs(
            "149.00",
            TIENDA_PRUEBA,
            momento=_hace(dias=d),
            estado="in_stock",
            tax_location="tienda_prueba",
            **propia,
            **comunes,
        )
        for d in (40, 30, 20, 10, 5)
    ]
    historial += [
        _obs("149.00", "ca", momento=_hace(dias=40), publicacion=PUB_B2_CA, **comunes),
        _obs("159.00", "cb", momento=_hace(dias=20), publicacion=PUB_B2_CB, **comunes),
        _obs("152.00", "ca", momento=_hace(6), publicacion=PUB_B2_CA, **comunes),
    ]
    return historial


def _fichas_b2() -> list[ObservacionRegistrada]:
    """B2: hoy Amazon $149 (botón de compra); mínimo de 60 días $139 (día −50); ranking 8,500
    hoy (promedio de 7 días) y 8,000 hace 30 días; 9 vendedores y 300 comprados."""
    comunes = {"publicacion": PUB_B2_AMAZON, "categoria": "tools", "peso": "2.0", **_B2}
    fichas = [_ficha_amazon(_hace(dias=50), buy_box="139.00", **comunes)]
    fichas += [
        _ficha_amazon(_hace(dias=d), buy_box=None, rank=8000, **comunes) for d in range(36, 29, -1)
    ]
    fichas += [
        _ficha_amazon(_hace(dias=d), buy_box=None, rank=8500, **comunes) for d in range(6, 0, -1)
    ]
    fichas.append(
        _ficha_amazon(_hace(2), buy_box="149.00", rank=8500, vendedores=9, comprados=300, **comunes)
    )
    return fichas


def _captura(tipo: str, datos: dict):
    return leer_captura(tipo, datos, zona=TIJUANA, dia_de_carga=INSTANTE.date())


def _capturas_locales_b2() -> dict:
    """B2: estimado local de Jesús $129; comparables locales $135, $139 y $150 (nuevos, en
    la zona de venta local, activos)."""
    producto = {"gtin": GTIN_B2}
    fecha = (INSTANTE.date() - dt.timedelta(days=2)).isoformat()
    comparables = tuple(
        _captura(
            "local_comparable",
            {
                **producto,
                "condition": "new",
                "askingPrice": precio,
                "currency": "USD",
                "city": "san_diego",
                "date": fecha,
                "sold": False,
            },
        )
        for precio in ("135.00", "139.00", "150.00")
    )
    estimado = _captura("local_estimate", {**producto, "price": "129.00", "date": fecha})
    return {"comparables": comparables, "estimados": (estimado,)}


def _contexto_b2(oferta=None) -> ContextoEvaluacion:
    return _contexto(
        _oferta_b2() if oferta is None else oferta,
        _historial_b2(),
        _fichas_b2(),
        **_capturas_locales_b2(),
    )


# =========================================================================================
# B4: perfume restringido (Walmart en línea, envío al PO Box, belleza, 0.3 kg)
# =========================================================================================

PROD_B4 = UUID(int=0x7130_0400)
PUB_B4_OFERTA = UUID(int=0x7130_0401)
ID_B4_OFERTA = UUID(int=0x7130_0402)
PUB_B4_AMAZON = UUID(int=0x7130_0403)
PUB_B4_TARGET = UUID(int=0x7130_0404)
PUB_B4_CB = UUID(int=0x7130_0405)

_B4 = {
    "producto": PROD_B4,
    "gtin": GTIN_PERFUME,
    "marca": MARCA_PERFUME,
    "modelo": MODELO_PERFUME,
    "categoria": "beauty",
    "peso": "0.3",
}


def _oferta_b4(**cambios) -> ObservacionRegistrada:
    """B4: "Walmart en línea" (cadena ``tienda-prueba``, envío al PO Box: ``taxLocation`` con
    la tasa de prueba 7.75% de REQ §5), perfumes y belleza, 0.3 kg, código confirmado,
    vendido por el comercio, $27.00 sin tachado, "disponible confirmada" hace 1 h."""
    argumentos = {
        "momento": _hace(1),
        "publicacion": PUB_B4_OFERTA,
        "ident": ID_B4_OFERTA,
        "estado": "in_stock_confirmed",
        "modo": "envio",
        "tax_location": "tienda_prueba",
        **_B4,
    }
    argumentos.update(cambios)
    precio = argumentos.pop("precio", "27.00")
    return _obs(precio, TIENDA_PRUEBA, **argumentos)


def _historial_b4() -> list[ObservacionRegistrada]:
    """B4: precio habitual $90 con historial suficiente: 80 (botón de compra de Amazon del día
    −50, en las fichas), 90 × 6 y 100 → mediana 90, en 6 días. Hoy "Target" (``ct``) $92."""
    hist = [
        _obs("90.00", "cb", momento=_hace(dias=d), publicacion=PUB_B4_CB, **_B4)
        for d in (45, 35, 25, 15, 8, 4)
    ]
    hist.append(_obs("100.00", "ct", momento=_hace(dias=25), publicacion=PUB_B4_TARGET, **_B4))
    hist.append(_obs("92.00", "ct", momento=_hace(5), publicacion=PUB_B4_TARGET, **_B4))
    return hist


def _fichas_b4() -> list[ObservacionRegistrada]:
    """B4: hoy Amazon $88 (botón de compra, hace 3 h); mínimo de 60 días $80 (día −50). El
    REQ no da ranking, vendedores ni comprados del perfume (Dado parcial, DEC-232): no se
    ponen; Amazon queda cerrado por la restricción de todos modos."""
    comunes = {"publicacion": PUB_B4_AMAZON, **_B4}
    return [
        _ficha_amazon(_hace(dias=50), buy_box="80.00", **comunes),
        _ficha_amazon(_hace(3), buy_box="88.00", **comunes),
    ]


def _capturas_locales_b4() -> dict:
    """B4: estimado local de Jesús $55; comparables locales $59 y $65 (nuevos, activos)."""
    producto = {"gtin": GTIN_PERFUME}
    fecha = (INSTANTE.date() - dt.timedelta(days=2)).isoformat()
    comparables = tuple(
        _captura(
            "local_comparable",
            {
                **producto,
                "condition": "new",
                "askingPrice": precio,
                "currency": "USD",
                "city": "san_diego",
                "date": fecha,
                "sold": False,
            },
        )
        for precio in ("59.00", "65.00")
    )
    estimado = _captura("local_estimate", {**producto, "price": "55.00", "date": fecha})
    return {"comparables": comparables, "estimados": (estimado,)}


def _contexto_b4(configuracion=CONFIG, oferta=None) -> ContextoEvaluacion:
    return _contexto(
        _oferta_b4() if oferta is None else oferta,
        _historial_b4(),
        _fichas_b4(),
        configuracion=configuracion,
        **_capturas_locales_b4(),
    )


# =========================================================================================
# B4 — Perfume restringido → venta local, Recomendable (REQ §5 B4)
# =========================================================================================


@pytest.fixture(scope="module")
def registro_b4():
    return motor.evaluar(_contexto_b4())


@pytest.mark.scenario("B4")
def test_b4_descuento_real_y_calidad(registro_b4):
    """Real **70.0%**. Calidad **Buena oferta** (27 ≤ 89.76 = 88 × 1.02)."""
    assert registro_b4.referencias.precio_habitual == D("90")
    assert registro_b4.descuento_real == D("70")
    assert _pct(registro_b4.descuento_real) == "70.0 %"
    assert registro_b4.referencias.precio_mercado_hoy == D("88.00")
    assert registro_b4.calidad_precio is CalidadPrecio.BUENA_OFERTA


@pytest.mark.scenario("B4")
def test_b4_amazon_cerrado_por_restriccion_con_material_peligroso(registro_b4):
    """Amazon: categoría belleza restringida, sin cuenta → `NO VENDIBLE EN AMAZON (POR AHORA)`
    y `MATERIAL PELIGROSO` → canal cerrado. Un canal cerrado no tiene `nivel_calculado`
    (REQ §3.2.2; DEC-224 a) ni RN-005 (§3.2.1)."""
    amazon = _canal(registro_b4, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.CERRADO
    assert CausaCanalCerrado.NO_VENDIBLE_EN_AMAZON in amazon.causas_cerrado
    assert amazon.nivel is None
    assert amazon.nivel_calculado is None
    assert amazon.unidades is None
    assert amazon.rendimiento_mensual_pct is None
    assert amazon.ganancia_total is None
    # §3.2.1: en un canal cerrado solo el margen neto (informativo), sin margen ajustado.
    assert amazon.margen_ajustado is None
    # Las causas de cerrado también se registran como marcas (§3.2.3).
    assert CausaCanalCerrado.NO_VENDIBLE_EN_AMAZON.value in _todas_las_marcas(registro_b4)
    todas = _todas_las_marcas(registro_b4)
    assert todas.count(Marca.MATERIAL_PELIGROSO.value) == 1  # DEC-267: en un solo lugar


@pytest.mark.scenario("B4")
def test_b4_costo_de_compra(registro_b4):
    """Compra: impuesto 27 × 7.75% = 2.0925 → $2.09 → **$29.09**."""
    assert registro_b4.costo_compra == D("29.09")


@pytest.mark.scenario("B4")
def test_b4_venta_local(registro_b4):
    """Local: pedido $55 (techo $59) → venta **$49.50**; neto 49.50 − 29.09 − 9.50 =
    **$10.91 (37.5%)**; castigo $0 (49.50 < 80); unidades mín(2, tope 3) = 2; rendimiento
    37.5%; mínimo $10 ✓ → **Recomendable** (Muy recomendable exige 40%)."""
    local = _canal(registro_b4, Canal.LOCAL)
    assert local.estado is EstadoCanal.DISPONIBLE
    assert local.precio_venta == D("49.50")
    assert local.costo_venta == D("9.50")
    assert local.margen_neto == D("10.91")
    assert _pct(local.margen_neto_pct) == "37.5 %"
    assert local.castigo == D("0.00")
    assert local.margen_ajustado == D("10.91")
    assert _pct(local.margen_ajustado_pct) == "37.5 %"
    assert local.unidades == 2
    assert _pct(local.rendimiento_mensual_pct) == "37.5 %"
    assert local.nivel is Nivel.RECOMENDABLE
    assert local.nivel_calculado is Nivel.RECOMENDABLE


@pytest.mark.scenario("B4")
def test_b4_resultado(registro_b4):
    """Resultado `NIVEL_ASIGNADO` = **Recomendable, venta local** (resumen)."""
    assert registro_b4.resultado is Resultado.NIVEL_ASIGNADO
    assert registro_b4.motivos == ()
    assert registro_b4.motivo_principal is None
    assert registro_b4.canal_elegido is Canal.LOCAL
    assert registro_b4.nivel_aviso is Nivel.RECOMENDABLE
    assert registro_b4.canal_aviso is Canal.LOCAL
    assert registro_b4.confianza is Confianza.ALTA  # disponible confirmada en línea (S-25)


# --- S-07, S-09 y S-10 alrededor de B4 (sin marcador: no son el escenario tal cual) -------


def test_s07_material_peligroso_solo_no_cierra_amazon():
    """S-07: `MATERIAL PELIGROSO` solo no cierra Amazon (marca). B1 con su producto en la
    lista de material peligroso: Amazon sigue disponible y con su nivel de B1."""
    config = _config((_LISTA_HAZMAT_VACIA, f'  hazmat_products: [{{gtin: "{GTIN_B1}"}}]\n'))
    registro = motor.evaluar(_contexto_b1(configuracion=config))
    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.DISPONIBLE
    assert amazon.causas_cerrado == ()
    assert amazon.nivel is Nivel.MUY_RECOMENDABLE
    assert _todas_las_marcas(registro).count(Marca.MATERIAL_PELIGROSO.value) == 1
    assert registro.resultado is Resultado.NIVEL_ASIGNADO
    assert registro.canal_elegido is Canal.AMAZON


def test_s07_material_peligroso_por_marca_y_por_producto():
    oferta = _oferta_b4().observacion
    assert canales.material_peligroso(oferta, PARAMS.lists) is True  # por producto (GTIN)
    sin_lista = _config().contenido.lists
    assert canales.material_peligroso(oferta, sin_lista) is False
    por_marca = _config(("  hazmat_brands: []\n", f"  hazmat_brands: [{MARCA_PERFUME}]\n"))
    assert canales.material_peligroso(oferta, por_marca.contenido.lists) is True


def test_s07_sin_material_peligroso_el_perfume_sigue_cerrado_por_la_categoria():
    """S-07: "el perfume se cierra por la categoría". Sin la lista de material peligroso,
    Amazon sigue cerrado (`NO VENDIBLE EN AMAZON (POR AHORA)`) y no hay la marca."""
    registro = motor.evaluar(_contexto_b4(configuracion=_config()))
    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.CERRADO
    assert CausaCanalCerrado.NO_VENDIBLE_EN_AMAZON in amazon.causas_cerrado
    assert Marca.MATERIAL_PELIGROSO.value not in _todas_las_marcas(registro)
    assert registro.resultado is Resultado.NIVEL_ASIGNADO
    assert registro.canal_elegido is Canal.LOCAL


def _obs_simple(categoria: str = "tools", marca: str = MARCA_B1, modelo: str = MODELO_B1):
    return _oferta_b1(categoria=categoria, marca=marca, modelo=modelo).observacion


def test_s09_restringido_por_categoria():
    assert canales.restringido_en_amazon(_oferta_b4().observacion, PARAMS, INSTANTE.date())
    assert not canales.restringido_en_amazon(_obs_simple(), PARAMS, INSTANTE.date())


def test_s09_restringido_por_marca():
    config = _config(
        ("  amazon_restricted_brands: []\n", f"  amazon_restricted_brands: [{MARCA_B1}]\n")
    )
    assert canales.restringido_en_amazon(_obs_simple(), config.contenido, INSTANTE.date())
    otra = _obs_simple(marca="OtraMarca")
    assert not canales.restringido_en_amazon(otra, config.contenido, INSTANTE.date())


@pytest.mark.parametrize(
    "producto",
    [f'{{gtin: "{GTIN_B1}"}}', f"{{brand: {MARCA_B1}, model: {MODELO_B1}}}"],
    ids=["por-gtin", "por-marca-y-modelo"],
)
def test_s09_restringido_por_producto(producto):
    config = _config(
        ("  amazon_restricted_products: []\n", f"  amazon_restricted_products: [{producto}]\n")
    )
    assert canales.restringido_en_amazon(_obs_simple(), config.contenido, INSTANTE.date())


def test_s09_producto_restringido_cierra_amazon_en_el_motor():
    """S-09: producto en la tabla de restricciones → no vendible → Amazon cerrado; B1 se va a
    venta local con sus números ($100.58, Muy recomendable)."""
    config = _config(
        (
            "  amazon_restricted_products: []\n",
            f'  amazon_restricted_products: [{{gtin: "{GTIN_B1}"}}]\n',
        )
    )
    registro = motor.evaluar(_contexto_b1(configuracion=config))
    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.CERRADO
    assert amazon.causas_cerrado == (CausaCanalCerrado.NO_VENDIBLE_EN_AMAZON,)
    assert amazon.nivel_calculado is None
    local = _canal(registro, Canal.LOCAL)
    assert local.ganancia_total == D("100.58")
    assert registro.resultado is Resultado.NIVEL_ASIGNADO
    assert registro.canal_elegido is Canal.LOCAL
    assert registro.nivel_aviso is Nivel.MUY_RECOMENDABLE


@pytest.mark.parametrize(
    ("dia", "restringido"),
    [
        (dt.date(2026, 10, 31), False),
        (dt.date(2026, 11, 1), True),
        (dt.date(2026, 12, 31), True),
        (dt.date(2027, 1, 1), False),
    ],
)
def test_s10_juguetes_en_temporada(dia, restringido):
    """S-10: juguetes en temporada navideña, del 1-nov al 31-dic (inclusivo)."""
    juguete = _obs_simple(categoria="toys")
    assert canales.restringido_en_amazon(juguete, PARAMS, dia) is restringido


def test_s10_temporada_configurable():
    config = _config(
        (
            '  toy_season: {start: "11-01", end: "12-31"}',
            '  toy_season: {start: "10-15", end: "10-31"}',
        )
    )
    juguete = _obs_simple(categoria="toys")
    assert canales.restringido_en_amazon(juguete, config.contenido, dt.date(2026, 10, 20))
    assert not canales.restringido_en_amazon(juguete, config.contenido, dt.date(2026, 11, 16))


def test_s10_fuera_de_temporada_un_juguete_no_restringido_por_la_temporada():
    assert not canales.restringido_en_amazon(_obs_simple(), PARAMS, dt.date(2026, 11, 16))


@pytest.mark.parametrize(
    ("instante", "restringido"),
    [
        # 31-oct 23:30 en Tijuana (ya 1-nov en UTC): día evaluado 31-oct → fuera.
        (dt.datetime(2026, 10, 31, 23, 30, tzinfo=TIJUANA), False),
        # 1-nov 00:30 en Tijuana: dentro.
        (dt.datetime(2026, 11, 1, 0, 30, tzinfo=TIJUANA), True),
    ],
)
def test_s10_el_motor_usa_el_dia_evaluado_en_tijuana(instante, restringido):
    """design.md §3: el día evaluado es el del instante en ``America/Tijuana`` (PAR-01), no
    el de UTC ni el de la máquina."""
    oferta = _oferta_b1(categoria="toys", momento=instante - dt.timedelta(hours=1))
    ficha = _ficha_amazon(
        instante - dt.timedelta(hours=1),
        publicacion=PUB_B1_AMAZON,
        categoria="toys",
        buy_box="119.00",
        rank=6000,
        vendedores=5,
        comprados=200,
        **_B1,
    )
    registro = motor.evaluar(_contexto(oferta, [], [ficha], instante=instante))
    amazon = _canal(registro, Canal.AMAZON)
    causas = amazon.causas_cerrado
    assert (CausaCanalCerrado.NO_VENDIBLE_EN_AMAZON in causas) is restringido


# =========================================================================================
# B9 (base) — Competencia más barata (REQ §5 B9, sin la variante b)
# =========================================================================================


@pytest.fixture(scope="module")
def registro_b9():
    return motor.evaluar(_contexto_b1(_target_99()))


@pytest.mark.scenario("B9 (base)")
def test_b9_base_mercado_hoy_y_competencia(registro_b9):
    """Mercado hoy $99; `COMPETENCIA MÁS BARATA` (99 < 101.15) → Amazon baja de Muy
    recomendable a **Recomendable**; tope 3; 3 unidades; total $134.19."""
    assert registro_b9.referencias.precio_mercado_hoy == D("99.00")
    amazon = _canal(registro_b9, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.DISPONIBLE
    assert _todas_las_marcas(registro_b9).count(Marca.COMPETENCIA_MAS_BARATA.value) == 1
    assert Marca.COMPETENCIA_MAS_BARATA.value in amazon.marcas  # DEC-267: marca del canal
    assert amazon.margen_ajustado == D("44.73")
    assert amazon.nivel is Nivel.RECOMENDABLE
    assert amazon.nivel_calculado is Nivel.RECOMENDABLE  # con la baja (REQ §3.2.2)
    assert amazon.unidades == 3
    assert amazon.ganancia_total == D("134.19")


@pytest.mark.scenario("B9 (base)")
def test_b9_base_venta_local(registro_b9):
    """Local: 99 × 85% = $84.15 → **$75.74**; neto $34.99 (112.0%); Muy recomendable;
    2 unidades; total $69.98. La baja por competencia no aplica en venta local."""
    local = _canal(registro_b9, Canal.LOCAL)
    assert local.precio_venta == D("75.74")
    assert local.margen_neto == D("34.99")
    assert _pct(local.margen_neto_pct) == "112.0 %"
    assert local.castigo == D("0.00")
    assert local.nivel is Nivel.MUY_RECOMENDABLE
    assert local.nivel_calculado is Nivel.MUY_RECOMENDABLE
    assert local.unidades == 2
    assert local.ganancia_total == D("69.98")
    assert Marca.COMPETENCIA_MAS_BARATA.value not in local.marcas


@pytest.mark.scenario("B9 (base)")
def test_b9_base_eleccion_resultado_y_calidad(registro_b9):
    """Diferencia (134.19 − 69.98) ÷ 134.19 = 47.9% → **Amazon**. Resultado
    `NIVEL_ASIGNADO` = **Recomendable, Amazon**. Calidad sigue en Buena oferta (29 ≤
    100.98)."""
    assert registro_b9.resultado is Resultado.NIVEL_ASIGNADO
    assert registro_b9.canal_elegido is Canal.AMAZON
    assert _canal(registro_b9, Canal.AMAZON).nivel is Nivel.RECOMENDABLE
    assert registro_b9.calidad_precio is CalidadPrecio.BUENA_OFERTA
    diferencia = (D("134.19") - D("69.98")) / D("134.19") * 100
    assert _pct(diferencia) == "47.9 %"


@pytest.mark.scenario("B9 (base)")
def test_b9_base_nivel_del_aviso(registro_b9):
    """Aviso (S-33, §3.3 punto 4): nivel más alto entre los canales = **Muy recomendable**
    (venta local) → inmediato. Es también la evaluación de la oferta de B1 con Target a $99:
    el nivel del aviso sigue en Muy recomendable (lo de "no se repite" es C5)."""
    assert registro_b9.nivel_aviso is Nivel.MUY_RECOMENDABLE
    assert registro_b9.canal_aviso is Canal.LOCAL
    assert PARAMS.levels.thresholds[Nivel.MUY_RECOMENDABLE].alert == "immediate"


def test_b1_sin_target_no_hay_competencia_mas_barata():
    """Control de B9: sin Target, mercado hoy $119 y 119 ≥ 101.15 → sin la marca; Amazon en
    Muy recomendable (B1)."""
    registro = motor.evaluar(_contexto_b1())
    assert Marca.COMPETENCIA_MAS_BARATA.value not in _todas_las_marcas(registro)
    assert _canal(registro, Canal.AMAZON).nivel is Nivel.MUY_RECOMENDABLE
    assert registro.nivel_aviso is Nivel.MUY_RECOMENDABLE
    assert registro.canal_aviso is Canal.AMAZON


@pytest.mark.parametrize(
    ("hoy", "venta", "esperado"),
    [
        ("99.00", "119.00", True),  # B9: 99 < 101.15
        ("101.15", "119.00", False),  # el borde no cuenta (estrictamente menor)
        ("101.14", "119.00", True),
        ("119.00", "119.00", False),  # B1
        ("60.00", "60.00", False),  # B9 (b): 60 ≥ 51
    ],
)
def test_competencia_mas_barata_umbral(hoy, venta, esperado):
    """RN-002 §4.3: mercado hoy < venta en Amazon × (1 − 15%)."""
    umbral = PARAMS.levels.cheaper_competition_pct
    assert umbral == D("15")
    assert canales.competencia_mas_barata(D(hoy), D(venta), umbral) is esperado


def test_competencia_mas_barata_sin_precio_no_se_evalua():
    umbral = PARAMS.levels.cheaper_competition_pct
    assert canales.competencia_mas_barata(None, D("119.00"), umbral) is False
    assert canales.competencia_mas_barata(D("99.00"), None, umbral) is False


def test_competencia_mas_barata_umbral_configurable():
    """PAR-13: con 20%, 99 ≥ 119 × 0.80 = 95.20 → ya no hay competencia más barata."""
    config = _config(("  cheaper_competition_pct: 15\n", "  cheaper_competition_pct: 20\n"))
    registro = motor.evaluar(_contexto_b1(_target_99(), configuracion=config))
    assert Marca.COMPETENCIA_MAS_BARATA.value not in _todas_las_marcas(registro)
    assert _canal(registro, Canal.AMAZON).nivel is Nivel.MUY_RECOMENDABLE


def _margenes(ajustado: str, pct: str) -> rentabilidad.Margenes:
    return rentabilidad.Margenes(
        margen_neto=D(ajustado),
        margen_neto_pct=D(pct),
        costo_devoluciones=D("0.00"),
        castigo=D("0.00"),
        margen_ajustado=D(ajustado),
        margen_ajustado_pct=D(pct),
    )


@pytest.mark.parametrize(
    ("ajustado", "pct", "sin_baja", "con_baja"),
    [
        ("44.73", "143.136", Nivel.MUY_RECOMENDABLE, Nivel.RECOMENDABLE),  # B1 → B9
        ("8.00", "25.6", None, None),  # sin el mínimo por unidad no hay nada que bajar
        ("10.00", "32.0", Nivel.VIGILAR, None),  # Vigilar baja a sin nivel (design.md §9)
    ],
)
def test_nivel_calculado_con_la_baja_por_competencia(ajustado, pct, sin_baja, con_baja):
    """REQ §3.2.2: `nivel_calculado` con el mínimo por unidad y la baja por competencia.
    Descuento real 30% y costo $31.25 (mínimo $10) en las filas 2 y 3; 75.6% en la 1."""
    real = (D("119") - D("29")) / D("119") * 100 if sin_baja is Nivel.MUY_RECOMENDABLE else D(30)
    margenes = _margenes(ajustado, pct)
    calc = rentabilidad.nivel_calculado
    assert calc(real, margenes, D("31.25"), PARAMS, False) is sin_baja
    assert calc(real, margenes, D("31.25"), PARAMS, True) is con_baja


# =========================================================================================
# B21 — Confianza baja en tienda (REQ §5 B21)
# =========================================================================================


def _oferta_b21() -> ObservacionRegistrada:
    """B21: los datos de B2, pero "existencia limitada" hace 3 h (sin cantidad)."""
    return _oferta_b2(estado="limited_stock", cantidad=None, momento=_hace(3))


@pytest.fixture(scope="module")
def registro_b21():
    return motor.evaluar(_contexto_b2(_oferta_b21()))


@pytest.mark.scenario("B21")
def test_b21_confianza_baja(registro_b21):
    """Confianza **Baja** (`CONFIANZA BAJA`)."""
    assert registro_b21.confianza is Confianza.BAJA
    assert _todas_las_marcas(registro_b21).count(Marca.CONFIANZA_BAJA.value) == 1
    # DEC-267: la confianza es de la oferta, no nace del cálculo de un canal.
    assert Marca.CONFIANZA_BAJA.value in registro_b21.marcas


@pytest.mark.scenario("B21")
def test_b21_nivel_calculado_vigilar_en_local_sin_nivel(registro_b21):
    """`nivel_calculado` = Vigilar (local); sin nivel en el canal (RN-009 §4.2: en tienda
    física hace falta confianza Alta o Media). Los números locales son los de B2."""
    local = _canal(registro_b21, Canal.LOCAL)
    assert local.estado is EstadoCanal.DISPONIBLE
    assert local.precio_venta == D("116.10")
    assert local.margen_neto == D("21.48")
    assert local.margen_ajustado == D("21.48")
    assert _pct(local.margen_ajustado_pct) == "25.2 %"
    assert local.nivel_calculado is Nivel.VIGILAR
    assert local.nivel is None
    amazon = _canal(registro_b21, Canal.AMAZON)
    assert amazon.margen_ajustado == D("17.31")  # B2: 20.3% → sin nivel ni nivel_calculado
    assert amazon.nivel is None
    assert amazon.nivel_calculado is None


@pytest.mark.scenario("B21")
def test_b21_resultado_sin_nivel(registro_b21):
    """Resultado **`SIN_NIVEL`**: sin motivos de revisión (`CONFIANZA BAJA` es marca), sin
    canal elegido ni nivel del aviso (design.md §10 punto 6: solo con `NIVEL_ASIGNADO`)."""
    assert registro_b21.resultado is Resultado.SIN_NIVEL
    assert registro_b21.motivos == ()
    assert registro_b21.motivo_principal is None
    assert registro_b21.costo_compra == D("85.12")
    assert registro_b21.canal_elegido is None
    assert registro_b21.nivel_aviso is None
    assert registro_b21.canal_aviso is None


def test_b2_con_cuatro_disponibles_hace_2_h_sigue_en_vigilar():
    """Control de B21: con los datos de B2 ("4 disponibles" hace 2 h, confianza Alta) el
    local tiene nivel Vigilar y el resultado es `NIVEL_ASIGNADO` (REQ §5 B2)."""
    registro = motor.evaluar(_contexto_b2())
    assert registro.confianza is Confianza.ALTA
    assert Marca.CONFIANZA_BAJA.value not in _todas_las_marcas(registro)
    assert _canal(registro, Canal.LOCAL).nivel is Nivel.VIGILAR
    assert registro.resultado is Resultado.NIVEL_ASIGNADO
    assert registro.canal_elegido is Canal.LOCAL


def test_confianza_baja_por_componentes():
    """RN-007: "existencia limitada" sin número hace 3 h en tienda (no liquidación) → Baja;
    en tienda física la confianza Baja no permite nivel (RN-009 §4.2)."""
    oferta = _oferta_b21().observacion
    assert identificacion.es_tienda_fisica(oferta) is True
    confianza = identificacion.confianza_disponibilidad(oferta, INSTANTE, PARAMS.levels.confidence)
    assert confianza is Confianza.BAJA
    assert identificacion.confianza_permite_nivel(oferta, Confianza.BAJA) is False
    assert identificacion.confianza_permite_nivel(oferta, Confianza.MEDIA) is True
    assert identificacion.confianza_permite_nivel(oferta, Confianza.ALTA) is True


def test_confianza_baja_no_aplica_en_linea():
    """REQ §3.2.1: el requisito de confianza es de tienda física; en línea siempre se
    cumple."""
    en_linea = _oferta_b4().observacion
    assert identificacion.es_tienda_fisica(en_linea) is False
    assert identificacion.confianza_permite_nivel(en_linea, Confianza.BAJA) is True


# =========================================================================================
# B25 — Sin rotación en Amazon (REQ §5 B25)
# =========================================================================================


@pytest.fixture(scope="module")
def registro_b25():
    return motor.evaluar(_contexto_b1(fichas=_fichas_b1(vendedores=15, comprados=10)))


@pytest.mark.scenario("B25")
def test_b25_ventas_al_mes_cero(registro_b25):
    """10 ÷ (15 + 1) = 0.625 → 0."""
    ficha = _fichas_b1(vendedores=15, comprados=10)[-1].observacion.amazon_listing
    assert canales.ventas_al_mes_amazon(ficha) == 0


@pytest.mark.scenario("B25")
def test_b25_amazon_cerrado_sin_rotacion(registro_b25):
    """→ Amazon cerrado (`SIN ROTACIÓN`, §13 S-08); un canal cerrado no tiene nivel ni
    `nivel_calculado` (DEC-224 a) ni unidades, días o rendimiento."""
    amazon = _canal(registro_b25, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.CERRADO
    assert amazon.causas_cerrado == (CausaCanalCerrado.SIN_ROTACION,)
    assert amazon.nivel is None
    assert amazon.nivel_calculado is None
    assert amazon.unidades is None
    assert amazon.rendimiento_mensual_pct is None
    assert amazon.ganancia_total is None
    assert amazon.margen_ajustado is None  # §3.2.1: cerrado, solo el margen neto
    assert CausaCanalCerrado.SIN_ROTACION.value in amazon.marcas


@pytest.mark.scenario("B25")
def test_b25_local_como_b1_y_resultado(registro_b25):
    """Local como B1 ($100.58) → resultado `NIVEL_ASIGNADO` = **Muy recomendable, venta
    local**."""
    local = _canal(registro_b25, Canal.LOCAL)
    assert local.precio_venta == D("91.04")
    assert local.margen_neto == D("50.29")
    assert local.unidades == 2
    assert local.nivel is Nivel.MUY_RECOMENDABLE
    assert local.nivel_calculado is Nivel.MUY_RECOMENDABLE
    assert local.ganancia_total == D("100.58")
    assert registro_b25.resultado is Resultado.NIVEL_ASIGNADO
    assert registro_b25.motivos == ()
    assert registro_b25.canal_elegido is Canal.LOCAL
    assert registro_b25.nivel_aviso is Nivel.MUY_RECOMENDABLE
    assert registro_b25.canal_aviso is Canal.LOCAL


@pytest.mark.parametrize(
    ("comprados", "vendedores", "esperado"),
    [(10, 15, 0), (16, 15, 1), (15, 15, 0), (200, 5, 33), (300, 9, 30)],
)
def test_ventas_al_mes_amazon_hacia_abajo(comprados, vendedores, esperado):
    """RN-005 §4: comprados ÷ (vendedores + 1), hacia abajo (B1: 33; B2: 30; B25: 0)."""
    ficha = _fichas_b1(vendedores=vendedores, comprados=comprados)[-1].observacion
    assert canales.ventas_al_mes_amazon(ficha.amazon_listing) == esperado


def test_ventas_al_mes_amazon_sin_datos():
    ficha = _fichas_b1()[1].observacion.amazon_listing  # ficha de ranking sin comprados
    assert canales.ventas_al_mes_amazon(ficha) is None
    assert canales.ventas_al_mes_amazon(None) is None


def test_s08_con_una_venta_al_mes_amazon_no_se_cierra_por_rotacion():
    """S-08: el cierre es con **menos de 1** venta al mes; con 16 ÷ 16 = 1 no hay `SIN
    ROTACIÓN` (unidades mín(1, 3, 5) = 1)."""
    registro = motor.evaluar(_contexto_b1(fichas=_fichas_b1(vendedores=15, comprados=16)))
    amazon = _canal(registro, Canal.AMAZON)
    assert CausaCanalCerrado.SIN_ROTACION not in amazon.causas_cerrado
    assert amazon.estado is EstadoCanal.DISPONIBLE
    assert amazon.unidades == 1


# =========================================================================================
# Nivel del aviso: el más alto entre los canales con nivel; con empate, el del canal
# elegido (design.md §10 punto 6; S-33)
# =========================================================================================


def _canal_con_nivel(canal: Canal, nivel: Nivel | None, ganancia: str, rendimiento: str):
    return EvaluacionCanal(
        canal=canal,
        estado=EstadoCanal.DISPONIBLE,
        nivel=nivel,
        nivel_calculado=nivel,
        ganancia_total=D(ganancia) if nivel is not None else None,
        rendimiento_mensual_pct=D(rendimiento) if nivel is not None else None,
    )


@pytest.mark.parametrize("elegido", [Canal.AMAZON, Canal.LOCAL])
def test_nivel_del_aviso_empate_usa_el_canal_elegido(elegido):
    lista = [
        _canal_con_nivel(Canal.AMAZON, Nivel.MUY_RECOMENDABLE, "134.19", "116.1"),
        _canal_con_nivel(Canal.LOCAL, Nivel.MUY_RECOMENDABLE, "100.58", "160.9"),
    ]
    assert eleccion.nivel_del_aviso(lista, elegido) == (Nivel.MUY_RECOMENDABLE, elegido)
    # El orden de la lista no cambia el resultado.
    assert eleccion.nivel_del_aviso(list(reversed(lista)), elegido) == (
        Nivel.MUY_RECOMENDABLE,
        elegido,
    )


def test_nivel_del_aviso_el_mas_alto_aunque_gane_otro_canal():
    """B9: Amazon elegido en Recomendable; local Muy recomendable → aviso Muy recomendable
    con el canal local."""
    lista = [
        _canal_con_nivel(Canal.AMAZON, Nivel.RECOMENDABLE, "134.19", "116.1"),
        _canal_con_nivel(Canal.LOCAL, Nivel.MUY_RECOMENDABLE, "69.98", "112.0"),
    ]
    assert eleccion.nivel_del_aviso(lista, Canal.AMAZON) == (Nivel.MUY_RECOMENDABLE, Canal.LOCAL)


def test_elegir_en_b9_y_en_empate():
    desempate = PARAMS.levels.channel_tiebreak_pct
    b9 = [
        _canal_con_nivel(Canal.AMAZON, Nivel.RECOMENDABLE, "134.19", "116.1"),
        _canal_con_nivel(Canal.LOCAL, Nivel.MUY_RECOMENDABLE, "69.98", "112.0"),
    ]
    resultado = eleccion.elegir(b9, desempate)
    assert resultado.canal_elegido is Canal.AMAZON
    assert resultado.nivel_aviso is Nivel.MUY_RECOMENDABLE
    assert resultado.canal_aviso is Canal.LOCAL
    # B1: los dos Muy recomendable, gana Amazon por ganancia (25.0%) → aviso con Amazon.
    b1 = [
        _canal_con_nivel(Canal.AMAZON, Nivel.MUY_RECOMENDABLE, "134.19", "116.1"),
        _canal_con_nivel(Canal.LOCAL, Nivel.MUY_RECOMENDABLE, "100.58", "160.9"),
    ]
    resultado = eleccion.elegir(b1, desempate)
    assert (resultado.canal_elegido, resultado.nivel_aviso, resultado.canal_aviso) == (
        Canal.AMAZON,
        Nivel.MUY_RECOMENDABLE,
        Canal.AMAZON,
    )


def test_nivel_del_aviso_sin_canales_con_nivel():
    lista = [
        _canal_con_nivel(Canal.AMAZON, None, "0", "0"),
        _canal_con_nivel(Canal.LOCAL, None, "0", "0"),
    ]
    assert eleccion.nivel_del_aviso(lista, None) == (None, None)


def test_nivel_del_aviso_un_solo_canal_con_nivel():
    lista = [
        _canal_con_nivel(Canal.AMAZON, None, "0", "0"),
        _canal_con_nivel(Canal.LOCAL, Nivel.RECOMENDABLE, "21.82", "37.5"),
    ]
    assert eleccion.nivel_del_aviso(lista, Canal.LOCAL) == (Nivel.RECOMENDABLE, Canal.LOCAL)


# =========================================================================================
# Seguridad y datos de prueba
# =========================================================================================


def test_los_fixtures_solo_usan_dominios_de_example_com():
    for dominio in _DOMINIO.values():
        assert dominio == "example.com" or dominio.endswith(".example.com")
