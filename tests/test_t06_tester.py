"""Pruebas independientes de oip-tester para T06 (CMP-20, RNF-8; DEC-250).

Escritas desde las fuentes, no desde el código: tasks.md T06 (comportamientos esperados),
design.md §4, §5, §8, §12 y §16, DEC-238, DEC-250 y la interfaz ``Repositorio`` (su
docstring es el contrato que deben cumplir **las dos** implementaciones).

- La batería (fixture ``repo``) corre con ``RepositorioMemoria`` en CI y con
  ``RepositorioPostgres`` solo con ``OIP_TEST_DATABASE_URL`` (``@pytest.mark.integracion``,
  DEC-233). La base debe ser **desechable**: cada prueba borra las tablas de OIP.
- Las pruebas ``xfail(strict=True)`` fijan defectos encontrados (memoria acepta filas que
  PostgreSQL rechaza por sus ``CHECK``): se conservan hasta que el developer los corrija.
- Deterministas: instante siempre explícito, sin reloj, sin red. Fixtures sintéticos con el
  comercio ``tienda-prueba`` (example.com); ninguna URL se abre. Ninguna credencial real.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import logging
import os
import traceback
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import func, select, text

from config_tienda_prueba import TIENDA_PRUEBA, configuracion_con_tienda_prueba
from oip.catalogos import (
    CalidadPrecio,
    Canal,
    Confianza,
    EstadoCanal,
    Identificacion,
    Motivo,
    Nivel,
    Resultado,
    TipoRegistro,
)
from oip.entradas.capturas import ComparableLocal, leer_captura
from oip.entradas.contrato import Observacion, leer_observacion
from oip.evaluacion.contexto import (
    ContextoEvaluacion,
    EvaluacionCanal,
    ObservacionRegistrada,
    ObservacionUsada,
    RegistroEvaluacion,
)
from oip.persistencia import tablas
from oip.persistencia.repositorios import (
    VARIABLE_URL,
    CapturaNueva,
    Carga,
    ErrorDeConexion,
    ErrorDeIntegridad,
    IdentificadorProducto,
    ObservacionNueva,
    Producto,
    Publicacion,
    RechazoCarga,
    RegistroRechazo,
    ReporteCarga,
    RepositorioMemoria,
    RepositorioPostgres,
    _filas,
    crear_motor,
    url_de_conexion,
)

RAIZ = Path(__file__).resolve().parent.parent
_VARIABLE_PRUEBAS = "OIP_TEST_DATABASE_URL"
CONFIG = configuracion_con_tienda_prueba()
T0 = dt.datetime(2026, 11, 16, 18, 0, tzinfo=dt.UTC)
TIJUANA = dt.timezone(dt.timedelta(hours=-8))
MICRO = dt.timedelta(microseconds=1)
#: Fecha y hora sin desfase: se rechaza en todo el repositorio.
SIN_DESFASE = dt.datetime(2026, 11, 16, 18, 0)  # noqa: DTZ001

PRODUCTO = UUID(int=0x7E5)
PUBLICACION = UUID(int=0x7E6)
CARGA = UUID(int=0x7E7)
URL = "https://tienda.example.com/p/tester-1"


def _h(n: int) -> str:
    return f"{n:064x}"


# --- Las dos implementaciones -------------------------------------------------------------


def _url():
    from sqlalchemy.engine import make_url

    valor = os.environ.get(_VARIABLE_PRUEBAS, "").strip()
    if not valor:
        pytest.skip(f"sin {_VARIABLE_PRUEBAS}: las pruebas de integración se saltan (DEC-233)")
    url = make_url(valor)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    return url


def _limpiar(motor) -> None:
    nombres = ", ".join([*tablas.metadata.tables, "alembic_version"])
    with motor.begin() as conexion:
        conexion.execute(text("DROP VIEW IF EXISTS open_opportunity"))
        conexion.execute(text(f"DROP TABLE IF EXISTS {nombres} CASCADE"))


def _alembic(motor, accion: str, revision: str) -> None:
    from alembic import command
    from alembic.config import Config

    with motor.begin() as conexion:
        config = Config(str(RAIZ / "alembic.ini"))
        config.attributes["connection"] = conexion
        getattr(command, accion)(config, revision)


def _repo_de(param: str):
    if param == "memoria":
        yield RepositorioMemoria()
        return
    motor = crear_motor(_url())
    _limpiar(motor)
    try:
        _alembic(motor, "upgrade", "head")
        repositorio = RepositorioPostgres(motor)
        repositorio._motor_tester = motor
        yield repositorio
    finally:
        _limpiar(motor)
        motor.dispose()


@pytest.fixture(params=["memoria", pytest.param("postgres", marks=pytest.mark.integracion)])
def repo(request):
    yield from _repo_de(request.param)


_DEFECTO_CHECK = (
    "IMPLEMENTATION DEFECT (T06, oip-tester): RepositorioMemoria no aplica los CHECK del "
    "esquema; PostgreSQL rechaza la fila con ErrorDeIntegridad y memoria la guarda"
)


@pytest.fixture(
    params=[
        pytest.param("memoria"),
        pytest.param("postgres", marks=pytest.mark.integracion),
    ]
)
def repo_check(request):
    """Como ``repo``; en memoria, estas pruebas fijan el defecto de los CHECK."""
    yield from _repo_de(request.param)


def _filas_de(repo, tabla) -> list[dict]:
    if isinstance(repo, RepositorioMemoria):
        return [dict(f) for f in repo._tablas[tabla.name].filas]
    with repo._motor_tester.connect() as c:
        return [dict(r._mapping) for r in c.execute(tabla.select())]


def _conteos(repo) -> dict[str, int]:
    if isinstance(repo, RepositorioMemoria):
        return {n: len(t.filas) for n, t in repo._tablas.items()}
    with repo._motor_tester.connect() as c:
        return {
            n: c.execute(select(func.count()).select_from(t)).scalar_one()
            for n, t in tablas.metadata.tables.items()
        }


# --- Datos sintéticos (tienda-prueba, example.com) -----------------------------------------


def _obs(extraida: str = "2026-11-16T09:00:00-08:00", precio: str = "40.00", **cambios):
    datos = {
        "retailerCode": TIENDA_PRUEBA,
        "storeCode": "tp-02",
        "productUrl": URL,
        "title": "Lijadora sintética",
        "brand": "MarcaT",
        "model": "T-6",
        "category": "tools",
        "weightKg": Decimal("2.375"),
        "price": {"current": precio, "was": "99.99", "currency": "USD"},
        "seller": "comercio",
        "condition": "new",
        "availability": {"state": "in_stock", "quantity": 2, "scope": "store"},
        "purchaseMode": "tienda",
        "extractedAt": extraida,
        "blocked": False,
    }
    datos.update(cambios)
    return leer_observacion(datos)


def _producto(id_=PRODUCTO) -> Producto:
    return Producto(id_, T0, "MarcaT", "T-6")


def _publicacion(id_=PUBLICACION, producto=PRODUCTO, url=URL, tienda="tp-02") -> Publicacion:
    return Publicacion(id_, producto, TIENDA_PRUEBA, url, T0, tienda)


def _nueva(n: int, observacion=None, *, clave=None, primera=False, carga=None, **cambios):
    return ObservacionNueva(
        registrada=ObservacionRegistrada(
            observacion or _obs(),
            UUID(int=n),
            cambios.pop("id_publicacion", PUBLICACION),
            PRODUCTO,
        ),
        identificacion=Identificacion.CONFIRMED,
        clave_idempotencia=clave or f"tester|{n}",
        origen="file" if carga else "worker",
        recibida_en=T0,
        id_carga=carga,
        producto=_producto() if primera else None,
        identificadores=(IdentificadorProducto("brand_model", "marcat|t-6"),) if primera else (),
        publicacion=cambios.pop("publicacion", _publicacion() if primera else None),
        **cambios,
    )


def _config(repo, cargada_en=T0 - dt.timedelta(days=2)) -> int:
    version, _ = repo.guardar_version_configuracion(CONFIG, cargada_en=cargada_en)
    return version.id


def _carga(repo) -> int:
    id_config = _config(repo)
    repo.iniciar_carga(Carga(CARGA, "tester.jsonl", _h(7), "jsonl", T0, id_config))
    return id_config


def _contexto(id_eval: UUID, instante, id_config: int) -> ContextoEvaluacion:
    return ContextoEvaluacion(
        id_evaluacion=id_eval,
        instante=instante,
        configuracion=CONFIG,
        id_version_configuracion=id_config,
        oferta=ObservacionRegistrada(_obs(), UUID(int=1), PUBLICACION, PRODUCTO),
    )


def _registro(n: int, instante, id_config: int, **cambios) -> RegistroEvaluacion:
    contexto = _contexto(UUID(int=0x5000 + n), instante, id_config)
    base = {
        "id": contexto.id_evaluacion,
        "evaluado_en": instante,
        "id_observacion_oferta": UUID(int=1),
        "id_publicacion": PUBLICACION,
        "id_producto": PRODUCTO,
        "id_version_configuracion": id_config,
        "versiones_rn": contexto.versiones_rn,
        "resultado": Resultado.NIVEL_ASIGNADO,
        "motivo_principal": None,
        "motivos": (),
        "motivo_rechazo": None,
        "marcas": ("MARGEN ESTIMADO",),
        "calidad_precio": CalidadPrecio.OFERTA_EXCEPCIONAL,
        "confianza": Confianza.ALTA,
        "identificacion": Identificacion.CONFIRMED,
        "referencias": None,
        "descuento_anunciado": Decimal("59.995999599959995999599959996"),
        "descuento_real": Decimal("66.66666666666666666666666667"),
        "costo_compra": Decimal("43.10"),
        "canal_elegido": Canal.LOCAL,
        "nivel_aviso": Nivel.RECOMENDABLE,
        "canal_aviso": Canal.LOCAL,
        "canales": (
            EvaluacionCanal(
                canal=Canal.LOCAL,
                estado=EstadoCanal.DISPONIBLE,
                precio_venta=Decimal("84.9915"),
                margen_neto=Decimal("31.40"),
                margen_neto_pct=Decimal("72.85382830626450116009280742"),
                unidades=1,
                nivel=Nivel.RECOMENDABLE,
                nivel_calculado=Nivel.RECOMENDABLE,
                ganancia_total=Decimal("31.40"),
                marcas=("Z MARCA", "A MARCA"),
            ),
        ),
        "observaciones_usadas": (ObservacionUsada(UUID(int=1), T0),),
        "entrada": contexto,
    }
    base.update(cambios)
    return RegistroEvaluacion(**base)


def _con_publicacion(repo) -> int:
    id_config = _config(repo)
    assert repo.guardar_observacion(_nueva(1, primera=True))
    return id_config


# === Idempotencia (design.md §5) ============================================================


def test_un_duplicado_por_clave_con_otro_contenido_no_escribe_nada(repo):
    _config(repo)
    assert repo.guardar_observacion(_nueva(1, primera=True))
    antes = _conteos(repo)
    # Misma clave, otra observación (otro id, otro precio, otra hora): no se guarda.
    otra = _nueva(2, _obs("2026-11-16T09:30:00-08:00", "35.00"), clave="tester|1")
    assert repo.guardar_observacion(otra) is False
    assert _conteos(repo) == antes
    assert repo.observacion_por_clave("tester|1") == UUID(int=1)
    assert repo.leer_observacion(UUID(int=2)) is None
    assert repo.leer_observacion(UUID(int=1)).observacion.price.current == Decimal("40.00")


def test_una_captura_duplicada_con_producto_nuevo_no_crea_el_producto(repo):
    _carga(repo)
    repo.guardar_producto(_producto())
    captura = leer_captura(
        TipoRegistro.LOCAL_ESTIMATE,
        {"brand": "MarcaT", "model": "T-6", "price": "55.5", "date": "2026-11-01"},
    )
    nueva = CapturaNueva(UUID(int=31), captura, _h(31), CARGA, T0, PRODUCTO)
    assert repo.guardar_captura(nueva) is True
    antes = _conteos(repo)
    otro = UUID(int=0x999)
    duplicada = dataclasses.replace(
        nueva,
        id=UUID(int=32),
        id_producto=otro,
        producto=Producto(otro, T0, "Otra", "O-1"),
        identificadores=(IdentificadorProducto("brand_model", "otra|o-1"),),
    )
    assert repo.guardar_captura(duplicada) is False
    assert _conteos(repo) == antes
    assert repo.leer_producto(otro) is None


def test_un_fallo_no_envenena_la_clave_de_idempotencia(repo):
    """Una transacción por registro: si falla después del recibo (TAB-08), el recibo no
    queda, y el mismo registro corregido entra después."""
    _config(repo)
    buena = _nueva(1, primera=True, clave="tester|x")
    # El mismo identificador dos veces en la misma llamada: choca después del recibo.
    rota = dataclasses.replace(buena, identificadores=buena.identificadores * 2)
    antes = _conteos(repo)
    with pytest.raises(ErrorDeIntegridad) as error:
        repo.guardar_observacion(rota)
    assert error.value.restriccion == "pk_product_identifier"
    assert _conteos(repo) == antes
    assert repo.observacion_por_clave("tester|x") is None
    assert repo.guardar_observacion(buena) is True
    assert repo.observacion_por_clave("tester|x") == UUID(int=1)


# === A un instante (design.md §5) ===========================================================


def test_las_observaciones_incluyen_el_instante_exacto_y_no_un_microsegundo_despues(repo):
    _config(repo)
    repo.guardar_observacion(_nueva(1, primera=True))  # 17:00Z
    repo.guardar_observacion(_nueva(2, _obs("2026-11-16T10:00:00-08:00")))  # 18:00Z = T0
    repo.guardar_observacion(_nueva(3, _obs("2026-11-16T10:00:00.000001-08:00")))
    ids = [o.id.int for o in repo.observaciones_del_producto(PRODUCTO, instante=T0)]
    assert ids == [1, 2]
    # El mismo instante con otro desfase es el mismo instante.
    en_tijuana = T0.astimezone(TIJUANA)
    assert [o.id.int for o in repo.observaciones_del_producto(PRODUCTO, instante=en_tijuana)] == [
        1,
        2,
    ]
    assert [o.id.int for o in repo.observaciones_del_producto(PRODUCTO, instante=T0 - MICRO)] == [1]
    # ``desde`` también incluye su borde.
    assert [
        o.id.int for o in repo.observaciones_del_producto(PRODUCTO, instante=T0 + MICRO, desde=T0)
    ] == [2, 3]
    # Lo leído vuelve en UTC.
    assert all(
        o.observacion.extracted_at.utcoffset() == dt.timedelta(0)
        for o in repo.observaciones_del_producto(PRODUCTO, instante=T0)
    )


@pytest.mark.parametrize("instante", [SIN_DESFASE, dt.date(2026, 11, 16), "2026-11-16T18:00Z"])
def test_un_instante_sin_desfase_o_de_otro_tipo_se_rechaza_en_cada_lectura(repo, instante):
    for leer in (
        lambda: repo.observaciones_del_producto(PRODUCTO, instante=instante),
        lambda: repo.capturas(TipoRegistro.LOCAL_DEMAND, instante=instante),
        lambda: repo.version_configuracion_activa(instante),
        lambda: repo.oportunidades_abiertas(instante=instante),
    ):
        with pytest.raises(TypeError):
            leer()


def test_la_configuracion_activa_en_los_bordes_del_instante(repo):
    assert repo.version_configuracion_activa(T0) is None
    primera, nueva = repo.guardar_version_configuracion(CONFIG, cargada_en=T0)
    assert nueva
    assert repo.version_configuracion_activa(T0 - MICRO) is None
    assert repo.version_configuracion_activa(T0).id == primera.id
    assert repo.version_configuracion_activa(T0.astimezone(TIJUANA)).id == primera.id
    # La misma configuración (mismo sha256) otra vez: no se escribe ni cambia su loaded_at.
    otra_vez, nueva = repo.guardar_version_configuracion(CONFIG, cargada_en=T0 + MICRO)
    assert (otra_vez.id, otra_vez.cargada_en, nueva) == (primera.id, T0, False)
    assert len(_filas_de(repo, tablas.config_version)) == 1


def test_las_capturas_incluyen_el_instante_exacto(repo):
    _carga(repo)
    demanda = leer_captura(
        TipoRegistro.LOCAL_DEMAND, {"category": "tools", "level": "high", "date": "2026-11-20"}
    )
    repo.guardar_captura(CapturaNueva(UUID(int=41), demanda, _h(41), CARGA, T0))
    tipo = TipoRegistro.LOCAL_DEMAND
    assert [c.id.int for c in repo.capturas(tipo, instante=T0)] == [41]
    assert repo.capturas(tipo, instante=T0 - MICRO) == ()


def test_una_oportunidad_se_cierra_con_una_evaluacion_posterior_sin_nivel(repo):
    id_config = _con_publicacion(repo)
    abierta = _registro(1, T0, id_config)
    repo.guardar_evaluacion(abierta)
    sin_nivel = _registro(
        2,
        T0 + dt.timedelta(hours=1),
        id_config,
        resultado=Resultado.SIN_NIVEL,
        nivel_aviso=None,
        canal_aviso=None,
        canal_elegido=None,
    )
    repo.guardar_evaluacion(sin_nivel)
    assert repo.oportunidades_abiertas(instante=T0 - MICRO) == ()
    assert [r.id for r in repo.oportunidades_abiertas(instante=T0)] == [abierta.id]
    assert [r.id for r in repo.oportunidades_abiertas(instante=T0 + dt.timedelta(minutes=59))] == [
        abierta.id
    ]
    assert repo.oportunidades_abiertas(instante=T0 + dt.timedelta(hours=1)) == ()
    assert repo.oportunidades_abiertas(instante=T0, id_producto=UUID(int=0xDEAD)) == ()


def test_con_el_mismo_instante_gana_la_evaluacion_de_id_mayor(repo):
    id_config = _con_publicacion(repo)
    # id mayor (0x5009) sin nivel, id menor (0x5001) con nivel: cierra la mayor.
    repo.guardar_evaluacion(_registro(1, T0, id_config))
    repo.guardar_evaluacion(
        _registro(
            9,
            T0,
            id_config,
            resultado=Resultado.DESCARTADA,
            nivel_aviso=None,
            canal_aviso=None,
            canal_elegido=None,
            motivo_principal=Motivo.MARGEN_NEGATIVO,
            motivos=(Motivo.MARGEN_NEGATIVO,),
        )
    )
    assert repo.oportunidades_abiertas(instante=T0) == ()


# === Decimal y orden (design.md §8) =========================================================


def test_los_montos_y_porcentajes_vuelven_como_decimal_exacto(repo):
    id_config = _con_publicacion(repo)
    registro = _registro(1, T0, id_config)
    repo.guardar_evaluacion(registro)
    leido = repo.leer_evaluacion(registro.id)
    assert leido == registro
    assert type(leido.descuento_real) is Decimal
    assert str(leido.descuento_real) == "66.66666666666666666666666667"  # sin redondear
    assert str(leido.descuento_anunciado) == "59.995999599959995999599959996"
    (canal,) = leido.canales
    assert str(canal.margen_neto_pct) == "72.85382830626450116009280742"
    assert type(canal.precio_venta) is Decimal and canal.precio_venta == Decimal("84.9915")
    assert canal.marcas == ("Z MARCA", "A MARCA")  # el orden del registro, no alfabético
    obs = repo.leer_observacion(UUID(int=1)).observacion
    assert type(obs.weight_kg) is Decimal and str(obs.weight_kg) == "2.375"
    assert type(obs.price.current) is Decimal and obs.price.current == Decimal("40.00")


def test_los_motivos_vuelven_en_el_orden_del_registro(repo):
    id_config = _con_publicacion(repo)
    # El orden de REQ §3.2.3 (el del catálogo); el registro lo impone y la base lo conserva.
    motivos = (Motivo.EVITAR, Motivo.MERCADO_YA_BARATO, Motivo.SOLO_REFERENCIA)
    registro = _registro(
        3,
        T0,
        id_config,
        resultado=motivos[0].lleva_a,
        nivel_aviso=None,
        canal_aviso=None,
        canal_elegido=None,
        motivo_principal=motivos[0],
        motivos=motivos,
        marcas=("MARGEN ESTIMADO", "EMPAQUE POR CONFIRMAR", "ESTIMADO (peso)"),
    )
    repo.guardar_evaluacion(registro)
    leido = repo.leer_evaluacion(registro.id)
    assert leido.motivos == motivos
    assert leido.marcas == ("MARGEN ESTIMADO", "EMPAQUE POR CONFIRMAR", "ESTIMADO (peso)")


# === DEC-250: el registro de un rechazo =====================================================

_COLUMNAS_DEL_RENGLON = (
    "input_snapshot",
    "offer_observation_id",
    "listing_id",
    "product_id",
    "main_reason",
    "price_quality",
    "confidence",
    "identification",
    "references",
    "advertised_discount",
    "real_discount",
    "purchase_cost",
    "chosen_channel",
    "alert_level",
    "alert_channel",
    "previous_evaluation_id",
)


def _rechazo(id_carga=CARGA, renglon=4, motivo="DOMINIO NO AUTORIZADO", n=0x701):
    return RegistroRechazo(
        id=UUID(int=n),
        evaluado_en=T0,
        id_version_configuracion=1,
        versiones_rn={"RN-001": 2, "RN-013": 1},
        motivo_rechazo=motivo,
        id_carga=id_carga,
        renglon=renglon,
    )


def test_el_rechazo_de_un_archivo_no_guarda_nada_del_renglon_y_se_liga_a_load_rejection(repo):
    _carga(repo)
    motivo = "CAMPO OBLIGATORIO FALTANTE (productUrl)"
    registro = _rechazo(motivo=motivo)
    repo.guardar_rechazo_carga(
        RechazoCarga(CARGA, 4, motivo, TipoRegistro.OBSERVATION, "productUrl"), registro
    )
    (fila,) = _filas_de(repo, tablas.evaluation)
    for columna in _COLUMNAS_DEL_RENGLON:
        assert fila[columna] is None, columna
    assert list(fila["reasons"]) == [] and list(fila["marks"]) == []
    assert list(fila["changed_references"]) == [] and fila["no_longer_recommended"] is False
    assert (
        json.loads(
            fila["observations_used"]
            if isinstance(fila["observations_used"], str)
            else json.dumps(fila["observations_used"])
        )
        == []
    )
    assert (fila["result"], fila["rejection_reason"]) == ("RECHAZADA_VALIDACION", motivo)
    assert (fila["load_run_id"], fila["line_number"], fila["config_version_id"]) == (CARGA, 4, 1)
    assert repo.leer_evaluacion(registro.id) == registro
    # El renglón de load_rejection tampoco guarda contenido: solo el nombre del campo.
    (rechazo,) = _filas_de(repo, tablas.load_rejection)
    assert set(rechazo) == {"load_run_id", "line_number", "record_type", "reason", "field"}
    # No es una oportunidad.
    assert repo.oportunidades_abiertas(instante=T0 + dt.timedelta(days=1)) == ()


def test_el_rechazo_que_no_viene_de_un_archivo_va_sin_carga_ni_renglon(repo):
    _config(repo)
    registro = _rechazo(id_carga=None, renglon=None, motivo="PRECIO INVÁLIDO")
    repo.guardar_registro_rechazo(registro)
    (fila,) = _filas_de(repo, tablas.evaluation)
    assert (fila["load_run_id"], fila["line_number"], fila["input_snapshot"]) == (None, None, None)
    assert repo.leer_evaluacion(registro.id) == registro


def test_rechazo_y_renglon_son_una_transaccion(repo):
    _carga(repo)
    # El registro cita una versión de configuración que no existe: falla y no queda el renglón.
    registro = dataclasses.replace(_rechazo(), id_version_configuracion=999)
    with pytest.raises(ErrorDeIntegridad):
        repo.guardar_rechazo_carga(RechazoCarga(CARGA, 4, "DOMINIO NO AUTORIZADO"), registro)
    assert _filas_de(repo, tablas.load_rejection) == []
    assert _filas_de(repo, tablas.evaluation) == []


@pytest.mark.parametrize(
    ("cambios", "error"),
    [
        ({"renglon": None}, ValueError),
        ({"id_carga": None}, ValueError),
        ({"renglon": 0}, ValueError),
        ({"motivo_rechazo": "OTRO MOTIVO"}, ValueError),
        ({"motivo_rechazo": "CAMPO OBLIGATORIO FALTANTE"}, ValueError),
        ({"renglon": True}, TypeError),
        ({"id_version_configuracion": "1"}, TypeError),
        ({"evaluado_en": SIN_DESFASE}, TypeError),
    ],
)
def test_un_registro_de_rechazo_invalido_no_se_construye(cambios, error):
    with pytest.raises(error):
        dataclasses.replace(_rechazo(), **cambios)


def test_cada_metodo_acepta_solo_su_tipo_de_registro(repo):
    _con_publicacion(repo)
    with pytest.raises(TypeError):
        repo.guardar_evaluacion(_rechazo(id_carga=None, renglon=None))
    with pytest.raises(TypeError):
        repo.guardar_registro_rechazo(_registro(1, T0, 1))
    assert _filas_de(repo, tablas.evaluation) == []


# === Vacío = ausente y tipos estrictos (DEC-238) ============================================


@pytest.mark.parametrize(
    "construir",
    [
        lambda: Producto(PRODUCTO, T0, ""),
        lambda: Producto(PRODUCTO, T0, "   "),
        lambda: Publicacion(PUBLICACION, PRODUCTO, TIENDA_PRUEBA, URL, T0, ""),
        lambda: IdentificadorProducto("gtin", " "),
        lambda: _nueva(1, clave=" "),
        lambda: RechazoCarga(CARGA, 1, "PRECIO INVÁLIDO", campo=""),
    ],
    ids=["marca", "marca-espacios", "tienda", "identificador", "clave", "campo"],
)
def test_un_texto_vacio_no_es_un_valor(construir):
    with pytest.raises(ValueError):
        construir()


@pytest.mark.parametrize(
    "construir",
    [
        lambda: ReporteCarga(T0, True, 0, 0, {}),
        lambda: ReporteCarga(T0, 1.0, 0, 0, {}),
        lambda: RechazoCarga(CARGA, True, "PRECIO INVÁLIDO"),
        lambda: Carga(CARGA, "a.jsonl", _h(1), "jsonl", T0, True),
        lambda: Producto(str(PRODUCTO), T0),
        lambda: Producto(PRODUCTO, SIN_DESFASE),
    ],
    ids=[
        "bool-por-entero",
        "float-por-entero",
        "renglon-bool",
        "config-bool",
        "uuid-str",
        "sin-desfase",
    ],
)
def test_los_tipos_son_estrictos_sin_conversiones(construir):
    with pytest.raises(TypeError):
        construir()


def test_un_float_no_entra_en_un_monto(repo):
    _con_publicacion(repo)
    registro = _registro(1, T0, 1)
    object.__setattr__(registro, "costo_compra", 43.1)  # saltando la verificación del tipo
    with pytest.raises(TypeError, match="float"):
        repo.guardar_evaluacion(registro)
    assert _filas_de(repo, tablas.evaluation) == []


# === Defectos: memoria no aplica los CHECK que aplica PostgreSQL ============================
# El contrato (protocolo.py) dice: "una clave o restricción violada levanta
# ErrorDeIntegridad con el nombre de la restricción", en las dos implementaciones
# (design.md §5: la misma batería pasa con memoria y con PostgreSQL). Cada caso usa un
# tipo del dominio que se construye sin error y viola un CHECK de tablas.py.


def test_defecto_una_visita_sin_producto_ni_evaluacion_se_rechaza(repo_check):
    _carga(repo_check)
    visita = leer_captura(
        TipoRegistro.STORE_VISIT,
        {
            "storeCode": "tp-02",
            "gtin": "0123456789012",
            "result": "found",
            "visitedAt": "2026-11-15T09:30:00",
        },
        zona=dt.timezone(dt.timedelta(hours=-8)),
    )
    nueva = CapturaNueva(UUID(int=51), visita, _h(51), CARGA, T0)  # sin id_producto
    with pytest.raises(ErrorDeIntegridad) as error:
        repo_check.guardar_captura(nueva)
    assert error.value.restriccion == "ck_store_visit_producto_u_oportunidad"


def test_defecto_un_comparable_en_mxn_sin_tipo_de_cambio_se_rechaza(repo_check):
    _carga(repo_check)
    repo_check.guardar_producto(_producto())
    comparable = ComparableLocal.model_validate(
        {
            "brand": "MarcaT",
            "model": "T-6",
            "condition": "used",
            "askingPrice": "1500.00",
            "currency": "MXN",
            "city": "tijuana",
            "date": "2026-11-10",
            "sold": False,
        }
    )
    nueva = CapturaNueva(UUID(int=52), comparable, _h(52), CARGA, T0, PRODUCTO)
    with pytest.raises(ErrorDeIntegridad) as error:
        repo_check.guardar_captura(nueva)
    assert error.value.restriccion == "ck_local_comparable_mxn_con_tipo_de_cambio"


def test_defecto_una_observacion_con_precio_cero_se_rechaza(repo_check):
    _config(repo_check)
    datos = _obs().model_dump(by_alias=True)
    datos["price"]["current"] = "0"
    with pytest.raises(ErrorDeIntegridad) as error:
        repo_check.guardar_observacion(_nueva(1, Observacion.model_validate(datos), primera=True))
    assert error.value.restriccion == "ck_price_observation_price_positivo"
    assert repo_check.observacion_por_clave("tester|1") is None


def test_defecto_ya_no_recomendado_sin_evaluacion_anterior_se_rechaza(repo_check):
    id_config = _con_publicacion(repo_check)
    registro = _registro(1, T0, id_config, ya_no_recomendado=True)  # sin id_evaluacion_anterior
    with pytest.raises(ErrorDeIntegridad) as error:
        repo_check.guardar_evaluacion(registro)
    assert error.value.restriccion == "ck_evaluation_reevaluacion"


@pytest.mark.parametrize(
    "param",
    [
        pytest.param("memoria"),
        pytest.param("postgres", marks=[pytest.mark.integracion]),
    ],
)
def test_defecto_un_entero_que_no_cabe_en_integer_se_rechaza_antes_de_escribir(param):
    """protocolo.py: "un valor que no cabe en su columna sin cambiarlo, ValueError o
    TypeError, antes de escribir" (``load_rejection.line_number`` es ``integer``)."""
    for repositorio in _repo_de(param):
        _carga(repositorio)
        with pytest.raises(ValueError):
            repositorio.guardar_rechazo_carga(RechazoCarga(CARGA, 2**31, "PRECIO INVÁLIDO"))
        assert _filas_de(repositorio, tablas.load_rejection) == []


