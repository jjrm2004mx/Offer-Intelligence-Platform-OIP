"""Filas de una evaluación (TAB-10, TAB-11) y del registro de un rechazo (DEC-250), y el
registro desde sus filas (CMP-20)."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Table,
)

from oip.catalogos import (
    CalidadPrecio,
    Canal,
    CausaCanalCerrado,
    CausaCanalPorRevisar,
    Confianza,
    EstadoCanal,
    Identificacion,
    Motivo,
    Nivel,
    ReferenciaPrecio,
    Resultado,
)
from oip.evaluacion._canonico import a_json, desde_json
from oip.evaluacion.contexto import (
    ContextoEvaluacion,
    EvaluacionCanal,
    ObservacionUsada,
    Referencias,
    RegistroEvaluacion,
)
from oip.persistencia import tablas
from oip.persistencia.repositorios._columnas import (
    Fila,
    enum_o_none,
    json_o_none,
    leer_json_o_none,
    normalizar,
    utc,
)
from oip.persistencia.repositorios._tipos import (
    ErrorRepositorio,
    RegistroRechazo,
)

_RECHAZADA = Resultado.RECHAZADA_VALIDACION

# --- TAB-10 y TAB-11: evaluación ----------------------------------------------------------


def filas_evaluacion(registro: RegistroEvaluacion) -> list[tuple[Table, Fila]]:
    """TAB-10 y TAB-11 de un registro del motor (no un rechazo de validación, DEC-250)."""
    if not isinstance(registro, RegistroEvaluacion):
        raise TypeError("registro: se esperaba RegistroEvaluacion")
    if registro.resultado is _RECHAZADA:
        raise ValueError(
            "registro: un RECHAZADA_VALIDACION no guarda su contexto (DEC-250); use RegistroRechazo"
        )
    fila = {
        "id": registro.id,
        "evaluated_at": registro.evaluado_en,
        "offer_observation_id": registro.id_observacion_oferta,
        "listing_id": registro.id_publicacion,
        "product_id": registro.id_producto,
        "config_version_id": registro.id_version_configuracion,
        "rn_versions": a_json(registro.versiones_rn, Mapping[str, int]),
        "result": registro.resultado,
        "main_reason": registro.motivo_principal,
        "reasons": registro.motivos,
        "rejection_reason": registro.motivo_rechazo,
        "marks": registro.marcas,
        "price_quality": registro.calidad_precio,
        "confidence": registro.confianza,
        "identification": registro.identificacion,
        "references": json_o_none(registro.referencias, Referencias),
        "advertised_discount": registro.descuento_anunciado,
        "real_discount": registro.descuento_real,
        "purchase_cost": registro.costo_compra,
        "chosen_channel": registro.canal_elegido,
        "alert_level": registro.nivel_aviso,
        "alert_channel": registro.canal_aviso,
        "observations_used": a_json(registro.observaciones_usadas, tuple[ObservacionUsada, ...]),
        "input_snapshot": registro.entrada.a_json(),
        "previous_evaluation_id": registro.id_evaluacion_anterior,
        "changed_references": registro.referencias_cambiadas,
        "no_longer_recommended": registro.ya_no_recomendado,
        "load_run_id": registro.id_carga,
        "line_number": None,
    }
    filas = [(tablas.evaluation, normalizar(tablas.evaluation, fila))]
    for canal in registro.canales:
        filas.append(
            (
                tablas.evaluation_channel,
                normalizar(
                    tablas.evaluation_channel,
                    {
                        "evaluation_id": registro.id,
                        "channel": canal.canal,
                        "state": canal.estado,
                        "closed_causes": canal.causas_cerrado,
                        "review_causes": canal.causas_por_revisar,
                        "sale_price": canal.precio_venta,
                        "selling_cost": canal.costo_venta,
                        "net_margin": canal.margen_neto,
                        "net_margin_pct": canal.margen_neto_pct,
                        "returns_cost": canal.costo_devoluciones,
                        "drop_penalty": canal.castigo,
                        "adjusted_margin": canal.margen_ajustado,
                        "adjusted_margin_pct": canal.margen_ajustado_pct,
                        "units": canal.unidades,
                        "days_to_recover": canal.dias_para_recuperar,
                        "monthly_yield_pct": canal.rendimiento_mensual_pct,
                        "level": canal.nivel,
                        "calculated_level": canal.nivel_calculado,
                        "total_profit": canal.ganancia_total,
                        "marks": canal.marcas,
                    },
                ),
            )
        )
    return filas


def fila_registro_rechazo(registro: RegistroRechazo) -> Fila:
    """TAB-10 de un rechazo de validación (DEC-250): nada del renglón."""
    if not isinstance(registro, RegistroRechazo):
        raise TypeError("registro: se esperaba RegistroRechazo")
    fila = {
        "id": registro.id,
        "evaluated_at": registro.evaluado_en,
        "config_version_id": registro.id_version_configuracion,
        "rn_versions": a_json(registro.versiones_rn, Mapping[str, int]),
        "result": _RECHAZADA,
        "reasons": (),
        "rejection_reason": registro.motivo_rechazo,
        "marks": (),
        "observations_used": a_json((), tuple[ObservacionUsada, ...]),
        "changed_references": (),
        "no_longer_recommended": False,
        "load_run_id": registro.id_carga,
        "line_number": registro.renglon,
    }
    return normalizar(tablas.evaluation, fila)


def _entero(valor: Decimal | None, ruta: str) -> int | None:
    if valor is None:
        return None
    if valor != valor.to_integral_value():
        raise ErrorRepositorio(f"{ruta}: se esperaba un entero")
    return int(valor)


def evaluacion_de_filas(
    fila: Mapping[str, Any], canales: list[Mapping[str, Any]]
) -> RegistroEvaluacion | RegistroRechazo:
    versiones = desde_json(fila["rn_versions"], Mapping[str, int])
    if fila["result"] == _RECHAZADA.value:
        return RegistroRechazo(
            id=fila["id"],
            evaluado_en=utc(fila["evaluated_at"]),
            id_version_configuracion=fila["config_version_id"],
            versiones_rn=versiones,
            motivo_rechazo=fila["rejection_reason"],
            id_carga=fila["load_run_id"],
            renglon=fila["line_number"],
        )
    if fila["input_snapshot"] is None:
        raise ErrorRepositorio("evaluation: un registro del motor sin input_snapshot")
    orden = list(Canal)
    leidos = sorted(canales, key=lambda c: orden.index(Canal(c["channel"])))
    return RegistroEvaluacion(
        id=fila["id"],
        evaluado_en=utc(fila["evaluated_at"]),
        id_observacion_oferta=fila["offer_observation_id"],
        id_publicacion=fila["listing_id"],
        id_producto=fila["product_id"],
        id_version_configuracion=fila["config_version_id"],
        versiones_rn=versiones,
        resultado=Resultado(fila["result"]),
        motivo_principal=enum_o_none(Motivo, fila["main_reason"]),
        motivos=tuple(Motivo(m) for m in fila["reasons"]),
        motivo_rechazo=fila["rejection_reason"],
        marcas=tuple(fila["marks"]),
        calidad_precio=enum_o_none(CalidadPrecio, fila["price_quality"]),
        confianza=enum_o_none(Confianza, fila["confidence"]),
        identificacion=enum_o_none(Identificacion, fila["identification"]),
        referencias=leer_json_o_none(fila["references"], Referencias),
        descuento_anunciado=fila["advertised_discount"],
        descuento_real=fila["real_discount"],
        costo_compra=fila["purchase_cost"],
        canal_elegido=enum_o_none(Canal, fila["chosen_channel"]),
        nivel_aviso=enum_o_none(Nivel, fila["alert_level"]),
        canal_aviso=enum_o_none(Canal, fila["alert_channel"]),
        canales=tuple(_canal_de_fila(c) for c in leidos),
        observaciones_usadas=desde_json(fila["observations_used"], tuple[ObservacionUsada, ...]),
        entrada=ContextoEvaluacion.desde_json(fila["input_snapshot"]),
        id_evaluacion_anterior=fila["previous_evaluation_id"],
        referencias_cambiadas=tuple(ReferenciaPrecio(r) for r in fila["changed_references"]),
        ya_no_recomendado=fila["no_longer_recommended"],
        id_carga=fila["load_run_id"],
    )


def _canal_de_fila(c: Mapping[str, Any]) -> EvaluacionCanal:
    return EvaluacionCanal(
        canal=Canal(c["channel"]),
        estado=EstadoCanal(c["state"]),
        causas_cerrado=tuple(CausaCanalCerrado(x) for x in c["closed_causes"]),
        causas_por_revisar=tuple(CausaCanalPorRevisar(x) for x in c["review_causes"]),
        precio_venta=c["sale_price"],
        costo_venta=c["selling_cost"],
        margen_neto=c["net_margin"],
        margen_neto_pct=c["net_margin_pct"],
        costo_devoluciones=c["returns_cost"],
        castigo=c["drop_penalty"],
        margen_ajustado=c["adjusted_margin"],
        margen_ajustado_pct=c["adjusted_margin_pct"],
        unidades=c["units"],
        dias_para_recuperar=_entero(c["days_to_recover"], "evaluation_channel.days_to_recover"),
        rendimiento_mensual_pct=c["monthly_yield_pct"],
        nivel=enum_o_none(Nivel, c["level"]),
        nivel_calculado=enum_o_none(Nivel, c["calculated_level"]),
        ganancia_total=c["total_profit"],
        marcas=tuple(c["marks"]),
    )
