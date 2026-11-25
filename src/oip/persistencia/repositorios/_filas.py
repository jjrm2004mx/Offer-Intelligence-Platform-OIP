"""Filas de las tablas (CMP-19) desde los tipos del dominio y de vuelta (CMP-20).

Las **dos** implementaciones del repositorio usan estas funciones: arman las mismas filas,
las normalizan igual y leen el dominio desde ellas. Así son equivalentes por construcción
(design.md §5: la misma batería de contrato pasa con memoria y con PostgreSQL), y la de
memoria se comporta como la base:

- ``numeric(p, s)`` devuelve el valor con la escala de la columna (``29.5`` vuelve como
  ``29.50``): el mismo valor (``==``), nunca otro. Un valor con **más** decimales que la
  escala, o más dígitos enteros que la precisión, se rechaza con ``ValueError`` antes de
  escribir: PostgreSQL lo redondearía en silencio y el repositorio no redondea (DEC-207).
  ``numeric`` sin escala conserva el valor exacto. Nunca pasa por ``float``.
- ``smallint``, ``integer`` y ``bigint`` fuera de su rango, y ``char(n)`` de más de ``n``,
  también se rechazan con ``ValueError`` antes de escribir (PostgreSQL daría un error).
- La memoria aplica además los ``CHECK`` del esquema desde su texto SQL (``_checks``), con
  el mismo nombre de restricción en ``ErrorDeIntegridad``.
- ``timestamptz`` vuelve en UTC; una fecha y hora sin desfase se rechaza.
- **Vacío = ausente:** un texto vacío o solo espacios se rechaza (los ``CHECK``
  ``*_no_vacio`` de T05); lo ausente es ``None``.
- ``jsonb`` viaja como el **texto JSON canónico** de ``oip.evaluacion._canonico`` (CTR-06):
  montos como texto decimal, sin ``float``. La lectura usa el decodificador estricto.

Este módulo reúne las filas de configuración, cargas y capturas, y vuelve a exportar las de
``_columnas`` (normalización), ``_observaciones`` (TAB-03 a TAB-08) y ``_evaluaciones``
(TAB-10 y TAB-11). Una observación guarda lo que tienen sus columnas (TAB-04 a TAB-07); lo
que no tiene columna vuelve como ausente (ver ``observacion_de_filas``).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from typing import Any

from sqlalchemy import (
    Table,
)

from oip.catalogos import (
    TipoRegistro,
)
from oip.configuracion import Configuracion, ConfiguracionVersionada
from oip.entradas.capturas import ESQUEMAS_CAPTURA, Captura
from oip.evaluacion._canonico import a_json, desde_json
from oip.persistencia import tablas
from oip.persistencia.repositorios._columnas import (
    Fila,
    exigir_tipo,
    instante_utc,
    normalizar,
    tienda_de_busqueda,
    utc,
)
from oip.persistencia.repositorios._evaluaciones import (
    evaluacion_de_filas,
    fila_registro_rechazo,
    filas_evaluacion,
)
from oip.persistencia.repositorios._observaciones import (
    fila_identificador,
    fila_producto,
    fila_publicacion,
    filas_observacion,
    observacion_de_filas,
    producto_de_fila,
    publicacion_de_fila,
)
from oip.persistencia.repositorios._tipos import (
    CapturaGuardada,
    CapturaNueva,
    Carga,
    ErrorRepositorio,
    RechazoCarga,
    RegistroRechazo,
    ReporteCarga,
    VersionConfiguracion,
)

__all__ = [
    "TABLA_CAPTURA",
    "OBSERVACION_INCOMPLETA",
    "Fila",
    "cambios_reporte",
    "captura_de_fila",
    "carga_de_filas",
    "configuracion_de_fila",
    "exigir_tipo",
    "evaluacion_de_filas",
    "fila_captura",
    "fila_carga",
    "fila_configuracion",
    "fila_identificador",
    "fila_producto",
    "fila_publicacion",
    "fila_rechazo_carga",
    "fila_registro_rechazo",
    "filas_evaluacion",
    "filas_observacion",
    "instante_utc",
    "mismo_renglon",
    "normalizar",
    "observacion_de_filas",
    "producto_de_fila",
    "publicacion_de_fila",
    "tienda_de_busqueda",
    "tipo_de_captura",
]

#: Mensaje de una observación de TAB-05 sin su disponibilidad (TAB-06) o su publicación
#: (TAB-04): datos inconsistentes. Sin ids ni valores de la fila.
OBSERVACION_INCOMPLETA = (
    "price_observation: la observación no tiene su disponibilidad o su publicación"
)

#: Tabla de cada captura (TAB-09).
TABLA_CAPTURA: Mapping[TipoRegistro, Table] = {
    TipoRegistro.LOCAL_COMPARABLE: tablas.local_comparable,
    TipoRegistro.LOCAL_ESTIMATE: tablas.local_estimate,
    TipoRegistro.MSRP: tablas.msrp_capture,
    TipoRegistro.LOCAL_DEMAND: tablas.local_demand,
    TipoRegistro.STORE_VISIT: tablas.store_visit,
    TipoRegistro.ACTUAL_RESULT: tablas.opportunity_outcome,
    TipoRegistro.CLIENT_REQUEST: tablas.client_request,
}


def tipo_de_captura(captura: Captura) -> TipoRegistro:
    for tipo, esquema in ESQUEMAS_CAPTURA.items():
        if type(captura) is esquema:
            return tipo
    raise TypeError("captura: tipo no admitido")


# --- TAB-01 config_version ----------------------------------------------------------------


def fila_configuracion(
    configuracion: ConfiguracionVersionada, cargada_en: dt.datetime, id_: int | None
) -> Fila:
    if not isinstance(configuracion, ConfiguracionVersionada):
        raise TypeError("configuracion: se esperaba ConfiguracionVersionada")
    fila = {
        "id": id_,
        "version": configuracion.version,
        "sha256": configuracion.sha256,
        "schema_version": configuracion.schema_version,
        "content": a_json(configuracion.contenido, Configuracion),
        "source_file": configuracion.origen,
        "loaded_at": cargada_en,
    }
    return normalizar(tablas.config_version, fila)


def configuracion_de_fila(fila: Mapping[str, Any]) -> VersionConfiguracion:
    contenido = desde_json(fila["content"], Configuracion)
    configuracion = ConfiguracionVersionada(
        version=fila["version"],
        schema_version=fila["schema_version"],
        sha256=fila["sha256"],
        contenido=contenido,
        origen=fila["source_file"],
    )
    return VersionConfiguracion(fila["id"], configuracion, utc(fila["loaded_at"]))


# --- TAB-02 load_run y load_rejection -----------------------------------------------------


def fila_carga(carga: Carga) -> Fila:
    if not isinstance(carga, Carga):
        raise TypeError("carga: se esperaba Carga")
    fila = {
        "id": carga.id,
        "file_name": carga.archivo,
        "file_sha256": carga.sha256_archivo,
        "format": carga.formato,
        "record_type": carga.tipo_registro,
        "started_at": carga.iniciada_en,
        "finished_at": None,
        "loaded": 0,
        "rejected": 0,
        "duplicates": 0,
        "rejected_by_reason": a_json({}, Mapping[str, int]),
        "config_version_id": carga.id_version_configuracion,
    }
    return normalizar(tablas.load_run, fila)


def cambios_reporte(fila_actual: Mapping[str, Any], reporte: ReporteCarga) -> Fila:
    """Las columnas que cambia el cierre de una carga, ya normalizadas."""
    if not isinstance(reporte, ReporteCarga):
        raise TypeError("reporte: se esperaba ReporteCarga")
    if reporte.terminada_en < utc(fila_actual["started_at"]):
        raise ValueError("load_run.finished_at: no antes de started_at")
    if fila_actual["finished_at"] is not None:
        raise ValueError("load_run: la carga ya terminó")
    fila = dict(fila_actual)
    fila.update(
        finished_at=reporte.terminada_en,
        loaded=reporte.cargados,
        rejected=reporte.rechazados,
        duplicates=reporte.duplicados,
        rejected_by_reason=a_json(dict(reporte.rechazados_por_motivo), Mapping[str, int]),
    )
    normalizada = normalizar(tablas.load_run, fila)
    nombres = ("finished_at", "loaded", "rejected", "duplicates", "rejected_by_reason")
    return {n: normalizada[n] for n in nombres}


def fila_rechazo_carga(rechazo: RechazoCarga) -> Fila:
    if not isinstance(rechazo, RechazoCarga):
        raise TypeError("rechazo: se esperaba RechazoCarga")
    fila = {
        "load_run_id": rechazo.id_carga,
        "line_number": rechazo.renglon,
        "record_type": rechazo.tipo_registro,
        "reason": rechazo.motivo,
        "field": rechazo.campo,
    }
    return normalizar(tablas.load_rejection, fila)


def carga_de_filas(
    fila: Mapping[str, Any], rechazos: list[Mapping[str, Any]]
) -> tuple[Carga, ReporteCarga | None, tuple[RechazoCarga, ...]]:
    carga = Carga(
        id=fila["id"],
        archivo=fila["file_name"],
        sha256_archivo=fila["file_sha256"],
        formato=fila["format"],
        iniciada_en=utc(fila["started_at"]),
        id_version_configuracion=fila["config_version_id"],
        tipo_registro=None if fila["record_type"] is None else TipoRegistro(fila["record_type"]),
    )
    reporte = None
    if fila["finished_at"] is not None:
        reporte = ReporteCarga(
            terminada_en=utc(fila["finished_at"]),
            cargados=fila["loaded"],
            rechazados=fila["rejected"],
            duplicados=fila["duplicates"],
            rechazados_por_motivo=desde_json(fila["rejected_by_reason"], Mapping[str, int]),
        )
    leidos = tuple(
        RechazoCarga(
            id_carga=r["load_run_id"],
            renglon=r["line_number"],
            motivo=r["reason"],
            tipo_registro=None if r["record_type"] is None else TipoRegistro(r["record_type"]),
            campo=r["field"],
        )
        for r in sorted(rechazos, key=lambda r: r["line_number"])
    )
    return carga, reporte, leidos


# --- TAB-09 capturas ----------------------------------------------------------------------


def fila_captura(nueva: CapturaNueva) -> tuple[Table, Fila]:
    if not isinstance(nueva, CapturaNueva):
        raise TypeError("nueva: se esperaba CapturaNueva")
    tipo = tipo_de_captura(nueva.captura)
    tabla = TABLA_CAPTURA[tipo]
    if "product_id" not in tabla.c and nueva.id_producto is not None:
        raise ValueError(f"{tabla.name}: este tipo de captura no lleva producto")
    fila: dict[str, Any] = {
        nombre: getattr(nueva.captura, nombre) for nombre in type(nueva.captura).model_fields
    }
    fila.update(
        id=nueva.id,
        load_run_id=nueva.id_carga,
        idempotency_key=nueva.huella,
        captured_at=nueva.capturada_en,
    )
    if "product_id" in tabla.c:
        fila["product_id"] = nueva.id_producto
    if tipo is TipoRegistro.LOCAL_COMPARABLE:
        fila["price_usd"] = nueva.captura.price_usd  # type: ignore[union-attr]
    return tabla, normalizar(tabla, fila)


def captura_de_fila(tipo: TipoRegistro, fila: Mapping[str, Any]) -> CapturaGuardada:
    esquema = ESQUEMAS_CAPTURA[tipo]
    datos = {
        (info.alias or nombre): utc(fila[nombre])
        if isinstance(fila[nombre], dt.datetime)
        else fila[nombre]
        for nombre, info in esquema.model_fields.items()
    }
    try:
        captura = esquema.model_validate(datos)
    except ValueError:
        raise ErrorRepositorio(
            f"{TABLA_CAPTURA[tipo].name}: la fila no forma una captura"
        ) from None
    return CapturaGuardada(
        id=fila["id"],
        captura=captura,  # type: ignore[arg-type]
        id_carga=fila["load_run_id"],
        capturada_en=utc(fila["captured_at"]),
        id_producto=fila.get("product_id"),
    )


def mismo_renglon(rechazo: RechazoCarga, registro: RegistroRechazo) -> None:
    """El registro ``RECHAZADA_VALIDACION`` de un renglón rechazado es de ese renglón."""
    if (registro.id_carga, registro.renglon) != (rechazo.id_carga, rechazo.renglon):
        raise ValueError("registro: debe ser de la misma carga y renglón que el rechazo")
