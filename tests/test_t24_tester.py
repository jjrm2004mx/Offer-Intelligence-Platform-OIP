"""Pruebas independientes de oip-tester para T24 (endurecimiento de los tipos de T04).

Fuentes: tasks.md T24 (decisiones 12, 13, 15, 20, 23, 28, 34 y 36 del issue #34), design.md
§6 (CTR-06), §9 (catálogos: Marca, Dato estimado, causas por canal y su orden), §11 (RNF-3),
DEC-245, DEC-266, DEC-269 y DEC-238. T24 no tiene escenarios propios (los ejercitan T12 a
T22), así que estas pruebas no llevan marcador de escenario.

Los catálogos esperados se copian de design.md §9, no del código. Fixtures sintéticos: URL de
example.com que ninguna prueba abre; instante fijo, sin reloj, sin red y sin aleatoriedad.
"""

from __future__ import annotations

import ast
import datetime as dt
import itertools
import json
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
    con_sucursales_prueba,
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
from oip.entradas.validacion import motivo_de_rechazo
from oip.evaluacion.contexto import (
    ContextoEvaluacion,
    EvaluacionCanal,
    ObservacionRegistrada,
    Referencias,
    RegistroEvaluacion,
)

RAIZ = Path(__file__).resolve().parent
CONFIG = configuracion_con_tienda_prueba()
INSTANTE = dt.datetime(2026, 11, 16, 22, 0, tzinfo=dt.UTC)

# --- Catálogos de design.md §9 (copiados de la fuente, no del código) ----------------------

MARCAS_REQ = (
    "PRECIO ANTES INFLADO",
    "DESCUENTO ANUNCIADO NO COMPROBADO",
    "DEMANDA A LA BAJA",
    "COMPETENCIA MÁS BARATA",
    "SIN OFERTA HOY",
    "MATERIAL PELIGROSO",
    "REVISAR RETIROS",
    "SIN COMPARABLES LOCALES",
    "CONFIANZA BAJA",
    "MARGEN ESTIMADO",
    "EMPAQUE POR CONFIRMAR",
)
DATOS_ESTIMADO = ("peso", "devolución", "unidades")
CERRADO_AMAZON = (
    "SIN PRECIO DE VENTA EN AMAZON",
    "DEMANDA INSUFICIENTE EN AMAZON",
    "NO VENDIBLE EN AMAZON (POR AHORA)",
    "COMISIÓN DESCONOCIDA",
    "TASA DE DEVOLUCIÓN DESCONOCIDA",
    "ENVÍO POR COTIZAR",
    "PRODUCTO NO NUEVO",
    "SIN ROTACIÓN",
)
CERRADO_LOCAL = ("DEMANDA LOCAL BAJA", "SIN PRECIO LOCAL", "SIN ROTACIÓN")
POR_REVISAR = {Canal.AMAZON: ("DEMANDA DESCONOCIDA",), Canal.LOCAL: ("SIN REFERENCIA DE USADOS",)}
CERRADO = {Canal.AMAZON: CERRADO_AMAZON, Canal.LOCAL: CERRADO_LOCAL}
TODAS_LAS_MARCAS = (
    *MARCAS_REQ,
    *(f"ESTIMADO ({d})" for d in DATOS_ESTIMADO),
    *dict.fromkeys((*CERRADO_AMAZON, *CERRADO_LOCAL)),
)

# Texto vacío o solo de espacios (decisión 12): espacio, tabulador, saltos y otros blancos.
VACIOS = ["", " ", "   ", "\t", "\n", " \t\r\n ", "\u00a0", "\u2003"]


# --- Constructores sintéticos ------------------------------------------------------------


def _datos_observacion(**cambios) -> dict:
    datos = {
        "retailerCode": TIENDA_PRUEBA,
        "productUrl": "https://tienda.example.com/p/t24-tester",
        "title": "Lijadora sintetica T24",
        "category": "tools",
        "price": {"current": "35.00", "currency": "USD"},
        "seller": "comercio",
        "condition": "new",
        "availability": {"state": "in_stock"},
        "purchaseMode": "envio",
        "extractedAt": "2026-11-16T12:00:00-08:00",
        "blocked": False,
    }
    datos.update(cambios)
    return datos


def _oferta(**cambios) -> ObservacionRegistrada:
    return ObservacionRegistrada(
        leer_observacion(_datos_observacion(**cambios)),
        UUID(int=0x2410),
        UUID(int=0x2411),
        UUID(int=0x2412),
    )


