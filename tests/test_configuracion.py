"""Pruebas unitarias de oip.configuracion (CMP-04; design.md §7 y §12; tasks.md T02 2.1 y 2.2)."""

import copy
import dataclasses
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel

from oip.catalogos import Categoria, Nivel
from oip.configuracion import (
    ESQUEMAS_SOPORTADOS,
    ComisionConUmbral,
    ComisionPorTramos,
    Configuracion,
    ConfiguracionVersionada,
    ErrorConfiguracion,
    TasaAsignada,
    _CargadorYaml,
    cargar_configuracion,
    cargar_configuracion_texto,
)

RAIZ = Path(__file__).resolve().parents[1]
BASE = RAIZ / "tests" / "fixtures" / "config" / "base.yaml"
PRODUCCION = RAIZ / "config" / "oip-config.yaml"


# --- Ayudas ----------------------------------------------------------------------------


class _Volcador(yaml.SafeDumper):
    pass


_Volcador.add_representer(
    Decimal, lambda d, v: d.represent_scalar("tag:yaml.org,2002:float", str(v))
)


def _datos_base() -> dict:
    return yaml.load(BASE.read_text(encoding="utf-8"), Loader=_CargadorYaml)  # noqa: S506


def _texto(datos: dict) -> str:
    return yaml.dump(datos, Dumper=_Volcador, allow_unicode=True, sort_keys=False)


def _quitar(datos: dict, ruta: str) -> dict:
    datos = copy.deepcopy(datos)
    *padres, hoja = ruta.split(".")
    nodo = datos
    for parte in padres:
        nodo = nodo[parte]
    del nodo[hoja]
    return datos


def _poner(datos: dict, ruta: str, valor: object) -> dict:
    datos = copy.deepcopy(datos)
    *padres, hoja = ruta.split(".")
    nodo = datos
    for parte in padres:
        nodo = nodo[parte]
    nodo[hoja] = valor
    return datos


def _errores(datos: dict) -> tuple[str, ...]:
    with pytest.raises(ErrorConfiguracion) as info:
        cargar_configuracion_texto(_texto(datos))
    return info.value.errores


def _recorrer(valor: object):
    """Todos los valores de un modelo, incluidos los de tablas y tuplas."""
    if isinstance(valor, BaseModel):
        for nombre in type(valor).model_fields:
            yield from _recorrer(getattr(valor, nombre))
    elif isinstance(valor, dict | tuple | list) or hasattr(valor, "items"):
        elementos = valor.values() if hasattr(valor, "values") else valor
        for elemento in elementos:
            yield from _recorrer(elemento)
    else:
        yield valor


# --- Los dos archivos del repo (2.2) ---------------------------------------------------


@pytest.mark.parametrize("ruta", [BASE, PRODUCCION], ids=["base", "produccion"])
def test_los_archivos_del_repo_cargan(ruta):
    cargada = cargar_configuracion(ruta)
    assert isinstance(cargada, ConfiguracionVersionada)
    assert cargada.version
    assert cargada.schema_version in ESQUEMAS_SOPORTADOS
    assert len(cargada.sha256) == 64
    assert int(cargada.sha256, 16) >= 0
    assert cargada.origen == ruta.name


@pytest.mark.parametrize("ruta", [BASE, PRODUCCION], ids=["base", "produccion"])
def test_ningun_valor_es_float(ruta):
    contenido = cargar_configuracion(ruta).contenido
    assert not any(isinstance(v, float) for v in _recorrer(contenido))


def test_base_tiene_el_guion_del_req_como_clave_ausente():
    # REQ §5: "—" = la configuración de prueba no trae ese valor (design.md §7).
    categorias = cargar_configuracion(BASE).contenido.categories
    assert categorias[Categoria.HOME_KITCHEN].commission is None
    assert categorias[Categoria.ELECTRONICS].commission is None
    assert categorias[Categoria.VIDEO_GAMES].commission is None
    assert categorias[Categoria.TOYS].commission is None
    assert categorias[Categoria.WATCHES].return_rate is None
    assert categorias[Categoria.JEWELRY].return_rate is None
    assert categorias[Categoria.TOYS].return_rate is None
    con_umbral = {c for c, v in categorias.items() if v.main_category_size is not None}
    assert con_umbral == {Categoria.TOOLS, Categoria.HOME_LIGHTING}