# === jsonb: el texto que devuelve PostgreSQL se lee igual (sin base) ========================


def _como_jsonb(texto: str) -> str:
    """El texto como lo devuelve ``jsonb::text``: claves ordenadas por longitud y luego
    por bytes, con ``", "`` y ``": "``. Solo reordena: no es una base de datos."""

    def ordenar(valor):
        if isinstance(valor, dict):
            claves = sorted(valor, key=lambda k: (len(k.encode()), k.encode()))
            return {k: ordenar(valor[k]) for k in claves}
        if isinstance(valor, list):
            return [ordenar(v) for v in valor]
        return valor

    datos = json.loads(texto, parse_float=Decimal)
    return json.dumps(ordenar(datos), ensure_ascii=False, separators=(", ", ": "), default=str)


def test_el_contexto_y_la_configuracion_se_leen_igual_con_el_orden_de_jsonb():
    registro = _registro(1, T0, 1)
    fila = _filas.filas_evaluacion(registro)[0][1]
    assert _como_jsonb(fila["input_snapshot"]) != fila["input_snapshot"]
    leido = _filas.evaluacion_de_filas(
        {
            **fila,
            **{
                c: _como_jsonb(fila[c])
                for c in ("input_snapshot", "rn_versions", "observations_used")
            },
        },
        [],
    )
    assert leido.entrada == registro.entrada
    assert leido.versiones_rn == registro.versiones_rn
    config = _filas.fila_configuracion(CONFIG, T0, 1)
    leida = _filas.configuracion_de_fila({**config, "content": _como_jsonb(config["content"])})
    assert leida.configuracion == CONFIG