def _contexto(**cambios) -> ContextoEvaluacion:
    base = {
        "id_evaluacion": UUID(int=0x2400),
        "instante": INSTANTE,
        "configuracion": CONFIG,
        "id_version_configuracion": 3,
        "oferta": _oferta(),
        "id_evaluacion_anterior": UUID(int=0x2401),
        "referencias_cambiadas": (
            ReferenciaPrecio.PRECIO_MERCADO_HOY,
            ReferenciaPrecio.PRECIO_HABITUAL,
        ),
        "id_carga": UUID(int=0x2402),
    }
    base.update(cambios)
    return ContextoEvaluacion(**base)


def _registro(entrada: ContextoEvaluacion | None = None, **cambios) -> RegistroEvaluacion:
    """Un registro SIN_NIVEL coherente con su entrada (lo que arma el motor)."""
    entrada = _contexto() if entrada is None else entrada
    base = {
        "id": entrada.id_evaluacion,
        "evaluado_en": entrada.instante,
        "id_observacion_oferta": entrada.oferta.id,
        "id_publicacion": entrada.oferta.id_publicacion,
        "id_producto": entrada.oferta.id_producto,
        "id_version_configuracion": entrada.id_version_configuracion,
        "versiones_rn": entrada.versiones_rn,
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
        "entrada": entrada,
        "id_evaluacion_anterior": entrada.id_evaluacion_anterior,
        "referencias_cambiadas": entrada.referencias_cambiadas,
        "id_carga": entrada.id_carga,
    }
    base.update(cambios)
    return RegistroEvaluacion(**base)


def _rechazado(motivo: str) -> RegistroEvaluacion:
    return _registro(
        resultado=Resultado.RECHAZADA_VALIDACION,
        id_observacion_oferta=None,
        motivo_rechazo=motivo,
    )


def _canal(canal: Canal = Canal.AMAZON, **cambios) -> EvaluacionCanal:
    base = {"canal": canal, "estado": EstadoCanal.DISPONIBLE}
    base.update(cambios)
    return EvaluacionCanal(**base)


# === 12: vacío = ausente (motivo_rechazo, marcas, fuente_precio_habitual) ==================


@pytest.mark.parametrize("vacio", VACIOS, ids=repr)
def test_12_motivo_de_rechazo_vacio_o_de_blancos_se_rechaza(vacio):
    assert _rechazado("PRECIO INVÁLIDO").motivo_rechazo == "PRECIO INVÁLIDO"
    assert _rechazado("CAMPO OBLIGATORIO FALTANTE (gtin)").resultado is (
        Resultado.RECHAZADA_VALIDACION
    )
    with pytest.raises(ValueError, match="motivo_rechazo: texto vacío"):
        _rechazado(vacio)


@pytest.mark.parametrize("vacio", VACIOS, ids=repr)
def test_12_una_marca_vacia_o_de_blancos_se_rechaza_en_el_registro_y_en_el_canal(vacio):
    marcas = ("MARGEN ESTIMADO", "EMPAQUE POR CONFIRMAR", vacio)
    with pytest.raises(ValueError, match=r"marcas\[2\]"):
        _registro(marcas=marcas)
    with pytest.raises(ValueError, match=r"marcas\[2\]"):
        _canal(marcas=marcas)
    with pytest.raises(ValueError, match=r"marcas\[0\]"):
        _canal(Canal.LOCAL, marcas=(vacio,))


@pytest.mark.parametrize("vacio", VACIOS, ids=repr)
def test_12_fuente_del_precio_habitual_vacia_o_de_blancos_se_rechaza(vacio):
    assert Referencias(fuente_precio_habitual=None).fuente_precio_habitual is None
    assert Referencias(fuente_precio_habitual="historial_propio").fuente_precio_habitual == (
        "historial_propio"
    )
    with pytest.raises(ValueError, match="fuente_precio_habitual: texto vacío"):
        Referencias(precio_habitual=Decimal("119"), fuente_precio_habitual=vacio)


def test_12_el_json_con_texto_vacio_tampoco_entra():
    """``desde_json`` construye el tipo: la misma regla vale al leer (CTR-06)."""
    referencias = Referencias(fuente_precio_habitual="historial_propio")
    datos = json.loads(referencias.a_json())
    datos["fuente_precio_habitual"] = " "
    with pytest.raises(ValueError, match="fuente_precio_habitual"):
        Referencias.desde_json(json.dumps(datos))
    canal = _canal(marcas=("MARGEN ESTIMADO",))
    datos = json.loads(canal.a_json())
    clave = next(k for k, v in datos.items() if v == ["MARGEN ESTIMADO"])
    datos[clave] = ["\t"]
    with pytest.raises(ValueError, match=r"marcas\[0\]"):
        EvaluacionCanal.desde_json(json.dumps(datos))


