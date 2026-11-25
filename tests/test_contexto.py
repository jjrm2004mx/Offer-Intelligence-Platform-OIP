"""Pruebas de T04 4.1: ``ContextoEvaluacion`` y ``RegistroEvaluacion`` con su serialización
canónica (CMP-09, CTR-06, RNF-3; design.md §12 "Contexto: ida y vuelta de la serialización").

Sin escenarios propios (tasks.md T04). Fixtures sintéticos; las URL son de example.com y
ninguna prueba las abre.
"""

from __future__ import annotations

import ast
import dataclasses
import datetime as dt
import json
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

import oip.evaluacion
from config_tienda_prueba import TIENDA_PRUEBA, configuracion_con_tienda_prueba
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
)
from oip.entradas.capturas import leer_captura
from oip.entradas.contrato import leer_observacion
from oip.evaluacion.contexto import (
    ContextoEvaluacion,
    Episodio,
    ErrorSerializacion,
    EvaluacionCanal,
    ObservacionRegistrada,
    ObservacionUsada,
    Referencias,
    RegistroEvaluacion,
)

RAIZ = Path(__file__).parent
# Desde T07 el paso 1 valida el dominio de la oferta: comercio sintético de example.com.
CONFIG = configuracion_con_tienda_prueba()
ZONA = "America/Tijuana"


def _uuid(n: int) -> UUID:
    return UUID(int=n)


def _observacion(**cambios):
    datos = {
        "retailerCode": TIENDA_PRUEBA,
        "storeCode": "hd-chula-vista",
        "productUrl": "https://tienda.example.com/p/123",
        "title": "Taladro de prueba",
        "brand": "MarcaP",
        "model": "MP-1",
        "gtin": "0123456789012",
        "category": "tools",
        "weightKg": Decimal("4.0"),
        "price": {"current": "29.00", "was": "129.00", "currency": "USD"},
        "seller": "comercio",
        "condition": "new",
        "availability": {"state": "in_stock", "quantity": 3, "scope": "store"},
        "isClearance": True,
        "purchaseMode": "tienda",
        "taxLocation": "chula_vista",
        "extractedAt": "2026-11-16T10:00:00-08:00",
        "blocked": False,
        "evidence": {"precio": Decimal("29.00"), "lista": [1, "x", None, True]},
    }
    datos.update(cambios)
    return leer_observacion(datos)


def _registrada(n: int, **cambios) -> ObservacionRegistrada:
    return ObservacionRegistrada(_observacion(**cambios), _uuid(n), _uuid(100), _uuid(200))


def _ficha(n: int) -> ObservacionRegistrada:
    return _registrada(
        n,
        retailerCode="amazon",
        storeCode=None,
        productUrl="https://amazon.example.com/dp/X",
        price={"current": "105.00"},
        purchaseMode="envio",
        amazonListing={"buyBoxPrice": "105.00", "sellersNew": 4, "rankMain": 12000},
        extractedAt="2026-11-15T12:30:00.123456+00:00",
    )


def _contexto(**cambios) -> ContextoEvaluacion:
    base = {
        "id_evaluacion": _uuid(1),
        "instante": dt.datetime(2026, 11, 16, 12, 0, tzinfo=dt.timezone(dt.timedelta(hours=-8))),
        "configuracion": CONFIG,
        "id_version_configuracion": 7,
        "oferta": _registrada(10),
        "historial": (_registrada(11, price={"current": "119.00"}), _registrada(12)),
        "fichas_amazon": (_ficha(20),),
        "comparables": (
            leer_captura(
                "local_comparable",
                {
                    "gtin": "0123456789012",
                    "condition": "used",
                    "askingPrice": "1500.00",
                    "currency": "MXN",
                    "exchangeRate": "17.25",
                    "city": "tijuana",
                    "date": "2026-11-10",
                    "sold": False,
                },
            ),
        ),
        "estimados": (
            leer_captura(
                "local_estimate", {"gtin": "0123456789012", "price": "90.00", "date": "2026-11-01"}
            ),
        ),
        "msrp": (
            leer_captura(
                "msrp",
                {
                    "gtin": "0123456789012",
                    "value": "149.00",
                    "source": "fabricante",
                    "date": "2026-10-01",
                },
            ),
        ),
        "demanda_local": (
            leer_captura(
                "local_demand", {"category": "tools", "level": "medium", "date": "2026-11-01"}
            ),
        ),
        "id_evaluacion_anterior": _uuid(2),
        "referencias_cambiadas": (ReferenciaPrecio.PRECIO_MERCADO_HOY,),
        "id_carga": _uuid(3),
    }
    base.update(cambios)
    return ContextoEvaluacion(**base)


