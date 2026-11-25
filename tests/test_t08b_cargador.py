"""Pruebas de T08b: cargador de archivos JSON Lines y CSV con su reporte (CMP-08, CMP-22).

Escenarios B34 (b) y B34 (c) de REQ-2026-0001 v2.9 por el cargador con
``RepositorioMemoria`` (design.md §12), más las pruebas unitarias de carga de §12 (archivo
vacío, renglón que no es JSON, CSV sin tipo en el nombre, celdas vacías, listas con ``|``,
duplicados), la clave de idempotencia (DEC-255), la URL canónica y el prefijo de ruta
normalizado (DEC-256), ``captured_at`` = instante de la carga (DEC-271), el origen de cada
rechazo (decisión 33 del #34) y los puntos 8 y 9 del comentario 7069378959 del #34
(DEC-274).

Fixtures sintéticos (``tests/fixtures/archivos/`` y archivos armados aquí); las URL de
comercio son de example.com (``tienda-prueba``) y los dominios de las plataformas salen de
la configuración. Ninguna prueba abre una URL; el instante siempre es explícito.
"""

from __future__ import annotations

import copy
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
    DOMINIO_PRUEBA,
    TIENDA_PRUEBA,
    configuracion_con_sucursales_prueba,
)
from oip import cli
from oip.catalogos import Identificacion, Resultado, TipoRegistro
from oip.entradas import cargador as modulo_cargador
from oip.entradas.cargador import (
    ErrorDeArchivo,
    cargar,
    cargar_archivo,
    clave_idempotencia,
    dia_de_carga,
    huella_captura,
)
from oip.entradas.contrato import leer_observacion
from oip.entradas.validacion import ruta_normalizada, url_autorizada, url_canonica, validar
from oip.persistencia.repositorios import RegistroRechazo, RepositorioMemoria

RAIZ = Path(__file__).parent
FIXTURES = RAIZ / "fixtures"
ARCHIVOS = FIXTURES / "archivos"
CONFIG = configuracion_con_sucursales_prueba()
CONTENIDO = CONFIG.contenido

#: Instante de la carga: 2026-11-18 10:00 en Tijuana (PAR-01).
INSTANTE = dt.datetime(2026, 11, 18, 18, 0, tzinfo=dt.UTC)
CONFIG_EN = dt.datetime(2026, 11, 1, tzinfo=dt.UTC)

TIPO_DESCONOCIDO = "TIPO DE REGISTRO DESCONOCIDO"
PRECIO_INVALIDO = "PRECIO INVÁLIDO"
DOMINIO_NO_AUTORIZADO = "DOMINIO NO AUTORIZADO"
CIUDAD_NO_CONFIGURADA = "CIUDAD NO CONFIGURADA"


def _faltante(campo: str) -> str:
    return f"CAMPO OBLIGATORIO FALTANTE ({campo})"


class Ids:
    """Identificadores deterministas (``UUID(int=n)``), con registro de los que dio."""

    def __init__(self, inicio: int = 1) -> None:
        self.siguiente = inicio
        self.dados: list[UUID] = []

    def __call__(self) -> UUID:
        nuevo = UUID(int=self.siguiente)
        self.siguiente += 1
        self.dados.append(nuevo)
        return nuevo


class Espia:
    """Repositorio en memoria que registra cada llamada que escribe (una por registro)."""

    def __init__(self) -> None:
        self.repo = RepositorioMemoria()
        self.llamadas: list[tuple[str, tuple[Any, ...]]] = []

    def __getattr__(self, nombre: str) -> Any:
        metodo = getattr(self.repo, nombre)
        if not nombre.startswith(("guardar_", "iniciar_", "terminar_")):
            return metodo

        def envuelto(*args: Any, **kwargs: Any) -> Any:
            self.llamadas.append((nombre, args))
            return metodo(*args, **kwargs)

        return envuelto


@pytest.fixture
def repo():
    return RepositorioMemoria()


def _version(repo):
    version, _ = repo.guardar_version_configuracion(CONFIG, cargada_en=CONFIG_EN)
    return version


def _jsonl(*renglones: dict[str, Any] | str) -> bytes:
    lineas = [r if isinstance(r, str) else json.dumps(r, ensure_ascii=False) for r in renglones]
    return ("\n".join(lineas) + "\n").encode("utf-8")


def _cargar(repo, nombre, contenido, instante=INSTANTE, ids=None):
    return cargar(nombre, contenido, repo, _version(repo), instante, nuevo_id=ids or Ids())


def _b18() -> dict[str, Any]:
    texto = (FIXTURES / "observaciones" / "b18_particular.json").read_text(encoding="utf-8")
    datos = json.loads(texto, parse_float=Decimal)
    datos.pop("_nota")
    return datos


