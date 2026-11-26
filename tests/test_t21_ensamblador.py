"""Pruebas de T21: la carga dispara la evaluación, el registro se guarda y se recalcula
(CMP-21, CMP-08, CMP-22; design.md §2, §3, §5, §11, CTR-06, CTR-07).

- Escenario **B34 (a)** de REQ-2026-0001 v2.9 de punta a punta: cargador → ensamblador →
  motor → registro guardado (TAB-10 y TAB-11).
- **RNF-3:** recalcular cada evaluación guardada da el mismo registro (``recalcular`` y
  ``oip evaluacion recalcular``).
- **RNF-2:** cambiar un parámetro y cargar la configuración cambia el resultado de una
  evaluación nueva; la anterior conserva su versión.
- **RNF-1:** evaluar con el historial sintético de design.md §11 (10 publicaciones × 90 días
  × 2 observaciones + 60 fichas) tarda menos de 2 s, de punta a punta con guardar el registro.
- **Borde de los 90 días del contexto** (DEC-264) y capturas "a un instante" (DEC-271).

Cada prueba con el repositorio corre contra ``RepositorioMemoria`` y, con
``@pytest.mark.integracion``, contra PostgreSQL + TimescaleDB (se salta sin
``OIP_TEST_DATABASE_URL``, DEC-233; la base debe ser **desechable**: se borran las tablas de
OIP). Fixtures sintéticos; las URL de comercio son de example.com y ninguna prueba abre una
URL. El instante siempre es explícito.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import io
import json
import os
import time
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

from config_tienda_prueba import (
    BASE,
    TIENDA_PRUEBA,
    con_sucursales_prueba,
    configuracion_con_sucursales_prueba,
)
from oip import cli
from oip.catalogos import (
    Canal,
    CausaCanalCerrado,
    EstadoCanal,
    Identificacion,
    Motivo,
    Resultado,
    TipoRegistro,
)
from oip.dinero import formatear_porcentaje
from oip.entradas.cargador import cargar, cargar_archivo
from oip.entradas.contrato import leer_observacion
from oip.evaluacion import motor
from oip.evaluacion.contexto import ObservacionRegistrada, RegistroEvaluacion
from oip.persistencia import tablas
from oip.persistencia.ensamblador import (
    EvaluacionNoEncontrada,
    EvaluacionNoRecalculable,
    armar_contexto,
    dias_del_contexto,
    evaluar_carga,
    evaluar_observacion,
    recalcular,
)
from oip.persistencia.repositorios import (
    IdentificadorProducto,
    ObservacionNueva,
    Producto,
    Publicacion,
    RepositorioMemoria,
    RepositorioPostgres,
    crear_motor,
)

D = Decimal
RAIZ = Path(__file__).resolve().parent.parent
ARCHIVOS = Path(__file__).parent / "fixtures" / "archivos"
ZONA = ZoneInfo("America/Tijuana")
CONFIG = configuracion_con_sucursales_prueba()
CONFIG_EN = dt.datetime(2026, 11, 1, tzinfo=dt.UTC)
#: Los comparables de B18 se cargan la víspera; el archivo de B34 (a), el día de B18.
COMPARABLES_EN = dt.datetime(2026, 11, 15, 20, 0, tzinfo=ZONA)
B34A_EN = dt.datetime(2026, 11, 16, 12, 0, tzinfo=ZONA)
_VARIABLE = "OIP_TEST_DATABASE_URL"


def _faltante(campo: str) -> str:
    return f"CAMPO OBLIGATORIO FALTANTE ({campo})"


class Ids:
    """Identificadores deterministas (``UUID(int=n)``)."""

    def __init__(self, inicio: int = 1) -> None:
        self.siguiente = inicio

    def __call__(self) -> UUID:
        nuevo = UUID(int=self.siguiente)
        self.siguiente += 1
        return nuevo


# --- Las dos implementaciones del repositorio -----------------------------------------------


def _url():
    from sqlalchemy.engine import make_url

    valor = os.environ.get(_VARIABLE, "").strip()
    if not valor:
        pytest.skip(f"sin {_VARIABLE}: las pruebas de integración se saltan (DEC-233)")
    url = make_url(valor)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    return url


def _limpiar(motor_bd) -> None:
    nombres = ", ".join([*tablas.metadata.tables, "alembic_version"])
    with motor_bd.begin() as conexion:
        conexion.execute(text("DROP VIEW IF EXISTS open_opportunity"))
        conexion.execute(text(f"DROP TABLE IF EXISTS {nombres} CASCADE"))


def _migrar_head(motor_bd) -> None:
    from alembic import command
    from alembic.config import Config

    with motor_bd.begin() as conexion:
        config = Config(str(RAIZ / "alembic.ini"))
        config.attributes["connection"] = conexion
        command.upgrade(config, "head")


@pytest.fixture(params=["memoria", pytest.param("postgres", marks=pytest.mark.integracion)])
def repo(request):
    if request.param == "memoria":
        yield RepositorioMemoria()
        return
    motor_bd = crear_motor(_url())
    _limpiar(motor_bd)
    try:
        _migrar_head(motor_bd)
        yield RepositorioPostgres(motor_bd)
    finally:
        _limpiar(motor_bd)
        motor_bd.dispose()


def _version(repo, configuracion=CONFIG, en=CONFIG_EN):
    version, _ = repo.guardar_version_configuracion(configuracion, cargada_en=en)
    return version


def _cargar_b34a(repo, ids=None):
    """Dado de B34 (a): los comparables de B18 ya cargados; después, el archivo (a)."""
    ids = ids or Ids()
    version = _version(repo)
    cargar_archivo(
        ARCHIVOS / "local_comparable__b18.csv", repo, version, COMPARABLES_EN, nuevo_id=ids
    )
    return cargar_archivo(ARCHIVOS / "b34a.jsonl", repo, version, B34A_EN, nuevo_id=ids)


def _canal(registro: RegistroEvaluacion, canal: Canal):
    return next(c for c in registro.canales if c.canal is canal)


def _afirmar_b18(registro: RegistroEvaluacion) -> None:
    """El resultado de B18 (REQ §11): los números y el resultado."""
    assert registro.referencias.valor_referencia_usados == D("110.50")  # 130 × 85%
    assert formatear_porcentaje(registro.descuento_real) == "36.7 %"
    assert registro.costo_compra == D("79.50")  # 70 + 9.50, sin impuesto
    amazon = _canal(registro, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.CERRADO
    assert CausaCanalCerrado.PRODUCTO_NO_NUEVO in amazon.causas_cerrado
    local = _canal(registro, Canal.LOCAL)
    assert local.precio_venta == D("99.45")
    assert local.margen_neto == D("10.45")
    assert local.castigo == D("9.95")
    assert local.margen_ajustado == D("0.50")
    assert local.nivel is None
    assert registro.motivos == (Motivo.PARTICULAR, Motivo.RIESGO_DE_PROCEDENCIA)
    assert registro.resultado is Resultado.REVISION_MANUAL
    assert registro.motivo_principal is Motivo.PARTICULAR


# --- B34 (a) ---------------------------------------------------------------------------------


@pytest.mark.scenario("B34 (a)")
def test_b34_a_carga_mixta_rechaza_dos_y_evalua_la_observacion_con_el_resultado_de_b18(repo):
    reporte = _cargar_b34a(repo)

    # Se cargan (1) y (3); (2) y (4) se rechazan, uno por cada motivo, y la carga sigue.
    assert (reporte.cargados, reporte.rechazados, reporte.duplicados) == (2, 2, 0)
    assert [(r.renglon, r.motivo) for r in reporte.rechazos] == [
        (2, _faltante("exchangeRate")),
        (4, "TIPO DE REGISTRO DESCONOCIDO"),
    ]
    assert reporte.rechazados_por_motivo == {
        _faltante("exchangeRate"): 1,
        "TIPO DE REGISTRO DESCONOCIDO": 1,
    }
    # CTR-05 no cambia: las evaluaciones no van en el reporte de carga.
    assert "evaluations" not in reporte.a_json()

    # La observación (1) dispara su evaluación, con el resultado de B18.
    assert len(reporte.evaluaciones) == 1
    registro = repo.leer_evaluacion(reporte.evaluaciones[0])
    assert isinstance(registro, RegistroEvaluacion)
    _afirmar_b18(registro)
    assert registro.evaluado_en == B34A_EN
    assert registro.id_carga == reporte.id_carga
    # Registro (REQ §7): versión de la configuración y de cada RN.
    version = repo.version_configuracion_activa(B34A_EN)
    assert registro.id_version_configuracion == version.id
    assert dict(registro.versiones_rn) == dict(CONFIG.contenido.general.rn_versions)
    # El registro vuelve igual que el que dio el motor, con su input_snapshot (CTR-06).
    assert recalcular(repo, registro.id).coincide


@pytest.mark.scenario("B34 (a)")
def test_b34_a_la_observacion_usada_y_las_capturas_del_contexto(repo):
    reporte = _cargar_b34a(repo)
    registro = repo.leer_evaluacion(reporte.evaluaciones[0])
    entrada = registro.entrada
    # La oferta es la única observación guardada del producto, con su fecha.
    assert [(u.id, u.fecha) for u in registro.observaciones_usadas] == [
        (entrada.oferta.id, dt.datetime(2026, 11, 16, 18, 0, tzinfo=dt.UTC))
    ]
    assert entrada.historial == () and entrada.fichas_amazon == ()
    # Los 3 comparables de B18 (el de MXN sin tipo de cambio se rechazó) y la demanda de
    # beauty de este mismo archivo: las capturas del archivo ya cuentan (design.md §2).
    assert sorted(c.asking_price for c in entrada.comparables) == [
        D("120.00"),
        D("130.00"),
        D("140.00"),
    ]
    assert [(d.category, d.level) for d in entrada.demanda_local] == [("beauty", "medium")]


# --- Conexión cargador → ensamblador ---------------------------------------------------------


def _comercio(n: int, extraida: dt.datetime, precio: str = "100.00", **cambios) -> dict:
    datos: dict[str, Any] = {
        "recordType": "observation",
        "schemaVersion": "3.1",
        "retailerCode": TIENDA_PRUEBA,
        "productUrl": f"https://www.example.com/p/t21-{n}",
        "title": "Producto sintético T21",
        "brand": "MARCA-SINTETICA",
        "model": "MS-T21",
        "category": "tools",
        "price": {"current": precio, "currency": "USD"},
        "seller": "comercio",
        "condition": "new",
        "availability": {"state": "in_stock"},
        "purchaseMode": "envio",
        "extractedAt": extraida.isoformat(),
        "blocked": False,
    }
    datos.update(cambios)
    return datos


#: El dominio de la ficha sale de la configuración (PAR-02): ninguno se escribe aquí.
_DOMINIO_AMAZON = CONFIG.contenido.retailers["amazon"].domains[0]


def _ficha(extraida: dt.datetime, precio: str = "130.00") -> dict:
    return _comercio(
        0,
        extraida,
        precio,
        retailerCode="amazon",
        productUrl=f"https://www.{_DOMINIO_AMAZON}/dp/T21",
        amazonListing={"buyBoxPrice": precio, "sellersNew": 3, "rankMain": 9000},
    )


def _jsonl(*renglones: dict) -> bytes:
    return ("\n".join(json.dumps(r, ensure_ascii=False) for r in renglones) + "\n").encode()


def test_la_carga_evalua_en_orden_del_archivo_sin_la_ficha_ni_los_duplicados(repo):
    version = _version(repo)
    instante = dt.datetime(2026, 11, 18, 10, 0, tzinfo=ZONA)
    hora = dt.datetime(2026, 11, 18, 8, 0, tzinfo=ZONA)
    contenido = _jsonl(
        _comercio(2, hora),
        _ficha(hora),
        _comercio(1, hora, "90.00"),
        _comercio(2, hora),  # duplicado del renglón 1
    )
    reporte = cargar("t21.jsonl", contenido, repo, version, instante, nuevo_id=Ids())
    assert (reporte.cargados, reporte.duplicados) == (3, 1)
    registros = [repo.leer_evaluacion(i) for i in reporte.evaluaciones]
    # Dos ofertas evaluadas (la ficha de Amazon no, DEC-203), en el orden del archivo.
    urls = [r.entrada.oferta.observacion.product_url for r in registros]
    # La URL vuelve canónica del repositorio (DEC-256: sin ``www.``).
    assert urls == ["https://example.com/p/t21-2", "https://example.com/p/t21-1"]
    # Una observación del mismo archivo posterior en orden ya está en el contexto de la
    # primera (las evaluaciones van después de cargar todo el archivo).
    primera = registros[0].entrada
    assert {r.observacion.product_url for r in primera.historial} == {"https://example.com/p/t21-1"}
    assert len(primera.fichas_amazon) == 1
    for registro in registros:
        assert recalcular(repo, registro.id).coincide


def test_un_rechazo_de_observacion_deja_su_registro_y_no_se_evalua_con_el_motor(repo):
    version = _version(repo)
    instante = dt.datetime(2026, 11, 18, 10, 0, tzinfo=ZONA)
    malo = _comercio(3, instante - dt.timedelta(hours=1), "0.00")
    reporte = cargar("r.jsonl", _jsonl(malo), repo, version, instante, nuevo_id=Ids())
    assert reporte.rechazados == 1 and reporte.evaluaciones == ()


# --- RNF-3: recalcular ----------------------------------------------------------------------


def test_rnf3_recalcular_cada_evaluacion_guardada_da_el_mismo_registro(repo):
    ids = Ids()
    reporte_b34 = _cargar_b34a(repo, ids)
    version = repo.version_configuracion_activa(B34A_EN)
    instante = dt.datetime(2026, 11, 18, 10, 0, tzinfo=ZONA)
    renglones = [
        _comercio(n, dt.datetime(2026, 11, 18 - d, 9, 0, tzinfo=ZONA), f"{100 + n}.00")
        for d in range(1, 5)
        for n in range(1, 4)
    ]
    renglones += [_comercio(1, instante - dt.timedelta(hours=1), "61.00"), _ficha(instante)]
    reporte = cargar("h.jsonl", _jsonl(*renglones), repo, version, instante, nuevo_id=ids)
    evaluaciones = (*reporte_b34.evaluaciones, *reporte.evaluaciones)
    assert len(evaluaciones) == 1 + 13
    for id_evaluacion in evaluaciones:
        resultado = recalcular(repo, id_evaluacion)
        assert resultado.coincide and resultado.diferencias == (), id_evaluacion
        salida = io.StringIO()
        codigo = cli.main(
            ["evaluacion", "recalcular", str(id_evaluacion)],
            repositorio=lambda: repo,
            salida=salida,
            errores=io.StringIO(),
        )
        assert codigo == 0
        assert json.loads(salida.getvalue()) == {
            "evaluationId": str(id_evaluacion),
            "matches": True,
            "differences": [],
        }


class _Alterado:
    """Repositorio que devuelve una evaluación guardada con un monto cambiado."""

    def __init__(self, repo) -> None:
        self.repo = repo

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self.repo, nombre)

    def leer_evaluacion(self, id_: UUID):
        registro = self.repo.leer_evaluacion(id_)
        return dataclasses.replace(registro, costo_compra=D("1.00"))


def test_recalcular_con_un_registro_distinto_sale_con_1_y_la_diferencia(repo):
    reporte = _cargar_b34a(repo)
    id_evaluacion = reporte.evaluaciones[0]
    alterado = _Alterado(repo)
    resultado = recalcular(alterado, id_evaluacion)
    assert not resultado.coincide
    assert [(d.campo, d.guardado, d.recalculado) for d in resultado.diferencias] == [
        ("purchase_cost", '"1.00"', '"79.50"')
    ]
    salida = io.StringIO()
    codigo = cli.main(
        ["evaluacion", "recalcular", str(id_evaluacion)],
        repositorio=lambda: alterado,
        salida=salida,
        errores=io.StringIO(),
    )
    assert codigo == 1
    assert json.loads(salida.getvalue())["differences"] == [
        {"field": "purchase_cost", "stored": '"1.00"', "recalculated": '"79.50"'}
    ]


def test_recalcular_no_existe_o_es_un_rechazo_sale_con_1(repo):
    version = _version(repo)
    instante = dt.datetime(2026, 11, 18, 10, 0, tzinfo=ZONA)
    malo = _comercio(3, instante - dt.timedelta(hours=1), "0.00")
    cargar("r.jsonl", _jsonl(malo), repo, version, instante, nuevo_id=Ids(500))
    id_rechazo = UUID(int=500 + 1)  # 500 es la carga; 501 el registro del rechazo
    assert repo.leer_evaluacion(id_rechazo) is not None
    with pytest.raises(EvaluacionNoRecalculable):
        recalcular(repo, id_rechazo)
    with pytest.raises(EvaluacionNoEncontrada):
        recalcular(repo, UUID(int=999_999))
    for id_evaluacion in (id_rechazo, UUID(int=999_999)):
        errores = io.StringIO()
        codigo = cli.main(
            ["evaluacion", "recalcular", str(id_evaluacion)],
            repositorio=lambda: repo,
            salida=io.StringIO(),
            errores=errores,
        )
        assert codigo == 1
        assert str(id_evaluacion) in errores.getvalue()


def test_recalcular_con_un_id_que_no_es_uuid_sale_con_2():
    errores = io.StringIO()
    codigo = cli.main(
        ["evaluacion", "recalcular", "no-es-un-uuid"],
        repositorio=RepositorioMemoria,
        salida=io.StringIO(),
        errores=errores,
    )
    assert codigo == 2


# --- RNF-2: un parámetro nuevo cambia la evaluación nueva, no la anterior -------------------


def test_rnf2_cambiar_un_parametro_y_cargar_la_configuracion(repo, tmp_path):
    texto_v1 = con_sucursales_prueba(BASE.read_text(encoding="utf-8"))
    texto_v2 = texto_v1.replace(
        'version: "escenarios-base-1"', 'version: "escenarios-base-1-rnf2"', 1
    ).replace("asking_price_factor_pct: 85", "asking_price_factor_pct: 80", 1)
    assert texto_v2.count("asking_price_factor_pct: 80") == 1
    (tmp_path / "v1.yaml").write_text(texto_v1, encoding="utf-8")
    (tmp_path / "v2.yaml").write_text(texto_v2, encoding="utf-8")
    observacion = json.loads((ARCHIVOS / "b34a.jsonl").read_text("utf-8").splitlines()[0])
    observacion["extractedAt"] = "2026-11-16T13:30:00-08:00"  # otra observación, misma URL
    (tmp_path / "b18_nueva.jsonl").write_text(json.dumps(observacion) + "\n", encoding="utf-8")

    def oip(*argumentos: str) -> dict:
        salida = io.StringIO()
        codigo = cli.main(
            list(argumentos), repositorio=lambda: repo, salida=salida, errores=io.StringIO()
        )
        assert codigo == 0, argumentos
        return json.loads(salida.getvalue())

    v1 = oip("config", "cargar", str(tmp_path / "v1.yaml"), "--instante", CONFIG_EN.isoformat())
    oip(
        "cargar",
        str(ARCHIVOS / "local_comparable__b18.csv"),
        "--instante",
        "2026-11-15T20:00-08:00",
    )
    oip("cargar", str(ARCHIVOS / "b34a.jsonl"), "--instante", "2026-11-16T12:00-08:00")
    v2 = oip("config", "cargar", str(tmp_path / "v2.yaml"), "--instante", "2026-11-16T13:00-08:00")
    assert v2["created"] and v2["configVersionId"] != v1["configVersionId"]
    oip("cargar", str(tmp_path / "b18_nueva.jsonl"), "--instante", "2026-11-16T14:00-08:00")

    producto = None
    registros = []
    for instante in ("2026-11-16T12:00-08:00", "2026-11-16T14:00-08:00"):
        momento = dt.datetime.fromisoformat(instante)
        abiertas_o_no = _evaluaciones_al(repo, momento)
        registros.append(abiertas_o_no)
        producto = producto or abiertas_o_no.id_producto
    anterior, nueva = registros
    # La evaluación anterior conserva su versión y su resultado.
    assert anterior.id_version_configuracion == v1["configVersionId"]
    assert anterior.referencias.valor_referencia_usados == D("110.50")  # 130 × 85%
    assert recalcular(repo, anterior.id).coincide
    # La nueva usa la versión cargada sin tocar código: 130 × 80% = 104.00.
    assert nueva.id_version_configuracion == v2["configVersionId"]
    assert nueva.referencias.valor_referencia_usados == D("104.00")
    assert nueva.costo_compra == anterior.costo_compra == D("79.50")
    assert recalcular(repo, nueva.id).coincide


def _evaluaciones_al(repo, instante: dt.datetime) -> RegistroEvaluacion:
    """La evaluación guardada en ``instante`` (busca por las cargas del repositorio)."""
    for registro in _todas_las_evaluaciones(repo):
        if registro.evaluado_en == instante:
            return registro
    raise AssertionError("sin evaluación en ese instante")


def _todas_las_evaluaciones(repo) -> list[RegistroEvaluacion]:
    if isinstance(repo, RepositorioMemoria):
        filas = repo._tablas["evaluation"].filas
        ids = [f["id"] for f in filas]
    else:
        with repo._motor.connect() as conexion:
            ids = [r[0] for r in conexion.execute(text("SELECT id FROM evaluation"))]
    registros = [repo.leer_evaluacion(i) for i in ids]
    return [r for r in registros if isinstance(r, RegistroEvaluacion)]


# --- Contexto "a un instante" y borde de los 90 días (DEC-264, DEC-271) ---------------------

DIA = dt.date(2026, 11, 18)
INSTANTE = dt.datetime(2026, 11, 18, 10, 0, tzinfo=ZONA)
PRODUCTO = UUID(int=10_000)


class Sembrador:
    """Guarda observaciones sintéticas directo en el repositorio (sin cargador): el producto
    y cada publicación se crean con su primera observación."""

    def __init__(self, repo) -> None:
        self.repo = repo
        self.ids = Ids(20_000)
        self.publicaciones: dict[str, UUID] = {}
        self.producto_creado = False

    def observacion(self, datos: dict) -> UUID:
        observacion = leer_observacion({k: v for k, v in datos.items() if k != "recordType"})
        url = observacion.product_url
        publicacion = None
        if url not in self.publicaciones:
            self.publicaciones[url] = self.ids()
            publicacion = Publicacion(
                self.publicaciones[url],
                PRODUCTO,
                observacion.retailer_code,
                url,
                observacion.extracted_at,
                observacion.store_code,
            )
        producto = None
        identificadores: tuple[IdentificadorProducto, ...] = ()
        if not self.producto_creado:
            producto = Producto(PRODUCTO, observacion.extracted_at, "MARCA-SINTETICA", "MS-T21")
            identificadores = (IdentificadorProducto("brand_model", "marca-sintetica|ms-t21"),)
            self.producto_creado = True
        id_ = self.ids()
        nueva = ObservacionNueva(
            registrada=ObservacionRegistrada(observacion, id_, self.publicaciones[url], PRODUCTO),
            identificacion=Identificacion.CONFIRMED,
            clave_idempotencia=f"t21|{id_}",
            origen="worker",
            recibida_en=observacion.extracted_at,
            producto=producto,
            identificadores=identificadores,
            publicacion=publicacion,
        )
        assert self.repo.guardar_observacion(nueva)
        return id_


def test_borde_de_los_90_dias_del_contexto(repo):
    """DEC-264: el contexto empieza a las 00:00 (zona de PAR-01) del día evaluado menos 90
    días (60 del habitual + 30 del episodio, PAR-08). Una observación del día anterior a ese
    no entra (una cadena de episodios que empezó antes no se ve) y el recálculo da el mismo
    registro, porque el ``input_snapshot`` guarda el contexto usado."""
    version = _version(repo)
    assert dias_del_contexto(version) == 90
    sembrador = Sembrador(repo)
    inicio = dt.datetime.combine(DIA - dt.timedelta(days=90), dt.time(0), tzinfo=ZONA)
    # La publicación 1 baja a 80 antes del borde (abriría un episodio) y sigue en 80.
    fuera = [
        sembrador.observacion(_comercio(1, inicio - dt.timedelta(days=2), "100.00")),
        sembrador.observacion(_comercio(1, inicio - dt.timedelta(minutes=1), "80.00")),
    ]
    dentro = [sembrador.observacion(_comercio(1, inicio, "80.00"))]
    for d in range(89, 0, -1):
        momento = dt.datetime.combine(DIA - dt.timedelta(days=d), dt.time(9), tzinfo=ZONA)
        dentro.append(sembrador.observacion(_comercio(2, momento, "100.00")))
        dentro.append(sembrador.observacion(_comercio(3, momento, "100.00")))
    oferta = sembrador.observacion(_comercio(1, INSTANTE - dt.timedelta(hours=1), "80.00"))

    registro = evaluar_observacion(repo, oferta, INSTANTE, version, nuevo_id=Ids(90_000))
    usadas = {u.id for u in registro.observaciones_usadas}
    assert usadas == {*dentro, oferta}
    assert not usadas & set(fuera)
    assert {r.id for r in registro.entrada.historial} == set(dentro)
    # El episodio que abrió la baja de antes del borde no se ve: la primera observación de
    # la publicación en el contexto no es una baja.
    assert registro.referencias.episodio is None
    assert registro.referencias.precio_habitual == D("100.00")
    resultado = recalcular(repo, registro.id)
    assert resultado.coincide
    assert repo.leer_evaluacion(registro.id) == registro


def test_el_contexto_no_trae_nada_posterior_al_instante(repo):
    """design.md §5 y DEC-271: observaciones con ``observed_at ≤ instante``, capturas con
    ``captured_at ≤ instante`` y la configuración de la evaluación."""
    version = _version(repo)
    sembrador = Sembrador(repo)
    antes = sembrador.observacion(_comercio(2, INSTANTE - dt.timedelta(hours=2)))
    despues = sembrador.observacion(_comercio(2, INSTANTE + dt.timedelta(minutes=1)))
    oferta = sembrador.observacion(_comercio(1, INSTANTE - dt.timedelta(hours=1), "80.00"))
    # Una demanda local capturada antes y otra después del instante.
    for capturada, nivel in ((INSTANTE - dt.timedelta(hours=3), "low"), (INSTANTE, "high")):
        renglon = {"recordType": "local_demand", "category": "tools", "level": nivel}
        renglon["date"] = "2026-11-18"
        cargar(
            "d.jsonl", _jsonl(renglon), repo, version, capturada, nuevo_id=Ids(70_000 + len(nivel))
        )
    tarde = INSTANTE - dt.timedelta(minutes=30)
    contexto = armar_contexto(repo, oferta, tarde, version, id_evaluacion=UUID(int=1))
    assert [r.id for r in contexto.historial] == [antes]
    assert despues not in {r.id for r in contexto.historial}
    assert [d.level for d in contexto.demanda_local] == ["low"]
    assert contexto.id_version_configuracion == version.id
    assert contexto.configuracion == version.configuracion
    assert contexto.oferta.id == oferta


def test_armar_contexto_de_una_observacion_que_no_existe(repo):
    version = _version(repo)
    with pytest.raises(EvaluacionNoEncontrada):
        armar_contexto(repo, UUID(int=4242), INSTANTE, version, id_evaluacion=UUID(int=1))
    with pytest.raises(EvaluacionNoEncontrada):
        evaluar_carga(repo, [UUID(int=4242)], INSTANTE, version)
    with pytest.raises(TypeError):
        armar_contexto(
            repo,
            UUID(int=4242),
            dt.datetime(2026, 11, 18),  # noqa: DTZ001 - sin desfase a propósito
            version,
            id_evaluacion=UUID(int=1),
        )


# --- RNF-1: menos de 2 s con el historial sintético de design.md §11 -------------------------


def test_rnf1_evaluar_con_el_historial_grande_tarda_menos_de_2_segundos(repo):
    version = _version(repo)
    sembrador = Sembrador(repo)
    for d in range(90, 0, -1):  # 10 publicaciones × 90 días × 2 observaciones
        dia = DIA - dt.timedelta(days=d)
        for hora in (8, 16):
            momento = dt.datetime.combine(dia, dt.time(hora), tzinfo=ZONA)
            for n in range(1, 11):
                sembrador.observacion(_comercio(n, momento, f"{100 + n}.00"))
    for d in range(59, -1, -1):  # 60 fichas de Amazon
        momento = dt.datetime.combine(DIA - dt.timedelta(days=d), dt.time(7), tzinfo=ZONA)
        sembrador.observacion(_ficha(momento))
    oferta = sembrador.observacion(_comercio(1, INSTANTE - dt.timedelta(hours=1), "60.00"))

    inicio = time.perf_counter()
    registro = evaluar_observacion(repo, oferta, INSTANTE, version, nuevo_id=Ids(90_000))
    transcurrido = time.perf_counter() - inicio

    assert len(registro.entrada.historial) == 1800
    assert len(registro.entrada.fichas_amazon) == 60
    assert len(registro.observaciones_usadas) == 1861
    assert repo.leer_evaluacion(registro.id) == registro
    assert transcurrido < 2.0, f"RNF-1: {transcurrido:.3f} s"


# --- La evaluación del motor y la del ensamblador son la misma -------------------------------


def test_el_ensamblador_solo_arma_llama_al_motor_y_guarda(repo):
    version = _version(repo)
    sembrador = Sembrador(repo)
    sembrador.observacion(_comercio(2, INSTANTE - dt.timedelta(days=1)))
    oferta = sembrador.observacion(_comercio(1, INSTANTE - dt.timedelta(hours=1), "80.00"))
    registro = evaluar_observacion(repo, oferta, INSTANTE, version, nuevo_id=Ids(90_000))
    contexto = armar_contexto(repo, oferta, INSTANTE, version, id_evaluacion=registro.id)
    assert motor.evaluar(contexto) == registro == repo.leer_evaluacion(registro.id)
    assert registro.id_carga is None
    assert registro.id_observacion_oferta == oferta


def test_la_captura_de_otro_tipo_no_entra_al_contexto(repo):
    reporte = _cargar_b34a(repo)
    registro = repo.leer_evaluacion(reporte.evaluaciones[0])
    assert registro.entrada.estimados == () and registro.entrada.msrp == ()
    assert repo.capturas(TipoRegistro.LOCAL_DEMAND, instante=B34A_EN)


def test_solo_entran_las_capturas_y_observaciones_del_producto_de_la_oferta(repo, tmp_path):
    """T12-tester-1 (#34): el motor confía en que el contexto trae solo los comparables del
    producto. El producto de una captura se identifica en la carga como el de una
    observación (design.md §10 punto 7): GTIN válido, si no marca + modelo."""
    ids = Ids()
    version = _version(repo)
    otro = (ARCHIVOS / "local_comparable__b18.csv").read_text("utf-8").replace("DCF840", "DCF850")
    (tmp_path / "local_comparable__otro.csv").write_text(otro, encoding="utf-8")
    cargar_archivo(
        tmp_path / "local_comparable__otro.csv", repo, version, COMPARABLES_EN, nuevo_id=ids
    )
    renglones = [
        {"recordType": "local_estimate", "brand": "DEWALT", "model": "DCF850"}
        | {"price": "500.00", "date": "2026-11-15"},
        {"recordType": "msrp", "brand": "DEWALT", "model": "DCF850"}
        | {"value": "600.00", "source": "sintético", "date": "2026-11-15"},
    ]
    cargar("otro.jsonl", _jsonl(*renglones), repo, version, COMPARABLES_EN, nuevo_id=ids)
    observacion = json.loads((ARCHIVOS / "b34a.jsonl").read_text("utf-8").splitlines()[0])
    observacion |= {"model": "DCF850", "productUrl": "https://offerup.com/item/detail/b18-otro"}
    observacion["extractedAt"] = "2026-11-16T09:00:00-08:00"
    otra = cargar("o.jsonl", _jsonl(observacion), repo, version, COMPARABLES_EN, nuevo_id=ids)
    id_otra = repo.leer_evaluacion(otra.evaluaciones[0]).id_observacion_oferta

    reporte = cargar_archivo(
        ARCHIVOS / "local_comparable__b18.csv", repo, version, COMPARABLES_EN, nuevo_id=ids
    )
    assert reporte.cargados == 3
    b34a = cargar_archivo(ARCHIVOS / "b34a.jsonl", repo, version, B34A_EN, nuevo_id=ids)
    registro = repo.leer_evaluacion(b34a.evaluaciones[0])
    entrada = registro.entrada
    # Solo los 3 comparables de DCF840: ninguno de DCF850 (mismo precio, ciudad y estado).
    assert len(entrada.comparables) == 3
    assert {c.model for c in entrada.comparables} == {"DCF840"}
    assert entrada.estimados == () and entrada.msrp == ()
    # La observación del otro modelo no entra al contexto ni a observations_used.
    assert id_otra not in {r.id for r in entrada.historial}
    assert id_otra not in {u.id for u in registro.observaciones_usadas}
    _afirmar_b18(registro)
    assert recalcular(repo, registro.id).coincide