def _canal(**cambios) -> EvaluacionCanal:
    base = {
        "canal": Canal.LOCAL,
        "estado": EstadoCanal.DISPONIBLE,
        "precio_venta": Decimal("76.61"),
        "margen_neto": Decimal("30.12"),
        "margen_neto_pct": Decimal("75.63157894736842105263157895"),
        "unidades": 3,
        "dias_para_recuperar": 51,
        "nivel": Nivel.MUY_RECOMENDABLE,
        "nivel_calculado": Nivel.MUY_RECOMENDABLE,
        "ganancia_total": Decimal("100.58"),
    }
    base.update(cambios)
    return EvaluacionCanal(**base)


def _registro(**cambios) -> RegistroEvaluacion:
    contexto = cambios.pop("entrada", None) or _contexto()
    base = {
        "id": contexto.id_evaluacion,
        "evaluado_en": contexto.instante,
        "id_observacion_oferta": contexto.oferta.id,
        "id_publicacion": contexto.oferta.id_publicacion,
        "id_producto": contexto.oferta.id_producto,
        "id_version_configuracion": 7,
        "versiones_rn": contexto.versiones_rn,
        "resultado": Resultado.NIVEL_ASIGNADO,
        "motivo_principal": None,
        "motivos": (),
        "motivo_rechazo": None,
        "marcas": ("SIN OFERTA HOY", "ESTIMADO (peso)"),
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
        "descuento_real": Decimal("75.63025210084033613445378151"),
        "costo_compra": Decimal("31.25"),
        "canal_elegido": Canal.LOCAL,
        "nivel_aviso": Nivel.MUY_RECOMENDABLE,
        "canal_aviso": Canal.LOCAL,
        "canales": (
            _canal(
                canal=Canal.AMAZON,
                estado=EstadoCanal.CERRADO,
                causas_cerrado=(CausaCanalCerrado.SIN_ROTACION,),
                nivel=None,
                nivel_calculado=None,
                unidades=None,
            ),
            _canal(),
        ),
        "observaciones_usadas": (
            ObservacionUsada(_uuid(11), dt.datetime(2026, 11, 1, 8, tzinfo=dt.UTC)),
        ),
        "entrada": contexto,
        "id_evaluacion_anterior": contexto.id_evaluacion_anterior,
        "referencias_cambiadas": contexto.referencias_cambiadas,
        "id_carga": contexto.id_carga,
    }
    base.update(cambios)
    return RegistroEvaluacion(**base)


# --- Ida y vuelta (RNF-3) -------------------------------------------------------------------


def test_ida_y_vuelta_del_contexto_da_un_contexto_igual_y_el_mismo_texto():
    contexto = _contexto()
    texto = contexto.a_json()
    leido = ContextoEvaluacion.desde_json(texto)
    assert leido == contexto
    assert leido.a_json().encode("utf-8") == texto.encode("utf-8")
    # Desde bytes, igual.
    assert ContextoEvaluacion.desde_json(texto.encode("utf-8")) == contexto


def test_las_fechas_del_dominio_quedan_en_utc_al_construir():
    contexto = _contexto()
    assert contexto.instante.tzinfo is dt.UTC
    assert contexto.instante == dt.datetime(2026, 11, 16, 20, 0, tzinfo=dt.UTC)
    leido = ContextoEvaluacion.desde_json(contexto.a_json())
    assert leido.instante.tzinfo is contexto.instante.tzinfo
    assert _registro().evaluado_en.tzinfo is dt.UTC