# === 13: el registro coincide con su entrada (CTR-06, RNF-3) ================================


OTRO_INSTANTE = INSTANTE + dt.timedelta(microseconds=1)


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("id", UUID(int=0x24FF)),
        ("evaluado_en", OTRO_INSTANTE),
        ("evaluado_en", INSTANTE - dt.timedelta(days=1)),
        ("versiones_rn", {}),
        ("versiones_rn", {**CONFIG.contenido.general.rn_versions, "RN-001": 99}),
        ("versiones_rn", {**CONFIG.contenido.general.rn_versions, "RN-999": 1}),
        ("id_evaluacion_anterior", None),
        ("id_evaluacion_anterior", UUID(int=0x24FE)),
        ("referencias_cambiadas", ()),
        # Las mismas referencias en otro orden no son las de la entrada.
        (
            "referencias_cambiadas",
            (ReferenciaPrecio.PRECIO_HABITUAL, ReferenciaPrecio.PRECIO_MERCADO_HOY),
        ),
        ("id_carga", None),
        ("id_carga", UUID(int=0x24FD)),
    ],
)
def test_13_cada_dato_distinto_del_de_la_entrada_se_rechaza(campo, valor):
    assert _registro().id == _contexto().id_evaluacion
    with pytest.raises(ValueError, match=f"^{campo}: distinto del de la entrada") as error:
        _registro(**{campo: valor})
    # El mensaje no copia valores (ni el de la entrada ni el del registro).
    assert str(UUID(int=0x2400)) not in str(error.value)


def test_13_sin_reevaluacion_ni_carga_el_registro_y_la_entrada_coinciden_en_vacio():
    entrada = _contexto(id_evaluacion_anterior=None, referencias_cambiadas=(), id_carga=None)
    registro = _registro(entrada)
    assert registro.id_evaluacion_anterior is None and registro.id_carga is None
    with pytest.raises(ValueError, match="id_carga: distinto"):
        _registro(entrada, id_carga=UUID(int=1))
    with pytest.raises(ValueError, match="referencias_cambiadas: distinto"):
        _registro(entrada, referencias_cambiadas=(ReferenciaPrecio.PRECIO_HABITUAL,))


def test_13_el_mismo_instante_en_otra_zona_y_las_versiones_como_dict_coinciden():
    tijuana = dt.timezone(dt.timedelta(hours=-8), "PST")
    registro = _registro(
        evaluado_en=INSTANTE.astimezone(tijuana),
        versiones_rn=dict(CONFIG.contenido.general.rn_versions),
    )
    assert registro.evaluado_en == INSTANTE and registro.evaluado_en.tzinfo is dt.UTC


def test_13_un_rechazado_tambien_exige_los_datos_de_su_entrada():
    with pytest.raises(ValueError, match="id: distinto"):
        _registro(
            resultado=Resultado.RECHAZADA_VALIDACION,
            id_observacion_oferta=None,
            motivo_rechazo="PRECIO INVÁLIDO",
            id=UUID(int=0x24FC),
        )


def test_13_un_json_con_el_input_snapshot_de_otra_evaluacion_no_se_lee():
    """Recalcular (T21) compara contra el registro guardado: un ``input_snapshot`` que no es
    el de su registro no llega a construirse (RNF-3)."""
    registro = _registro()
    assert RegistroEvaluacion.desde_json(registro.a_json()) == registro
    otro = _registro(_contexto(instante=OTRO_INSTANTE))
    datos = json.loads(registro.a_json())
    datos_otro = json.loads(otro.a_json())
    claves_entrada = [k for k in datos if datos[k] != datos_otro[k] and isinstance(datos[k], dict)]
    assert len(claves_entrada) == 1  # solo la entrada trae objetos que cambian
    datos[claves_entrada[0]] = datos_otro[claves_entrada[0]]
    with pytest.raises(ValueError, match="evaluado_en: distinto"):
        RegistroEvaluacion.desde_json(json.dumps(datos))


# === 15: marcas del catálogo (DEC-266) =====================================================


