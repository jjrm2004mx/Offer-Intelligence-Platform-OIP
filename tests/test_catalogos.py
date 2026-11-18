"""Pruebas unitarias de oip.catalogos (CMP-03; design.md §9; tasks.md T01 1.3).

Los valores se copian del REQ-2026-0001 §3.2.1 a §3.2.6, de design.md §9 y de la
arquitectura v2.2 §8: con sus espacios y acentos.
"""

import pytest

from oip import catalogos as c


def valores(enum):
    return [m.value for m in enum]


# --- Motivos y su orden (REQ §3.2.3) --------------------------------------------------


def test_motivos_en_el_orden_de_req_3_2_3():
    assert valores(c.Motivo) == [
        "EVITAR",
        "MERCADO YA BARATO",
        "SIN CANAL DISPONIBLE",
        "MARGEN NEGATIVO",
        "SOLO REFERENCIA",
        "SIN HISTORIAL SUFICIENTE",
        "SIN REFERENCIA DE USADOS",
        "COINCIDENCIA NO CONFIRMADA",
        "VENDEDOR EXTERNO",
        "PARTICULAR",
        "RIESGO DE PROCEDENCIA",
        "DEMANDA DESCONOCIDA",
    ]


def test_cada_motivo_lleva_a_su_resultado():
    r = c.Resultado
    assert [m.lleva_a for m in c.Motivo] == [
        r.DESCARTADA,
        r.DESCARTADA,
        r.DESCARTADA,
        r.DESCARTADA,
        r.SOLO_REFERENCIA,
        r.REVISION_MANUAL,
        r.REVISION_MANUAL,
        r.REVISION_MANUAL,
        r.REVISION_MANUAL,
        r.REVISION_MANUAL,
        r.REVISION_MANUAL,
        r.REVISION_MANUAL,
    ]


def test_los_motivos_de_descarte_van_antes_que_los_demas():
    # Coherente con §3.2.4: los motivos de DESCARTADA son los primeros de §3.2.3.
    destinos = [m.lleva_a for m in c.Motivo]
    ultimo_descarte = max(i for i, d in enumerate(destinos) if d is c.Resultado.DESCARTADA)
    primero_otro = min(i for i, d in enumerate(destinos) if d is not c.Resultado.DESCARTADA)
    assert ultimo_descarte < primero_otro


# --- Resultado ------------------------------------------------------------------------


def test_resultados_de_req_3_2_2():
    assert valores(c.Resultado) == [
        "RECHAZADA_VALIDACION",
        "DESCARTADA",
        "SOLO_REFERENCIA",
        "REVISION_MANUAL",
        "SIN_NIVEL",
        "NIVEL_ASIGNADO",
    ]


# --- Motivos de rechazo ---------------------------------------------------------------


def test_motivos_de_rechazo_en_el_orden_de_comprobacion_de_design_6():
    assert valores(c.MotivoRechazo) == [
        "TIPO DE REGISTRO DESCONOCIDO",
        "CAMPO OBLIGATORIO FALTANTE",
        "PRECIO INVÁLIDO",
        "DOMINIO NO AUTORIZADO",
        "CIUDAD NO CONFIGURADA",
    ]


@pytest.mark.parametrize(
    ("campo", "esperado"),
    [
        ("exchangeRate", "CAMPO OBLIGATORIO FALTANTE (exchangeRate)"),
        ("condition", "CAMPO OBLIGATORIO FALTANTE (condition)"),
        ("pickupLocation", "CAMPO OBLIGATORIO FALTANTE (pickupLocation)"),
        ("price.current", "CAMPO OBLIGATORIO FALTANTE (price.current)"),
    ],
)
def test_motivo_campo_faltante_lleva_el_nombre_del_campo(campo, esperado):
    assert c.motivo_campo_faltante(campo) == esperado


@pytest.mark.parametrize("campo", ["", "   ", None])
def test_motivo_campo_faltante_exige_el_campo(campo):
    with pytest.raises(ValueError):
        c.motivo_campo_faltante(campo)


# --- Marcas ---------------------------------------------------------------------------


def test_marcas_de_req_3_2_3():
    assert valores(c.Marca) == [
        "PRECIO ANTES INFLADO",
        "DESCUENTO ANUNCIADO NO COMPROBADO",
        "DEMANDA A LA BAJA",
        "COMPETENCIA MÁS BARATA",
        "SIN OFERTA HOY",
        "MATERIAL PELIGROSO",
        "REVISAR RETIROS",
        "SIN COMPARABLES LOCALES",
        "CONFIANZA BAJA",
        "ESTIMADO",
        "MARGEN ESTIMADO",
        "EMPAQUE POR CONFIRMAR",
    ]


@pytest.mark.parametrize(
    ("dato", "esperado"),
    [
        ("peso", "ESTIMADO (peso)"),
        ("devolución", "ESTIMADO (devolución)"),
        ("unidades", "ESTIMADO (unidades)"),
    ],
)
def test_marca_estimado_lleva_el_dato(dato, esperado):
    assert c.marca_estimado(dato) == esperado


def test_marca_estimado_exige_el_dato():
    with pytest.raises(ValueError):
        c.marca_estimado("")


# --- Canales --------------------------------------------------------------------------


def test_canales_y_estados():
    assert valores(c.Canal) == ["amazon", "local"]
    assert valores(c.EstadoCanal) == ["CERRADO", "POR_REVISAR", "DISPONIBLE"]