# === Secretos (RNF-8) ======================================================================

USUARIO = "usuario_tester_t06"
CLAVE = "Clave-Tester-T06-no-real-91"


def _entorno(tmp_path: Path) -> dict[str, str]:
    # Socket Unix en un directorio que no existe: falla sin red.
    return {VARIABLE_URL: f"postgresql://{USUARIO}@/oip_t06?host={tmp_path}/sin-socket"}


def _secreto(tmp_path: Path, contenido: str = CLAVE + "\n") -> Path:
    archivo = tmp_path / "oip_db_password"
    archivo.write_text(contenido, encoding="utf-8")
    return archivo


def _sin_secretos(texto: str, tmp_path: Path | None = None) -> None:
    assert CLAVE not in texto
    assert "postgresql" not in texto
    if tmp_path is not None:
        assert str(tmp_path) not in texto


def test_el_motor_y_la_url_no_muestran_la_contrasena(tmp_path):
    url = url_de_conexion(_entorno(tmp_path), _secreto(tmp_path))
    assert url.password == CLAVE  # solo el salto de renglón final se quita
    assert CLAVE not in str(url) and CLAVE not in repr(url)
    motor = crear_motor(url)
    try:
        assert CLAVE not in repr(motor) and CLAVE not in str(motor.url)
    finally:
        motor.dispose()


