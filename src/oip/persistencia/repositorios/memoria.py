"""``RepositorioMemoria`` (CMP-20): el repositorio en memoria para pruebas y desarrollo.

Guarda las **mismas filas** que ``RepositorioPostgres`` (``_filas``), con las claves
primarias, los únicos (también el de ``listing`` con ``coalesce(store_code, '')``) y las
claves foráneas de los metadatos de ``oip.persistencia.tablas``: una violación levanta
``ErrorDeIntegridad`` con el nombre de la misma restricción que daría PostgreSQL. Cada
método que escribe es una transacción: valida todas sus filas y solo entonces las agrega.

No es seguro entre hilos ni persiste nada. Sin reloj, sin red, sin I/O.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterable, Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import Index, PrimaryKeyConstraint, Table, UniqueConstraint

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
    ErrorDeIntegridad,
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

__all__ = ["RepositorioMemoria"]

Clave = Callable[[Mapping[str, Any]], tuple[Any, ...] | None]


def _clave(columnas: Iterable[str]) -> Clave:
    nombres = tuple(columnas)

    def clave(fila: Mapping[str, Any]) -> tuple[Any, ...] | None:
        valores = tuple(fila[n] for n in nombres)
        return None if None in valores else valores  # NULL no choca en un único

    return clave


def _unicos(tabla: Table) -> list[tuple[str, Clave]]:
    """Clave primaria, únicos e índices únicos de ``tabla``, con su nombre."""
    unicos: list[tuple[str, Clave]] = []
    for restriccion in tabla.constraints:
        if isinstance(restriccion, PrimaryKeyConstraint | UniqueConstraint):
            unicos.append((str(restriccion.name), _clave(c.name for c in restriccion.columns)))
    for indice in tabla.indexes:
        if not isinstance(indice, Index) or not indice.unique:
            continue
        if indice.name != "uq_listing_retailer_url_store":  # pragma: no cover
            raise NotImplementedError(f"índice único sin equivalente en memoria: {indice.name}")

        def clave_listing(fila: Mapping[str, Any]) -> tuple[Any, ...]:
            return (fila["retailer_code"], fila["canonical_url"], fila["store_code"] or "")

        unicos.append((indice.name, clave_listing))
    return unicos


class _Tabla:
    """Filas de una tabla con un índice por cada clave única."""

    def __init__(self, tabla: Table) -> None:
        self.tabla = tabla
        self.filas: list[Fila] = []
        self.unicos = _unicos(tabla)
        self.indices: dict[str, dict[tuple[Any, ...], Fila]] = {n: {} for n, _ in self.unicos}
        self.pk = tuple(c.name for c in tabla.primary_key.columns)
        self.foraneas = [
            (
                str(fk.name),
                [c.name for c in fk.columns],
                fk.referred_table.name,
                [e.column.name for e in fk.elements],
            )
            for fk in tabla.foreign_key_constraints
        ]

    def por_pk(self, *valores: Any) -> Fila | None:
        return self.indices[str(self.tabla.primary_key.name)].get(tuple(valores))


class _Transaccion:
    """Filas pendientes de una transacción: se validan contra lo guardado y lo pendiente, y
    se agregan todas juntas en ``confirmar``."""

    def __init__(self, repo: RepositorioMemoria) -> None:
        self._repo = repo
        self._pendientes: list[tuple[_Tabla, Fila]] = []
        self._indices: dict[tuple[str, str], dict[tuple[Any, ...], Fila]] = {}

    def _existe(self, tabla: _Tabla, nombre: str, clave: tuple[Any, ...]) -> Fila | None:
        return tabla.indices[nombre].get(clave) or self._indices.get(
            (tabla.tabla.name, nombre), {}
        ).get(clave)

    def insertar(self, tabla_sa: Table, fila: Fila) -> None:
        tabla = self._repo._tablas[tabla_sa.name]
        for nombre, clave in tabla.unicos:
            valor = clave(fila)
            if valor is not None and self._existe(tabla, nombre, valor) is not None:
                raise ErrorDeIntegridad(nombre)
        for nombre, locales, referida, remotas in tabla.foraneas:
            valores = [fila[c] for c in locales]
            if None in valores:
                continue  # MATCH SIMPLE: con un nulo no se comprueba
            destino = self._repo._tablas[referida]
            por_columna = dict(zip(remotas, valores, strict=True))
            clave_pk = tuple(por_columna[c] for c in destino.pk)
            pk = str(destino.tabla.primary_key.name)
            if self._existe(destino, pk, clave_pk) is None:
                raise ErrorDeIntegridad(nombre)
        for nombre, clave in tabla.unicos:
            valor = clave(fila)
            if valor is not None:
                self._indices.setdefault((tabla.tabla.name, nombre), {})[valor] = fila
        self._pendientes.append((tabla, fila))

    def confirmar(self) -> None:
        for tabla, fila in self._pendientes:
            tabla.filas.append(fila)
            for nombre, clave in tabla.unicos:
                valor = clave(fila)
                if valor is not None:
                    tabla.indices[nombre][valor] = fila


class RepositorioMemoria:
    """Implementación en memoria de ``Repositorio`` (design.md §5)."""

    def __init__(self) -> None:
        self._tablas = {nombre: _Tabla(t) for nombre, t in tablas.metadata.tables.items()}
        self._siguiente_config = 1

    def __repr__(self) -> str:
        return "RepositorioMemoria()"

    def _t(self, tabla: Table) -> _Tabla:
        return self._tablas[tabla.name]

    def _escribir(self, filas: Iterable[tuple[Table, Fila]]) -> None:
        transaccion = _Transaccion(self)
        for tabla, fila in filas:
            transaccion.insertar(tabla, fila)
        transaccion.confirmar()

    # --- TAB-01 ---------------------------------------------------------------------------

    def guardar_version_configuracion(
        self, configuracion: ConfiguracionVersionada, *, cargada_en: dt.datetime
    ) -> tuple[VersionConfiguracion, bool]:
        fila = _filas.fila_configuracion(configuracion, cargada_en, self._siguiente_config)
        existente = (
            self._t(tablas.config_version)
            .indices["uq_config_version_sha256"]
            .get((fila["sha256"],))
        )
        if existente is not None:
            return _filas.configuracion_de_fila(existente), False
        self._escribir([(tablas.config_version, fila)])
        self._siguiente_config += 1
        return _filas.configuracion_de_fila(fila), True

    def version_configuracion(self, id_: int) -> VersionConfiguracion | None:
        fila = self._t(tablas.config_version).por_pk(id_)
        return None if fila is None else _filas.configuracion_de_fila(fila)

    def version_configuracion_activa(self, instante: dt.datetime) -> VersionConfiguracion | None:
        limite = _filas.instante_utc(instante)
        candidatas = [f for f in self._t(tablas.config_version).filas if f["loaded_at"] <= limite]
        if not candidatas:
            return None
        fila = max(candidatas, key=lambda f: (f["loaded_at"], f["id"]))
        return _filas.configuracion_de_fila(fila)

    # --- TAB-03 y TAB-04 ------------------------------------------------------------------

    def guardar_producto(
        self, producto: Producto, identificadores: tuple[IdentificadorProducto, ...] = ()
    ) -> None:
        filas = [(tablas.product, _filas.fila_producto(producto))]
        filas += [
            (tablas.product_identifier, _filas.fila_identificador(i, producto.id))
            for i in identificadores
        ]
        self._escribir(filas)

    def leer_producto(self, id_: UUID) -> Producto | None:
        fila = self._t(tablas.product).por_pk(id_)
        return None if fila is None else _filas.producto_de_fila(fila)

    def buscar_producto(self, identificador: IdentificadorProducto) -> UUID | None:
        fila = self._t(tablas.product_identifier).por_pk(identificador.clase, identificador.valor)
        return None if fila is None else fila["product_id"]

    def buscar_publicacion(
        self, comercio: str, url_canonica: str, tienda: str | None
    ) -> Publicacion | None:
        indice = self._t(tablas.listing).indices["uq_listing_retailer_url_store"]
        fila = indice.get((comercio, url_canonica, tienda or ""))
        return None if fila is None else _filas.publicacion_de_fila(fila)

    # --- TAB-05 a TAB-08 ------------------------------------------------------------------

    def guardar_observacion(self, nueva: ObservacionNueva) -> bool:
        filas = _filas.filas_observacion(nueva)
        if self.observacion_por_clave(nueva.clave_idempotencia) is not None:
            return False
        self._escribir(filas)
        return True

    def observacion_por_clave(self, clave_idempotencia: str) -> UUID | None:
        fila = self._t(tablas.ingest_receipt).por_pk(clave_idempotencia)
        return None if fila is None else fila["observation_id"]

    def _registrada(self, precio: Fila) -> ObservacionRegistrada:
        clave = (precio["observation_id"], precio["observed_at"])
        disponibilidad = self._t(tablas.availability_observation).por_pk(*clave)
        ficha = self._t(tablas.amazon_listing_observation).por_pk(*clave)
        publicacion = self._t(tablas.listing).por_pk(precio["listing_id"])
        if disponibilidad is None or publicacion is None:
            raise ErrorRepositorio(_filas.OBSERVACION_INCOMPLETA)
        return _filas.observacion_de_filas(precio, disponibilidad, publicacion, ficha)

    def leer_observacion(self, id_: UUID) -> ObservacionRegistrada | None:
        filas = [f for f in self._t(tablas.price_observation).filas if f["observation_id"] == id_]
        if not filas:
            return None
        return self._registrada(min(filas, key=lambda f: f["observed_at"]))

    def observaciones_del_producto(
        self, id_producto: UUID, *, instante: dt.datetime, desde: dt.datetime | None = None
    ) -> tuple[ObservacionRegistrada, ...]:
        limite = _filas.instante_utc(instante)
        inicio = None if desde is None else _filas.instante_utc(desde, "desde")
        filas = [
            f
            for f in self._t(tablas.price_observation).filas
            if f["product_id"] == id_producto
            and f["observed_at"] <= limite
            and (inicio is None or f["observed_at"] >= inicio)
        ]
        filas.sort(key=lambda f: (f["observed_at"], f["observation_id"]))
        return tuple(self._registrada(f) for f in filas)

    # --- TAB-09 ---------------------------------------------------------------------------

    def guardar_captura(self, nueva: CapturaNueva) -> bool:
        tabla, fila = _filas.fila_captura(nueva)
        indice = self._t(tabla).indices[f"uq_{tabla.name}_idempotency_key"]
        if (fila["idempotency_key"],) in indice:
            return False
        filas: list[tuple[Table, Fila]] = []
        if nueva.producto is not None:
            filas.append((tablas.product, _filas.fila_producto(nueva.producto)))
        filas += [
            (tablas.product_identifier, _filas.fila_identificador(i, nueva.id_producto))
            for i in nueva.identificadores
        ]
        filas.append((tabla, fila))
        self._escribir(filas)
        return True

    def capturas(
        self, tipo: TipoRegistro, *, instante: dt.datetime, id_producto: UUID | None = None
    ) -> tuple[CapturaGuardada, ...]:
        tabla = _filas.TABLA_CAPTURA[TipoRegistro(tipo)]
        limite = _filas.instante_utc(instante)
        filas = [
            f
            for f in self._t(tabla).filas
            if f["captured_at"] <= limite
            and (id_producto is None or f.get("product_id") == id_producto)
        ]
        filas.sort(key=lambda f: (f["captured_at"], f["id"]))
        return tuple(_filas.captura_de_fila(TipoRegistro(tipo), f) for f in filas)

    # --- TAB-02 ---------------------------------------------------------------------------

    def iniciar_carga(self, carga: Carga) -> None:
        self._escribir([(tablas.load_run, _filas.fila_carga(carga))])

    def guardar_rechazo_carga(
        self, rechazo: RechazoCarga, registro: RegistroRechazo | None = None
    ) -> None:
        filas = [(tablas.load_rejection, _filas.fila_rechazo_carga(rechazo))]
        if registro is not None:
            _filas.mismo_renglon(rechazo, registro)
            filas.append((tablas.evaluation, _filas.fila_registro_rechazo(registro)))
        self._escribir(filas)

    def terminar_carga(self, id_carga: UUID, reporte: ReporteCarga) -> None:
        fila = self._t(tablas.load_run).por_pk(id_carga)
        if fila is None:
            raise ValueError("terminar_carga: la carga no existe")
        fila.update(_filas.cambios_reporte(fila, reporte))

    def leer_carga(self, id_carga: UUID) -> CargaGuardada | None:
        fila = self._t(tablas.load_run).por_pk(id_carga)
        if fila is None:
            return None
        rechazos = [f for f in self._t(tablas.load_rejection).filas if f["load_run_id"] == id_carga]
        return CargaGuardada(*_filas.carga_de_filas(fila, rechazos))

    # --- TAB-10 y TAB-11 ------------------------------------------------------------------

    def guardar_evaluacion(self, registro: RegistroEvaluacion) -> None:
        self._escribir(_filas.filas_evaluacion(registro))

    def guardar_registro_rechazo(self, registro: RegistroRechazo) -> None:
        self._escribir([(tablas.evaluation, _filas.fila_registro_rechazo(registro))])

    def _evaluacion(self, fila: Fila) -> RegistroEvaluacion | RegistroRechazo:
        canales = [
            c for c in self._t(tablas.evaluation_channel).filas if c["evaluation_id"] == fila["id"]
        ]
        return _filas.evaluacion_de_filas(fila, canales)

    def leer_evaluacion(self, id_: UUID) -> RegistroEvaluacion | RegistroRechazo | None:
        fila = self._t(tablas.evaluation).por_pk(id_)
        return None if fila is None else self._evaluacion(fila)

    def oportunidades_abiertas(
        self, *, instante: dt.datetime, id_producto: UUID | None = None
    ) -> tuple[RegistroEvaluacion, ...]:
        limite = _filas.instante_utc(instante)
        ultima: dict[UUID, Fila] = {}
        for fila in self._t(tablas.evaluation).filas:
            if fila["listing_id"] is None or fila["evaluated_at"] > limite:
                continue
            actual = ultima.get(fila["listing_id"])
            if actual is None or (fila["evaluated_at"], fila["id"]) > (
                actual["evaluated_at"],
                actual["id"],
            ):
                ultima[fila["listing_id"]] = fila
        abiertas = [
            f
            for _, f in sorted(ultima.items())
            if f["result"] == Resultado.NIVEL_ASIGNADO.value
            and (id_producto is None or f["product_id"] == id_producto)
        ]
        return tuple(self._evaluacion(f) for f in abiertas)  # type: ignore[misc]
