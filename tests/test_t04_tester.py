"""Pruebas de oip-tester para T04 de req-2026-0001-b-evaluacion (contexto, registro,
precedencia y esqueleto del motor; CMP-09, CMP-16, CMP-17, CTR-06, RNF-3).

T04 no tiene escenarios propios (tasks.md §4: la precedencia la verifican B3 y B29 en T18).
Estas pruebas cubren sus comportamientos esperados de forma independiente de las del
developer; los oráculos se copian de las fuentes, no del código:

- la tabla de §3.2.3 (motivo, orden y "lleva a") y la precedencia de §3.2.4, escritas aquí
  a mano desde el REQ;
- las columnas de TAB-10 y TAB-11 (design.md §4) y los elementos de REQ §7, escritos a mano;
- CTR-06 (design.md §6) comprobado sobre el texto JSON, sin usar el decodificador del código;
- pureza de ``evaluacion/`` (design.md §14) por AST y ejecutando el motor sin red ni archivos;
- tipos estrictos (DEC-238) y sin ``float`` (design.md §8).

Sin marcador de escenario. Fixtures sintéticos con example.com; ninguna prueba abre una URL.
"""

from __future__ import annotations

import ast
import builtins
import dataclasses
import datetime as dt
import itertools
import json
import re
import socket
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from oip.catalogos import (
    CalidadPrecio,
    Canal,
    CausaCanalPorRevisar,
    Confianza,
    EstadoCanal,
    Identificacion,
    Motivo,
    Nivel,
    ReferenciaPrecio,
    Resultado,
)
from oip.configuracion import cargar_configuracion
from oip.entradas.capturas import leer_captura
from oip.entradas.contrato import leer_observacion
from oip.evaluacion import motor
from oip.evaluacion.contexto import (
    ContextoEvaluacion,
    Episodio,
    ErrorSerializacion,
    EvaluacionCanal,
    ObservacionRegistrada,
    ObservacionUsada,
    Referencias,
    RegistroEvaluacion,
)
from oip.evaluacion.resultado import decidir, reunir_motivos

RAIZ = Path(__file__).resolve().parent
SRC_EVALUACION = RAIZ.parent / "src" / "oip" / "evaluacion"
CONFIG = cargar_configuracion(RAIZ / "fixtures" / "config" / "base.yaml")

# --- Oráculos copiados del REQ ------------------------------------------------------------

# REQ §3.2.3, en orden: (código, "lleva a").
TABLA_3_2_3 = (
    ("EVITAR", "DESCARTADA"),
    ("MERCADO YA BARATO", "DESCARTADA"),
    ("SIN CANAL DISPONIBLE", "DESCARTADA"),
    ("MARGEN NEGATIVO", "DESCARTADA"),
    ("SOLO REFERENCIA", "SOLO_REFERENCIA"),
    ("SIN HISTORIAL SUFICIENTE", "REVISION_MANUAL"),
    ("SIN REFERENCIA DE USADOS", "REVISION_MANUAL"),
    ("COINCIDENCIA NO CONFIRMADA", "REVISION_MANUAL"),
    ("VENDEDOR EXTERNO", "REVISION_MANUAL"),
    ("PARTICULAR", "REVISION_MANUAL"),
    ("RIESGO DE PROCEDENCIA", "REVISION_MANUAL"),
    ("DEMANDA DESCONOCIDA", "REVISION_MANUAL"),
)
LLEVA_A = dict(TABLA_3_2_3)
ORDEN_3_2_3 = [codigo for codigo, _ in TABLA_3_2_3]


def _oraculo_3_2_4(codigos: set[str], hay_nivel: bool) -> tuple[str, str | None, list[str]]:
    """REQ §3.2.4 punto por punto, con la tabla de arriba."""
    todos = [c for c in ORDEN_3_2_3 if c in codigos]
    principal = todos[0] if todos else None
    if any(LLEVA_A[c] == "DESCARTADA" for c in todos):  # punto 1
        return "DESCARTADA", principal, todos
    if "SOLO REFERENCIA" in todos:  # punto 2
        return "SOLO_REFERENCIA", principal, todos
    if any(LLEVA_A[c] == "REVISION_MANUAL" for c in todos):  # punto 3
        return "REVISION_MANUAL", principal, todos
    return ("NIVEL_ASIGNADO" if hay_nivel else "SIN_NIVEL"), None, todos  # punto 4


# design.md §4, TAB-10 (columnas en el orden del diseño).
COLUMNAS_TAB_10 = (
    "id evaluated_at offer_observation_id listing_id product_id config_version_id "
    "rn_versions result main_reason reasons rejection_reason marks price_quality confidence "
    "identification references advertised_discount real_discount purchase_cost "
    "chosen_channel alert_level alert_channel observations_used input_snapshot "
    "previous_evaluation_id changed_references no_longer_recommended load_run_id"
).split()
# design.md §4, TAB-11 (sin evaluation_id, que es el registro que contiene el canal).
COLUMNAS_TAB_11 = (
    "channel state closed_causes review_causes sale_price selling_cost net_margin "
    "net_margin_pct returns_cost drop_penalty adjusted_margin adjusted_margin_pct units "
    "days_to_recover monthly_yield_pct level calculated_level total_profit marks"
).split()
# design.md §4, "references" de TAB-10: habitual con su fuente y episodio, mercado hoy,
# MSRP, mínimo de 60 días, venta esperada en Amazon.
CONTENIDO_REFERENCIAS = (
    "precio habitual",
    "fuente del habitual",
    "episodio",
    "mercado hoy",
    "msrp",
    "mínimo de 60 días",
    "venta esperada en amazon",
)

# design.md §3: orden interno.
ORDEN_DESIGN_3 = (
    "validar",
    "identificar",
    "referencias",
    "descuento",
    "calidad",
    "costo de compra",
    "estado y números de cada canal",
    "nivel",
    "unidades, días y rendimiento",
    "elección y nivel del aviso",
    "motivos y precedencia",
)

