"""Pruebas de T24: endurecimiento de los tipos de T04 (decisiones 12, 13, 15, 20, 23, 28, 34
y 36 del issue #34; DEC-266, DEC-269).

Sin escenarios propios (tasks.md T24). Fixtures sintéticos; las URL son de example.com y
ninguna prueba las abre.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from config_tienda_prueba import (
    BASE,
    DOMINIO_PRUEBA_2,
    SUCURSAL_PRUEBA,
    SUCURSAL_PRUEBA_2,
    TIENDA_PRUEBA,
    TIENDA_PRUEBA_2,
    con_tienda_prueba,
    configuracion_con_sucursales_prueba,
    configuracion_con_tienda_prueba,
)
from oip.catalogos import (
    Canal,
    CausaCanalCerrado,
    CausaCanalPorRevisar,
    DatoEstimado,
    EstadoCanal,
    Marca,
    ReferenciaPrecio,
    Resultado,
    es_marca,
    marca_estimado,
)
from oip.configuracion import ErrorConfiguracion, cargar_configuracion_texto
from oip.entradas.contrato import leer_observacion
from oip.evaluacion.contexto import (
    ContextoEvaluacion,
    EvaluacionCanal,
    ObservacionRegistrada,
    Referencias,
    RegistroEvaluacion,
)

CONFIG = configuracion_con_tienda_prueba()
INSTANTE = dt.datetime(2026, 11, 16, 20, 0, tzinfo=dt.UTC)
VACIOS = ["", "   ", "\t\n"]


def _observacion(**cambios):
    datos = {
        "retailerCode": TIENDA_PRUEBA,
        "productUrl": "https://example.com/p/1",
        "title": "Taladro de prueba",
        "category": "tools",
        "price": {"current": "29.00", "currency": "USD"},
        "seller": "comercio",
        "condition": "new",
        "availability": {"state": "in_stock"},
        "purchaseMode": "envio",
        "extractedAt": "2026-11-16T10:00:00-08:00",
        "blocked": False,
    }
    datos.update(cambios)
    return leer_observacion(datos)


def _contexto(**cambios) -> ContextoEvaluacion:
    base = {
        "id_evaluacion": UUID(int=1),
        "instante": INSTANTE,
        "configuracion": CONFIG,
        "id_version_configuracion": 7,
        "oferta": ObservacionRegistrada(_observacion(), UUID(int=10), UUID(int=11), UUID(int=12)),
        "id_evaluacion_anterior": UUID(int=2),
        "referencias_cambiadas": (ReferenciaPrecio.PRECIO_HABITUAL,),
        "id_carga": UUID(int=3),
    }
    base.update(cambios)
    return ContextoEvaluacion(**base)


def _registro(**cambios) -> RegistroEvaluacion:
    contexto = cambios.pop("entrada", None) or _contexto()
    base = {
        "id": contexto.id_evaluacion,
        "evaluado_en": contexto.instante,
        "id_observacion_oferta": contexto.oferta.id,
        "id_publicacion": contexto.oferta.id_publicacion,
        "id_producto": contexto.oferta.id_producto,
        "id_version_configuracion": contexto.id_version_configuracion,
        "versiones_rn": contexto.versiones_rn,
        "resultado": Resultado.SIN_NIVEL,
        "motivo_principal": None,
        "motivos": (),
        "motivo_rechazo": None,
        "marcas": (),
        "calidad_precio": None,
        "confianza": None,
        "identificacion": None,
        "referencias": None,
        "descuento_anunciado": None,
        "descuento_real": None,
        "costo_compra": None,
        "canal_elegido": None,
        "nivel_aviso": None,
        "canal_aviso": None,
        "canales": (),
        "observaciones_usadas": (),
        "entrada": contexto,
        "id_evaluacion_anterior": contexto.id_evaluacion_anterior,
        "referencias_cambiadas": contexto.referencias_cambiadas,
        "id_carga": contexto.id_carga,
    }
    base.update(cambios)
    return RegistroEvaluacion(**base)


def _rechazado(**cambios) -> RegistroEvaluacion:
    base = {
        "resultado": Resultado.RECHAZADA_VALIDACION,
        "id_observacion_oferta": None,
        "motivo_rechazo": "PRECIO INVÁLIDO",
    }
    base.update(cambios)
    return _registro(**base)


# --- 12: vacío = ausente en motivo_rechazo, marcas y fuente_precio_habitual -----------------


@pytest.mark.parametrize("vacio", VACIOS)
def test_12_texto_vacio_o_solo_espacios_se_rechaza(vacio):
    assert _rechazado().motivo_rechazo == "PRECIO INVÁLIDO"
    with pytest.raises(ValueError, match="motivo_rechazo"):
        _rechazado(motivo_rechazo=vacio)
    with pytest.raises(ValueError, match=r"marcas\[0\]"):
        _registro(marcas=(vacio,))
    with pytest.raises(ValueError, match=r"marcas\[0\]"):
        EvaluacionCanal(canal=Canal.LOCAL, estado=EstadoCanal.DISPONIBLE, marcas=(vacio,))
    assert Referencias(fuente_precio_habitual="historial_propio").fuente_precio_habitual
    assert Referencias(fuente_precio_habitual=None).fuente_precio_habitual is None
    with pytest.raises(ValueError, match="fuente_precio_habitual"):
        Referencias(fuente_precio_habitual=vacio)


# --- 13: el registro coincide con su entrada --------------------------------------------------


@pytest.mark.parametrize(
    "cambios",
    [
        {"id": UUID(int=99)},
        {"evaluado_en": INSTANTE + dt.timedelta(seconds=1)},
        {"versiones_rn": {}},
        {"versiones_rn": {"RN-001": 999}},
        {"id_evaluacion_anterior": None},
        {"id_evaluacion_anterior": UUID(int=98)},
        {"referencias_cambiadas": ()},
        {"referencias_cambiadas": (ReferenciaPrecio.PRECIO_MERCADO_HOY,)},
        {"id_carga": None},
        {"id_carga": UUID(int=97)},
    ],
    ids=lambda c: next(iter(c)),
)
def test_13_el_registro_exige_los_datos_de_su_entrada(cambios):
    registro = _registro()
    assert registro.id == registro.entrada.id_evaluacion
    with pytest.raises(ValueError, match=f"{next(iter(cambios))}: distinto"):
        _registro(**cambios)


def test_13_el_mismo_instante_en_otra_zona_es_igual_a_la_entrada():
    tijuana = dt.timezone(dt.timedelta(hours=-8))
    registro = _registro(evaluado_en=INSTANTE.astimezone(tijuana))
    assert registro.evaluado_en == INSTANTE


# --- 15: marcas del catálogo (DEC-266) --------------------------------------------------------


def test_15_las_marcas_se_validan_contra_el_catalogo():
    validas = (
        *(m.value for m in Marca if m is not Marca.ESTIMADO),
        *(c.value for c in CausaCanalCerrado),
        *(marca_estimado(d) for d in DatoEstimado),
    )
    assert [d.value for d in DatoEstimado] == ["peso", "devolución", "unidades"]
    assert all(es_marca(m) for m in validas)
    assert _registro(marcas=validas).marcas == validas
    canal = EvaluacionCanal(canal=Canal.AMAZON, estado=EstadoCanal.DISPONIBLE, marcas=validas)
    assert canal.marcas == validas
    invalidas = [
        "ESTIMADO",  # sin dato
        "ESTIMADO (color)",  # dato fuera del catálogo
        "ESTIMADO(peso)",
        "estimado (peso)",
        " MARGEN ESTIMADO",
        "MARCA INVENTADA",
        CausaCanalPorRevisar.DEMANDA_DESCONOCIDA.value,  # una causa de por revisar no es marca
        CausaCanalPorRevisar.SIN_REFERENCIA_DE_USADOS.value,
    ]
    for marca in invalidas:
        assert not es_marca(marca)
        with pytest.raises(ValueError, match=r"marcas\[1\]: fuera del catálogo") as error:
            _registro(marcas=("MARGEN ESTIMADO", marca))
        assert marca not in str(error.value) or marca == "ESTIMADO"
        with pytest.raises(ValueError, match=r"marcas\[0\]: fuera del catálogo"):
            EvaluacionCanal(canal=Canal.AMAZON, estado=EstadoCanal.DISPONIBLE, marcas=(marca,))
    with pytest.raises(ValueError, match="DatoEstimado"):
        marca_estimado("color")


# --- 20: enteros y zona de la configuración con fullmatch -------------------------------------


def test_20_un_entero_con_salto_de_linea_final_se_rechaza():
    texto = con_tienda_prueba(BASE.read_text(encoding="utf-8"))
    assert "usual_window_days: 60\n" in texto
    malo = texto.replace("usual_window_days: 60\n", 'usual_window_days: !!int "60\\n"\n', 1)
    with pytest.raises(ErrorConfiguracion, match="número no admitido"):
        cargar_configuracion_texto(malo)
    bueno = texto.replace("usual_window_days: 60\n", 'usual_window_days: !!int "60"\n', 1)
    assert cargar_configuracion_texto(bueno).contenido == CONFIG.contenido


def test_20_una_zona_con_salto_de_linea_final_se_rechaza():
    texto = con_tienda_prueba(BASE.read_text(encoding="utf-8"))
    assert "timezone: America/Tijuana " in texto
    malo = texto.replace("timezone: America/Tijuana ", 'timezone: "America/Tijuana\\n" ', 1)
    with pytest.raises(ErrorConfiguracion, match="timezone"):
        cargar_configuracion_texto(malo)


# --- 23: causas en el orden del catálogo del canal (DEC-269) ----------------------------------


def test_23_las_causas_van_en_el_orden_del_catalogo_del_canal():
    amazon = (
        CausaCanalCerrado.NO_VENDIBLE_EN_AMAZON,
        CausaCanalCerrado.ENVIO_POR_COTIZAR,
        CausaCanalCerrado.SIN_ROTACION,
    )
    local = (CausaCanalCerrado.DEMANDA_LOCAL_BAJA, CausaCanalCerrado.SIN_ROTACION)
    assert EvaluacionCanal(
        canal=Canal.AMAZON, estado=EstadoCanal.CERRADO, causas_cerrado=amazon
    ).causas_cerrado == (amazon)
    # SIN ROTACIÓN va antes de DEMANDA LOCAL BAJA en el enum, pero no en la lista local.
    assert EvaluacionCanal(canal=Canal.LOCAL, estado=EstadoCanal.CERRADO, causas_cerrado=local)
    with pytest.raises(ValueError, match="causas_cerrado: en el orden"):
        EvaluacionCanal(canal=Canal.AMAZON, estado=EstadoCanal.CERRADO, causas_cerrado=amazon[::-1])
    with pytest.raises(ValueError, match="causas_cerrado: en el orden"):
        EvaluacionCanal(canal=Canal.LOCAL, estado=EstadoCanal.CERRADO, causas_cerrado=local[::-1])
    with pytest.raises(ValueError, match="causas_cerrado: fuera del catálogo del canal"):
        EvaluacionCanal(
            canal=Canal.LOCAL,
            estado=EstadoCanal.CERRADO,
            causas_cerrado=(CausaCanalCerrado.ENVIO_POR_COTIZAR,),
        )
    with pytest.raises(ValueError, match="causas_por_revisar: fuera del catálogo del canal"):
        EvaluacionCanal(
            canal=Canal.AMAZON,
            estado=EstadoCanal.POR_REVISAR,
            causas_por_revisar=(CausaCanalPorRevisar.SIN_REFERENCIA_DE_USADOS,),
        )


# --- 28: sucursales sintéticas por cadena -----------------------------------------------------


def test_28_sucursales_sinteticas_por_cadena():
    config = configuracion_con_sucursales_prueba().contenido
    assert config.stores[SUCURSAL_PRUEBA].retailer == TIENDA_PRUEBA == "tienda-prueba"
    assert SUCURSAL_PRUEBA == "tp-cv"
    assert config.stores[SUCURSAL_PRUEBA_2].retailer == TIENDA_PRUEBA_2
    cadenas = {
        config.retailers[config.stores[s].retailer].chain
        for s in (SUCURSAL_PRUEBA, SUCURSAL_PRUEBA_2)
    }
    assert len(cadenas) == 2
    assert config.retailers[TIENDA_PRUEBA_2].domains == (DOMINIO_PRUEBA_2,)
    assert DOMINIO_PRUEBA_2.endswith(".example.com")
    # Los fixtures anteriores no cambian: mismas sucursales, mismos comercios más los nuevos.
    viejo = CONFIG.contenido
    assert set(viejo.stores) == set(config.stores) - {SUCURSAL_PRUEBA, SUCURSAL_PRUEBA_2}
    assert set(viejo.retailers) == set(config.retailers) - {TIENDA_PRUEBA_2}
    assert CONFIG.sha256 == configuracion_con_tienda_prueba().sha256


# --- 34: tuplas dentro de un valor Any (evidence) ---------------------------------------------


def test_34_las_tuplas_de_la_evidencia_se_vuelven_listas_y_hacen_ida_y_vuelta():
    evidencia = {"lista": (1, ("x", None)), "mapa": {"t": (True, Decimal("2.5"))}}
    observacion = _observacion(evidence=evidencia)
    assert observacion.evidence == {
        "lista": [1, ["x", None]],
        "mapa": {"t": [True, Decimal("2.5")]},
    }
    contexto = _contexto(
        oferta=ObservacionRegistrada(observacion, UUID(int=10), UUID(int=11), UUID(int=12))
    )
    leido = ContextoEvaluacion.desde_json(contexto.a_json())
    assert leido == contexto
    assert leido.a_json() == contexto.a_json()
    registro = _registro(entrada=contexto)
    assert RegistroEvaluacion.desde_json(registro.a_json()) == registro


# --- 36: pruebas renombradas (DEC-245) --------------------------------------------------------


def test_36_las_pruebas_de_content_del_particular_citan_dec245():
    raiz = Path(__file__).parent
    contrato = (raiz / "test_contrato.py").read_text(encoding="utf-8")
    decisiones = (raiz / "test_t03_tester_decisiones.py").read_text(encoding="utf-8")
    viejos = (
        "test_el_particular_conserva_content_mientras_se_resuelve_rn_013",
        "test_dec236_content_del_particular_se_conserva_pendiente_de_jesus",
    )
    for texto in (contrato, decisiones):
        assert not any(v in texto for v in viejos)
    for texto, nombre in (
        (contrato, "test_el_particular_conserva_content_dec245"),
        (decisiones, "test_dec245_content_del_particular_se_conserva"),
    ):
        cuerpo = texto.split(f"def {nombre}():", 1)[1].split("\ndef ", 1)[0]
        assert "DEC-245" in cuerpo and "pendiente" not in cuerpo.lower()
