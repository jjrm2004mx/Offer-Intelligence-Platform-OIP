"""Pruebas unitarias de T09: precio habitual, historial suficiente, episodio y franja
(CMP-11, CMP-12, PAR-08; design.md §10.1, §10.2 y §12 "Mediana par e impar").

Fixtures sintéticos; las URL son de example.com y ninguna prueba las abre.
"""

from __future__ import annotations

import builtins
import datetime as dt
import socket
from decimal import Decimal
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from oip.catalogos import Motivo
from oip.configuracion import cargar_configuracion, cargar_configuracion_texto
from oip.entradas.contrato import leer_observacion
from oip.evaluacion import motor, referencias
from oip.evaluacion.contexto import ContextoEvaluacion, Episodio, ObservacionRegistrada
from oip.evaluacion.descuento import descuento_real, franja

BASE = Path(__file__).parent / "fixtures" / "config" / "base.yaml"
CONFIG = cargar_configuracion(BASE)
PARAMETROS = CONFIG.contenido.price_reference
ZONA = ZoneInfo("America/Tijuana")
HOY = dt.date(2026, 11, 18)
PRODUCTO = UUID(int=500)
PUB_A = UUID(int=501)
PUB_B = UUID(int=502)

_contador = iter(range(1_000, 1_000_000))


def _dia(n: int) -> dt.date:
    return HOY + dt.timedelta(days=n)


def _momento(n: int, hora: int = 12, minuto: int = 0) -> dt.datetime:
    fecha = _dia(n)
    return dt.datetime(fecha.year, fecha.month, fecha.day, hora, minuto, tzinfo=ZONA)


def _obs(
    n: int,
    precio: str,
    *,
    publicacion: UUID = PUB_A,
    hora: int = 12,
    minuto: int = 0,
    ident: UUID | None = None,
    **cambios,
) -> ObservacionRegistrada:
    datos = {
        "retailerCode": "homedepot",
        "storeCode": "hd-chula-vista",
        "productUrl": "https://tienda.example.com/p/1",
        "title": "Producto de prueba",
        "brand": "MarcaP",
        "model": "MP-1",
        "category": "tools",
        "price": {"current": precio, "currency": "USD"},
        "seller": "comercio",
        "condition": "new",
        "availability": {"state": "in_stock"},
        "purchaseMode": "tienda",
        "extractedAt": _momento(n, hora, minuto).isoformat(),
        "blocked": False,
    }
    datos.update(cambios)
    ident = UUID(int=next(_contador)) if ident is None else ident
    return ObservacionRegistrada(leer_observacion(datos), ident, publicacion, PRODUCTO)


def _ficha(n: int, buy_box: str | None, **cambios) -> ObservacionRegistrada:
    return _obs(
        n,
        "999.00",
        publicacion=UUID(int=503),
        retailerCode="amazon",
        storeCode=None,
        productUrl="https://amazon.example.com/dp/X",
        purchaseMode="envio",
        amazonListing={"buyBoxPrice": buy_box, "sellersNew": 3},
        **cambios,
    )


def _contexto(oferta, historial=(), fichas=(), configuracion=CONFIG, hora=13):
    return ContextoEvaluacion(
        id_evaluacion=UUID(int=1),
        instante=_momento(0, hora),
        configuracion=configuracion,
        id_version_configuracion=1,
        oferta=oferta,
        historial=tuple(historial),
        fichas_amazon=tuple(fichas),
    )


def _diez_dias(precio: str = "100.00", publicacion: UUID = PUB_A):
    return [_obs(n, precio, publicacion=publicacion) for n in range(-10, 0)]


# --- Mediana -------------------------------------------------------------------------------


def test_mediana_impar_es_la_central():
    valores = [Decimal("3"), Decimal("1"), Decimal("2")]
    assert referencias.mediana(valores) == Decimal("2")


def test_mediana_par_es_el_promedio_de_las_dos_centrales_sin_redondear():
    valores = [Decimal("10.00"), Decimal("10.01"), Decimal("1"), Decimal("99")]
    resultado = referencias.mediana(valores)
    assert resultado == Decimal("10.005")  # no 10.01: el habitual no se redondea
    assert str(resultado) == "10.005"


def test_mediana_par_con_un_tercio():
    valores = [Decimal("1"), Decimal("1.0000000001")]
    assert referencias.mediana(valores) == Decimal("1.00000000005")


