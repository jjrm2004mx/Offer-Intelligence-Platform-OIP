"""Pruebas independientes de oip-tester para T07: validación de cada observación (B20).

Fuentes: REQ-2026-0001 v2.9 §3.2 paso 1, §3.2.2, §4 (B20), §6 punto 1, §10 y §11;
design.md §2, §6 (orden de las comprobaciones), §7 (PAR-02, PAR-09), §11 (RNF-7) y §16;
DEC-212, DEC-227, DEC-236, DEC-238 y DEC-242. Los datos y los motivos esperados se copian
del REQ, no del código.

Los datos son sintéticos (``tests/fixtures/observaciones/t07_tester.json``). Los dominios
solo aparecen como texto en el fixture: ninguna prueba abre una URL ni sale a la red
(CLAUDE.md §2.1, DEC-194). Sin reloj de la máquina: el instante es fijo.
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

from oip.catalogos import Resultado
from oip.configuracion import cargar_configuracion
from oip.entradas._comun import RegistroInvalido
from oip.entradas.contrato import leer_observacion
from oip.entradas.validacion import motivo_de_rechazo, validar
from oip.evaluacion import motor
from oip.evaluacion.contexto import ContextoEvaluacion, ObservacionRegistrada

RAIZ = Path(__file__).parent
CONFIG = cargar_configuracion(RAIZ / "fixtures" / "config" / "base.yaml")
CONTENIDO = CONFIG.contenido

_FIXTURE = json.loads(
    (RAIZ / "fixtures" / "observaciones" / "t07_tester.json").read_text(encoding="utf-8"),
    parse_float=Decimal,
)
URL = _FIXTURE["urls"]

# --- Oráculos copiados del REQ (§3.2 paso 1 y B20) -----------------------------------------

RECHAZADA = "RECHAZADA_VALIDACION"
PRECIO_INVALIDO = "PRECIO INVÁLIDO"
DOMINIO_NO_AUTORIZADO = "DOMINIO NO AUTORIZADO"
CIUDAD_NO_CONFIGURADA = "CIUDAD NO CONFIGURADA"


def faltante(campo: str) -> str:
    return f"CAMPO OBLIGATORIO FALTANTE ({campo})"


INSTANTE = dt.datetime(2026, 11, 16, 20, 0, tzinfo=dt.UTC)

# --- Constructores -------------------------------------------------------------------------

_QUITAR = object()


def _con(base: dict[str, Any], **cambios: Any) -> dict[str, Any]:
    """Copia de ``base`` con ``cambios``; ``_QUITAR`` quita el campo. Acepta rutas con
    doble guion bajo para un campo anidado (``price__current``)."""
    datos = copy.deepcopy(base)
    for clave, valor in cambios.items():
        ruta = clave.split("__")
        destino = datos
        for parte in ruta[:-1]:
            destino = destino[parte]
        if valor is _QUITAR:
            destino.pop(ruta[-1], None)
        else:
            destino[ruta[-1]] = valor
    return datos


def comercio(**cambios: Any) -> dict[str, Any]:
    return _con(_FIXTURE["comercio_home_depot"], **cambios)


def particular(**cambios: Any) -> dict[str, Any]:
    """La publicación de particular de B18 (DEWALT DCF840 usado, San Diego, $70)."""
    return _con(_FIXTURE["particular_b18"], **cambios)


def _contexto(datos: dict[str, Any]) -> ContextoEvaluacion:
    return ContextoEvaluacion(
        id_evaluacion=UUID(int=7),
        instante=INSTANTE,
        configuracion=CONFIG,
        id_version_configuracion=1,
        oferta=ObservacionRegistrada(leer_observacion(datos), None, None, None),
    )


def _rechazo(datos: dict[str, Any]) -> str:
    """Motivo del paso 1 por ``validar``; verifica el resultado y que no se guarda."""
    entrada = copy.deepcopy(datos)
    v = validar(datos, CONTENIDO)
    assert datos == entrada, "la validación no debe modificar el registro"
    assert v.rechazada
    assert v.resultado is Resultado.RECHAZADA_VALIDACION
    assert v.resultado.value == RECHAZADA
    # REQ §3.2 paso 1 "y termina"; RNF-7: el rechazo no devuelve la observación.
    assert v.observacion is None
    return v.motivo_rechazo


def _rechazo_del_motor(datos: dict[str, Any]) -> str:
    """Motivo del paso 1 por el motor (CMP-17) con una oferta ya leída en forma."""
    r = motor.evaluar(_contexto(datos))
    assert r.resultado is Resultado.RECHAZADA_VALIDACION
    # "y termina": sin canales ni motivos de los pasos siguientes.
    assert r.canales == ()
    assert r.motivos == ()
    assert r.motivo_principal is None
    assert r.id_observacion_oferta is None
    return r.motivo_rechazo


def _valida(datos: dict[str, Any]) -> None:
    v = validar(datos, CONTENIDO)
    assert not v.rechazada, v.motivo_rechazo
    assert v.resultado is None
    assert v.observacion is not None


# --- Bases válidas -------------------------------------------------------------------------


def test_las_bases_sinteticas_son_validas():
    _valida(comercio())
    _valida(particular())
    assert motivo_de_rechazo(leer_observacion(comercio()), CONTENIDO) is None
    assert motivo_de_rechazo(leer_observacion(particular()), CONTENIDO) is None
    for datos in (comercio(), particular()):
        assert motor.evaluar(_contexto(datos)).resultado is not Resultado.RECHAZADA_VALIDACION


# --- Escenarios B20 (REQ §4) ---------------------------------------------------------------


@pytest.mark.scenario("B20 (a)")
def test_b20_a_precio_cero():
    datos = comercio(price={"current": "0.00", "currency": "USD"})
    assert _rechazo(datos) == PRECIO_INVALIDO
    assert _rechazo_del_motor(datos) == PRECIO_INVALIDO


@pytest.mark.scenario("B20 (b)")
def test_b20_b_url_de_ejemplo_com_para_home_depot():
    datos = comercio(productUrl="https://ejemplo.com/p/tester-t07/200000002")
    assert datos["retailerCode"] == "homedepot"
    assert _rechazo(datos) == DOMINIO_NO_AUTORIZADO
    assert _rechazo_del_motor(datos) == DOMINIO_NO_AUTORIZADO


@pytest.mark.scenario("B20 (c)")
def test_b20_c_sin_category():
    datos = comercio(category=_QUITAR)
    assert _rechazo(datos) == faltante("category")


@pytest.mark.scenario("B20 (d)")
def test_b20_d_particular_de_b18_con_enlace_http_de_offerup():
    datos = particular(productUrl=URL["offerup_http"])
    assert _rechazo(datos) == DOMINIO_NO_AUTORIZADO
    assert _rechazo_del_motor(datos) == DOMINIO_NO_AUTORIZADO


@pytest.mark.scenario("B20 (e)")
def test_b20_e_particular_con_https_de_plataforma_fuera_de_la_lista():
    datos = particular(productUrl="https://plataforma-no-permitida.example.com/item/b18")
    assert _rechazo(datos) == DOMINIO_NO_AUTORIZADO
    assert _rechazo_del_motor(datos) == DOMINIO_NO_AUTORIZADO


@pytest.mark.scenario("B20 (f)")
def test_b20_f_particular_de_b18_sin_pickup_location():
    datos = particular(pickupLocation=_QUITAR)
    assert _rechazo(datos) == faltante("pickupLocation")


@pytest.mark.scenario("B20 (g)")
def test_b20_g_particular_con_ciudad_que_no_esta_en_la_lista():
    datos = particular(pickupLocation="ensenada")
    assert "ensenada" not in CONTENIDO.private_sellers.cities
    assert _rechazo(datos) == CIUDAD_NO_CONFIGURADA
    assert _rechazo_del_motor(datos) == CIUDAD_NO_CONFIGURADA


@pytest.mark.scenario("B20 (h)")
def test_b20_h_particular_de_b18_sin_model():
    datos = particular(model=_QUITAR)
    assert _rechazo(datos) == faltante("model")


def test_b20_sin_brand_en_particular():
    # REQ §3.2 paso 1 y §11: brand también es obligatorio en el particular (DEC-227).
    assert _rechazo(particular(brand=_QUITAR)) == faltante("brand")


# --- Orden de las comprobaciones (design.md §6): el primer fallo es el motivo --------------


@pytest.mark.parametrize(
    ("datos", "esperado"),
    [
        # obligatorio del contrato antes que precio, dominio y ciudad
        (
            comercio(
                category=_QUITAR,
                price={"current": "0.00"},
                productUrl="https://ejemplo.com/p/1",
            ),
            faltante("category"),
        ),
        # orden de la arquitectura §8: productUrl antes que category
        (comercio(category=_QUITAR, productUrl=_QUITAR), faltante("productUrl")),
        # precio antes que dominio
        (
            comercio(price={"current": "0.00"}, productUrl="https://ejemplo.com/p/1"),
            PRECIO_INVALIDO,
        ),
        # obligatorio del particular antes que precio y enlace
        (
            particular(
                model=_QUITAR,
                price={"current": "0.00"},
                productUrl=URL["offerup_http"],
            ),
            faltante("model"),
        ),
        # obligatorios del particular en su orden: pickupLocation, brand, model
        (particular(pickupLocation=_QUITAR, model=_QUITAR), faltante("pickupLocation")),
        (particular(brand=_QUITAR, model=_QUITAR), faltante("brand")),
        # obligatorio del contrato antes que el del particular
        (particular(category=_QUITAR, pickupLocation=_QUITAR), faltante("category")),
        # precio antes que enlace y ciudad
        (
            particular(
                price={"current": "-5.00"},
                productUrl=URL["offerup_http"],
                pickupLocation="ensenada",
            ),
            PRECIO_INVALIDO,
        ),
        # enlace antes que ciudad (la d y la g a la vez)
        (
            particular(productUrl=URL["offerup_http"], pickupLocation="ensenada"),
            DOMINIO_NO_AUTORIZADO,
        ),
    ],
)
def test_orden_de_las_comprobaciones(datos, esperado):
    assert _rechazo(datos) == esperado


@pytest.mark.parametrize(
    ("datos", "esperado"),
    [
        (
            comercio(price={"current": "0.00"}, productUrl="https://ejemplo.com/p/1"),
            PRECIO_INVALIDO,
        ),
        (
            particular(productUrl=URL["offerup_http"], pickupLocation="ensenada"),
            DOMINIO_NO_AUTORIZADO,
        ),
        (
            particular(price={"current": "0.00"}, pickupLocation="ensenada"),
            PRECIO_INVALIDO,
        ),
    ],
)
def test_orden_en_el_motor(datos, esperado):
    assert _rechazo_del_motor(datos) == esperado


# --- availability.state del particular: listed (REQ §6 punto 1; DEC-242) -------------------

_OTROS_ESTADOS = ["in_stock_confirmed", "in_stock", "limited_stock", "unconfirmed", "out_of_stock"]


@pytest.mark.parametrize("estado", _OTROS_ESTADOS)
def test_particular_con_estado_distinto_de_listed(estado):
    datos = particular(availability={"state": estado})
    assert _rechazo(datos) == faltante("availability.state")
    assert _rechazo_del_motor(datos) == faltante("availability.state")


def test_particular_listed_es_valido():
    _valida(particular(availability={"state": "listed"}))


def test_particular_sin_estado_o_codigo_desconocido():
    assert _rechazo(particular(availability={})) == faltante("availability.state")
    assert _rechazo(particular(availability={"state": ""})) == faltante("availability.state")
    assert _rechazo(particular(availability={"state": "vendido"})) == faltante("availability.state")


@pytest.mark.parametrize(
    ("cambios", "esperado"),
    [
        # category (antes que availability en la arquitectura §8) gana
        ({"category": _QUITAR}, faltante("category")),
        # availability gana a los obligatorios del particular, al precio, al enlace y a la ciudad
        ({"pickupLocation": _QUITAR}, faltante("availability.state")),
        ({"model": _QUITAR}, faltante("availability.state")),
        ({"price": {"current": "0.00"}}, faltante("availability.state")),
        ({"productUrl": URL["offerup_http"]}, faltante("availability.state")),
        ({"pickupLocation": "ensenada"}, faltante("availability.state")),
        # extractedAt va después de availability
        ({"extractedAt": _QUITAR}, faltante("availability.state")),
    ],
)
def test_estado_no_listed_en_la_posicion_de_availability(cambios, esperado):
    datos = particular(availability={"state": "in_stock"}, **cambios)
    assert _rechazo(datos) == esperado


def test_comercio_con_listed_no_se_rechaza_por_el_estado():
    # DEC-242 solo aplica al particular; listed es un código válido de la 3.1.
    assert validar(comercio(availability={"state": "listed"}), CONTENIDO).motivo_rechazo != (
        faltante("availability.state")
    )


# --- Vacío = ausente (CTR-03) --------------------------------------------------------------


@pytest.mark.parametrize("vacio", ["", "   ", None])
@pytest.mark.parametrize(
    ("constructor", "campo"),
    [
        (comercio, "category"),
        (comercio, "productUrl"),
        (particular, "pickupLocation"),
        (particular, "brand"),
        (particular, "model"),
        (particular, "productUrl"),
    ],
)
def test_vacio_cuenta_como_ausente(constructor, campo, vacio):
    assert _rechazo(constructor(**{campo: vacio})) == faltante(campo)


# --- Precio: Decimal, > 0 y 2 decimales como máximo ----------------------------------------


@pytest.mark.parametrize(
    "precio", ["0", "0.00", "-0.01", "-70.00", "0.001", "70.005", "abc", Decimal("0")]
)
def test_precio_invalido(precio):
    assert _rechazo(comercio(price={"current": precio})) == PRECIO_INVALIDO
    assert _rechazo(particular(price={"current": precio})) == PRECIO_INVALIDO


@pytest.mark.parametrize("precio", ["0.01", "70", "70.0", "70.00", Decimal("70.00"), 70])
def test_precio_valido(precio):
    _valida(particular(price={"current": precio}))


def test_precio_float_nunca_se_acepta():
    # DEC-060: ningún monto pasa por float.
    assert _rechazo(comercio(price={"current": 45.5})) == PRECIO_INVALIDO


def test_el_precio_valido_queda_en_decimal_exacto():
    v = validar(particular(), CONTENIDO)
    actual = v.observacion.price.current
    assert type(actual) is Decimal
    assert actual == Decimal("70.00")


# --- Tipos estrictos (DEC-238) -------------------------------------------------------------


@pytest.mark.parametrize(
    ("cambios", "campo"),
    [
        ({"blocked": "false"}, "blocked"),
        ({"blocked": 0}, "blocked"),
        ({"availability__quantity": True}, "availability.quantity"),
        ({"availability__quantity": "5"}, "availability.quantity"),
    ],
)
def test_tipos_estrictos(cambios, campo):
    assert _rechazo(comercio(**cambios)) == faltante(campo)


# --- Dominio del comercio (PAR-02) ---------------------------------------------------------


@pytest.mark.parametrize("clave", ["home_depot_http", "home_depot_raiz", "home_depot_mayusculas"])
def test_url_de_comercio_autorizada(clave):
    # arquitectura §10: el comercio acepta http o https; host igual o subdominio.
    _valida(comercio(productUrl=URL[clave]))


def test_url_de_comercio_con_arroba_en_la_consulta_no_se_rechaza():
    _valida(comercio(productUrl="https://www.homedepot.com/p/1?ref=a@b"))


@pytest.mark.parametrize(
    "clave",
    [
        "home_depot_sufijo_falso",
        "home_depot_prefijo_falso",
        "home_depot_credenciales",
        "home_depot_puerto",
        "home_depot_barra_invertida",
        "home_depot_ftp",
        "walmart",
    ],
)
def test_url_de_comercio_no_autorizada(clave):
    assert _rechazo(comercio(productUrl=URL[clave])) == DOMINIO_NO_AUTORIZADO


def test_url_relativa_o_sin_host():
    for url in ("/p/1", "https:///p/1", "www.homedepot.com/p/1"):
        assert _rechazo(comercio(productUrl=url)) == DOMINIO_NO_AUTORIZADO


def test_comercio_sin_configuracion():
    assert _rechazo(comercio(retailerCode="comercio-inexistente")) == DOMINIO_NO_AUTORIZADO


def test_ficha_de_amazon_pasa_el_paso_1():
    datos = comercio(
        retailerCode="amazon",
        storeCode=_QUITAR,
        productUrl=URL["amazon_ficha"],
        purchaseMode="envio",
        amazonListing={"buyBoxPrice": "120.00", "sellersNew": 4, "rankMain": 9000},
    )
    _valida(datos)


# --- Enlace del particular (PAR-09; DEC-212) -----------------------------------------------


def test_particular_marketplace_dentro_del_prefijo():
    _valida(particular(productUrl=URL["marketplace_ok"]))


@pytest.mark.parametrize("clave", ["facebook_fuera_de_marketplace", "facebook_prefijo_pegado"])
def test_particular_facebook_fuera_del_prefijo(clave):
    assert _rechazo(particular(productUrl=URL[clave])) == DOMINIO_NO_AUTORIZADO


def test_particular_con_dominio_de_comercio():
    assert _rechazo(particular(productUrl=URL["home_depot_raiz"])) == DOMINIO_NO_AUTORIZADO


def test_particular_con_credenciales_o_puerto():
    for url in (
        "https://offerup.com@example.com/item/1",
        "https://offerup.com:444/item/1",
        "https://offerup.com/item/ 1",
    ):
        assert _rechazo(particular(productUrl=url)) == DOMINIO_NO_AUTORIZADO


def test_particular_ciudad_configurada_tijuana():
    _valida(particular(pickupLocation="tijuana"))


# --- Datos personales (R-20, RNF-7, DEC-181) -----------------------------------------------

_SECRETO_TEL = "619-555-0142"
_SECRETO_TEXTO = "llamar a Fulano por la tarde"


@pytest.mark.parametrize(
    "datos",
    [
        particular(pickupLocation=_QUITAR, sellerPhone=_SECRETO_TEL, description=_SECRETO_TEXTO),
        particular(
            pickupLocation="ciudad-" + _SECRETO_TEL,
            sellerPhone=_SECRETO_TEL,
            availability={"state": "listed", "text": _SECRETO_TEXTO},
        ),
        particular(
            productUrl="http://offerup.com/item/" + _SECRETO_TEL,
            evidence={"nota": _SECRETO_TEXTO},
        ),
        particular(
            availability={"state": "in_stock", "text": _SECRETO_TEXTO},
            sellerName=_SECRETO_TEXTO,
        ),
    ],
)
def test_el_rechazo_no_lleva_datos_del_renglon(datos, caplog):
    caplog.set_level(logging.DEBUG)
    v = validar(datos, CONTENIDO)
    assert v.rechazada
    texto = " ".join([repr(v), str(v.motivo_rechazo), str(v.campo), caplog.text])
    for secreto in (_SECRETO_TEL, _SECRETO_TEXTO, "offerup.com"):
        assert secreto not in texto


def test_la_excepcion_de_forma_no_lleva_valores():
    with pytest.raises(RegistroInvalido) as error:
        leer_observacion(particular(pickupLocation=_QUITAR, sellerPhone=_SECRETO_TEL))
    assert _SECRETO_TEL not in str(error.value)
    assert _SECRETO_TEL not in repr(error.value)


def test_particular_valido_sin_texto_del_vendedor():
    datos = particular(
        title=_SECRETO_TEXTO,
        sellerPhone=_SECRETO_TEL,
        evidence={"nota": _SECRETO_TEXTO},
        availability={"state": "listed", "text": _SECRETO_TEXTO},
    )
    v = validar(datos, CONTENIDO)
    assert not v.rechazada
    obs = v.observacion
    assert obs.title == "DEWALT DCF840"
    assert obs.evidence is None
    assert obs.availability.text is None
    volcado = obs.model_dump_json()
    assert _SECRETO_TEL not in volcado
    assert _SECRETO_TEXTO not in volcado


# --- Sin red, reproducible -----------------------------------------------------------------


def test_la_validacion_nunca_abre_una_url(monkeypatch):
    def _prohibido(*_a, **_k):
        raise AssertionError("la validación intentó usar la red")

    monkeypatch.setattr(socket, "getaddrinfo", _prohibido)
    monkeypatch.setattr(socket, "gethostbyname", _prohibido)
    monkeypatch.setattr(socket, "create_connection", _prohibido)
    monkeypatch.setattr(socket.socket, "connect", _prohibido)
    casos = [comercio(), particular(), *(comercio(productUrl=u) for u in URL.values())]
    casos += [particular(productUrl=u) for u in URL.values()]
    for datos in casos:
        validar(datos, CONTENIDO)
        motor.evaluar(_contexto(datos))


def test_reproducible():
    for datos in (
        comercio(),
        particular(),
        particular(pickupLocation="ensenada"),
        comercio(price={"current": "0.00"}),
    ):
        a = validar(datos, CONTENIDO)
        b = validar(copy.deepcopy(datos), CONTENIDO)
        assert (a.motivo_rechazo, a.campo) == (b.motivo_rechazo, b.campo)
        ra = motor.evaluar(_contexto(datos))
        rb = motor.evaluar(_contexto(copy.deepcopy(datos)))
        assert ra == rb


# --- Regresión de leer_observacion (T03) sin el parámetro nuevo ----------------------------


def test_leer_observacion_sin_no_validos_no_cambia():
    # Sin el parámetro, un particular con otro estado se lee en forma (la regla es del paso 1).
    datos = particular(availability={"state": "in_stock"})
    a = leer_observacion(datos)
    b = leer_observacion(datos, no_validos=())
    assert a == b
    assert a.availability.state == "in_stock"
    # Y los faltantes del contrato siguen con su motivo.
    with pytest.raises(RegistroInvalido) as error:
        leer_observacion(comercio(category=_QUITAR))
    assert error.value.motivo == faltante("category")