def test_la_contrasena_conserva_sus_espacios_internos(tmp_path):
    url = url_de_conexion(_entorno(tmp_path), _secreto(tmp_path, " a b \r\n"))
    assert url.password == " a b "  # noqa: S105 (sintética)


def test_un_secreto_ilegible_da_un_error_sin_cadena(tmp_path):
    directorio = tmp_path / "secreto"
    directorio.mkdir()
    (directorio / "x").write_text("x")
    # Un directorio no es is_file(): se trata como sin secreto.
    assert url_de_conexion(_entorno(tmp_path), directorio).password is None
    archivo = tmp_path / "binario"
    archivo.write_bytes(b"\xff\xfe" + CLAVE.encode())
    with pytest.raises(ErrorDeConexion) as error:
        url_de_conexion(_entorno(tmp_path), archivo)
    assert error.value.__context__ is None and error.value.__cause__ is None
    _sin_secretos("".join(traceback.format_exception(error.value)))


def test_una_url_mal_formada_con_contrasena_no_la_cita_ni_la_encadena():
    # Armada por partes: ninguna prueba trae una URL con credenciales escrita (RNF-8).
    entorno = {VARIABLE_URL: "postgresql://" + USUARIO + ":" + CLAVE + "@host:puerto/oip"}
    with pytest.raises(ErrorDeConexion) as error:
        url_de_conexion(entorno, None)
    texto = "".join(traceback.format_exception(error.value))
    assert CLAVE not in texto and USUARIO not in texto
    assert error.value.__context__ is None and error.value.__cause__ is None