def test_15_el_catalogo_de_marcas_y_de_dato_estimado_es_el_de_design_md():
    assert tuple(m.value for m in Marca if m is not Marca.ESTIMADO) == MARCAS_REQ
    assert tuple(d.value for d in DatoEstimado) == DATOS_ESTIMADO
    assert tuple(marca_estimado(d) for d in DATOS_ESTIMADO) == (
        "ESTIMADO (peso)",
        "ESTIMADO (devolución)",
        "ESTIMADO (unidades)",
    )
    assert all(es_marca(m) for m in TODAS_LAS_MARCAS)


def test_15_el_registro_y_el_canal_aceptan_todas_las_marcas_del_catalogo_en_su_orden():
    al_reves = TODAS_LAS_MARCAS[::-1]
    assert _registro(marcas=al_reves).marcas == al_reves
    assert _canal(marcas=al_reves).marcas == al_reves
    assert _canal(Canal.LOCAL, marcas=TODAS_LAS_MARCAS).marcas == TODAS_LAS_MARCAS


@pytest.mark.parametrize(
    "marca",
    [
        "ESTIMADO",  # sin dato (DEC-266)
        "ESTIMADO ()",
        "ESTIMADO (color)",  # dato fuera del catálogo
        "ESTIMADO (Peso)",
        "ESTIMADO (devolucion)",  # sin acento
        "ESTIMADO (peso) ",
        "ESTIMADO  (peso)",
        "ESTIMADO(peso)",
        "ESTIMADO (peso, unidades)",
        "DEMANDA DESCONOCIDA",  # causa de por revisar (y motivo): no es marca
        "SIN REFERENCIA DE USADOS",  # causa de por revisar (y motivo): no es marca
        "SIN HISTORIAL SUFICIENTE",  # un motivo no es marca
        "PRECIO INVÁLIDO",  # un motivo de rechazo no es marca
        "margen estimado",
        "MARGEN ESTIMADO\n",
        "SIN ROTACION",  # sin acento
        "NO VENDIBLE EN AMAZON",  # sin "(POR AHORA)"
        "MARCA INVENTADA",
    ],
)
def test_15_una_marca_fuera_del_catalogo_se_rechaza_sin_copiarla_al_mensaje(marca):
    assert not es_marca(marca)
    with pytest.raises(ValueError, match=r"^marcas\[1\]: fuera del catálogo") as error:
        _registro(marcas=("CONFIANZA BAJA", marca))
    assert str(error.value) == "marcas[1]: fuera del catálogo de marcas (DEC-266)"
    with pytest.raises(ValueError, match=r"^marcas\[0\]: fuera del catálogo"):
        _canal(marcas=(marca, "MARGEN ESTIMADO"))
    with pytest.raises(ValueError, match=r"^marcas\[0\]: fuera del catálogo"):
        _canal(Canal.LOCAL, marcas=(marca,))


def test_15_una_marca_repetida_sigue_rechazada():
    with pytest.raises(ValueError, match="marcas: sin repetidos"):
        _registro(marcas=("ESTIMADO (peso)", "MARGEN ESTIMADO", "ESTIMADO (peso)"))
    with pytest.raises(ValueError, match="marcas: sin repetidos"):
        _canal(marcas=("SIN ROTACIÓN", "SIN ROTACIÓN"))


def test_15_una_marca_que_no_es_str_se_rechaza_por_su_tipo():
    """DEC-238: tipos estrictos; un miembro del enum no es el código (``str``)."""
    with pytest.raises(TypeError):
        _registro(marcas=(Marca.MARGEN_ESTIMADO,))
    assert not es_marca(Marca.MARGEN_ESTIMADO)  # type: ignore[arg-type]
    assert not es_marca(None)  # type: ignore[arg-type]


@pytest.mark.parametrize("dato", ["color", "Peso", "", "   ", "peso (2)"])
def test_15_marca_estimado_solo_con_un_dato_del_catalogo(dato):
    with pytest.raises(ValueError) as error:
        marca_estimado(dato)
    assert "color" not in str(error.value)


def test_15_el_json_con_una_marca_fuera_del_catalogo_no_se_lee():
    registro = _registro(marcas=("ESTIMADO (unidades)",))
    texto = registro.a_json()
    assert "ESTIMADO (unidades)" in texto
    with pytest.raises(ValueError, match=r"marcas\[0\]: fuera del catálogo"):
        RegistroEvaluacion.desde_json(texto.replace("ESTIMADO (unidades)", "ESTIMADO (color)"))


# === 20: fullmatch en la configuración ======================================================


