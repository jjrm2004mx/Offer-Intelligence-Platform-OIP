"""Pruebas independientes de oip-tester para T21 (ensamblador, carga que evalúa, recálculo;
CMP-21, CMP-08, CMP-22; RNF-1, RNF-2, RNF-3).

Escritas desde REQ-2026-0001 v2.9 (§3.1 punto 10, §3.2, §3.2.6, §7, §12; escenarios B34 a y
B18), design.md (§2, §3, §4 TAB-10 y TAB-11, §5, CTR-05, CTR-06, CTR-07, §11, §12) y las
DEC-203, DEC-250, DEC-264 y DEC-271, **sin ver la implementación** (DEC-252, etapa 2): de
``persistencia/ensamblador.py``, del cargador y de la CLI solo se usan las firmas públicas.
Los valores esperados salen del REQ o se calculan a mano en el docstring de cada prueba.

Fixtures sintéticos armados aquí. Comercios: los sintéticos ``tienda-prueba`` y
``tienda-prueba-2`` (example.com). El dominio de la plataforma de particulares y el de la
ficha de Amazon se leen de la configuración (PAR-02, PAR-09), no se escriben en la prueba.
Ninguna prueba abre una URL; el instante siempre es explícito (zona de PAR-01); los ids son
deterministas.

Las pruebas con ``@pytest.mark.integracion`` corren también contra PostgreSQL y se saltan
sin ``OIP_TEST_DATABASE_URL`` (DEC-233); esa base debe ser desechable.

Fuera de alcance (T22): la reevaluación de oportunidades abiertas. DEC-278 (``--instante``
no cambia un ``loaded_at`` ya registrado) es una observación abierta del #34 y no se prueba
aquí.
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

from config_tienda_prueba import (
    BASE,
    DOMINIO_PRUEBA,
    DOMINIO_PRUEBA_2,
    TIENDA_PRUEBA,
    TIENDA_PRUEBA_2,
    con_sucursales_prueba,
    configuracion_con_sucursales_prueba,
)
from oip import cli
from oip.catalogos import (
    CalidadPrecio,
    Canal,
    Categoria,
    EstadoCanal,
    Identificacion,
    Motivo,
    Resultado,
)
from oip.configuracion import cargar_configuracion_texto
from oip.entradas.cargador import cargar, clave_idempotencia
from oip.entradas.contrato import leer_observacion
from oip.entradas.validacion import url_canonica
from oip.evaluacion import motor
from oip.evaluacion.contexto import ContextoEvaluacion, ObservacionRegistrada
from oip.persistencia.ensamblador import (
    Diferencia,
    ErrorEnsamblador,
    EvaluacionNoEncontrada,
    EvaluacionNoRecalculable,
    ResultadoRecalculo,
    armar_contexto,
    evaluar_observacion,
    recalcular,
)
from oip.persistencia.repositorios import (
    ErrorRepositorio,
    ObservacionNueva,
    Producto,
    Publicacion,
    RegistroRechazo,
    RepositorioMemoria,
)

D = Decimal
RAIZ = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
TIJUANA = ZoneInfo("America/Tijuana")
CONFIG = configuracion_con_sucursales_prueba()
PARAMS = CONFIG.contenido

#: Comercio de la ficha de Amazon y su dominio, leídos de PAR-02 (no se escriben aquí).
FICHA = next(c for c, r in PARAMS.retailers.items() if r.amazon_listing)
DOMINIO_FICHA = PARAMS.retailers[FICHA].domains[0]
#: Plataforma permitida de particulares sin prefijo de ruta (PAR-09).
PLATAFORMA = next(p for p in PARAMS.private_sellers.platforms.values() if not p.path_prefix)

CONFIG_EN = dt.datetime(2026, 11, 1, tzinfo=dt.UTC)
#: B18: la publicación se capturó el 2026-11-16 a las 10:00 (Tijuana).
COMPARABLES_EN = dt.datetime(2026, 11, 16, 10, 30, tzinfo=TIJUANA)
INSTANTE = dt.datetime(2026, 11, 16, 12, 0, tzinfo=TIJUANA)

TIPO_DESCONOCIDO = "TIPO DE REGISTRO DESCONOCIDO"


def faltante(campo: str) -> str:
    return f"CAMPO OBLIGATORIO FALTANTE ({campo})"


class Ids:
    """``nuevo_id`` determinista; guarda los ids que dio."""

    def __init__(self, base: int = 0) -> None:
        self.n = base
        self.dados: list[UUID] = []

    def __call__(self) -> UUID:
        self.n += 1
        nuevo = UUID(int=self.n)
        self.dados.append(nuevo)
        return nuevo


# --- Repositorio: memoria y, con marcador, PostgreSQL ---------------------------------------

_VARIABLE = "OIP_TEST_DATABASE_URL"


def _url():
    from sqlalchemy.engine import make_url

    valor = os.environ.get(_VARIABLE, "").strip()
    if not valor:
        pytest.skip(f"sin {_VARIABLE}: las pruebas de integración se saltan (DEC-233)")
    url = make_url(valor)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    return url


def _limpiar(motor_db) -> None:
    from sqlalchemy import text

    from oip.persistencia import tablas

    nombres = ", ".join([*tablas.metadata.tables, "alembic_version"])
    with motor_db.begin() as conexion:
        conexion.execute(text("DROP VIEW IF EXISTS open_opportunity"))
        conexion.execute(text(f"DROP TABLE IF EXISTS {nombres} CASCADE"))


def _migrar(motor_db) -> None:
    from alembic import command
    from alembic.config import Config

    with motor_db.begin() as conexion:
        config = Config(str(RAIZ / "alembic.ini"))
        config.attributes["connection"] = conexion
        command.upgrade(config, "head")


@pytest.fixture(params=["memoria", pytest.param("postgres", marks=pytest.mark.integracion)])
def repo_vacio(request):
    """Un repositorio vacío: ``RepositorioMemoria`` y, en integración, ``RepositorioPostgres``
    migrado a ``head`` sobre la base desechable de ``OIP_TEST_DATABASE_URL``."""
    if request.param == "memoria":
        yield RepositorioMemoria()
        return
    from oip.persistencia.repositorios import RepositorioPostgres, crear_motor

    motor_db = crear_motor(_url())
    _limpiar(motor_db)
    try:
        _migrar(motor_db)
        yield RepositorioPostgres(motor_db)
    finally:
        _limpiar(motor_db)
        motor_db.dispose()


def con_version(repo, config=CONFIG, en=CONFIG_EN):
    version, _ = repo.guardar_version_configuracion(config, cargada_en=en)
    return version


# --- Renglones sintéticos -----------------------------------------------------------------


def jsonl(*renglones: dict[str, Any]) -> bytes:
    return b"".join(json.dumps(r, ensure_ascii=False).encode("utf-8") + b"\n" for r in renglones)


def b18(**cambios: Any) -> dict[str, Any]:
    """B34 (a) (1): la publicación de B18 como observación: atornillador DEWALT DCF840 usado,
    de un particular en San Diego, $70, modelo + marca y mismo contenido; ``seller:
    particular``, ``availability.state: listed``, ``pickupLocation: san_diego`` y enlace
    ``https`` de una plataforma permitida."""
    datos: dict[str, Any] = {
        "recordType": "observation",
        "schemaVersion": "3.1",
        "retailerCode": "particular",
        "productUrl": f"https://{PLATAFORMA.domains[0]}/item/detail/b18-t21",
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


#: B34 (a) (2): un ``local_comparable`` en MXN **sin tipo de cambio**.
COMPARABLE_MXN = {
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
#: B34 (a) (3): un ``local_demand`` de ``beauty``, media.
DEMANDA_BEAUTY = {
    "recordType": "local_demand",
    "category": "beauty",
    "level": "medium",
    "date": "2026-11-16",
}
#: B34 (a) (4): un registro con ``recordType: coupon``.
CUPON = {"recordType": "coupon", "code": "SINTETICO-10"}

#: B18: usados comparables (precios pedidos) $120, $130 y $140, ya cargados (fixture de T08b).
CSV_B18 = (FIXTURES / "archivos" / "local_comparable__b18.csv").read_bytes()


def comparables_json(fecha: str = "2026-11-15") -> list[dict[str, Any]]:
    """Los mismos tres comparables de B18, como renglones JSON Lines."""
    return [
        {
            "recordType": "local_comparable",
            "brand": "DEWALT",
            "model": "DCF840",
            "condition": "used",
            "askingPrice": precio,
            "currency": "USD",
            "city": "san_diego",
            "date": fecha,
            "sold": False,
        }
        for precio in ("120.00", "130.00", "140.00")
    ]


def comercio(ruta: str, modelo: str, extraido: str, precio: str = "49.99", **cambios: Any):
    """Observación válida de ``tienda-prueba`` (example.com), nueva y vendida por el
    comercio."""
    datos: dict[str, Any] = {
        "recordType": "observation",
        "schemaVersion": "3.1",
        "retailerCode": TIENDA_PRUEBA,
        "productUrl": f"https://www.{DOMINIO_PRUEBA}{ruta}",
        "title": f"Producto sintético T21 {modelo}",
        "brand": "MARCA-T21",
        "model": modelo,
        "category": "tools",
        "price": {"current": precio, "currency": "USD"},
        "seller": "comercio",
        "condition": "new",
        "availability": {"state": "in_stock"},
        "purchaseMode": "envio",
        "extractedAt": extraido,
        "blocked": False,
    }
    datos.update(cambios)
    return datos


def ficha_amazon(modelo: str, extraido: str, buy_box: str = "119.00") -> dict[str, Any]:
    """Observación de la ficha de Amazon (``amazonListing`` no nulo) del mismo producto."""
    return {
        "recordType": "observation",
        "schemaVersion": "3.1",
        "retailerCode": FICHA,
        "productUrl": f"https://www.{DOMINIO_FICHA}/dp/T21{modelo}",
        "title": f"Producto sintético T21 {modelo}",
        "brand": "MARCA-T21",
        "model": modelo,
        "category": "tools",
        "price": {"current": buy_box, "currency": "USD"},
        "seller": "comercio",
        "condition": "new",
        "availability": {"state": "in_stock_confirmed"},
        "purchaseMode": "envio",
        "amazonListing": {
            "buyBoxPrice": buy_box,
            "rankMain": 6000,
            "sellersNew": 5,
            "boughtLastMonth": 200,
        },
        "extractedAt": extraido,
        "blocked": False,
    }


def id_observacion(repo, renglon: dict[str, Any]) -> UUID:
    """El id guardado de un renglón de observación, por su clave de idempotencia (TAB-08)."""
    datos = {k: v for k, v in renglon.items() if k != "recordType"}
    encontrado = repo.observacion_por_clave(clave_idempotencia(leer_observacion(datos)))
    assert encontrado is not None, "la observación no quedó guardada"
    return encontrado


def canal(registro, cual: Canal):
    encontrados = [c for c in registro.canales if c.canal is cual]
    assert len(encontrados) == 1, f"se esperaba un canal {cual}"
    return encontrados[0]


def cerca(valor: Decimal | None, esperado: Decimal) -> bool:
    """Porcentajes sin redondear (DEC-060): igualdad salvo el último dígito del contexto."""
    assert isinstance(valor, Decimal), f"se esperaba Decimal, llegó {type(valor).__name__}"
    return abs(valor - esperado) < D("1e-20")


def rechazos(reporte) -> list[tuple[int, str]]:
    return [(r.renglon, r.motivo) for r in reporte.rechazos]


def cargar_b34_a(repo, version, ids: Ids):
    """El "Dado" de B34 (a): los comparables de B18 ya cargados y, después, el JSON Lines de
    4 registros (1) B18, (2) comparable MXN sin tipo de cambio, (3) demanda local de beauty,
    (4) ``recordType: coupon``."""
    previo = cargar(
        "local_comparable__b18.csv", CSV_B18, repo, version, COMPARABLES_EN, nuevo_id=ids
    )
    assert (previo.cargados, previo.rechazados) == (3, 0)
    assert previo.evaluaciones == ()  # una carga sin observaciones no evalúa nada
    contenido = jsonl(b18(), COMPARABLE_MXN, DEMANDA_BEAUTY, CUPON)
    return cargar("b34a.jsonl", contenido, repo, version, INSTANTE, nuevo_id=ids)


def afirmar_resultado_b18(registro) -> None:
    """Las afirmaciones de B18 (REQ v2.9): valor de referencia 130 × 85% = $110.50; real
    36.7%; compra 70 + 9.50 = $79.50 sin impuesto; calidad no aplica; Amazon cerrado (usado);
    local: venta $99.45, neto $10.45, castigo $9.95, ajustado $0.50, sin nivel; motivos
    PARTICULAR y RIESGO DE PROCEDENCIA → REVISION_MANUAL, principal PARTICULAR."""
    assert registro.resultado is Resultado.REVISION_MANUAL
    assert registro.motivo_principal is Motivo.PARTICULAR
    assert registro.motivos == (Motivo.PARTICULAR, Motivo.RIESGO_DE_PROCEDENCIA)
    assert registro.motivo_rechazo is None
    assert registro.referencias.valor_referencia_usados == D("110.50")
    assert cerca(registro.descuento_real, (D("110.50") - D("70")) / D("110.50") * 100)
    assert registro.costo_compra == D("79.50")
    assert registro.calidad_precio is CalidadPrecio.NO_APLICA
    amazon = canal(registro, Canal.AMAZON)
    assert amazon.estado is EstadoCanal.CERRADO
    assert amazon.margen_ajustado is None and amazon.nivel_calculado is None
    local = canal(registro, Canal.LOCAL)
    assert local.estado is EstadoCanal.DISPONIBLE
    assert local.precio_venta == D("99.45")
    assert local.margen_neto == D("10.45")
    assert local.castigo == D("9.95")
    assert local.margen_ajustado == D("0.50")
    assert local.nivel is None
    assert registro.nivel_aviso is None and registro.canal_aviso is None


# =========================================================================================
# Escenario B34 (a) — REQ v2.9 "B34 — Carga por archivo"
# =========================================================================================


@pytest.mark.scenario("B34 (a)")
def test_b34_a_carga_mixta_y_la_observacion_se_evalua_con_el_resultado_de_b18(repo_vacio):
    """Se cargan (1) y (3); (2) se rechaza con ``CAMPO OBLIGATORIO FALTANTE (tipo de
    cambio)``, que design.md §6 escribe ``(exchangeRate)``, y (4) con ``TIPO DE REGISTRO
    DESCONOCIDO``; los rechazos no detienen la carga. Reporte: 2 cargados y 2 rechazados, uno
    por cada motivo. La observación (1) dispara su evaluación, con el resultado de B18."""
    repo = repo_vacio
    version = con_version(repo)
    ids = Ids()

    reporte = cargar_b34_a(repo, version, ids)

    assert (reporte.cargados, reporte.rechazados, reporte.duplicados) == (2, 2, 0)
    assert rechazos(reporte) == [(2, faltante("exchangeRate")), (4, TIPO_DESCONOCIDO)]
    assert dict(reporte.rechazados_por_motivo) == {
        faltante("exchangeRate"): 1,
        TIPO_DESCONOCIDO: 1,
    }
    json_ = reporte.a_json()
    assert (json_["loaded"], json_["rejected"]) == (2, 2)
    assert "evaluaciones" not in json_ and "evaluations" not in json_  # CTR-05 sin cambio

    # Una sola evaluación: la de la observación (1); su id lo dio el mismo nuevo_id.
    assert len(reporte.evaluaciones) == 1
    (id_eval,) = reporte.evaluaciones
    assert id_eval in ids.dados
    registro = repo.leer_evaluacion(id_eval)
    assert registro is not None and not isinstance(registro, RegistroRechazo)
    afirmar_resultado_b18(registro)

    # Registro de REQ §7 / TAB-10: fecha = instante de la carga, la observación evaluada,
    # la carga, la versión de configuración y las versiones de cada RN (PAR-01).
    id_oferta = id_observacion(repo, b18())
    assert registro.id == id_eval
    assert registro.evaluado_en == INSTANTE
    assert registro.id_observacion_oferta == id_oferta
    assert registro.id_carga == reporte.id_carga
    assert registro.id_version_configuracion == version.id
    assert dict(registro.versiones_rn) == dict(PARAMS.general.rn_versions)
    assert registro.entrada.oferta.id == id_oferta

    # observations_used: cada observación del contexto con su fecha (= extractedAt).
    usadas = {u.id: u.fecha for u in registro.observaciones_usadas}
    assert usadas[id_oferta] == dt.datetime(2026, 11, 16, 10, 0, tzinfo=TIJUANA)
    del_contexto = {
        o.id: o.observacion.extracted_at
        for o in (
            registro.entrada.oferta,
            *registro.entrada.historial,
            *registro.entrada.fichas_amazon,
        )
    }
    assert usadas == del_contexto

    # El contexto vio los 3 comparables de B18 y no el rechazado en MXN.
    assert len(registro.entrada.comparables) == 3


@pytest.mark.scenario("B34 (a)")
def test_b34_a_el_registro_guardado_se_recalcula_igual_rnf_3(repo_vacio):
    """RNF-3 (REQ §12): el registro de B34 (a) se recalcula desde su ``input_snapshot`` con el
    mismo resultado; ``recalcular`` no escribe."""
    repo = repo_vacio
    version = con_version(repo)
    reporte = cargar_b34_a(repo, version, Ids())
    (id_eval,) = reporte.evaluaciones
    antes = repo.leer_evaluacion(id_eval).a_json()

    resultado = recalcular(repo, id_eval)

    assert resultado == ResultadoRecalculo(id_eval, True, ())
    assert resultado.a_json() == {
        "evaluationId": str(id_eval),
        "matches": True,
        "differences": [],
    }
    assert repo.leer_evaluacion(id_eval).a_json() == antes


# =========================================================================================
# design.md §2: la carga evalúa al final, en orden, solo observaciones nuevas de un origen
# de compra
# =========================================================================================


def test_la_evaluacion_va_despues_de_cargar_todo_el_archivo():
    """design.md §2: las evaluaciones se hacen después de cargar todo el archivo, para que
    una captura del mismo archivo ya cuente. La publicación de B18 va **antes** que sus 3
    comparables en el mismo archivo y aun así se evalúa con ellos (valor de referencia
    $110.50, resultado de B18)."""
    repo = RepositorioMemoria()
    version = con_version(repo)
    contenido = jsonl(b18(), *comparables_json())

    reporte = cargar("b18_y_comparables.jsonl", contenido, repo, version, INSTANTE, nuevo_id=Ids())

    assert (reporte.cargados, reporte.rechazados) == (4, 0)
    (id_eval,) = reporte.evaluaciones
    afirmar_resultado_b18(repo.leer_evaluacion(id_eval))


def test_orden_del_archivo_sin_ficha_de_amazon_rechazos_ni_duplicados():
    """REQ §3.1 punto 10 y DEC-203: se evalúa cada observación nueva de un origen de compra;
    la ficha de Amazon no se evalúa como oferta. design.md §2: en el orden del archivo; un
    duplicado no se evalúa otra vez; un rechazo deja su ``RECHAZADA_VALIDACION`` (DEC-250) y
    no es una evaluación de la carga."""
    repo = RepositorioMemoria()
    version = con_version(repo)
    ids = Ids()
    obs_b = comercio("/p/t21-b", "T21-B", "2026-11-16T09:00:00-08:00")
    obs_a = comercio("/p/t21-a", "T21-A", "2026-11-16T09:30:00-08:00")
    ficha = ficha_amazon("T21-B", "2026-11-16T09:10:00-08:00")
    cero = comercio(
        "/p/t21-cero",
        "T21-C",
        "2026-11-16T09:20:00-08:00",
        price={"current": "0.00", "currency": "USD"},
    )
    contenido = jsonl(obs_b, ficha, cero, obs_a, obs_b)

    reporte = cargar("orden.jsonl", contenido, repo, version, INSTANTE, nuevo_id=ids)

    assert (reporte.cargados, reporte.rechazados, reporte.duplicados) == (3, 1, 1)
    assert rechazos(reporte) == [(3, "PRECIO INVÁLIDO")]
    # B (renglón 1) antes que A (renglón 4), aunque A no sea la más reciente ni la primera.
    registros = [repo.leer_evaluacion(i) for i in reporte.evaluaciones]
    assert [r.id_observacion_oferta for r in registros] == [
        id_observacion(repo, obs_b),
        id_observacion(repo, obs_a),
    ]
    assert all(r.evaluado_en == INSTANTE for r in registros)
    assert id_observacion(repo, ficha) not in {r.id_observacion_oferta for r in registros}
    # El RECHAZADA_VALIDACION existe, pero no está entre las evaluaciones de la carga.
    rechazo = [r for r in map(repo.leer_evaluacion, ids.dados) if isinstance(r, RegistroRechazo)]
    assert len(rechazo) == 1
    assert rechazo[0].id not in reporte.evaluaciones

    # El mismo archivo otra vez: todo duplicado, nada se evalúa.
    otra = cargar(
        "orden.jsonl", contenido, repo, version, INSTANTE + dt.timedelta(hours=1), nuevo_id=ids
    )
    assert otra.cargados == 0 and otra.evaluaciones == ()


def test_la_misma_carga_con_el_mismo_nuevo_id_da_las_mismas_evaluaciones():
    """CMP-08: con un ``nuevo_id`` determinista, la misma carga da el mismo resultado, también
    los ids de las evaluaciones y sus registros (design.md §12: deterministas)."""
    salidas = []
    for _ in range(2):
        repo = RepositorioMemoria()
        version = con_version(repo)
        reporte = cargar_b34_a(repo, version, Ids())
        salidas.append(
            (reporte.evaluaciones, [repo.leer_evaluacion(i).a_json() for i in reporte.evaluaciones])
        )
    assert salidas[0] == salidas[1]


# =========================================================================================
# RNF-3: recalcular (CTR-06, DEC-250)
# =========================================================================================


def _alterado(registro, nuevo_id: UUID, **cambios):
    """Una copia del registro con otro id (el de su entrada también) y los cambios dados:
    simula un registro guardado que ya no coincide con su ``input_snapshot``."""
    entrada = dataclasses.replace(registro.entrada, id_evaluacion=nuevo_id)
    return dataclasses.replace(registro, id=nuevo_id, entrada=entrada, **cambios)


def test_recalcular_dice_que_campos_no_coinciden():
    """CTR-07: ``recalcular`` compara el registro guardado con el recalculado; si no
    coincide, dice en qué campos (nombre de TAB-10 o ``canales[<canal>].<campo>`` de TAB-11)
    con los dos valores en el JSON canónico de CTR-06."""
    repo = RepositorioMemoria()
    version = con_version(repo)
    (id_eval,) = cargar_b34_a(repo, version, Ids()).evaluaciones
    original = repo.leer_evaluacion(id_eval)
    otro = UUID(int=0x7210_0001)
    local = canal(original, Canal.LOCAL)
    canales = tuple(
        dataclasses.replace(c, margen_ajustado=D("0.60")) if c is local else c
        for c in original.canales
    )
    repo.guardar_evaluacion(_alterado(original, otro, costo_compra=D("79.51"), canales=canales))

    resultado = recalcular(repo, otro)

    assert resultado.id_evaluacion == otro
    assert resultado.coincide is False
    por_campo = {d.campo: d for d in resultado.diferencias}
    assert set(por_campo) == {"purchase_cost", "canales[local].adjusted_margin"}
    assert "79.51" in por_campo["purchase_cost"].guardado
    assert "79.50" in por_campo["purchase_cost"].recalculado
    assert "0.60" in por_campo["canales[local].adjusted_margin"].guardado
    assert "0.50" in por_campo["canales[local].adjusted_margin"].recalculado
    json_ = resultado.a_json()
    assert json_["evaluationId"] == str(otro) and json_["matches"] is False
    assert {d["field"] for d in json_["differences"]} == set(por_campo)
    assert all(set(d) == {"field", "stored", "recalculated"} for d in json_["differences"])
    # La original sigue coincidiendo.
    assert recalcular(repo, id_eval).coincide is True


def test_recalcular_un_rechazo_o_una_evaluacion_que_no_existe():
    """DEC-250 (4): un ``RECHAZADA_VALIDACION`` no se recalcula (no tiene
    ``input_snapshot``). Una evaluación que no existe → ``EvaluacionNoEncontrada``, que
    también es ``LookupError``."""
    repo = RepositorioMemoria()
    version = con_version(repo)
    ids = Ids()
    cero = comercio(
        "/p/t21-cero",
        "T21-C",
        "2026-11-16T09:20:00-08:00",
        price={"current": "0.00", "currency": "USD"},
    )
    reporte = cargar("rechazo.jsonl", jsonl(cero), repo, version, INSTANTE, nuevo_id=ids)
    assert reporte.evaluaciones == ()
    (rechazo,) = [r for r in map(repo.leer_evaluacion, ids.dados) if isinstance(r, RegistroRechazo)]

    with pytest.raises(EvaluacionNoRecalculable):
        recalcular(repo, rechazo.id)
    with pytest.raises(EvaluacionNoEncontrada):
        recalcular(repo, UUID(int=0xDEAD))
    with pytest.raises(LookupError):
        recalcular(repo, UUID(int=0xDEAD))
    assert issubclass(EvaluacionNoRecalculable, ErrorEnsamblador)


def test_resultado_recalculo_a_json():
    """CTR-07 / interfaz: ``{"evaluationId", "matches", "differences": [{"field", "stored",
    "recalculated"}]}``, listo para ``json.dumps``."""
    id_ = UUID(int=7)
    resultado = ResultadoRecalculo(id_, False, (Diferencia("result", '"A"', '"B"'),))
    json_ = resultado.a_json()
    assert json_ == {
        "evaluationId": str(id_),
        "matches": False,
        "differences": [{"field": "result", "stored": '"A"', "recalculated": '"B"'}],
    }
    json.dumps(json_)


# =========================================================================================
# CLI: oip evaluacion recalcular <id> (CTR-07, CMP-22)
# =========================================================================================


def _sin_reloj():
    raise AssertionError("oip evaluacion recalcular no lee el reloj")


def _cli(repo, *argv: str) -> tuple[int, str, str]:
    salida, errores = io.StringIO(), io.StringIO()
    codigo = cli.main(
        list(argv), repositorio=lambda: repo, reloj=_sin_reloj, salida=salida, errores=errores
    )
    return codigo, salida.getvalue(), errores.getvalue()


def test_cli_recalcular_coincide_sale_0_y_no_coincide_sale_1():
    repo = RepositorioMemoria()
    version = con_version(repo)
    (id_eval,) = cargar_b34_a(repo, version, Ids()).evaluaciones

    codigo, salida, _ = _cli(repo, "evaluacion", "recalcular", str(id_eval))
    assert codigo == 0
    assert json.loads(salida) == {"evaluationId": str(id_eval), "matches": True, "differences": []}

    otro = UUID(int=0x7210_0002)
    original = repo.leer_evaluacion(id_eval)
    repo.guardar_evaluacion(_alterado(original, otro, costo_compra=D("80.00")))
    codigo, salida, _ = _cli(repo, "evaluacion", "recalcular", str(otro))
    assert codigo == 1
    json_ = json.loads(salida)
    assert json_["matches"] is False
    assert [d["field"] for d in json_["differences"]] == ["purchase_cost"]


def test_cli_recalcular_errores():
    """Sale con 1 si la evaluación no existe, si es ``RECHAZADA_VALIDACION`` o si falla el
    repositorio (mensaje en la salida de errores); con 2 si el id no es un UUID."""
    repo = RepositorioMemoria()
    version = con_version(repo)
    ids = Ids()
    cero = comercio(
        "/p/t21-cero",
        "T21-C",
        "2026-11-16T09:20:00-08:00",
        price={"current": "0.00", "currency": "USD"},
    )
    cargar("rechazo.jsonl", jsonl(cero), repo, version, INSTANTE, nuevo_id=ids)
    (rechazo,) = [r for r in map(repo.leer_evaluacion, ids.dados) if isinstance(r, RegistroRechazo)]

    codigo, _, errores = _cli(repo, "evaluacion", "recalcular", str(UUID(int=0xDEAD)))
    assert codigo == 1 and errores.strip()
    codigo, _, errores = _cli(repo, "evaluacion", "recalcular", str(rechazo.id))
    assert codigo == 1 and errores.strip()
    codigo, _, _ = _cli(repo, "evaluacion", "recalcular", "no-es-un-uuid")
    assert codigo == 2

    class RepositorioQueFalla(RepositorioMemoria):
        def leer_evaluacion(self, id_):
            raise ErrorRepositorio("falla sintética del repositorio")

    codigo, _, errores = _cli(RepositorioQueFalla(), "evaluacion", "recalcular", str(UUID(int=1)))
    assert codigo == 1 and errores.strip()


# =========================================================================================
# Contexto "a un instante" (design.md §3 y §5; DEC-264, DEC-271)
# =========================================================================================

HOY = dt.date(2026, 11, 18)
PRODUCTO = UUID(int=0x7210_A000)
PUB_TIENDA = UUID(int=0x7210_A001)
PUB_FICHA = UUID(int=0x7210_A002)


def _momento(dia: int, hora: int = 10) -> dt.datetime:
    fecha = HOY + dt.timedelta(days=dia)
    return dt.datetime(fecha.year, fecha.month, fecha.day, hora, tzinfo=TIJUANA)


INSTANTE_HOY = _momento(0, 12)


def _datos_tienda(
    dia: int,
    precio: str,
    ruta: str = "/p/t21-ctx",
    comercio_: str = TIENDA_PRUEBA,
    dominio: str = DOMINIO_PRUEBA,
    hora: int = 10,
) -> dict[str, Any]:
    return {
        "schemaVersion": "3.1",
        "retailerCode": comercio_,
        "productUrl": f"https://www.{dominio}{ruta}",
        "title": "Producto sintético T21 contexto",
        "brand": "MARCA-T21",
        "model": "T21-CTX",
        "category": "tools",
        "price": {"current": precio, "currency": "USD"},
        "seller": "comercio",
        "condition": "new",
        "availability": {"state": "in_stock"},
        "purchaseMode": "envio",
        "extractedAt": _momento(dia, hora).isoformat(),
        "blocked": False,
    }


def _datos_ficha(dia: int, buy_box: str = "119.00", hora: int = 10) -> dict[str, Any]:
    datos = ficha_amazon("T21-CTX", _momento(dia, hora).isoformat(), buy_box)
    datos.pop("recordType")
    return datos


class Guardador:
    """Guarda observaciones directo en el repositorio (origen ``worker``), sin pasar por la
    carga: así un historial grande no dispara una evaluación por renglón. Crea el producto
    y cada publicación la primera vez."""

    def __init__(self, repo, base: int) -> None:
        self.repo = repo
        self.n = base
        self.publicaciones: set[UUID] = set()
        self.producto_creado = False

    def __call__(self, datos: dict[str, Any], id_pub: UUID, comercio_: str) -> UUID:
        observacion = leer_observacion(datos)
        self.n += 1
        id_obs = UUID(int=self.n)
        producto = None
        if not self.producto_creado:
            producto = Producto(
                id=PRODUCTO,
                creado_en=observacion.extracted_at,
                marca="MARCA-T21",
                modelo="T21-CTX",
                categoria=Categoria("tools"),
            )
            self.producto_creado = True
        publicacion = None
        if id_pub not in self.publicaciones:
            publicacion = Publicacion(
                id=id_pub,
                id_producto=PRODUCTO,
                comercio=comercio_,
                url_canonica=url_canonica(datos["productUrl"]),
                vista_por_primera_vez=observacion.extracted_at,
            )
            self.publicaciones.add(id_pub)
        guardada = self.repo.guardar_observacion(
            ObservacionNueva(
                registrada=ObservacionRegistrada(observacion, id_obs, id_pub, PRODUCTO),
                identificacion=Identificacion.CONFIRMED,
                clave_idempotencia=f"t21|{id_obs}",
                origen="worker",
                recibida_en=observacion.extracted_at,
                producto=producto,
                publicacion=publicacion,
            )
        )
        assert guardada
        return id_obs

    def tienda(self, dia: int, precio: str, **kw: Any) -> UUID:
        return self(
            _datos_tienda(dia, precio, **kw),
            PUB_TIENDA,
            TIENDA_PRUEBA,
        )

    def ficha(self, dia: int, buy_box: str = "119.00") -> UUID:
        return self(_datos_ficha(dia, buy_box), PUB_FICHA, FICHA)


def test_armar_contexto_errores_de_entrada():
    """``TypeError`` si el instante no lleva desfase (sin zona de la máquina, design.md §12);
    ``EvaluacionNoEncontrada`` si la observación no existe."""
    repo = RepositorioMemoria()
    version = con_version(repo)
    id_oferta = Guardador(repo, 0x7210_B000).tienda(0, "99.00")
    with pytest.raises(TypeError):
        armar_contexto(
            repo,
            id_oferta,
            dt.datetime(2026, 11, 18, 12),  # noqa: DTZ001 (a propósito)
            version,
            id_evaluacion=UUID(int=1),
        )
    with pytest.raises(EvaluacionNoEncontrada):
        armar_contexto(repo, UUID(int=0xBEEF), INSTANTE_HOY, version, id_evaluacion=UUID(int=1))
    with pytest.raises(EvaluacionNoEncontrada):
        evaluar_observacion(repo, UUID(int=0xBEEF), INSTANTE_HOY, version)


def test_armar_contexto_ventanas_de_observaciones_y_fichas():
    """design.md §3 y §5: nada posterior al instante; observaciones del producto de los 90
    días (60 de ventana + 30 de episodio, PAR-08); las fichas de los últimos 59 días entran.
    Se evitan los bordes exactos (89 y 91 días). El borde de 60 días de las fichas va en
    ``test_armar_contexto_fichas_de_amazon_solo_de_60_dias``."""
    repo = RepositorioMemoria()
    version = con_version(repo)
    g = Guardador(repo, 0x7210_C000)
    viejas = [g.tienda(-120, "129.00"), g.tienda(-91, "129.00")]
    dentro = [g.tienda(-89, "129.00"), g.tienda(-30, "119.00"), g.tienda(-1, "109.00")]
    id_oferta = g.tienda(0, "99.00")
    futura = g.tienda(1, "89.00")
    ficha_vieja = g.ficha(-61)
    fichas_dentro = [g.ficha(-59), g.ficha(-1)]
    ficha_futura = g.ficha(1)
    id_eval = UUID(int=0x7210_C0FF)

    ctx = armar_contexto(repo, id_oferta, INSTANTE_HOY, version, id_evaluacion=id_eval)

    assert ctx.oferta.id == id_oferta
    assert ctx.instante == INSTANTE_HOY
    assert ctx.id_evaluacion == id_eval
    assert ctx.id_version_configuracion == version.id
    assert ctx.configuracion == version.configuracion
    historial = {o.id for o in ctx.historial if o.observacion.amazon_listing is None}
    assert set(dentro) <= historial
    assert historial.isdisjoint({*viejas, futura})
    fichas = {o.id for o in ctx.fichas_amazon}
    assert set(fichas_dentro) <= fichas
    assert ficha_futura not in fichas
    for o in (*ctx.historial, *ctx.fichas_amazon):
        assert o.observacion.extracted_at <= INSTANTE_HOY
    assert ficha_vieja is not None  # su ventana se prueba aparte (contradicción de fuentes)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Contradicción de fuentes, no defecto (DEC-249): design.md §3 y la interfaz de "
        "f2b0b25 dan a las fichas de Amazon una ventana de 60 días (amazon_min_window_days); "
        "la implementación usa los 90 días del historial por design.md §10.1 (#34, comentario "
        "7181387506). Lo decide Jesús en G4; quitar el xfail o cambiar la aserción entonces."
    ),
)
def test_armar_contexto_fichas_de_amazon_solo_de_60_dias():
    """design.md §3: el contexto trae "las fichas de Amazon (60 días)"; una de hace 61 días no
    entra a ``fichas_amazon``."""
    repo = RepositorioMemoria()
    version = con_version(repo)
    g = Guardador(repo, 0x7210_C100)
    id_oferta = g.tienda(0, "99.00")
    ficha_vieja = g.ficha(-61)
    ficha_dentro = g.ficha(-59)

    ctx = armar_contexto(repo, id_oferta, INSTANTE_HOY, version, id_evaluacion=UUID(int=6))

    fichas = {o.id for o in ctx.fichas_amazon}
    assert ficha_dentro in fichas
    assert ficha_vieja not in fichas


def test_armar_contexto_la_ventana_sale_de_la_configuracion():
    """design.md §7 (sin valores por defecto en el código): con el límite del episodio en 10
    días (PAR-08), la ventana del contexto es de 60 + 10 = 70 días: una observación de hace 80
    días ya no entra; una de hace 65 sí."""
    texto = con_sucursales_prueba(BASE.read_text(encoding="utf-8"))
    for viejo, nuevo in (
        ("clearance_episode_max_days: 30", "clearance_episode_max_days: 10"),
        ('version: "escenarios-base-1"', 'version: "escenarios-base-1-t21-ventana"'),
    ):
        assert texto.count(viejo) == 1
        texto = texto.replace(viejo, nuevo)
    config = cargar_configuracion_texto(texto, origen="t21-ventana")
    repo = RepositorioMemoria()
    version = con_version(repo, config)
    g = Guardador(repo, 0x7210_D000)
    fuera = g.tienda(-80, "129.00")
    dentro = g.tienda(-65, "129.00")
    id_oferta = g.tienda(0, "99.00")

    ctx = armar_contexto(repo, id_oferta, INSTANTE_HOY, version, id_evaluacion=UUID(int=2))

    ids = {o.id for o in ctx.historial}
    assert dentro in ids and fuera not in ids


def test_armar_contexto_capturas_con_captured_at_hasta_el_instante_dec_271():
    """DEC-271: el contexto toma las capturas con ``captured_at`` ≤ instante; el cargador pone
    ``captured_at`` = instante de la carga. Los comparables de B18 y una demanda local
    cargados a las 11:00 no se ven a las 10:45 y sí a las 11:30."""
    repo = RepositorioMemoria()
    version = con_version(repo)
    ids = Ids()
    t_obs = dt.datetime(2026, 11, 16, 10, 30, tzinfo=TIJUANA)
    t_cap = dt.datetime(2026, 11, 16, 11, 0, tzinfo=TIJUANA)
    cargar("b18.jsonl", jsonl(b18()), repo, version, t_obs, nuevo_id=ids)
    demanda_tools = {
        "recordType": "local_demand",
        "category": "tools",
        "level": "high",
        "date": "2026-11-16",
    }
    reporte = cargar(
        "capturas.jsonl",
        jsonl(*comparables_json(), demanda_tools),
        repo,
        version,
        t_cap,
        nuevo_id=ids,
    )
    assert (reporte.cargados, reporte.rechazados) == (4, 0)
    id_oferta = id_observacion(repo, b18())

    antes = armar_contexto(
        repo, id_oferta, t_cap - dt.timedelta(minutes=15), version, id_evaluacion=UUID(int=3)
    )
    despues = armar_contexto(
        repo, id_oferta, t_cap + dt.timedelta(minutes=30), version, id_evaluacion=UUID(int=4)
    )

    assert antes.comparables == ()
    assert antes.demanda_local == ()
    assert len(despues.comparables) == 3
    assert len(despues.demanda_local) == 1


def test_un_comparable_u_observacion_de_otro_modelo_no_entra_al_contexto():
    """Observación T12-tester-1 (#34, comentario 7181351024): el contexto de B18 (DEWALT
    DCF840) no trae comparables ni observaciones de otro modelo (DCF850), y
    ``observations_used`` tampoco. Si entraran los comparables de $300, $310 y $320, la mediana
    de pedidos cambiaría y el valor de referencia ya no sería $110.50 (B18)."""
    repo = RepositorioMemoria()
    version = con_version(repo)
    ids = Ids()
    otros = [
        dict(c, model="DCF850", askingPrice=p)
        for c, p in zip(comparables_json(), ("300.00", "310.00", "320.00"), strict=True)
    ]
    obs_otro = b18(
        model="DCF850",
        productUrl=f"https://{PLATAFORMA.domains[0]}/item/detail/dcf850-t21",
        extractedAt="2026-11-16T09:00:00-08:00",
    )
    cargar(
        "previo.jsonl",
        jsonl(*comparables_json(), *otros, obs_otro),
        repo,
        version,
        COMPARABLES_EN,
        nuevo_id=ids,
    )
    reporte = cargar("b18.jsonl", jsonl(b18()), repo, version, INSTANTE, nuevo_id=ids)
    (id_eval,) = reporte.evaluaciones
    registro = repo.leer_evaluacion(id_eval)

    afirmar_resultado_b18(registro)
    assert len(registro.entrada.comparables) == 3
    assert {c.model for c in registro.entrada.comparables} == {"DCF840"}
    id_otro = id_observacion(repo, obs_otro)
    assert id_otro not in {u.id for u in registro.observaciones_usadas}
    assert id_otro not in {o.id for o in registro.entrada.historial}


# --- DEC-264: episodios encadenados en el borde de los 90 días ------------------------------


def _precios_dec_264() -> dict[int, str]:
    """Una publicación con bajas escalonadas (un precio por día, a las 10:00 de Tijuana; sin
    observaciones los días −91 y −90, para no depender del borde exacto):

    - días −110 a −101 $200; −100 a −92 y −89 a −81 $150; −80 a −56 $140; −55 a −46 $130;
      −45 a −23 $120; −22 a 0 $110 (hoy, la oferta).

    **Contexto completo** (lo que no se debe ver): baja el día −100 → episodio E1 (congelado
    $200, días −100 a −71); el día −80 baja durante E1 (no empieza otro); el día −55 baja con
    E1 ya vencido → E2 (mediana de los 60 días anteriores, días −115 a −56: 25 × $140, 18 ×
    $150 y 10 × $200 → $150; −55 a −26); el día −45, durante E2; el día −22, con E2 vencido →
    E3 (mediana de los días −82 a −23: 23 × $120, 10 × $130, 25 × $140, 2 × $150 → $130),
    vigente hoy: real (130 − 110) ÷ 130 = 15.4%.

    **Contexto de 90 días** (DEC-264): la primera observación (día −89) no tiene anterior, no
    es baja (DEC-226 c); el día −80 baja bajo la mediana $150 → E1' (−80 a −51); el día −55,
    durante E1'; el día −45 baja bajo la mediana de los días −89 a −46 (9 × $150, 25 × $140,
    9 × $130 → $140) → E2' (−45 a −16); el día −22, durante E2'; hoy no hay episodio y el
    habitual es la mediana de los días −60 a −1: 22 × $110, 23 × $120, 10 × $130, 5 × $140 →
    **$120**; real (120 − 110) ÷ 120 = 8.3% → ``MERCADO YA BARATO``."""
    precios = {d: "200.00" for d in range(-110, -100)}
    precios |= {d: "150.00" for d in (*range(-100, -91), *range(-89, -80))}
    precios |= {d: "140.00" for d in range(-80, -55)}
    precios |= {d: "130.00" for d in range(-55, -45)}
    precios |= {d: "120.00" for d in range(-45, -22)}
    precios |= {d: "110.00" for d in range(-22, 1)}
    return precios


def _guardar_dec_264(repo) -> dict[int, UUID]:
    g = Guardador(repo, 0x7210_E000)
    return {dia: g.tienda(dia, precio) for dia, precio in sorted(_precios_dec_264().items())}


def test_dec_264_control_los_datos_distinguen_las_dos_vistas():
    """Control del fixture, por el motor (T09): con todo el historial, hoy hay episodio
    congelado en $130; con solo los 90 días, no hay episodio y el habitual es $120. Si esta
    prueba falla, el fixture no sirve para la de abajo."""
    repo = RepositorioMemoria()
    ids = _guardar_dec_264(repo)
    todas = repo.observaciones_del_producto(PRODUCTO, instante=INSTANTE_HOY)
    oferta = next(o for o in todas if o.id == ids[0])
    noventa = tuple(
        o for o in todas if o.observacion.extracted_at >= INSTANTE_HOY - dt.timedelta(days=90)
    )

    def evaluar(historial):
        return motor.evaluar(
            ContextoEvaluacion(
                id_evaluacion=UUID(int=5),
                instante=INSTANTE_HOY,
                configuracion=CONFIG,
                id_version_configuracion=1,
                oferta=oferta,
                historial=historial,
            )
        )

    completo, en_90 = evaluar(todas), evaluar(noventa)
    assert completo.referencias.episodio is not None
    assert completo.referencias.episodio.valor_congelado == D("130")
    assert completo.referencias.episodio.inicio == HOY - dt.timedelta(days=22)
    assert en_90.referencias.episodio is None
    assert en_90.referencias.precio_habitual == D("120")


def test_dec_264_una_cadena_de_episodios_anterior_al_contexto_no_se_ve(repo_vacio):
    """DEC-264: el episodio se determina con los 90 días del contexto; una cadena que empezó
    antes no se ve, y el recálculo da el mismo registro (RNF-3 por el ``input_snapshot``).
    Valores de ``_precios_dec_264``: sin episodio, habitual $120, real 8.3%, ``DESCARTADA``
    por ``MERCADO YA BARATO``."""
    repo = repo_vacio
    version = con_version(repo)
    ids = _guardar_dec_264(repo)
    id_eval = UUID(int=0x7210_E0FF)

    registro = evaluar_observacion(repo, ids[0], INSTANTE_HOY, version, nuevo_id=lambda: id_eval)

    assert registro.id == id_eval
    assert registro.referencias.episodio is None
    assert registro.referencias.precio_habitual == D("120")
    assert cerca(registro.descuento_real, (D("120") - D("110")) / D("120") * 100)
    assert registro.resultado is Resultado.DESCARTADA
    assert registro.motivo_principal is Motivo.MERCADO_YA_BARATO
    viejas = {ids[d] for d in ids if d <= -92}
    assert viejas.isdisjoint({u.id for u in registro.observaciones_usadas})
    assert viejas.isdisjoint({o.id for o in registro.entrada.historial})
    # Guardado (TAB-10/TAB-11) y recalculable.
    assert repo.leer_evaluacion(id_eval).a_json() == registro.a_json()
    assert recalcular(repo, id_eval).coincide is True


# =========================================================================================
# RNF-2: cambiar un parámetro y cargar la configuración cambia el resultado
# =========================================================================================


def _config_tools_demanda_baja():
    """La base con la demanda local inicial de ``tools`` en ``low`` (PAR-04)."""
    texto = con_sucursales_prueba(BASE.read_text(encoding="utf-8"))
    inicio = texto.index("\n  tools:\n")
    fin = texto.index("\n  home_lighting:\n")
    bloque = texto[inicio:fin]
    assert bloque.count("initial_local_demand: medium") == 1
    texto = (
        texto[:inicio]
        + bloque.replace("initial_local_demand: medium", "initial_local_demand: low")
        + texto[fin:]
    )
    viejo = 'version: "escenarios-base-1"'
    assert texto.count(viejo) == 1
    texto = texto.replace(viejo, 'version: "escenarios-base-1-t21-rnf2"')
    return cargar_configuracion_texto(texto, origen="t21-rnf2")


def test_rnf_2_un_parametro_nuevo_cambia_la_evaluacion_nueva_y_la_anterior_conserva_su_version():
    """RNF-2 (design.md §7 y §11): sin tocar código, se registra una versión con la demanda
    local de herramientas **baja**. La misma publicación de B18 observada otra vez se evalúa
    con la versión activa: la venta local queda **cerrada** por demanda local baja (REQ
    §3.2.1, RN-017), cuando con la versión anterior estaba disponible. La evaluación anterior
    conserva su versión, su resultado de B18 y se recalcula igual. El resultado final
    (``DESCARTADA``) va en la prueba siguiente."""
    repo, id_anterior, id_nueva, v1, v2 = _rnf_2()
    nueva_eval = repo.leer_evaluacion(id_nueva)
    assert nueva_eval.id_version_configuracion == v2.id
    local = canal(nueva_eval, Canal.LOCAL)
    assert local.estado is EstadoCanal.CERRADO
    assert local.nivel_calculado is None and local.margen_ajustado is None

    anterior = repo.leer_evaluacion(id_anterior)
    assert anterior.id_version_configuracion == v1.id
    afirmar_resultado_b18(anterior)
    assert canal(anterior, Canal.LOCAL).estado is EstadoCanal.DISPONIBLE
    assert recalcular(repo, id_anterior).coincide is True
    assert recalcular(repo, id_nueva).coincide is True


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Hueco del plan, no defecto de T21 (DEC-249): SIN CANAL DISPONIBLE lo construye T18 "
        "(tasks.md §18; #34, T20-2), igual que el xfail de B24 (b) en test_t20_tester.py. "
        "Quitar el xfail cuando T18 lo agregue."
    ),
)
def test_rnf_2_con_los_dos_canales_cerrados_la_evaluacion_nueva_se_descarta():
    """REQ §3.2.3: con los dos canales cerrados (Amazon por usado, S-12; local por demanda
    baja) → ``SIN CANAL DISPONIBLE`` → ``DESCARTADA`` (como B24 b)."""
    repo, _, id_nueva, _, _ = _rnf_2()
    nueva_eval = repo.leer_evaluacion(id_nueva)
    assert nueva_eval.resultado is Resultado.DESCARTADA
    assert nueva_eval.motivo_principal is Motivo.SIN_CANAL_DISPONIBLE


def _rnf_2():
    repo = RepositorioMemoria()
    v1 = con_version(repo)
    ids = Ids()
    primera = cargar_b34_a(repo, v1, ids)
    (id_anterior,) = primera.evaluaciones

    t_config = dt.datetime(2026, 11, 17, 8, 0, tzinfo=TIJUANA)
    v2, nueva = repo.guardar_version_configuracion(
        _config_tools_demanda_baja(), cargada_en=t_config
    )
    assert nueva and v2.id != v1.id
    t_carga = dt.datetime(2026, 11, 17, 12, 0, tzinfo=TIJUANA)
    activa = repo.version_configuracion_activa(t_carga)
    assert activa.id == v2.id
    otra_vez = b18(extractedAt="2026-11-17T10:00:00-08:00")
    segunda = cargar("b18_otra_vez.jsonl", jsonl(otra_vez), repo, activa, t_carga, nuevo_id=ids)
    (id_nueva,) = segunda.evaluaciones
    return repo, id_anterior, id_nueva, v1, v2


# =========================================================================================
# RNF-1: evaluar una observación en menos de 2 s (REQ §12; design.md §11)
# =========================================================================================


def _historial_rnf_1(repo) -> UUID:
    """Historial sintético de design.md §11: 10 publicaciones × 90 días × 2 observaciones
    (08:00 y 18:00 de Tijuana, días −90 a −1) más 60 fichas de Amazon (días −59 a 0, a las
    10:00, dentro de los 60 días). Cinco publicaciones son de ``tienda-prueba`` y cinco de
    ``tienda-prueba-2``. Devuelve el id de la oferta de hoy (publicación 0, $79)."""
    g = Guardador(repo, 0x7211_0000)
    pubs = []
    for i in range(10):
        comercio_, dominio = (
            (TIENDA_PRUEBA, DOMINIO_PRUEBA) if i < 5 else (TIENDA_PRUEBA_2, DOMINIO_PRUEBA_2)
        )
        pubs.append((UUID(int=0x7211_F000 + i), comercio_, dominio, f"/p/rnf1-{i}"))
    for dia in range(-90, 0):
        for hora in (8, 18):
            for i, (id_pub, comercio_, dominio, ruta) in enumerate(pubs):
                precio = f"{129 + i + (dia % 7)}.00"
                datos = _datos_tienda(
                    dia, precio, ruta=ruta, comercio_=comercio_, dominio=dominio, hora=hora
                )
                g(datos, id_pub, comercio_)
    for dia in range(-59, 1):
        g(_datos_ficha(dia, "125.00"), PUB_FICHA, FICHA)
    id_pub, comercio_, dominio, ruta = pubs[0]
    return g(
        _datos_tienda(0, "79.00", ruta=ruta, comercio_=comercio_, dominio=dominio),
        id_pub,
        comercio_,
    )


def test_rnf_1_evaluar_con_el_historial_sintetico_tarda_menos_de_2_s(repo_vacio):
    """RNF-1: de punta a punta (armar el contexto, evaluar y guardar el registro) < 2 s, con
    el historial sintético grande de design.md §11, en memoria y contra PostgreSQL."""
    repo = repo_vacio
    version = con_version(repo)
    id_oferta = _historial_rnf_1(repo)
    id_eval = UUID(int=0x7211_EEEE)

    inicio = time.perf_counter()
    registro = evaluar_observacion(repo, id_oferta, INSTANTE_HOY, version, nuevo_id=lambda: id_eval)
    duracion = time.perf_counter() - inicio

    assert duracion < 2.0, f"RNF-1: la evaluación tardó {duracion:.3f} s (máximo 2 s)"
    assert repo.leer_evaluacion(id_eval) is not None
    # El contexto trae el historial de los 90 días y las 60 fichas.
    assert len(registro.entrada.fichas_amazon) == 60
    assert (
        len([o for o in registro.entrada.historial if o.observacion.amazon_listing is None])
        >= 10 * 89 * 2
    )