# --- Fixtures sintéticos propios ----------------------------------------------------------

TIJUANA = dt.timezone(dt.timedelta(hours=-8))
CENTINELA = "ALIAS-CLIENTE-CENTINELA-9F3"


def _u(n: int) -> UUID:
    return UUID(int=0xA000 + n)


def _obs(**cambios):
    datos = {
        "schemaVersion": "3.1",
        "retailerCode": "tienda-prueba",
        "storeCode": "t-0042",
        "productUrl": "https://tienda.example.com/p/777",
        "title": "Sierra sintética",
        "brand": "MarcaT",
        "model": "ST-77",
        "gtin": "4006381333931",
        "category": "tools",
        "weightKg": Decimal("3.50"),
        "price": {"current": "31.25", "was": "149.00", "currency": "USD"},
        "seller": "comercio",
        "condition": "new",
        "availability": {"state": "limited_stock", "quantity": 2, "scope": "store"},
        "isClearance": True,
        "purchaseMode": "tienda",
        "taxLocation": "tienda_prueba",
        "extractedAt": "2026-11-17T23:30:00.250000-08:00",
        "blocked": False,
        "evidence": {"lectura": Decimal("31.250"), "pila": [Decimal("-0.5"), "ñ", None]},
    }
    datos.update(cambios)
    return leer_observacion(datos)


def _reg(n: int, **cambios) -> ObservacionRegistrada:
    return ObservacionRegistrada(_obs(**cambios), _u(n), _u(500), _u(600))


def _contexto(**cambios) -> ContextoEvaluacion:
    base = {
        "id_evaluacion": _u(1),
        # 2026-11-17 22:15 en Tijuana = 2026-11-18 06:15 UTC (cruza el día).
        "instante": dt.datetime(2026, 11, 17, 22, 15, 5, 123, tzinfo=TIJUANA),
        "configuracion": CONFIG,
        "id_version_configuracion": 42,
        "oferta": _reg(10),
        "historial": (
            _reg(11, price={"current": "119.00"}, extractedAt="2026-11-10T08:00:00Z"),
            _reg(12, price={"current": "118.995"}, extractedAt="2026-11-11T08:00:00+05:30"),
        ),
        "fichas_amazon": (
            _reg(
                20,
                retailerCode="amazon",
                storeCode=None,
                productUrl="https://amazon.example.com/dp/T77",
                price={"current": "119.00"},
                purchaseMode="envio",
                amazonListing={"buyBoxPrice": None, "sellersNew": 5, "rankMain": 6000},
                extractedAt="2026-11-17T12:00:00Z",
            ),
        ),
        "comparables": (
            leer_captura(
                "local_comparable",
                {
                    "brand": "MarcaT",
                    "model": "ST-77",
                    "condition": "used",
                    "askingPrice": "1999.90",
                    "currency": "MXN",
                    "exchangeRate": "17.3",
                    "city": "tijuana",
                    "date": "2026-11-09",
                    "sold": True,
                },
            ),
        ),
        "estimados": (
            leer_captura(
                "local_estimate", {"gtin": "4006381333931", "price": "95.5", "date": "2026-11-02"}
            ),
        ),
        "msrp": (
            leer_captura(
                "msrp",
                {
                    "gtin": "4006381333931",
                    "value": "199.99",
                    "source": "caja",
                    "date": "2026-09-30",
                },
            ),
        ),
        "demanda_local": (
            leer_captura(
                "local_demand", {"category": "tools", "level": "high", "date": "2026-11-03"}
            ),
        ),
        "id_evaluacion_anterior": _u(2),
        "referencias_cambiadas": (
            ReferenciaPrecio.PRECIO_HABITUAL,
            ReferenciaPrecio.PRECIO_VENTA_AMAZON,
        ),
        "id_carga": _u(3),
    }
    base.update(cambios)
    return ContextoEvaluacion(**base)


def _canal(canal: Canal, **cambios) -> EvaluacionCanal:
    base = {
        "canal": canal,
        "estado": EstadoCanal.DISPONIBLE,
        "precio_venta": Decimal("119"),
        "costo_venta": Decimal("33.85"),
        "margen_neto": Decimal("53.90"),
        "margen_neto_pct": Decimal("172.48"),
        "costo_devoluciones": Decimal("4.17"),
        "castigo": Decimal("5.00"),
        "margen_ajustado": Decimal("44.73"),
        "margen_ajustado_pct": Decimal("143.136"),
        "unidades": 3,
        "dias_para_recuperar": 37,
        "rendimiento_mensual_pct": Decimal("116.0562162162162162162162162"),
        "nivel": Nivel.MUY_RECOMENDABLE,
        "nivel_calculado": Nivel.MUY_RECOMENDABLE,
        "ganancia_total": Decimal("134.19"),
        "marcas": ("MARGEN ESTIMADO", "EMPAQUE POR CONFIRMAR"),
    }
    base.update(cambios)
    return EvaluacionCanal(**base)