def _base_texto() -> str:
    return con_tienda_prueba(BASE.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "escalar",
    [
        '!!int "12\\n"',  # entero con salto de línea final (tasks.md T24, punto 20)
        '!!int "60\\n"',
        '!!int "60\\n\\n"',
        '!!int "\\n60"',
        '!!int " 60"',
    ],
)
def test_20_un_entero_con_salto_de_linea_o_blancos_se_rechaza(escalar):
    texto = _base_texto()
    assert texto.count("usual_window_days: 60\n") == 1
    with pytest.raises(ErrorConfiguracion):
        cargar_configuracion_texto(
            texto.replace("usual_window_days: 60\n", f"usual_window_days: {escalar}\n")
        )


def test_20_un_entero_de_bloque_con_salto_final_se_rechaza_y_sin_el_salto_se_acepta():
    texto = _base_texto()
    bloque = texto.replace("usual_window_days: 60\n", "usual_window_days: !!int |\n      12\n", 1)
    with pytest.raises(ErrorConfiguracion):
        cargar_configuracion_texto(bloque)
    sin_salto = texto.replace(
        "usual_window_days: 60\n", "usual_window_days: !!int |-\n      12\n", 1
    )
    assert cargar_configuracion_texto(sin_salto).contenido.price_reference.usual_window_days == 12


def test_20_una_zona_con_salto_de_linea_final_se_rechaza():
    texto = _base_texto()
    assert texto.count("timezone: America/Tijuana ") == 1
    for malo in ('"America/Tijuana\\n"', '"America/Tijuana\\n\\n"', '"\\nAmerica/Tijuana"'):
        with pytest.raises(ErrorConfiguracion, match="timezone"):
            cargar_configuracion_texto(
                texto.replace("timezone: America/Tijuana ", f"timezone: {malo} ", 1)
            )
    bien = texto.replace("timezone: America/Tijuana ", 'timezone: "America/Tijuana" ', 1)
    assert cargar_configuracion_texto(bien).contenido == CONFIG.contenido


# === 23: causas en el orden del catálogo del canal (DEC-269) ================================


@pytest.mark.parametrize("canal", list(Canal))
def test_23_toda_combinacion_en_el_orden_del_catalogo_se_acepta(canal):
    catalogo = CERRADO[canal]
    for n in range(len(catalogo) + 1):
        for combinacion in itertools.combinations(catalogo, n):
            causas = tuple(CausaCanalCerrado(c) for c in combinacion)
            estado = EstadoCanal.CERRADO if causas else EstadoCanal.DISPONIBLE
            assert _canal(canal, estado=estado, causas_cerrado=causas).causas_cerrado == causas


@pytest.mark.parametrize("canal", list(Canal))
def test_23_cada_par_fuera_de_orden_se_rechaza(canal):
    catalogo = CERRADO[canal]
    for primera, segunda in itertools.combinations(catalogo, 2):
        causas = (CausaCanalCerrado(segunda), CausaCanalCerrado(primera))
        with pytest.raises(ValueError, match="^causas_cerrado: en el orden del catálogo"):
            _canal(canal, estado=EstadoCanal.CERRADO, causas_cerrado=causas)


def test_23_en_venta_local_el_orden_es_el_de_su_lista_no_el_del_enum():
    """design.md §9: local = DEMANDA LOCAL BAJA, SIN PRECIO LOCAL, SIN ROTACIÓN."""
    local = tuple(CausaCanalCerrado(c) for c in CERRADO_LOCAL)
    assert _canal(Canal.LOCAL, estado=EstadoCanal.CERRADO, causas_cerrado=local)
    with pytest.raises(ValueError, match="en el orden"):
        _canal(
            Canal.LOCAL,
            estado=EstadoCanal.CERRADO,
            causas_cerrado=(CausaCanalCerrado.SIN_ROTACION, CausaCanalCerrado.SIN_PRECIO_LOCAL),
        )


@pytest.mark.parametrize("canal", list(Canal))
def test_23_una_causa_de_otro_canal_se_rechaza(canal):
    otro = Canal.LOCAL if canal is Canal.AMAZON else Canal.AMAZON
    ajenas = [c for c in CERRADO[otro] if c not in CERRADO[canal]]
    assert ajenas
    for ajena in ajenas:
        with pytest.raises(ValueError, match="causas_cerrado: fuera del catálogo del canal"):
            _canal(canal, estado=EstadoCanal.CERRADO, causas_cerrado=(CausaCanalCerrado(ajena),))
    (ajena_por_revisar,) = POR_REVISAR[otro]
    with pytest.raises(ValueError, match="causas_por_revisar: fuera del catálogo del canal"):
        _canal(
            canal,
            estado=EstadoCanal.POR_REVISAR,
            causas_por_revisar=(CausaCanalPorRevisar(ajena_por_revisar),),
        )
    (propia,) = POR_REVISAR[canal]
    revisar = (CausaCanalPorRevisar(propia),)
    assert _canal(canal, estado=EstadoCanal.POR_REVISAR, causas_por_revisar=revisar)