def test_base_valores_del_req_5():
    contenido = cargar_configuracion(BASE).contenido
    herramientas = contenido.categories[Categoria.TOOLS]
    assert herramientas.commission.rate_pct == Decimal("15")
    assert herramientas.commission.min_per_unit == Decimal("0.30")
    assert herramientas.return_rate.rate_pct == Decimal("7")
    # Umbral 168,440 = tamaño × 0.5% (DEC-225).
    umbral = herramientas.main_category_size * contenido.amazon.demand.category_rank_pct / 100
    assert int(umbral) == 168440
    belleza = contenido.categories[Categoria.BEAUTY].commission
    assert isinstance(belleza, ComisionConUmbral)
    assert (belleza.threshold, belleza.rate_pct_at_or_below, belleza.rate_pct_above) == (
        Decimal("10.00"),
        Decimal("8"),
        Decimal("15"),
    )
    relojes = contenido.categories[Categoria.WATCHES].commission
    assert isinstance(relojes, ComisionPorTramos)
    assert [(t.up_to, t.rate_pct) for t in relojes.tiers] == [
        (Decimal("1500.00"), Decimal("16")),
        (None, Decimal("3")),
    ]
    consolas = contenido.categories[Categoria.VIDEO_GAME_CONSOLES].return_rate
    assert isinstance(consolas, TasaAsignada)
    assert consolas.from_category is Categoria.ELECTRONICS
    assert contenido.taxes.fallback_rate_pct == Decimal("7.75")
    assert contenido.taxes.locations["tienda_prueba"].rate_pct == Decimal("7.75")
    assert contenido.taxes.locations["chula_vista"].rate_pct == Decimal("8.75")
    traslado = contenido.local_sale.transport
    entrega = (
        traslado.default_delivery_km * traslado.cost_per_km
        + traslado.default_delivery_hours * traslado.hour_value
    )
    assert entrega == Decimal("9.50")  # REQ §5, S-24
    assert contenido.general.timezone == "America/Tijuana"
    assert set(contenido.levels.thresholds) == set(Nivel)


def test_produccion_toma_de_las_rn_los_guiones_del_req():
    # DEC-234 punto 7 (PROVISIONAL hasta que Jesús revise el PR de T02).
    categorias = cargar_configuracion(PRODUCCION).contenido.categories
    assert categorias[Categoria.ELECTRONICS].commission.rate_pct == Decimal("8")  # RN-006
    assert categorias[Categoria.TOYS].commission.rate_pct == Decimal("15")  # RN-006
    assert categorias[Categoria.VIDEO_GAMES].commission.rate_pct == Decimal("15")  # RN-006
    assert categorias[Categoria.WATCHES].return_rate.rate_pct == Decimal("12")  # RN-005
    assert categorias[Categoria.JEWELRY].return_rate.rate_pct == Decimal("11")  # RN-005
    assert categorias[Categoria.TOYS].return_rate.rate_pct == Decimal("5")  # RN-005
    # RN-006 §4.1 no da comisión de "Hogar y cocina": sigue ausente (COMISIÓN DESCONOCIDA).
    assert categorias[Categoria.HOME_KITCHEN].commission is None


# --- Objeto inmutable con huella estable (2.1) -----------------------------------------


def test_objeto_inmutable():
    cargada = cargar_configuracion(BASE)
    with pytest.raises(dataclasses.FrozenInstanceError):
        cargada.version = "otra"  # type: ignore[misc]
    with pytest.raises(Exception):  # noqa: B017 (pydantic ValidationError por frozen)
        cargada.contenido.general.timezone = "UTC"  # type: ignore[misc]
    with pytest.raises(TypeError):
        cargada.contenido.categories[Categoria.TOOLS] = None  # type: ignore[index]
    with pytest.raises(TypeError):
        cargada.contenido.general.rn_versions["RN-001"] = 9  # type: ignore[index]
    assert isinstance(cargada.contenido.shipping.weight_bands, tuple)
    assert isinstance(cargada.contenido.lists.avoid_always, tuple)


def test_huella_estable_ante_comentarios_espacios_y_fin_de_linea():
    texto = BASE.read_text(encoding="utf-8")
    original = cargar_configuracion_texto(texto).sha256
    assert cargar_configuracion_texto(texto).sha256 == original
    otra_forma = "# comentario nuevo\n" + texto.replace("\n", "  \r\n")
    assert cargar_configuracion_texto(otra_forma).sha256 == original


def test_huella_cambia_si_cambia_un_valor():
    datos = _datos_base()
    original = cargar_configuracion_texto(_texto(datos)).sha256
    cambiado = _poner(datos, "local_sale.negotiation_pct", 12)
    assert cargar_configuracion_texto(_texto(cambiado)).sha256 != original


