"""Pruebas de T08c: cierre de las entradas con DEC-276 a DEC-280 (CMP-06 a CMP-08, CMP-22).

Una prueba (o un grupo parametrizado) por decisión, como pide ``tasks.md`` (T08c):

- DEC-276: los cinco precios de las capturas que no son un número dan ``PRECIO INVÁLIDO``.
- DEC-277: ``%2f``, ``%5c`` o ``%25`` en la ruta del enlace de un particular dan ``DOMINIO
  NO AUTORIZADO``; una ruta normal sigue pasando.
- DEC-278: ``oip config cargar --instante`` fija ``loaded_at``; una carga con ``--instante``
  anterior al registro por el reloj vuelve a encontrar la configuración.
- DEC-279: la columna ``recordType`` de un CSV, igual, distinta o vacía.
- DEC-280: ``extractedAt`` = ``0001-01-01T03:00:00Z`` con ``America/Tijuana``, por JSON
  Lines y por CSV, con la carga completa y su reporte.

Sin escenarios propios (no cambia B20 ni B34). Fixtures sintéticos: las URL de comercio son
de example.com (``tienda-prueba``) y los dominios de las plataformas salen de la
configuración. Ninguna prueba abre una URL; el instante siempre es explícito.
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
from zoneinfo import ZoneInfo

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
from oip.entradas.capturas import leer_captura, motivo_de_rechazo
from oip.entradas.cargador import cargar
from oip.entradas.contrato import leer_observacion
from oip.entradas.validacion import motivo_de_rechazo as motivo_de_observacion
from oip.entradas.validacion import validar
from oip.persistencia.repositorios import RegistroRechazo, RepositorioMemoria

RAIZ = Path(__file__).parent
FIXTURES = RAIZ / "fixtures"
CONFIG = configuracion_con_sucursales_prueba()
CONTENIDO = CONFIG.contenido

#: Instante de la carga: 2026-11-18 10:00 en Tijuana (PAR-01).
INSTANTE = dt.datetime(2026, 11, 18, 18, 0, tzinfo=dt.UTC)
CONFIG_EN = dt.datetime(2026, 11, 1, tzinfo=dt.UTC)

TIPO_DESCONOCIDO = "TIPO DE REGISTRO DESCONOCIDO"
PRECIO_INVALIDO = "PRECIO INVÁLIDO"
DOMINIO_NO_AUTORIZADO = "DOMINIO NO AUTORIZADO"
FUERA_DE_ZONA = "0001-01-01T03:00:00Z"


def _faltante(campo: str) -> str:
    return f"CAMPO OBLIGATORIO FALTANTE ({campo})"


class Ids:
    """Identificadores deterministas (``UUID(int=n)``)."""

    def __init__(self) -> None:
        self.siguiente = 1

    def __call__(self) -> UUID:
        nuevo = UUID(int=self.siguiente)
        self.siguiente += 1
        return nuevo


class Espia:
    """Repositorio en memoria que registra cada rechazo que guarda (con su registro)."""

    def __init__(self) -> None:
        self.repo = RepositorioMemoria()
        self.rechazos: list[tuple[Any, RegistroRechazo | None]] = []

    def __getattr__(self, nombre: str) -> Any:
        metodo = getattr(self.repo, nombre)
        if nombre != "guardar_rechazo_carga":
            return metodo

        def envuelto(rechazo: Any, registro: RegistroRechazo | None = None) -> Any:
            self.rechazos.append((rechazo, registro))
            return metodo(rechazo, registro)

        return envuelto


@pytest.fixture
def repo():
    return RepositorioMemoria()


def _cargar(repo, nombre: str, contenido: bytes, instante: dt.datetime = INSTANTE):
    version, _ = repo.guardar_version_configuracion(CONFIG, cargada_en=CONFIG_EN)
    return cargar(nombre, contenido, repo, version, instante, nuevo_id=Ids())


def _jsonl(*renglones: dict[str, Any]) -> bytes:
    return ("\n".join(json.dumps(r, ensure_ascii=False) for r in renglones) + "\n").encode()


def _rechazos(reporte) -> list[tuple[int, str]]:
    return [(r.renglon, r.motivo) for r in reporte.rechazos]


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


def test_la_zona_de_las_pruebas_es_tijuana():
    assert CONTENIDO.general.timezone == "America/Tijuana"


# --- DEC-276: precio de captura que no es un número ----------------------------------------

#: Capturas válidas, sintéticas, con los cinco precios (CTR-04).
_CAPTURAS: dict[str, dict[str, Any]] = {
    "local_comparable": {
        "brand": "MARCA",
        "model": "M-1",
        "condition": "used",
        "askingPrice": "120.00",
        "currency": "USD",
        "city": "san_diego",
        "date": "2026-11-15",
        "sold": False,
    },
    "local_estimate": {"brand": "MARCA", "model": "M-1", "price": "95.00", "date": "2026-11-15"},
    "msrp": {
        "brand": "MARCA",
        "model": "M-1",
        "value": "149.00",
        "source": "caja",
        "date": "2026-11-15",
    },
    "actual_result": {
        "evaluationId": "00000000-0000-0000-0000-000000000001",
        "channel": "local",
        "units": 1,
        "purchasePrice": "70.00",
        "salePrice": "110.00",
        "actualCosts": "5.00",
        "purchasedOn": "2026-11-10",
        "soldOn": "2026-11-15",
    },
}

#: (tipo, campo) de los cinco precios (DEC-276).
_PRECIOS = [
    ("local_comparable", "askingPrice"),
    ("local_estimate", "price"),
    ("msrp", "value"),
    ("actual_result", "purchasePrice"),
    ("actual_result", "salePrice"),
]

#: Valores que no son un número de un monto (texto, ``float``, booleano, no finitos, lista).
_NO_NUMEROS = ["abc", "12,50", "$10", 29.5, True, "NaN", "Infinity", ["10"], {"v": "10"}]


def _captura(tipo: str, **cambios: Any) -> dict[str, Any]:
    datos = copy.deepcopy(_CAPTURAS[tipo])
    datos.update(cambios)
    return datos


@pytest.mark.parametrize(("tipo", "campo"), _PRECIOS)
def test_las_capturas_base_son_validas(tipo, campo):
    captura = leer_captura(tipo, _captura(tipo))
    assert motivo_de_rechazo(captura) is None
    assert isinstance(getattr(captura, _atributo(campo)), Decimal)


def _atributo(campo: str) -> str:
    return {"askingPrice": "asking_price", "purchasePrice": "purchase_price"}.get(
        campo, {"salePrice": "sale_price"}.get(campo, campo)
    )


@pytest.mark.parametrize("valor", _NO_NUMEROS)
@pytest.mark.parametrize(("tipo", "campo"), _PRECIOS)
def test_precio_de_captura_que_no_es_un_numero_da_precio_invalido(tipo, campo, valor):
    captura = leer_captura(tipo, _captura(tipo, **{campo: valor}))
    assert captura.precio_invalido is True
    assert motivo_de_rechazo(captura) == PRECIO_INVALIDO
    # Nunca un float en la captura (DEC-060).
    assert all(not isinstance(v, float) for v in captura.model_dump().values())


@pytest.mark.parametrize(("tipo", "campo"), _PRECIOS)
@pytest.mark.parametrize("valor", [None, "", "   "])
def test_precio_de_captura_ausente_o_vacio_sigue_siendo_faltante(tipo, campo, valor):
    from oip.entradas._comun import RegistroInvalido

    with pytest.raises(RegistroInvalido) as error:
        leer_captura(tipo, _captura(tipo, **{campo: valor}))
    assert error.value.motivo == _faltante(campo)
    assert error.value.campo == campo


@pytest.mark.parametrize(("tipo", "campo"), _PRECIOS)
def test_un_faltante_va_antes_que_el_precio_que_no_es_un_numero(tipo, campo):
    from oip.entradas._comun import RegistroInvalido

    datos = _captura(tipo, **{campo: "abc"})
    ultimo = "soldOn" if tipo == "actual_result" else "date"
    datos.pop(ultimo)
    with pytest.raises(RegistroInvalido) as error:
        leer_captura(tipo, datos)
    assert error.value.motivo == _faltante(ultimo)


@pytest.mark.parametrize(("tipo", "campo"), _PRECIOS)
def test_precio_que_no_es_un_numero_de_punta_a_punta_por_json_lines(repo, tipo, campo):
    contenido = _jsonl(
        {"recordType": tipo, **_captura(tipo, **{campo: "precio-secreto"})},
        {"recordType": tipo, **_captura(tipo, date="2026-11-14", purchasedOn="2026-11-09")},
    )
    reporte = _cargar(repo, "capturas.jsonl", contenido)
    assert _rechazos(reporte) == [(1, PRECIO_INVALIDO)]
    assert reporte.cargados == 1
    assert "precio-secreto" not in json.dumps(reporte.a_json())  # R-20: sin el valor


@pytest.mark.parametrize(("tipo", "campo"), _PRECIOS)
def test_precio_que_no_es_un_numero_de_punta_a_punta_por_csv(repo, tipo, campo):
    datos = _captura(tipo, **{campo: "abc"})
    datos.pop("sold", None)
    columnas = list(datos)
    encabezado = ",".join([*columnas, "sold"] if tipo == "local_comparable" else columnas)
    celdas = [str(datos[c]) for c in columnas]
    if tipo == "local_comparable":
        celdas.append("false")
    contenido = f"{encabezado}\n{','.join(celdas)}\n".encode()
    reporte = _cargar(repo, f"{tipo}.csv", contenido)
    assert _rechazos(reporte) == [(2, PRECIO_INVALIDO)]
    guardada = repo.leer_carga(reporte.id_carga)
    assert [(r.motivo, r.campo) for r in guardada.rechazos] == [(PRECIO_INVALIDO, None)]


# --- DEC-277: separadores codificados en la ruta de un particular ---------------------------


def _plataformas():
    return list(CONTENIDO.private_sellers.platforms.values())


def _enlace(plataforma, cola: str) -> str:
    prefijo = plataforma.path_prefix or ""
    return f"https://{plataforma.domains[0]}{prefijo}/{cola}"


_CODIFICADOS = ["%2f", "%2F", "%5c", "%5C", "%25", "%252e%252e"]


@pytest.mark.parametrize("codificado", _CODIFICADOS)
@pytest.mark.parametrize("indice", range(len(_plataformas())))
def test_separador_codificado_en_la_ruta_de_un_particular(indice, codificado):
    plataforma = _plataformas()[indice]
    for cola in (f"item{codificado}1", f"{codificado}..{codificado}groups", f"a/{codificado}"):
        datos = {**_b18(), "productUrl": _enlace(plataforma, cola)}
        validacion = validar(datos, CONTENIDO)
        assert validacion.motivo_rechazo == DOMINIO_NO_AUTORIZADO
        assert validacion.campo is None


@pytest.mark.parametrize("indice", range(len(_plataformas())))
def test_ruta_normal_de_un_particular_sigue_pasando(indice):
    plataforma = _plataformas()[indice]
    for cola in ("item/1", "item/detalle-sintetico", "item/%2e/1", "item/a%20b", "item/%41"):
        datos = {**_b18(), "productUrl": _enlace(plataforma, cola)}
        assert validar(datos, CONTENIDO).motivo_rechazo is None, cola


def test_separador_codificado_en_la_query_de_un_particular_no_cuenta():
    # DEC-277 habla de la ruta: la query se queda tal cual (DEC-256).
    plataforma = _plataformas()[0]
    datos = {**_b18(), "productUrl": _enlace(plataforma, "item/1?r=%2Fa%5Cb%25")}
    assert validar(datos, CONTENIDO).motivo_rechazo is None


def test_separador_codificado_en_la_ruta_de_un_comercio_no_cambia():
    # DEC-277 es del enlace de un particular; la regla por comercio llega en la parte A.
    datos = _comercio(productUrl=f"https://www.{DOMINIO_PRUEBA}/p/a%2Fb")
    assert validar(datos, CONTENIDO).motivo_rechazo is None


def test_el_precio_invalido_va_antes_que_el_separador_codificado():
    plataforma = _plataformas()[0]
    datos = {**_b18(), "productUrl": _enlace(plataforma, "item%2f1")}
    datos["price"] = {"current": "0", "currency": "USD"}
    assert validar(datos, CONTENIDO).motivo_rechazo == PRECIO_INVALIDO


def test_separador_codificado_de_punta_a_punta(repo):
    plataforma = _plataformas()[0]
    contenido = _jsonl(
        _obs({**_b18(), "productUrl": _enlace(plataforma, "item%2F1")}),
        _obs({**_b18(), "productUrl": _enlace(plataforma, "item/1")}),
    )
    reporte = _cargar(repo, "particulares.jsonl", contenido)
    assert _rechazos(reporte) == [(1, DOMINIO_NO_AUTORIZADO)]
    assert reporte.cargados == 1
    assert "%2F" not in json.dumps(reporte.a_json())


# --- DEC-278: oip config cargar --instante --------------------------------------------------


def _cli(argv, repo, reloj):
    salida, errores = io.StringIO(), io.StringIO()
    codigo = cli.main(argv, repositorio=lambda: repo, reloj=reloj, salida=salida, errores=errores)
    return codigo, salida.getvalue(), errores.getvalue()


def _config_yaml(tmp_path) -> Path:
    ruta = tmp_path / "oip-config.yaml"
    ruta.write_text(con_sucursales_prueba(BASE.read_text(encoding="utf-8")), encoding="utf-8")
    return ruta


def _reloj_prohibido() -> dt.datetime:
    raise AssertionError("con --instante no se lee el reloj")


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("2026-11-01T00:00:00-08:00", dt.datetime(2026, 11, 1, 8, tzinfo=dt.UTC)),
        ("2026-11-01T08:00:00Z", dt.datetime(2026, 11, 1, 8, tzinfo=dt.UTC)),
        ("2026-11-01T08:00:00+00:00", dt.datetime(2026, 11, 1, 8, tzinfo=dt.UTC)),
    ],
)
def test_config_cargar_con_instante_fija_loaded_at(tmp_path, repo, texto, esperado):
    argv = ["config", "cargar", str(_config_yaml(tmp_path)), "--instante", texto]
    codigo, salida, _ = _cli(argv, repo, _reloj_prohibido)
    assert codigo == 0 and json.loads(salida)["created"] is True
    assert repo.version_configuracion_activa(esperado - dt.timedelta(microseconds=1)) is None
    activa = repo.version_configuracion_activa(esperado)
    assert activa is not None and activa.cargada_en == esperado


def test_config_cargar_sin_instante_usa_el_reloj(tmp_path, repo):
    reloj = dt.datetime(2026, 11, 20, 12, tzinfo=dt.UTC)
    codigo, _, _ = _cli(["config", "cargar", str(_config_yaml(tmp_path))], repo, lambda: reloj)
    assert codigo == 0
    assert repo.version_configuracion_activa(reloj - dt.timedelta(seconds=1)) is None
    assert repo.version_configuracion_activa(reloj).cargada_en == reloj


@pytest.mark.parametrize(
    "instante", ["2026-11-01T00:00:00", "2026-11-01", "ayer", "", "9999-12-31T23:00:00-08:00"]
)
def test_config_cargar_con_instante_sin_desfase_o_invalido(tmp_path, repo, instante):
    argv = ["config", "cargar", str(_config_yaml(tmp_path)), "--instante", instante]
    codigo, salida, _ = _cli(argv, repo, _reloj_prohibido)
    assert codigo == 2 and salida == ""
    assert repo.version_configuracion_activa(dt.datetime(9000, 1, 1, tzinfo=dt.UTC)) is None


def test_carga_con_instante_anterior_al_reloj_vuelve_a_encontrar_la_configuracion(tmp_path):
    """DEC-278: la configuración se registra hoy, pero con ``--instante`` de la carga pasada;
    ``oip cargar --instante`` con ese instante la encuentra (sin DEC-278, "no hay
    configuración activa", DEC-271)."""
    hoy = dt.datetime(2026, 11, 25, 12, tzinfo=dt.UTC)
    archivo = tmp_path / "local_demand__2026-11-18.csv"
    archivo.write_bytes(b"category,level,date\nbeauty,medium,2026-11-18\n")
    pasado = "2026-11-18T10:00:00-08:00"

    # Sin --instante en config cargar: loaded_at = reloj (hoy) y la carga pasada no la ve.
    solo_reloj = RepositorioMemoria()
    _cli(["config", "cargar", str(_config_yaml(tmp_path))], solo_reloj, lambda: hoy)
    codigo, _, errores = _cli(["cargar", str(archivo), "--instante", pasado], solo_reloj, None)
    assert codigo == 1 and "no hay configuración activa" in errores

    # Con --instante: la misma carga pasada se reproduce.
    repo = RepositorioMemoria()
    argv = ["config", "cargar", str(_config_yaml(tmp_path)), "--instante", "2026-11-01T00:00Z"]
    assert _cli(argv, repo, lambda: hoy)[0] == 0
    codigo, salida, _ = _cli(["cargar", str(archivo), "--instante", pasado], repo, lambda: hoy)
    assert codigo == 0
    assert json.loads(salida)["loaded"] == 1
    (guardada,) = repo.capturas(TipoRegistro.LOCAL_DEMAND, instante=INSTANTE)
    assert guardada.capturada_en == INSTANTE


def test_config_cargar_con_instante_es_idempotente_y_conserva_loaded_at(tmp_path, repo):
    """Lectura de DEC-278 con CTR-07 (idempotente por ``sha256``): volver a registrar la
    misma versión con otro ``--instante`` no la duplica ni cambia su ``loaded_at``."""
    ruta = str(_config_yaml(tmp_path))
    primera = json.loads(
        _cli(["config", "cargar", ruta, "--instante", "2026-11-10T00:00Z"], repo, None)[1]
    )
    segunda = json.loads(
        _cli(["config", "cargar", ruta, "--instante", "2026-11-01T00:00Z"], repo, None)[1]
    )
    assert segunda["created"] is False
    assert segunda["configVersionId"] == primera["configVersionId"]
    activa = repo.version_configuracion_activa(dt.datetime(2026, 11, 10, tzinfo=dt.UTC))
    assert activa.cargada_en == dt.datetime(2026, 11, 10, tzinfo=dt.UTC)
    assert repo.version_configuracion_activa(dt.datetime(2026, 11, 5, tzinfo=dt.UTC)) is None


# --- DEC-279: columna recordType en un CSV --------------------------------------------------

_DEMANDA = "category,level,date"


@pytest.mark.parametrize("valor", ["local_demand", " local_demand ", "\tlocal_demand"])
def test_columna_record_type_igual_al_nombre_se_acepta_y_se_descarta(repo, valor):
    contenido = f"recordType,{_DEMANDA}\n{valor},beauty,medium,2026-11-18\n".encode()
    reporte = _cargar(repo, "local_demand__a.csv", contenido)
    assert (reporte.cargados, reporte.rechazados) == (1, 0)
    (guardada,) = repo.capturas(TipoRegistro.LOCAL_DEMAND, instante=INSTANTE)
    assert "recordType" not in guardada.captura.model_dump(by_alias=True)


@pytest.mark.parametrize(
    "valor", ["msrp", "observation", "coupon", "LOCAL_DEMAND", "local_demand__a", "", "   "]
)
def test_columna_record_type_distinta_o_vacia_rechaza_ese_renglon(repo, valor):
    contenido = (
        f"{_DEMANDA},recordType\n"
        "beauty,medium,2026-11-18,local_demand\n"
        f"beauty,low,2026-11-17,{valor}\n"
        "tools,high,2026-11-16,local_demand\n"
    ).encode()
    reporte = _cargar(repo, "local_demand.csv", contenido)
    # El tipo sigue saliendo del nombre (CTR-03).
    assert reporte.tipo_registro is TipoRegistro.LOCAL_DEMAND
    assert (reporte.cargados, reporte.rechazados) == (2, 1)
    assert _rechazos(reporte) == [(3, TIPO_DESCONOCIDO)]
    assert reporte.a_json()["rejections"] == [
        {"line": 3, "recordType": None, "reason": TIPO_DESCONOCIDO}
    ]


def test_columna_record_type_faltante_en_un_renglon_corto_cuenta_como_vacia(repo):
    contenido = f"{_DEMANDA},recordType\nbeauty,medium,2026-11-18\n".encode()
    reporte = _cargar(repo, "local_demand.csv", contenido)
    assert _rechazos(reporte) == [(2, TIPO_DESCONOCIDO)]


def test_csv_sin_columna_record_type_no_cambia(repo):
    contenido = f"{_DEMANDA}\nbeauty,medium,2026-11-18\n".encode()
    reporte = _cargar(repo, "local_demand.csv", contenido)
    assert (reporte.cargados, reporte.rechazados) == (1, 0)


def test_columna_record_type_en_csv_de_observaciones_no_deja_registro_de_evaluacion():
    """Como un renglón JSON Lines con tipo desconocido, solo queda en el reporte (B34 c)."""
    espia = Espia()
    encabezado = (
        "recordType,retailerCode,productUrl,title,category,price.current,seller,"
        "availability.state,purchaseMode,extractedAt,blocked"
    )
    cola = f"{TIENDA_PRUEBA},https://{DOMINIO_PRUEBA}/p/1,P,tools,49.99,comercio,in_stock,envio"
    contenido = (
        f"{encabezado}\n"
        f"msrp,{cola},2026-11-17T10:00:00-08:00,false\n"
        f"observation,{cola},2026-11-17T11:00:00-08:00,false\n"
    ).encode()
    reporte = _cargar(espia, "observation.csv", contenido)
    assert _rechazos(reporte) == [(2, TIPO_DESCONOCIDO)]
    assert reporte.cargados == 1
    ((rechazo, registro),) = espia.rechazos
    assert rechazo.tipo_registro is None and registro is None


def test_columna_record_type_con_nombre_sin_tipo_sigue_rechazando(repo):
    contenido = f"recordType,{_DEMANDA}\nlocal_demand,beauty,medium,2026-11-18\n".encode()
    reporte = _cargar(repo, "capturas.csv", contenido)
    assert reporte.tipo_registro is None
    assert _rechazos(reporte) == [(2, TIPO_DESCONOCIDO)]


# --- DEC-280: extractedAt que no cabe en la zona de la carga --------------------------------


def test_fuera_de_zona_cabe_en_utc_pero_no_en_tijuana():
    valor = dt.datetime.fromisoformat(FUERA_DE_ZONA)
    valor.astimezone(dt.UTC)
    with pytest.raises(OverflowError):
        valor.astimezone(ZoneInfo("America/Tijuana"))


@pytest.mark.parametrize("valor", [FUERA_DE_ZONA, "0001-01-01T07:00:00+00:00"])
def test_extracted_at_fuera_de_la_zona_da_campo_faltante(valor):
    validacion = validar(_comercio(extractedAt=valor), CONTENIDO)
    assert validacion.motivo_rechazo == _faltante("extractedAt")
    assert validacion.campo == "extractedAt"
    assert validacion.observacion is None


def test_extracted_at_justo_dentro_de_la_zona_pasa():
    assert validar(_comercio(extractedAt="0001-01-01T08:00:00Z"), CONTENIDO).motivo_rechazo is None


def test_la_zona_llega_por_parametro_a_leer_observacion():
    datos = _comercio(extractedAt=FUERA_DE_ZONA)
    # Sin zona no se comprueba (como antes); con ella, no es un valor válido del campo.
    assert leer_observacion(datos).extracted_at.year == 1
    from oip.entradas._comun import RegistroInvalido

    for zona in ("America/Tijuana", ZoneInfo("America/Tijuana")):
        with pytest.raises(RegistroInvalido) as error:
            leer_observacion(datos, zona=zona)
        assert error.value.motivo == _faltante("extractedAt")
    # En UTC sí cabe.
    assert leer_observacion(datos, zona=dt.UTC).extracted_at.year == 1


def test_extracted_at_fuera_de_la_zona_respeta_el_orden_de_los_obligatorios():
    # category va antes que extractedAt (arquitectura §8); blocked, después.
    datos = _comercio(extractedAt=FUERA_DE_ZONA, category="no-existe")
    assert validar(datos, CONTENIDO).motivo_rechazo == _faltante("category")
    datos = _comercio(extractedAt=FUERA_DE_ZONA, blocked="no")
    assert validar(datos, CONTENIDO).motivo_rechazo == _faltante("extractedAt")
    # Va antes que el precio inválido y que el dominio.
    datos = _comercio(
        extractedAt=FUERA_DE_ZONA, price={"current": "0"}, productUrl="https://x.test/"
    )
    assert validar(datos, CONTENIDO).motivo_rechazo == _faltante("extractedAt")


def test_el_paso_1_sobre_una_observacion_ya_leida_tambien_lo_rechaza():
    observacion = leer_observacion(_comercio(extractedAt=FUERA_DE_ZONA))
    assert motivo_de_observacion(observacion, CONTENIDO) == _faltante("extractedAt")


def _esperar_rechazo_fuera_de_zona(espia, reporte, renglon: int) -> None:
    assert reporte.cargados == 1 and reporte.rechazados == 1
    assert _rechazos(reporte) == [(renglon, _faltante("extractedAt"))]
    assert reporte.rechazados_por_motivo == {_faltante("extractedAt"): 1}
    assert reporte.a_json()["rejections"] == [
        {"line": renglon, "recordType": "observation", "reason": _faltante("extractedAt")}
    ]
    guardada = espia.repo.leer_carga(reporte.id_carga)
    assert guardada.reporte is not None and guardada.reporte.rechazados == 1
    assert [(r.renglon, r.motivo, r.campo) for r in guardada.rechazos] == [
        (renglon, _faltante("extractedAt"), "extractedAt")
    ]
    # DEC-250: deja su RECHAZADA_VALIDACION, sin nada del renglón.
    ((_, registro),) = espia.rechazos
    assert isinstance(registro, RegistroRechazo)
    leido = espia.repo.leer_evaluacion(registro.id)
    assert isinstance(leido, RegistroRechazo)
    assert leido.motivo_rechazo == _faltante("extractedAt")
    assert (leido.id_carga, leido.renglon) == (reporte.id_carga, renglon)
    assert FUERA_DE_ZONA not in repr(leido) and "0001-01-01" not in json.dumps(reporte.a_json())


def test_extracted_at_fuera_de_la_zona_por_json_lines_carga_completa():
    espia = Espia()
    contenido = _jsonl(
        _obs(_comercio(extractedAt=FUERA_DE_ZONA)),
        _obs(_comercio(productUrl=f"https://{DOMINIO_PRUEBA}/p/2")),
    )
    reporte = _cargar(espia, "vps.jsonl", contenido)
    _esperar_rechazo_fuera_de_zona(espia, reporte, 1)


def test_extracted_at_fuera_de_la_zona_por_csv_carga_completa():
    espia = Espia()
    encabezado = (
        "retailerCode,productUrl,title,category,price.current,seller,"
        "availability.state,purchaseMode,extractedAt,blocked"
    )
    cola = "P,tools,49.99,comercio,in_stock,envio"
    contenido = (
        f"{encabezado}\n"
        f"{TIENDA_PRUEBA},https://{DOMINIO_PRUEBA}/p/1,{cola},2026-11-17T10:00:00-08:00,false\n"
        f"{TIENDA_PRUEBA},https://{DOMINIO_PRUEBA}/p/2,{cola},{FUERA_DE_ZONA},false\n"
    ).encode()
    reporte = _cargar(espia, "observation__vps.csv", contenido)
    _esperar_rechazo_fuera_de_zona(espia, reporte, 3)


def test_los_motivos_de_t08c_no_llevan_valores_en_los_logs(repo, caplog):
    caplog.set_level(logging.DEBUG)
    plataforma = _plataformas()[0]
    contenido = _jsonl(
        _obs(_comercio(extractedAt=FUERA_DE_ZONA)),
        _obs({**_b18(), "productUrl": _enlace(plataforma, "item%2Fsecreto")}),
        {"recordType": "msrp", **_captura("msrp", value="valor-secreto")},
    )
    reporte = _cargar(repo, "mezcla.jsonl", contenido)
    assert [m for _, m in _rechazos(reporte)] == [
        _faltante("extractedAt"),
        DOMINIO_NO_AUTORIZADO,
        PRECIO_INVALIDO,
    ]
    texto = json.dumps(reporte.a_json()) + caplog.text
    for secreto in ("0001-01-01", "secreto", "%2F"):
        assert secreto not in texto


@pytest.mark.parametrize("zona", [8, -8, b"America/Tijuana"])
def test_leer_observacion_exige_una_zona_valida(zona):
    with pytest.raises(TypeError):
        leer_observacion(_comercio(), zona=zona)
