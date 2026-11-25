"""Pruebas independientes de oip-tester para T08b (cargador de archivos; CMP-08, CMP-22).

Escritas desde REQ-2026-0001 v2.9 (§3.2.6 punto 1, §6, B34 b y c), design.md (§2, §6,
CTR-02, CTR-03, CTR-05, CTR-07, §12) y las DEC-238, DEC-240, DEC-247, DEC-250, DEC-255,
DEC-256, DEC-257, DEC-271 y DEC-274 (puntos 8 y 9 del comentario 7069378959 del #34). No
copian datos ni resultados del código: los valores esperados salen de esas fuentes.

Fixtures sintéticos armados aquí. La URL de comercio es de example.com (``tienda-prueba``);
los dominios de las plataformas de particulares se leen de la configuración (PAR-09), no se
escriben en la prueba. Ninguna prueba abre una URL; el instante siempre es explícito; los
identificadores son deterministas.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from config_tienda_prueba import (
    BASE,
    DOMINIO_PRUEBA,
    TIENDA_PRUEBA,
    con_sucursales_prueba,
    configuracion_con_sucursales_prueba,
)
from oip import cli
from oip.catalogos import TipoRegistro
from oip.configuracion import cargar_configuracion_texto
from oip.entradas.cargador import cargar, clave_idempotencia
from oip.entradas.contrato import leer_observacion
from oip.entradas.validacion import ruta_normalizada, url_canonica
from oip.persistencia.repositorios import (
    IdentificadorProducto,
    RegistroRechazo,
    RepositorioMemoria,
)

CONFIG = configuracion_con_sucursales_prueba()
PLATAFORMAS = CONFIG.contenido.private_sellers.platforms
#: Plataforma con prefijo de ruta en PAR-09 (``/marketplace``) y una sin prefijo.
CON_PREFIJO = next(p for p in PLATAFORMAS.values() if p.path_prefix)
SIN_PREFIJO = next(p for p in PLATAFORMAS.values() if not p.path_prefix)

#: 2026-11-18 10:00 en Tijuana (PAR-01, UTC−8 en noviembre).
INSTANTE = dt.datetime(2026, 11, 18, 18, 0, tzinfo=dt.UTC)
CONFIG_EN = dt.datetime(2026, 11, 1, tzinfo=dt.UTC)

TIPO_DESCONOCIDO = "TIPO DE REGISTRO DESCONOCIDO"
PRECIO_INVALIDO = "PRECIO INVÁLIDO"
DOMINIO_NO_AUTORIZADO = "DOMINIO NO AUTORIZADO"
CIUDAD_NO_CONFIGURADA = "CIUDAD NO CONFIGURADA"


def faltante(campo: str) -> str:
    return f"CAMPO OBLIGATORIO FALTANTE ({campo})"


class Ids:
    def __init__(self) -> None:
        self.n = 0
        self.dados: list[UUID] = []

    def __call__(self) -> UUID:
        self.n += 1
        nuevo = UUID(int=self.n)
        self.dados.append(nuevo)
        return nuevo


def nuevo_repo(config=CONFIG):
    repo = RepositorioMemoria()
    version, _ = repo.guardar_version_configuracion(config, cargada_en=CONFIG_EN)
    return repo, version


def jsonl(*renglones: dict[str, Any] | str | bytes) -> bytes:
    partes = []
    for r in renglones:
        if isinstance(r, bytes):
            partes.append(r)
        elif isinstance(r, str):
            partes.append(r.encode("utf-8"))
        else:
            partes.append(json.dumps(r, ensure_ascii=False).encode("utf-8"))
    return b"\n".join(partes) + b"\n"


def csv_bytes(*lineas: str) -> bytes:
    return ("\n".join(lineas) + "\n").encode("utf-8")


def correr(nombre, contenido, repo=None, version=None, instante=INSTANTE, ids=None):
    if repo is None:
        repo, version = nuevo_repo()
    ids = ids or Ids()
    reporte = cargar(nombre, contenido, repo, version, instante, nuevo_id=ids)
    return reporte, repo, ids


def motivos(reporte) -> list[tuple[int, str]]:
    return [(r.renglon, r.motivo) for r in reporte.rechazos]


def comercio(url_path: str = "/p/t08b-1", **cambios: Any) -> dict[str, Any]:
    """Observación válida de ``tienda-prueba`` (example.com), con ``recordType``."""
    datos: dict[str, Any] = {
        "recordType": "observation",
        "schemaVersion": "3.1",
        "retailerCode": TIENDA_PRUEBA,
        "productUrl": f"https://www.{DOMINIO_PRUEBA}{url_path}",
        "title": "Producto sintético T08b",
        "brand": "MARCA-T08B",
        "model": "MT-1",
        "category": "tools",
        "price": {"current": "49.99", "currency": "USD"},
        "seller": "comercio",
        "condition": "new",
        "availability": {"state": "in_stock"},
        "purchaseMode": "envio",
        "extractedAt": "2026-11-17T10:00:42-08:00",
        "blocked": False,
    }
    datos.update(cambios)
    return datos


def particular(url: str, **cambios: Any) -> dict[str, Any]:
    """La publicación de B18 (REQ: DEWALT DCF840 usado, San Diego, $70) con ``url``."""
    datos: dict[str, Any] = {
        "recordType": "observation",
        "schemaVersion": "3.1",
        "retailerCode": "particular",
        "productUrl": url,
        "brand": "DEWALT",
        "model": "DCF840",
        "content": "atornillador, batería y cargador",
        "category": "tools",
        "price": {"current": "70.00", "currency": "USD"},
        "seller": "particular",
        "condition": "used",
        "availability": {"state": "listed"},
        "purchaseMode": "particular",
        "pickupLocation": "san_diego",
        "extractedAt": "2026-11-16T10:00:00-08:00",
        "blocked": False,
    }
    datos.update(cambios)
    return datos


def demanda(fecha: str = "2026-11-18", **cambios: Any) -> dict[str, Any]:
    return {"recordType": "local_demand", "category": "beauty", "level": "medium", "date": fecha}


ENCABEZADO_COMPARABLE = (
    "gtin,brand,model,condition,askingPrice,currency,exchangeRate,city,date,sold"
)
#: B18: usados comparables (precios pedidos) $120, $130 y $140 del DEWALT DCF840.
CSV_B18 = csv_bytes(
    ENCABEZADO_COMPARABLE,
    ",DEWALT,DCF840,used,120.00,USD,,san_diego,2026-11-14,false",
    ",DEWALT,DCF840,used,130.00,USD,,san_diego,2026-11-15,false",
    ",DEWALT,DCF840,used,140.00,USD,,san_diego,2026-11-16,false",
)


# =========================================================================================
# Escenarios B34 (b) y B34 (c) — REQ v2.9 "B34 — Carga por archivo"
# =========================================================================================


@pytest.mark.scenario("B34 (b)")
def test_b34_b_csv_de_comparables_con_un_renglon_sin_estado():
    """Dado los comparables de B18 ya cargados y un CSV de ``local_comparable`` con 4
    renglones de otro producto en USD (3 completos y un cuarto sin estado): se cargan 3 y se
    rechaza 1 con ``CAMPO OBLIGATORIO FALTANTE (estado)``, que design.md §6 escribe
    ``(condition)``. Reporte: 3 cargados y 1 rechazado."""
    repo, version = nuevo_repo()
    ids = Ids()
    previo, _, _ = correr("local_comparable__b18.csv", CSV_B18, repo, version, ids=ids)
    assert (previo.cargados, previo.rechazados) == (3, 0)

    contenido = csv_bytes(
        ENCABEZADO_COMPARABLE,
        ",OTRA-MARCA,OM-77,used,60.00,USD,,san_diego,2026-11-15,false",
        ",OTRA-MARCA,OM-77,open_box,65.00,USD,,tijuana,2026-11-16,true",
        ",OTRA-MARCA,OM-77,used,70.00,USD,,san_diego,2026-11-17,false",
        ",OTRA-MARCA,OM-77,,75.00,USD,,san_diego,2026-11-17,false",
    )
    reporte, _, _ = correr("local_comparable__b34b.csv", contenido, repo, version, ids=ids)

    assert reporte.cargados == 3
    assert reporte.rechazados == 1
    assert reporte.duplicados == 0
    assert motivos(reporte) == [(5, faltante("condition"))]
    json_ = reporte.a_json()
    assert json_["loaded"] == 3 and json_["rejected"] == 1
    assert json_["rejectedByReason"] == {faltante("condition"): 1}
    assert json_["recordType"] == "local_comparable" and json_["format"] == "csv"
    # Los comparables de B18 siguen ahí: 3 + 3.
    assert len(repo.capturas(TipoRegistro.LOCAL_COMPARABLE, instante=INSTANTE)) == 6
    # El reporte queda guardado (TAB-02) con lo mismo.
    guardada = repo.leer_carga(reporte.id_carga)
    assert guardada.reporte.cargados == 3 and guardada.reporte.rechazados == 1
    assert dict(guardada.reporte.rechazados_por_motivo) == {faltante("condition"): 1}


@pytest.mark.scenario("B34 (c)")
def test_b34_c_jsonl_del_vps_con_un_renglon_sin_record_type():
    """Un JSON Lines de observaciones guardadas del VPS con 2 renglones, uno con
    ``recordType: observation`` y otro sin ``recordType`` (DEC-227): se carga 1 y se rechaza
    1 con ``TIPO DE REGISTRO DESCONOCIDO``. Reporte: 1 cargado y 1 rechazado."""
    sin_tipo = comercio("/p/vps-2", extractedAt="2026-11-17T18:05:00Z")
    sin_tipo.pop("recordType")
    contenido = jsonl(comercio("/p/vps-1", extractedAt="2026-11-17T18:00:12Z"), sin_tipo)

    reporte, repo, ids = correr("observaciones_vps.jsonl", contenido)

    assert (reporte.cargados, reporte.rechazados) == (1, 1)
    assert motivos(reporte) == [(2, TIPO_DESCONOCIDO)]
    assert reporte.a_json()["rejectedByReason"] == {TIPO_DESCONOCIDO: 1}
    guardada = repo.leer_carga(reporte.id_carga)
    assert (guardada.reporte.cargados, guardada.reporte.rechazados) == (1, 1)
    # Sin recordType solo queda en el reporte (design.md §2): ningún RECHAZADA_VALIDACION.
    assert _registros_rechazo(repo, ids) == []


def _registros_rechazo(repo, ids) -> list[RegistroRechazo]:
    salida = []
    for id_ in ids.dados:
        registro = repo.leer_evaluacion(id_)
        if isinstance(registro, RegistroRechazo):
            salida.append(registro)
    return salida


# =========================================================================================
# REQ §3.2.6 punto 1: un registro inválido no detiene la carga; motivos del catálogo
# =========================================================================================


def test_mezcla_de_tipos_cada_rechazo_con_su_motivo_y_la_carga_sigue():
    """JSON Lines admite tipos mezclados (CTR-02). Un rechazo por cada motivo de §3.2.6,
    intercalados con registros válidos: ninguno detiene la carga."""
    plataforma = SIN_PREFIJO.domains[0]
    comparable_mxn = {
        "recordType": "local_comparable",
        "brand": "DEWALT",
        "model": "DCF840",
        "condition": "used",
        "askingPrice": "2400.00",
        "currency": "MXN",
        "city": "san_diego",
        "date": "2026-11-15",
        "sold": False,
    }
    contenido = jsonl(
        demanda(),  # 1 válido
        comparable_mxn,  # 2 sin tipo de cambio (B34 a)
        comercio("/p/precio-cero", price={"current": "0.00", "currency": "USD"}),  # 3
        comercio("/p/ok"),  # 4 válido
        {"recordType": "coupon"},  # 5
        particular(f"https://{plataforma}/item/x", pickupLocation="ensenada"),  # 6
        comercio(productUrl="https://ejemplo-no-autorizado.example.net/p/1"),  # 7
        demanda("2026-11-17"),  # 8 válido
    )
    reporte, _, _ = correr("mezcla.jsonl", contenido)

    assert motivos(reporte) == [
        (2, faltante("exchangeRate")),
        (3, PRECIO_INVALIDO),
        (5, TIPO_DESCONOCIDO),
        (6, CIUDAD_NO_CONFIGURADA),
        (7, DOMINIO_NO_AUTORIZADO),
    ]
    assert reporte.cargados == 3
    assert reporte.rechazados == 5
    assert reporte.a_json()["citiesToRegister"] == ["ensenada"]
    assert sum(reporte.rechazados_por_motivo.values()) == 5


def test_todo_rechazo_lleva_su_carga_y_su_renglon_decision_33_y_dec_250():
    contenido = jsonl(
        {"recordType": "coupon"},
        comercio("/p/sin-cat", category=None),
        demanda("no-es-fecha"),
    )
    reporte, repo, ids = correr("r.jsonl", contenido)
    guardada = repo.leer_carga(reporte.id_carga)
    assert [(r.id_carga, r.renglon) for r in guardada.rechazos] == [
        (reporte.id_carga, 1),
        (reporte.id_carga, 2),
        (reporte.id_carga, 3),
    ]
    # Solo la observación rechazada deja RECHAZADA_VALIDACION, de esa carga y renglón, sin
    # nada del renglón (DEC-250).
    registros = _registros_rechazo(repo, ids)
    assert [(r.id_carga, r.renglon, r.motivo_rechazo) for r in registros] == [
        (reporte.id_carga, 2, faltante("category"))
    ]
    assert registros[0].evaluado_en == INSTANTE


# =========================================================================================
# design.md §12: unitarias de carga
# =========================================================================================


@pytest.mark.parametrize("nombre", ["vacio.jsonl", "local_demand.csv", "solo_blancos.jsonl"])
def test_archivo_vacio_deja_reporte_en_cero(nombre):
    contenido = b"" if "blancos" not in nombre else b"\n  \n\n"
    reporte, repo, _ = correr(nombre, contenido)
    assert (reporte.cargados, reporte.rechazados, reporte.duplicados) == (0, 0, 0)
    assert repo.leer_carga(reporte.id_carga).reporte is not None


def test_csv_solo_con_encabezado_deja_reporte_en_cero():
    reporte, _, _ = correr("local_demand.csv", csv_bytes("category,level,date"))
    assert (reporte.cargados, reporte.rechazados) == (0, 0)


def test_renglon_que_no_es_json_se_rechaza_y_la_carga_sigue():
    contenido = jsonl(demanda(), "{esto no es json", "[1, 2]", "42", demanda("2026-11-16"))
    reporte, _, _ = correr("mal.jsonl", contenido)
    assert reporte.cargados == 2
    assert [r for r, _ in motivos(reporte)] == [2, 3, 4]
    assert {m for _, m in motivos(reporte)} == {TIPO_DESCONOCIDO}


def test_json_con_parse_float_decimal_sin_float():
    """CTR-02: ``parse_float=Decimal``. 85.10 llega como Decimal('85.10'), no 85.1 de float."""
    contenido = (
        b'{"recordType":"local_estimate","brand":"B","model":"M","price":85.10,'
        b'"date":"2026-11-18"}\n'
    )
    reporte, repo, _ = correr("e.jsonl", contenido)
    assert reporte.cargados == 1
    (guardado,) = repo.capturas(TipoRegistro.LOCAL_ESTIMATE, instante=INSTANTE)
    assert guardado.captura.price == Decimal("85.10")
    assert isinstance(guardado.captura.price, Decimal)


@pytest.mark.parametrize("nombre", ["comparables.csv", "coupon.csv", "observaciones-vps.csv"])
def test_csv_sin_tipo_en_el_nombre_rechaza_cada_renglon(nombre):
    contenido = csv_bytes("category,level,date", "beauty,medium,2026-11-18", "tools,low,2026-11-18")
    reporte, _, _ = correr(nombre, contenido)
    assert reporte.cargados == 0
    assert motivos(reporte) == [(2, TIPO_DESCONOCIDO), (3, TIPO_DESCONOCIDO)]


def test_csv_con_sufijo_toma_el_tipo_del_nombre():
    contenido = csv_bytes("category,level,date", "beauty,medium,2026-11-18")
    reporte, _, _ = correr("local_demand__2026-11-18.csv", contenido)
    assert reporte.cargados == 1 and reporte.tipo_registro is TipoRegistro.LOCAL_DEMAND


def test_csv_celda_vacia_es_campo_ausente():
    """CTR-03: celda vacía = campo ausente. ``condition`` vacía en ``local_estimate`` (opcional)
    vale para cualquier estado; ``exchangeRate`` vacía en USD no falta."""
    contenido = csv_bytes(
        "gtin,brand,model,condition,price,date",
        ",B,M,,90.00,2026-11-18",
    )
    reporte, repo, _ = correr("local_estimate.csv", contenido)
    assert reporte.cargados == 1
    (guardado,) = repo.capturas(TipoRegistro.LOCAL_ESTIMATE, instante=INSTANTE)
    assert guardado.captura.condition is None and guardado.captura.gtin is None


def test_csv_listas_separadas_por_barra():
    contenido = csv_bytes(
        "clientAlias,items,quantity,acceptedConditions,modality,date",
        "cliente-a,MODELO-1|MODELO-2|MODELO-3,2,new|open_box,link_only,2026-11-18",
    )
    reporte, repo, _ = correr("client_request.csv", contenido)
    assert (reporte.cargados, reporte.rechazados) == (1, 0)
    (guardado,) = repo.capturas(TipoRegistro.CLIENT_REQUEST, instante=INSTANTE)
    assert list(guardado.captura.items) == ["MODELO-1", "MODELO-2", "MODELO-3"]
    assert [getattr(c, "value", c) for c in guardado.captura.accepted_conditions] == [
        "new",
        "open_box",
    ]
    assert guardado.captura.quantity == 2


def test_csv_campos_anidados_con_punto():
    """CTR-03: ``price.current``, ``availability.state`` en el encabezado."""
    contenido = csv_bytes(
        "schemaVersion,retailerCode,productUrl,title,brand,model,category,price.current,"
        "price.currency,seller,condition,availability.state,availability.quantity,"
        "purchaseMode,extractedAt,blocked",
        f"3.1,{TIENDA_PRUEBA},https://www.{DOMINIO_PRUEBA}/p/csv-1,T,MB,M1,tools,49.99,USD,"
        "comercio,new,in_stock,3,envio,2026-11-17T10:00:00-08:00,false",
    )
    reporte, _, _ = correr("observation.csv", contenido)
    assert (reporte.cargados, reporte.rechazados) == (1, 0)


def test_duplicados_se_cuentan_en_duplicates_y_no_se_guardan():
    contenido = jsonl(demanda(), demanda(), comercio("/p/d"), comercio("/p/d"))
    ids = Ids()
    reporte, repo, _ = correr("d.jsonl", contenido, ids=ids)
    assert (reporte.cargados, reporte.rechazados, reporte.duplicados) == (2, 0, 2)
    assert reporte.a_json()["duplicates"] == 2
    assert len(repo.capturas(TipoRegistro.LOCAL_DEMAND, instante=INSTANTE)) == 1
    # Recargar el mismo archivo: todo duplicado.
    otra, _, _ = correr("d.jsonl", contenido, repo, repo.version_configuracion(1), ids=ids)
    assert (otra.cargados, otra.rechazados, otra.duplicados) == (0, 0, 4)


def test_reporte_ctr_05_sin_contenido_de_los_renglones():
    alias = "ALIAS-SECRETO-T08B"
    contenido = jsonl(
        {
            "recordType": "client_request",
            "clientAlias": alias,
            "items": ["X"],
            "quantity": "no-es-entero",
            "modality": "link_only",
            "date": "2026-11-18",
        },
        comercio("/p/secreto-de-url", title="TITULO-SECRETO", category=None),
    )
    reporte, repo, _ = correr("c.jsonl", contenido)
    assert set(reporte.a_json()) == {
        "loadRunId",
        "fileName",
        "format",
        "recordType",
        "loaded",
        "rejected",
        "duplicates",
        "rejectedByReason",
        "rejections",
        "citiesToRegister",
    }
    for rechazo in reporte.a_json()["rejections"]:
        assert set(rechazo) == {"line", "recordType", "reason"}
    texto = json.dumps(reporte.a_json(), ensure_ascii=False) + repr(reporte)
    texto += repr(repo.leer_carga(reporte.id_carga))
    for secreto in (alias, "TITULO-SECRETO", "secreto-de-url", "no-es-entero"):
        assert secreto not in texto


# =========================================================================================
# DEC-255: clave de idempotencia sin idempotencyKey
# =========================================================================================


def _leida(datos: dict[str, Any]):
    datos = dict(datos)
    datos.pop("recordType", None)
    return leer_observacion(datos)


def test_dec_255_clave_con_utc_truncado_al_minuto_y_tienda_vacia():
    obs = _leida(comercio("/p/k1", extractedAt="2026-11-17T10:00:42-08:00"))
    assert clave_idempotencia(obs) == (
        f"{TIENDA_PRUEBA}|https://{DOMINIO_PRUEBA}/p/k1||2026-11-17T18:00"
    )
    con_tienda = _leida(comercio("/p/k1", storeCode="tp-cv", extractedAt="2026-11-17T23:59:59Z"))
    assert clave_idempotencia(con_tienda) == (
        f"{TIENDA_PRUEBA}|https://{DOMINIO_PRUEBA}/p/k1|tp-cv|2026-11-17T23:59"
    )


def test_dec_255_idempotency_key_del_contrato_se_usa_tal_cual():
    obs = _leida(comercio("/p/k2", idempotencyKey="Clave Del Worker #1"))
    assert clave_idempotencia(obs) == "Clave Del Worker #1"


def test_dec_255_misma_minuto_utc_desde_otra_zona_es_duplicado():
    contenido = jsonl(
        comercio("/p/k3", extractedAt="2026-11-17T10:00:05-08:00"),
        comercio("/p/k3", extractedAt="2026-11-17T18:00:59Z"),  # mismo minuto UTC
        comercio("/p/k3", extractedAt="2026-11-17T18:01:00Z"),  # minuto siguiente
        comercio("/p/k3", extractedAt="2026-11-17T18:00:30Z", storeCode="tp-cv"),  # otra tienda
    )
    reporte, _, _ = correr("k.jsonl", contenido)
    assert (reporte.cargados, reporte.duplicados) == (3, 1)


def test_dec_255_la_url_escrita_de_otra_forma_es_la_misma_clave():
    variantes = [
        f"https://www.{DOMINIO_PRUEBA}/p/k4",
        f"http://{DOMINIO_PRUEBA}/p/k4/",
        f"https://WWW.{DOMINIO_PRUEBA.upper()}/p/./k4#resenas",
        f"https://{DOMINIO_PRUEBA}/p/otra/../k4",
    ]
    contenido = jsonl(*(comercio(productUrl=u) for u in variantes))
    reporte, _, _ = correr("u.jsonl", contenido)
    assert (reporte.cargados, reporte.duplicados, reporte.rechazados) == (1, 3, 0)


# =========================================================================================
# DEC-256: URL canónica y prefijo de PAR-09 sobre la ruta normalizada
# =========================================================================================


@pytest.mark.parametrize(
    ("entrada", "esperada"),
    [
        (f"http://WWW.{DOMINIO_PRUEBA.upper()}/a/b/", f"https://{DOMINIO_PRUEBA}/a/b"),
        (f"https://{DOMINIO_PRUEBA}/a/./b/../c#frag", f"https://{DOMINIO_PRUEBA}/a/c"),
        (f"https://{DOMINIO_PRUEBA}/a/%2e%2e/c", f"https://{DOMINIO_PRUEBA}/c"),
        (f"https://{DOMINIO_PRUEBA}/a/%2E/c", f"https://{DOMINIO_PRUEBA}/a/c"),
        (f"https://{DOMINIO_PRUEBA}/p?b=2&a=1#x", f"https://{DOMINIO_PRUEBA}/p?b=2&a=1"),
        (f"https://sub.www.{DOMINIO_PRUEBA}/p", f"https://sub.www.{DOMINIO_PRUEBA}/p"),
    ],
)
def test_dec_256_url_canonica(entrada, esperada):
    assert url_canonica(entrada) == esperada


@pytest.mark.parametrize(
    ("ruta", "esperada"),
    [
        ("/marketplace/../groups", "/groups"),
        ("/marketplace/%2e%2e/groups", "/groups"),
        ("/marketplace/.%2E/groups", "/groups"),
        ("/../../x", "/x"),
        ("/", ""),
        ("/a//b/", "/a//b"),
    ],
)
def test_dec_256_ruta_normalizada(ruta, esperada):
    assert ruta_normalizada(ruta) == esperada


@pytest.mark.parametrize(
    ("ruta", "motivo"),
    [
        ("/marketplace/item/1", None),
        ("/marketplace/./item/1", None),
        ("/marketplace/../groups/1", DOMINIO_NO_AUTORIZADO),
        ("/marketplace/%2e%2e/groups/1", DOMINIO_NO_AUTORIZADO),
        ("/marketplace/%2E%2E/groups/1", DOMINIO_NO_AUTORIZADO),
        ("/marketplace/item/../../groups/1", DOMINIO_NO_AUTORIZADO),
        ("/marketplacefalso/item/1", DOMINIO_NO_AUTORIZADO),
    ],
)
def test_dec_256_prefijo_sobre_la_ruta_normalizada_de_punta_a_punta(ruta, motivo):
    url = f"https://{CON_PREFIJO.domains[0]}{ruta}"
    reporte, repo, ids = correr("p.jsonl", jsonl(particular(url)))
    if motivo is None:
        assert (reporte.cargados, reporte.rechazados) == (1, 0)
    else:
        assert motivos(reporte) == [(1, motivo)]
        assert reporte.cargados == 0
        # El rechazo deja su RECHAZADA_VALIDACION (DEC-250) y no guarda la publicación.
        assert [r.motivo_rechazo for r in _registros_rechazo(repo, ids)] == [motivo]


def test_dec_256_la_publicacion_guarda_la_url_canonica():
    url = f"https://WWW.{SIN_PREFIJO.domains[0].upper()}/item/./b18/#fotos"
    reporte, repo, _ = correr("p.jsonl", jsonl(particular(url)))
    assert reporte.cargados == 1
    canonica = f"https://{SIN_PREFIJO.domains[0]}/item/b18"
    assert repo.buscar_publicacion("particular", canonica, None) is not None


# =========================================================================================
# DEC-271: captured_at = instante de la carga
# =========================================================================================


def test_dec_271_captured_at_es_el_instante_de_la_carga_no_la_fecha_de_la_captura():
    instante = dt.datetime(2026, 11, 18, 9, 15, tzinfo=dt.timezone(dt.timedelta(hours=-8)))
    reporte, repo, _ = correr("c.jsonl", jsonl(demanda("2026-11-10")), instante=instante)
    assert reporte.cargados == 1
    (guardada,) = repo.capturas(TipoRegistro.LOCAL_DEMAND, instante=instante)
    assert guardada.capturada_en == instante
    # "A un instante": antes de la carga no existe.
    antes = instante - dt.timedelta(seconds=1)
    assert repo.capturas(TipoRegistro.LOCAL_DEMAND, instante=antes) == ()


def test_dec_271_reproduccion_mismo_archivo_mismo_instante_mismo_resultado():
    contenido = jsonl(demanda(), {"recordType": "coupon"}, comercio("/p/r"))
    r1, _, _ = correr("x.jsonl", contenido)
    r2, _, _ = correr("x.jsonl", contenido)
    assert r1.a_json() == r2.a_json()


def test_dec_271_cli_instante_explicito_es_captured_at(tmp_path):
    repo, _ = nuevo_repo()
    archivo = tmp_path / "local_demand.csv"
    archivo.write_bytes(csv_bytes("category,level,date", "beauty,high,2026-11-18"))
    salida, errores = io.StringIO(), io.StringIO()

    def reloj():  # no debe usarse con --instante
        raise AssertionError("el reloj no se lee con --instante")

    codigo = cli.main(
        ["cargar", str(archivo), "--instante", "2026-11-18T18:00:00Z"],
        repositorio=lambda: repo,
        reloj=reloj,
        salida=salida,
        errores=errores,
    )
    assert codigo == 0, errores.getvalue()
    impreso = json.loads(salida.getvalue())
    assert impreso["loaded"] == 1 and impreso["fileName"] == "local_demand.csv"
    (guardada,) = repo.capturas(TipoRegistro.LOCAL_DEMAND, instante=INSTANTE)
    assert guardada.capturada_en == INSTANTE


def test_cli_sin_instante_usa_el_reloj(tmp_path):
    repo, _ = nuevo_repo()
    archivo = tmp_path / "local_demand.csv"
    archivo.write_bytes(csv_bytes("category,level,date", "beauty,high,2026-11-18"))
    codigo = cli.main(
        ["cargar", str(archivo)],
        repositorio=lambda: repo,
        reloj=lambda: INSTANTE,
        salida=io.StringIO(),
        errores=io.StringIO(),
    )
    assert codigo == 0
    (guardada,) = repo.capturas(TipoRegistro.LOCAL_DEMAND, instante=INSTANTE)
    assert guardada.capturada_en == INSTANTE


@pytest.mark.parametrize("instante", ["2026-11-18T10:00:00", "mañana", "2026-11-18"])
def test_cli_instante_sin_desfase_o_invalido_sale_con_2(tmp_path, instante):
    repo, _ = nuevo_repo()
    archivo = tmp_path / "local_demand.csv"
    archivo.write_bytes(csv_bytes("category,level,date", "beauty,high,2026-11-18"))
    codigo = cli.main(
        ["cargar", str(archivo), "--instante", instante],
        repositorio=lambda: repo,
        reloj=lambda: INSTANTE,
        salida=io.StringIO(),
        errores=io.StringIO(),
    )
    assert codigo == 2


def test_cli_config_cargar_es_idempotente_por_sha256(tmp_path):
    repo = RepositorioMemoria()
    archivo = tmp_path / "config.yaml"
    archivo.write_text(con_sucursales_prueba(BASE.read_text(encoding="utf-8")), encoding="utf-8")
    salidas = []
    for _ in range(2):
        salida = io.StringIO()
        codigo = cli.main(
            ["config", "cargar", str(archivo)],
            repositorio=lambda: repo,
            reloj=lambda: CONFIG_EN,
            salida=salida,
            errores=io.StringIO(),
        )
        assert codigo == 0
        salidas.append(json.loads(salida.getvalue()))
    assert salidas[0]["created"] is True and salidas[1]["created"] is False
    assert salidas[0]["configVersionId"] == salidas[1]["configVersionId"]
    assert salidas[0]["sha256"] == salidas[1]["sha256"]


# =========================================================================================
# DEC-238: conversión estricta del texto de un CSV a int y bool
# =========================================================================================


@pytest.mark.parametrize(
    ("sold", "quantity_ok"),
    [("true", True), ("false", True)],
)
def test_dec_238_csv_true_false_se_convierten(sold, quantity_ok):
    contenido = csv_bytes(
        ENCABEZADO_COMPARABLE, f",B,M,used,10.00,USD,,san_diego,2026-11-18,{sold}"
    )
    reporte, repo, _ = correr("local_comparable.csv", contenido)
    assert reporte.cargados == 1
    (guardado,) = repo.capturas(TipoRegistro.LOCAL_COMPARABLE, instante=INSTANTE)
    assert guardado.captura.sold is (sold == "true")


@pytest.mark.parametrize("sold", ["1", "0", "yes", "verdadero", "si"])
def test_dec_238_csv_booleano_que_no_se_convierte_se_rechaza(sold):
    contenido = csv_bytes(
        ENCABEZADO_COMPARABLE, f",B,M,used,10.00,USD,,san_diego,2026-11-18,{sold}"
    )
    reporte, _, _ = correr("local_comparable.csv", contenido)
    assert motivos(reporte) == [(2, faltante("sold"))]


def test_dec_238_csv_entero_se_convierte():
    contenido = csv_bytes(
        "clientAlias,items,quantity,modality,date", "c1,MOD-1,3,link_only,2026-11-18"
    )
    reporte, repo, _ = correr("client_request.csv", contenido)
    assert reporte.cargados == 1
    (guardado,) = repo.capturas(TipoRegistro.CLIENT_REQUEST, instante=INSTANTE)
    assert guardado.captura.quantity == 3 and type(guardado.captura.quantity) is int
    # Por defecto [new] (DEC-241).
    assert [getattr(c, "value", c) for c in guardado.captura.accepted_conditions] == ["new"]


@pytest.mark.parametrize("quantity", ["3.0", "tres", "1e1", "true"])
def test_dec_238_csv_entero_que_no_se_convierte_se_rechaza(quantity):
    contenido = csv_bytes(
        "clientAlias,items,quantity,modality,date", f"c1,MOD-1,{quantity},link_only,2026-11-18"
    )
    reporte, _, _ = correr("client_request.csv", contenido)
    assert motivos(reporte) == [(2, faltante("quantity"))]


def test_dec_238_jsonl_booleano_y_entero_estrictos():
    """En JSON Lines no hay conversión: ``"false"`` no es False y ``true`` no es 1."""
    comparable = {
        "recordType": "local_comparable",
        "brand": "B",
        "model": "M",
        "condition": "used",
        "askingPrice": "10.00",
        "currency": "USD",
        "city": "san_diego",
        "date": "2026-11-18",
        "sold": "false",
    }
    pedido = {
        "recordType": "client_request",
        "clientAlias": "c1",
        "items": ["M"],
        "quantity": True,
        "modality": "link_only",
        "date": "2026-11-18",
    }
    reporte, _, _ = correr("t.jsonl", jsonl(comparable, pedido))
    assert motivos(reporte) == [(1, faltante("sold")), (2, faltante("quantity"))]


# =========================================================================================
# DEC-240 y DEC-247: zona de general.timezone pasada siempre a leer_captura
# =========================================================================================


def _config_con_zona(zona: str):
    texto = con_sucursales_prueba(BASE.read_text(encoding="utf-8"))
    assert texto.count("timezone: America/Tijuana") == 1
    texto = texto.replace("timezone: America/Tijuana", f"timezone: {zona}")
    return cargar_configuracion_texto(texto, origen=f"base + {zona}")


def _visita(visited_at: str) -> dict[str, Any]:
    return {
        "recordType": "store_visit",
        "storeCode": "tp-cv",
        "brand": "B",
        "model": "M",
        "result": "found",
        "visitedAt": visited_at,
    }


def test_dec_240_visited_at_sin_desfase_en_la_zona_de_la_configuracion():
    reporte, repo, _ = correr("v.jsonl", jsonl(_visita("2026-11-18T09:00:00")))
    assert reporte.cargados == 1
    (guardada,) = repo.capturas(TipoRegistro.STORE_VISIT, instante=INSTANTE)
    # Tijuana en noviembre: UTC−8.
    assert guardada.captura.visited_at == dt.datetime(2026, 11, 18, 17, 0, tzinfo=dt.UTC)


def test_dec_240_otra_zona_en_la_configuracion_cambia_la_lectura():
    """La zona no está fija en el código: sale de general.timezone."""
    repo, version = nuevo_repo(_config_con_zona("America/New_York"))
    reporte, repo, _ = correr("v.jsonl", jsonl(_visita("2026-11-18T09:00:00")), repo, version)
    assert reporte.cargados == 1
    (guardada,) = repo.capturas(TipoRegistro.STORE_VISIT, instante=INSTANTE)
    assert guardada.captura.visited_at == dt.datetime(2026, 11, 18, 14, 0, tzinfo=dt.UTC)


def test_dec_240_csv_visited_at_sin_desfase():
    contenido = csv_bytes(
        "storeCode,brand,model,result,visitedAt", "tp-cv,B,M,found,2026-11-18T09:00:00"
    )
    reporte, repo, _ = correr("store_visit.csv", contenido)
    assert reporte.cargados == 1
    (guardada,) = repo.capturas(TipoRegistro.STORE_VISIT, instante=INSTANTE)
    assert guardada.captura.visited_at == dt.datetime(2026, 11, 18, 17, 0, tzinfo=dt.UTC)


def test_dec_240_observacion_sin_desfase_sigue_siendo_campo_faltante():
    reporte, _, _ = correr("o.jsonl", jsonl(comercio("/p/z", extractedAt="2026-11-17T10:00:00")))
    assert motivos(reporte) == [(1, faltante("extractedAt"))]


# =========================================================================================
# DEC-274 punto 8: el día de la carga siempre se pasa (zona de PAR-01)
# =========================================================================================

#: 2026-11-19 07:30 UTC = 2026-11-18 23:30 en Tijuana; 08:30 UTC = 2026-11-19 00:30.
ANTES_DE_MEDIANOCHE = dt.datetime(2026, 11, 19, 7, 30, tzinfo=dt.UTC)
DESPUES_DE_MEDIANOCHE = dt.datetime(2026, 11, 19, 8, 30, tzinfo=dt.UTC)


def _capturas_del_19() -> list[tuple[dict[str, Any], str]]:
    eval_id = str(UUID(int=999))
    return [
        (demanda("2026-11-19"), "date"),
        (
            {
                "recordType": "local_estimate",
                "brand": "B",
                "model": "M",
                "price": "5.00",
                "date": "2026-11-19",
            },
            "date",
        ),
        (
            {
                "recordType": "msrp",
                "brand": "B",
                "model": "M",
                "value": "9.00",
                "source": "caja",
                "date": "2026-11-19",
            },
            "date",
        ),
        (
            {
                "recordType": "local_comparable",
                "brand": "B",
                "model": "M",
                "condition": "used",
                "askingPrice": "5.00",
                "currency": "USD",
                "city": "san_diego",
                "date": "2026-11-19",
                "sold": False,
            },
            "date",
        ),
        (
            {
                "recordType": "client_request",
                "clientAlias": "c1",
                "items": ["M"],
                "quantity": 1,
                "modality": "link_only",
                "date": "2026-11-19",
            },
            "date",
        ),
        (_visita("2026-11-19T00:05:00"), "visitedAt"),
        (
            {
                "recordType": "actual_result",
                "evaluationId": eval_id,
                "channel": "local",
                "units": 1,
                "purchasePrice": "5.00",
                "salePrice": "9.00",
                "actualCosts": "0.00",
                "purchasedOn": "2026-11-18",
                "soldOn": "2026-11-19",
            },
            "soldOn",
        ),
    ]


def test_dec_274_8_fecha_del_dia_siguiente_en_tijuana_se_rechaza_de_punta_a_punta():
    casos = _capturas_del_19()
    reporte, _, _ = correr("f.jsonl", jsonl(*(c for c, _ in casos)), instante=ANTES_DE_MEDIANOCHE)
    assert reporte.cargados == 0
    assert motivos(reporte) == [(i, faltante(campo)) for i, (_, campo) in enumerate(casos, 1)]


def test_dec_274_8_la_misma_fecha_pasa_despues_de_la_medianoche_en_tijuana():
    casos = _capturas_del_19()
    reporte, _, _ = correr("f.jsonl", jsonl(*(c for c, _ in casos)), instante=DESPUES_DE_MEDIANOCHE)
    assert (reporte.cargados, reporte.rechazados) == (len(casos), 0)


def test_dec_274_8_csv_con_fecha_del_dia_siguiente():
    contenido = csv_bytes("category,level,date", "beauty,low,2026-11-19", "tools,low,2026-11-18")
    reporte, _, _ = correr("local_demand.csv", contenido, instante=ANTES_DE_MEDIANOCHE)
    assert motivos(reporte) == [(2, faltante("date"))]
    assert reporte.cargados == 1


def test_dec_274_8_el_dia_sale_de_la_zona_de_la_configuracion_no_de_utc():
    """Con America/New_York (UTC−5), las 07:30 UTC del 19 ya son el 19: la fecha pasa."""
    repo, version = nuevo_repo(_config_con_zona("America/New_York"))
    reporte, _, _ = correr(
        "f.jsonl", jsonl(demanda("2026-11-19")), repo, version, instante=ANTES_DE_MEDIANOCHE
    )
    assert reporte.cargados == 1


# =========================================================================================
# DEC-274 punto 9: un monto enorme entero que detiene el repositorio es rechazo del renglón
# =========================================================================================

_OBS_ENORME = (
    b'{"recordType":"observation","schemaVersion":"3.1","retailerCode":"tienda-prueba",'
    b'"productUrl":"https://www.example.com/p/enorme","title":"T","brand":"MARCA-ENORME",'
    b'"model":"ME-1","category":"tools","price":{"current":1e400,"currency":"USD"},'
    b'"seller":"comercio","condition":"new","availability":{"state":"in_stock"},'
    b'"purchaseMode":"envio","extractedAt":"2026-11-17T10:00:42-08:00","blocked":false}'
)


def test_dec_274_9_precio_enorme_es_precio_invalido_y_la_carga_sigue():
    contenido = jsonl(demanda(), _OBS_ENORME, comercio("/p/despues"))
    reporte, repo, ids = correr("e.jsonl", contenido)
    assert motivos(reporte) == [(2, PRECIO_INVALIDO)]
    assert reporte.cargados == 2
    # El renglón rechazado no deja producto, publicación ni observación.
    marca_modelo = IdentificadorProducto("brand_model", "marca-enorme|me-1")
    assert repo.buscar_producto(marca_modelo) is None
    url = f"https://{DOMINIO_PRUEBA}/p/enorme"
    assert repo.buscar_publicacion(TIENDA_PRUEBA, url, None) is None
    # Deja su RECHAZADA_VALIDACION (DEC-250) y su load_rejection, de esa carga y renglón.
    registros = _registros_rechazo(repo, ids)
    assert [(r.renglon, r.motivo_rechazo) for r in registros] == [(2, PRECIO_INVALIDO)]
    assert repo.leer_carga(reporte.id_carga).reporte.rechazados == 1


@pytest.mark.parametrize(
    ("columna", "renglon_csv", "motivo"),
    [
        ("askingPrice", ",B,M,used,1e400,USD,,san_diego,2026-11-18,false", PRECIO_INVALIDO),
    ],
)
def test_dec_274_9_precio_enorme_en_csv_de_captura(columna, renglon_csv, motivo):
    contenido = csv_bytes(
        ENCABEZADO_COMPARABLE, renglon_csv, ",B,M,used,10.00,USD,,san_diego,2026-11-18,false"
    )
    reporte, _, _ = correr("local_comparable.csv", contenido)
    assert motivos(reporte) == [(2, motivo)]
    assert reporte.cargados == 1


def test_dec_274_9_otro_monto_enorme_de_la_observacion_cita_su_campo():
    texto = _OBS_ENORME.replace(
        b'{"current":1e400,"currency":"USD"}', b'{"current":10.00,"was":1e400,"currency":"USD"}'
    )
    reporte, _, _ = correr("e.jsonl", jsonl(texto, comercio("/p/despues")))
    assert motivos(reporte) == [(1, faltante("price.was"))]
    assert reporte.cargados == 1


# =========================================================================================
# citiesToRegister, blocked, orden del archivo, archivo inválido
# =========================================================================================


def test_cities_to_register_junta_las_ciudades_de_ciudad_no_configurada():
    plataforma = SIN_PREFIJO.domains[0]
    contenido = csv_bytes(
        ENCABEZADO_COMPARABLE,
        ",B,M,used,10.00,USD,,rosarito,2026-11-18,false",
        ",B,M,used,11.00,USD,,ensenada,2026-11-18,false",
        ",B,M,used,12.00,USD,,rosarito,2026-11-18,false",
    )
    repo, version = nuevo_repo()
    ids = Ids()
    reporte, _, _ = correr("local_comparable.csv", contenido, repo, version, ids=ids)
    assert set(reporte.a_json()["citiesToRegister"]) == {"rosarito", "ensenada"}
    assert len(reporte.a_json()["citiesToRegister"]) == 2
    assert reporte.rechazados_por_motivo == {CIUDAD_NO_CONFIGURADA: 3}
    obs = particular(f"https://{plataforma}/item/c", pickupLocation="mexicali")
    otro, _, _ = correr("p.jsonl", jsonl(obs), repo, version, ids=ids)
    assert otro.a_json()["citiesToRegister"] == ["mexicali"]


def test_sin_rechazos_de_ciudad_cities_to_register_vacia():
    reporte, _, _ = correr("x.jsonl", jsonl(demanda(), {"recordType": "coupon"}))
    assert reporte.a_json()["citiesToRegister"] == []


def test_archivo_con_extension_desconocida_no_empieza_la_carga():
    from oip.entradas.cargador import ErrorDeArchivo

    repo, version = nuevo_repo()
    with pytest.raises(ErrorDeArchivo):
        cargar("datos.json", jsonl(demanda()), repo, version, INSTANTE, nuevo_id=Ids())


def test_el_cargador_no_escribe_el_alias_en_los_logs(caplog):
    alias = "ALIAS-LOG-T08B"
    caplog.set_level(logging.DEBUG)
    contenido = jsonl(
        {
            "recordType": "client_request",
            "clientAlias": alias,
            "items": [],
            "quantity": 1,
            "modality": "link_only",
            "date": "2026-11-18",
        },
        {
            "recordType": "client_request",
            "clientAlias": alias,
            "items": ["A"],
            "quantity": 1,
            "modality": "link_only",
            "date": "2026-11-18",
        },
    )
    reporte, repo, _ = correr("c.jsonl", contenido)
    assert reporte.rechazados == 1 and reporte.cargados == 1
    assert alias not in caplog.text
    assert alias not in repr(repo.capturas(TipoRegistro.CLIENT_REQUEST, instante=INSTANTE))


# =========================================================================================
# Defectos (xfail estricto): un renglón no debe detener la carga (REQ §3.2.6 punto 1)
# =========================================================================================


@pytest.mark.xfail(
    strict=True,
    raises=OverflowError,
    reason=(
        "IMPLEMENTATION DEFECT T08b-1: un extractedAt válido para el contrato pero fuera del "
        "rango de datetime al pasar a UTC (9999-12-31T23:00-08:00 o 0001-01-01T00:00+05:00) "
        "levanta OverflowError y detiene toda la carga (REQ §3.2.6 punto 1: un registro "
        "inválido no detiene la carga)"
    ),
)
@pytest.mark.parametrize("extraida", ["9999-12-31T23:00:00-08:00", "0001-01-01T00:00:00+05:00"])
def test_defecto_1_extracted_at_fuera_de_rango_utc_no_detiene_la_carga(extraida):
    contenido = jsonl(comercio("/p/fuera", extractedAt=extraida), comercio("/p/siguiente"))
    reporte, _, _ = correr("o.jsonl", contenido)
    assert reporte.cargados == 1
    assert reporte.rechazados == 1
    assert motivos(reporte)[0][0] == 1


@pytest.mark.xfail(
    strict=True,
    raises=OverflowError,
    reason=(
        "IMPLEMENTATION DEFECT T08b-2: un visitedAt con desfase fuera del rango de datetime "
        "en la zona de la carga (0001-01-01T00:00+05:00) levanta OverflowError al comprobar "
        "el día de la carga y detiene toda la carga (REQ §3.2.6 punto 1)"
    ),
)
def test_defecto_2_visited_at_fuera_de_rango_no_detiene_la_carga():
    contenido = jsonl(_visita("0001-01-01T00:00:00+05:00"), demanda())
    reporte, _, _ = correr("v.jsonl", contenido)
    assert reporte.cargados == 1
    assert reporte.rechazados == 1
