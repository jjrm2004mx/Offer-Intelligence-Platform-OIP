"""Configuración versionada de la parte B (CMP-04; design.md §7, PAR-01 a PAR-13).

Reglas (REQ-2026-0001 §5 y §6; RNF-2; DEC-234):

- La configuración se lee de **un archivo YAML** con ``version`` y ``schemaVersion``. Vive en
  ``config/`` (fuera de ``src/``, por el gate de egress): este módulo no conoce ningún
  dominio de comercio, solo lo recibe del archivo.
- **No hay valores por defecto en el código**: todo número de las reglas sale del archivo.
  Un parámetro faltante, un tipo inválido o una sección desconocida rechazan el archivo
  entero (``ErrorConfiguracion``) con el nombre de cada parámetro.
- Un "—" de REQ §5 es una **clave ausente**. Solo pueden faltar las claves que el esquema
  declara opcionales (por ejemplo la comisión, la tasa de devolución o el tamaño de la
  categoría de una ``category``); su ausencia la interpretan las reglas (RN-004 §11,
  §3.2.1, DEC-225).
- Montos y porcentajes son ``Decimal``. Los números del YAML con punto se leen como
  ``Decimal`` desde su texto (nunca pasan por ``float``); los enteros se aceptan en campos
  decimales. Los porcentajes van **en puntos** (``15`` = 15%), igual que
  ``oip.dinero.formatear_porcentaje``.
- El resultado es inmutable (modelos congelados, tablas como ``MappingProxyType`` y listas
  como tuplas) y trae ``version``, ``schema_version`` y una huella ``sha256`` estable: la
  del contenido canónico del archivo (claves ordenadas, decimales como texto), que no
  cambia con comentarios, espacios ni fin de línea.

Este módulo no guarda la versión en la base (T06) ni tiene la CLI (T08). Las partes A, C y
D agregan sus secciones con un ``schemaVersion`` nuevo.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    Strict,
    ValidationError,
    model_validator,
)

from oip.catalogos import Categoria, DemandaLocal, Nivel

__all__ = [
    "ESQUEMAS_SOPORTADOS",
    "Configuracion",
    "ConfiguracionVersionada",
    "ErrorConfiguracion",
    "cargar_configuracion",
    "cargar_configuracion_texto",
]

#: ``schemaVersion`` que entiende este módulo (parte B).
ESQUEMAS_SOPORTADOS = ("1",)

_RN_DEL_REQ = tuple(f"RN-{n:03d}" for n in range(1, 19))  # REQ §4: RN-001 a RN-018


class ErrorConfiguracion(ValueError):
    """El archivo de configuración no es válido; no se carga nada.

    ``errores`` trae un texto por problema, cada uno con la ruta del parámetro
    (``categories.tools.return_loss_pct``).
    """

    def __init__(self, errores: list[str] | tuple[str, ...]) -> None:
        self.errores = tuple(errores)
        super().__init__("configuración inválida:\n- " + "\n- ".join(self.errores))


# --- Tipos de valor -------------------------------------------------------------------


def _a_decimal(valor: object) -> Decimal:
    # bool es subclase de int: se rechaza antes.
    if isinstance(valor, bool) or isinstance(valor, float) or isinstance(valor, str):
        raise ValueError(f"se esperaba un número decimal, no {type(valor).__name__}")
    if isinstance(valor, int):
        return Decimal(valor)
    if isinstance(valor, Decimal):
        if not valor.is_finite():
            raise ValueError("se esperaba un número finito")
        return valor
    raise ValueError(f"se esperaba un número decimal, no {type(valor).__name__}")


def _a_tupla(valor: object) -> object:
    # Solo listas del YAML; un texto o un mapa no son listas.
    if isinstance(valor, list):
        return tuple(valor)
    return valor


def _congelar(valor: Mapping[Any, Any]) -> Mapping[Any, Any]:
    return MappingProxyType(dict(valor))


_Dec = Annotated[Decimal, BeforeValidator(_a_decimal)]
Monto = Annotated[_Dec, Field(ge=0)]
"""Monto en USD (``Decimal`` ≥ 0)."""
Porcentaje = Annotated[_Dec, Field(ge=0, le=100)]
"""Porcentaje en puntos (``15`` = 15%), sin redondear."""
Factor = Annotated[_Dec, Field(gt=0)]
Entero = Annotated[int, Strict(), Field(ge=0)]
EnteroPositivo = Annotated[int, Strict(), Field(ge=1)]
Texto = Annotated[str, Strict(), Field(min_length=1)]
Bandera = Annotated[bool, Strict()]
Fecha = Annotated[date, Strict()]
Codigo = Annotated[str, Strict(), Field(pattern=r"^[a-z0-9]+(?:[_-][a-z0-9]+)*$")]
"""Código en minúsculas y snake_case (o con guion, como ``hd-0123``)."""
Dominio = Annotated[str, Strict(), Field(max_length=253, pattern=r"^[a-z0-9-]+(?:\.[a-z0-9-]+)+$")]
"""Dominio sin esquema ni ruta, en minúsculas (``example.com``)."""
MesDia = Annotated[str, Strict(), Field(pattern=r"^\d{2}-\d{2}$")]


def _tupla(tipo: Any) -> Any:
    return Annotated[tuple[tipo, ...], BeforeValidator(_a_tupla)]


def _tabla(clave: Any, valor: Any, *, minimo: int = 0) -> Any:
    return Annotated[dict[clave, valor], Field(min_length=minimo), AfterValidator(_congelar)]


class _Seccion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- PAR-01 general --------------------------------------------------------------------


class CuentaAmazon(StrEnum):
    NEW = "new"
    ESTABLISHED = "established"


def _zona_valida(nombre: str) -> str:
    try:
        ZoneInfo(nombre)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"zona horaria desconocida: {nombre}") from None
    return nombre


class General(_Seccion):
    """PAR-01: zona del día calendario, moneda, cuenta de Amazon y versión de cada RN."""

    timezone: Annotated[Texto, AfterValidator(_zona_valida)]
    currency: Literal["USD"]
    amazon_account: CuentaAmazon
    rn_versions: _tabla(Annotated[str, Strict(), Field(pattern=r"^RN-\d{3}$")], EnteroPositivo)

    @model_validator(mode="after")
    def _todas_las_rn(self) -> General:
        faltan = [rn for rn in _RN_DEL_REQ if rn not in self.rn_versions]
        sobran = [rn for rn in self.rn_versions if rn not in _RN_DEL_REQ]
        if faltan or sobran:
            raise ValueError(
                f"rn_versions debe traer RN-001 a RN-018; faltan {faltan}, sobran {sobran}"
            )
        return self


# --- PAR-02 retailers y PAR-03 stores --------------------------------------------------


class Comercio(_Seccion):
    """PAR-02: cadena, dominios autorizados y si es la ficha de Amazon."""

    chain: Codigo
    domains: Annotated[_tupla(Dominio), Field(min_length=1)]
    amazon_listing: Bandera


class Sucursal(_Seccion):
    """PAR-03: comercio y, si lo hay, límite de unidades por cliente (RN-008 §4.4)."""

    retailer: Codigo
    max_units_per_customer: EnteroPositivo | None = None


# --- PAR-04 categories -----------------------------------------------------------------


class ComisionFija(_Seccion):
    """Un porcentaje del precio de venta (RN-006 §4.1)."""

    type: Literal["flat"]
    rate_pct: Porcentaje
    min_per_unit: Monto


class ComisionConUmbral(_Seccion):
    """Un porcentaje del **total** según el total quede hasta el umbral o lo pase (DEC-217)."""

    type: Literal["total_threshold"]
    threshold: Monto
    rate_pct_at_or_below: Porcentaje
    rate_pct_above: Porcentaje
    min_per_unit: Monto


class Tramo(_Seccion):
    up_to: Monto | None
    rate_pct: Porcentaje


class ComisionPorTramos(_Seccion):
    """Porcentaje parte por parte (DEC-217). El último tramo no tiene ``up_to``."""

    type: Literal["tiers"]
    tiers: Annotated[_tupla(Tramo), Field(min_length=2)]
    min_per_unit: Monto

    @model_validator(mode="after")
    def _tramos_crecientes(self) -> ComisionPorTramos:
        limites = [t.up_to for t in self.tiers]
        if limites[-1] is not None or any(lim is None for lim in limites[:-1]):
            raise ValueError("solo el último tramo va sin up_to")
        if any(a >= b for a, b in zip(limites[:-2], limites[1:-1], strict=True)):
            raise ValueError("los up_to de los tramos deben ser crecientes")
        return self


Comision = Annotated[
    ComisionFija | ComisionConUmbral | ComisionPorTramos, Field(discriminator="type")
]


class TasaPropia(_Seccion):
    source: Literal["own"]
    rate_pct: Porcentaje


class TasaAsignada(_Seccion):
    """Tasa de otra categoría, con marca ``ESTIMADO (devolución)`` (S-27)."""

    source: Literal["assigned"]
    from_category: Categoria


TasaDevolucion = Annotated[TasaPropia | TasaAsignada, Field(discriminator="source")]


class ValoresCategoria(_Seccion):
    """PAR-04: valores por código de ``category``. Las claves opcionales son el "—" del REQ."""

    commission: Comision | None = None
    return_rate: TasaDevolucion | None = None
    return_loss_pct: Porcentaje
    amazon_restricted: Bandera
    main_category_size: EnteroPositivo | None = None
    subcategory_rank_required: Bandera
    initial_local_demand: DemandaLocal
    provenance_risk: Bandera


# --- PAR-05 lists ----------------------------------------------------------------------


class ProductoRef(_Seccion):
    """Un producto por GTIN o por marca + modelo (RN-013)."""

    gtin: Annotated[str, Strict(), Field(pattern=r"^\d{8,14}$")] | None = None
    brand: Texto | None = None
    model: Texto | None = None

    @model_validator(mode="after")
    def _identificado(self) -> ProductoRef:
        if self.gtin is None and (self.brand is None or self.model is None):
            raise ValueError("el producto necesita gtin, o brand y model")
        return self


def _mes_dia_valido(valor: str) -> str:
    mes, dia = (int(x) for x in valor.split("-"))
    try:
        date(2024, mes, dia)  # año bisiesto: admite 02-29
    except ValueError:
        raise ValueError(f"no es una fecha MM-DD válida: {valor}") from None
    return valor


class Temporada(_Seccion):
    """Fechas ``MM-DD`` de inicio y fin, inclusivas (S-10)."""

    start: Annotated[MesDia, AfterValidator(_mes_dia_valido)]
    end: Annotated[MesDia, AfterValidator(_mes_dia_valido)]


class Listas(_Seccion):
    """PAR-05: restricciones de Amazon, evitar siempre, lujo, material peligroso, procedencia."""

    amazon_restricted_brands: _tupla(Texto)
    amazon_restricted_products: _tupla(ProductoRef)
    avoid_always: _tupla(ProductoRef)
    luxury_brands: _tupla(Texto)
    hazmat_brands: _tupla(Texto)
    hazmat_products: _tupla(ProductoRef)
    provenance_risk_brands: _tupla(Texto)
    provenance_risk_products: _tupla(ProductoRef)
    toy_season: Temporada


# --- PAR-06 shipping -------------------------------------------------------------------


class RangoPeso(_Seccion):
    max_kg: Factor
    shipping: Monto
    packaging: Monto


class EnvioSinPeso(_Seccion):
    shipping: Monto
    packaging: Monto


class Cotizacion(_Seccion):
    product: ProductoRef
    shipping: Monto
    date: Fecha


class Envio(_Seccion):
    """PAR-06: rangos FBM, sin peso (S-06), límite para cotizar y cotizaciones capturadas."""

    weight_bands: Annotated[_tupla(RangoPeso), Field(min_length=1)]
    unknown_weight: EnvioSinPeso
    quote_above_kg: Factor
    quotes: _tupla(Cotizacion)
    shipping_to_me_default: Monto

    @model_validator(mode="after")
    def _rangos_hasta_el_limite(self) -> Envio:
        pesos = [r.max_kg for r in self.weight_bands]
        if any(a >= b for a, b in zip(pesos, pesos[1:], strict=False)):
            raise ValueError("los max_kg de weight_bands deben ser crecientes")
        if pesos[-1] != self.quote_above_kg:
            raise ValueError("el último max_kg de weight_bands debe ser quote_above_kg")
        return self


# --- PAR-07 taxes ----------------------------------------------------------------------


class TasaUbicacion(_Seccion):
    rate_pct: Porcentaje
    source: Texto
    effective_date: Fecha


class Impuestos(_Seccion):
    """PAR-07: tasa por ``taxLocation``, respaldo (DEC-220) y particulares (S-14)."""

    locations: _tabla(Codigo, TasaUbicacion)
    fallback_rate_pct: Porcentaje
    private_sellers_exempt: Bandera


# --- PAR-08 price_reference ------------------------------------------------------------


class ReferenciaPrecio(_Seccion):
    """PAR-08: ventanas del precio habitual, del episodio y del mercado hoy (RN-002, DEC-201)."""

    usual_window_days: EnteroPositivo
    sufficient_history_observations: EnteroPositivo
    sufficient_history_days: EnteroPositivo
    clearance_episode_max_days: EnteroPositivo
    market_today_max_age_hours: EnteroPositivo
    store_typical_window_days: EnteroPositivo
    amazon_min_window_days: EnteroPositivo


# --- PAR-09 private_sellers ------------------------------------------------------------


class Plataforma(_Seccion):
    domains: Annotated[_tupla(Dominio), Field(min_length=1)]
    path_prefix: Annotated[str, Strict(), Field(pattern=r"^/[^\s]*$")] | None = None


class Ciudad(_Seccion):
    pickup_km: Monto
    pickup_hours: Monto
    in_local_sale_zone: Bandera


class Particulares(_Seccion):
    """PAR-09: plataformas permitidas (DEC-212) y ciudades de recogida (DEC-223, DEC-171)."""

    platforms: _tabla(Codigo, Plataforma, minimo=1)
    cities: _tabla(Codigo, Ciudad, minimo=1)


# --- PAR-10 discount_quality -----------------------------------------------------------


class CalidadPrecio(_Seccion):
    good_offer_min_discount_pct: Porcentaje
    cheapest_tolerance_pct: Porcentaje
    exceptional_min_history_days: EnteroPositivo
    min_other_retailers: EnteroPositivo


class DescuentoYCalidad(_Seccion):
    """PAR-10: franjas del descuento real, inflado (RN-003) y calidad del precio (RN-012)."""

    discard_below_pct: Porcentaje
    reference_only_below_pct: Porcentaje
    inflated_factor: Factor
    quality: CalidadPrecio

    @model_validator(mode="after")
    def _franjas_ordenadas(self) -> DescuentoYCalidad:
        if self.discard_below_pct > self.reference_only_below_pct:
            raise ValueError("discard_below_pct no puede pasar de reference_only_below_pct")
        return self


# --- PAR-11 amazon ---------------------------------------------------------------------


class DemandaAmazon(_Seccion):
    category_rank_pct: Porcentaje
    subcategory_max_rank: EnteroPositivo
    max_new_sellers: Entero
    worsening_pct: Porcentaje
    rank_window_days: EnteroPositivo
    trend_lookback_days: EnteroPositivo


class DiasVenta(_Seccion):
    """Días de venta por ranking: < ``fast_below_rank``; ≤ ``medium_up_to_rank``; el resto."""

    fast_below_rank: EnteroPositivo
    fast_days: EnteroPositivo
    medium_up_to_rank: EnteroPositivo
    medium_days: EnteroPositivo
    slow_days: EnteroPositivo

    @model_validator(mode="after")
    def _cortes_crecientes(self) -> DiasVenta:
        if self.fast_below_rank > self.medium_up_to_rank:
            raise ValueError("fast_below_rank no puede pasar de medium_up_to_rank")
        return self


class DiasPago(_Seccion):
    new: Entero
    established: Entero


class Castigo(_Seccion):
    drop_weight_pct: Porcentaje
    without_minimum_pct: Porcentaje


class TopePrimeraCompra(_Seccion):
    units: EnteroPositivo
    boosted_units: EnteroPositivo
    boosted_below_rank: EnteroPositivo
    boosted_levels: Annotated[_tupla(Nivel), Field(min_length=1)]


class Amazon(_Seccion):
    """PAR-11: demanda (RN-004), ranking (DEC-206), días, pago, castigo y tope (RN-005)."""

    demand: DemandaAmazon
    sale_days_by_rank: DiasVenta
    payment_days: DiasPago
    drop_penalty: Castigo
    first_purchase_cap: TopePrimeraCompra
    max_units_without_monthly_sales: EnteroPositivo
    other_selling_costs: Monto


# --- PAR-12 local_sale -----------------------------------------------------------------


class Usados(_Seccion):
    min_comparables: EnteroPositivo
    asking_price_factor_pct: Porcentaje


class DemandaLocalConfig(_Seccion):
    days_per_unit_high: EnteroPositivo
    days_per_unit_medium: EnteroPositivo
    competition_threshold: Entero


class Traslados(_Seccion):
    cost_per_km: Monto
    hour_value: Monto
    fixed_costs: Monto
    default_delivery_km: Monto
    default_delivery_hours: Monto


class VentaLocal(_Seccion):
    """PAR-12: precio local (RN-016), usados (RN-014), demanda (RN-017) y traslados (RN-008)."""

    market_today_pct: Porcentaje
    negotiation_pct: Porcentaje
    used_reference_value_pct: Porcentaje
    used: Usados
    demand: DemandaLocalConfig
    return_rate_pct: Porcentaje
    payment_days: Entero
    transport: Traslados


# --- PAR-13 levels ---------------------------------------------------------------------


class TipoAviso(StrEnum):
    IMMEDIATE = "immediate"
    DIGEST = "digest"
    DASHBOARD = "dashboard"


class UmbralNivel(_Seccion):
    min_real_discount_pct: Porcentaje
    min_adjusted_margin_pct: Porcentaje
    alert: TipoAviso


class MinimoPorUnidad(_Seccion):
    amount: Monto
    pct_of_purchase_cost: Porcentaje


class VentanasConfianza(_Seccion):
    """Horas de RN-007 §4.1: cantidad exacta Alta, sin número Media y límite de cualquier dato."""

    exact_high_max_hours: Factor
    no_number_medium_max_hours: Factor
    max_age_hours: Factor


class Confianza(_Seccion):
    normal: VentanasConfianza
    clearance: VentanasConfianza
    few_units_medium_max_hours: Factor


class Niveles(_Seccion):
    """PAR-13: niveles (RN-009), mínimo por unidad, competencia, confianza y desempate."""

    thresholds: _tabla(Nivel, UmbralNivel)
    min_per_unit: MinimoPorUnidad
    cheaper_competition_pct: Porcentaje
    confidence: Confianza
    channel_tiebreak_pct: Porcentaje

    @model_validator(mode="after")
    def _los_cuatro_niveles(self) -> Niveles:
        faltan = [n.value for n in Nivel if n not in self.thresholds]
        if faltan:
            raise ValueError(f"thresholds debe traer los cuatro niveles; faltan {faltan}")
        return self


# --- Archivo completo ------------------------------------------------------------------


class Configuracion(_Seccion):
    """Contenido validado de un archivo de configuración (PAR-01 a PAR-13)."""

    version: Texto
    schema_version: Literal["1"] = Field(alias="schemaVersion")
    general: General
    retailers: _tabla(Codigo, Comercio, minimo=1)
    stores: _tabla(Codigo, Sucursal)
    categories: _tabla(Categoria, ValoresCategoria, minimo=1)
    lists: Listas
    shipping: Envio
    taxes: Impuestos
    price_reference: ReferenciaPrecio
    private_sellers: Particulares
    discount_quality: DescuentoYCalidad
    amazon: Amazon
    local_sale: VentaLocal
    levels: Niveles

    @model_validator(mode="after")
    def _referencias_cruzadas(self) -> Configuracion:
        errores: list[str] = []
        for codigo, sucursal in self.stores.items():
            if sucursal.retailer not in self.retailers:
                errores.append(f"stores.{codigo}.retailer: comercio desconocido")
        fichas = [c for c, v in self.retailers.items() if v.amazon_listing]
        if len(fichas) > 1:
            errores.append(f"retailers: solo un comercio puede ser la ficha de Amazon: {fichas}")
        for codigo, valores in self.categories.items():
            tasa = valores.return_rate
            if isinstance(tasa, TasaAsignada):
                origen = self.categories.get(tasa.from_category)
                if origen is None or not isinstance(origen.return_rate, TasaPropia):
                    errores.append(
                        f"categories.{codigo}.return_rate.from_category: "
                        f"{tasa.from_category} no tiene tasa propia"
                    )
        if errores:
            raise ValueError("; ".join(errores))
        return self


@dataclass(frozen=True, slots=True)
class ConfiguracionVersionada:
    """Configuración cargada: el contenido validado más su versión y su huella."""

    version: str
    schema_version: str
    sha256: str
    contenido: Configuracion
    origen: str


# --- Lectura del YAML ------------------------------------------------------------------


class _CargadorYaml(yaml.SafeLoader):
    """``SafeLoader`` que lee los números con punto como ``Decimal`` y rechaza claves repetidas."""


def _decimal_desde_yaml(cargador: yaml.SafeLoader, nodo: yaml.ScalarNode) -> Decimal:
    texto = str(cargador.construct_scalar(nodo)).replace("_", "")
    try:
        valor = Decimal(texto)
    except InvalidOperation:
        raise yaml.constructor.ConstructorError(
            None, None, f"número no válido: {texto}", nodo.start_mark
        ) from None
    if not valor.is_finite():
        raise yaml.constructor.ConstructorError(
            None, None, f"número no finito: {texto}", nodo.start_mark
        )
    return valor


def _mapa_sin_repetidos(cargador: yaml.SafeLoader, nodo: yaml.MappingNode) -> dict[Any, Any]:
    cargador.flatten_mapping(nodo)
    resultado: dict[Any, Any] = {}
    for nodo_clave, nodo_valor in nodo.value:
        clave = cargador.construct_object(nodo_clave, deep=True)
        if clave in resultado:
            raise yaml.constructor.ConstructorError(
                None, None, f"clave repetida: {clave}", nodo_clave.start_mark
            )
        resultado[clave] = cargador.construct_object(nodo_valor, deep=True)
    return resultado


_CargadorYaml.add_constructor("tag:yaml.org,2002:float", _decimal_desde_yaml)
_CargadorYaml.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapa_sin_repetidos)


def _canonico(valor: Any) -> Any:
    if isinstance(valor, Mapping):
        return {str(k): _canonico(v) for k, v in valor.items()}
    if isinstance(valor, list | tuple):
        return [_canonico(v) for v in valor]
    if isinstance(valor, Decimal):
        return {"$decimal": str(valor)}
    if isinstance(valor, date):
        return {"$date": valor.isoformat()}
    return valor


def _huella(datos: Mapping[str, Any]) -> str:
    texto = json.dumps(_canonico(datos), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _ruta(loc: tuple[int | str, ...]) -> str:
    # pydantic agrega a la ruta el nombre de la variante de una unión discriminada.
    partes = [str(p) for p in loc if not (isinstance(p, str) and p in _VARIANTES)]
    return ".".join(partes) or "(archivo)"


_VARIANTES = {"flat", "total_threshold", "tiers", "own", "assigned"}


def _traducir(error: ValidationError) -> list[str]:
    mensajes = []
    for detalle in error.errors(include_url=False):
        ruta = _ruta(detalle["loc"])
        tipo = detalle["type"]
        if tipo == "missing":
            mensajes.append(f"{ruta}: falta el parámetro")
        elif tipo == "extra_forbidden":
            mensajes.append(f"{ruta}: sección o parámetro desconocido")
        else:
            mensajes.append(f"{ruta}: tipo o valor inválido ({detalle['msg']})")
    return mensajes


def cargar_configuracion_texto(texto: str, origen: str = "<texto>") -> ConfiguracionVersionada:
    """Valida el texto YAML completo y devuelve la configuración con su huella.

    Levanta ``ErrorConfiguracion`` si el archivo no es YAML válido o no cumple el esquema.
    """
    try:
        # _CargadorYaml es un SafeLoader que lee los números con punto como Decimal.
        datos = yaml.load(texto, Loader=_CargadorYaml)  # noqa: S506  # nosec B506
    except yaml.YAMLError as error:
        raise ErrorConfiguracion([f"el archivo no es YAML válido: {error}"]) from None
    if not isinstance(datos, dict):
        raise ErrorConfiguracion(["el archivo debe ser un mapa de secciones"])
    try:
        contenido = Configuracion.model_validate(datos)
    except ValidationError as error:
        raise ErrorConfiguracion(_traducir(error)) from None
    return ConfiguracionVersionada(
        version=contenido.version,
        schema_version=contenido.schema_version,
        sha256=_huella(datos),
        contenido=contenido,
        origen=origen,
    )


def cargar_configuracion(ruta: str | Path) -> ConfiguracionVersionada:
    """Lee y valida un archivo YAML de configuración (UTF-8)."""
    ruta = Path(ruta)
    return cargar_configuracion_texto(ruta.read_text(encoding="utf-8"), origen=ruta.name)