def test_ida_y_vuelta_del_contexto_minimo():
    contexto = _contexto(
        historial=(),
        fichas_amazon=(),
        comparables=(),
        estimados=(),
        msrp=(),
        demanda_local=(),
        id_evaluacion_anterior=None,
        referencias_cambiadas=(),
        id_carga=None,
        id_version_configuracion=None,
    )
    texto = contexto.a_json()
    assert ContextoEvaluacion.desde_json(texto) == contexto
    assert ContextoEvaluacion.desde_json(texto).a_json() == texto


def test_ida_y_vuelta_conserva_la_configuracion_y_las_versiones_de_rn():
    leido = ContextoEvaluacion.desde_json(_contexto().a_json())
    assert leido.configuracion.contenido == CONFIG.contenido
    assert leido.configuracion.sha256 == CONFIG.sha256
    assert leido.configuracion.version == CONFIG.version
    assert dict(leido.versiones_rn) == dict(CONFIG.contenido.general.rn_versions)
    assert leido.versiones_rn["RN-012"] == 1


def test_ida_y_vuelta_conserva_la_evidencia_con_sus_tipos():
    leido = ContextoEvaluacion.desde_json(_contexto().a_json())
    evidencia = leido.oferta.observacion.evidence
    assert evidencia == {"precio": Decimal("29.00"), "lista": [1, "x", None, True]}
    assert isinstance(evidencia["precio"], Decimal)


def test_ida_y_vuelta_del_registro_da_un_registro_igual_y_el_mismo_texto():
    registro = _registro()
    texto = registro.a_json()
    leido = RegistroEvaluacion.desde_json(texto)
    assert leido == registro
    assert leido.a_json().encode("utf-8") == texto.encode("utf-8")


def test_el_registro_lleva_el_contexto_completo_como_entrada():
    registro = _registro()
    datos = json.loads(registro.a_json())
    assert datos["entrada"] == json.loads(registro.entrada.a_json())
    assert datos["id_version_configuracion"] == 7


def test_la_serializacion_es_estable_entre_objetos_iguales_construidos_aparte():
    assert _contexto().a_json() == _contexto().a_json()
    assert _registro().a_json() == _registro().a_json()


# --- Forma canónica (CTR-06) ----------------------------------------------------------------