@pytest.mark.parametrize(
    "operacion",
    [
        lambda r: r.version_configuracion(1),
        lambda r: r.guardar_version_configuracion(CONFIG, cargada_en=T0),
        lambda r: r.guardar_producto(_producto()),
        lambda r: r.guardar_observacion(_nueva(1, primera=True)),
        lambda r: r.guardar_registro_rechazo(_rechazo(id_carga=None, renglon=None)),
        lambda r: r.oportunidades_abiertas(instante=T0),
    ],
    ids=["leer-config", "guardar-config", "producto", "observacion", "rechazo", "oportunidades"],
)
def test_ningun_metodo_filtra_la_url_ni_la_contrasena_al_fallar(tmp_path, caplog, operacion):
    caplog.set_level(logging.DEBUG)
    nombres = ("sqlalchemy.engine", "sqlalchemy.pool", "sqlalchemy.dialects", "psycopg")
    for nombre in nombres:
        logging.getLogger(nombre).setLevel(logging.DEBUG)
    repo = RepositorioPostgres.desde_entorno(_entorno(tmp_path), _secreto(tmp_path))
    try:
        with pytest.raises(ErrorDeConexion) as error:
            operacion(repo)
    finally:
        repo.cerrar()
        for nombre in nombres:
            logging.getLogger(nombre).setLevel(logging.NOTSET)
    completo = "".join(traceback.format_exception(error.value))
    _sin_secretos(completo, tmp_path)
    assert USUARIO not in completo
    assert error.value.__context__ is None and error.value.__cause__ is None
    # En DEBUG, el logger propio de psycopg registra el host del intento (no la URL, el
    # usuario ni la contraseña); ver la observación en #34.
    _sin_secretos(caplog.text)
    assert USUARIO not in caplog.text and "oip_t06" not in caplog.text


