"""Pruebas de oip-tester para T02 de req-2026-0001-b-evaluacion (configuración versionada).

T02 no tiene escenarios propios (tasks.md §2): estas pruebas cubren sus comportamientos
esperados (design.md §7 y §12) de forma independiente de las del developer:

- los valores de los dos archivos del repo se comparan con la tabla de REQ §5, copiada aquí
  del cuerpo del #2 (no del código ni del YAML);
- parámetro faltante, tipo inválido y sección desconocida se prueban en **todas** las rutas
  del archivo base, generadas al recorrerlo, y no en una muestra;
- montos y porcentajes son ``Decimal`` (ni ``float`` ni ``int``), también si el YAML trae
  un entero;
- la huella no cambia con el orden de las claves, el BOM ni el fin de línea, y cambia con un
  valor de cualquier sección;
- comisiones ``flat``, ``total_threshold`` y ``tiers`` con mínimo por unidad, tasa asignada
  (S-27) y tamaño de la categoría como fuente del umbral (DEC-225);
- el cargador es seguro (sin etiquetas de Python) y el código no trae valores del REQ.

Sin marcador de escenario: T02 no tiene escenarios propios.
"""

import copy
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

import pytest
import yaml
from pydantic import BaseModel, ValidationError

from oip.catalogos import Categoria, Nivel
from oip.configuracion import (
    ComisionConUmbral,
    ComisionFija,
    ComisionPorTramos,
    Configuracion,
    ErrorConfiguracion,
    TasaAsignada,
    TasaPropia,
    _CargadorYaml,
    cargar_configuracion,
    cargar_configuracion_texto,
)

RAIZ = Path(__file__).resolve().parents[1]
BASE = RAIZ / "tests" / "fixtures" / "config" / "base.yaml"
PRODUCCION = RAIZ / "config" / "oip-config.yaml"
CODIGO = RAIZ / "src" / "oip" / "configuracion.py"

D = Decimal

# --- REQ §5 (cuerpo del #2), copiado a mano ---------------------------------------------
# category: (comisión, devolución, pérdida por devolución, umbral de demanda). None = "—".
# Comisión: ("flat", %), ("total_threshold", umbral, % hasta, % arriba) o
# ("tiers", ((hasta, %), (None, %))).
TABLA_REQ_5 = {
    "tools": (("flat", D("15")), ("own", D("7")), D("50"), 168440),
    "home_lighting": (("flat", D("15")), ("own", D("8")), D("50"), 168440),
    "home_kitchen": (None, ("own", D("8")), D("50"), None),
    "beauty": (("total_threshold", D("10"), D("8"), D("15")), ("own", D("6")), D("75"), None),
    "electronics": (None, ("own", D("11")), D("50"), None),
    "video_game_consoles": (("flat", D("8")), ("assigned", "electronics"), D("50"), None),
    "video_games": (None, ("assigned", "electronics"), D("50"), None),
    "watches": (("tiers", ((D("1500"), D("16")), (None, D("3")))), None, D("50"), None),
    "jewelry": (("tiers", ((D("250"), D("20")), (None, D("5")))), None, D("75"), None),
    "toys": (None, None, D("50"), None),
}
MINIMO_POR_UNIDAD_REQ = D("0.30")  # REQ §5: "Mínimo $0.30 por unidad"

# Tablas (mapas por código) del esquema: sus claves son datos, no parámetros.
TABLAS = {
    "general.rn_versions",
    "retailers",
    "stores",
    "categories",
    "taxes.locations",
    "private_sellers.platforms",
    "private_sellers.cities",
    "levels.thresholds",
}
# Claves que pueden faltar (el "—" del REQ §5 y los opcionales por regla).
OPCIONALES = re.compile(
    r"^categories\.[a-z_]+\.(commission|return_rate|main_category_size)$"
    r"|^private_sellers\.platforms\.[a-z_]+\.path_prefix$"
    r"|^stores\.[a-z0-9-]+\.max_units_per_customer$"
)
# Discriminadores de uniones: su error va en el campo de la unión.
DISCRIMINADORES = (".commission.type", ".return_rate.source")


# --- Ayudas -----------------------------------------------------------------------------


class _Volcador(yaml.SafeDumper):
    pass


_Volcador.add_representer(D, lambda d, v: d.represent_scalar("tag:yaml.org,2002:float", str(v)))


