"""``RepositorioPostgres`` (CMP-20); la conexión por ``podman secret`` está en ``conexion``.

SQLAlchemy 2 Core con psycopg 3 (design.md §5), sobre el esquema de las migraciones
(``alembic upgrade head``). Las filas son las de ``_filas``, las mismas que guarda
``RepositorioMemoria``. Cada método que escribe es **una** transacción
(``Engine.begin``): si algo falla, no queda nada de esa llamada.

**Conexión** (design.md §5, RNF-8): la URL **sin contraseña** sale de ``OIP_DATABASE_URL``;
la contraseña, del archivo del ``podman secret`` montado (``/run/secrets/oip_db_password``)
si existe. La URL nunca va a un log, a un ``repr`` ni a un mensaje de error: los errores de
la base se traducen a ``ErrorRepositorio`` con solo la causa (nombre de la restricción o
clase del error), sin el SQL, los parámetros ni la URL, y sin encadenar la excepción
original. El motor se crea con ``hide_parameters=True``.

Los ``jsonb`` se escriben como texto JSON canónico con ``CAST(... AS jsonb)`` y se leen con
``CAST(... AS text)``: ningún número pasa por ``float`` (design.md §8).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, TypeVar
from uuid import UUID

from sqlalchemy import (
    Engine,
    Table,
    Text,
    and_,
    cast,
    func,
    literal,
    null,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection
from sqlalchemy.exc import (
    SQLAlchemyError,
)

from oip.catalogos import Resultado, TipoRegistro
from oip.configuracion import ConfiguracionVersionada
from oip.evaluacion.contexto import ObservacionRegistrada, RegistroEvaluacion
from oip.persistencia import tablas
from oip.persistencia.repositorios import _filas
from oip.persistencia.repositorios._filas import Fila
from oip.persistencia.repositorios._tipos import (
    CapturaGuardada,
    CapturaNueva,
    Carga,
    CargaGuardada,
    ErrorRepositorio,
    IdentificadorProducto,
    ObservacionNueva,
    Producto,
    Publicacion,
    RechazoCarga,
    RegistroRechazo,
    ReporteCarga,
    VersionConfiguracion,
)
from oip.persistencia.repositorios.conexion import (
    ARCHIVO_SECRETO,
    VARIABLE_URL,
    crear_motor,
    traducir_error,
    url_de_conexion,
)

__all__ = [
    "ARCHIVO_SECRETO",
    "VARIABLE_URL",
    "RepositorioPostgres",
    "crear_motor",
    "url_de_conexion",
]

T = TypeVar("T")

# --- Consultas ----------------------------------------------------------------------------


def _bind(tabla: Table, nombre: str, valor: Any) -> Any:
    if isinstance(tabla.c[nombre].type, JSONB):
        return null() if valor is None else cast(literal(valor, Text), JSONB)
    return valor


def _valores(tabla: Table, fila: Fila) -> dict[str, Any]:
    return {
        n: _bind(tabla, n, v)
        for n, v in fila.items()
        if not (v is None and tabla.c[n].autoincrement is True)
    }


def _insertar(c: Connection, tabla: Table, fila: Fila) -> None:
    c.execute(tabla.insert().values(**_valores(tabla, fila)))


def _columnas(tabla: Table, prefijo: str = "") -> list[Any]:
    """Las columnas de ``tabla`` (los ``jsonb`` como texto), con ``prefijo`` en su nombre."""
    return [
        (cast(c, Text) if isinstance(c.type, JSONB) else c).label(prefijo + c.name)
        for c in tabla.columns
    ]


def _parte(fila: Mapping[str, Any], tabla: Table, prefijo: str) -> Fila:
    return {c.name: fila[prefijo + c.name] for c in tabla.columns}


def _leer(
    c: Connection, tabla: Table, *condiciones: Any, orden: tuple[Any, ...] = ()
) -> list[Fila]:
    consulta = select(*_columnas(tabla)).where(*condiciones).order_by(*orden)
    return [dict(r._mapping) for r in c.execute(consulta)]


def _una(c: Connection, tabla: Table, *condiciones: Any) -> Fila | None:
    filas = _leer(c, tabla, *condiciones)
    return filas[0] if filas else None


_P, _D, _L, _F = (
    tablas.price_observation,
    tablas.availability_observation,
    tablas.listing,
    (tablas.amazon_listing_observation),
)


class RepositorioPostgres:
    """Implementación de ``Repositorio`` sobre PostgreSQL + TimescaleDB (design.md §5)."""

    def __init__(self, motor: Engine) -> None:
        if not isinstance(motor, Engine):
            raise TypeError("motor: se esperaba un sqlalchemy.Engine")
        self._motor = motor

    @classmethod
    def desde_entorno(
        cls,
        entorno: Mapping[str, str] | None = None,
        archivo_secreto: Path | None = ARCHIVO_SECRETO,
    ) -> RepositorioPostgres:
        """Con la URL de ``OIP_DATABASE_URL`` y la contraseña del ``podman secret``."""
        return cls(crear_motor(url_de_conexion(entorno, archivo_secreto)))

    def __repr__(self) -> str:
        return "RepositorioPostgres()"  # sin la URL (RNF-8)

    def cerrar(self) -> None:
        """Cierra las conexiones del motor."""
        self._motor.dispose()

    def _correr(self, funcion: Callable[[Connection], T]) -> T:
        """Corre ``funcion`` en una transacción; traduce el error **fuera** del ``except``
        para que no quede encadenado (ni en ``__context__``) el error original."""
        traducido: ErrorRepositorio | None = None
        try:
            with self._motor.begin() as conexion:
                return funcion(conexion)
        except SQLAlchemyError as error:
            traducido = traducir_error(error)
        raise traducido

    # --- TAB-01 ---------------------------------------------------------------------------

    def guardar_version_configuracion(
        self, configuracion: ConfiguracionVersionada, *, cargada_en: dt.datetime
    ) -> tuple[VersionConfiguracion, bool]:
        fila = _filas.fila_configuracion(configuracion, cargada_en, None)
        t = tablas.config_version

        def tx(c: Connection) -> tuple[VersionConfiguracion, bool]:
            existente = _una(c, t, t.c.sha256 == fila["sha256"])
            if existente is not None:
                return _filas.configuracion_de_fila(existente), False
            id_ = c.execute(t.insert().values(**_valores(t, fila)).returning(t.c.id)).scalar_one()
            return _filas.configuracion_de_fila({**fila, "id": id_}), True

        return self._correr(tx)

    def version_configuracion(self, id_: int) -> VersionConfiguracion | None:
        t = tablas.config_version
        fila = self._correr(lambda c: _una(c, t, t.c.id == id_))
        return None if fila is None else _filas.configuracion_de_fila(fila)

    def version_configuracion_activa(self, instante: dt.datetime) -> VersionConfiguracion | None:
        t = tablas.config_version
        limite = _filas.instante_utc(instante)

        def tx(c: Connection) -> Fila | None:
            filas = _leer(
                c, t, t.c.loaded_at <= limite, orden=(t.c.loaded_at.desc(), t.c.id.desc())
            )
            return filas[0] if filas else None

        fila = self._correr(tx)
        return None if fila is None else _filas.configuracion_de_fila(fila)

    # --- TAB-03 y TAB-04 ------------------------------------------------------------------

    def guardar_producto(
        self, producto: Producto, identificadores: tuple[IdentificadorProducto, ...] = ()
    ) -> None:
        filas = [(tablas.product, _filas.fila_producto(producto))]
        filas += [
            (tablas.product_identifier, _filas.fila_identificador(i, producto.id))
            for i in identificadores
        ]
        self._correr(lambda c: [_insertar(c, t, f) for t, f in filas])

    def leer_producto(self, id_: UUID) -> Producto | None:
        t = tablas.product
        fila = self._correr(lambda c: _una(c, t, t.c.id == id_))
        return None if fila is None else _filas.producto_de_fila(fila)

    def buscar_producto(self, identificador: IdentificadorProducto) -> UUID | None:
        t = tablas.product_identifier
        fila = self._correr(
            lambda c: _una(c, t, t.c.kind == identificador.clase, t.c.value == identificador.valor)
        )
        return None if fila is None else fila["product_id"]

    def buscar_publicacion(
        self, comercio: str, url_canonica: str, tienda: str | None
    ) -> Publicacion | None:
        t = tablas.listing
        condicion_tienda = t.c.store_code.is_(None) if tienda is None else t.c.store_code == tienda
        fila = self._correr(
            lambda c: _una(
                c,
                t,
                t.c.retailer_code == comercio,
                t.c.canonical_url == url_canonica,
                condicion_tienda,
            )
        )
        return None if fila is None else _filas.publicacion_de_fila(fila)

    # --- TAB-05 a TAB-08 ------------------------------------------------------------------

    def guardar_observacion(self, nueva: ObservacionNueva) -> bool:
        filas = _filas.filas_observacion(nueva)
        recibo_tabla, recibo = filas[0]

        def tx(c: Connection) -> bool:
            insertado = c.execute(
                pg_insert(recibo_tabla)
                .values(**_valores(recibo_tabla, recibo))
                .on_conflict_do_nothing(index_elements=["idempotency_key"])
                .returning(recibo_tabla.c.idempotency_key)
            ).first()
            if insertado is None:
                return False  # duplicado: no se escribe nada más
            for tabla, fila in filas[1:]:
                _insertar(c, tabla, fila)
            return True

        return self._correr(tx)

    def observacion_por_clave(self, clave_idempotencia: str) -> UUID | None:
        t = tablas.ingest_receipt
        fila = self._correr(lambda c: _una(c, t, t.c.idempotency_key == clave_idempotencia))
        return None if fila is None else fila["observation_id"]

    def _leer_observaciones(self, *condiciones: Any) -> tuple[ObservacionRegistrada, ...]:
        consulta = (
            select(
                *_columnas(_P, "p__"),
                *_columnas(_D, "d__"),
                *_columnas(_L, "l__"),
                *_columnas(_F, "f__"),
            )
            .select_from(
                _P.outerjoin(
                    _D,
                    and_(
                        _D.c.observation_id == _P.c.observation_id,
                        _D.c.observed_at == _P.c.observed_at,
                    ),
                )
                .outerjoin(_L, _L.c.id == _P.c.listing_id)
                .outerjoin(
                    _F,
                    and_(
                        _F.c.observation_id == _P.c.observation_id,
                        _F.c.observed_at == _P.c.observed_at,
                    ),
                )
            )
            .where(*condiciones)
            .order_by(_P.c.observed_at, _P.c.observation_id)
        )

        def tx(c: Connection) -> list[Fila]:
            return [dict(r._mapping) for r in c.execute(consulta)]

        return tuple(_registrada(f) for f in self._correr(tx))

    def leer_observacion(self, id_: UUID) -> ObservacionRegistrada | None:
        leidas = self._leer_observaciones(_P.c.observation_id == id_)
        return leidas[0] if leidas else None

    def observaciones_del_producto(
        self, id_producto: UUID, *, instante: dt.datetime, desde: dt.datetime | None = None
    ) -> tuple[ObservacionRegistrada, ...]:
        condiciones = [
            _P.c.product_id == id_producto,
            _P.c.observed_at <= _filas.instante_utc(instante),
        ]
        if desde is not None:
            condiciones.append(_P.c.observed_at >= _filas.instante_utc(desde, "desde"))
        return self._leer_observaciones(*condiciones)

    # --- TAB-09 ---------------------------------------------------------------------------

    def guardar_captura(self, nueva: CapturaNueva) -> bool:
        tabla, fila = _filas.fila_captura(nueva)
        filas: list[tuple[Table, Fila]] = []
        if nueva.producto is not None:
            filas.append((tablas.product, _filas.fila_producto(nueva.producto)))
        filas += [
            (tablas.product_identifier, _filas.fila_identificador(i, nueva.id_producto))
            for i in nueva.identificadores
        ]
        filas.append((tabla, fila))

        def tx(c: Connection) -> bool:
            if _una(c, tabla, tabla.c.idempotency_key == fila["idempotency_key"]) is not None:
                return False  # duplicado: no se escribe nada
            for t, f in filas:
                _insertar(c, t, f)
            return True

        return self._correr(tx)

    def capturas(
        self, tipo: TipoRegistro, *, instante: dt.datetime, id_producto: UUID | None = None
    ) -> tuple[CapturaGuardada, ...]:
        tipo = TipoRegistro(tipo)
        tabla = _filas.TABLA_CAPTURA[tipo]
        condiciones = [tabla.c.captured_at <= _filas.instante_utc(instante)]
        if id_producto is not None:
            if "product_id" not in tabla.c:
                return ()
            condiciones.append(tabla.c.product_id == id_producto)
        filas = self._correr(
            lambda c: _leer(c, tabla, *condiciones, orden=(tabla.c.captured_at, tabla.c.id))
        )
        return tuple(_filas.captura_de_fila(tipo, f) for f in filas)

    # --- TAB-02 ---------------------------------------------------------------------------

    def iniciar_carga(self, carga: Carga) -> None:
        fila = _filas.fila_carga(carga)
        self._correr(lambda c: _insertar(c, tablas.load_run, fila))

    def guardar_rechazo_carga(
        self, rechazo: RechazoCarga, registro: RegistroRechazo | None = None
    ) -> None:
        filas = [(tablas.load_rejection, _filas.fila_rechazo_carga(rechazo))]
        if registro is not None:
            _filas.mismo_renglon(rechazo, registro)
            filas.append((tablas.evaluation, _filas.fila_registro_rechazo(registro)))
        self._correr(lambda c: [_insertar(c, t, f) for t, f in filas])

    def terminar_carga(self, id_carga: UUID, reporte: ReporteCarga) -> None:
        t = tablas.load_run

        def tx(c: Connection) -> None:
            filas = _filas_para_actualizar(c, t, t.c.id == id_carga)
            if not filas:
                raise ValueError("terminar_carga: la carga no existe")
            cambios = _filas.cambios_reporte(filas[0], reporte)
            c.execute(
                t.update()
                .where(t.c.id == id_carga)
                .values(**{n: _bind(t, n, v) for n, v in cambios.items()})
            )

        self._correr(tx)

    def leer_carga(self, id_carga: UUID) -> CargaGuardada | None:
        t, r = tablas.load_run, tablas.load_rejection

        def tx(c: Connection) -> tuple[Fila | None, list[Fila]]:
            return _una(c, t, t.c.id == id_carga), _leer(c, r, r.c.load_run_id == id_carga)

        fila, rechazos = self._correr(tx)
        return None if fila is None else CargaGuardada(*_filas.carga_de_filas(fila, rechazos))

    # --- TAB-10 y TAB-11 ------------------------------------------------------------------

    def guardar_evaluacion(self, registro: RegistroEvaluacion) -> None:
        filas = _filas.filas_evaluacion(registro)
        self._correr(lambda c: [_insertar(c, t, f) for t, f in filas])

    def guardar_registro_rechazo(self, registro: RegistroRechazo) -> None:
        fila = _filas.fila_registro_rechazo(registro)
        self._correr(lambda c: _insertar(c, tablas.evaluation, fila))

    @staticmethod
    def _evaluaciones(c: Connection, ids: list[UUID]) -> list[RegistroEvaluacion | RegistroRechazo]:
        if not ids:
            return []
        e, k = tablas.evaluation, tablas.evaluation_channel
        filas = {f["id"]: f for f in _leer(c, e, e.c.id.in_(ids))}
        canales: dict[UUID, list[Fila]] = {}
        for canal in _leer(c, k, k.c.evaluation_id.in_(ids)):
            canales.setdefault(canal["evaluation_id"], []).append(canal)
        return [_filas.evaluacion_de_filas(filas[i], canales.get(i, [])) for i in ids]

    def leer_evaluacion(self, id_: UUID) -> RegistroEvaluacion | RegistroRechazo | None:
        e = tablas.evaluation

        def tx(c: Connection) -> list[RegistroEvaluacion | RegistroRechazo]:
            existe = c.execute(select(e.c.id).where(e.c.id == id_)).first()
            return [] if existe is None else self._evaluaciones(c, [id_])

        leidas = self._correr(tx)
        return leidas[0] if leidas else None

    def oportunidades_abiertas(
        self, *, instante: dt.datetime, id_producto: UUID | None = None
    ) -> tuple[RegistroEvaluacion, ...]:
        e = tablas.evaluation
        # Lo mismo que la vista TAB-12 (DISTINCT ON), pero hasta el instante.
        orden = func.row_number().over(
            partition_by=e.c.listing_id, order_by=(e.c.evaluated_at.desc(), e.c.id.desc())
        )
        ultima = (
            select(e.c.id, e.c.listing_id, e.c.product_id, e.c.result, orden.label("n"))
            .where(e.c.listing_id.is_not(None), e.c.evaluated_at <= _filas.instante_utc(instante))
            .subquery()
        )
        consulta = select(ultima.c.id).where(
            ultima.c.n == 1, ultima.c.result == Resultado.NIVEL_ASIGNADO.value
        )
        if id_producto is not None:
            consulta = consulta.where(ultima.c.product_id == id_producto)
        consulta = consulta.order_by(ultima.c.listing_id)

        def tx(c: Connection) -> list[RegistroEvaluacion | RegistroRechazo]:
            return self._evaluaciones(c, list(c.execute(consulta).scalars()))

        return tuple(self._correr(tx))  # type: ignore[arg-type]


def _registrada(f: Mapping[str, Any]) -> ObservacionRegistrada:
    # Igual que la memoria: una fila de TAB-05 sin su TAB-06 o su TAB-04 es inconsistente.
    if f["d__observation_id"] is None or f["l__id"] is None:
        raise ErrorRepositorio(_filas.OBSERVACION_INCOMPLETA)
    return _filas.observacion_de_filas(
        _parte(f, _P, "p__"),
        _parte(f, _D, "d__"),
        _parte(f, _L, "l__"),
        None if f["f__observation_id"] is None else _parte(f, _F, "f__"),
    )


def _filas_para_actualizar(c: Connection, tabla: Table, *condiciones: Any) -> list[Fila]:
    consulta = select(*_columnas(tabla)).where(*condiciones).with_for_update()
    return [dict(r._mapping) for r in c.execute(consulta)]