def _registro(contexto: ContextoEvaluacion | None = None, **cambios) -> RegistroEvaluacion:
    contexto = contexto or _contexto()
    base = {
        "id": contexto.id_evaluacion,
        "evaluado_en": contexto.instante,
        "id_observacion_oferta": contexto.oferta.id,
        "id_publicacion": contexto.oferta.id_publicacion,
        "id_producto": contexto.oferta.id_producto,
        "id_version_configuracion": contexto.id_version_configuracion,
        "versiones_rn": contexto.versiones_rn,
        "resultado": Resultado.NIVEL_ASIGNADO,
        "motivo_principal": None,
        "motivos": (),
        "motivo_rechazo": None,
        "marcas": ("COMPETENCIA MÁS BARATA",),
        "calidad_precio": CalidadPrecio.BUENA_OFERTA,
        "confianza": Confianza.MEDIA,
        "identificacion": Identificacion.CONFIRMED,
        "referencias": Referencias(
            precio_habitual=Decimal("118.9975"),
            fuente_precio_habitual="historial_propio",
            episodio=Episodio(dt.date(2026, 11, 4), Decimal("120.50")),
            precio_mercado_hoy=Decimal("100.15"),
            msrp=Decimal("199.99"),
            minimo_60_dias_amazon=Decimal("109"),
            precio_venta_amazon=Decimal("119.00"),
        ),
        "descuento_anunciado": Decimal("79.02684563758389261744966443"),
        "descuento_real": Decimal("73.73894409546419042412655728"),
        "costo_compra": Decimal("31.25"),
        "canal_elegido": Canal.AMAZON,
        "nivel_aviso": Nivel.MUY_RECOMENDABLE,
        "canal_aviso": Canal.AMAZON,
        "canales": (
            _canal(Canal.AMAZON),
            _canal(
                Canal.LOCAL,
                estado=EstadoCanal.POR_REVISAR,
                causas_por_revisar=(CausaCanalPorRevisar.SIN_REFERENCIA_DE_USADOS,),
                unidades=None,
                dias_para_recuperar=None,
                rendimiento_mensual_pct=None,
                nivel=None,
                nivel_calculado=None,
                ganancia_total=None,
                marcas=(),
            ),
        ),
        "observaciones_usadas": (
            ObservacionUsada(_u(11), dt.datetime(2026, 11, 10, 8, tzinfo=dt.UTC)),
            ObservacionUsada(_u(12), dt.datetime(2026, 11, 11, 8, tzinfo=TIJUANA)),
        ),
        "entrada": contexto,
        "id_evaluacion_anterior": contexto.id_evaluacion_anterior,
        "referencias_cambiadas": contexto.referencias_cambiadas,
        "ya_no_recomendado": True,
        "id_carga": contexto.id_carga,
    }
    base.update(cambios)
    return RegistroEvaluacion(**base)


def _sin_floats(texto: str):
    def falla(t):
        raise AssertionError(f"número JSON con punto: {t}")

    return json.loads(texto, parse_float=falla, parse_constant=falla)


def _recorrer(nodo, ruta=""):
    yield ruta, nodo
    if isinstance(nodo, dict):
        for k, v in nodo.items():
            yield from _recorrer(v, f"{ruta}.{k}")
    elif isinstance(nodo, list):
        for i, v in enumerate(nodo):
            yield from _recorrer(v, f"{ruta}[{i}]")


# --- 1. Ida y vuelta (RNF-3, design.md §12) ------------------------------------------------


@pytest.mark.parametrize("tipo", ["contexto", "registro"])
def test_ida_y_vuelta_da_objeto_igual_y_texto_igual_byte_a_byte(tipo):
    original = _contexto() if tipo == "contexto" else _registro()
    clase = type(original)
    texto = original.a_json()
    leido = clase.desde_json(texto)
    assert leido == original
    assert leido.a_json() == texto
    assert leido.a_json().encode("utf-8") == texto.encode("utf-8")
    # Desde bytes también (lo que guarda jsonb).
    assert clase.desde_json(texto.encode("utf-8")).a_json() == texto
    # Dos vueltas no cambian nada.
    assert clase.desde_json(leido.a_json()) == original


def test_ida_y_vuelta_conserva_valores_sin_redondear_y_ceros():
    contexto = _contexto()
    leido = ContextoEvaluacion.desde_json(contexto.a_json())
    historial = leido.historial[1].observacion
    # 118.995 no se redondea a 119.00 ni a 119.0 (precio del historial, no es de la lista).
    assert str(historial.price.current) == "118.995"
    assert str(leido.oferta.observacion.weight_kg) == "3.50"
    assert str(leido.oferta.observacion.evidence["lectura"]) == "31.250"
    assert isinstance(leido.oferta.observacion.evidence["lectura"], Decimal)
    assert leido.oferta.observacion.evidence["pila"] == [Decimal("-0.5"), "ñ", None]
    assert str(leido.estimados[0].price) == "95.5"
    assert str(leido.comparables[0].exchange_rate) == "17.3"


def test_el_contexto_trae_instante_version_de_configuracion_y_versiones_rn():
    contexto = _contexto()
    datos = _sin_floats(contexto.a_json())
    # design.md §3 y CTR-06: instante, config_version_id y la configuración completa.
    assert datos["instante"] == "2026-11-18T06:15:05.000123Z"
    assert datos["id_version_configuracion"] == 42
    assert "configuracion" in datos and datos["configuracion"]
    # Versiones de RN de la configuración (PAR-01), las del REQ §4 que trae base.yaml.
    assert dict(contexto.versiones_rn)["RN-001"] == 2
    assert dict(contexto.versiones_rn)["RN-016"] == 1
    leido = ContextoEvaluacion.desde_json(contexto.a_json())
    assert dict(leido.versiones_rn) == dict(contexto.versiones_rn)
    assert leido.configuracion.sha256 == CONFIG.sha256
    assert leido.configuracion.version == CONFIG.version
    # Registro: las versiones RN y la de configuración viajan con él.
    reg = _sin_floats(_registro().a_json())
    assert reg["versiones_rn"] == {k: v for k, v in contexto.versiones_rn.items()}
    assert reg["id_version_configuracion"] == 42
    assert reg["entrada"]["id_version_configuracion"] == 42


def test_contextos_distintos_dan_textos_distintos():
    a = _contexto().a_json()
    b = _contexto(id_version_configuracion=43).a_json()
    c = _contexto(instante=dt.datetime(2026, 11, 18, 6, 15, 5, 124, tzinfo=dt.UTC)).a_json()
    assert len({a, b, c}) == 3


def test_el_mismo_instante_en_otra_zona_da_el_mismo_texto():
    a = _contexto().a_json()
    b = _contexto(instante=dt.datetime(2026, 11, 18, 6, 15, 5, 123, tzinfo=dt.UTC)).a_json()
    assert a == b