def _base() -> dict:
    return yaml.load(BASE.read_text(encoding="utf-8"), Loader=_CargadorYaml)  # noqa: S506


def _texto(datos: dict, *, ordenar: bool = False) -> str:
    return yaml.dump(datos, Dumper=_Volcador, allow_unicode=True, sort_keys=ordenar)


def _nodo(datos: dict, ruta: str) -> tuple[dict, str]:
    *padres, hoja = ruta.split(".")
    nodo = datos
    for parte in padres:
        nodo = nodo[parte]
    return nodo, hoja


def _sin(datos: dict, ruta: str) -> dict:
    datos = copy.deepcopy(datos)
    nodo, hoja = _nodo(datos, ruta)
    del nodo[hoja]
    return datos


def _con(datos: dict, ruta: str, valor: object) -> dict:
    datos = copy.deepcopy(datos)
    nodo, hoja = _nodo(datos, ruta)
    nodo[hoja] = valor
    return datos


def _errores(datos: dict) -> tuple[str, ...]:
    with pytest.raises(ErrorConfiguracion) as info:
        cargar_configuracion_texto(_texto(datos))
    return info.value.errores


def _rutas(valor: object, prefijo: str = "") -> list[tuple[str, object]]:
    """Todas las rutas de claves de mapas del archivo (sin entrar en listas)."""
    rutas = []
    if isinstance(valor, dict):
        for clave, hijo in valor.items():
            ruta = f"{prefijo}.{clave}" if prefijo else str(clave)
            rutas.append((ruta, hijo))
            rutas.extend(_rutas(hijo, ruta))
    return rutas


def _padre(ruta: str) -> str:
    return ruta.rpartition(".")[0]


_RUTAS_BASE = _rutas(_base())
# Parámetros = claves cuyo padre no es una tabla (las claves de una tabla son entradas).
_PARAMETROS = [r for r, _ in _RUTAS_BASE if _padre(r) not in TABLAS]
_OBLIGATORIOS = [r for r in _PARAMETROS if not OPCIONALES.match(r)]
_ESCALARES = [
    r for r, v in _RUTAS_BASE if not isinstance(v, dict | list) and _padre(r) not in TABLAS
]
_MODELOS = [r for r, v in _RUTAS_BASE if isinstance(v, dict) and r not in TABLAS]


def _ruta_esperada(ruta: str) -> str:
    return ruta.rpartition(".")[0] if ruta.endswith(DISCRIMINADORES) else ruta


# --- Los dos archivos tienen los valores de REQ §5 --------------------------------------


def _comision_como_tupla(comision):
    if comision is None:
        return None
    if isinstance(comision, ComisionFija):
        return ("flat", comision.rate_pct)
    if isinstance(comision, ComisionConUmbral):
        return (
            "total_threshold",
            comision.threshold,
            comision.rate_pct_at_or_below,
            comision.rate_pct_above,
        )
    assert isinstance(comision, ComisionPorTramos)
    return ("tiers", tuple((t.up_to, t.rate_pct) for t in comision.tiers))


def _tasa_como_tupla(tasa):
    if tasa is None:
        return None
    if isinstance(tasa, TasaPropia):
        return ("own", tasa.rate_pct)
    return ("assigned", tasa.from_category.value)


def _umbral(contenido, valores) -> int | None:
    # DEC-225: umbral = tamaño de la categoría × porcentaje de PAR-11, sin redondear.
    if valores.main_category_size is None:
        return None
    return int(valores.main_category_size * contenido.amazon.demand.category_rank_pct / 100)


def test_base_tiene_la_tabla_de_categorias_de_req_5_tal_cual():
    contenido = cargar_configuracion(BASE).contenido
    assert {c.value for c in contenido.categories} == set(TABLA_REQ_5)
    for codigo, (comision, devolucion, perdida, umbral) in TABLA_REQ_5.items():
        valores = contenido.categories[Categoria(codigo)]
        assert _comision_como_tupla(valores.commission) == comision, codigo
        assert _tasa_como_tupla(valores.return_rate) == devolucion, codigo
        assert valores.return_loss_pct == perdida, codigo
        assert _umbral(contenido, valores) == umbral, codigo