def test_el_alias_no_sale_en_los_errores_de_una_solicitud(repo, caplog):
    alias = "alias-tester-t06"
    caplog.set_level(logging.DEBUG)
    _carga(repo)
    solicitud = leer_captura(
        TipoRegistro.CLIENT_REQUEST,
        {
            "clientAlias": alias,
            "items": ["T-6"],
            "quantity": 2,
            "modality": "link_only",
            "date": "2026-11-16",
        },
    )
    nueva = CapturaNueva(UUID(int=61), solicitud, _h(61), CARGA, T0)
    assert repo.guardar_captura(nueva)
    # Otra con el mismo id (choca la clave primaria) y otra huella.
    with pytest.raises(ErrorDeIntegridad) as error:
        repo.guardar_captura(dataclasses.replace(nueva, huella=_h(62)))
    texto = "".join(traceback.format_exception(error.value))
    assert alias not in texto
    assert error.value.__context__ is None and error.value.__cause__ is None
    # Un alias con un carácter nulo: el error cita la columna, no el valor.
    con_nulo = solicitud.model_copy(update={"client_alias": alias + "\x00"})
    with pytest.raises(ValueError) as error:
        repo.guardar_captura(CapturaNueva(UUID(int=63), con_nulo, _h(63), CARGA, T0))
    assert alias not in str(error.value) and "client_alias" in str(error.value)
    (leida,) = repo.capturas(TipoRegistro.CLIENT_REQUEST, instante=T0)
    assert alias not in repr(leida)
    assert alias not in caplog.text


# === Migración 0003 contra PostgreSQL (integración) =========================================


@pytest.fixture
def motor():
    motor = crear_motor(_url())
    _limpiar(motor)
    try:
        yield motor
    finally:
        _limpiar(motor)
        motor.dispose()


@pytest.mark.integracion
def test_head_coincide_con_el_modelo_vigente(motor):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    _alembic(motor, "upgrade", "head")
    with motor.connect() as conexion:
        diferencias = compare_metadata(MigrationContext.configure(conexion), tablas.metadata)
    # Lo que la reflexión no compara bien: el índice con expresión (coalesce) y los
    # índices que agrega TimescaleDB a las hypertables.
    diferencias = [
        d
        for d in diferencias
        if not (
            isinstance(d, tuple)
            and d[0] in ("add_index", "remove_index")
            and (
                d[1].name == "uq_listing_retailer_url_store"
                or str(d[1].name).endswith("_observed_at_idx")
            )
        )
    ]
    assert diferencias == []


@pytest.mark.integracion
def test_0003_bajar_con_un_rechazo_guardado_impide_volver_a_subir_sin_dejar_nada_a_medias(motor):
    """La reversión de 0003 borra ``line_number`` (está documentado). Con un registro de
    rechazo guardado, al volver a subir el registro queda sin renglón y la subida falla
    por ``ck_evaluation_renglon_del_rechazo``: se comprueba que no deja la base a medias."""
    _alembic(motor, "upgrade", "head")
    repositorio = RepositorioPostgres(motor)
    _carga(repositorio)
    repositorio.guardar_rechazo_carga(RechazoCarga(CARGA, 4, "DOMINIO NO AUTORIZADO"), _rechazo())
    _alembic(motor, "downgrade", "0002_hypertables")
    with pytest.raises(Exception, match="ck_evaluation_renglon_del_rechazo"):
        _alembic(motor, "upgrade", "head")
    with motor.connect() as c:
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "0002_hypertables"
        )
        assert c.execute(text("SELECT count(*) FROM evaluation")).scalar_one() == 1


# === Segunda pasada: el evaluador de CHECK en memoria (_checks) ============================
#
# Fuente: tasks.md T06 ("la misma batería de contrato pasa con memoria y con PostgreSQL") y
# la semántica de PostgreSQL: un CHECK se cumple si da verdadero o nulo (lógica de tres
# valores), se evalúan en orden alfabético de nombre, ``x[k]`` fuera de rango es NULL,
# ``btrim(x)`` quita solo espacios, ``IS NOT DISTINCT FROM`` nunca es NULL, un NULL dentro de
# un arreglo nunca está contenido (``<@``) y, en una expresión regular avanzada (ARE) sin
# modo sensible a saltos de línea, ``$`` solo coincide al final del texto.

_FALSO, _VERDADERO, _NULO = False, True, None


def _check(tabla: str, nombre: str, **valores):
    """El valor (verdadero, falso o nulo) del CHECK ``ck_<tabla>_<nombre>`` sobre la fila de
    ``tabla`` con ``valores`` y el resto de columnas en NULL."""
    from oip.persistencia.repositorios import _checks

    fila = {c.name: None for c in tablas.metadata.tables[tabla].columns} | valores
    return dict(_checks.CHECKS[tabla])[f"ck_{tabla}_{nombre}"](fila)


_T1 = T0 + dt.timedelta(hours=1)

_DEFECTO_FIN_DE_LINEA = (
    "IMPLEMENTATION DEFECT (T06, oip-tester, 2a pasada): _checks evalúa '~' con re.search, "
    "donde '$' también coincide antes de un salto de línea final; en PostgreSQL (ARE) '$' "
    "solo coincide al final del texto, así que PostgreSQL rechaza lo que memoria acepta"
)