def test_23_causas_repetidas_siguen_rechazadas():
    with pytest.raises(ValueError, match="causas_cerrado: sin repetidos"):
        _canal(
            estado=EstadoCanal.CERRADO,
            causas_cerrado=(CausaCanalCerrado.SIN_ROTACION, CausaCanalCerrado.SIN_ROTACION),
        )
    revisar = (CausaCanalPorRevisar.DEMANDA_DESCONOCIDA,) * 2
    with pytest.raises(ValueError, match="causas_por_revisar: sin repetidos"):
        _canal(estado=EstadoCanal.POR_REVISAR, causas_por_revisar=revisar)


def test_23_el_json_con_causas_fuera_de_orden_no_se_lee():
    causas = (CausaCanalCerrado.ENVIO_POR_COTIZAR, CausaCanalCerrado.SIN_ROTACION)
    canal = _canal(estado=EstadoCanal.CERRADO, causas_cerrado=causas)
    texto = canal.a_json()
    assert '["ENVÍO POR COTIZAR","SIN ROTACIÓN"]' in texto.replace(", ", ",")
    al_reves = texto.replace('"ENVÍO POR COTIZAR"', '"__X__"').replace(
        '"SIN ROTACIÓN"', '"ENVÍO POR COTIZAR"'
    )
    al_reves = al_reves.replace('"__X__"', '"SIN ROTACIÓN"')
    with pytest.raises(ValueError, match="en el orden"):
        EvaluacionCanal.desde_json(al_reves)


# --- Revisión 4: el motor siempre emite el orden y las marcas del catálogo -----------------
# Barrido de combinaciones que dan varias causas a la vez (categorías sin comisión, sin tasa,
# restringidas; usado; sin ficha, sin ventas, sin ranking; sin peso o por cotizar; demanda
# local baja). Usa los constructores sintéticos de las pruebas de T11 (B1).


def _barrido_del_motor():
    import test_t11_tester as t11  # constructores sintéticos de B1 (sin red)
    from oip.evaluacion import motor

    tools = "DEC-225)\n    subcategory_rank_required: false\n    initial_local_demand: "
    baja = t11._config((tools + "medium", tools + "low"))  # demanda local baja en ``tools``
    fichas = {
        "b1": t11._fichas_b1,
        "sin_fichas": list,
        "sin_ventas": lambda: t11._fichas_b1(comprados=0),
        "sin_ranking": lambda: t11._fichas_b1(rank_hoy=None, rank_hace_30=None),
        "muchos_vendedores": lambda: t11._fichas_b1(vendedores=500, comprados=10),
    }
    categorias = ("tools", "home_kitchen", "beauty", "watches", "video_game_consoles")
    for categoria, estado, ficha, peso, config in itertools.product(
        categorias, ("new", "used"), fichas, ("4.0", None, "10.0"), (t11.CONFIG, baja)
    ):
        oferta = t11._oferta_b1(peso=peso, extra={"category": categoria, "condition": estado})
        contexto = t11._contexto(oferta=oferta, fichas=fichas[ficha](), configuracion=config)
        yield motor.evaluar(contexto)
    # T20 (S-31): un usado sin valor de referencia deja la venta local por revisar, no con
    # SIN PRECIO LOCAL; la combinación de dos causas locales sale de un nuevo sin precio de
    # mercado hoy (sin historial ni fichas) y con demanda local baja.
    for categoria in categorias:
        oferta = t11._oferta_b1(extra={"category": categoria})
        contexto = t11._contexto(oferta=oferta, historial=[], fichas=[], configuracion=baja)
        yield motor.evaluar(contexto)


def test_revision_4_el_motor_emite_causas_en_orden_y_marcas_del_catalogo():
    vistas: set[tuple[str, tuple[str, ...]]] = set()
    for registro in _barrido_del_motor():
        assert all(es_marca(m) for m in registro.marcas)
        for canal in registro.canales:
            causas = tuple(c.value for c in canal.causas_cerrado)
            catalogo = CERRADO[canal.canal]
            assert list(causas) == sorted(causas, key=catalogo.index)
            assert all(es_marca(m) for m in canal.marcas)
            # Las causas de cerrado del canal también van como marcas del canal (§3.2.3).
            assert set(causas) <= set(canal.marcas)
            vistas.add((canal.canal.value, causas))
    # El barrido sí produjo combinaciones de varias causas en los dos canales.
    assert max(len(c) for k, c in vistas if k == "amazon") >= 5
    assert ("local", ("DEMANDA LOCAL BAJA",)) in vistas
    assert any(k == "local" and len(c) >= 2 for k, c in vistas)