def test_mediana_vacia_o_con_float():
    with pytest.raises(ValueError):
        referencias.mediana([])
    with pytest.raises(TypeError):
        referencias.mediana([Decimal("1"), 2.0])  # type: ignore[list-item]


# --- Día calendario y observación diaria ---------------------------------------------------


def test_el_dia_es_el_de_la_zona_de_par_01_no_el_de_utc():
    tarde = _momento(-1, 23, 30)  # 07:30 UTC del día siguiente
    assert tarde.astimezone(dt.UTC).date() == HOY
    assert referencias.dia_calendario(tarde, ZONA) == _dia(-1)


def test_un_momento_sin_desfase_se_rechaza():
    with pytest.raises(ValueError):
        referencias.dia_calendario(dt.datetime(2026, 11, 18, 12), ZONA)  # noqa: DTZ001


def test_una_observacion_por_publicacion_y_dia_la_ultima():
    historial = [
        _obs(-3, "150.00", hora=8),
        _obs(-3, "120.00", hora=23, minuto=59),
        _obs(-3, "130.00", hora=15),
        _obs(-3, "80.00", publicacion=PUB_B),
    ]
    diarias = referencias.observaciones_diarias(_contexto(_obs(0, "50.00"), historial))
    por_publicacion = {(d.id_publicacion, d.dia): d.precio for d in diarias}
    assert por_publicacion == {
        (PUB_A, _dia(-3)): Decimal("120.00"),
        (PUB_B, _dia(-3)): Decimal("80.00"),
    }


def test_una_observacion_repetida_cuenta_una_vez():
    repetida = _obs(-2, "100.00")
    contexto = _contexto(_obs(0, "50.00"), [repetida, repetida], [])
    assert len(referencias.observaciones_diarias(contexto)) == 1


@pytest.mark.parametrize(
    "cambios",
    [
        {"seller": "externo"},
        {"seller": "desconocido"},
        {"condition": "used"},
        {"condition": "open_box"},
        {"blocked": True},
    ],
)
def test_solo_cuenta_nuevo_y_vendido_por_el_comercio(cambios):
    historial = [_obs(-1, "100.00", **cambios)]
    assert referencias.observaciones_diarias(_contexto(_obs(0, "50.00"), historial)) == ()


def test_estado_desconocido_de_un_comercio_cuenta_como_nuevo_s13():
    historial = [_obs(-1, "100.00", condition=None)]
    assert len(referencias.observaciones_diarias(_contexto(_obs(0, "50.00"), historial))) == 1


def test_el_boton_de_compra_de_amazon_cuenta_y_sin_oferta_no():
    fichas = [_ficha(-2, "90.00"), _ficha(-1, None)]
    diarias = referencias.observaciones_diarias(_contexto(_obs(0, "50.00"), (), fichas))
    assert [(d.dia, d.precio) for d in diarias] == [(_dia(-2), Decimal("90.00"))]


# --- Historial suficiente y precio habitual ------------------------------------------------


@pytest.mark.parametrize(
    ("dias", "por_dia", "suficiente"),
    [
        (3, 2, True),  # 6 observaciones en 3 días
        (5, 1, True),  # 5 en 5
        (2, 3, False),  # 6 en 2 días
        (4, 1, False),  # 4 en 4
    ],
)
def test_historial_suficiente_5_en_3_dias(dias, por_dia, suficiente):
    publicaciones = [UUID(int=600 + i) for i in range(por_dia)]
    historial = [
        _obs(-n, "100.00", publicacion=p) for n in range(1, dias + 1) for p in publicaciones
    ]
    contexto = _contexto(_obs(0, "70.00"), historial)
    habitual = referencias.precio_habitual_del_producto(
        referencias.observaciones_diarias(contexto), HOY, PARAMETROS
    )
    assert (habitual is not None) is suficiente


def test_la_ventana_es_de_los_60_dias_anteriores_sin_el_dia_evaluado():
    historial = [
        _obs(-61, "500.00"),  # fuera de la ventana
        *[_obs(n, "100.00") for n in (-60, -30, -10, -5, -1)],
        _obs(0, "1.00", hora=9),  # el día evaluado no entra
    ]
    contexto = _contexto(_obs(0, "70.00", hora=12), historial)
    habitual = referencias.precio_habitual_del_producto(
        referencias.observaciones_diarias(contexto), HOY, PARAMETROS
    )
    assert habitual == Decimal("100.00")