@pytest.mark.parametrize("ruta", [BASE, PRODUCCION], ids=["base", "produccion"])
def test_valores_de_req_5_que_no_son_guion(ruta):
    """Lo que REQ §5 fija (no es "—") es igual en la base y en producción."""
    contenido = cargar_configuracion(ruta).contenido
    for codigo, (comision, devolucion, perdida, umbral) in TABLA_REQ_5.items():
        valores = contenido.categories[Categoria(codigo)]
        if comision is not None:
            assert _comision_como_tupla(valores.commission) == comision, codigo
            assert valores.commission.min_per_unit == MINIMO_POR_UNIDAD_REQ, codigo
        if devolucion is not None:
            assert _tasa_como_tupla(valores.return_rate) == devolucion, codigo
        assert valores.return_loss_pct == perdida, codigo
        if umbral is not None:
            assert _umbral(contenido, valores) == umbral, codigo


@pytest.mark.parametrize("ruta", [BASE, PRODUCCION], ids=["base", "produccion"])
def test_resto_de_la_configuracion_base_de_req_5(ruta):
    c = cargar_configuracion(ruta).contenido
    # Impuesto: 7.75% de respaldo; envío hacia mí $0; particulares sin impuesto.
    assert c.taxes.fallback_rate_pct == D("7.75")
    assert c.shipping.shipping_to_me_default == D("0")
    assert c.taxes.private_sellers_exempt is True
    # Envío FBM ≤ 1 kg $8 · ≤ 3 kg $12 · ≤ 6 kg $14; empaque ≤ 1 kg $1 · > 1 kg $2.
    assert [(b.max_kg, b.shipping, b.packaging) for b in c.shipping.weight_bands] == [
        (D("1"), D("8"), D("1")),
        (D("3"), D("12"), D("2")),
        (D("6"), D("14"), D("2")),
    ]
    assert c.shipping.quote_above_kg == D("6")
    # Castigo 50%; pago de Amazon 30 días (cuenta nueva); venta local 0.
    assert c.amazon.drop_penalty.drop_weight_pct == D("50")
    assert c.general.amazon_account == "new"
    assert c.amazon.payment_days.new == 30
    assert c.local_sale.payment_days == 0
    # Días de venta: < 10,000 → 7; 10,000 a 50,000 → 21; > 50,000 → 45. Máximo 20 vendedores.
    dias = c.amazon.sale_days_by_rank
    assert (dias.fast_below_rank, dias.fast_days) == (10000, 7)
    assert (dias.medium_up_to_rank, dias.medium_days, dias.slow_days) == (50000, 21, 45)
    assert c.amazon.demand.max_new_sellers == 20
    assert c.amazon.demand.rank_window_days == 7  # DEC-206
    # Venta local: 85% del mercado hoy; negociación 10%; demanda media 14 días por unidad.
    assert c.local_sale.market_today_pct == D("85")
    assert c.local_sale.negotiation_pct == D("10")
    assert c.local_sale.demand.days_per_unit_medium == 14
    # Entrega 10 km y 0.5 h = $9.50.
    t = c.local_sale.transport
    assert (t.default_delivery_km, t.default_delivery_hours) == (D("10"), D("0.5"))
    entrega = t.default_delivery_km * t.cost_per_km + t.default_delivery_hours * t.hour_value
    assert entrega + t.fixed_costs == D("9.50")
    # Tope de primera compra 3 (5 con ranking < 10,000 y Comprar ya o Muy recomendable).
    tope = c.amazon.first_purchase_cap
    assert (tope.units, tope.boosted_units, tope.boosted_below_rank) == (3, 5, 10000)
    assert set(tope.boosted_levels) == {Nivel.COMPRAR_YA, Nivel.MUY_RECOMENDABLE}
    # Historial suficiente 5 en 3 días, en 60 días; episodio 30 días; competencia 15%.
    p = c.price_reference
    assert (p.sufficient_history_observations, p.sufficient_history_days) == (5, 3)
    assert p.usual_window_days == 60
    assert p.clearance_episode_max_days == 30
    assert c.levels.cheaper_competition_pct == D("15")


def test_base_tiene_la_tienda_de_prueba_a_7_75_y_las_de_b31_a_8_75():
    ubicaciones = cargar_configuracion(BASE).contenido.taxes.locations
    tasas = {codigo: u.rate_pct for codigo, u in ubicaciones.items()}
    assert D("7.75") in tasas.values()  # REQ §5: la tienda tiene cargada 7.75%
    assert tasas["chula_vista"] == D("8.75")  # B31
    assert tasas["national_city"] == D("8.75")  # B31