def _comercio(**cambios: Any) -> dict[str, Any]:
    """Observación sintética de ``tienda-prueba`` (example.com), válida."""
    datos: dict[str, Any] = {
        "schemaVersion": "3.1",
        "retailerCode": TIENDA_PRUEBA,
        "productUrl": f"https://www.{DOMINIO_PRUEBA}/p/sintetico-1",
        "title": "Producto sintético",
        "brand": "MARCA-SINTETICA",
        "model": "MS-100",
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


def _obs(datos: dict[str, Any]) -> dict[str, Any]:
    return {"recordType": "observation", **datos}


def _demanda(fecha: str = "2026-11-18", **cambios: Any) -> dict[str, Any]:
    return {
        "recordType": "local_demand",
        "category": "beauty",
        "level": "medium",
        "date": fecha,
        **cambios,
    }


def _rechazos(reporte) -> list[tuple[int, str]]:
    return [(r.renglon, r.motivo) for r in reporte.rechazos]


# --- Escenarios B34 (b) y B34 (c) ---------------------------------------------------------


@pytest.mark.scenario("B34 (b)")
def test_b34_b_csv_de_local_comparable_con_un_renglon_sin_estado(repo):
    version = _version(repo)
    ids = Ids()
    # Dado: los comparables de B18 ya están cargados.
    previo = cargar_archivo(
        ARCHIVOS / "local_comparable__b18.csv", repo, version, INSTANTE, nuevo_id=ids
    )
    assert (previo.cargados, previo.rechazados) == (3, 0)

    reporte = cargar_archivo(
        ARCHIVOS / "local_comparable__b34b.csv", repo, version, INSTANTE, nuevo_id=ids
    )

    assert reporte.formato == "csv" and reporte.tipo_registro is TipoRegistro.LOCAL_COMPARABLE
    assert (reporte.cargados, reporte.rechazados, reporte.duplicados) == (3, 1, 0)
    assert _rechazos(reporte) == [(5, _faltante("condition"))]
    assert reporte.rechazados_por_motivo == {_faltante("condition"): 1}
    assert reporte.a_json()["rejections"] == [
        {"line": 5, "recordType": "local_comparable", "reason": _faltante("condition")}
    ]
    guardados = repo.capturas(TipoRegistro.LOCAL_COMPARABLE, instante=INSTANTE)
    assert len(guardados) == 6
    nuevos = [g for g in guardados if g.id_carga == reporte.id_carga]
    assert [g.captura.asking_price for g in nuevos] == [
        Decimal("80.00"),
        Decimal("85.50"),
        Decimal("90.00"),
    ]
    # El reporte guardado (TAB-02) dice lo mismo.
    guardada = repo.leer_carga(reporte.id_carga)
    assert (guardada.reporte.cargados, guardada.reporte.rechazados) == (3, 1)
    assert guardada.reporte.rechazados_por_motivo == {_faltante("condition"): 1}
    assert [(r.renglon, r.motivo, r.campo) for r in guardada.rechazos] == [
        (5, _faltante("condition"), "condition")
    ]


@pytest.mark.scenario("B34 (c)")
def test_b34_c_observaciones_del_vps_con_un_renglon_sin_record_type(repo):
    reporte = cargar_archivo(
        ARCHIVOS / "b34c_vps.jsonl", repo, _version(repo), INSTANTE, nuevo_id=Ids()
    )

    assert reporte.formato == "jsonl" and reporte.tipo_registro is None
    assert (reporte.cargados, reporte.rechazados, reporte.duplicados) == (1, 1, 0)
    assert _rechazos(reporte) == [(2, TIPO_DESCONOCIDO)]
    assert reporte.a_json()["rejections"] == [
        {"line": 2, "recordType": None, "reason": TIPO_DESCONOCIDO}
    ]
    assert reporte.rechazados_por_motivo == {TIPO_DESCONOCIDO: 1}
    guardada = repo.leer_carga(reporte.id_carga)
    assert (guardada.reporte.cargados, guardada.reporte.rechazados) == (1, 1)
    # El renglón sin recordType solo queda en el reporte (design.md §2): sin tipo y sin
    # registro RECHAZADA_VALIDACION.
    assert [(r.renglon, r.tipo_registro) for r in guardada.rechazos] == [(2, None)]


# --- Formato del reporte (CTR-05) ----------------------------------------------------------


def test_el_reporte_tiene_los_campos_de_ctr_05(repo):
    reporte = _cargar(repo, "mezcla.jsonl", _jsonl(_demanda(), {"recordType": "coupon"}))
    assert list(reporte.a_json()) == [
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
    ]
    assert reporte.a_json()["fileName"] == "mezcla.jsonl"
    assert reporte.a_json()["rejections"] == [
        {"line": 2, "recordType": None, "reason": TIPO_DESCONOCIDO}
    ]
    json.dumps(reporte.a_json())  # serializable tal cual


# --- Unitarias de carga de design.md §12 ---------------------------------------------------


@pytest.mark.parametrize(("nombre", "contenido"), [("vacio.jsonl", b""), ("msrp.csv", b"")])
def test_archivo_vacio_deja_un_reporte_en_cero(repo, nombre, contenido):
    reporte = _cargar(repo, nombre, contenido)
    assert (reporte.cargados, reporte.rechazados, reporte.duplicados) == (0, 0, 0)
    assert reporte.rechazos == () and reporte.rechazados_por_motivo == {}
    guardada = repo.leer_carga(reporte.id_carga)
    assert guardada.reporte is not None and guardada.reporte.cargados == 0


def test_csv_solo_con_encabezado_y_renglones_en_blanco(repo):
    reporte = _cargar(repo, "local_demand.csv", b"category,level,date\n\n\n")
    assert (reporte.cargados, reporte.rechazados) == (0, 0)


def test_renglones_en_blanco_no_son_registros_pero_cuentan_en_la_numeracion(repo):
    contenido = _jsonl(_demanda(), "", "   ", {"recordType": "coupon"})
    reporte = _cargar(repo, "a.jsonl", contenido)
    assert reporte.cargados == 1
    assert _rechazos(reporte) == [(4, TIPO_DESCONOCIDO)]


@pytest.mark.parametrize(
    "renglon",
    [
        "esto no es JSON",
        '{"recordType": "local_demand", "category": ',
        '["recordType", "local_demand"]',
        '"local_demand"',
        "42",
        "null",
        '{"recordType": "local_demand", "category": "beauty", "level": "medium", '
        '"date": "2026-11-18", "x": NaN}',
        '{"recordType": "local_demand", "x": Infinity}',
    ],
)
def test_renglon_que_no_es_un_objeto_json_se_rechaza_sin_detener_la_carga(repo, renglon):
    reporte = _cargar(repo, "a.jsonl", _jsonl(_demanda(), renglon, _demanda("2026-11-17")))
    assert reporte.cargados == 2
    assert _rechazos(reporte) == [(2, TIPO_DESCONOCIDO)]


def test_renglon_que_no_es_utf8_se_rechaza(repo):
    contenido = _jsonl(_demanda()) + b'{"recordType": "\xff"}\n' + _jsonl(_demanda("2026-11-17"))
    reporte = _cargar(repo, "a.jsonl", contenido)
    assert reporte.cargados == 2 and _rechazos(reporte) == [(2, TIPO_DESCONOCIDO)]


def test_bom_y_fin_de_renglon_crlf(repo):
    contenido = b"\xef\xbb\xbf" + _jsonl(_demanda(), _demanda("2026-11-17")).replace(b"\n", b"\r\n")
    reporte = _cargar(repo, "a.jsonl", contenido)
    assert (reporte.cargados, reporte.rechazados) == (2, 0)


@pytest.mark.parametrize(
    "valor", [None, "", "   ", "coupon", "OBSERVATION", 3, True, ["observation"], {"a": 1}]
)
def test_record_type_ausente_vacio_o_desconocido(repo, valor):
    renglon = _demanda()
    if valor is None:
        renglon.pop("recordType")
    else:
        renglon["recordType"] = valor
    reporte = _cargar(repo, "a.jsonl", _jsonl(renglon))
    assert _rechazos(reporte) == [(1, TIPO_DESCONOCIDO)]
    assert reporte.rechazos[0].tipo_registro is None


def test_record_type_se_quita_antes_de_validar_y_admite_tipos_mezclados(repo):
    ids = Ids()
    contenido = _jsonl(
        _obs(_comercio()),
        _demanda(),
        {
            "recordType": " msrp ",
            "brand": "M",
            "model": "X",
            "value": "10.00",
            "source": "caja",
            "date": "2026-11-10",
        },
    )
    reporte = _cargar(repo, "mezcla.jsonl", contenido, ids=ids)
    assert (reporte.cargados, reporte.rechazados) == (3, 0)


@pytest.mark.parametrize(
    "nombre",
    ["capturas.csv", "coupon.csv", "local_comparable-2026.csv", "LOCAL_DEMAND.csv", "__msrp.csv"],
)
def test_csv_con_nombre_sin_tipo_rechaza_cada_renglon(repo, nombre):
    contenido = b"category,level,date\nbeauty,medium,2026-11-18\nbeauty,low,2026-11-17\n"
    reporte = _cargar(repo, nombre, contenido)
    assert reporte.tipo_registro is None and reporte.a_json()["recordType"] is None
    assert reporte.cargados == 0
    assert _rechazos(reporte) == [(2, TIPO_DESCONOCIDO), (3, TIPO_DESCONOCIDO)]
    assert repo.leer_carga(reporte.id_carga).carga.tipo_registro is None


@pytest.mark.parametrize("nombre", ["local_demand.csv", "local_demand__2026-11-18.csv"])
def test_el_tipo_del_csv_sale_del_nombre(repo, nombre):
    contenido = b"recordType,category,level,date\ncoupon,beauty,medium,2026-11-18\n"
    reporte = _cargar(repo, nombre, contenido)
    # La columna recordType se descarta: manda el nombre (CTR-03).
    assert reporte.tipo_registro is TipoRegistro.LOCAL_DEMAND
    assert (reporte.cargados, reporte.rechazados) == (1, 0)


def test_celdas_vacias_son_campos_ausentes(repo):
    contenido = (
        b"gtin,brand,model,condition,askingPrice,currency,exchangeRate,city,date,sold\n"
        b",M,X,new,10.00,USD,,san_diego,2026-11-10,false\n"  # exchangeRate vacío en USD: vale
        b",M,X,new,10.00,MXN,  ,san_diego,2026-11-10,false\n"  # vacío en MXN: falta
        b",M,X,new,10.00,USD,,san_diego,,false\n"
        b",,,new,10.00,USD,,san_diego,2026-11-10,false\n"
        b",M,X,new,10.00,USD,,san_diego,2026-11-10,\n"
    )
    reporte = _cargar(repo, "local_comparable.csv", contenido)
    assert reporte.cargados == 1
    assert _rechazos(reporte) == [
        (3, _faltante("exchangeRate")),
        (4, _faltante("date")),
        (5, _faltante("gtin")),
        (6, _faltante("sold")),
    ]


def test_csv_con_menos_celdas_que_el_encabezado_y_celdas_de_mas(repo):
    contenido = b"category,level,date\nbeauty,medium\nbeauty,medium,2026-11-18,extra,otra\n"
    reporte = _cargar(repo, "local_demand.csv", contenido)
    assert reporte.cargados == 1 and _rechazos(reporte) == [(2, _faltante("date"))]


def test_listas_con_barra_vertical_en_csv(repo):
    contenido = (
        b"clientAlias,items,quantity,acceptedConditions,modality,date\n"
        b"alias-1,MS-1|MS-2 | MS-3,2,new|open_box,link_only,2026-11-18\n"
        b"alias-2,MS-1,1,,buy_and_deliver,2026-11-18\n"
        b"alias-3,MS-1|MS-2|MS-3|MS-4,1,,link_only,2026-11-18\n"
        b"alias-4,MS-1||MS-3,1,,link_only,2026-11-18\n"
    )
    reporte = _cargar(repo, "client_request.csv", contenido)
    assert reporte.cargados == 2
    assert _rechazos(reporte) == [(4, _faltante("items")), (5, _faltante("items"))]
    guardadas = repo.capturas(TipoRegistro.CLIENT_REQUEST, instante=INSTANTE)
    assert guardadas[0].captura.items == ("MS-1", "MS-2", "MS-3")
    assert [c.value for c in guardadas[0].captura.accepted_conditions] == ["new", "open_box"]
    # acceptedConditions vacío vale [new] (DEC-241).
    assert [c.value for c in guardadas[1].captura.accepted_conditions] == ["new"]


def test_csv_de_observaciones_con_campos_anidados(repo):
    contenido = (
        "retailerCode,productUrl,title,category,price.current,price.was,seller,"
        "availability.state,availability.quantity,availability.addToCart,purchaseMode,"
        "extractedAt,blocked\n"
        f"{TIENDA_PRUEBA},https://{DOMINIO_PRUEBA}/p/1,Producto,tools,49.99,79.99,comercio,"
        "in_stock,3,true,envio,2026-11-17T10:00:00-08:00,false\n"
    ).encode()
    ids = Ids()
    reporte = _cargar(repo, "observation__vps.csv", contenido, ids=ids)
    assert (reporte.cargados, reporte.rechazados) == (1, 0)
    guardada = next(o for i in ids.dados if (o := repo.leer_observacion(i)) is not None).observacion
    assert guardada.price.current == Decimal("49.99") and guardada.price.was == Decimal("79.99")
    assert guardada.availability.quantity == 3 and guardada.availability.add_to_cart is True


# --- Tipos estrictos en CSV (DEC-238) -------------------------------------------------------

_CABECERA_RESULTADO = (
    "evaluationId,channel,units,purchasePrice,salePrice,actualCosts,purchasedOn,soldOn\n"
)


@pytest.mark.parametrize(
    ("units", "esperado"),
    [("3", 3), (" 3 ", 3), ("1", 1)],
)
def test_csv_convierte_el_entero_exacto(repo, units, esperado):
    contenido = (
        _CABECERA_RESULTADO
        + f"{UUID(int=99)},amazon,{units},10.00,20.00,1.00,2026-11-01,2026-11-10\n"
    ).encode()
    reporte = _cargar(repo, "actual_result.csv", contenido)
    assert reporte.cargados == 1
    guardada = repo.capturas(TipoRegistro.ACTUAL_RESULT, instante=INSTANTE)[0]
    assert guardada.captura.units == esperado and type(guardada.captura.units) is int


@pytest.mark.parametrize("units", ["03", "3.0", "1e1", "+3", "tres", "true", "٣", "3 4"])
def test_csv_un_entero_que_no_se_convierte_llega_como_texto_y_se_rechaza(repo, units):
    contenido = (
        _CABECERA_RESULTADO
        + f"{UUID(int=99)},amazon,{units},10.00,20.00,1.00,2026-11-01,2026-11-10\n"
    ).encode()
    reporte = _cargar(repo, "actual_result.csv", contenido)
    assert _rechazos(reporte) == [(2, _faltante("units"))]


@pytest.mark.parametrize(("sold", "esperado"), [("true", True), ("false", False), (" true ", True)])
def test_csv_convierte_el_booleano_exacto(repo, sold, esperado):
    contenido = (
        "brand,model,condition,askingPrice,currency,city,date,sold\n"
        f"M,X,new,10.00,USD,san_diego,2026-11-10,{sold}\n"
    ).encode()
    reporte = _cargar(repo, "local_comparable.csv", contenido)
    assert reporte.cargados == 1
    guardada = repo.capturas(TipoRegistro.LOCAL_COMPARABLE, instante=INSTANTE)[0]
    assert guardada.captura.sold is esperado


@pytest.mark.parametrize("sold", ["TRUE", "True", "1", "0", "yes", "sí", "f"])
def test_csv_un_booleano_que_no_se_convierte_se_rechaza(repo, sold):
    contenido = (
        "brand,model,condition,askingPrice,currency,city,date,sold\n"
        f"M,X,new,10.00,USD,san_diego,2026-11-10,{sold}\n"
    ).encode()
    reporte = _cargar(repo, "local_comparable.csv", contenido)
    assert _rechazos(reporte) == [(2, _faltante("sold"))]


def test_json_lines_no_convierte_texto_a_entero_ni_a_booleano(repo):
    renglon = {
        "recordType": "local_comparable",
        "brand": "M",
        "model": "X",
        "condition": "new",
        "askingPrice": "10.00",
        "currency": "USD",
        "city": "san_diego",
        "date": "2026-11-10",
        "sold": "false",
    }
    reporte = _cargar(repo, "a.jsonl", _jsonl(renglon))
    assert _rechazos(reporte) == [(1, _faltante("sold"))]


# --- Dinero sin float -------------------------------------------------------------------------


def test_los_numeros_del_json_se_leen_como_decimal(repo, monkeypatch):
    ids = Ids()
    datos = _comercio()
    texto = json.dumps(_obs(datos)).replace('"49.99"', "70.10")
    reporte = _cargar(repo, "a.jsonl", (texto + "\n").encode(), ids=ids)
    assert reporte.cargados == 1
    guardada = next(o for i in ids.dados if (o := repo.leer_observacion(i)) is not None)
    precio = guardada.observacion.price.current
    assert type(precio) is Decimal and precio == Decimal("70.10")


def test_el_csv_lee_los_montos_como_decimal_desde_el_texto(repo):
    contenido = (
        b"brand,model,condition,askingPrice,currency,exchangeRate,city,date,sold\n"
        b"M,X,new,1000.10,MXN,17.3,san_diego,2026-11-10,false\n"
    )
    _cargar(repo, "local_comparable.csv", contenido)
    guardada = repo.capturas(TipoRegistro.LOCAL_COMPARABLE, instante=INSTANTE)[0].captura
    assert guardada.asking_price == Decimal("1000.10")
    # Sin redondear (S-23): el cargador no redondea.
    assert guardada.price_usd == Decimal("1000.10") / Decimal("17.3")


# --- Duplicados e idempotencia (design.md §5; DEC-255) -----------------------------------------


def test_duplicados_se_cuentan_y_no_se_guardan_dos_veces(repo):
    ids = Ids()
    contenido = _jsonl(_obs(_comercio()), _demanda(), _obs(_comercio()), _demanda())
    reporte = _cargar(repo, "a.jsonl", contenido, ids=ids)
    assert (reporte.cargados, reporte.rechazados, reporte.duplicados) == (2, 0, 2)
    assert repo.leer_carga(reporte.id_carga).reporte.duplicados == 2
    assert len(repo.capturas(TipoRegistro.LOCAL_DEMAND, instante=INSTANTE)) == 1
    # Cargar el mismo archivo otra vez: todo es duplicado.
    otra = cargar("a.jsonl", contenido, repo, _version(repo), INSTANTE, nuevo_id=ids)
    assert (otra.cargados, otra.rechazados, otra.duplicados) == (0, 0, 4)
    assert len(repo.capturas(TipoRegistro.LOCAL_DEMAND, instante=INSTANTE)) == 1


def test_una_captura_con_el_mismo_valor_escrito_distinto_es_duplicado(repo):
    contenido = (
        b"brand,model,condition,askingPrice,currency,city,date,sold\n"
        b"M,X,new,10.5,USD,san_diego,2026-11-10,false\n"
        b"M,X,new,10.50,USD,san_diego,2026-11-10,false\n"
        b"M,X,new,10.51,USD,san_diego,2026-11-10,false\n"
    )
    reporte = _cargar(repo, "local_comparable.csv", contenido)
    assert (reporte.cargados, reporte.duplicados) == (2, 1)


def test_huella_de_captura_estable_y_sin_contenido():
    datos = {
        "clientAlias": "CENTINELA-T08B",
        "items": ["MS-1"],
        "quantity": 1,
        "modality": "link_only",
        "date": "2026-11-18",
    }
    from oip.entradas.capturas import leer_captura

    uno = leer_captura("client_request", datos)
    dos = leer_captura("client_request", {**datos, "acceptedConditions": ["new"], "x": "y"})
    huella = huella_captura(TipoRegistro.CLIENT_REQUEST, uno)
    assert huella == huella_captura(TipoRegistro.CLIENT_REQUEST, dos)
    assert len(huella) == 64 and "CENTINELA" not in huella
    with pytest.raises(TypeError):
        huella_captura(TipoRegistro.MSRP, uno)


def test_clave_de_idempotencia_sin_idempotency_key():
    datos = _comercio(
        productUrl="https://WWW.Example.com/p/sintetico-1/#arriba",
        extractedAt="2026-11-17T10:00:42-08:00",
    )
    observacion = leer_observacion(datos)
    assert clave_idempotencia(observacion) == (
        f"{TIENDA_PRUEBA}|https://{DOMINIO_PRUEBA}/p/sintetico-1||2026-11-17T18:00"
    )
    con_tienda = leer_observacion({**datos, "storeCode": "tp-cv"})
    assert clave_idempotencia(con_tienda) == (
        f"{TIENDA_PRUEBA}|https://{DOMINIO_PRUEBA}/p/sintetico-1|tp-cv|2026-11-17T18:00"
    )


def test_clave_de_idempotencia_con_idempotency_key_tal_cual():
    observacion = leer_observacion(_comercio(idempotencyKey="clave-del-worker|1"))
    assert clave_idempotencia(observacion) == "clave-del-worker|1"


@pytest.mark.parametrize(
    ("hora", "otra", "duplicado"),
    [
        ("2026-11-17T10:00:00-08:00", "2026-11-17T10:00:59-08:00", True),
        ("2026-11-17T10:00:59-08:00", "2026-11-17T18:00:01Z", True),
        ("2026-11-17T10:00:59-08:00", "2026-11-17T10:01:00-08:00", False),
        ("2026-11-17T23:59:30-08:00", "2026-11-18T07:59:00Z", True),
    ],
)
def test_extracted_at_en_utc_truncado_al_minuto(repo, hora, otra, duplicado):
    contenido = _jsonl(_obs(_comercio(extractedAt=hora)), _obs(_comercio(extractedAt=otra)))
    reporte = _cargar(repo, "a.jsonl", contenido)
    assert reporte.duplicados == (1 if duplicado else 0)
    assert reporte.cargados == (1 if duplicado else 2)


def test_la_misma_url_escrita_distinto_es_la_misma_publicacion(repo):
    contenido = _jsonl(
        _obs(_comercio(productUrl=f"https://www.{DOMINIO_PRUEBA}/p/sintetico-1/")),
        _obs(_comercio(productUrl=f"http://{DOMINIO_PRUEBA.upper()}/p/x/../sintetico-1#a")),
    )
    reporte = _cargar(repo, "a.jsonl", contenido)
    assert (reporte.cargados, reporte.duplicados) == (1, 1)
    publicacion = repo.buscar_publicacion(
        TIENDA_PRUEBA, f"https://{DOMINIO_PRUEBA}/p/sintetico-1", None
    )
    assert publicacion is not None


# --- URL canónica y prefijo de ruta normalizado (DEC-256) -------------------------------------


@pytest.mark.parametrize(
    ("url", "canonica"),
    [
        ("https://example.com/p/1", "https://example.com/p/1"),
        ("http://example.com/p/1", "https://example.com/p/1"),
        ("https://WWW.EXAMPLE.COM/p/1", "https://example.com/p/1"),
        ("https://www.www.example.com/p/1", "https://www.example.com/p/1"),
        ("https://tienda.example.com/p/1", "https://tienda.example.com/p/1"),
        ("https://example.com/p/1/", "https://example.com/p/1"),
        ("https://example.com/p/1#reseñas", "https://example.com/p/1"),
        ("https://example.com/p/1?b=2&a=1#x", "https://example.com/p/1?b=2&a=1"),
        ("https://example.com/p/./x/../1", "https://example.com/p/1"),
        ("https://example.com/p/%2e%2e/q/%2E/1", "https://example.com/q/1"),
        ("https://example.com/../../p/1", "https://example.com/p/1"),
        ("https://example.com/p/a%2eb/P", "https://example.com/p/a%2eb/P"),
        ("https://example.com/", "https://example.com"),
        ("https://example.com", "https://example.com"),
        ("https://example.com/p/1/..", "https://example.com/p"),
    ],
)
def test_url_canonica(url, canonica):
    assert url_canonica(url) == canonica


@pytest.mark.parametrize(
    "url", ["", "notaurl", "https://user@example.com/p", "https://example.com:8443/p", "a b"]
)
def test_url_canonica_rechaza_formas_dudosas_sin_la_url(url):
    with pytest.raises(ValueError) as error:
        url_canonica(url)
    assert url not in str(error.value) or not url


@pytest.mark.parametrize(
    ("ruta", "normalizada"),
    [
        ("/marketplace/item/1", "/marketplace/item/1"),
        ("/marketplace/../groups/1", "/groups/1"),
        ("/marketplace/%2e%2e/groups/1", "/groups/1"),
        ("/marketplace/%2E%2e/groups", "/groups"),
        ("/marketplace/./item/", "/marketplace/item"),
        ("/marketplace/.%2e/../x", "/x"),
        ("", ""),
        ("/", ""),
    ],
)
def test_ruta_normalizada(ruta, normalizada):
    assert ruta_normalizada(ruta) == normalizada


@pytest.mark.parametrize(
    ("url", "esperado"),
    [
        ("https://example.com/marketplace/item/1", True),
        ("https://example.com/marketplace/x/../item/1", True),
        ("https://example.com/marketplace/../groups/1", False),
        ("https://example.com/marketplace/%2e%2e/groups/1", False),
        ("https://example.com/marketplace/%2E%2E/groups/1", False),
        ("https://example.com/marketplace/..", False),
        ("https://example.com/marketplace/%2e%2e", False),
        ("https://example.com/groups/../marketplace/item/1", True),
    ],
)
def test_prefijo_de_ruta_sobre_la_ruta_normalizada(url, esperado):
    resultado = url_autorizada(
        url, ("example.com",), esquemas=("https",), prefijo_ruta="/marketplace"
    )
    assert resultado is esperado


def _plataforma_con_prefijo():
    con_prefijo = [p for p in CONTENIDO.private_sellers.platforms.values() if p.path_prefix]
    assert con_prefijo
    return con_prefijo[0]


@pytest.mark.parametrize("salto", ["..", "%2e%2e", "%2E%2E", ".%2e"])
def test_particular_que_sale_del_prefijo_da_dominio_no_autorizado_de_punta_a_punta(repo, salto):
    plataforma = _plataforma_con_prefijo()
    dominio = plataforma.domains[0]
    fuera = f"https://www.{dominio}{plataforma.path_prefix}/{salto}/groups/1"
    dentro = f"https://www.{dominio}{plataforma.path_prefix}/item/1"
    assert validar({**_b18(), "productUrl": fuera}, CONTENIDO).motivo_rechazo == (
        DOMINIO_NO_AUTORIZADO
    )
    contenido = _jsonl(
        _obs({**_b18(), "productUrl": fuera}), _obs({**_b18(), "productUrl": dentro})
    )
    reporte = _cargar(repo, "a.jsonl", contenido)
    assert _rechazos(reporte) == [(1, DOMINIO_NO_AUTORIZADO)]
    assert reporte.cargados == 1


def test_la_publicacion_de_un_particular_guarda_plataforma_y_ciudad(repo):
    _cargar(repo, "a.jsonl", _jsonl(_obs(_b18())))
    datos = _b18()
    url = url_canonica(datos["productUrl"])
    publicacion = repo.buscar_publicacion("particular", url, None)
    assert publicacion is not None
    assert publicacion.plataforma in CONTENIDO.private_sellers.platforms
    assert publicacion.ciudad_recogida == "san_diego"


# --- captured_at = instante de la carga (DEC-271) y reproducción --------------------------------


def _archivo_de_capturas() -> bytes:
    return _jsonl(
        _demanda(),
        {
            "recordType": "msrp",
            "brand": "M",
            "model": "X",
            "value": "199.99",
            "source": "caja",
            "date": "2026-11-01",
        },
        {"recordType": "coupon"},
        {
            "recordType": "store_visit",
            "storeCode": "tp-cv",
            "brand": "M",
            "model": "X",
            "result": "found",
            "visitedAt": "2026-11-18T09:15:00",
        },
        _obs(_comercio()),
        _obs(_comercio(price={"current": "0", "currency": "USD"})),
    )


def test_captured_at_es_el_instante_de_la_carga(repo):
    reporte = _cargar(repo, "a.jsonl", _archivo_de_capturas())
    assert reporte.cargados == 4
    for tipo in (TipoRegistro.LOCAL_DEMAND, TipoRegistro.MSRP, TipoRegistro.STORE_VISIT):
        (guardada,) = repo.capturas(tipo, instante=INSTANTE)
        assert guardada.capturada_en == INSTANTE
        assert guardada.id_carga == reporte.id_carga
    # Antes del instante de la carga no se ven (a un instante, DEC-271).
    antes = INSTANTE - dt.timedelta(microseconds=1)
    assert repo.capturas(TipoRegistro.LOCAL_DEMAND, instante=antes) == ()


def test_la_misma_carga_con_el_mismo_instante_se_reproduce():
    resultados = []
    for _ in range(2):
        repo = RepositorioMemoria()
        reporte = _cargar(repo, "a.jsonl", _archivo_de_capturas(), ids=Ids())
        capturas = {
            tipo: repo.capturas(tipo, instante=INSTANTE)
            for tipo in (TipoRegistro.LOCAL_DEMAND, TipoRegistro.MSRP, TipoRegistro.STORE_VISIT)
        }
        resultados.append((reporte, capturas, repo.leer_carga(reporte.id_carga)))
    assert resultados[0] == resultados[1]


def test_otro_instante_cambia_captured_at_y_nada_mas(repo):
    otro = INSTANTE + dt.timedelta(hours=1)
    uno = _cargar(RepositorioMemoria(), "a.jsonl", _archivo_de_capturas(), ids=Ids())
    repo_dos = RepositorioMemoria()
    dos = _cargar(repo_dos, "a.jsonl", _archivo_de_capturas(), instante=otro, ids=Ids())
    assert uno == dos
    (guardada,) = repo_dos.capturas(TipoRegistro.LOCAL_DEMAND, instante=otro)
    assert guardada.capturada_en == otro


def test_el_cargador_no_lee_el_reloj():
    # El reloj solo se lee en la CLI (CMP-22); el cargador recibe el instante (DEC-271).
    for modulo in ("cargador.py", "_archivos.py"):
        texto = (RAIZ.parent / "src" / "oip" / "entradas" / modulo).read_text(encoding="utf-8")
        for prohibido in ("now(", "today(", "utcnow", "time.time", "import time", "random"):
            assert prohibido not in texto, (modulo, prohibido)


def test_el_instante_sin_desfase_se_rechaza(repo):
    with pytest.raises(TypeError):
        _cargar(repo, "a.jsonl", b"", instante=dt.datetime(2026, 11, 18, 10))  # noqa: DTZ001


# --- Zona y día de la carga (DEC-240, DEC-247, DEC-257, DEC-274 punto 8) -----------------------


def test_dia_de_carga_en_la_zona_de_general_timezone():
    # 07:30 UTC del 19 = 23:30 del 18 en Tijuana (PST, UTC-8).
    assert dia_de_carga(dt.datetime(2026, 11, 19, 7, 30, tzinfo=dt.UTC), CONTENIDO) == dt.date(
        2026, 11, 18
    )
    assert dia_de_carga(dt.datetime(2026, 11, 19, 8, 30, tzinfo=dt.UTC), CONTENIDO) == dt.date(
        2026, 11, 19
    )


def test_el_cargador_siempre_pasa_el_dia_de_carga(repo, monkeypatch):
    vistos = []
    original = modulo_cargador.leer_captura

    def espia(tipo, datos, *, zona=None, dia_de_carga=None):
        vistos.append((zona, dia_de_carga))
        return original(tipo, datos, zona=zona, dia_de_carga=dia_de_carga)

    monkeypatch.setattr(modulo_cargador, "leer_captura", espia)
    _cargar(repo, "a.jsonl", _archivo_de_capturas())
    assert len(vistos) == 3
    assert all(dia == dt.date(2026, 11, 18) for _, dia in vistos)
    assert all(str(zona) == CONTENIDO.general.timezone for zona, _ in vistos)


@pytest.mark.parametrize(
    ("instante", "rechazada"),
    [
        (dt.datetime(2026, 11, 19, 7, 30, tzinfo=dt.UTC), True),  # 18 en Tijuana
        (dt.datetime(2026, 11, 19, 8, 30, tzinfo=dt.UTC), False),  # 19 en Tijuana
    ],
)
def test_fecha_de_captura_del_dia_siguiente_se_rechaza_de_punta_a_punta(repo, instante, rechazada):
    contenido = _jsonl(
        _demanda("2026-11-19"),
        {
            "recordType": "store_visit",
            "storeCode": "tp-cv",
            "brand": "M",
            "model": "X",
            "result": "found",
            "visitedAt": "2026-11-19T00:10:00",
        },
        _demanda("2026-11-18", category="tools"),
    )
    reporte = _cargar(repo, "a.jsonl", contenido, instante=instante)
    if rechazada:
        assert _rechazos(reporte) == [(1, _faltante("date")), (2, _faltante("visitedAt"))]
        assert reporte.cargados == 1
        guardada = repo.leer_carga(reporte.id_carga)
        assert [(r.renglon, r.campo) for r in guardada.rechazos] == [
            (1, "date"),
            (2, "visitedAt"),
        ]
    else:
        assert (reporte.cargados, reporte.rechazados) == (3, 0)


def test_csv_con_fecha_del_dia_siguiente_se_rechaza(repo):
    contenido = b"category,level,date\nbeauty,medium,2026-11-19\nbeauty,high,2026-11-18\n"
    reporte = _cargar(repo, "local_demand.csv", contenido)
    assert _rechazos(reporte) == [(2, _faltante("date"))] and reporte.cargados == 1


def test_fecha_y_hora_sin_desfase_se_toma_en_la_zona_de_la_configuracion(repo):
    _cargar(repo, "a.jsonl", _archivo_de_capturas())
    (visita,) = repo.capturas(TipoRegistro.STORE_VISIT, instante=INSTANTE)
    # 09:15 en Tijuana (PST) = 17:15 UTC.
    assert visita.captura.visited_at == dt.datetime(2026, 11, 18, 17, 15, tzinfo=dt.UTC)


# --- Repositorio como última barrera (DEC-274 punto 9) -----------------------------------------


def test_monto_enorme_y_entero_pasa_la_lectura():
    datos = json.loads(json.dumps(_comercio()).replace('"49.99"', "1e400"), parse_float=Decimal)
    assert datos["price"]["current"] == Decimal("1e400")
    assert not validar(datos, CONTENIDO).rechazada


def test_monto_que_no_cabe_en_el_repositorio_es_rechazo_del_renglon_y_no_detiene_la_carga():
    repo = Espia()
    enorme = json.dumps(_obs(_comercio())).replace('"49.99"', "1e400")
    contenido = _jsonl(
        _demanda(), enorme, _obs(_comercio(productUrl=f"https://{DOMINIO_PRUEBA}/p/2"))
    )
    ids = Ids()
    reporte = _cargar(repo, "a.jsonl", contenido, ids=ids)

    assert (reporte.cargados, reporte.rechazados) == (2, 1)
    assert _rechazos(reporte) == [(2, PRECIO_INVALIDO)]
    assert reporte.rechazados_por_motivo == {PRECIO_INVALIDO: 1}
    guardada = repo.leer_carga(reporte.id_carga)
    assert [(r.renglon, r.motivo, r.tipo_registro) for r in guardada.rechazos] == [
        (2, PRECIO_INVALIDO, TipoRegistro.OBSERVATION)
    ]
    # El renglón rechazado no dejó nada en el historial (una transacción por registro).
    claves = [
        llamada[1][0].clave_idempotencia
        for llamada in repo.llamadas
        if llamada[0] == "guardar_observacion"
    ]
    assert len(claves) == 2
    assert repo.observacion_por_clave(claves[0]) is None
    assert repo.observacion_por_clave(claves[1]) is not None


@pytest.mark.parametrize(
    ("renglon", "motivo"),
    [
        (
            {
                "recordType": "local_estimate",
                "brand": "M",
                "model": "X",
                "price": 10**20,
                "date": "2026-11-10",
            },
            PRECIO_INVALIDO,
        ),
        (
            {
                "recordType": "actual_result",
                "evaluationId": str(UUID(int=7)),
                "channel": "local",
                "units": 10**12,
                "purchasePrice": "1.00",
                "salePrice": "2.00",
                "actualCosts": "0",
                "purchasedOn": "2026-11-01",
                "soldOn": "2026-11-02",
            },
            _faltante("units"),
        ),
        (
            {
                "recordType": "actual_result",
                "evaluationId": str(UUID(int=7)),
                "channel": "local",
                "units": 1,
                "purchasePrice": "1.00",
                "salePrice": "2.00",
                "actualCosts": 10**11,
                "purchasedOn": "2026-11-01",
                "soldOn": "2026-11-02",
            },
            _faltante("actualCosts"),
        ),
        (
            _obs(_comercio(availability={"state": "in_stock", "quantity": 10**12})),
            _faltante("availability.quantity"),
        ),
        (
            _obs(_comercio(price={"current": "10.00", "was": 10**11, "currency": "USD"})),
            _faltante("price.was"),
        ),
    ],
)
def test_otros_valores_que_no_caben_se_rechazan_con_su_campo(repo, renglon, motivo):
    reporte = _cargar(repo, "a.jsonl", _jsonl(renglon, _demanda()))
    assert _rechazos(reporte) == [(1, motivo)]
    assert reporte.cargados == 1


# --- Cada rechazo lleva su carga y su renglón (decisión 33; DEC-250) -----------------------------


def test_todo_rechazo_lleva_su_carga_y_su_renglon():
    repo = Espia()
    contenido = _jsonl(
        _obs(_comercio(price={"current": "0", "currency": "USD"})),
        {"recordType": "coupon"},
        "no es json",
        _demanda("2026-12-01"),
        _obs({**_b18(), "pickupLocation": "ciudad_inexistente"}),
        _obs(_comercio()),
        json.dumps(_obs(_comercio(productUrl=f"https://{DOMINIO_PRUEBA}/p/3"))).replace(
            '"49.99"', "1e400"
        ),
    )
    reporte = _cargar(repo, "a.jsonl", contenido)
    rechazos = [args for nombre, args in repo.llamadas if nombre == "guardar_rechazo_carga"]
    assert [r[0].renglon for r in rechazos] == [1, 2, 3, 4, 5, 7]
    assert all(r[0].id_carga == reporte.id_carga for r in rechazos)
    # Las observaciones rechazadas dejan además su registro RECHAZADA_VALIDACION, de la misma
    # carga y renglón y sin nada del renglón (DEC-250); las demás, solo el rechazo.
    con_registro = {r[0].renglon: r[1] for r in rechazos if r[1] is not None}
    assert sorted(con_registro) == [1, 5, 7]
    for renglon, registro in con_registro.items():
        guardado = repo.leer_evaluacion(registro.id)
        assert isinstance(guardado, RegistroRechazo)
        assert (guardado.id_carga, guardado.renglon) == (reporte.id_carga, renglon)
        assert guardado.evaluado_en == INSTANTE
        assert dict(guardado.versiones_rn) == dict(CONTENIDO.general.rn_versions)
    assert con_registro[1].motivo_rechazo == PRECIO_INVALIDO
    assert con_registro[5].motivo_rechazo == CIUDAD_NO_CONFIGURADA
    assert Resultado.RECHAZADA_VALIDACION.value == "RECHAZADA_VALIDACION"
    guardada = repo.leer_carga(reporte.id_carga)
    assert [r.renglon for r in guardada.rechazos] == [1, 2, 3, 4, 5, 7]
    assert reporte.ciudades_por_registrar == ("ciudad_inexistente",)
    assert reporte.a_json()["citiesToRegister"] == ["ciudad_inexistente"]


def test_una_transaccion_por_registro():
    repo = Espia()
    contenido = _jsonl(_obs(_comercio()), _demanda(), {"recordType": "coupon"}, _demanda())
    _cargar(repo, "a.jsonl", contenido)
    assert [nombre for nombre, _ in repo.llamadas] == [
        "guardar_version_configuracion",
        "iniciar_carga",
        "guardar_observacion",
        "guardar_captura",
        "guardar_rechazo_carga",
        "guardar_captura",
        "terminar_carga",
    ]


# --- Motivos y su orden (design.md §6) --------------------------------------------------------


def test_orden_de_los_motivos_cuando_fallan_dos_a_la_vez(repo):
    contenido = (
        b"brand,model,condition,askingPrice,currency,city,date,sold\n"
        b"M,X,,10.00,USD,lima,2026-11-10,false\n"  # condition antes que la ciudad
        b"M,X,new,0,USD,lima,2026-11-10,false\n"  # precio antes que la ciudad
        b"M,X,new,10.00,USD,lima,2026-11-10,false\n"
        b",,new,0,USD,san_diego,2026-11-10,false\n"  # producto antes que el precio
    )
    reporte = _cargar(repo, "local_comparable.csv", contenido)
    assert _rechazos(reporte) == [
        (2, _faltante("condition")),
        (3, PRECIO_INVALIDO),
        (4, CIUDAD_NO_CONFIGURADA),
        (5, _faltante("gtin")),
    ]
    assert reporte.ciudades_por_registrar == ("lima",)


def test_observaciones_con_sus_motivos_del_paso_1(repo):
    contenido = _jsonl(
        _obs(_comercio(category=None)),
        _obs(_comercio(price={"current": "0", "currency": "USD"})),
        _obs(_comercio(productUrl="https://otro-dominio.example.org/p/1")),
        _obs({**_b18(), "pickupLocation": "ciudad_x"}),
        _obs({**_b18(), "model": ""}),
    )
    reporte = _cargar(repo, "a.jsonl", contenido)
    assert _rechazos(reporte) == [
        (1, _faltante("category")),
        (2, PRECIO_INVALIDO),
        (3, DOMINIO_NO_AUTORIZADO),
        (4, CIUDAD_NO_CONFIGURADA),
        (5, _faltante("model")),
    ]
    assert reporte.ciudades_por_registrar == ("ciudad_x",)


def test_ciudades_por_registrar_sin_repetir_y_en_orden(repo):
    contenido = (
        b"brand,model,condition,askingPrice,currency,city,date,sold\n"
        b"M,X,new,10.00,USD,zeta,2026-11-10,false\n"
        b"M,X,new,11.00,USD,alfa,2026-11-10,false\n"
        b"M,X,new,12.00,USD,zeta,2026-11-10,false\n"
    )
    reporte = _cargar(repo, "local_comparable.csv", contenido)
    assert reporte.ciudades_por_registrar == ("alfa", "zeta")


# --- Identificación del producto (design.md §10 punto 7) ---------------------------------------


def test_identificacion_por_gtin_marca_y_modelo_y_publicacion(repo):
    ids = Ids()
    gtin12 = "036000291452"  # UPC-A sintético con dígito verificador válido
    contenido = _jsonl(
        _obs(_comercio(gtin=gtin12, productUrl=f"https://{DOMINIO_PRUEBA}/p/a")),
        _obs(
            _comercio(
                gtin="0" + gtin12,
                brand=None,
                model=None,
                productUrl=f"https://{DOMINIO_PRUEBA}/p/b",
            )
        ),
        _obs(
            _comercio(
                brand=" marca-sintetica ",
                model="ms-100",
                productUrl=f"https://{DOMINIO_PRUEBA}/p/c",
            )
        ),
        _obs(
            _comercio(
                brand=None,
                model=None,
                productUrl=f"https://{DOMINIO_PRUEBA}/p/a",
                extractedAt="2026-11-17T11:00:00-08:00",
            )
        ),
        _obs(_comercio(brand=None, model=None, productUrl=f"https://{DOMINIO_PRUEBA}/p/d")),
    )
    reporte = _cargar(repo, "a.jsonl", contenido, ids=ids)
    assert reporte.cargados == 5
    observaciones = [o for i in ids.dados if (o := repo.leer_observacion(i)) is not None]
    productos = [o.id_producto for o in observaciones]
    assert productos[0] == productos[1] == productos[2] == productos[3]
    assert productos[4] != productos[0]
    assert observaciones[3].id_publicacion == observaciones[0].id_publicacion


def test_la_coincidencia_sale_de_la_evidencia_de_la_observacion(repo, monkeypatch):
    nuevas = []
    original = RepositorioMemoria.guardar_observacion

    def espia(self, nueva):
        nuevas.append(nueva)
        return original(self, nueva)

    monkeypatch.setattr(RepositorioMemoria, "guardar_observacion", espia)
    contenido = _jsonl(
        _obs(_comercio()),
        _obs(_comercio(brand=None, model=None, productUrl=f"https://{DOMINIO_PRUEBA}/p/2")),
    )
    _cargar(repo, "a.jsonl", contenido)
    assert [n.identificacion for n in nuevas] == [
        Identificacion.CONFIRMED,
        Identificacion.UNCONFIRMED,
    ]
    assert all(n.origen == "file" and n.recibida_en == INSTANTE for n in nuevas)


def test_una_consulta_bloqueada_no_genera_observacion(repo):
    ids = Ids()
    reporte = _cargar(repo, "a.jsonl", _jsonl(_obs(_comercio(blocked=True))), ids=ids)
    assert (reporte.cargados, reporte.rechazados, reporte.duplicados) == (0, 0, 0)
    assert all(repo.leer_observacion(i) is None for i in ids.dados)


# --- Sin contenido: alias, logs, reporte y excepciones ------------------------------------------

CENTINELA = "CENTINELA-T08B-QZX"


def test_el_alias_y_el_contenido_no_salen_en_el_reporte_ni_en_los_logs(repo, caplog):
    caplog.set_level(logging.DEBUG)
    contenido = _jsonl(
        {
            "recordType": "client_request",
            "clientAlias": CENTINELA,
            "items": [],
            "quantity": 1,
            "modality": "link_only",
            "date": "2026-11-18",
        },
        {
            "recordType": "client_request",
            "clientAlias": CENTINELA,
            "items": ["MS-1"],
            "quantity": 0,
            "modality": "link_only",
            "date": "2026-11-18",
            "notes": CENTINELA,
        },
        {
            "recordType": "client_request",
            "clientAlias": CENTINELA,
            "items": ["MS-1"],
            "quantity": 1,
            "modality": "link_only",
            "date": "2026-11-18",
        },
        _obs(_comercio(title=CENTINELA, price={"current": "0", "currency": "USD"})),
        {"recordType": CENTINELA},
        CENTINELA,
    )
    reporte = _cargar(repo, "a.jsonl", contenido)
    assert reporte.cargados == 1 and reporte.rechazados == 5
    texto = json.dumps(reporte.a_json(), ensure_ascii=False) + repr(reporte) + caplog.text
    guardada = repo.leer_carga(reporte.id_carga)
    texto += repr(guardada)
    assert CENTINELA not in texto


def test_un_error_de_archivo_no_lleva_contenido(repo):
    contenido = f"category,{CENTINELA},{CENTINELA}\n".encode()
    with pytest.raises(ErrorDeArchivo) as error:
        _cargar(repo, "local_demand.csv", contenido)
    assert CENTINELA not in str(error.value)


# --- Errores del archivo (antes de empezar la carga) --------------------------------------------


@pytest.mark.parametrize(
    ("nombre", "contenido"),
    [
        ("datos.json", b"{}"),
        ("datos.txt", b""),
        ("local_demand.csv", b"category,level,date\n\xff\xfe,medium,2026-11-18\n"),
        ("local_demand.csv", b"category,level,level\nbeauty,medium,low\n"),
        ("observation.csv", b"price,price.current\n1,2\n"),
    ],
)
def test_un_archivo_que_no_se_puede_leer_no_empieza_la_carga(nombre, contenido):
    repo = Espia()
    with pytest.raises(ErrorDeArchivo):
        _cargar(repo, nombre, contenido)
    assert "iniciar_carga" not in [n for n, _ in repo.llamadas]


def test_formato_por_extension_sin_distinguir_mayusculas(repo):
    reporte = _cargar(repo, "DATOS.JSONL", _jsonl(_demanda()))
    assert reporte.formato == "jsonl" and reporte.cargados == 1


def test_la_carga_guarda_su_archivo_y_su_huella(repo):
    contenido = _jsonl(_demanda())
    reporte = _cargar(repo, "dir/a.jsonl", contenido)
    carga = repo.leer_carga(reporte.id_carga).carga
    assert carga.archivo == "a.jsonl"
    import hashlib

    assert carga.sha256_archivo == hashlib.sha256(contenido).hexdigest()
    assert carga.iniciada_en == INSTANTE and carga.formato == "jsonl"


# --- CLI (CTR-07) -------------------------------------------------------------------------------


def _cli(argv, repo, reloj=None):
    salida, errores = io.StringIO(), io.StringIO()
    codigo = cli.main(
        argv,
        repositorio=lambda: repo,
        reloj=reloj or (lambda: INSTANTE),
        salida=salida,
        errores=errores,
    )
    return codigo, salida.getvalue(), errores.getvalue()


def _config_yaml(tmp_path) -> Path:
    from config_tienda_prueba import BASE, con_sucursales_prueba

    ruta = tmp_path / "oip-config.yaml"
    ruta.write_text(con_sucursales_prueba(BASE.read_text(encoding="utf-8")), encoding="utf-8")
    return ruta


def test_cli_config_cargar_es_idempotente(tmp_path, repo):
    ruta = _config_yaml(tmp_path)
    codigo, salida, _ = _cli(["config", "cargar", str(ruta)], repo, lambda: CONFIG_EN)
    assert codigo == 0
    primera = json.loads(salida)
    assert primera["created"] is True and len(primera["sha256"]) == 64
    codigo, salida, _ = _cli(["config", "cargar", str(ruta)], repo)
    assert codigo == 0
    segunda = json.loads(salida)
    assert segunda["created"] is False
    assert segunda["configVersionId"] == primera["configVersionId"]


def test_cli_config_invalida(tmp_path, repo):
    ruta = tmp_path / "mala.yaml"
    ruta.write_text("version: x\n", encoding="utf-8")
    codigo, _, errores = _cli(["config", "cargar", str(ruta)], repo)
    assert codigo == 1 and "configuración inválida" in errores


def test_cli_cargar_imprime_el_reporte_con_el_instante_dado(tmp_path, repo):
    _cli(["config", "cargar", str(_config_yaml(tmp_path))], repo, lambda: CONFIG_EN)
    archivo = tmp_path / "local_demand__2026-11-18.csv"
    archivo.write_bytes(b"category,level,date\nbeauty,medium,2026-11-18\nbeauty,x,2026-11-18\n")
    codigo, salida, _ = _cli(
        ["cargar", str(archivo), "--instante", "2026-11-18T10:00:00-08:00"], repo
    )
    assert codigo == 0
    reporte = json.loads(salida)
    assert (reporte["loaded"], reporte["rejected"]) == (1, 1)
    assert reporte["recordType"] == "local_demand" and reporte["format"] == "csv"
    (guardada,) = repo.capturas(TipoRegistro.LOCAL_DEMAND, instante=INSTANTE)
    assert guardada.capturada_en == INSTANTE


def test_cli_cargar_sin_instante_usa_el_reloj(tmp_path, repo):
    _cli(["config", "cargar", str(_config_yaml(tmp_path))], repo, lambda: CONFIG_EN)
    archivo = tmp_path / "a.jsonl"
    archivo.write_bytes(_jsonl(_demanda()))
    reloj = INSTANTE + dt.timedelta(minutes=5)
    codigo, _, _ = _cli(["cargar", str(archivo)], repo, lambda: reloj)
    assert codigo == 0
    (guardada,) = repo.capturas(TipoRegistro.LOCAL_DEMAND, instante=reloj)
    assert guardada.capturada_en == reloj


def test_cli_cargar_sin_configuracion_activa(tmp_path, repo):
    archivo = tmp_path / "a.jsonl"
    archivo.write_bytes(_jsonl(_demanda()))
    codigo, salida, errores = _cli(["cargar", str(archivo)], repo)
    assert codigo == 1 and salida == "" and "oip config cargar" in errores


@pytest.mark.parametrize("instante", ["2026-11-18T10:00:00", "mañana"])
def test_cli_instante_sin_desfase_o_invalido(tmp_path, repo, instante):
    archivo = tmp_path / "a.jsonl"
    archivo.write_bytes(b"")
    codigo, _, _ = _cli(["cargar", str(archivo), "--instante", instante], repo)
    assert codigo == 2


def test_cli_archivo_inexistente_o_de_formato_desconocido(tmp_path, repo):
    _cli(["config", "cargar", str(_config_yaml(tmp_path))], repo, lambda: CONFIG_EN)
    codigo, _, errores = _cli(["cargar", str(tmp_path / "no-existe.jsonl")], repo)
    assert codigo == 1 and "no se pudo leer" in errores
    otro = tmp_path / "a.txt"
    otro.write_bytes(b"")
    codigo, _, errores = _cli(["cargar", str(otro)], repo)
    assert codigo == 1 and "formato" in errores


def test_cli_sin_comando():
    assert cli.main([], repositorio=RepositorioMemoria, errores=io.StringIO()) == 2


def test_la_entrada_oip_esta_en_pyproject():
    texto = (RAIZ.parent / "pyproject.toml").read_text(encoding="utf-8")
    assert 'oip = "oip.cli:main"' in texto


def test_copia_profunda_de_los_datos_no_cambia(repo):
    # El cargador no modifica los datos de quien llama: lee bytes.
    datos = _comercio()
    original = copy.deepcopy(datos)
    _cargar(repo, "a.jsonl", _jsonl(_obs(datos)))
    assert datos == original