# --- 2. CTR-06 sobre el texto -------------------------------------------------------------


def test_ctr06_claves_ordenadas_en_todos_los_niveles_y_separadores_fijos():
    texto = _registro().a_json()
    vistos = 0

    def ganchos(pares):
        nonlocal vistos
        claves = [k for k, _ in pares]
        assert claves == sorted(claves)
        vistos += 1
        return dict(pares)

    json.loads(texto, object_pairs_hook=ganchos)
    assert vistos > 20
    # Separadores fijos y UTF-8 sin escapar: el texto es su propia forma canónica.
    datos = json.loads(texto)
    canonico = json.dumps(datos, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert texto == canonico
    assert "\\u00" not in texto and "MÁS" in texto
    assert "\n" not in texto


def test_ctr06_montos_y_porcentajes_como_texto_decimal_sin_redondear():
    datos = _sin_floats(_registro().a_json())
    amazon = datos["canales"][0]
    assert amazon["margen_ajustado"] == "44.73"
    assert amazon["castigo"] == "5.00"
    assert amazon["precio_venta"] == "119"
    assert amazon["margen_ajustado_pct"] == "143.136"
    assert amazon["rendimiento_mensual_pct"] == "116.0562162162162162162162162"
    assert datos["descuento_real"] == "73.73894409546419042412655728"
    assert datos["costo_compra"] == "31.25"
    assert datos["referencias"]["precio_habitual"] == "118.9975"
    assert datos["referencias"]["episodio"]["valor_congelado"] == "120.50"
    # Ningún monto sale con exponente.
    for ruta, nodo in _recorrer(datos):
        if isinstance(nodo, str) and re.fullmatch(r"-?\d+(\.\d+)?[eE][+-]?\d+", nodo):
            raise AssertionError(f"{ruta}: decimal con exponente")


def test_ctr06_decimal_con_exponente_sale_en_notacion_fija_y_sin_perder_valor():
    canal = _canal(Canal.AMAZON, margen_neto=Decimal("5.39E+1"), castigo=Decimal("0E-2"))
    datos = _sin_floats(canal.a_json())
    assert datos["margen_neto"] == "53.9"
    assert datos["castigo"] == "0.00"
    assert EvaluacionCanal.desde_json(canal.a_json()) == canal


_INGENUA = dt.datetime(2026, 11, 18, 6, 15, tzinfo=dt.UTC).replace(tzinfo=None)  # sin zona
_ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{6})?Z$")


def test_ctr06_fechas_iso_8601_en_utc():
    datos = _sin_floats(_registro().a_json())
    assert datos["evaluado_en"] == "2026-11-18T06:15:05.000123Z"
    assert datos["observaciones_usadas"][1]["fecha"] == "2026-11-11T16:00:00Z"
    oferta = datos["entrada"]["oferta"]["observacion"]
    assert oferta["extractedAt"] == "2026-11-18T07:30:00.250000Z"
    historial = datos["entrada"]["historial"][1]["observacion"]
    assert historial["extractedAt"] == "2026-11-11T02:30:00Z"
    # Toda fecha y hora del texto está en UTC con Z; las fechas solas, AAAA-MM-DD.
    for ruta, nodo in _recorrer(datos):
        if isinstance(nodo, str) and re.match(r"^\d{4}-\d{2}-\d{2}T", nodo):
            assert _ISO_UTC.match(nodo), ruta
    assert datos["referencias"]["episodio"]["inicio"] == "2026-11-04"


def test_ctr06_enums_por_su_codigo():
    datos = _sin_floats(_registro().a_json())
    assert datos["resultado"] == "NIVEL_ASIGNADO"
    assert datos["canal_elegido"] == "amazon"
    assert datos["canal_aviso"] == "amazon"
    assert datos["nivel_aviso"] == "MUY_RECOMENDABLE"
    assert datos["calidad_precio"] == "BUENA_OFERTA"
    assert datos["confianza"] == "MEDIA"
    assert datos["identificacion"] == "confirmed"
    assert datos["referencias_cambiadas"] == ["precio_habitual", "precio_venta_amazon"]
    assert [c["canal"] for c in datos["canales"]] == ["amazon", "local"]
    assert datos["canales"][1]["estado"] == "POR_REVISAR"
    assert datos["canales"][1]["causas_por_revisar"] == ["SIN REFERENCIA DE USADOS"]
    oferta = datos["entrada"]["oferta"]["observacion"]
    assert oferta["category"] == "tools"
    assert oferta["availability"]["state"] == "limited_stock"
    motivos = _sin_floats(
        _registro(
            resultado=Resultado.DESCARTADA,
            motivo_principal=Motivo.MERCADO_YA_BARATO,
            motivos=(Motivo.MERCADO_YA_BARATO, Motivo.VENDEDOR_EXTERNO),
            canal_elegido=None,
            nivel_aviso=None,
            canal_aviso=None,
        ).a_json()
    )
    assert motivos["motivos"] == ["MERCADO YA BARATO", "VENDEDOR EXTERNO"]
    assert motivos["motivo_principal"] == "MERCADO YA BARATO"


def test_ctr06_input_snapshot_es_el_contexto_completo():
    contexto = _contexto()
    datos = _sin_floats(_registro(contexto).a_json())
    assert datos["entrada"] == _sin_floats(contexto.a_json())


# --- 3. Campos de REQ §7, TAB-10 y TAB-11 ---------------------------------------------------