@pytest.mark.parametrize("ruta", [BASE, PRODUCCION], ids=["base", "produccion"])
def test_versiones_de_rn_de_req_4(ruta):
    versiones = dict(cargar_configuracion(ruta).contenido.general.rn_versions)
    esperado = {f"RN-{n:03d}": 2 for n in range(1, 12)} | {f"RN-{n:03d}": 1 for n in range(12, 19)}
    assert versiones == esperado


# --- Objeto inmutable con version, schemaVersion y sha256 -------------------------------


def test_cargada_trae_version_schema_version_y_huella():
    base = cargar_configuracion(BASE)
    produccion = cargar_configuracion(PRODUCCION)
    assert (base.version, base.schema_version) == ("escenarios-base-1", "1")
    assert (produccion.version, produccion.schema_version) == ("2026-11-18.1", "1")
    assert re.fullmatch(r"[0-9a-f]{64}", base.sha256)
    assert base.sha256 != produccion.sha256


def test_inmutable_en_profundidad():
    c = cargar_configuracion(BASE).contenido
    with pytest.raises(ValidationError):
        c.shipping.weight_bands[0].shipping = D("1")
    with pytest.raises(ValidationError):
        c.categories[Categoria.WATCHES].commission.tiers[0].rate_pct = D("1")
    with pytest.raises(ValidationError):
        c.taxes.locations["chula_vista"].rate_pct = D("1")
    with pytest.raises(ValidationError):
        c.version = "otra"
    tablas = [
        c.general.rn_versions,
        c.retailers,
        c.stores,
        c.categories,
        c.taxes.locations,
        c.private_sellers.platforms,
        c.private_sellers.cities,
        c.levels.thresholds,
    ]
    assert all(isinstance(t, MappingProxyType) for t in tablas)
    assert isinstance(c.retailers["homedepot"].domains, tuple)
    assert isinstance(c.amazon.first_purchase_cap.boosted_levels, tuple)
    assert isinstance(c.categories[Categoria.WATCHES].commission.tiers, tuple)


def test_huella_igual_con_otro_orden_bom_y_crlf():
    datos = _base()
    original = cargar_configuracion(BASE).sha256
    assert cargar_configuracion_texto(_texto(datos, ordenar=True)).sha256 == original
    texto = BASE.read_text(encoding="utf-8")
    assert cargar_configuracion_texto("﻿" + texto.replace("\n", "\r\n")).sha256 == original
    assert cargar_configuracion_texto(texto, origen="otro-nombre.yaml").sha256 == original


_NUMEROS_Y_BANDERAS = [
    r for r, v in _RUTAS_BASE if isinstance(v, bool | int | D) and _padre(r) not in TABLAS
]


@pytest.mark.parametrize("ruta", _NUMEROS_Y_BANDERAS)
def test_huella_cambia_con_cualquier_valor(ruta):
    datos = _base()
    original = cargar_configuracion_texto(_texto(datos)).sha256
    nodo, hoja = _nodo(datos, ruta)
    valor = nodo[hoja]
    otro = (not valor) if isinstance(valor, bool) else valor + 1
    try:
        nueva = cargar_configuracion_texto(_texto(_con(datos, ruta, otro))).sha256
    except ErrorConfiguracion:
        return  # rechazado (fuera de rango o regla cruzada): no hay huella que comparar
    assert nueva != original


def test_huella_cambia_con_un_texto_o_una_fecha():
    datos = _base()
    original = cargar_configuracion_texto(_texto(datos)).sha256
    for ruta, valor in [
        ("version", "escenarios-base-2"),
        ("taxes.locations.chula_vista.source", "CDTFA"),
        ("taxes.locations.chula_vista.effective_date", date(2026, 1, 2)),
        ("lists.toy_season.start", "11-02"),
    ]:
        assert cargar_configuracion_texto(_texto(_con(datos, ruta, valor))).sha256 != original


# --- Parámetro faltante: cada ruta del archivo base -------------------------------------


@pytest.mark.parametrize("ruta", _OBLIGATORIOS)
def test_cada_parametro_obligatorio_faltante_rechaza_con_su_nombre(ruta):
    errores = _errores(_sin(_base(), ruta))
    esperado = _ruta_esperada(ruta)
    if ruta.endswith(DISCRIMINADORES):
        assert any(e.startswith(f"{esperado}:") for e in errores), errores
    else:
        assert f"{esperado}: falta el parámetro" in errores, errores