# === 28: sucursales sintéticas por cadena ===================================================


def test_28_las_sucursales_sinteticas_son_de_dos_cadenas_distintas():
    config = configuracion_con_sucursales_prueba().contenido
    assert SUCURSAL_PRUEBA == "tp-cv"
    assert config.stores[SUCURSAL_PRUEBA].retailer == TIENDA_PRUEBA
    assert config.stores[SUCURSAL_PRUEBA_2].retailer == TIENDA_PRUEBA_2
    assert config.retailers[TIENDA_PRUEBA].chain != config.retailers[TIENDA_PRUEBA_2].chain
    assert config.retailers[TIENDA_PRUEBA_2].amazon_listing is False
    # Ningún dominio de los comercios sintéticos sale de example.com (DEC-194).
    for codigo in (TIENDA_PRUEBA, TIENDA_PRUEBA_2):
        for dominio in config.retailers[codigo].domains:
            assert dominio == "example.com" or dominio.endswith(".example.com")
    assert DOMINIO_PRUEBA_2 in config.retailers[TIENDA_PRUEBA_2].domains


def test_28_una_oferta_de_la_segunda_cadena_valida_con_su_dominio_y_no_con_el_otro():
    config = configuracion_con_sucursales_prueba().contenido
    buena = leer_observacion(
        _datos_observacion(
            retailerCode=TIENDA_PRUEBA_2,
            productUrl=f"https://{DOMINIO_PRUEBA_2}/p/t24",
            storeCode=SUCURSAL_PRUEBA_2,
            purchaseMode="tienda",
        )
    )
    assert motivo_de_rechazo(buena, config) is None
    dominio_1 = configuracion_con_tienda_prueba().contenido.retailers[TIENDA_PRUEBA].domains[0]
    ajena = leer_observacion(
        _datos_observacion(retailerCode=TIENDA_PRUEBA_2, productUrl=f"https://{dominio_1}/p/t24")
    )
    assert motivo_de_rechazo(ajena, config) == "DOMINIO NO AUTORIZADO"


def test_28_los_fixtures_anteriores_no_cambian():
    base = BASE.read_text(encoding="utf-8")
    viejo = con_tienda_prueba(base)
    nuevo = con_sucursales_prueba(base)
    # El texto anterior queda entero; lo nuevo solo agrega renglones.
    assert [r for r in viejo.splitlines() if r not in nuevo.splitlines()] == []
    agregados = [r for r in nuevo.splitlines() if r not in viejo.splitlines()]
    assert len(agregados) == 3
    assert all(TIENDA_PRUEBA in r for r in agregados)
    anterior = configuracion_con_tienda_prueba().contenido
    con_sucursales = configuracion_con_sucursales_prueba().contenido
    assert SUCURSAL_PRUEBA not in anterior.stores and TIENDA_PRUEBA_2 not in anterior.retailers
    for codigo, tienda in anterior.stores.items():
        assert con_sucursales.stores[codigo] == tienda
    for codigo, comercio in anterior.retailers.items():
        assert con_sucursales.retailers[codigo] == comercio
    # El archivo de los escenarios no cambia.
    assert "tp-cv" not in base and TIENDA_PRUEBA_2 not in base


# === 34: tuplas dentro de evidence (Any) ===================================================


def _sin_tuplas(valor) -> bool:
    if isinstance(valor, tuple):
        return False
    if isinstance(valor, list):
        return all(_sin_tuplas(v) for v in valor)
    if isinstance(valor, dict):
        return all(_sin_tuplas(v) for v in valor.values())
    return True