# Correspondencia de columnas, escrita a mano (design.md §14: nombres en español).
_TAB_10_A_CAMPO = {
    "id": "id",
    "evaluated_at": "evaluado_en",
    "offer_observation_id": "id_observacion_oferta",
    "listing_id": "id_publicacion",
    "product_id": "id_producto",
    "config_version_id": "id_version_configuracion",
    "rn_versions": "versiones_rn",
    "result": "resultado",
    "main_reason": "motivo_principal",
    "reasons": "motivos",
    "rejection_reason": "motivo_rechazo",
    "marks": "marcas",
    "price_quality": "calidad_precio",
    "confidence": "confianza",
    "identification": "identificacion",
    "references": "referencias",
    "advertised_discount": "descuento_anunciado",
    "real_discount": "descuento_real",
    "purchase_cost": "costo_compra",
    "chosen_channel": "canal_elegido",
    "alert_level": "nivel_aviso",
    "alert_channel": "canal_aviso",
    "observations_used": "observaciones_usadas",
    "input_snapshot": "entrada",
    "previous_evaluation_id": "id_evaluacion_anterior",
    "changed_references": "referencias_cambiadas",
    "no_longer_recommended": "ya_no_recomendado",
    "load_run_id": "id_carga",
}
_TAB_11_A_CAMPO = {
    "channel": "canal",
    "state": "estado",
    "closed_causes": "causas_cerrado",
    "review_causes": "causas_por_revisar",
    "sale_price": "precio_venta",
    "selling_cost": "costo_venta",
    "net_margin": "margen_neto",
    "net_margin_pct": "margen_neto_pct",
    "returns_cost": "costo_devoluciones",
    "drop_penalty": "castigo",
    "adjusted_margin": "margen_ajustado",
    "adjusted_margin_pct": "margen_ajustado_pct",
    "units": "unidades",
    "days_to_recover": "dias_para_recuperar",
    "monthly_yield_pct": "rendimiento_mensual_pct",
    "level": "nivel",
    "calculated_level": "nivel_calculado",
    "total_profit": "ganancia_total",
    "marks": "marcas",
}


def test_registro_tiene_todas_las_columnas_de_tab_10():
    assert sorted(_TAB_10_A_CAMPO) == sorted(COLUMNAS_TAB_10)
    campos = {f.name for f in dataclasses.fields(RegistroEvaluacion)}
    faltan = [c for c, campo in _TAB_10_A_CAMPO.items() if campo not in campos]
    assert faltan == []
    # Además los valores por canal (TAB-11) van dentro del registro.
    assert "canales" in campos
    # Todo campo sale en el JSON (un None como null).
    datos = _sin_floats(_registro().a_json())
    assert set(datos) == campos


def test_canal_tiene_todas_las_columnas_de_tab_11():
    assert sorted(_TAB_11_A_CAMPO) == sorted(COLUMNAS_TAB_11)
    campos = {f.name for f in dataclasses.fields(EvaluacionCanal)}
    assert [c for c, campo in _TAB_11_A_CAMPO.items() if campo not in campos] == []
    datos = _sin_floats(EvaluacionCanal(canal=Canal.LOCAL, estado=EstadoCanal.CERRADO).a_json())
    assert set(datos) == campos
    assert all(datos[c] is None for c in ("margen_neto", "unidades", "nivel", "nivel_calculado"))


def test_referencias_tienen_el_contenido_de_tab_10():
    campos = {f.name for f in dataclasses.fields(Referencias)}
    esperados = {
        "precio habitual": "precio_habitual",
        "fuente del habitual": "fuente_precio_habitual",
        "episodio": "episodio",
        "mercado hoy": "precio_mercado_hoy",
        "msrp": "msrp",
        "mínimo de 60 días": "minimo_60_dias_amazon",
        "venta esperada en amazon": "precio_venta_amazon",
    }
    assert set(esperados) == set(CONTENIDO_REFERENCIAS)
    assert {esperados[c] for c in CONTENIDO_REFERENCIAS} <= campos
    # Episodio: inicio y valor congelado (design.md §10.2).
    assert {f.name for f in dataclasses.fields(Episodio)} == {"inicio", "valor_congelado"}
    # Observaciones usadas: id y fecha (REQ §7; TAB-10).
    assert {f.name for f in dataclasses.fields(ObservacionUsada)} == {"id", "fecha"}


def test_req_7_elementos_del_registro():
    """REQ §7 B: cada elemento del registro de evaluación está en el registro."""
    r = _registro()
    elementos = {
        "identificador": r.id,
        "fecha": r.evaluado_en,
        "observaciones usadas con su fecha": r.observaciones_usadas[0].fecha,
        "valores calculados por canal": r.canales[0].margen_ajustado,
        "estado de cada canal": [c.estado for c in r.canales],
        "calidad del precio": r.calidad_precio,
        "marcas": r.marcas,
        "todos los motivos": r.motivos,
        "motivo principal": "motivo_principal" in RegistroEvaluacion.__dataclass_fields__,
        "nivel_calculado por canal": [c.nivel_calculado for c in r.canales],
        "canal elegido": r.canal_elegido,
        "nivel del aviso": r.nivel_aviso,
        "resultado": r.resultado,
        "versión de cada RN": dict(r.versiones_rn),
        "versión de la configuración": r.id_version_configuracion,
        "evaluación anterior": r.id_evaluacion_anterior,
        "referencia que cambió": r.referencias_cambiadas,
    }
    assert all(v is not None for v in elementos.values())


# --- 4. Precedencia (REQ §3.2.3 y §3.2.4) ---------------------------------------------------


def test_catalogo_de_motivos_igual_a_la_tabla_de_3_2_3():
    assert [m.value for m in Motivo] == ORDEN_3_2_3
    assert {m.value: m.lleva_a.value for m in Motivo} == LLEVA_A


@pytest.mark.parametrize("hay_nivel", [False, True])
def test_precedencia_contra_el_oraculo_en_todas_las_combinaciones(hay_nivel):
    por_codigo = {m.value: m for m in Motivo}
    for n in range(len(ORDEN_3_2_3) + 1):
        for combo in itertools.combinations(ORDEN_3_2_3, n):
            resultado, principal, todos = _oraculo_3_2_4(set(combo), hay_nivel)
            # Entran desordenados y con repetidos: el orden y la unicidad son de decidir.
            entrada = [por_codigo[c] for c in reversed(combo)] * 2
            d = decidir(entrada, hay_nivel)
            assert d.resultado.value == resultado, combo
            assert (d.motivo_principal.value if d.motivo_principal else None) == principal
            assert [m.value for m in d.motivos] == todos


