"""Batería de contrato del repositorio (T06; CMP-20, RNF-8; design.md §5 y §12).

La **misma** batería corre sobre ``RepositorioMemoria`` (en CI) y sobre
``RepositorioPostgres`` (``@pytest.mark.integracion``: se salta sin
``OIP_TEST_DATABASE_URL``, DEC-233). Comportamientos de tasks.md T06:

- la misma batería pasa con memoria y con PostgreSQL;
- un duplicado por clave de idempotencia (TAB-08) o por huella (TAB-09) no se guarda dos
  veces y no escribe nada;
- ninguna lectura devuelve datos posteriores al instante;
- una transacción por registro y por evaluación: si algo falla, no queda nada;
- ``Decimal`` de ida y vuelta sin ``float`` ni redondeos; los motivos conservan su orden;
- el registro de un rechazo de validación no guarda nada del renglón (DEC-250).

Las pruebas de la conexión (la URL y la contraseña nunca en logs, ``repr`` ni excepciones)
están en ``tests/test_repositorios_conexion.py``.

Determinista: el instante siempre explícito, sin reloj ni red. Fixtures sintéticos con el
comercio ``tienda-prueba`` (example.com); ninguna URL se abre. La base de
``OIP_TEST_DATABASE_URL`` debe ser **desechable**: cada prueba borra las tablas de OIP.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import logging
import os
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import func, select, text

from config_tienda_prueba import TIENDA_PRUEBA, con_tienda_prueba, configuracion_con_tienda_prueba
from oip.catalogos import (
    CalidadPrecio,
    Canal,
    CausaCanalCerrado,
    Confianza,
    EstadoCanal,
    Identificacion,
    Motivo,
    Nivel,
    ReferenciaPrecio,
    Resultado,
    TipoRegistro,
)
from oip.configuracion import cargar_configuracion_texto
from oip.entradas.capturas import leer_captura
from oip.entradas.contrato import leer_observacion
from oip.evaluacion.contexto import (
    ContextoEvaluacion,
    Episodio,
    EvaluacionCanal,
    ObservacionRegistrada,
    ObservacionUsada,
    Referencias,
    RegistroEvaluacion,
)
from oip.persistencia import tablas
from oip.persistencia.repositorios import (
    CapturaNueva,
    Carga,
    ErrorDeIntegridad,
    ErrorRepositorio,
    IdentificadorProducto,
    ObservacionNueva,
    Producto,
    Publicacion,
    RechazoCarga,
    RegistroRechazo,
    ReporteCarga,
    Repositorio,
    RepositorioMemoria,
    RepositorioPostgres,
    crear_motor,
)

RAIZ = Path(__file__).resolve().parent.parent
_VARIABLE = "OIP_TEST_DATABASE_URL"
CONFIG = configuracion_con_tienda_prueba()
T0 = dt.datetime(2026, 11, 16, 18, 0, tzinfo=dt.UTC)
ZONA = "America/Tijuana"


def _t(horas: float) -> dt.datetime:
    return T0 + dt.timedelta(hours=horas)


def _huella(n: int) -> str:
    return f"{n:064x}"


# --- Las dos implementaciones ---------------------------------------------------------------


def _url():
    from sqlalchemy.engine import make_url

    valor = os.environ.get(_VARIABLE, "").strip()
    if not valor:
        pytest.skip(f"sin {_VARIABLE}: las pruebas de integración se saltan (DEC-233)")
    url = make_url(valor)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    return url


def _limpiar(motor) -> None:
    nombres = ", ".join([*tablas.metadata.tables, "alembic_version"])
    with motor.begin() as conexion:
        conexion.execute(text("DROP VIEW IF EXISTS open_opportunity"))
        conexion.execute(text(f"DROP TABLE IF EXISTS {nombres} CASCADE"))


def _migrar_head(motor) -> None:
    from alembic import command
    from alembic.config import Config

    with motor.connect() as conexion:
        hay = conexion.execute(
            text("SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb'")
        ).first()
    if hay is None:
        pytest.fail("la base de OIP_TEST_DATABASE_URL no tiene la extensión timescaledb")
    with motor.begin() as conexion:
        config = Config(str(RAIZ / "alembic.ini"))
        config.attributes["connection"] = conexion
        command.upgrade(config, "head")


@pytest.fixture(
    params=["memoria", pytest.param("postgres", marks=pytest.mark.integracion)],
)
def repo(request):
    if request.param == "memoria":
        yield RepositorioMemoria()
        return
    motor = crear_motor(_url())
    _limpiar(motor)
    try:
        _migrar_head(motor)
        repositorio = RepositorioPostgres(motor)
        repositorio._motor_de_pruebas = motor  # para leer filas crudas
        yield repositorio
    finally:
        _limpiar(motor)
        motor.dispose()


def _fila_cruda(repo, tabla, columna: str, valor: Any) -> dict[str, Any] | None:
    """La fila tal como quedó guardada (para comprobar lo que **no** se guarda)."""
    if isinstance(repo, RepositorioMemoria):
        filas = [f for f in repo._tablas[tabla.name].filas if f[columna] == valor]
    else:
        with repo._motor_de_pruebas.connect() as c:
            filas = [
                dict(r._mapping) for r in c.execute(tabla.select().where(tabla.c[columna] == valor))
            ]
    return filas[0] if filas else None


def _cuenta(repo, tabla) -> int:
    if isinstance(repo, RepositorioMemoria):
        return len(repo._tablas[tabla.name].filas)
    with repo._motor_de_pruebas.connect() as c:
        return c.execute(select(func.count()).select_from(tabla)).scalar_one()


# --- Datos sintéticos -----------------------------------------------------------------------

ID_PRODUCTO = UUID(int=100)
ID_PUBLICACION = UUID(int=200)
ID_FICHA_PUB = UUID(int=201)


def _observacion(**cambios):
    datos = {
        "retailerCode": TIENDA_PRUEBA,
        "storeCode": "tp-01",
        "productUrl": "https://tienda.example.com/p/123",
        "title": "Taladro de prueba",
        "brand": "MarcaP",
        "model": "MP-1",
        "gtin": "0123456789012",
        "category": "tools",
        "weightKg": Decimal("4.125"),
        "dimsCm": {"l": Decimal("30.5"), "w": Decimal("20")},
        "price": {"current": "29.5", "was": "129.00", "currency": "USD"},
        "seller": "comercio",
        "condition": "new",
        "availability": {"state": "in_stock", "quantity": 3, "scope": "store", "text": "3 disp."},
        "isClearance": True,
        "purchaseMode": "tienda",
        "taxLocation": "chula_vista",
        "shipping": {"toMeCost": "0.00", "days": 2, "mode": "pickup"},
        "msrp": {"value": "149.00", "source": "fabricante", "date": "2026-11-10"},
        "extractedAt": "2026-11-16T10:00:00-08:00",
        "extractionMethod": "manual",
        "sourceType": "clearance",
        "blocked": False,
        "evidence": {"nota": "no se guarda"},
    }
    datos.update(cambios)
    return leer_observacion(datos)


def _ficha(**cambios):
    return _observacion(
        storeCode=None,
        productUrl="https://amazon.example.com/dp/X",
        price={"current": "105.00"},
        purchaseMode="envio",
        amazonListing={"buyBoxPrice": "105.00", "sellersNew": 4, "rankMain": 12000},
        **cambios,
    )


def _producto() -> Producto:
    return Producto(ID_PRODUCTO, T0, "MarcaP", "MP-1", None, None)


def _publicacion(id_=ID_PUBLICACION, url="https://tienda.example.com/p/123", tienda="tp-01"):
    return Publicacion(id_, ID_PRODUCTO, TIENDA_PRUEBA, url, T0, tienda)


def _nueva(n: int, observacion=None, *, clave=None, carga=None, primera=False, **cambios):
    observacion = observacion or _observacion()
    publicacion = cambios.pop("publicacion", _publicacion() if primera else None)
    return ObservacionNueva(
        registrada=ObservacionRegistrada(
            observacion, UUID(int=n), cambios.pop("id_publicacion", ID_PUBLICACION), ID_PRODUCTO
        ),
        identificacion=Identificacion.CONFIRMED,
        clave_idempotencia=clave or f"{TIENDA_PRUEBA}|obs-{n}",
        origen="file" if carga else "worker",
        recibida_en=_t(1),
        id_carga=carga,
        producto=_producto() if primera else None,
        identificadores=(IdentificadorProducto("gtin", "0123456789012"),) if primera else (),
        publicacion=publicacion,
        **cambios,
    )


def _con_config(repo) -> int:
    version, _ = repo.guardar_version_configuracion(CONFIG, cargada_en=T0 - dt.timedelta(days=1))
    return version.id


# --- La interfaz ------------------------------------------------------------------------------


def test_las_dos_implementaciones_cumplen_la_interfaz(repo):
    assert isinstance(repo, Repositorio)
    assert "postgresql" not in repr(repo) and "@" not in repr(repo)


# --- TAB-01 configuración ---------------------------------------------------------------------


def test_la_version_de_configuracion_vuelve_completa_y_es_idempotente_por_sha256(repo):
    version, nueva = repo.guardar_version_configuracion(CONFIG, cargada_en=T0)
    assert nueva
    assert version.configuracion == CONFIG
    assert version.cargada_en == T0
    otra, nueva_otra = repo.guardar_version_configuracion(CONFIG, cargada_en=_t(5))
    assert not nueva_otra and otra == version
    leida = repo.version_configuracion(version.id)
    assert leida == version
    assert repo.version_configuracion(version.id + 1000) is None


def test_la_misma_version_con_otro_contenido_choca(repo):
    repo.guardar_version_configuracion(CONFIG, cargada_en=T0)
    texto = con_tienda_prueba((RAIZ / "tests/fixtures/config/base.yaml").read_text("utf-8"))
    otra = cargar_configuracion_texto(
        texto.replace("timezone: America/Tijuana", "timezone: America/Los_Angeles")
    )
    assert otra.version == CONFIG.version and otra.sha256 != CONFIG.sha256
    with pytest.raises(ErrorDeIntegridad) as error:
        repo.guardar_version_configuracion(otra, cargada_en=_t(1))
    assert error.value.restriccion == "uq_config_version_version"


def _otra_version(numero: str):
    texto = con_tienda_prueba((RAIZ / "tests/fixtures/config/base.yaml").read_text("utf-8"))
    return cargar_configuracion_texto(
        texto.replace(f'version: "{CONFIG.version}"', f'version: "{numero}"', 1)
    )


def test_la_configuracion_activa_es_la_mas_reciente_hasta_el_instante(repo):
    assert repo.version_configuracion_activa(T0) is None
    v1, _ = repo.guardar_version_configuracion(CONFIG, cargada_en=T0)
    v2, _ = repo.guardar_version_configuracion(_otra_version("9999.1"), cargada_en=_t(10))
    assert repo.version_configuracion_activa(T0 - dt.timedelta(seconds=1)) is None
    assert repo.version_configuracion_activa(T0) == v1
    assert repo.version_configuracion_activa(_t(9.99)) == v1
    assert repo.version_configuracion_activa(_t(10)) == v2
    # Otra zona, el mismo instante.
    tijuana = _t(10).astimezone(dt.timezone(dt.timedelta(hours=-8)))
    assert repo.version_configuracion_activa(tijuana) == v2


def test_una_lectura_sin_instante_con_zona_se_rechaza(repo):
    with pytest.raises(TypeError):
        repo.version_configuracion_activa(dt.datetime(2026, 11, 16, 18, 0))  # noqa: DTZ001
    with pytest.raises(TypeError):
        repo.observaciones_del_producto(ID_PRODUCTO, instante=dt.datetime(2026, 11, 16))  # noqa: DTZ001


# --- TAB-03 y TAB-04 producto y publicación ----------------------------------------------------


def test_producto_e_identificadores(repo):
    repo.guardar_producto(_producto(), (IdentificadorProducto("gtin", "0123456789012"),))
    assert repo.leer_producto(ID_PRODUCTO) == _producto()
    assert repo.buscar_producto(IdentificadorProducto("gtin", "0123456789012")) == ID_PRODUCTO
    assert repo.buscar_producto(IdentificadorProducto("asin", "0123456789012")) is None
    assert repo.leer_producto(UUID(int=999)) is None
    with pytest.raises(ErrorDeIntegridad) as error:
        repo.guardar_producto(
            Producto(UUID(int=101), T0), (IdentificadorProducto("gtin", "0123456789012"),)
        )
    assert error.value.restriccion == "pk_product_identifier"
    # Una transacción: el producto 101 tampoco quedó.
    assert repo.leer_producto(UUID(int=101)) is None


def test_la_publicacion_se_busca_por_su_clave_con_tienda_o_sin_ella(repo):
    _con_config(repo)
    repo.guardar_observacion(_nueva(1, primera=True))
    sin_tienda = _publicacion(ID_FICHA_PUB, "https://amazon.example.com/dp/X", None)
    repo.guardar_observacion(
        _nueva(2, _ficha(), publicacion=sin_tienda, id_publicacion=ID_FICHA_PUB)
    )
    assert repo.buscar_publicacion(TIENDA_PRUEBA, "https://tienda.example.com/p/123", "tp-01") == (
        _publicacion()
    )
    assert repo.buscar_publicacion(TIENDA_PRUEBA, "https://amazon.example.com/dp/X", None) == (
        sin_tienda
    )
    assert repo.buscar_publicacion(TIENDA_PRUEBA, "https://tienda.example.com/p/123", None) is None


def test_la_misma_publicacion_dos_veces_choca_con_su_unico(repo):
    _con_config(repo)
    repo.guardar_observacion(_nueva(1, primera=True))
    otra = dataclasses.replace(_publicacion(), id=UUID(int=299))
    with pytest.raises(ErrorDeIntegridad) as error:
        repo.guardar_observacion(_nueva(2, publicacion=otra, id_publicacion=otra.id))
    assert error.value.restriccion == "uq_listing_retailer_url_store"


# --- TAB-05 a TAB-08 observaciones ---------------------------------------------------------------


def test_la_observacion_vuelve_con_lo_que_guardan_sus_columnas(repo):
    original = _observacion()
    assert repo.guardar_observacion(_nueva(1, original, primera=True))
    leida = repo.leer_observacion(UUID(int=1))
    assert leida.id == UUID(int=1)
    assert (leida.id_publicacion, leida.id_producto) == (ID_PUBLICACION, ID_PRODUCTO)
    o = leida.observacion
    # Igual (los montos con la escala de su columna: el mismo valor, nunca otro).
    assert o.price.current == original.price.current == Decimal("29.50")
    assert type(o.price.current) is Decimal and str(o.price.current) == "29.50"
    assert o.price.was == Decimal("129.00") and o.price.currency == "USD"
    assert o.weight_kg == Decimal("4.125") and str(o.weight_kg) == "4.125"
    assert o.dims_cm == {"l": Decimal("30.5"), "w": Decimal("20")}
    assert o.extracted_at == original.extracted_at and o.extracted_at.tzinfo is dt.UTC
    for campo in (
        "retailer_code",
        "store_code",
        "title",
        "category",
        "seller",
        "condition",
        "is_clearance",
        "purchase_mode",
        "tax_location",
        "msrp",
        "schema_version",
        "source_type",
        "extraction_method",
        "availability",
        "blocked",
    ):
        assert getattr(o, campo) == getattr(original, campo), campo
    assert o.product_url == "https://tienda.example.com/p/123"  # la canónica (TAB-04)
    assert o.shipping.to_me_cost == Decimal("0.00")
    # Sin columna: vuelven ausentes (documentado en _filas.observacion_de_filas).
    assert (o.brand, o.model, o.gtin, o.evidence, o.crawl_job_id, o.idempotency_key) == (None,) * 6
    assert (o.shipping.days, o.shipping.mode) == (None, None)
    assert not o.es_ficha_amazon


def test_la_ficha_de_amazon_vuelve_con_su_ficha(repo):
    sin_tienda = _publicacion(ID_FICHA_PUB, "https://amazon.example.com/dp/X", None)
    repo.guardar_producto(_producto())
    repo.guardar_observacion(
        _nueva(2, _ficha(), publicacion=sin_tienda, id_publicacion=ID_FICHA_PUB)
    )
    ficha = repo.leer_observacion(UUID(int=2)).observacion
    assert ficha.es_ficha_amazon
    assert ficha.amazon_listing == _ficha().amazon_listing
    assert ficha.store_code is None


def test_un_duplicado_por_clave_de_idempotencia_no_se_guarda_dos_veces(repo):
    assert repo.guardar_observacion(_nueva(1, primera=True, clave="k|1"))
    antes = {t: _cuenta(repo, t) for t in tablas.metadata.sorted_tables}
    # Mismo recibo con otra observación (otro id y otro precio): no escribe nada.
    otra = _nueva(2, _observacion(price={"current": "10.00"}), clave="k|1")
    assert not repo.guardar_observacion(otra)
    assert {t: _cuenta(repo, t) for t in tablas.metadata.sorted_tables} == antes
    assert repo.leer_observacion(UUID(int=2)) is None
    assert repo.observacion_por_clave("k|1") == UUID(int=1)
    assert repo.observacion_por_clave("k|2") is None


def test_una_observacion_es_una_transaccion(repo):
    # Sin la publicación (no existe y no se crea): falla la clave foránea y no queda nada,
    # ni el recibo, ni el producto nuevo.
    nueva = dataclasses.replace(_nueva(1, primera=True), publicacion=None)
    with pytest.raises(ErrorDeIntegridad) as error:
        repo.guardar_observacion(nueva)
    assert error.value.restriccion.startswith("fk_price_observation_listing_id")
    assert repo.observacion_por_clave(nueva.clave_idempotencia) is None
    assert repo.leer_producto(ID_PRODUCTO) is None
    # Después se guarda bien: el error no dejó nada a medias.
    assert repo.guardar_observacion(_nueva(1, primera=True))


def test_un_monto_con_mas_decimales_que_su_columna_no_se_redondea_ni_se_guarda(repo):
    nueva = _nueva(1, _observacion(shipping={"toMeCost": "1.005"}), primera=True)
    with pytest.raises(ValueError, match="no redondea") as error:
        repo.guardar_observacion(nueva)
    assert "1.005" not in str(error.value)
    assert repo.observacion_por_clave(nueva.clave_idempotencia) is None


def test_las_observaciones_del_producto_no_pasan_del_instante(repo):
    repo.guardar_observacion(_nueva(1, primera=True))
    for n, horas in ((2, 1), (3, 2), (4, 3)):
        hora = (T0 - dt.timedelta(hours=2) + dt.timedelta(hours=horas)).isoformat()
        repo.guardar_observacion(_nueva(n, _observacion(extractedAt=hora)))

    # extractedAt de la 1: 2026-11-16T18:00Z (= T0); 2, 3, 4: T0-1h, T0, T0+1h.
    def ids(**kw):
        return [r.id.int for r in repo.observaciones_del_producto(ID_PRODUCTO, **kw)]

    assert ids(instante=T0) == [2, 1, 3]  # orden: observed_at, id
    assert ids(instante=T0 - dt.timedelta(microseconds=1)) == [2]
    assert ids(instante=_t(1)) == [2, 1, 3, 4]
    assert ids(instante=_t(1), desde=T0) == [1, 3, 4]
    assert ids(instante=_t(-5)) == []
    assert repo.observaciones_del_producto(UUID(int=7), instante=_t(1)) == ()
    for registrada in repo.observaciones_del_producto(ID_PRODUCTO, instante=T0):
        assert registrada.observacion.extracted_at <= T0


def test_una_observacion_bloqueada_no_se_guarda():
    with pytest.raises(ValueError, match="blocked"):
        _nueva(1, _observacion(blocked=True))


# --- TAB-09 capturas ------------------------------------------------------------------------------

_CAPTURAS = {
    TipoRegistro.LOCAL_COMPARABLE: {
        "gtin": "0123456789012",
        "condition": "used",
        "askingPrice": "1500.00",
        "currency": "MXN",
        "exchangeRate": "17.3",
        "city": "tijuana",
        "date": "2026-11-10",
        "sold": False,
    },
    TipoRegistro.LOCAL_ESTIMATE: {"gtin": "0123456789012", "price": "90.5", "date": "2026-11-01"},
    TipoRegistro.MSRP: {
        "gtin": "0123456789012",
        "value": "149.00",
        "source": "fabricante",
        "date": "2026-10-01",
    },
    TipoRegistro.LOCAL_DEMAND: {"category": "tools", "level": "medium", "date": "2026-11-01"},
    TipoRegistro.STORE_VISIT: {
        "storeCode": "tp-01",
        "gtin": "0123456789012",
        "result": "found",
        "visitedAt": "2026-11-15T09:30:00",
    },
    TipoRegistro.ACTUAL_RESULT: {
        "evaluationId": str(UUID(int=55)),
        "channel": "local",
        "units": 2,
        "purchasePrice": "29.00",
        "salePrice": "76.61",
        "actualCosts": "9.50",
        "purchasedOn": "2026-11-16",
        "soldOn": "2026-11-20",
    },
    TipoRegistro.CLIENT_REQUEST: {
        "clientAlias": "cliente-sintetico-7",
        "items": ["MP-1", "MP-2"],
        "quantity": 1,
        "modality": "link_only",
        "date": "2026-11-16",
    },
}
_CON_PRODUCTO = {
    TipoRegistro.LOCAL_COMPARABLE,
    TipoRegistro.LOCAL_ESTIMATE,
    TipoRegistro.MSRP,
    TipoRegistro.STORE_VISIT,
}
ID_CARGA = UUID(int=900)


def _con_carga(repo, id_=ID_CARGA) -> Carga:
    carga = Carga(id_, "capturas.jsonl", _huella(1), "jsonl", T0, _con_config(repo))
    repo.iniciar_carga(carga)
    return carga


def _captura_nueva(tipo, n: int, *, capturada_en=T0, **datos) -> CapturaNueva:
    captura = leer_captura(tipo, {**_CAPTURAS[tipo], **datos}, zona=ZONA)
    return CapturaNueva(
        id=UUID(int=n),
        captura=captura,
        huella=_huella(n),
        id_carga=ID_CARGA,
        capturada_en=capturada_en,
        id_producto=ID_PRODUCTO if tipo in _CON_PRODUCTO else None,
    )


@pytest.mark.parametrize("tipo", list(_CAPTURAS), ids=str)
def test_cada_captura_vuelve_igual_y_su_huella_no_se_repite(repo, tipo):
    _con_carga(repo)
    repo.guardar_producto(_producto())
    nueva = _captura_nueva(tipo, 1)
    assert repo.guardar_captura(nueva)
    (leida,) = repo.capturas(tipo, instante=T0)
    assert leida.captura == nueva.captura
    assert (leida.id, leida.id_carga, leida.capturada_en) == (nueva.id, ID_CARGA, T0)
    assert leida.id_producto == nueva.id_producto
    # La misma huella otra vez (con otro id): no se guarda.
    assert not repo.guardar_captura(dataclasses.replace(nueva, id=UUID(int=2)))
    assert len(repo.capturas(tipo, instante=_t(1))) == 1


def test_el_comparable_en_mxn_conserva_el_precio_en_usd_sin_redondear(repo):
    _con_carga(repo)
    repo.guardar_producto(_producto())
    nueva = _captura_nueva(TipoRegistro.LOCAL_COMPARABLE, 1)
    repo.guardar_captura(nueva)
    (leida,) = repo.capturas(TipoRegistro.LOCAL_COMPARABLE, instante=T0)
    # 1500 / 17.3 sin redondear (S-23): se recalcula de los dos valores exactos.
    assert leida.captura.price_usd == Decimal("1500.00") / Decimal("17.3")
    assert leida.captura.exchange_rate == Decimal("17.3")


def test_las_capturas_no_pasan_del_instante_y_se_filtran_por_producto(repo):
    _con_carga(repo)
    repo.guardar_producto(_producto())
    repo.guardar_producto(Producto(UUID(int=101), T0))
    tipo = TipoRegistro.LOCAL_ESTIMATE
    repo.guardar_captura(_captura_nueva(tipo, 1, capturada_en=_t(2)))
    repo.guardar_captura(_captura_nueva(tipo, 2, capturada_en=T0, price="80.00"))
    otra = dataclasses.replace(_captura_nueva(tipo, 3, price="70.00"), id_producto=UUID(int=101))
    repo.guardar_captura(otra)
    assert [c.id.int for c in repo.capturas(tipo, instante=_t(1))] == [2, 3]
    assert [c.id.int for c in repo.capturas(tipo, instante=_t(2))] == [2, 3, 1]
    assert [c.id.int for c in repo.capturas(tipo, instante=_t(2), id_producto=ID_PRODUCTO)] == [
        2,
        1,
    ]
    assert repo.capturas(tipo, instante=T0 - dt.timedelta(seconds=1)) == ()


def test_una_captura_con_su_producto_nuevo_es_una_transaccion(repo):
    _con_carga(repo)
    nueva = dataclasses.replace(
        _captura_nueva(TipoRegistro.MSRP, 1),
        producto=_producto(),
        identificadores=(IdentificadorProducto("gtin", "0123456789012"),),
    )
    assert repo.guardar_captura(nueva)
    assert repo.leer_producto(ID_PRODUCTO) == _producto()
    # Otra captura con un producto que ya existe: falla y no queda la captura.
    otra = dataclasses.replace(_captura_nueva(TipoRegistro.LOCAL_ESTIMATE, 2), producto=_producto())
    with pytest.raises(ErrorDeIntegridad) as error:
        repo.guardar_captura(otra)
    assert error.value.restriccion == "pk_product"
    assert repo.capturas(TipoRegistro.LOCAL_ESTIMATE, instante=_t(1)) == ()


def test_el_alias_del_cliente_no_sale_en_repr_errores_ni_logs(repo, caplog):
    alias = "cliente-sintetico-7"
    caplog.set_level(logging.DEBUG)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.DEBUG)
    nueva = _captura_nueva(TipoRegistro.CLIENT_REQUEST, 1)
    assert alias not in repr(nueva)
    # Sin la carga (clave foránea): el error no cita el alias.
    with pytest.raises(ErrorDeIntegridad) as error:
        repo.guardar_captura(nueva)
    assert alias not in str(error.value) and alias not in repr(error.value)
    assert error.value.__context__ is None and error.value.__cause__ is None
    _con_carga(repo)
    repo.guardar_captura(nueva)
    (leida,) = repo.capturas(TipoRegistro.CLIENT_REQUEST, instante=T0)
    assert leida.captura.client_alias == alias
    assert alias not in repr(leida)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.NOTSET)
    # Los logs de SQLAlchemy no llevan parámetros (hide_parameters, RNF-8).
    assert alias not in caplog.text


# --- TAB-02 cargas y el registro de un rechazo (DEC-250) ------------------------------------------


def _rechazo_registro(
    renglon: int = 3, carga=ID_CARGA, motivo="CAMPO OBLIGATORIO FALTANTE (model)"
):
    rechazo = RechazoCarga(carga, renglon, motivo, TipoRegistro.OBSERVATION, "model")
    registro = RegistroRechazo(
        id=UUID(int=700 + renglon),
        evaluado_en=_t(1),
        id_version_configuracion=1,
        versiones_rn={"RN-001": 2, "RN-013": 1},
        motivo_rechazo=motivo,
        id_carga=carga,
        renglon=renglon,
    )
    return rechazo, registro


def test_la_carga_con_sus_rechazos_y_su_reporte(repo):
    carga = _con_carga(repo)
    guardada = repo.leer_carga(ID_CARGA)
    assert guardada.carga == carga and guardada.reporte is None and guardada.rechazos == ()
    repo.guardar_rechazo_carga(RechazoCarga(ID_CARGA, 5, "PRECIO INVÁLIDO", TipoRegistro.MSRP))
    repo.guardar_rechazo_carga(RechazoCarga(ID_CARGA, 2, "TIPO DE REGISTRO DESCONOCIDO"))
    reporte = ReporteCarga(
        _t(1), 7, 2, 1, {"PRECIO INVÁLIDO": 1, "TIPO DE REGISTRO DESCONOCIDO": 1}
    )
    repo.terminar_carga(ID_CARGA, reporte)
    guardada = repo.leer_carga(ID_CARGA)
    assert guardada.reporte == reporte
    assert [r.renglon for r in guardada.rechazos] == [2, 5]
    assert guardada.rechazos[1] == RechazoCarga(ID_CARGA, 5, "PRECIO INVÁLIDO", TipoRegistro.MSRP)
    with pytest.raises(ValueError, match="ya terminó"):
        repo.terminar_carga(ID_CARGA, reporte)
    assert repo.leer_carga(UUID(int=1)) is None
    with pytest.raises(ValueError, match="no existe"):
        repo.terminar_carga(UUID(int=1), reporte)


def test_el_mismo_renglon_dos_veces_choca(repo):
    _con_carga(repo)
    repo.guardar_rechazo_carga(RechazoCarga(ID_CARGA, 1, "PRECIO INVÁLIDO"))
    with pytest.raises(ErrorDeIntegridad) as error:
        repo.guardar_rechazo_carga(RechazoCarga(ID_CARGA, 1, "PRECIO INVÁLIDO"))
    assert error.value.restriccion == "pk_load_rejection"


def test_el_registro_de_un_rechazo_no_guarda_nada_del_renglon(repo):
    _con_carga(repo)
    rechazo, registro = _rechazo_registro()
    repo.guardar_rechazo_carga(rechazo, registro)
    assert repo.leer_evaluacion(registro.id) == registro
    fila = _fila_cruda(repo, tablas.evaluation, "id", registro.id)
    assert fila["result"] == "RECHAZADA_VALIDACION"
    assert fila["rejection_reason"] == "CAMPO OBLIGATORIO FALTANTE (model)"
    assert (fila["load_run_id"], fila["line_number"]) == (ID_CARGA, 3)
    for columna in (
        "input_snapshot",
        "offer_observation_id",
        "listing_id",
        "product_id",
        "references",
        "purchase_cost",
        "identification",
        "price_quality",
    ):
        assert fila[columna] is None, columna
    assert list(fila["reasons"]) == [] and list(fila["marks"]) == []
    # Rechazo y registro, una transacción: un registro de otro renglón no se acepta.
    otro_rechazo, _ = _rechazo_registro(4)
    with pytest.raises(ValueError, match="misma carga"):
        repo.guardar_rechazo_carga(otro_rechazo, registro)
    assert [r.renglon for r in repo.leer_carga(ID_CARGA).rechazos] == [3]


def test_el_registro_de_un_rechazo_se_liga_a_su_renglon(repo):
    _con_carga(repo)
    _, registro = _rechazo_registro(9)
    with pytest.raises(ErrorDeIntegridad) as error:
        repo.guardar_registro_rechazo(registro)  # el renglón 9 no está en load_rejection
    assert error.value.restriccion == "fk_evaluation_load_run_id_line_number_load_rejection"
    # Sin carga (no viene de un archivo): sin renglón.
    suelto = dataclasses.replace(registro, id=UUID(int=799), id_carga=None, renglon=None)
    repo.guardar_registro_rechazo(suelto)
    assert repo.leer_evaluacion(suelto.id) == suelto


def test_un_registro_rechazado_del_motor_no_se_guarda_con_su_contexto(repo):
    _con_config(repo)
    registro = _registro(
        resultado=Resultado.RECHAZADA_VALIDACION,
        motivo_rechazo="PRECIO INVÁLIDO",
        nivel_aviso=None,
        canal_aviso=None,
    )
    with pytest.raises(ValueError, match="DEC-250"):
        repo.guardar_evaluacion(registro)


# --- TAB-10 y TAB-11 evaluaciones ----------------------------------------------------------------


def _contexto(id_evaluacion: UUID, instante: dt.datetime, id_config: int) -> ContextoEvaluacion:
    return ContextoEvaluacion(
        id_evaluacion=id_evaluacion,
        instante=instante,
        configuracion=CONFIG,
        id_version_configuracion=id_config,
        oferta=ObservacionRegistrada(_observacion(), UUID(int=1), ID_PUBLICACION, ID_PRODUCTO),
        historial=(
            ObservacionRegistrada(
                _observacion(price={"current": "119.00"}), UUID(int=11), ID_PUBLICACION, ID_PRODUCTO
            ),
        ),
        id_carga=None,
    )


def _canal(**cambios) -> EvaluacionCanal:
    base = {
        "canal": Canal.LOCAL,
        "estado": EstadoCanal.DISPONIBLE,
        "precio_venta": Decimal("76.6175"),
        "costo_venta": Decimal("9.50"),
        "margen_neto": Decimal("30.12"),
        "margen_neto_pct": Decimal("75.63157894736842105263157895"),
        "unidades": 3,
        "dias_para_recuperar": 51,
        "rendimiento_mensual_pct": Decimal("44.1"),
        "nivel": Nivel.MUY_RECOMENDABLE,
        "nivel_calculado": Nivel.COMPRAR_YA,
        "ganancia_total": Decimal("100.58"),
        "marcas": ("SIN COMPARABLES LOCALES",),
    }
    base.update(cambios)
    return EvaluacionCanal(**base)


def _registro(
    n: int = 1, instante=T0, id_config: int = 1, id_publicacion=ID_PUBLICACION, **cambios
) -> RegistroEvaluacion:
    contexto = _contexto(UUID(int=500 + n), instante, id_config)
    base = {
        "id": contexto.id_evaluacion,
        "evaluado_en": instante,
        "id_observacion_oferta": UUID(int=1),
        "id_publicacion": id_publicacion,
        "id_producto": ID_PRODUCTO,
        "id_version_configuracion": id_config,
        "versiones_rn": contexto.versiones_rn,
        "resultado": Resultado.NIVEL_ASIGNADO,
        "motivo_principal": None,
        "motivos": (),
        "motivo_rechazo": None,
        "marcas": ("SIN OFERTA HOY", "ESTIMADO (peso)", "MARGEN ESTIMADO"),
        "calidad_precio": CalidadPrecio.OFERTA_EXCEPCIONAL,
        "confianza": Confianza.ALTA,
        "identificacion": Identificacion.CONFIRMED,
        "referencias": Referencias(
            precio_habitual=Decimal("119"),
            fuente_precio_habitual="historial_propio",
            episodio=Episodio(dt.date(2026, 11, 1), Decimal("120.5")),
            precio_mercado_hoy=Decimal("100.15"),
        ),
        "descuento_anunciado": Decimal("77.51937984496124031007751938"),
        "descuento_real": Decimal("75.21008403361344537815126050"),
        "costo_compra": Decimal("31.25"),
        "canal_elegido": Canal.LOCAL,
        "nivel_aviso": Nivel.MUY_RECOMENDABLE,
        "canal_aviso": Canal.LOCAL,
        "canales": (
            _canal(
                canal=Canal.AMAZON,
                estado=EstadoCanal.CERRADO,
                causas_cerrado=(
                    CausaCanalCerrado.SIN_ROTACION,
                    CausaCanalCerrado.PRODUCTO_NO_NUEVO,
                ),
                precio_venta=None,
                nivel=None,
                nivel_calculado=None,
                unidades=None,
                dias_para_recuperar=None,
            ),
            _canal(),
        ),
        "observaciones_usadas": (
            ObservacionUsada(UUID(int=11), dt.datetime(2026, 11, 1, 8, tzinfo=dt.UTC)),
        ),
        "entrada": contexto,
    }
    base.update(cambios)
    return RegistroEvaluacion(**base)


def _con_publicacion(repo) -> int:
    id_config = _con_config(repo)
    repo.guardar_observacion(_nueva(1, primera=True))
    return id_config


def test_la_evaluacion_vuelve_igual_con_su_contexto_y_sus_canales(repo):
    id_config = _con_publicacion(repo)
    registro = _registro(id_config=id_config)
    repo.guardar_evaluacion(registro)
    leido = repo.leer_evaluacion(registro.id)
    assert leido == registro
    # input_snapshot: el contexto completo, byte a byte (RNF-3).
    assert leido.entrada.a_json() == registro.entrada.a_json()
    # Decimal sin float ni redondeo (porcentajes y descuentos exactos, DEC-207).
    assert str(leido.descuento_real) == "75.21008403361344537815126050"
    assert str(leido.canales[1].margen_neto_pct) == "75.63157894736842105263157895"
    assert type(leido.canales[1].dias_para_recuperar) is int
    assert str(leido.canales[1].precio_venta) == "76.6175"
    assert leido.canales[0].causas_cerrado == (
        CausaCanalCerrado.SIN_ROTACION,
        CausaCanalCerrado.PRODUCTO_NO_NUEVO,
    )
    assert repo.leer_evaluacion(UUID(int=12345)) is None


def test_los_motivos_y_las_marcas_conservan_su_orden(repo):
    id_config = _con_publicacion(repo)
    motivos = (Motivo.COINCIDENCIA_NO_CONFIRMADA, Motivo.PARTICULAR, Motivo.DEMANDA_DESCONOCIDA)
    registro = _registro(
        id_config=id_config,
        resultado=Resultado.REVISION_MANUAL,
        motivo_principal=motivos[0],
        motivos=motivos,
        nivel_aviso=None,
        canal_aviso=None,
        marcas=("MARGEN ESTIMADO", "EMPAQUE POR CONFIRMAR", "CONFIANZA BAJA"),
        id_evaluacion_anterior=None,
        referencias_cambiadas=(),
    )
    repo.guardar_evaluacion(registro)
    leido = repo.leer_evaluacion(registro.id)
    assert leido.motivos == motivos and leido.motivo_principal is Motivo.COINCIDENCIA_NO_CONFIRMADA
    assert leido.marcas == ("MARGEN ESTIMADO", "EMPAQUE POR CONFIRMAR", "CONFIANZA BAJA")


def test_la_reevaluacion_guarda_la_anterior_y_las_referencias_cambiadas(repo):
    id_config = _con_publicacion(repo)
    anterior = _registro(1, id_config=id_config)
    repo.guardar_evaluacion(anterior)
    cambiadas = (ReferenciaPrecio.PRECIO_MERCADO_HOY, ReferenciaPrecio.PRECIO_HABITUAL)
    nueva = _registro(
        2,
        instante=_t(1),
        id_config=id_config,
        resultado=Resultado.SIN_NIVEL,
        nivel_aviso=None,
        canal_aviso=None,
        id_evaluacion_anterior=anterior.id,
        referencias_cambiadas=cambiadas,
        ya_no_recomendado=True,
    )
    repo.guardar_evaluacion(nueva)
    leida = repo.leer_evaluacion(nueva.id)
    assert leida == nueva and leida.referencias_cambiadas == cambiadas
    # La anterior debe existir (clave foránea).
    huerfana = _registro(3, id_config=id_config, id_evaluacion_anterior=UUID(int=4242))
    with pytest.raises(ErrorDeIntegridad) as error:
        repo.guardar_evaluacion(huerfana)
    assert error.value.restriccion == "fk_evaluation_previous_evaluation_id_evaluation"


def test_una_evaluacion_y_sus_canales_son_una_transaccion(repo):
    id_config = _con_publicacion(repo)
    # Un canal que no cabe en su columna: nada se escribe (ni la evaluación).
    malo = _registro(id_config=id_config, canales=(_canal(precio_venta=Decimal("76.61751")),))
    with pytest.raises(ValueError, match="no redondea"):
        repo.guardar_evaluacion(malo)
    assert repo.leer_evaluacion(malo.id) is None
    # Una versión de configuración que no existe: falla en la base y no queda nada.
    sin_config = _registro(2, id_config=id_config + 1000)
    with pytest.raises(ErrorDeIntegridad) as error:
        repo.guardar_evaluacion(sin_config)
    assert error.value.restriccion == "fk_evaluation_config_version_id_config_version"
    assert repo.leer_evaluacion(sin_config.id) is None
    assert _cuenta(repo, tablas.evaluation_channel) == 0
    # El mismo id dos veces.
    bueno = _registro(3, id_config=id_config)
    repo.guardar_evaluacion(bueno)
    with pytest.raises(ErrorDeIntegridad) as error:
        repo.guardar_evaluacion(bueno)
    assert error.value.restriccion == "pk_evaluation"
    assert _cuenta(repo, tablas.evaluation_channel) == 2


def test_las_oportunidades_abiertas_a_un_instante(repo):
    id_config = _con_publicacion(repo)
    otra_pub = _publicacion(UUID(int=202), "https://tienda.example.com/p/456", "tp-01")
    repo.guardar_observacion(_nueva(9, publicacion=otra_pub, id_publicacion=otra_pub.id))
    sin_nivel = {"resultado": Resultado.SIN_NIVEL, "nivel_aviso": None, "canal_aviso": None}
    a1 = _registro(1, instante=T0, id_config=id_config)
    a2 = _registro(2, instante=_t(2), id_config=id_config, **sin_nivel)
    b1 = _registro(3, instante=_t(3), id_config=id_config, id_publicacion=otra_pub.id)
    for registro in (b1, a2, a1):
        repo.guardar_evaluacion(registro)
    assert repo.oportunidades_abiertas(instante=T0 - dt.timedelta(seconds=1)) == ()
    assert repo.oportunidades_abiertas(instante=_t(1)) == (a1,)
    assert repo.oportunidades_abiertas(instante=_t(2)) == ()  # la más reciente ya no tiene nivel
    assert repo.oportunidades_abiertas(instante=_t(3)) == (b1,)
    assert repo.oportunidades_abiertas(instante=_t(3), id_producto=UUID(int=7)) == ()
    # Mismo instante: desempata el id mayor (como la vista TAB-12).
    a3 = _registro(4, instante=_t(2), id_config=id_config)
    repo.guardar_evaluacion(a3)
    assert a3.id > a2.id
    assert repo.oportunidades_abiertas(instante=_t(2)) == (a3,)


# --- Validaciones antes de escribir (las mismas en las dos implementaciones) ---------------------


def test_un_obligatorio_faltante_o_un_texto_vacio_se_rechazan_antes_de_escribir(repo):
    id_config = _con_publicacion(repo)
    with pytest.raises(ValueError, match="obligatorio"):
        repo.guardar_evaluacion(_registro(id_config=id_config, id_version_configuracion=None))
    assert _cuenta(repo, tablas.evaluation) == 0
    with pytest.raises(ValueError, match="vacío"):
        Producto(UUID(int=1), T0, marca=" ")


def test_una_observacion_sin_su_disponibilidad_da_un_error_del_repositorio(repo):
    # Datos inconsistentes (TAB-05 sin TAB-06): un error propio, no un assert (que
    # desaparece con ``python -O``), y sin ids ni valores de la fila en el mensaje.
    repo.guardar_observacion(_nueva(1, primera=True))
    if isinstance(repo, RepositorioMemoria):
        tabla = repo._tablas[tablas.availability_observation.name]
        tabla.filas.clear()
        for indice in tabla.indices.values():
            indice.clear()
    else:
        with repo._motor_de_pruebas.begin() as c:
            c.execute(tablas.availability_observation.delete())
    with pytest.raises(ErrorRepositorio, match="disponibilidad") as error:
        repo.leer_observacion(UUID(int=1))
    assert str(UUID(int=1)) not in str(error.value)
    assert error.value.__context__ is None and error.value.__cause__ is None
    with pytest.raises(ErrorRepositorio):
        repo.observaciones_del_producto(ID_PRODUCTO, instante=_t(1))


# --- Los CHECK del esquema en memoria (_checks) -----------------------------------------


def test_la_memoria_evalua_todos_los_check_del_esquema_desde_su_texto():
    from sqlalchemy import CheckConstraint

    from oip.persistencia.repositorios import _checks

    for nombre, tabla in tablas.metadata.tables.items():
        esperados = {str(r.name) for r in tabla.constraints if isinstance(r, CheckConstraint)}
        assert {n for n, _ in _checks.CHECKS[nombre]} == esperados, nombre


@pytest.mark.parametrize(
    ("tabla", "fila", "violado"),
    [
        # NULL no viola un CHECK (lógica de tres valores, como PostgreSQL).
        ("local_comparable", {"asking_price": None, "currency": None}, None),
        ("local_comparable", {"asking_price": Decimal("0.00")}, "asking_price_positivo"),
        ("local_comparable", {"currency": "MXN", "exchange_rate": None}, "mxn_con_tipo_de_cambio"),
        ("client_request", {"items": ["a", "b", "c", "d"]}, "items_de_1_a_3"),
        (
            "client_request",
            {"accepted_conditions": ["new", "nuevo"]},
            "accepted_conditions_catalogo",
        ),
        ("load_rejection", {"reason": "CAMPO OBLIGATORIO FALTANTE (model)"}, None),
        ("load_rejection", {"reason": "CAMPO OBLIGATORIO FALTANTE (a b)"}, "reason_catalogo"),
        ("load_rejection", {"field": "a b"}, "field_nombre"),
        ("evaluation", {"main_reason": None, "reasons": []}, None),
        ("evaluation", {"main_reason": "EVITAR", "reasons": []}, "motivo_principal"),
        ("evaluation", {"main_reason": "EVITAR", "reasons": ["EVITAR", "PARTICULAR"]}, None),
        ("config_version", {"content": '["no", "objeto"]'}, "content_objeto"),
    ],
)
def test_los_check_en_memoria_siguen_la_semantica_de_sql(tabla, fila, violado):
    from oip.persistencia.repositorios import _checks

    completa = {c.name: None for c in tablas.metadata.tables[tabla].columns} | fila
    esperado = None if violado is None else f"ck_{tabla}_{violado}"
    assert _checks.violado(tabla, completa) == esperado
