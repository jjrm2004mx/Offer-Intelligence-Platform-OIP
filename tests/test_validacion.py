"""Pruebas de T07: validación de cada observación, paso 1 de REQ §3.2 (CMP-07, CMP-17).

Escenarios B20 (a) a (h) con los datos y resultados de REQ-2026-0001 v2.9 §4 (B20), más
las pruebas unitarias del orden de design.md §6 cuando fallan dos comprobaciones a la vez,
de ``listed`` en el particular (REQ §6 punto 1; DEC-242) y de la comparación sintáctica de
la URL (design.md §16).

Fixtures sintéticos (``tests/fixtures/observaciones/``); los dominios de comercios y
plataformas solo aparecen en esos archivos y en la configuración. Las pruebas unitarias de
URL usan example.com. Ninguna prueba abre una URL: ``test_validar_no_usa_la_red`` lo
comprueba con la red bloqueada.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import logging
import socket
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from oip.catalogos import MotivoRechazo, Resultado
from oip.configuracion import cargar_configuracion
from oip.entradas.contrato import leer_observacion
from oip.entradas.validacion import (
    CAMPO_ESTADO,
    Validacion,
    motivo_de_rechazo,
    url_autorizada,
    validar,
)
from oip.evaluacion import motor
from oip.evaluacion.contexto import ContextoEvaluacion, ObservacionRegistrada

RAIZ = Path(__file__).parent
FIXTURES = RAIZ / "fixtures"
CONFIG = cargar_configuracion(FIXTURES / "config" / "base.yaml")
CONTENIDO = CONFIG.contenido

PRECIO_INVALIDO = "PRECIO INVÁLIDO"
DOMINIO_NO_AUTORIZADO = "DOMINIO NO AUTORIZADO"
CIUDAD_NO_CONFIGURADA = "CIUDAD NO CONFIGURADA"


def _faltante(campo: str) -> str:
    return f"CAMPO OBLIGATORIO FALTANTE ({campo})"


def _cargar(nombre: str) -> dict[str, Any]:
    texto = (FIXTURES / "observaciones" / nombre).read_text(encoding="utf-8")
    datos = json.loads(texto, parse_float=Decimal)
    datos.pop("_nota")
    return datos


_B18 = _cargar("b18_particular.json")
_COMERCIO = _cargar("b20_comercio.json")


def b18(**cambios: Any) -> dict[str, Any]:
    """La publicación de particular de B18 con ``cambios`` (``None`` quita el campo)."""
    return _aplicar(_B18, cambios)


def comercio(**cambios: Any) -> dict[str, Any]:
    """Observación de Home Depot válida con ``cambios`` (``None`` quita el campo)."""
    return _aplicar(_COMERCIO, cambios)


def _aplicar(base: dict[str, Any], cambios: dict[str, Any]) -> dict[str, Any]:
    datos = copy.deepcopy(base)
    for campo, valor in cambios.items():
        if valor is None:
            datos.pop(campo, None)
        else:
            datos[campo] = valor
    return datos


def _otra_url(datos: dict[str, Any], antes: str, despues: str) -> str:
    url = datos["productUrl"]
    assert antes in url
    return url.replace(antes, despues, 1)


def _contexto(datos: dict[str, Any]) -> ContextoEvaluacion:
    """Contexto con la oferta ya leída en forma (sin ids: aún no se guarda)."""
    return ContextoEvaluacion(
        id_evaluacion=UUID(int=1),
        instante=dt.datetime(2026, 11, 16, 12, 0, tzinfo=dt.UTC),
        configuracion=CONFIG,
        id_version_configuracion=1,
        oferta=ObservacionRegistrada(leer_observacion(datos), None, None, None),
    )


def _verificar_rechazo(datos: dict[str, Any], motivo: str) -> Validacion:
    validacion = validar(datos, CONTENIDO)
    assert validacion.resultado is Resultado.RECHAZADA_VALIDACION
    assert validacion.rechazada
    assert validacion.motivo_rechazo == motivo
    # Un rechazo no devuelve la observación: no se puede guardar en el historial (RNF-7).
    assert validacion.observacion is None
    return validacion


def _verificar_rechazo_del_motor(datos: dict[str, Any], motivo: str) -> None:
    registro = motor.evaluar(_contexto(datos))
    assert registro.resultado is Resultado.RECHAZADA_VALIDACION
    assert registro.motivo_rechazo == motivo
    assert registro.id_observacion_oferta is None
    assert registro.motivos == ()
    assert registro.motivo_principal is None
    assert registro.canales == ()


# --- Bases válidas ---------------------------------------------------------------------------


def test_las_bases_de_los_escenarios_son_validas():
    for datos in (b18(), comercio()):
        validacion = validar(datos, CONTENIDO)
        assert not validacion.rechazada
        assert validacion.resultado is None
        assert validacion.observacion is not None
        assert motivo_de_rechazo(validacion.observacion, CONTENIDO) is None
        assert motor.evaluar(_contexto(datos)).resultado is not Resultado.RECHAZADA_VALIDACION


# --- Escenarios B20 (REQ §4, B20; spec carga-y-validacion) -----------------------------------


@pytest.mark.scenario("B20 (a)")
def test_b20_a_precio_cero():
    datos = comercio(price={"current": "0.00", "currency": "USD"})
    _verificar_rechazo(datos, PRECIO_INVALIDO)
    _verificar_rechazo_del_motor(datos, PRECIO_INVALIDO)


@pytest.mark.scenario("B20 (b)")
def test_b20_b_url_de_otro_dominio_para_home_depot():
    datos = comercio(productUrl="https://ejemplo.com/p/sintetico-b20/100000001")
    _verificar_rechazo(datos, DOMINIO_NO_AUTORIZADO)
    _verificar_rechazo_del_motor(datos, DOMINIO_NO_AUTORIZADO)


@pytest.mark.scenario("B20 (c)")
def test_b20_c_sin_category():
    validacion = _verificar_rechazo(comercio(category=None), _faltante("category"))
    assert validacion.campo == "category"


@pytest.mark.scenario("B20 (d)")
def test_b20_d_particular_con_enlace_http():
    datos = b18()
    datos["productUrl"] = _otra_url(datos, "https://", "http://")
    _verificar_rechazo(datos, DOMINIO_NO_AUTORIZADO)
    _verificar_rechazo_del_motor(datos, DOMINIO_NO_AUTORIZADO)


@pytest.mark.scenario("B20 (e)")
def test_b20_e_particular_de_una_plataforma_fuera_de_la_lista():
    datos = b18(productUrl="https://plataforma.example.com/item/b18-sintetico")
    _verificar_rechazo(datos, DOMINIO_NO_AUTORIZADO)
    _verificar_rechazo_del_motor(datos, DOMINIO_NO_AUTORIZADO)


@pytest.mark.scenario("B20 (f)")
def test_b20_f_particular_sin_pickup_location():
    validacion = _verificar_rechazo(b18(pickupLocation=None), _faltante("pickupLocation"))
    assert validacion.campo == "pickupLocation"


@pytest.mark.scenario("B20 (g)")
def test_b20_g_particular_con_ciudad_fuera_de_la_lista():
    datos = b18(pickupLocation="ciudad_no_configurada")
    assert "ciudad_no_configurada" not in CONTENIDO.private_sellers.cities
    _verificar_rechazo(datos, CIUDAD_NO_CONFIGURADA)
    _verificar_rechazo_del_motor(datos, CIUDAD_NO_CONFIGURADA)


@pytest.mark.scenario("B20 (h)")
def test_b20_h_particular_sin_model():
    validacion = _verificar_rechazo(b18(model=None), _faltante("model"))
    assert validacion.campo == "model"


# --- Vacío = ausente --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("datos", "campo"),
    [
        (comercio(category=""), "category"),
        (comercio(productUrl="   "), "productUrl"),
        (b18(pickupLocation=""), "pickupLocation"),
        (b18(pickupLocation="  "), "pickupLocation"),
        (b18(brand=""), "brand"),
        (b18(model=" "), "model"),
    ],
)
def test_un_campo_vacio_cuenta_como_faltante(datos, campo):
    _verificar_rechazo(datos, _faltante(campo))


# --- Orden de design.md §6 cuando fallan dos a la vez ------------------------------------------


@pytest.mark.parametrize(
    ("datos", "motivo"),
    [
        # Obligatorio del contrato antes que obligatorio del particular.
        (b18(category=None, pickupLocation=None), _faltante("category")),
        (b18(category=None, model=None), _faltante("category")),
        # Obligatorios del particular en su orden: pickupLocation, brand, model.
        (b18(pickupLocation=None, brand=None, model=None), _faltante("pickupLocation")),
        (b18(brand=None, model=None), _faltante("brand")),
        # Obligatorio (contrato o particular) antes que el precio.
        (comercio(category=None, price={"current": "0.00"}), _faltante("category")),
        (b18(model=None, price={"current": "0"}), _faltante("model")),
        (b18(pickupLocation=None, price={"current": "-1"}), _faltante("pickupLocation")),
        # Precio antes que el dominio.
        (
            comercio(price={"current": "0.00"}, productUrl="https://ejemplo.com/p/1"),
            PRECIO_INVALIDO,
        ),
        (
            b18(price={"current": "70.001"}, productUrl="https://plataforma.example.com/i/1"),
            PRECIO_INVALIDO,
        ),
        # Dominio antes que la ciudad.
        (
            b18(
                productUrl="https://plataforma.example.com/i/1",
                pickupLocation="ciudad_no_configurada",
            ),
            DOMINIO_NO_AUTORIZADO,
        ),
        # Precio antes que la ciudad.
        (b18(price={"current": "0"}, pickupLocation="ciudad_no_configurada"), PRECIO_INVALIDO),
    ],
)
def test_el_primer_fallo_en_el_orden_de_design_6_es_el_motivo(datos, motivo):
    _verificar_rechazo(datos, motivo)


def test_enlace_http_y_ciudad_fuera_de_la_lista_da_dominio():
    datos = b18(pickupLocation="ciudad_no_configurada")
    datos["productUrl"] = _otra_url(datos, "https://", "http://")
    _verificar_rechazo(datos, DOMINIO_NO_AUTORIZADO)
    _verificar_rechazo_del_motor(datos, DOMINIO_NO_AUTORIZADO)


# --- Precio -----------------------------------------------------------------------------------


@pytest.mark.parametrize("precio", ["0", "0.00", "-0.01", "-70.00", "70.001", "0.005", "abc"])
def test_precio_invalido(precio):
    _verificar_rechazo(comercio(price={"current": precio, "currency": "USD"}), PRECIO_INVALIDO)


@pytest.mark.parametrize("precio", ["0.01", "70", "70.0", "70.00", Decimal("70.10"), 70])
def test_precio_valido_con_dos_decimales_como_maximo(precio):
    assert not validar(comercio(price={"current": precio}), CONTENIDO).rechazada


def test_precio_float_no_se_acepta_como_numero():
    # Un float no se lee como monto (design.md §8): queda para PRECIO INVÁLIDO.
    _verificar_rechazo(comercio(price={"current": 70.5}), PRECIO_INVALIDO)


# --- listed en el particular (REQ §6 punto 1; DEC-242) -----------------------------------------


@pytest.mark.parametrize("estado", ["in_stock", "limited_stock", "out_of_stock"])
def test_particular_con_estado_distinto_de_listed_se_rechaza(estado):
    datos = b18(availability={"state": estado})
    validacion = _verificar_rechazo(datos, _faltante(CAMPO_ESTADO))
    assert validacion.campo == CAMPO_ESTADO
    _verificar_rechazo_del_motor(datos, _faltante(CAMPO_ESTADO))


def test_listed_va_en_la_posicion_de_availability():
    # availability va antes que los obligatorios del particular y que el precio...
    _verificar_rechazo(
        b18(availability={"state": "in_stock"}, pickupLocation=None), _faltante(CAMPO_ESTADO)
    )
    _verificar_rechazo(
        b18(availability={"state": "in_stock"}, price={"current": "0"}), _faltante(CAMPO_ESTADO)
    )
    # ... y después de category (arquitectura §8).
    _verificar_rechazo(
        b18(availability={"state": "in_stock"}, category=None), _faltante("category")
    )


def test_un_comercio_no_necesita_listed():
    assert not validar(comercio(), CONTENIDO).rechazada


# --- Dominio del comercio (PAR-02; arquitectura §10) -------------------------------------------


def test_un_comercio_acepta_http():
    datos = comercio()
    datos["productUrl"] = _otra_url(datos, "https://", "http://")
    assert not validar(datos, CONTENIDO).rechazada


def test_un_comercio_acepta_su_dominio_sin_subdominio():
    datos = comercio()
    datos["productUrl"] = _otra_url(datos, "://www.", "://")
    assert not validar(datos, CONTENIDO).rechazada


def test_un_comercio_sin_configuracion_no_tiene_dominio_autorizado():
    datos = comercio(retailerCode="comercio-sin-configurar", storeCode=None)
    _verificar_rechazo(datos, DOMINIO_NO_AUTORIZADO)


def test_la_url_de_otro_comercio_configurado_no_vale():
    # El dominio debe ser el del comercio de la observación, no el de cualquiera.
    datos = comercio(retailerCode="walmart", storeCode=None)
    _verificar_rechazo(datos, DOMINIO_NO_AUTORIZADO)


def test_un_particular_no_vale_con_el_dominio_de_un_comercio():
    datos = b18(productUrl=_COMERCIO["productUrl"])
    _verificar_rechazo(datos, DOMINIO_NO_AUTORIZADO)


# --- Comparación sintáctica de la URL (design.md §16) ------------------------------------------

_DOMINIOS = ("example.com",)
_TODOS = ("http", "https")


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/p/1",
        "https://example.com",
        "https://www.example.com/p/1",
        "https://a.b.example.com/p/1",
        "HTTPS://Example.COM/p/1",
        "http://example.com/p/1?x=1#y",
    ],
)
def test_url_autorizada_host_igual_o_subdominio(url):
    assert url_autorizada(url, _DOMINIOS, esquemas=_TODOS)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.org/p/1",  # otro dominio
        "https://notexample.com/p/1",  # termina igual, pero no es subdominio
        "https://example.com.example.org/p/1",  # dominio como etiqueta de otro
        "https://example.com@example.org/p/1",  # credenciales: el host es otro
        "https://user@example.com/p/1",  # credenciales en la URL
        "https://example.com:8443/p/1",  # puerto explícito
        "https://example.com:abc/p/1",  # puerto inválido
        "https://example.com\\@example.org/p/1",  # barra invertida
        "https://exam ple.com/p/1",  # espacio
        "https://example.com/p/1\n",  # control
        "ftp://example.com/p/1",  # esquema
        "//example.com/p/1",  # sin esquema
        "example.com/p/1",  # relativa
        "https:///p/1",  # sin host
        "",
    ],
)
def test_url_no_autorizada(url):
    assert not url_autorizada(url, _DOMINIOS, esquemas=_TODOS)


def test_url_autorizada_respeta_el_esquema():
    assert url_autorizada("https://example.com/i/1", _DOMINIOS, esquemas=("https",))
    assert not url_autorizada("http://example.com/i/1", _DOMINIOS, esquemas=("https",))


@pytest.mark.parametrize(
    ("url", "esperado"),
    [
        ("https://example.com/marketplace", True),
        ("https://example.com/marketplace/", True),
        ("https://www.example.com/marketplace/item/1", True),
        ("https://example.com/marketplacex/item/1", False),
        ("https://example.com/groups/1", False),
        ("https://example.com/", False),
        ("https://example.com", False),
        ("https://example.com/MARKETPLACE/item/1", False),
    ],
)
def test_url_autorizada_con_prefijo_de_ruta(url, esperado):
    resultado = url_autorizada(url, _DOMINIOS, esquemas=("https",), prefijo_ruta="/marketplace")
    assert resultado is esperado


def test_plataforma_con_prefijo_de_ruta_en_la_configuracion():
    # PAR-09 de base.yaml: una plataforma con prefijo; el enlace sin el prefijo no vale.
    con_prefijo = [p for p in CONTENIDO.private_sellers.platforms.values() if p.path_prefix]
    assert con_prefijo
    plataforma = con_prefijo[0]
    dominio = plataforma.domains[0]
    valido = b18(productUrl=f"https://www.{dominio}{plataforma.path_prefix}/item/1")
    assert not validar(valido, CONTENIDO).rechazada
    fuera = b18(productUrl=f"https://www.{dominio}/groups/1")
    _verificar_rechazo(fuera, DOMINIO_NO_AUTORIZADO)


# --- Sin fugas, sin red, tipos estrictos -------------------------------------------------------

CENTINELA = "CENTINELA-T07-ZQX"


@pytest.mark.parametrize(
    "datos",
    [
        b18(pickupLocation=CENTINELA.lower().replace("-", "_")),
        b18(productUrl=f"https://{CENTINELA.lower()}.example.com/i/1"),
        b18(model=None, brand=CENTINELA),
        b18(availability={"state": "in_stock", "text": CENTINELA}),
        comercio(price={"current": "0", "currency": CENTINELA}),
        comercio(category=CENTINELA),
    ],
)
def test_el_rechazo_no_lleva_el_contenido_del_registro(datos, caplog):
    caplog.set_level(logging.DEBUG)
    validacion = validar(datos, CONTENIDO)
    assert validacion.rechazada
    for texto in (validacion.motivo_rechazo, str(validacion.campo), repr(validacion)):
        assert CENTINELA.lower() not in texto.lower()
        assert CENTINELA.lower().replace("-", "_") not in texto.lower()
    assert caplog.records == []


def test_validar_no_usa_la_red(monkeypatch):
    def _sin_red(*_args, **_kwargs):
        raise AssertionError("la validación no debe abrir conexiones ni resolver nombres")

    monkeypatch.setattr(socket, "socket", _sin_red)
    monkeypatch.setattr(socket, "getaddrinfo", _sin_red)
    monkeypatch.setattr(socket, "create_connection", _sin_red)
    assert not validar(b18(), CONTENIDO).rechazada
    assert not validar(comercio(), CONTENIDO).rechazada
    assert validar(comercio(productUrl="https://ejemplo.com/p/1"), CONTENIDO).rechazada


def test_validar_es_reproducible():
    datos = b18(pickupLocation="ciudad_no_configurada")
    assert validar(datos, CONTENIDO) == validar(copy.deepcopy(datos), CONTENIDO)


def test_validar_no_modifica_el_registro():
    datos = b18(availability={"state": "listed", "text": "texto libre"})
    original = copy.deepcopy(datos)
    validar(datos, CONTENIDO)
    assert datos == original


def test_tipos_estrictos():
    with pytest.raises(TypeError):
        validar(b18(), CONFIG)  # la versionada, no el contenido
    with pytest.raises(TypeError):
        validar([("retailerCode", "particular")], CONTENIDO)
    with pytest.raises(TypeError):
        motivo_de_rechazo(b18(), CONTENIDO)
    with pytest.raises(TypeError):
        motivo_de_rechazo(leer_observacion(b18()), CONFIG)


def test_validacion_lleva_la_observacion_o_el_motivo():
    observacion = leer_observacion(b18())
    with pytest.raises(ValueError):
        Validacion()
    with pytest.raises(ValueError):
        Validacion(observacion=observacion, motivo_rechazo=PRECIO_INVALIDO)
    assert "observacion" not in repr(Validacion(observacion=observacion))


def test_los_motivos_son_los_del_catalogo():
    assert PRECIO_INVALIDO == MotivoRechazo.PRECIO_INVALIDO.value
    assert DOMINIO_NO_AUTORIZADO == MotivoRechazo.DOMINIO_NO_AUTORIZADO.value
    assert CIUDAD_NO_CONFIGURADA == MotivoRechazo.CIUDAD_NO_CONFIGURADA.value


# --- Paso 1 del motor -------------------------------------------------------------------------


def test_el_motor_termina_en_el_paso_1(monkeypatch):
    llamados: list[str] = []
    pasos = []
    for paso in motor.PASOS:
        if paso is motor.validar:
            pasos.append(paso)
            continue

        def _espia(contexto, avance, _paso=paso):
            llamados.append(_paso.__name__)
            return _paso(contexto, avance)

        pasos.append(_espia)
    monkeypatch.setattr(motor, "PASOS", tuple(pasos))
    registro = motor.evaluar(_contexto(comercio(price={"current": "0"})))
    assert registro.resultado is Resultado.RECHAZADA_VALIDACION
    assert llamados == []
    motor.evaluar(_contexto(comercio()))
    assert len(llamados) == len(motor.PASOS) - 1


def test_el_motor_valida_contra_la_configuracion_del_contexto():
    # La misma oferta, válida en base.yaml, se rechaza si su ciudad no está en PAR-09.
    datos = b18(pickupLocation="tijuana")
    assert motor.evaluar(_contexto(datos)).resultado is not Resultado.RECHAZADA_VALIDACION
    sin_tijuana = dict(CONTENIDO.private_sellers.cities)
    del sin_tijuana["tijuana"]
    particulares = CONTENIDO.private_sellers.model_copy(update={"cities": sin_tijuana})
    contenido = CONTENIDO.model_copy(update={"private_sellers": particulares})
    assert motivo_de_rechazo(leer_observacion(datos), contenido) == CIUDAD_NO_CONFIGURADA