@pytest.mark.parametrize(
    ("tabla", "nombre", "valores", "esperado"),
    [
        # Comparación simple y NULL.
        ("load_rejection", "line_number_positivo", {"line_number": None}, _NULO),
        ("load_rejection", "line_number_positivo", {"line_number": 0}, _FALSO),
        ("load_rejection", "line_number_positivo", {"line_number": 1}, _VERDADERO),
        ("load_run", "finished_at_orden", {"started_at": T0, "finished_at": T0}, _VERDADERO),
        ("load_run", "finished_at_orden", {"started_at": _T1, "finished_at": T0}, _FALSO),
        ("load_run", "finished_at_orden", {"started_at": T0}, _NULO),
        # AND de tres valores: NULL AND FALSO = FALSO; NULL AND VERDADERO = NULL.
        (
            "load_run",
            "conteos_no_negativos",
            {"loaded": None, "rejected": -1, "duplicates": 0},
            _FALSO,
        ),
        (
            "load_run",
            "conteos_no_negativos",
            {"loaded": None, "rejected": 0, "duplicates": 0},
            _NULO,
        ),
        # OR de tres valores: NULL OR FALSO = NULL; FALSO OR VERDADERO = VERDADERO.
        ("local_comparable", "mxn_con_tipo_de_cambio", {}, _NULO),
        ("local_comparable", "mxn_con_tipo_de_cambio", {"currency": "USD"}, _VERDADERO),
        ("local_comparable", "mxn_con_tipo_de_cambio", {"currency": "MXN"}, _FALSO),
        (
            "local_comparable",
            "mxn_con_tipo_de_cambio",
            {"currency": "MXN", "exchange_rate": Decimal("17.5")},
            _VERDADERO,
        ),
        ("load_run", "record_type_solo_csv", {"record_type": "msrp"}, _NULO),
        ("load_run", "record_type_solo_csv", {"format": "jsonl", "record_type": "msrp"}, _FALSO),
        ("load_run", "record_type_solo_csv", {"format": "jsonl"}, _VERDADERO),
        # IN: NULL da NULL; fuera del catálogo, FALSO.
        ("load_run", "format_catalogo", {}, _NULO),
        ("load_run", "format_catalogo", {"format": "csv"}, _VERDADERO),
        ("load_run", "format_catalogo", {"format": "CSV"}, _FALSO),
        # BETWEEN y cardinality.
        ("client_request", "items_de_1_a_3", {}, _NULO),
        ("client_request", "items_de_1_a_3", {"items": []}, _FALSO),
        ("client_request", "items_de_1_a_3", {"items": ["a"]}, _VERDADERO),
        ("client_request", "items_de_1_a_3", {"items": ["a", "b", "c"]}, _VERDADERO),
        ("client_request", "items_de_1_a_3", {"items": ["a", "b", "c", "d"]}, _FALSO),
        # <@: vacío contenido; NULL dentro nunca contenido; arreglo NULL, NULL.
        ("evaluation", "reasons_catalogo", {"reasons": []}, _VERDADERO),
        ("evaluation", "reasons_catalogo", {"reasons": ["EVITAR", "EVITAR"]}, _VERDADERO),
        ("evaluation", "reasons_catalogo", {"reasons": ["EVITAR", None]}, _FALSO),
        ("evaluation", "reasons_catalogo", {"reasons": ["evitar"]}, _FALSO),
        ("evaluation", "reasons_catalogo", {}, _NULO),
        # IS NOT DISTINCT FROM y subíndice desde 1 (fuera de rango = NULL).
        ("evaluation", "motivo_principal", {"reasons": []}, _VERDADERO),
        ("evaluation", "motivo_principal", {}, _VERDADERO),
        ("evaluation", "motivo_principal", {"main_reason": "EVITAR"}, _FALSO),
        (
            "evaluation",
            "motivo_principal",
            {"main_reason": "PARTICULAR", "reasons": ["EVITAR", "PARTICULAR"]},
            _FALSO,
        ),
        ("evaluation", "motivo_principal", {"main_reason": None, "reasons": ["EVITAR"]}, _FALSO),
        # NOT y paréntesis: FALSO OR (VERDADERO AND NULL) = NULL; ... AND NOT VERDADERO = FALSO.
        ("evaluation", "reevaluacion", {"changed_references": []}, _NULO),
        (
            "evaluation",
            "reevaluacion",
            {"changed_references": [], "no_longer_recommended": True},
            _FALSO,
        ),
        (
            "evaluation",
            "reevaluacion",
            {"changed_references": ["precio_habitual"], "no_longer_recommended": False},
            _FALSO,
        ),
        (
            "evaluation",
            "reevaluacion",
            {"changed_references": [], "no_longer_recommended": False},
            _VERDADERO,
        ),
        (
            "evaluation",
            "reevaluacion",
            {
                "previous_evaluation_id": UUID(int=1),
                "changed_references": ["x"],
                "no_longer_recommended": True,
            },
            _VERDADERO,
        ),
        # (a = b) = (c IS NOT NULL): igualdad de booleanos; NULL se propaga.
        ("evaluation", "aviso_solo_con_nivel", {}, _NULO),
        ("evaluation", "aviso_solo_con_nivel", {"result": "SIN_NIVEL"}, _VERDADERO),
        (
            "evaluation",
            "aviso_solo_con_nivel",
            {"result": "SIN_NIVEL", "alert_level": "VIGILAR"},
            _FALSO,
        ),
        (
            "evaluation",
            "aviso_solo_con_nivel",
            {"result": "NIVEL_ASIGNADO", "alert_level": "VIGILAR", "alert_channel": "amazon"},
            _FALSO,  # sin chosen_channel
        ),
        (
            "evaluation",
            "aviso_solo_con_nivel",
            {
                "result": "NIVEL_ASIGNADO",
                "alert_level": "VIGILAR",
                "alert_channel": "amazon",
                "chosen_channel": "amazon",
            },
            _VERDADERO,
        ),
        (
            "evaluation",
            "rechazo_con_motivo",
            {"result": "RECHAZADA_VALIDACION"},
            _FALSO,
        ),
        # btrim quita solo espacios (no tabuladores).
        ("product", "brand_no_vacio", {"brand": "   "}, _FALSO),
        ("product", "brand_no_vacio", {"brand": " a "}, _VERDADERO),
        ("product", "brand_no_vacio", {"brand": "\t"}, _VERDADERO),
        ("product", "brand_no_vacio", {}, _NULO),
        # jsonb_typeof.
        ("config_version", "content_objeto", {"content": "{}"}, _VERDADERO),
        ("config_version", "content_objeto", {"content": "[]"}, _FALSO),
        ("config_version", "content_objeto", {"content": "null"}, _FALSO),
        ("config_version", "content_objeto", {"content": '"{}"'}, _FALSO),
        ("config_version", "content_objeto", {}, _NULO),
        ("evaluation", "observations_used_arreglo", {"observations_used": "[]"}, _VERDADERO),
        # Expresión regular (~).
        ("config_version", "sha256_sha256", {"sha256": _h(1)}, _VERDADERO),
        ("config_version", "sha256_sha256", {"sha256": "A" * 64}, _FALSO),
        ("config_version", "sha256_sha256", {"sha256": "a" * 63}, _FALSO),
        ("config_version", "sha256_sha256", {}, _NULO),
        ("load_rejection", "field_nombre", {"field": "price.current"}, _VERDADERO),
        ("load_rejection", "field_nombre", {"field": "1precio"}, _FALSO),
        ("load_rejection", "field_nombre", {"field": ".*"}, _FALSO),
        ("load_rejection", "reason_catalogo", {"reason": "PRECIO INVÁLIDO"}, _VERDADERO),
        (
            "load_rejection",
            "reason_catalogo",
            {"reason": "CAMPO OBLIGATORIO FALTANTE (price.current)"},
            _VERDADERO,
        ),
        ("load_rejection", "reason_catalogo", {"reason": "precio inválido"}, _FALSO),
        ("load_rejection", "reason_catalogo", {"reason": "CAMPO OBLIGATORIO FALTANTE ()"}, _FALSO),
        # '$' de una ARE: solo al final del texto (no antes de un salto de línea final).
        pytest.param(
            "load_rejection",
            "field_nombre",
            {"field": "precio\n"},
            _FALSO,
            marks=pytest.mark.xfail(strict=True, reason=_DEFECTO_FIN_DE_LINEA),
        ),
        pytest.param(
            "load_rejection",
            "reason_catalogo",
            {"reason": "CAMPO OBLIGATORIO FALTANTE (model)\n"},
            _FALSO,
            marks=pytest.mark.xfail(strict=True, reason=_DEFECTO_FIN_DE_LINEA),
        ),
        pytest.param(
            "evaluation",
            "rejection_reason_catalogo",
            {"rejection_reason": "CAMPO OBLIGATORIO FALTANTE (model)\n"},
            _FALSO,
            marks=pytest.mark.xfail(strict=True, reason=_DEFECTO_FIN_DE_LINEA),
        ),
    ],
)
def test_cada_check_del_esquema_da_lo_mismo_que_postgresql(tabla, nombre, valores, esperado):
    assert _check(tabla, nombre, **valores) is esperado


def test_varios_check_violados_se_informa_el_primero_por_nombre_como_postgresql():
    """PostgreSQL prueba los CHECK de una fila en orden alfabético de nombre."""
    from oip.persistencia.repositorios import _checks

    fila = {c.name: None for c in tablas.evaluation.columns} | {
        "main_reason": "EVITAR",  # motivo_principal: EVITAR vs NULL -> falso
        "reasons": ["NO EXISTE"],  # reasons_catalogo -> falso
        "result": "OTRO",  # result_catalogo -> falso
        "confidence": "NINGUNA",  # confidence_catalogo -> falso
    }
    assert _checks.violado("evaluation", fila) == "ck_evaluation_confidence_catalogo"