# La tasa propia de electronics es el origen de la tasa asignada (S-27): sin ella se rechaza.
_ORIGEN_S27 = "categories.electronics.return_rate"


@pytest.mark.parametrize(
    "ruta", [r for r in _PARAMETROS if OPCIONALES.match(r) and r != _ORIGEN_S27]
)
def test_cada_opcional_del_req_puede_faltar(ruta):
    assert cargar_configuracion_texto(_texto(_sin(_base(), ruta)))


def test_sin_la_tasa_de_origen_de_s27_rechaza():
    errores = _errores(_sin(_base(), _ORIGEN_S27))
    assert any("video_game_consoles.return_rate.from_category" in e for e in errores)
    assert any("video_games.return_rate.from_category" in e for e in errores)


@pytest.mark.parametrize(
    ("original", "cambio", "esperado"),
    [
        (
            "{up_to: 1500.00, rate_pct: 16}",
            '{up_to: 1500.00, rate_pct: "16"}',
            "categories.watches.commission.tiers.0.rate_pct: tipo o valor inválido",
        ),
        (
            "{up_to: 1500.00, rate_pct: 16}",
            "{up_to: 1500.00}",
            "categories.watches.commission.tiers.0.rate_pct: falta el parámetro",
        ),
    ],
    ids=["tipo", "faltante"],
)
def test_error_dentro_de_un_tramo_nombra_la_ruta_completa(original, cambio, esperado):
    """El nombre del parámetro incluye ``tiers`` (tasks.md §2: "con el nombre del parámetro")."""
    texto = BASE.read_text(encoding="utf-8").replace(original, cambio, 1)
    with pytest.raises(ErrorConfiguracion) as info:
        cargar_configuracion_texto(texto)
    assert any(e.startswith(esperado) for e in info.value.errores), info.value.errores


@pytest.mark.parametrize("categoria", [c.value for c in Categoria])
def test_falta_una_categoria_del_catalogo_rechaza(categoria):
    """Cada ``category`` del catálogo cerrado trae parámetros obligatorios (pérdida por
    devolución, restricción, demanda local inicial, procedencia): si falta la categoría,
    faltan esos parámetros y el archivo entero se rechaza con su nombre (tasks.md §2;
    design.md §7, PAR-04; REQ §5 "Por categoría" y §6 "Categorías")."""
    errores = _errores(_sin(_base(), f"categories.{categoria}"))
    assert any(f"categories.{categoria}" in e for e in errores), errores


# --- Tipo inválido: cada valor del archivo base ----------------------------------------


@pytest.mark.parametrize("ruta", _ESCALARES)
def test_cada_valor_con_tipo_invalido_rechaza_con_su_nombre(ruta):
    # Ningún parámetro escalar acepta un mapa.
    errores = _errores(_con(_base(), ruta, {"x": 1}))
    esperado = _ruta_esperada(ruta)
    assert any(e.startswith(esperado) for e in errores), errores


@pytest.mark.parametrize(
    "ruta", [r for r, v in _RUTAS_BASE if isinstance(v, int | D) and not isinstance(v, bool)]
)
def test_cada_numero_escrito_como_texto_rechaza(ruta):
    datos = _base()
    nodo, hoja = _nodo(datos, ruta)
    errores = _errores(_con(datos, ruta, str(nodo[hoja])))
    assert any(e.startswith(ruta) for e in errores), errores


def test_float_no_entra_ni_por_la_api_del_modelo():
    datos = _con(_base(), "taxes.fallback_rate_pct", 7.75)
    with pytest.raises(ValidationError):
        Configuracion.model_validate(datos)
    datos = _con(_base(), "price_reference.usual_window_days", 60.0)
    with pytest.raises(ValidationError):
        Configuracion.model_validate(datos)


@pytest.mark.parametrize(
    "texto",
    [
        "effective_date: 2026-01-01 10:00:00}",  # fecha y hora en una fecha
        "effective_date: 01/01/2026}",
    ],
)
def test_fecha_de_vigencia_solo_fecha(texto):
    t = BASE.read_text(encoding="utf-8").replace("effective_date: 2026-01-01}", texto, 1)
    with pytest.raises(ErrorConfiguracion, match="effective_date"):
        cargar_configuracion_texto(t)