def test_json_canonico_claves_ordenadas_y_separadores_fijos():
    texto = _registro().a_json()
    datos = json.loads(texto)
    assert texto == json.dumps(datos, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    assert "\n" not in texto


def test_decimales_como_texto_sin_redondear():
    datos = json.loads(_registro().a_json())
    assert datos["costo_compra"] == "31.25"
    assert datos["descuento_real"] == "75.63025210084033613445378151"
    assert datos["referencias"]["precio_habitual"] == "119"
    assert datos["referencias"]["episodio"]["valor_congelado"] == "120.5"
    canal_local = datos["canales"][1]
    assert canal_local["margen_neto_pct"] == "75.63157894736842105263157895"
    assert canal_local["unidades"] == 3
    oferta = datos["entrada"]["oferta"]["observacion"]
    assert oferta["price"]["current"] == "29.00"
    assert oferta["weightKg"] == "4.0"
    # Ningún número JSON con punto en todo el texto.
    json.loads(_registro().a_json(), parse_float=lambda _: pytest.fail("número con punto"))


def test_un_decimal_con_exponente_sale_en_notacion_fija():
    referencias = Referencias(precio_mercado_hoy=Decimal("1E+2"), msrp=Decimal("1.50E-3"))
    datos = json.loads(referencias.a_json())
    assert datos["precio_mercado_hoy"] == "100"
    assert datos["msrp"] == "0.00150"
    assert Referencias.desde_json(referencias.a_json()) == referencias


def test_fechas_en_utc_con_z_y_enums_por_su_codigo():
    datos = json.loads(_registro().a_json())
    assert datos["evaluado_en"] == "2026-11-16T20:00:00Z"
    entrada = datos["entrada"]
    assert entrada["instante"] == "2026-11-16T20:00:00Z"
    assert entrada["oferta"]["observacion"]["extractedAt"] == "2026-11-16T18:00:00Z"
    assert entrada["fichas_amazon"][0]["observacion"]["extractedAt"] == (
        "2026-11-15T12:30:00.123456Z"
    )
    assert datos["referencias"]["episodio"]["inicio"] == "2026-11-01"
    assert datos["resultado"] == "NIVEL_ASIGNADO"
    assert datos["canales"][0]["causas_cerrado"] == ["SIN ROTACIÓN"]
    assert datos["identificacion"] == "confirmed"
    assert entrada["referencias_cambiadas"] == ["precio_mercado_hoy"]
    assert "SIN ROTACIÓN" in _registro().a_json()  # UTF-8 sin escapar


def test_todos_los_campos_salen_aunque_esten_vacios():
    datos = json.loads(Referencias().a_json())
    assert datos == {
        "precio_habitual": None,
        "fuente_precio_habitual": None,
        "episodio": None,
        "precio_mercado_hoy": None,
        "msrp": None,
        "minimo_60_dias_amazon": None,
        "precio_venta_amazon": None,
        "valor_referencia_usados": None,
    }


# --- Lectura estricta (DEC-238) -------------------------------------------------------------


def _con(texto: str, ruta: list[str | int], valor) -> str:
    datos = json.loads(texto)
    actual = datos
    for parte in ruta[:-1]:
        actual = actual[parte]
    actual[ruta[-1]] = valor
    return json.dumps(datos, ensure_ascii=False)


@pytest.mark.parametrize(
    ("ruta", "valor"),
    [
        (["canales", 1, "unidades"], True),  # booleano como entero
        (["canales", 1, "unidades"], "3"),  # texto como entero
        (["id_version_configuracion"], "7"),
        (["ya_no_recomendado"], 0),  # entero como booleano
        (["ya_no_recomendado"], "false"),
        (["costo_compra"], 31),  # número donde va texto decimal
        (["costo_compra"], "31.25 "),
        (["costo_compra"], "NaN"),
        (["costo_compra"], "3.125e1"),
        (["resultado"], "nivel_asignado"),  # código fuera del catálogo
        (["motivos"], "EVITAR"),  # texto donde va lista
        (["evaluado_en"], "2026-11-16T20:00:00+00:00"),  # sin Z
        (["evaluado_en"], "2026-11-16T12:00:00"),
        (["id"], "00000000000000000000000000000001"),  # UUID no canónico
        (["referencias", "episodio", "inicio"], "2026-11-01T00:00:00Z"),
    ],
)
def test_la_lectura_rechaza_conversiones_implicitas(ruta, valor):
    with pytest.raises(ErrorSerializacion):
        RegistroEvaluacion.desde_json(_con(_registro().a_json(), ruta, valor))


def test_la_lectura_rechaza_un_numero_con_punto_aunque_sea_entero():
    texto = _registro().a_json().replace('"unidades":3', '"unidades":3.0')
    with pytest.raises(ErrorSerializacion):
        RegistroEvaluacion.desde_json(texto)


def test_la_lectura_rechaza_claves_faltantes_sobrantes_y_repetidas():
    datos = json.loads(_registro().a_json())
    sin_clave = dict(datos)
    del sin_clave["marcas"]
    with pytest.raises(ErrorSerializacion):
        RegistroEvaluacion.desde_json(json.dumps(sin_clave))
    with pytest.raises(ErrorSerializacion):
        RegistroEvaluacion.desde_json(json.dumps({**datos, "otro": 1}))
    texto = _registro().a_json()
    assert '"canal_aviso":' in texto
    repetida = texto.replace('"canal_aviso":', '"canal_aviso":"local","canal_aviso":', 1)
    with pytest.raises(ErrorSerializacion):
        RegistroEvaluacion.desde_json(repetida)
    with pytest.raises(ErrorSerializacion):
        RegistroEvaluacion.desde_json("no es json")


def test_el_error_de_lectura_no_cita_el_valor():
    with pytest.raises(ErrorSerializacion) as error:
        RegistroEvaluacion.desde_json(_con(_registro().a_json(), ["costo_compra"], "valor-secreto"))
    assert "valor-secreto" not in str(error.value)
    assert "costo_compra" in str(error.value)


# --- Construcción estricta (DEC-238, design.md §8) ------------------------------------------


@pytest.mark.parametrize(
    "cambios",
    [
        {"precio_venta": 76.61},  # float en un monto
        {"precio_venta": 76},  # entero donde va Decimal
        {"precio_venta": "76.61"},  # texto donde va Decimal
        {"precio_venta": Decimal("NaN")},
        {"unidades": True},  # booleano como entero
        {"unidades": Decimal("3")},
        {"nivel": "MUY_RECOMENDABLE"},  # texto en lugar del enum
        {"marcas": ["SIN OFERTA HOY"]},  # lista en lugar de tupla
        {"canal": "local"},
    ],
)
def test_la_construccion_rechaza_tipos_que_no_son_los_declarados(cambios):
    with pytest.raises(TypeError):
        _canal(**cambios)


def test_la_construccion_rechaza_fechas_sin_desfase_y_float_en_porcentajes():
    with pytest.raises(TypeError):
        ObservacionUsada(_uuid(1), dt.datetime(2026, 11, 1, 8))  # noqa: DTZ001
    with pytest.raises(TypeError):
        _contexto(instante=dt.datetime(2026, 11, 16, 12))  # noqa: DTZ001
    with pytest.raises(TypeError):
        _registro(descuento_real=75.6)
    with pytest.raises(TypeError):
        _contexto(id_version_configuracion=True)


def test_float_en_la_evidencia_no_se_serializa():
    observacion = _observacion(evidence={"x": 1.5})
    contexto = _contexto(oferta=ObservacionRegistrada(observacion, None, None, None))
    with pytest.raises(TypeError):
        contexto.a_json()


def test_las_observaciones_guardadas_llevan_sus_ids():
    sin_id = ObservacionRegistrada(_observacion(), None, _uuid(100), _uuid(200))
    with pytest.raises(ValueError, match="historial"):
        _contexto(historial=(sin_id,))
    with pytest.raises(ValueError, match="fichas_amazon"):
        _contexto(fichas_amazon=(sin_id,))
    # La oferta sí puede no tenerlos (una oferta rechazada no se guarda).
    assert _contexto(oferta=sin_id).oferta.id is None


def test_los_tipos_son_inmutables():
    contexto = _contexto()
    with pytest.raises(dataclasses.FrozenInstanceError):
        contexto.instante = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)  # type: ignore[misc]
    registro = _registro()
    with pytest.raises(TypeError):
        registro.versiones_rn["RN-001"] = 9  # type: ignore[index]