def test_causas_de_canal_cerrado_por_canal():
    amazon = c.CAUSAS_CERRADO_POR_CANAL[c.Canal.AMAZON]
    local = c.CAUSAS_CERRADO_POR_CANAL[c.Canal.LOCAL]
    assert [x.value for x in amazon] == [
        "SIN PRECIO DE VENTA EN AMAZON",
        "DEMANDA INSUFICIENTE EN AMAZON",
        "NO VENDIBLE EN AMAZON (POR AHORA)",
        "COMISIÓN DESCONOCIDA",
        "TASA DE DEVOLUCIÓN DESCONOCIDA",
        "ENVÍO POR COTIZAR",
        "PRODUCTO NO NUEVO",
        "SIN ROTACIÓN",
    ]
    assert [x.value for x in local] == ["DEMANDA LOCAL BAJA", "SIN PRECIO LOCAL", "SIN ROTACIÓN"]
    assert set(amazon) | set(local) == set(c.CausaCanalCerrado)


def test_causas_de_canal_por_revisar_por_canal():
    assert [x.value for x in c.CAUSAS_POR_REVISAR_POR_CANAL[c.Canal.AMAZON]] == [
        "DEMANDA DESCONOCIDA"
    ]
    assert [x.value for x in c.CAUSAS_POR_REVISAR_POR_CANAL[c.Canal.LOCAL]] == [
        "SIN REFERENCIA DE USADOS"
    ]


def test_las_tablas_de_causas_no_se_modifican():
    with pytest.raises(TypeError):
        c.CAUSAS_CERRADO_POR_CANAL[c.Canal.AMAZON] = ()
    with pytest.raises(TypeError):
        c.CAUSAS_POR_REVISAR_POR_CANAL[c.Canal.LOCAL] = ()


# --- Niveles --------------------------------------------------------------------------


def test_niveles_de_mayor_a_menor():
    assert valores(c.Nivel) == ["COMPRAR_YA", "MUY_RECOMENDABLE", "RECOMENDABLE", "VIGILAR"]


def test_bajar_un_nivel_es_el_siguiente_y_vigilar_queda_sin_nivel():
    assert c.nivel_inferior(c.Nivel.COMPRAR_YA) is c.Nivel.MUY_RECOMENDABLE
    assert c.nivel_inferior(c.Nivel.MUY_RECOMENDABLE) is c.Nivel.RECOMENDABLE
    assert c.nivel_inferior(c.Nivel.RECOMENDABLE) is c.Nivel.VIGILAR
    assert c.nivel_inferior(c.Nivel.VIGILAR) is None


# --- Calidad del precio ---------------------------------------------------------------


def test_calidad_en_el_orden_de_asignacion_de_rn_012():
    # RN-012 §4: se asigna la primera que se cumple; Descuento cuestionable va primero.
    assert valores(c.CalidadPrecio) == [
        "DESCUENTO_CUESTIONABLE",
        "OFERTA_EXCEPCIONAL",
        "BUENA_OFERTA",
        "PRECIO_COMPETITIVO",
        "PRECIO_NORMAL",
        "NO_APLICA",
    ]


# --- Confianza, demanda, recordType y referencias -------------------------------------


def test_confianza_y_demanda():
    assert valores(c.Confianza) == ["ALTA", "MEDIA", "BAJA"]
    assert valores(c.DemandaAmazon) == ["SUFICIENTE", "INSUFICIENTE", "DESCONOCIDA"]
    assert valores(c.DemandaLocal) == ["high", "medium", "low"]


def test_tipos_de_registro():
    assert valores(c.TipoRegistro) == [
        "observation",
        "local_comparable",
        "local_estimate",
        "msrp",
        "local_demand",
        "store_visit",
        "actual_result",
        "client_request",
    ]


def test_referencias_de_precio_de_req_3_2_5():
    assert valores(c.ReferenciaPrecio) == [
        "precio_habitual",
        "precio_mercado_hoy",
        "minimo_60_dias_amazon",
        "precio_venta_amazon",
    ]


# --- Códigos del contrato de ingesta 3.1 (arquitectura v2.2 §8) -----------------------


def test_codigos_cerrados_del_contrato_3_1():
    assert valores(c.EstadoDisponibilidad) == [
        "in_stock_confirmed",
        "in_stock",
        "limited_stock",
        "unconfirmed",
        "out_of_stock",
        "listed",
    ]
    assert valores(c.Categoria) == [
        "tools",
        "home_lighting",
        "home_kitchen",
        "electronics",
        "video_game_consoles",
        "video_games",
        "toys",
        "watches",
        "jewelry",
        "beauty",
    ]
    assert valores(c.Condicion) == ["new", "open_box", "refurbished", "used", "for_parts"]
    assert valores(c.Vendedor) == ["comercio", "externo", "particular", "desconocido"]
    assert valores(c.ModoCompra) == ["envio", "recoleccion", "tienda", "particular"]


def test_un_codigo_fuera_del_catalogo_no_existe():
    with pytest.raises(ValueError):
        c.Categoria("foo")
    with pytest.raises(ValueError):
        c.Condicion("nuevo")


def test_los_codigos_se_comparan_como_texto():
    # Los códigos se guardan como texto (design.md §4); el enum es igual a su código.
    assert c.Motivo.MERCADO_YA_BARATO == "MERCADO YA BARATO"
    assert f"{c.CausaCanalCerrado.COMISION_DESCONOCIDA}" == "COMISIÓN DESCONOCIDA"
