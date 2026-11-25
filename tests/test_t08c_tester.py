"""Pruebas independientes del tester para T08c (DEC-276 a DEC-280; PR #52).

Escritas desde las fuentes (registro de decisiones §9.16 y ``design.md`` §5, §6, CTR-03,
CTR-04, CTR-05, CTR-07), no desde el código. T08c no tiene escenarios propios del REQ (no
cambia B20 ni B34), así que no llevan ``@pytest.mark.scenario``.

Fixtures sintéticos: la tienda de prueba usa example.com; los dominios de las plataformas
de particulares salen de la configuración de pruebas (``tests/fixtures/config``), nunca se
escriben aquí. Ninguna prueba abre una URL; el instante y el reloj siempre son explícitos.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import logging
from decimal import Decimal
from pathlib import Path
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
from oip.entradas.capturas import leer_captura, motivo_de_rechazo
from oip.entradas.cargador import cargar
from oip.entradas.validacion import validar
from oip.persistencia.repositorios import RegistroRechazo, RepositorioMemoria

FIXTURES = Path(__file__).parent / "fixtures"
CONFIG = configuracion_con_sucursales_prueba()

#: 2026-11-18 10:00 en Tijuana (UTC−8 en noviembre).
INSTANTE = dt.datetime(2026, 11, 18, 18, 0, tzinfo=dt.UTC)
CONFIG_EN = dt.datetime(2026, 11, 1, tzinfo=dt.UTC)

PRECIO_INVALIDO = "PRECIO INVÁLIDO"
DOMINIO = "DOMINIO NO AUTORIZADO"
TIPO_DESCONOCIDO = "TIPO DE REGISTRO DESCONOCIDO"
#: El valor de DEC-280: cabe en UTC, no en America/Tijuana (año 1, antes del 1 de enero).
FUERA_DE_ZONA = "0001-01-01T03:00:00Z"


def faltante(campo: str) -> str:
    return f"CAMPO OBLIGATORIO FALTANTE ({campo})"


class Ids:
    def __init__(self) -> None:
        self.n = 0
        self.dados: list[UUID] = []

    def __call__(self) -> UUID:
        self.n += 1
        nuevo = UUID(int=0xC0000 + self.n)
        self.dados.append(nuevo)
        return nuevo


def _config_con_zona(zona: str):
    texto = con_sucursales_prueba(BASE.read_text(encoding="utf-8"))
    assert texto.count("timezone: America/Tijuana") == 1
    return cargar_configuracion_texto(
        texto.replace("timezone: America/Tijuana", f"timezone: {zona}"), origen=f"base+{zona}"
    )


def correr(nombre: str, contenido: bytes, config=CONFIG):
    repo = RepositorioMemoria()
    version, _ = repo.guardar_version_configuracion(config, cargada_en=CONFIG_EN)
    ids = Ids()
    reporte = cargar(nombre, contenido, repo, version, INSTANTE, nuevo_id=ids)
    return reporte, repo, ids


def jsonl(*renglones: dict[str, Any]) -> bytes:
    return ("\n".join(json.dumps(r, ensure_ascii=False) for r in renglones) + "\n").encode()


def csv_bytes(*renglones: str) -> bytes:
    return ("\n".join(renglones) + "\n").encode()


def rechazos(reporte) -> list[tuple[int, str]]:
    return [(r.renglon, r.motivo) for r in reporte.rechazos]


def registros_rechazo(repo, ids) -> list[RegistroRechazo]:
    salida = []
    for id_ in ids.dados:
        registro = repo.leer_evaluacion(id_)
        if isinstance(registro, RegistroRechazo):
            salida.append(registro)
    return salida


def comercio(**cambios: Any) -> dict[str, Any]:
    """Observación sintética válida de ``tienda-prueba`` (example.com)."""
    datos: dict[str, Any] = {
        "schemaVersion": "3.1",
        "retailerCode": TIENDA_PRUEBA,
        "productUrl": f"https://{DOMINIO_PRUEBA}/p/tester-t08c",
        "title": "Producto sintético del tester",
        "category": "tools",
        "price": {"current": "39.99", "currency": "USD"},
        "seller": "comercio",
        "condition": "new",
        "availability": {"state": "in_stock"},
        "purchaseMode": "envio",
        "extractedAt": "2026-11-17T09:15:00-08:00",
        "blocked": False,
    }
    datos.update(cambios)
    return datos


def particular(**cambios: Any) -> dict[str, Any]:
    """La publicación sintética de B18 (fixture), con cambios."""
    texto = (FIXTURES / "observaciones" / "b18_particular.json").read_text(encoding="utf-8")
    datos = json.loads(texto, parse_float=Decimal)
    datos.pop("_nota")
    datos.update(cambios)
    return datos


def _plataforma(codigo: str) -> tuple[str, str]:
    """(dominio, prefijo) de una plataforma de PAR-09 de la configuración de pruebas."""
    plataforma = CONFIG.contenido.private_sellers.platforms[codigo]
    return plataforma.domains[0], plataforma.path_prefix or ""


# =========================================================================================
# DEC-276: los cinco precios de las capturas que no son un número → PRECIO INVÁLIDO
# =========================================================================================

#: Capturas válidas de CTR-04 (obligatorios de REQ §6), sintéticas.
CAPTURAS: dict[str, dict[str, Any]] = {
    "local_comparable": {
        "gtin": "00012345678905",
        "condition": "used",
        "askingPrice": "80.00",
        "currency": "USD",
        "city": "tijuana",
        "date": "2026-11-14",
        "sold": True,
    },
    "local_estimate": {"brand": "MARCA-T", "model": "MT-8", "price": "61.50", "date": "2026-11-14"},
    "msrp": {
        "brand": "MARCA-T",
        "model": "MT-8",
        "value": "99.99",
        "source": "etiqueta",
        "date": "2026-11-14",
    },
    "actual_result": {
        "evaluationId": "00000000-0000-0000-0000-0000000000c8",
        "channel": "local",
        "units": 1,
        "purchasePrice": "40.00",
        "salePrice": "70.00",
        "actualCosts": "3.25",
        "purchasedOn": "2026-11-10",
        "soldOn": "2026-11-12",
    },
}

#: Los cinco precios de DEC-276, con el nombre que tienen en el archivo.
CINCO_PRECIOS = [
    ("local_comparable", "askingPrice"),
    ("local_estimate", "price"),
    ("msrp", "value"),
    ("actual_result", "purchasePrice"),
    ("actual_result", "salePrice"),
]

#: Valores presentes que no son un número.
NO_NUMEROS = [
    "abc",
    "doce",
    "12,50",
    "$12.50",
    "NaN",
    "Infinity",
    "-Infinity",
    12.5,  # float: nunca se acepta un monto como float
    True,
    False,
    [12],
    {"monto": "12.00"},
]


def test_las_capturas_base_son_validas():
    for tipo, datos in CAPTURAS.items():
        captura = leer_captura(tipo, datos)
        assert captura.precio_invalido is False, tipo
        assert motivo_de_rechazo(captura) is None, tipo


@pytest.mark.parametrize("valor", NO_NUMEROS, ids=repr)
@pytest.mark.parametrize(("tipo", "campo"), CINCO_PRECIOS)
def test_dec_276_precio_que_no_es_un_numero(tipo, campo, valor):
    captura = leer_captura(tipo, {**CAPTURAS[tipo], campo: valor})
    assert captura.precio_invalido is True
    motivo = motivo_de_rechazo(captura)
    assert motivo == PRECIO_INVALIDO
    # R-20: el motivo es solo el código, sin el valor.
    assert str(valor) not in motivo


@pytest.mark.parametrize("vacio", ["", "   ", None], ids=repr)
@pytest.mark.parametrize(("tipo", "campo"), CINCO_PRECIOS)
def test_dec_276_ausente_o_vacio_sigue_siendo_faltante(tipo, campo, vacio):
    # DEC-276 solo cambia el valor presente que no es un número.
    datos = {**CAPTURAS[tipo], campo: vacio}
    with pytest.raises(Exception) as error:
        leer_captura(tipo, datos)
    assert getattr(error.value, "motivo", None) == faltante(campo)
    sin = {k: v for k, v in CAPTURAS[tipo].items() if k != campo}
    with pytest.raises(Exception) as error:
        leer_captura(tipo, sin)
    assert getattr(error.value, "motivo", None) == faltante(campo)


def test_dec_276_actual_costs_no_es_uno_de_los_cinco():
    # actualCosts no es un "precio" de DEC-276: sigue siendo campo faltante (CTR-04).
    with pytest.raises(Exception) as error:
        leer_captura("actual_result", {**CAPTURAS["actual_result"], "actualCosts": "abc"})
    assert getattr(error.value, "motivo", None) == faltante("actualCosts")


def test_dec_276_obligatorio_faltante_va_antes_que_precio_invalido():
    # design.md §6: obligatorios → precio. Sin date y con price que no es número: date.
    datos = {k: v for k, v in CAPTURAS["local_estimate"].items() if k != "date"}
    with pytest.raises(Exception) as error:
        leer_captura("local_estimate", {**datos, "price": "abc"})
    assert getattr(error.value, "motivo", None) == faltante("date")


@pytest.mark.parametrize(("tipo", "campo"), CINCO_PRECIOS)
def test_dec_276_por_json_lines_con_la_carga_completa(tipo, campo):
    validos = {"recordType": tipo, **CAPTURAS[tipo]}
    malo = {**validos, campo: "no-es-numero"}
    if tipo == "actual_result":
        # Otro evaluationId para que el válido no sea un duplicado del malo.
        validos = {**validos, "evaluationId": "00000000-0000-0000-0000-0000000000c9"}
    reporte, _, ids = correr("c.jsonl", jsonl(malo, validos))
    assert rechazos(reporte) == [(1, PRECIO_INVALIDO)]
    assert reporte.rechazos[0].tipo_registro is TipoRegistro(tipo)
    assert (reporte.cargados, reporte.rechazados) == (1, 1)
    assert reporte.a_json()["rejectedByReason"] == {PRECIO_INVALIDO: 1}
    assert "no-es-numero" not in json.dumps(reporte.a_json(), ensure_ascii=False)


def test_dec_276_nan_sin_comillas_no_es_json_valido():
    # El texto "NaN" en un precio da PRECIO INVÁLIDO (arriba). Sin comillas, el renglón no es
    # JSON válido (CTR-02, lectura de T08b y DEC-274): no tiene recordType y no llega a
    # DEC-276. Se deja fijado para que T08c no lo cambie sin decisión (anotado en el #34).
    renglon = json.dumps({"recordType": "msrp", **CAPTURAS["msrp"]}).replace('"99.99"', "NaN")
    reporte, _, _ = correr("m.jsonl", (renglon + "\n").encode())
    assert rechazos(reporte) == [(1, TIPO_DESCONOCIDO)]


def test_dec_276_por_csv():
    contenido = csv_bytes(
        "brand,model,price,date",
        "MARCA-T,MT-8,sesenta,2026-11-14",
        "MARCA-T,MT-9,61.50,2026-11-14",
    )
    reporte, _, _ = correr("local_estimate.csv", contenido)
    assert rechazos(reporte) == [(2, PRECIO_INVALIDO)]
    assert reporte.cargados == 1


# =========================================================================================
# DEC-277: %2f, %5c o %25 en la ruta del enlace de un particular → DOMINIO NO AUTORIZADO
# =========================================================================================


def test_dec_277_el_fixture_del_particular_es_valido():
    assert validar(particular(), CONFIG.contenido).motivo_rechazo is None


@pytest.mark.parametrize(
    "ruta",
    [
        "/item/detail%2fotro",
        "/item/detail%2Fotro",
        "/item%5cdetail",
        "/item%5Cdetail",
        "/item%25detail",
        "/item%252fdetail",  # %2f doblemente codificado
        "/%2F",
    ],
)
def test_dec_277_separador_codificado_en_la_ruta_sin_prefijo(ruta):
    dominio, _ = _plataforma("offerup")
    v = validar(particular(productUrl=f"https://{dominio}{ruta}"), CONFIG.contenido)
    assert v.motivo_rechazo == DOMINIO


@pytest.mark.parametrize("ruta", ["%2f..%2fotra", "/%2F..%2Fotra", "/item%5c..%5cx", "/a%25b"])
def test_dec_277_separador_codificado_con_prefijo(ruta):
    dominio, prefijo = _plataforma("facebook_marketplace")
    assert prefijo  # la plataforma con prefijo de PAR-09
    v = validar(particular(productUrl=f"https://{dominio}{prefijo}{ruta}"), CONFIG.contenido)
    assert v.motivo_rechazo == DOMINIO


@pytest.mark.parametrize(
    ("plataforma", "ruta"),
    [
        ("offerup", "/item/detail/sintetico-77"),
        ("offerup", "/item/detail/con%20espacio"),  # otro escape que no es separador
        ("offerup", "/item/detail/x?ref=%2fa%5cb%25"),  # la query no cuenta (DEC-256)
        ("offerup", "/item/detail/x#%2f"),
        ("facebook_marketplace", "/item/123"),
    ],
)
def test_dec_277_ruta_normal_sigue_pasando(plataforma, ruta):
    dominio, prefijo = _plataforma(plataforma)
    v = validar(particular(productUrl=f"https://{dominio}{prefijo}{ruta}"), CONFIG.contenido)
    assert v.motivo_rechazo is None


def test_dec_277_el_enlace_de_un_comercio_no_cambia():
    # DEC-277 habla de la ruta "de un particular".
    datos = comercio(productUrl=f"https://{DOMINIO_PRUEBA}/p/a%2Fb%5cc%25d")
    assert validar(datos, CONFIG.contenido).motivo_rechazo is None


def test_dec_277_precio_invalido_va_antes():
    dominio, _ = _plataforma("offerup")
    datos = particular(
        productUrl=f"https://{dominio}/item%2fx", price={"current": "0.00", "currency": "USD"}
    )
    assert validar(datos, CONFIG.contenido).motivo_rechazo == PRECIO_INVALIDO


def test_dec_277_por_carga_deja_su_rechazada_validacion():
    dominio, _ = _plataforma("offerup")
    malo = {"recordType": "observation", **particular(productUrl=f"https://{dominio}/i%2Fx")}
    bueno = {"recordType": "observation", **particular()}
    reporte, repo, ids = correr("p.jsonl", jsonl(json_seguro(malo), json_seguro(bueno)))
    assert rechazos(reporte) == [(1, DOMINIO)]
    assert reporte.cargados == 1
    assert [(r.renglon, r.motivo_rechazo) for r in registros_rechazo(repo, ids)] == [(1, DOMINIO)]
    # Sin el enlace en el reporte (R-20).
    assert "%2F" not in json.dumps(reporte.a_json())


def json_seguro(datos: dict[str, Any]) -> dict[str, Any]:
    """Los Decimal del fixture como texto, para ``json.dumps``."""
    return json.loads(json.dumps(datos, default=str))


# =========================================================================================
# DEC-278: oip config cargar <archivo> [--instante ISO] fija loaded_at
# =========================================================================================


def _cli(argv: list[str], repo, reloj):
    salida, errores = io.StringIO(), io.StringIO()
    codigo = cli.main(argv, repositorio=lambda: repo, reloj=reloj, salida=salida, errores=errores)
    return codigo, salida.getvalue(), errores.getvalue()


def _yaml(tmp_path: Path) -> Path:
    ruta = tmp_path / "config-tester.yaml"
    ruta.write_text(con_sucursales_prueba(BASE.read_text(encoding="utf-8")), encoding="utf-8")
    return ruta


def _sin_reloj() -> dt.datetime:
    raise AssertionError("con --instante no se lee el reloj")


HOY = dt.datetime(2026, 11, 25, 15, 30, tzinfo=dt.UTC)


@pytest.mark.parametrize(
    ("texto", "utc"),
    [
        ("2026-11-02T09:00:00-08:00", dt.datetime(2026, 11, 2, 17, tzinfo=dt.UTC)),
        ("2026-11-02T17:00:00Z", dt.datetime(2026, 11, 2, 17, tzinfo=dt.UTC)),
        ("2026-11-03T02:00:00+09:00", dt.datetime(2026, 11, 2, 17, tzinfo=dt.UTC)),
    ],
)
def test_dec_278_con_instante_y_desfase_fija_loaded_at(tmp_path, texto, utc):
    repo = RepositorioMemoria()
    codigo, salida, _ = _cli(
        ["config", "cargar", str(_yaml(tmp_path)), "--instante", texto], repo, _sin_reloj
    )
    assert codigo == 0 and json.loads(salida)["created"] is True
    assert repo.version_configuracion_activa(utc - dt.timedelta(microseconds=1)) is None
    assert repo.version_configuracion_activa(utc).cargada_en == utc


@pytest.mark.parametrize("texto", ["2026-11-02T09:00:00", "2026-11-02", "mañana", ""])
def test_dec_278_instante_sin_desfase_no_registra(tmp_path, texto):
    repo = RepositorioMemoria()
    codigo, salida, _ = _cli(
        ["config", "cargar", str(_yaml(tmp_path)), "--instante", texto], repo, _sin_reloj
    )
    assert codigo != 0 and salida == ""
    assert repo.version_configuracion_activa(dt.datetime(9000, 1, 1, tzinfo=dt.UTC)) is None


def test_dec_278_sin_instante_el_reloj(tmp_path):
    repo = RepositorioMemoria()
    codigo, _, _ = _cli(["config", "cargar", str(_yaml(tmp_path))], repo, lambda: HOY)
    assert codigo == 0
    assert repo.version_configuracion_activa(HOY - dt.timedelta(seconds=1)) is None
    assert repo.version_configuracion_activa(HOY).cargada_en == HOY


def test_dec_278_reproduce_una_carga_pasada(tmp_path):
    """Con loaded_at del reloj (HOY) la carga del 18 no encontraba configuración (DEC-271);
    con ``--instante`` del 1 de noviembre la encuentra y la carga se hace con ese instante."""
    archivo = tmp_path / "local_demand__2026-11-18.csv"
    archivo.write_bytes(b"category,level,date\ntools,high,2026-11-18\n")
    pasado = ["--instante", "2026-11-18T10:00:00-08:00"]

    solo_reloj = RepositorioMemoria()
    assert _cli(["config", "cargar", str(_yaml(tmp_path))], solo_reloj, lambda: HOY)[0] == 0
    codigo, _, errores = _cli(["cargar", str(archivo), *pasado], solo_reloj, _sin_reloj)
    assert codigo == 1 and "configuración activa" in errores

    repo = RepositorioMemoria()
    argv = ["config", "cargar", str(_yaml(tmp_path)), "--instante", "2026-11-01T00:00:00-07:00"]
    assert _cli(argv, repo, _sin_reloj)[0] == 0
    codigo, salida, _ = _cli(["cargar", str(archivo), *pasado], repo, _sin_reloj)
    assert codigo == 0
    reporte = json.loads(salida)
    assert (reporte["loaded"], reporte["rejected"]) == (1, 0)
    (guardada,) = repo.capturas(TipoRegistro.LOCAL_DEMAND, instante=INSTANTE)
    assert guardada.capturada_en == INSTANTE


def test_dec_278_sigue_siendo_idempotente_por_sha256(tmp_path):
    repo = RepositorioMemoria()
    ruta = str(_yaml(tmp_path))
    primero = _cli(
        ["config", "cargar", ruta, "--instante", "2026-11-01T00:00:00Z"], repo, _sin_reloj
    )
    segundo = _cli(
        ["config", "cargar", ruta, "--instante", "2026-11-01T00:00:00Z"], repo, _sin_reloj
    )
    assert json.loads(primero[1])["created"] is True
    assert json.loads(segundo[1])["created"] is False
    assert json.loads(primero[1])["configVersionId"] == json.loads(segundo[1])["configVersionId"]


# =========================================================================================
# DEC-279: columna recordType en un CSV
# =========================================================================================


@pytest.mark.parametrize("valor", ["local_demand", " local_demand ", "\tlocal_demand"])
def test_dec_279_columna_igual_al_nombre_se_acepta(valor):
    contenido = csv_bytes("recordType,category,level,date", f"{valor},tools,low,2026-11-18")
    reporte, repo, _ = correr("local_demand.csv", contenido)
    assert (reporte.cargados, reporte.rechazados) == (1, 0)
    (guardada,) = repo.capturas(TipoRegistro.LOCAL_DEMAND, instante=INSTANTE)
    # Se descarta: no queda como dato de la captura.
    assert "recordType" not in json.dumps(guardada.captura.model_dump(mode="json"))


@pytest.mark.parametrize("valor", ["msrp", "observation", "", "   ", "desconocido"])
def test_dec_279_columna_distinta_o_vacia_rechaza_ese_renglon(valor):
    contenido = csv_bytes(
        "category,recordType,level,date",
        f"tools,{valor},low,2026-11-18",
        "beauty,local_demand,high,2026-11-18",
    )
    reporte, _, ids = correr("local_demand__semana.csv", contenido)
    assert rechazos(reporte) == [(2, TIPO_DESCONOCIDO)]
    assert reporte.cargados == 1
    # El tipo del archivo sigue saliendo del nombre (CTR-03).
    assert reporte.tipo_registro is TipoRegistro.LOCAL_DEMAND


def test_dec_279_celda_faltante_en_un_renglon_corto():
    contenido = csv_bytes("category,level,date,recordType", "tools,low,2026-11-18")
    reporte, _, _ = correr("local_demand.csv", contenido)
    assert rechazos(reporte) == [(2, TIPO_DESCONOCIDO)]


def test_dec_279_sin_columna_no_cambia():
    reporte, _, _ = correr(
        "local_demand.csv", csv_bytes("category,level,date", "tools,low,2026-11-18")
    )
    assert (reporte.cargados, reporte.rechazados) == (1, 0)


def test_dec_279_observacion_csv_con_otra_columna_solo_queda_en_el_reporte():
    # design.md §2: un renglón con tipo desconocido solo queda en el reporte (B34 c).
    contenido = csv_bytes(
        "recordType,schemaVersion,retailerCode,productUrl,title,category,price.current,"
        "price.currency,seller,condition,availability.state,purchaseMode,extractedAt,blocked",
        f"msrp,3.1,{TIENDA_PRUEBA},https://{DOMINIO_PRUEBA}/p/t1,Sintetico,tools,10.00,USD,"
        "comercio,new,in_stock,envio,2026-11-17T09:00:00-08:00,false",
    )
    reporte, repo, ids = correr("observation.csv", contenido)
    assert rechazos(reporte) == [(2, TIPO_DESCONOCIDO)]
    assert registros_rechazo(repo, ids) == []


# =========================================================================================
# DEC-280: extractedAt que no cabe en la zona de general.timezone
# =========================================================================================

_ENCABEZADO_OBS = (
    "schemaVersion,retailerCode,productUrl,title,category,price.current,price.currency,"
    "seller,condition,availability.state,purchaseMode,extractedAt,blocked"
)


def _renglon_obs(ruta: str, extraida: str) -> str:
    return (
        f"3.1,{TIENDA_PRUEBA},https://{DOMINIO_PRUEBA}{ruta},Sintetico,tools,10.00,USD,"
        f"comercio,new,in_stock,envio,{extraida},false"
    )


def test_dec_280_validar_con_tijuana():
    v = validar(comercio(extractedAt=FUERA_DE_ZONA), CONFIG.contenido)
    assert v.motivo_rechazo == faltante("extractedAt")


def test_dec_280_por_json_lines_carga_completa_y_reporte(caplog):
    caplog.set_level(logging.DEBUG)
    contenido = jsonl(
        {"recordType": "observation", **comercio(productUrl=f"https://{DOMINIO_PRUEBA}/p/a")},
        {"recordType": "observation", **comercio(extractedAt=FUERA_DE_ZONA)},
        {"recordType": "observation", **comercio(productUrl=f"https://{DOMINIO_PRUEBA}/p/c")},
    )
    reporte, repo, ids = correr("o.jsonl", contenido)
    assert rechazos(reporte) == [(2, faltante("extractedAt"))]
    assert (reporte.cargados, reporte.rechazados, reporte.duplicados) == (2, 1, 0)
    assert reporte.a_json()["rejections"] == [
        {"line": 2, "recordType": "observation", "reason": faltante("extractedAt")}
    ]
    registros = registros_rechazo(repo, ids)
    assert [(r.renglon, r.motivo_rechazo) for r in registros] == [(2, faltante("extractedAt"))]
    assert registros[0].id_carga == reporte.id_carga
    assert FUERA_DE_ZONA not in caplog.text


def test_dec_280_por_csv_carga_completa_y_reporte():
    contenido = csv_bytes(
        _ENCABEZADO_OBS,
        _renglon_obs("/p/a", FUERA_DE_ZONA),
        _renglon_obs("/p/b", "2026-11-17T09:00:00-08:00"),
    )
    reporte, repo, ids = correr("observation.csv", contenido)
    assert rechazos(reporte) == [(2, faltante("extractedAt"))]
    assert reporte.cargados == 1
    assert [(r.renglon, r.motivo_rechazo) for r in registros_rechazo(repo, ids)] == [
        (2, faltante("extractedAt"))
    ]


def test_dec_280_va_antes_que_precio_y_dominio():
    datos = comercio(
        extractedAt=FUERA_DE_ZONA,
        price={"current": "0.00", "currency": "USD"},
        productUrl="https://otro-dominio.example.net/p/x",
    )
    assert validar(datos, CONFIG.contenido).motivo_rechazo == faltante("extractedAt")


def test_dec_280_un_dia_despues_si_cabe():
    # 0001-01-02T00:00Z en Tijuana es el 1 de enero del año 1: cabe.
    assert (
        validar(comercio(extractedAt="0001-01-02T00:00:00Z"), CONFIG.contenido).motivo_rechazo
        is None
    )


def test_dec_280_la_zona_sale_de_la_configuracion():
    # DEC-240 y DEC-247: la zona llega por parámetro. En Tokio (UTC+9) el valor de DEC-280
    # cabe; el extremo superior no.
    tokio = _config_con_zona("Asia/Tokyo")
    assert validar(comercio(extractedAt=FUERA_DE_ZONA), tokio.contenido).motivo_rechazo is None
    fin = comercio(extractedAt="9999-12-31T20:00:00Z")
    assert validar(fin, tokio.contenido).motivo_rechazo == faltante("extractedAt")
    assert validar(fin, CONFIG.contenido).motivo_rechazo is None