@pytest.mark.parametrize(
    ("codigos", "esperado", "principal"),
    [
        # Cualquier motivo de descarte gana, aunque haya SOLO REFERENCIA y revisión.
        (
            {"DEMANDA DESCONOCIDA", "MARGEN NEGATIVO", "SOLO REFERENCIA"},
            "DESCARTADA",
            "MARGEN NEGATIVO",
        ),
        ({"PARTICULAR", "SIN CANAL DISPONIBLE"}, "DESCARTADA", "SIN CANAL DISPONIBLE"),
        ({"SOLO REFERENCIA", "VENDEDOR EXTERNO"}, "SOLO_REFERENCIA", "SOLO REFERENCIA"),
        (
            {"DEMANDA DESCONOCIDA", "SIN HISTORIAL SUFICIENTE"},
            "REVISION_MANUAL",
            "SIN HISTORIAL SUFICIENTE",
        ),
        (set(), "NIVEL_ASIGNADO", None),
    ],
)
def test_precedencia_casos_de_lectura(codigos, esperado, principal):
    por_codigo = {m.value: m for m in Motivo}
    d = decidir([por_codigo[c] for c in codigos], hay_nivel=True)
    assert d.resultado.value == esperado
    assert (d.motivo_principal.value if d.motivo_principal else None) == principal
    # Todos se guardan.
    assert {m.value for m in d.motivos} == codigos


def test_reunir_motivos_une_todos_los_pasos_en_orden():
    r = reunir_motivos(
        [Motivo.DEMANDA_DESCONOCIDA],
        (Motivo.EVITAR, Motivo.PARTICULAR),
        iter([Motivo.DEMANDA_DESCONOCIDA, Motivo.SOLO_REFERENCIA]),
        [],
    )
    assert [m.value for m in r] == [
        "EVITAR",
        "SOLO REFERENCIA",
        "PARTICULAR",
        "DEMANDA DESCONOCIDA",
    ]


def test_reunir_y_decidir_son_estrictos():
    with pytest.raises(TypeError):
        reunir_motivos(["EVITAR"])
    with pytest.raises(TypeError):
        decidir([], 1)  # un entero no es un booleano (DEC-238)


# --- 5. Esqueleto del motor --------------------------------------------------------------


def test_pasos_siguen_el_orden_interno_de_design_3():
    assert len(motor.PASOS) == len(ORDEN_DESIGN_3)
    # Lo que dice el docstring de cada paso debe corresponder a su lugar en el orden.
    claves = (
        "validar",
        "identific",
        "referencia",
        "descuento",
        "calidad",
        "costo",
        "canal",
        "nivel",
        "unidades",
        "elegi",
        "motivos",
    )
    for paso, clave in zip(motor.PASOS, claves, strict=True):
        assert clave in (paso.__name__ + (paso.__doc__ or "")).lower(), paso.__name__


def _con_paso(monkeypatch, indice, funcion):
    pasos = list(motor.PASOS)
    original = pasos[indice]

    def paso(contexto, avance):
        return funcion(contexto, original(contexto, avance))

    pasos[indice] = paso
    monkeypatch.setattr(motor, "PASOS", tuple(pasos))


def test_con_pasos_vacios_el_motor_es_puro_y_reproducible(monkeypatch):
    contexto = _contexto()

    def prohibido(*a, **k):
        raise AssertionError("el motor no usa red ni archivos")

    monkeypatch.setattr(socket, "socket", prohibido)
    monkeypatch.setattr(builtins, "open", prohibido)
    r1 = motor.evaluar(contexto)
    r2 = motor.evaluar(ContextoEvaluacion.desde_json(contexto.a_json()))
    assert r1 == r2
    assert r1.a_json() == r2.a_json()
    assert r1.evaluado_en == contexto.instante
    assert r1.id == contexto.id_evaluacion
    assert r1.entrada == contexto
    assert r1.id_version_configuracion == 42
    assert dict(r1.versiones_rn) == dict(CONFIG.contenido.general.rn_versions)
    assert r1.id_evaluacion_anterior == _u(2)
    assert r1.referencias_cambiadas == contexto.referencias_cambiadas
    assert r1.id_carga == _u(3)
    assert r1.id_observacion_oferta == _u(10)


def test_un_rechazo_termina_la_evaluacion(monkeypatch):
    llamados = []

    def rechazar(contexto, avance):
        return dataclasses.replace(avance, motivo_rechazo="PRECIO INVÁLIDO")

    _con_paso(monkeypatch, 0, rechazar)
    pasos = list(motor.PASOS)
    for i in range(1, len(pasos)):
        original = pasos[i]

        def espia(contexto, avance, _o=original, _i=i):
            llamados.append(_i)
            return _o(contexto, avance)

        pasos[i] = espia
    monkeypatch.setattr(motor, "PASOS", tuple(pasos))
    r = motor.evaluar(_contexto())
    assert llamados == []
    assert r.resultado is Resultado.RECHAZADA_VALIDACION
    assert r.motivo_rechazo == "PRECIO INVÁLIDO"
    assert r.motivos == () and r.motivo_principal is None
    assert r.id_observacion_oferta is None  # TAB-10: null en un rechazo
    assert r.canales == ()