@pytest.mark.parametrize(
    "texto",
    [
        "upper(x) = 'A'",
        "coalesce(x, '') <> ''",
        "x LIKE 'a%'",
        "x + 1 > 2",
        "x = -1",
        "x ~* 'a'",
        "x !~ 'a'",
        "x IS TRUE",
        "x IN (SELECT y FROM t)",
        '"X" > 0',
        "x = 1 = 2",
        "x = 1.5e3",
        "x = E'a'",
        "(x > 0",
        "x > 0)",
        "x > 0; DROP TABLE t",
        "x BETWEEN 1",
        "",
    ],
)
def test_un_check_fuera_del_subconjunto_falla_de_forma_explicita(texto):
    from oip.persistencia.repositorios import _checks

    with pytest.raises(NotImplementedError):
        _checks._Analizador(texto).todo()


def test_el_evaluador_no_ejecuta_codigo_construido_desde_texto():
    """Sin ``eval``/``exec``/``compile``/``__import__``; la única expresión regular que
    compila es su tokenizador, desde una constante."""
    import ast
    import inspect

    from oip.persistencia.repositorios import _checks

    arbol = ast.parse(inspect.getsource(_checks))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Call):
            funcion = nodo.func
            nombre = getattr(funcion, "id", None) or getattr(funcion, "attr", None)
            assert nombre not in {"eval", "exec", "compile", "__import__", "getattr"} or (
                nombre == "compile" and all(isinstance(a, ast.Constant) for a in nodo.args)
            ), ast.dump(nodo)


@pytest.mark.parametrize(
    ("tabla", "nombre", "valores"),
    [
        ("load_run", "format_catalogo", {"format": "csv' OR '1'='1"}),
        ("load_run", "format_catalogo", {"format": "csv') OR (1=1"}),
        ("product", "category_catalogo", {"category": "tools' OR category IS NOT NULL OR '"}),
        ("load_rejection", "field_nombre", {"field": "a') OR ('1"}),
        ("load_rejection", "reason_catalogo", {"reason": "PRECIO INVÁLIDO' OR 'a'='a"}),
        ("evaluation", "reasons_catalogo", {"reasons": ["EVITAR'] OR TRUE OR ARRAY['x"]}),
        ("config_version", "sha256_sha256", {"sha256": "' OR sha256 IS NULL OR '"}),
    ],
)
def test_un_valor_con_sql_no_altera_la_evaluacion(tabla, nombre, valores):
    assert _check(tabla, nombre, **valores) is _FALSO


def test_un_dato_no_se_usa_como_expresion_regular():
    """Solo el literal del esquema es patrón: un dato con metacaracteres se compara tal cual."""
    assert _check("config_version", "sha256_sha256", sha256="^.*$") is _FALSO
    assert _check("load_rejection", "field_nombre", field="a|b") is _FALSO


# --- Equivalencia memoria / PostgreSQL a nivel repositorio ----------------------------------


def _xfail_memoria(defecto: str):
    return [
        pytest.param("memoria", marks=pytest.mark.xfail(strict=True, reason=defecto)),
        pytest.param("postgres", marks=pytest.mark.integracion),
    ]


@pytest.mark.parametrize("param", _xfail_memoria(_DEFECTO_FIN_DE_LINEA))
@pytest.mark.parametrize(
    "rechazo",
    [
        {"motivo": "PRECIO INVÁLIDO", "campo": "precio\n"},
        {"motivo": "CAMPO OBLIGATORIO FALTANTE (model)\n"},
    ],
    ids=["campo", "motivo"],
)
def test_un_salto_de_linea_final_se_rechaza_igual_que_en_postgresql(param, rechazo):
    """PostgreSQL rechaza ``field``/``reason`` con ``\\n`` final (``~ '...$'``): ninguna de
    las dos implementaciones guarda el renglón. Vale rechazarlo al construirlo
    (``ValueError``) o al guardarlo (``ErrorDeIntegridad``)."""
    for repositorio in _repo_de(param):
        _carga(repositorio)
        with pytest.raises((ValueError, ErrorDeIntegridad)):
            repositorio.guardar_rechazo_carga(RechazoCarga(CARGA, 2, **rechazo))
        assert _filas_de(repositorio, tablas.load_rejection) == []


@pytest.mark.parametrize(
    "param", ["memoria", pytest.param("postgres", marks=pytest.mark.integracion)]
)
def test_terminar_una_carga_que_viola_un_check_no_cambia_la_carga(param):
    """Un cierre que viola ``ck_load_run_finished_at_orden`` se rechaza antes de escribir
    (``ValueError``) o por el CHECK (``ErrorDeIntegridad``), y la carga queda sin terminar."""
    for repositorio in _repo_de(param):
        _carga(repositorio)
        antes = _filas_de(repositorio, tablas.load_run)
        reporte = ReporteCarga(T0 - MICRO, 0, 0, 0, {})
        with pytest.raises((ValueError, ErrorDeIntegridad)) as error:
            repositorio.terminar_carga(CARGA, reporte)
        if isinstance(error.value, ErrorDeIntegridad):
            assert error.value.restriccion == "ck_load_run_finished_at_orden"
        assert _filas_de(repositorio, tablas.load_run) == antes
        assert repositorio.leer_carga(CARGA).reporte is None


@pytest.mark.parametrize(
    "param", ["memoria", pytest.param("postgres", marks=pytest.mark.integracion)]
)
def test_el_borde_de_integer_se_guarda_y_uno_mas_no(param):
    for repositorio in _repo_de(param):
        _carga(repositorio)
        repositorio.guardar_rechazo_carga(RechazoCarga(CARGA, 2**31 - 1, "PRECIO INVÁLIDO"))
        with pytest.raises(ValueError):
            repositorio.guardar_rechazo_carga(RechazoCarga(CARGA, 2**31, "PRECIO INVÁLIDO"))
        assert [f["line_number"] for f in _filas_de(repositorio, tablas.load_rejection)] == [
            2**31 - 1
        ]


@pytest.mark.parametrize(
    ("columna", "valor", "cabe"),
    [
        (tablas.load_rejection.c.line_number, 2**31 - 1, True),
        (tablas.load_rejection.c.line_number, 2**31, False),
        (tablas.load_rejection.c.line_number, -(2**31), True),
        (tablas.load_rejection.c.line_number, -(2**31) - 1, False),
        (tablas.evaluation.c.config_version_id, 2**63 - 1, True),
        (tablas.evaluation.c.config_version_id, 2**63, False),
        (tablas.evaluation.c.config_version_id, -(2**63), True),
        (tablas.evaluation.c.config_version_id, -(2**63) - 1, False),
        (tablas.client_request.c.idempotency_key, _h(1), True),
        (tablas.client_request.c.idempotency_key, _h(1) + "0", False),
    ],
)
def test_los_rangos_de_integer_bigint_y_char_son_los_de_postgresql(columna, valor, cabe):
    from oip.persistencia.repositorios import _columnas

    if cabe:
        assert _columnas._valor(columna, valor, "ruta") == valor
    else:
        with pytest.raises(ValueError):
            _columnas._valor(columna, valor, "ruta")


def test_un_booleano_no_entra_en_un_entero():
    from oip.persistencia.repositorios import _columnas

    with pytest.raises(TypeError):
        _columnas._valor(tablas.load_rejection.c.line_number, True, "ruta")