@pytest.mark.parametrize("numero", [".inf", "-.inf", ".nan"])
def test_numero_no_finito_rechaza(numero):
    t = BASE.read_text(encoding="utf-8").replace(
        "fallback_rate_pct: 7.75", f"fallback_rate_pct: {numero}"
    )
    with pytest.raises(ErrorConfiguracion):
        cargar_configuracion_texto(t)


@pytest.mark.parametrize(
    ("ruta", "valor"),
    [
        ("local_sale.negotiation_pct", D("100.01")),
        ("local_sale.negotiation_pct", D("-0.01")),
        ("categories.tools.main_category_size", 0),
        ("categories.tools.main_category_size", D("33688021.5")),
        ("shipping.weight_bands", []),
    ],
)
def test_valor_fuera_de_rango_rechaza(ruta, valor):
    assert any(e.startswith(ruta) for e in _errores(_con(_base(), ruta, valor)))


@pytest.mark.parametrize(
    "dominio",
    [
        "Example.com",
        "example.com:443",
        "example.com/x",
        "https://example.com",
        "a@example.com",
        "example",
    ],
)
def test_dominio_autorizado_solo_como_nombre(dominio):
    errores = _errores(_con(_base(), "retailers.walmart.domains", [dominio]))
    assert any(e.startswith("retailers.walmart.domains") for e in errores)


# --- Sección o parámetro desconocido: en cada nivel -------------------------------------


@pytest.mark.parametrize("ruta", ["", *_MODELOS])
def test_parametro_desconocido_en_cada_nivel_rechaza(ruta):
    nueva = f"{ruta}.zz_desconocido" if ruta else "zz_desconocido"
    errores = _errores(_con(_base(), nueva, 1))
    assert f"{nueva}: sección o parámetro desconocido" in errores, errores


def test_rechazo_no_devuelve_nada_aunque_solo_falle_un_valor():
    datos = _con(_base(), "levels.thresholds.VIGILAR.alert", "telegram")
    with pytest.raises(ErrorConfiguracion) as info:
        cargar_configuracion_texto(_texto(datos))
    assert len(info.value.errores) == 1


# --- Montos y porcentajes como Decimal --------------------------------------------------


def _es_decimal(anotacion) -> bool:
    return anotacion is D or D in getattr(anotacion, "__args__", ())


def _campos_decimales(modelo: BaseModel, ruta: str = ""):
    for nombre, campo in type(modelo).model_fields.items():
        valor = getattr(modelo, nombre)
        aqui = f"{ruta}.{nombre}" if ruta else nombre
        if _es_decimal(campo.annotation):
            yield aqui, valor
        yield from _hijos(valor, aqui)


def _hijos(valor, ruta):
    if isinstance(valor, BaseModel):
        yield from _campos_decimales(valor, ruta)
    elif isinstance(valor, MappingProxyType | dict):
        for clave, hijo in valor.items():
            yield from _hijos(hijo, f"{ruta}.{clave}")
    elif isinstance(valor, tuple):
        for i, hijo in enumerate(valor):
            yield from _hijos(hijo, f"{ruta}.{i}")


@pytest.mark.parametrize("ruta", [BASE, PRODUCCION], ids=["base", "produccion"])
def test_montos_y_porcentajes_son_decimal_aunque_el_yaml_traiga_un_entero(ruta):
    campos = list(_campos_decimales(cargar_configuracion(ruta).contenido))
    assert len(campos) > 50
    for nombre, valor in campos:
        assert valor is None or type(valor) is D, (nombre, type(valor))


def test_decimal_exacto_desde_el_texto():
    t = BASE.read_text(encoding="utf-8").replace("negotiation_pct: 10", "negotiation_pct: 0.1")
    c = cargar_configuracion_texto(t).contenido
    assert c.local_sale.negotiation_pct == D("0.1")
    assert c.local_sale.negotiation_pct + D("0.2") == D("0.3")
    assert str(c.categories[Categoria.TOOLS].commission.min_per_unit) == "0.30"


# --- Comisiones, tasa asignada (S-27) y umbral por tamaño (DEC-225) ---------------------


@pytest.mark.parametrize(
    "categoria", ["tools", "beauty", "watches"], ids=["flat", "total_threshold", "tiers"]
)
def test_cada_tipo_de_comision_exige_el_minimo_por_unidad(categoria):
    ruta = f"categories.{categoria}.commission.min_per_unit"
    assert f"{ruta}: falta el parámetro" in _errores(_sin(_base(), ruta))