def test_numeros_con_punto_son_decimal_exacto():
    contenido = cargar_configuracion(BASE).contenido
    assert contenido.taxes.fallback_rate_pct == Decimal("7.75")
    assert str(contenido.local_sale.transport.cost_per_km) == "0.20"
    assert isinstance(contenido.amazon.demand.category_rank_pct, Decimal)
    assert contenido.taxes.locations["chula_vista"].effective_date == date(2026, 1, 1)


# --- Parámetro faltante, tipo inválido y sección desconocida (2.1) ---------------------


@pytest.mark.parametrize(
    "ruta",
    [
        "version",
        "schemaVersion",
        "general.timezone",
        "general.rn_versions",
        "retailers",
        "categories.tools.return_loss_pct",
        "categories.tools.commission.min_per_unit",
        "lists.toy_season",
        "shipping.unknown_weight.packaging",
        "taxes.fallback_rate_pct",
        "price_reference.clearance_episode_max_days",
        "private_sellers.cities",
        "discount_quality.quality.min_other_retailers",
        "amazon.sale_days_by_rank.slow_days",
        "local_sale.transport.hour_value",
        "levels.channel_tiebreak_pct",
    ],
)
def test_parametro_faltante_rechaza_con_su_nombre(ruta):
    errores = _errores(_quitar(_datos_base(), ruta))
    assert f"{ruta}: falta el parámetro" in errores


def test_falta_un_nivel_rechaza():
    errores = _errores(_quitar(_datos_base(), "levels.thresholds.VIGILAR"))
    assert any(e.startswith("levels:") and "VIGILAR" in e for e in errores)


def test_faltan_versiones_de_rn():
    errores = _errores(_quitar(_datos_base(), "general.rn_versions.RN-018"))
    assert any(e.startswith("general:") and "RN-018" in e for e in errores)


@pytest.mark.parametrize(
    ("ruta", "valor"),
    [
        ("categories.tools.return_loss_pct", "50"),  # texto en un porcentaje
        ("categories.tools.return_loss_pct", True),  # bandera en un porcentaje
        ("categories.tools.return_loss_pct", 150),  # fuera de 0 a 100
        ("price_reference.usual_window_days", Decimal("60.5")),  # decimal en un entero
        ("price_reference.usual_window_days", "60"),
        ("categories.tools.amazon_restricted", "no"),  # texto en una bandera
        ("taxes.fallback_rate_pct", -1),
        ("general.currency", "MXN"),
        ("general.timezone", "Marte/Olimpo"),
        ("categories.tools.initial_local_demand", "regular"),
        ("categories.tools.commission.type", "por_pieza"),  # el error va en commission
        # Dominios sintéticos: los de comercios solo van en config/ y tests/fixtures/.
        ("retailers.homedepot.domains", ["https://example.com/"]),  # dominio con esquema
        ("retailers.homedepot.domains", "example.com"),  # texto en vez de lista
        ("taxes.locations.chula_vista.effective_date", "2026-01-01"),  # texto, no fecha
        ("lists.toy_season.start", "13-01"),
        ("levels.thresholds.VIGILAR.alert", "telegram"),
    ],
)
def test_tipo_invalido_rechaza_con_su_nombre(ruta, valor):
    errores = _errores(_poner(_datos_base(), ruta, valor))
    # Una unión discriminada reporta la etiqueta desconocida en el campo de la unión.
    esperado = ruta.removesuffix(".type")
    assert any(e.startswith(esperado) for e in errores), errores


def test_schema_version_no_soportado():
    errores = _errores(_poner(_datos_base(), "schemaVersion", "99"))
    assert any(e.startswith("schemaVersion:") for e in errores)


@pytest.mark.parametrize(
    "ruta",
    [
        "alerts",  # sección de la parte C
        "general.locale",
        "categories.tools.notes",
        "amazon.demand.keepa",
    ],
)
def test_seccion_o_parametro_desconocido_rechaza(ruta):
    errores = _errores(_poner(_datos_base(), ruta, {}))
    assert f"{ruta}: sección o parámetro desconocido" in errores


def test_categoria_fuera_del_catalogo_rechaza():
    datos = _datos_base()
    datos["categories"]["garden"] = copy.deepcopy(datos["categories"]["tools"])
    errores = _errores(datos)
    assert any(e.startswith("categories.garden") for e in errores)


def test_rechaza_el_archivo_entero_con_todos_los_errores():
    datos = _quitar(_datos_base(), "taxes.fallback_rate_pct")
    datos = _poner(datos, "levels.cheaper_competition_pct", "15")
    datos = _poner(datos, "extra", 1)
    errores = _errores(datos)
    assert "taxes.fallback_rate_pct: falta el parámetro" in errores
    assert any(e.startswith("levels.cheaper_competition_pct") for e in errores)
    assert "extra: sección o parámetro desconocido" in errores