def test_vacio_equivale_a_ausente_en_las_colecciones_del_contexto():
    explicito = _contexto(historial=(), comparables=(), referencias_cambiadas=())
    por_defecto = ContextoEvaluacion(
        id_evaluacion=explicito.id_evaluacion,
        instante=explicito.instante,
        configuracion=CONFIG,
        id_version_configuracion=7,
        oferta=explicito.oferta,
        fichas_amazon=explicito.fichas_amazon,
        estimados=explicito.estimados,
        msrp=explicito.msrp,
        demanda_local=explicito.demanda_local,
        id_evaluacion_anterior=explicito.id_evaluacion_anterior,
        id_carga=explicito.id_carga,
    )
    assert por_defecto == explicito
    assert por_defecto.a_json() == explicito.a_json()


# --- Invariantes del registro (REQ §3.2.3, §3.2.4; design.md §10.6) -------------------------


def test_motivos_en_orden_canonico_y_sin_repetidos():
    _registro(
        resultado=Resultado.DESCARTADA,
        motivo_principal=Motivo.MERCADO_YA_BARATO,
        motivos=(Motivo.MERCADO_YA_BARATO, Motivo.VENDEDOR_EXTERNO),
        canal_elegido=None,
        nivel_aviso=None,
        canal_aviso=None,
    )
    with pytest.raises(ValueError, match="orden"):
        _registro(
            resultado=Resultado.DESCARTADA,
            motivo_principal=Motivo.VENDEDOR_EXTERNO,
            motivos=(Motivo.VENDEDOR_EXTERNO, Motivo.MERCADO_YA_BARATO),
            nivel_aviso=None,
            canal_aviso=None,
        )
    with pytest.raises(ValueError, match="orden"):
        _registro(
            resultado=Resultado.DESCARTADA,
            motivo_principal=Motivo.EVITAR,
            motivos=(Motivo.EVITAR, Motivo.EVITAR),
            nivel_aviso=None,
            canal_aviso=None,
        )