def test_tramos_tres_crecientes_cargan_y_los_iguales_o_sin_ultimo_abierto_rechazan():
    ruta = "categories.watches.commission.tiers"
    tres = [
        {"up_to": D("500"), "rate_pct": 16},
        {"up_to": D("1500"), "rate_pct": 10},
        {"up_to": None, "rate_pct": 3},
    ]
    assert cargar_configuracion_texto(_texto(_con(_base(), ruta, tres)))
    for malos in (
        [
            {"up_to": D("1500"), "rate_pct": 16},
            {"up_to": D("1500"), "rate_pct": 10},
            {"up_to": None, "rate_pct": 3},
        ],
        [{"up_to": D("1500"), "rate_pct": 16}, {"up_to": D("3000"), "rate_pct": 3}],
        [{"up_to": None, "rate_pct": 3}],
    ):
        assert any(
            e.startswith("categories.watches.commission")
            for e in _errores(_con(_base(), ruta, malos))
        )


def test_comision_total_threshold_exige_sus_dos_porcentajes():
    for hoja in ("threshold", "rate_pct_at_or_below", "rate_pct_above"):
        ruta = f"categories.beauty.commission.{hoja}"
        assert f"{ruta}: falta el parámetro" in _errores(_sin(_base(), ruta))


def test_tasa_asignada_a_si_misma_o_a_otra_asignada_rechaza():
    a_si_misma = _con(
        _base(),
        "categories.video_games.return_rate",
        {"source": "assigned", "from_category": "video_games"},
    )
    assert any(
        "categories.video_games.return_rate.from_category" in e for e in _errores(a_si_misma)
    )
    en_cadena = _con(
        _base(),
        "categories.video_games.return_rate",
        {"source": "assigned", "from_category": "video_game_consoles"},
    )
    assert any("categories.video_games.return_rate.from_category" in e for e in _errores(en_cadena))


def test_tasa_asignada_a_categoria_del_catalogo_ausente_del_archivo_rechaza():
    datos = _con(
        _base(),
        "categories.toys.return_rate",
        {"source": "assigned", "from_category": "electronics"},
    )
    datos = _con(datos, "categories.electronics.return_rate", None)
    errores = _errores(datos)
    assert any("categories.toys.return_rate.from_category" in e for e in errores)


def test_tasa_asignada_de_s27_apunta_a_tecnologia_11():
    c = cargar_configuracion(BASE).contenido
    for codigo in (Categoria.VIDEO_GAME_CONSOLES, Categoria.VIDEO_GAMES):
        tasa = c.categories[codigo].return_rate
        assert isinstance(tasa, TasaAsignada)
        assert c.categories[tasa.from_category].return_rate.rate_pct == D("11")


def test_umbral_de_demanda_no_es_un_parametro_fijo_sino_tamano_por_porcentaje():
    # DEC-225: el archivo trae el tamaño de la categoría y el porcentaje de PAR-11.
    c = cargar_configuracion(BASE).contenido
    assert c.amazon.demand.category_rank_pct == D("0.5")
    campos = set(type(c.categories[Categoria.TOOLS]).model_fields)
    assert "main_category_size" in campos
    assert not any("threshold" in campo for campo in campos)
    produccion = cargar_configuracion(PRODUCCION).contenido
    joyeria = produccion.categories[Categoria.JEWELRY]
    assert _umbral(produccion, joyeria) == 1242346  # RN-004 §4 (oct-2025), comentario del archivo


# --- Seguridad del cargador y sin valores del REQ en el código --------------------------


@pytest.mark.parametrize(
    "etiqueta",
    ["!!python/object/apply:os.getcwd []", "!!python/name:os.system", "!!binary aGk="],
)
def test_cargador_no_construye_objetos_de_python(etiqueta):
    t = BASE.read_text(encoding="utf-8").replace(
        "fallback_rate_pct: 7.75", f"fallback_rate_pct: {etiqueta}"
    )
    with pytest.raises(ErrorConfiguracion):
        cargar_configuracion_texto(t)


def test_el_codigo_no_trae_valores_de_req_5():
    """Sin valores por defecto en el código (design.md §7): ningún número de REQ §5 vive en
    ``configuracion.py`` como literal."""
    codigo = CODIGO.read_text(encoding="utf-8")
    for valor in ("7.75", "8.75", "0.30", "9.50", "168440", "168,440", "33688021", "1500", "0.5"):
        assert valor not in codigo, valor