def test_motor_descartada_con_nivel_no_lleva_aviso(monkeypatch):
    canales = (_canal(Canal.AMAZON), _canal(Canal.LOCAL, nivel=Nivel.VIGILAR))

    def llenar(contexto, avance):
        return dataclasses.replace(
            avance,
            canales=canales,
            canal_elegido=Canal.AMAZON,
            nivel_aviso=Nivel.MUY_RECOMENDABLE,
            canal_aviso=Canal.AMAZON,
            motivos=(Motivo.DEMANDA_DESCONOCIDA, Motivo.MERCADO_YA_BARATO),
        )

    _con_paso(monkeypatch, 9, llenar)
    r = motor.evaluar(_contexto())
    assert r.resultado is Resultado.DESCARTADA
    assert r.motivo_principal is Motivo.MERCADO_YA_BARATO
    assert r.motivos == (Motivo.MERCADO_YA_BARATO, Motivo.DEMANDA_DESCONOCIDA)
    assert r.nivel_aviso is None and r.canal_aviso is None
    # nivel_calculado se guarda siempre que se pueda calcular (REQ §3.2).
    assert [c.nivel_calculado for c in r.canales] == [Nivel.MUY_RECOMENDABLE] * 2


def test_motor_nivel_asignado_con_canal_disponible_con_nivel(monkeypatch):
    def llenar(contexto, avance):
        return dataclasses.replace(
            avance,
            canales=(_canal(Canal.AMAZON),),
            canal_elegido=Canal.AMAZON,
            nivel_aviso=Nivel.MUY_RECOMENDABLE,
            canal_aviso=Canal.AMAZON,
        )

    _con_paso(monkeypatch, 9, llenar)
    r = motor.evaluar(_contexto())
    assert r.resultado is Resultado.NIVEL_ASIGNADO
    assert (r.canal_elegido, r.nivel_aviso, r.canal_aviso) == (
        Canal.AMAZON,
        Nivel.MUY_RECOMENDABLE,
        Canal.AMAZON,
    )
    assert RegistroEvaluacion.desde_json(r.a_json()) == r


def test_motor_canal_por_revisar_solo_con_nivel_calculado_no_da_nivel(monkeypatch):
    por_revisar = _canal(
        Canal.AMAZON, estado=EstadoCanal.POR_REVISAR, nivel=None, nivel_calculado=Nivel.COMPRAR_YA
    )

    def llenar(contexto, avance):
        return dataclasses.replace(avance, canales=(por_revisar,))

    _con_paso(monkeypatch, 9, llenar)
    r = motor.evaluar(_contexto())
    assert r.resultado is Resultado.SIN_NIVEL
    assert r.canales[0].nivel_calculado is Nivel.COMPRAR_YA


# --- 6. Invariantes del registro ---------------------------------------------------------


@pytest.mark.parametrize(
    "cambios",
    [
        # Resultado distinto del "lleva a" del principal.
        {
            "resultado": Resultado.REVISION_MANUAL,
            "motivo_principal": Motivo.EVITAR,
            "motivos": (Motivo.EVITAR,),
        },
        # Principal que no es el primero de §3.2.3.
        {
            "resultado": Resultado.REVISION_MANUAL,
            "motivo_principal": Motivo.PARTICULAR,
            "motivos": (Motivo.PARTICULAR, Motivo.SIN_HISTORIAL_SUFICIENTE),
        },
        # Motivos repetidos.
        {
            "resultado": Resultado.REVISION_MANUAL,
            "motivo_principal": Motivo.PARTICULAR,
            "motivos": (Motivo.PARTICULAR, Motivo.PARTICULAR),
        },
        # Motivos sin principal.
        {
            "resultado": Resultado.REVISION_MANUAL,
            "motivo_principal": None,
            "motivos": (Motivo.PARTICULAR,),
        },
        # Descartada sin motivos.
        {"resultado": Resultado.DESCARTADA},
        # Rechazo sin motivo de rechazo; motivo de rechazo fuera del rechazo.
        {"resultado": Resultado.RECHAZADA_VALIDACION},
        {"motivo_rechazo": "PRECIO INVÁLIDO"},
        # NIVEL_ASIGNADO sin canal elegido.
        {"canal_elegido": None},
        # Canales repetidos o en otro orden.
        {"canales": (_canal(Canal.LOCAL), _canal(Canal.AMAZON))},
        {"canales": (_canal(Canal.AMAZON), _canal(Canal.AMAZON))},
    ],
)
def test_registro_rechaza_invariantes_rotas(cambios):
    base = {}
    if cambios.get("resultado") not in (None, Resultado.NIVEL_ASIGNADO):
        base = {"canal_elegido": None, "nivel_aviso": None, "canal_aviso": None}
    base.update(cambios)
    with pytest.raises(ValueError):
        _registro(**base)


def test_registro_inmutable():
    r = _registro()
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.resultado = Resultado.SIN_NIVEL  # type: ignore[misc]
    with pytest.raises(TypeError):
        r.versiones_rn["RN-001"] = 99  # type: ignore[index]


# --- 7. Tipos estrictos (DEC-238) y sin float (design.md §8) --------------------------------


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("unidades", True),
        ("unidades", 3.0),
        ("unidades", "3"),
        ("dias_para_recuperar", False),
        ("margen_neto", 53.9),
        ("margen_neto", "53.90"),
        ("margen_neto", 54),
        ("margen_neto", Decimal("NaN")),
        ("margen_neto", Decimal("Infinity")),
        ("nivel", "MUY_RECOMENDABLE"),
        ("estado", "DISPONIBLE"),
        ("marcas", ["MARGEN ESTIMADO"]),
        ("causas_cerrado", ("SIN ROTACIÓN",)),
    ],
)
def test_construccion_sin_conversiones_implicitas(campo, valor):
    with pytest.raises(TypeError):
        _canal(Canal.AMAZON, **{campo: valor})


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("instante", _INGENUA),
        ("instante", "2026-11-18T06:15:00Z"),
        ("id_version_configuracion", True),
        ("id_version_configuracion", "42"),
        ("id_evaluacion", "00000000-0000-0000-0000-00000000a001"),
        ("historial", []),
        ("referencias_cambiadas", ("precio_habitual",)),
    ],
)
def test_contexto_sin_conversiones_implicitas(campo, valor):
    with pytest.raises(TypeError):
        _contexto(**{campo: valor})