def test_sin_historial_suficiente_no_hay_precio_habitual_ni_descuento_real():
    registro = motor.evaluar(_contexto(_obs(0, "70.00"), [_obs(-1, "100.00")]))
    assert registro.referencias.precio_habitual is None
    assert registro.referencias.fuente_precio_habitual is None
    assert registro.referencias.episodio is None
    assert registro.descuento_real is None
    assert Motivo.MERCADO_YA_BARATO not in registro.motivos


def test_sin_historial_alguno_las_referencias_quedan_vacias():
    registro = motor.evaluar(_contexto(_obs(0, "70.00")))
    assert registro.referencias == referencias.Referencias()


def test_la_ventana_y_el_historial_suficiente_salen_de_la_configuracion():
    texto = BASE.read_text("utf-8")
    texto = texto.replace(
        "sufficient_history_observations: 5", "sufficient_history_observations: 11"
    )
    otra = cargar_configuracion_texto(texto)
    historial = _diez_dias()
    con_base = motor.evaluar(_contexto(_obs(0, "70.00"), historial))
    con_otra = motor.evaluar(_contexto(_obs(0, "70.00"), historial, configuracion=otra))
    assert con_base.referencias.precio_habitual == Decimal("100.00")
    assert con_otra.referencias.precio_habitual is None


# --- Episodio -----------------------------------------------------------------------------


def _serie(*precios: tuple[int, str]):
    return tuple((_dia(n), Decimal(p)) for n, p in precios)


def test_una_baja_que_no_queda_bajo_el_habitual_no_abre_episodio():
    serie = _serie((-1, "120.00"), (0, "110.00"))
    habitual = {_dia(-1): Decimal("100"), _dia(0): Decimal("100")}
    assert referencias.episodio_vigente(serie, habitual, PARAMETROS) is None


def test_sin_habitual_el_dia_de_la_baja_no_abre_episodio():
    serie = _serie((-1, "120.00"), (0, "50.00"))
    assert referencias.episodio_vigente(serie, {_dia(0): None}, PARAMETROS) is None


def test_un_precio_bajo_el_habitual_sin_baja_no_abre_episodio():
    serie = _serie((-1, "50.00"), (0, "50.00"))
    habitual = {_dia(-1): Decimal("100"), _dia(0): Decimal("100")}
    assert referencias.episodio_vigente(serie, habitual, PARAMETROS) is None


def test_otra_baja_dentro_del_episodio_no_lo_reinicia():
    serie = _serie((-3, "100.00"), (-2, "80.00"), (-1, "60.00"), (0, "40.00"))
    habitual = {
        _dia(-2): Decimal("100"),
        _dia(-1): Decimal("90"),
        _dia(0): Decimal("80"),
    }
    episodio = referencias.episodio_vigente(serie, habitual, PARAMETROS)
    assert episodio == Episodio(inicio=_dia(-2), valor_congelado=Decimal("100"))


def test_tras_el_limite_una_baja_nueva_abre_otro_episodio():
    limite = PARAMETROS.clearance_episode_max_days
    inicio = -limite - 5
    serie = _serie(
        (inicio - 1, "100.00"),
        (inicio, "80.00"),
        (-2, "80.00"),  # día del episodio > límite: termina
        (-1, "70.00"),  # baja nueva
        (0, "70.00"),
    )
    habitual = {dia: Decimal("90") for dia, _ in serie}
    episodio = referencias.episodio_vigente(serie, habitual, PARAMETROS)
    assert episodio == Episodio(inicio=_dia(-1), valor_congelado=Decimal("90"))


def test_el_limite_del_episodio_sale_de_la_configuracion():
    texto = BASE.read_text("utf-8").replace(
        "clearance_episode_max_days: 30", "clearance_episode_max_days: 2"
    )
    otra = cargar_configuracion_texto(texto).contenido.price_reference
    serie = _serie((-3, "100.00"), (-2, "50.00"), (-1, "50.00"), (0, "50.00"))
    habitual = {dia: Decimal("100") for dia, _ in serie}
    assert referencias.episodio_vigente(serie[:-1], habitual, otra) is not None  # día 2
    assert referencias.episodio_vigente(serie, habitual, otra) is None  # día 3
    assert referencias.episodio_vigente(serie, habitual, PARAMETROS) is not None