def test_tasa_asignada_a_categoria_sin_tasa_propia_rechaza():
    # S-27: la tasa asignada referencia otra categoría con tasa propia.
    datos = _poner(
        _datos_base(),
        "categories.toys.return_rate",
        {"source": "assigned", "from_category": "watches"},
    )
    errores = _errores(datos)
    assert any("categories.toys.return_rate.from_category" in e for e in errores)


def test_sucursal_de_comercio_desconocido_rechaza():
    datos = _poner(_datos_base(), "stores.xx-1", {"retailer": "kmart"})
    assert any("stores.xx-1.retailer" in e for e in _errores(datos))


def test_tramos_mal_formados_rechazan():
    datos = _poner(
        _datos_base(),
        "categories.watches.commission.tiers",
        [{"up_to": None, "rate_pct": 16}, {"up_to": Decimal("1500"), "rate_pct": 3}],
    )
    assert any(e.startswith("categories.watches.commission") for e in _errores(datos))


def test_rangos_de_peso_deben_llegar_al_limite_de_cotizar():
    datos = _poner(_datos_base(), "shipping.quote_above_kg", 8)
    assert any(e.startswith("shipping") for e in _errores(datos))


def test_clave_repetida_rechaza():
    texto = BASE.read_text(encoding="utf-8").replace(
        "  currency: USD", "  currency: USD\n  currency: USD", 1
    )
    with pytest.raises(ErrorConfiguracion, match="clave repetida"):
        cargar_configuracion_texto(texto)


@pytest.mark.parametrize("texto", ["", "- una\n- lista\n", "version: [sin cerrar\n"])
def test_archivo_que_no_es_un_mapa_valido_rechaza(texto):
    with pytest.raises(ErrorConfiguracion):
        cargar_configuracion_texto(texto)


# --- Sin valores por defecto en el código (design.md §7) -------------------------------

# Solo pueden faltar el "—" del REQ §5 por categoría y los datos que son opcionales por regla.
_OPCIONALES = {
    "ValoresCategoria.commission",
    "ValoresCategoria.return_rate",
    "ValoresCategoria.main_category_size",
    "Sucursal.max_units_per_customer",
    "Plataforma.path_prefix",
    "ProductoRef.gtin",
    "ProductoRef.brand",
    "ProductoRef.model",
}


def _modelos(modelo: type[BaseModel], vistos: set) -> None:
    if modelo in vistos:
        return
    vistos.add(modelo)
    for campo in modelo.model_fields.values():
        for tipo in _tipos(campo.annotation):
            if isinstance(tipo, type) and issubclass(tipo, BaseModel):
                _modelos(tipo, vistos)


def _tipos(anotacion):
    yield anotacion
    for argumento in getattr(anotacion, "__args__", ()) or ():
        yield from _tipos(argumento)
    origen = getattr(anotacion, "__origin__", None)
    if origen is not None:
        yield from _tipos(origen)


def test_sin_valores_por_defecto_salvo_los_opcionales_declarados():
    modelos: set = set()
    _modelos(Configuracion, modelos)
    con_defecto = {
        f"{m.__name__}.{nombre}"
        for m in modelos
        for nombre, campo in m.model_fields.items()
        if not campo.is_required()
    }
    assert con_defecto == _OPCIONALES
    # Y los opcionales no traen un número por defecto: su ausencia vale None.
    for m in modelos:
        for nombre, campo in m.model_fields.items():
            if f"{m.__name__}.{nombre}" in _OPCIONALES:
                assert campo.default is None


# --- Endurecimiento del esquema (decisión de Jesús del 2026-11-18, PR #32) --------------


@pytest.mark.parametrize(
    ("original", "cambio"),
    [
        ("usual_window_days: 60", "usual_window_days: 060"),  # YAML 1.1: octal = 48
        ("usual_window_days: 60", "usual_window_days: -060"),
        ("usual_window_days: 60", "usual_window_days: 0x3C"),  # hexadecimal
        ("usual_window_days: 60", "usual_window_days: 0b111100"),  # binario
        ("default_delivery_km: 10", "default_delivery_km: 1:30"),  # sexagesimal = 90
        ("default_delivery_km: 10", "default_delivery_km: 1:30.5"),
    ],
)
def test_numero_con_cero_inicial_base_o_sexagesimal_rechaza(original, cambio):
    texto = BASE.read_text(encoding="utf-8")
    assert original in texto
    with pytest.raises(ErrorConfiguracion) as info:
        cargar_configuracion_texto(texto.replace(original, cambio, 1))
    (error,) = info.value.errores
    parametro = original.split(":")[0]
    assert f"en el parámetro {parametro}" in error
    assert "número no admitido" in error
    assert "line " in error  # y su posición