def test_34_las_tuplas_anidadas_de_evidence_se_vuelven_listas():
    evidencia = {
        "codigos": ("012345678905", ("A", ("B",))),
        "lista": [("x", 1), {"t": ()}],
        "mapa": {"m": {"n": (Decimal("1.5"), None, True)}},
        "simple": "sin tupla",
    }
    observacion = leer_observacion(_datos_observacion(evidence=evidencia))
    assert observacion.evidence == {
        "codigos": ["012345678905", ["A", ["B"]]],
        "lista": [["x", 1], {"t": []}],
        "mapa": {"m": {"n": [Decimal("1.5"), None, True]}},
        "simple": "sin tupla",
    }
    assert _sin_tuplas(observacion.evidence)
    # Igual a la misma evidencia escrita con listas (como llega de JSON Lines).
    con_listas = leer_observacion(
        _datos_observacion(evidence=json.loads(json.dumps(evidencia, default=str)))
    )
    assert con_listas.evidence["codigos"] == observacion.evidence["codigos"]
    assert leer_observacion(_datos_observacion(evidence=None)).evidence is None


def test_34_ida_y_vuelta_canonica_del_input_snapshot_con_tuplas_en_evidence():
    evidencia = {"capturas": (("foto", 1), ("foto", 2)), "nota": {"lote": ("a", "b")}}
    oferta = ObservacionRegistrada(
        leer_observacion(_datos_observacion(evidence=evidencia)),
        UUID(int=0x2410),
        UUID(int=0x2411),
        UUID(int=0x2412),
    )
    contexto = _contexto(oferta=oferta)
    texto = contexto.a_json()
    leido = ContextoEvaluacion.desde_json(texto)
    assert leido == contexto
    assert leido.a_json() == texto  # byte a byte (CTR-06)
    registro = _registro(contexto)
    vuelta = RegistroEvaluacion.desde_json(registro.a_json())
    assert vuelta == registro and vuelta.a_json() == registro.a_json()
    assert vuelta.entrada.oferta.observacion.evidence == {
        "capturas": [["foto", 1], ["foto", 2]],
        "nota": {"lote": ["a", "b"]},
    }


# === 36: pruebas renombradas (DEC-245), con las mismas aserciones ==========================

# Cuerpos (sin docstring) de las dos pruebas tal como estaban en main (a4f9f30).
_RENOMBRADAS = {
    "test_contrato.py": (
        "test_el_particular_conserva_content_dec245",
        "obs = leer_observacion({**PARTICULAR, 'content': 'tool only'})\n"
        "assert obs.content == 'tool only'",
    ),
    "test_t03_tester_decisiones.py": (
        "test_dec245_content_del_particular_se_conserva",
        "assert leer_observacion(_particular()).content == 'tool only'",
    ),
}
_NOMBRES_VIEJOS = (
    "test_el_particular_conserva_content_mientras_se_resuelve_rn_013",
    "test_dec236_content_del_particular_se_conserva_pendiente_de_jesus",
)


@pytest.mark.parametrize("archivo", sorted(_RENOMBRADAS))
def test_36_las_pruebas_renombradas_citan_dec245_y_conservan_sus_aserciones(archivo):
    nombre, cuerpo = _RENOMBRADAS[archivo]
    arbol = ast.parse((RAIZ / archivo).read_text(encoding="utf-8"))
    funciones = {n.name: n for n in arbol.body if isinstance(n, ast.FunctionDef)}
    assert nombre in funciones and "pendiente" not in nombre
    funcion = funciones[nombre]
    docstring = ast.get_docstring(funcion) or ""
    assert "DEC-245" in docstring and "pendiente" not in docstring.lower()
    sentencias = funcion.body[1:]  # sin el docstring
    assert "\n".join(ast.unparse(s) for s in sentencias) == cuerpo


def test_36_los_nombres_viejos_ya_no_estan_en_ninguna_prueba():
    for archivo in RAIZ.glob("test_*.py"):
        if archivo.name in (Path(__file__).name, "test_t24_endurecimiento.py"):
            continue  # las dos pruebas de T24 citan los nombres viejos para buscarlos
        texto = archivo.read_text(encoding="utf-8")
        assert not any(viejo in texto for viejo in _NOMBRES_VIEJOS), archivo.name


# === Seguridad: los mensajes nuevos no copian datos ========================================


def test_seguridad_los_mensajes_de_las_validaciones_nuevas_no_copian_el_texto():
    secreto = "Ana 555-0100"  # texto que nunca debe salir en un mensaje
    for construir in (
        lambda: _registro(marcas=(secreto,)),
        lambda: _canal(marcas=("MARGEN ESTIMADO", secreto)),
        lambda: marca_estimado(secreto),
    ):
        with pytest.raises(ValueError) as error:
            construir()
        assert secreto not in str(error.value) and "555" not in str(error.value)
    # ``entrada`` (el input_snapshot, con la oferta completa) no sale en el repr.
    assert "entrada=" not in repr(_registro(marcas=("MARGEN ESTIMADO",)))