@pytest.mark.parametrize(
    "cambios",
    [
        # El principal no es el primero.
        {
            "resultado": Resultado.REVISION_MANUAL,
            "motivo_principal": Motivo.PARTICULAR,
            "motivos": (Motivo.VENDEDOR_EXTERNO, Motivo.PARTICULAR),
        },
        # Hay motivos y falta el principal.
        {
            "resultado": Resultado.REVISION_MANUAL,
            "motivo_principal": None,
            "motivos": (Motivo.PARTICULAR,),
        },
        # El resultado no sigue la precedencia.
        {
            "resultado": Resultado.REVISION_MANUAL,
            "motivo_principal": Motivo.EVITAR,
            "motivos": (Motivo.EVITAR, Motivo.PARTICULAR),
        },
        # Sin motivos no hay DESCARTADA.
        {"resultado": Resultado.DESCARTADA},
        # Motivo de rechazo fuera de RECHAZADA_VALIDACION.
        {"resultado": Resultado.SIN_NIVEL, "motivo_rechazo": "PRECIO INVÁLIDO"},
        # RECHAZADA_VALIDACION sin motivo de rechazo.
        {"resultado": Resultado.RECHAZADA_VALIDACION},
    ],
)
def test_el_registro_rechaza_motivos_y_resultados_incoherentes(cambios):
    base = {"nivel_aviso": None, "canal_aviso": None, "canal_elegido": None}
    with pytest.raises(ValueError):
        _registro(**{**base, **cambios})


def test_nivel_del_aviso_solo_con_nivel_asignado():
    with pytest.raises(ValueError, match="NIVEL_ASIGNADO"):
        _registro(resultado=Resultado.SIN_NIVEL)
    with pytest.raises(ValueError, match="NIVEL_ASIGNADO"):
        _registro(nivel_aviso=None)
    assert _registro(resultado=Resultado.SIN_NIVEL, nivel_aviso=None, canal_aviso=None)


def test_canales_uno_por_canal_en_orden():
    with pytest.raises(ValueError, match="canales"):
        _registro(canales=(_canal(), _canal(canal=Canal.AMAZON)))
    with pytest.raises(ValueError, match="canales"):
        _registro(canales=(_canal(), _canal()))


def test_el_repr_del_registro_no_incluye_la_entrada():
    texto = repr(_registro())
    assert "entrada" not in texto
    assert "evidence" not in texto


# --- Pureza de evaluacion/ (design.md §14) --------------------------------------------------

_PROHIBIDOS_IMPORT = (
    "oip.persistencia",
    "random",
    "secrets",
    "time",
    "socket",
    "urllib",
    "http",
    "requests",
    "httpx",
    "os",
)
_PROHIBIDOS_LLAMADA = ("now", "utcnow", "today", "localtime", "time", "uuid4", "uuid1", "open")


@pytest.mark.parametrize(
    "archivo",
    sorted(Path(oip.evaluacion.__file__).parent.rglob("*.py")),
    ids=lambda p: p.name,
)
def test_evaluacion_no_importa_persistencia_ni_usa_reloj_ni_io(archivo):
    arbol = ast.parse(archivo.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            nombres = [a.name for a in nodo.names]
        elif isinstance(nodo, ast.ImportFrom):
            nombres = [nodo.module or ""]
        else:
            nombres = []
        for nombre in nombres:
            assert not any(nombre == p or nombre.startswith(p + ".") for p in _PROHIBIDOS_IMPORT), (
                nombre
            )
        if isinstance(nodo, ast.Call):
            funcion = nodo.func
            nombre = (
                funcion.attr if isinstance(funcion, ast.Attribute) else getattr(funcion, "id", "")
            )
            assert nombre not in _PROHIBIDOS_LLAMADA, nombre