def test_el_episodio_es_por_publicacion():
    # La publicación B baja el día −1 y abre su episodio; la A no baja y no lo tiene.
    historial = [
        *_diez_dias("100.00", PUB_A),
        *_diez_dias("100.00", PUB_B)[:-1],
        _obs(-1, "60.00", publicacion=PUB_B),
    ]
    oferta_a = _obs(0, "100.00", publicacion=PUB_A)
    oferta_b = _obs(0, "60.00", publicacion=PUB_B)
    registro_a = motor.evaluar(_contexto(oferta_a, [*historial, oferta_a]))
    registro_b = motor.evaluar(_contexto(oferta_b, [*historial, oferta_b]))
    assert registro_a.referencias.episodio is None
    assert registro_a.referencias.precio_habitual == Decimal("100.00")
    assert registro_b.referencias.episodio == Episodio(
        inicio=_dia(-1), valor_congelado=Decimal("100.00")
    )


def test_el_motor_guarda_el_episodio_con_su_inicio_y_su_valor_congelado():
    historial = _diez_dias("100.00")
    registro = motor.evaluar(_contexto(_obs(0, "60.00"), historial))
    assert registro.referencias.episodio == Episodio(inicio=HOY, valor_congelado=Decimal("100.00"))
    assert registro.referencias.precio_habitual == Decimal("100.00")
    assert registro.referencias.fuente_precio_habitual == "historial_propio"
    assert registro.descuento_real == Decimal("40")


# --- Descuento real y franja ---------------------------------------------------------------


def test_descuento_real_sin_redondear():
    real = descuento_real(Decimal("129"), Decimal("99.00"))
    assert real == (Decimal("30.00") / Decimal("129") * 100)
    assert str(real).startswith("23.255813953488372093")


@pytest.mark.parametrize(
    ("real", "motivo"),
    [
        (Decimal("-5"), Motivo.MERCADO_YA_BARATO),
        (Decimal("19.9999"), Motivo.MERCADO_YA_BARATO),
        (Decimal("20"), Motivo.SOLO_REFERENCIA),
        (Decimal("24.9999"), Motivo.SOLO_REFERENCIA),
        (Decimal("25"), None),
        (Decimal("80"), None),
    ],
)
def test_franja_con_los_cortes_de_par_10(real, motivo):
    assert franja(real, CONFIG.contenido.discount_quality) is motivo


def test_descuento_real_rechaza_float_y_habitual_no_positivo():
    with pytest.raises(TypeError):
        descuento_real(129.0, Decimal("99"))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        franja(20.0, CONFIG.contenido.discount_quality)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        descuento_real(Decimal("0"), Decimal("99"))


def test_un_usado_no_se_mide_contra_el_precio_habitual():
    registro = motor.evaluar(_contexto(_obs(0, "99.00", condition="used"), _diez_dias()))
    assert registro.referencias.precio_habitual == Decimal("100.00")
    assert registro.descuento_real is None
    assert registro.motivos == ()


# --- Reproducible y puro -------------------------------------------------------------------


def test_reproducible_desde_el_json_y_sin_red_ni_archivos(monkeypatch):
    contexto = _contexto(_obs(0, "60.00"), _diez_dias(), [_ficha(-3, "95.00")])
    leido = ContextoEvaluacion.desde_json(contexto.a_json())

    def prohibido(*a, **k):
        raise AssertionError("el motor no usa red ni archivos")

    monkeypatch.setattr(socket, "socket", prohibido)
    monkeypatch.setattr(builtins, "open", prohibido)
    primero = motor.evaluar(contexto)
    segundo = motor.evaluar(leido)
    assert primero == segundo
    assert primero.a_json() == segundo.a_json()


def test_el_orden_del_historial_no_cambia_el_resultado():
    historial = [*_diez_dias(), _obs(-4, "90.00", hora=20), _ficha(-3, "95.00")]
    a = motor.evaluar(_contexto(_obs(0, "60.00"), historial))
    b = motor.evaluar(_contexto(_obs(0, "60.00"), list(reversed(historial))))
    assert a.referencias == b.referencias
    assert a.descuento_real == b.descuento_real


def test_un_precio_invalido_del_historial_no_cuenta():
    historial = [_obs(-1, "100.001"), _obs(-2, "0")]
    assert referencias.observaciones_diarias(_contexto(_obs(0, "50.00"), historial)) == ()


def test_una_oferta_sin_publicacion_no_tiene_episodio_pero_si_mediana():
    sin_ids = ObservacionRegistrada(_obs(0, "60.00").observacion, None, None, None)
    contexto = _contexto(sin_ids, _diez_dias())
    assert referencias.serie_de_la_publicacion(contexto) == ()
    registro = motor.evaluar(contexto)
    assert registro.referencias.episodio is None
    assert registro.referencias.precio_habitual == Decimal("100.00")