def test_numeros_normales_siguen_cargando():
    texto = "a: 0\nb: 0.30\nc: 0.5\nd: 60\ne: -5\nf: 1_000\ng: 7.75\nh: -0\ni: +5\n"
    datos = yaml.load(texto, Loader=_CargadorYaml)  # noqa: S506
    assert datos == {
        "a": 0,
        "b": Decimal("0.30"),
        "c": Decimal("0.5"),
        "d": 60,
        "e": -5,
        "f": 1000,
        "g": Decimal("7.75"),
        "h": 0,
        "i": 5,
    }
    assert str(datos["b"]) == "0.30"
    assert type(datos["d"]) is int


@pytest.mark.parametrize(
    "zona",
    [
        "localtime",  # la zona del equipo: depende de la máquina
        "UTC",
        "GMT",
        "Etc/UTC",
        "Etc/GMT+8",
        "US/Pacific",  # alias, no Región/Ciudad
        "Mexico/BajaNorte",
        "posix/America/Tijuana",
        "America/Tijuana ",
        "america/tijuana",
        "America/Ciudad_Inexistente",
        "America/../Tijuana",
    ],
)
def test_zona_horaria_que_no_es_region_ciudad_rechaza(zona):
    errores = _errores(_poner(_datos_base(), "general.timezone", zona))
    assert any(e.startswith("general.timezone:") for e in errores), errores


@pytest.mark.parametrize(
    "zona", ["America/Tijuana", "America/Argentina/Buenos_Aires", "Europe/Madrid", "Asia/Tokyo"]
)
def test_zona_horaria_region_ciudad_carga(zona):
    cargada = cargar_configuracion_texto(_texto(_poner(_datos_base(), "general.timezone", zona)))
    assert cargada.contenido.general.timezone == zona


@pytest.mark.parametrize("version", ["", "   ", " escenarios-base-1", "2026-11-18.1 ", "a\nb"])
def test_version_vacia_o_con_espacios_en_los_extremos_rechaza(version):
    errores = _errores(_poner(_datos_base(), "version", version))
    assert any(e.startswith("version:") for e in errores), errores


@pytest.mark.parametrize("version", ["escenarios-base-1", "2026-11-18.1", "prueba 2"])
def test_version_sin_espacios_en_los_extremos_carga(version):
    cargada = cargar_configuracion_texto(_texto(_poner(_datos_base(), "version", version)))
    assert cargada.version == version


# Dominios sintéticos: los de comercios solo van en config/ y tests/fixtures/.
@pytest.mark.parametrize("dominio", ["10.0.0.1", "192.168.1.20", "example.123"])
def test_dominio_que_es_una_ip_rechaza(dominio):
    datos = _poner(_datos_base(), "retailers.homedepot.domains", [dominio])
    errores = _errores(datos)
    assert any(e.startswith("retailers.homedepot.domains.0:") for e in errores), errores
    datos = _poner(_datos_base(), "private_sellers.platforms", {"prueba": {"domains": [dominio]}})
    errores = _errores(datos)
    assert any(e.startswith("private_sellers.platforms.prueba.domains.0:") for e in errores)


@pytest.mark.parametrize("dominio", ["example.com", "shop.example.co", "a1.example-2.org"])
def test_dominio_con_nombre_carga(dominio):
    datos = _poner(_datos_base(), "retailers.homedepot.domains", [dominio])
    assert cargar_configuracion_texto(_texto(datos))


def test_sin_ficha_de_amazon_rechaza():
    datos = _poner(_datos_base(), "retailers.amazon.amazon_listing", False)
    errores = _errores(datos)
    assert any(e.startswith("retailers: debe haber exactamente un comercio") for e in errores)


def test_dos_fichas_de_amazon_rechaza():
    datos = _poner(_datos_base(), "retailers.walmart.amazon_listing", True)
    errores = _errores(datos)
    assert any(e.startswith("retailers: debe haber exactamente un comercio") for e in errores)


def test_errores_cruzados_salen_con_su_ruta_real():
    datos = _poner(_datos_base(), "stores.xx-1", {"retailer": "kmart"})
    assert "stores.xx-1.retailer: comercio desconocido" in _errores(datos)
    datos = _poner(
        _datos_base(),
        "categories.toys.return_rate",
        {"source": "assigned", "from_category": "watches"},
    )
    assert "categories.toys.return_rate.from_category: watches no tiene tasa propia" in (
        _errores(datos)
    )