def test_episodio_rechaza_una_fecha_y_hora_como_fecha():
    with pytest.raises(TypeError):
        Episodio(dt.datetime(2026, 11, 4, tzinfo=dt.UTC), Decimal("120.50"))


def _canal_json(**cambios) -> str:
    datos = json.loads(_canal(Canal.AMAZON).a_json())
    datos.update(cambios)
    return json.dumps(datos, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@pytest.mark.parametrize(
    "cambios",
    [
        {"unidades": True},
        {"unidades": "3"},
        {"margen_neto": 53.9},
        {"margen_neto": 54},
        {"margen_neto": "53.9e0"},
        {"margen_neto": " 53.90"},
        {"margen_neto": ""},
        {"nivel": "muy_recomendable"},
        {"canal": "Amazon"},
        {"marcas": "MARGEN ESTIMADO"},
    ],
)
def test_lectura_estricta(cambios):
    with pytest.raises(ErrorSerializacion):
        EvaluacionCanal.desde_json(_canal_json(**cambios))


def test_lectura_rechaza_claves_que_faltan_sobran_o_se_repiten():
    datos = json.loads(_canal(Canal.AMAZON).a_json())
    sin = dict(datos)
    del sin["unidades"]
    with pytest.raises(ErrorSerializacion):
        EvaluacionCanal.desde_json(json.dumps(sin))
    with pytest.raises(ErrorSerializacion):
        EvaluacionCanal.desde_json(json.dumps({**datos, "extra": None}))
    texto = _canal(Canal.AMAZON).a_json()
    with pytest.raises(ErrorSerializacion):
        EvaluacionCanal.desde_json(texto[:-1] + ',"unidades":3}')


def test_lectura_rechaza_fechas_fuera_de_utc():
    texto = _contexto().a_json()
    otro = texto.replace(
        '"instante":"2026-11-18T06:15:05.000123Z"', '"instante":"2026-11-17T22:15:05.000123-08:00"'
    )
    assert otro != texto
    with pytest.raises(ErrorSerializacion):
        ContextoEvaluacion.desde_json(otro)


def test_float_no_se_serializa_en_ningun_lugar():
    with pytest.raises(TypeError):
        _reg(99, evidence={"x": 1.5}).a_json()
    with pytest.raises(TypeError):
        Referencias(precio_habitual=119.0)  # type: ignore[arg-type]


def test_el_codigo_de_evaluacion_no_tiene_literales_ni_llamadas_float():
    for archivo in sorted(SRC_EVALUACION.glob("*.py")):
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Constant):
                assert not isinstance(nodo.value, float), f"{archivo.name}:{nodo.lineno}"
            if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name):
                assert nodo.func.id != "float", f"{archivo.name}:{nodo.lineno}"


# --- 8. Pureza de evaluacion/ (design.md §14) -----------------------------------------------

_MODULOS_PROHIBIDOS = {
    "oip.persistencia",
    "time",
    "random",
    "secrets",
    "os",
    "io",
    "socket",
    "http",
    "urllib",
    "requests",
    "httpx",
    "aiohttp",
    "subprocess",
    "pathlib",
    "sqlalchemy",
    "psycopg",
    "logging",
}
_LLAMADAS_PROHIBIDAS = {"now", "utcnow", "today", "uuid1", "uuid4", "open", "getenv", "time"}


def test_evaluacion_no_importa_persistencia_reloj_io_ni_aleatoriedad():
    for archivo in sorted(SRC_EVALUACION.glob("*.py")):
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            nombres: list[str] = []
            if isinstance(nodo, ast.Import):
                nombres = [a.name for a in nodo.names]
            elif isinstance(nodo, ast.ImportFrom):
                base = nodo.module or ""
                nombres = [base] + [f"{base}.{a.name}" for a in nodo.names]
                assert nodo.level == 0 or "persistencia" not in base, archivo.name
            for nombre in nombres:
                for prohibido in _MODULOS_PROHIBIDOS:
                    assert not (nombre == prohibido or nombre.startswith(prohibido + ".")), (
                        f"{archivo.name}: importa {nombre}"
                    )
            if isinstance(nodo, ast.Call):
                func = nodo.func
                nombre = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                assert nombre not in _LLAMADAS_PROHIBIDAS, f"{archivo.name}:{nodo.lineno} {nombre}"


# --- 9. Datos personales: nada de valores en los mensajes (DEC-181, R-20) -------------------


def test_contexto_no_trae_solicitudes_de_clientes():
    from oip.entradas.capturas import SolicitudCliente

    texto = " ".join(str(f.type) for f in dataclasses.fields(ContextoEvaluacion))
    assert SolicitudCliente.__name__ not in texto
    assert "cliente" not in texto.lower() and "alias" not in texto.lower()


def test_los_errores_no_citan_el_valor():
    with pytest.raises(TypeError) as e1:
        _contexto(id_version_configuracion=CENTINELA)
    assert CENTINELA not in str(e1.value)
    with pytest.raises(TypeError) as e2:
        _canal(Canal.AMAZON, marcas=[CENTINELA])
    assert CENTINELA not in str(e2.value)
    with pytest.raises(ErrorSerializacion) as e3:
        EvaluacionCanal.desde_json(_canal_json(unidades=CENTINELA))
    assert CENTINELA not in str(e3.value)
    # Un modelo de pydantic inválido dentro del JSON: el detalle no cita el valor.
    texto = _contexto().a_json()
    otro = texto.replace('"title":"Sierra sintética"', f'"title":{{"x":"{CENTINELA}"}}', 1)
    assert otro != texto
    with pytest.raises(ErrorSerializacion) as e4:
        ContextoEvaluacion.desde_json(otro)
    assert CENTINELA not in str(e4.value)
    assert e4.value.__cause__ is None or CENTINELA not in str(e4.value.__cause__)


def test_repr_del_registro_no_incluye_la_entrada():
    r = _registro()
    assert "entrada=" not in repr(r)
