"""Pruebas unitarias de oip.dinero (CMP-02; design.md §8 y §12; tasks.md T01 1.2)."""

from decimal import Decimal

import pytest

from oip.dinero import TipoMonto, formatear_porcentaje, leer_monto, redondear

# --- Lista cerrada --------------------------------------------------------------------


def test_lista_cerrada_de_montos_del_req():
    # REQ §5 / DEC-207: impuesto, costo de compra, comisión, envío, devoluciones, castigo,
    # precio de venta local, valor de referencia de usados, traslados (entrega, recogida y
    # viaje), margen neto, margen ajustado y ganancia total.
    assert [t.value for t in TipoMonto] == [
        "impuesto",
        "costo_compra",
        "comision",
        "envio",
        "devoluciones",
        "castigo",
        "precio_venta_local",
        "valor_referencia_usados",
        "traslado_entrega",
        "traslado_recogida",
        "traslado_viaje",
        "margen_neto",
        "margen_ajustado",
        "ganancia_total",
    ]


# --- Redondeo ROUND_HALF_UP a centavos ------------------------------------------------


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("2.2475", "2.25"),
        ("5.215", "5.22"),
        ("2.5375", "2.54"),
        ("76.614750", "76.61"),
        ("-9.125", "-9.13"),
        ("0.005", "0.01"),
        ("0.004", "0.00"),
        ("-0.005", "-0.01"),
        ("29", "29.00"),
        ("12.3", "12.30"),
    ],
)
@pytest.mark.parametrize("tipo", list(TipoMonto))
def test_redondear_half_up_a_centavos_en_cada_tipo(tipo, valor, esperado):
    resultado = redondear(tipo, Decimal(valor))
    assert isinstance(resultado, Decimal)
    assert resultado == Decimal(esperado)
    assert resultado.as_tuple().exponent == -2


def test_redondeo_una_sola_vez_al_final_b33():
    # B33: 100.15 × 85% × 90% = 76.614750 → 76.61; redondear en cada paso daría 76.62.
    mercado_hoy = leer_monto("100.15")
    una_vez = redondear(
        TipoMonto.PRECIO_VENTA_LOCAL, mercado_hoy * Decimal("0.85") * Decimal("0.90")
    )
    assert una_vez == Decimal("76.61")
    paso_a_paso = redondear(
        TipoMonto.PRECIO_VENTA_LOCAL,
        redondear(TipoMonto.PRECIO_VENTA_LOCAL, mercado_hoy * Decimal("0.85")) * Decimal("0.90"),
    )
    assert paso_a_paso == Decimal("76.62")
    assert una_vez != paso_a_paso


def test_redondear_no_cambia_el_valor_de_entrada():
    valor = Decimal("2.2475")
    redondear(TipoMonto.MARGEN_NETO, valor)
    assert valor == Decimal("2.2475")


# --- Sin float ------------------------------------------------------------------------


def test_redondear_rechaza_float():
    with pytest.raises(TypeError):
        redondear(TipoMonto.IMPUESTO, 2.2475)


@pytest.mark.parametrize("valor", [2, "2.25", None])
def test_redondear_exige_decimal(valor):
    with pytest.raises(TypeError):
        redondear(TipoMonto.IMPUESTO, valor)


@pytest.mark.parametrize("tipo", ["impuesto", None, "precio_habitual"])
def test_redondear_exige_un_tipo_de_la_lista_cerrada(tipo):
    with pytest.raises(TypeError):
        redondear(tipo, Decimal("1.005"))


@pytest.mark.parametrize("valor", ["NaN", "Infinity", "-Infinity", "sNaN"])
def test_redondear_rechaza_no_finitos(valor):
    with pytest.raises(ValueError):
        redondear(TipoMonto.IMPUESTO, Decimal(valor))


# --- Lectura desde texto --------------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [("29.00", "29.00"), (" 129.00 ", "129.00"), ("76.614750", "76.614750"), ("-9.125", "-9.125")],
)
def test_leer_monto_desde_texto_sin_redondear(texto, esperado):
    valor = leer_monto(texto)
    assert isinstance(valor, Decimal)
    assert valor == Decimal(esperado)
    assert str(valor) == esperado


def test_leer_monto_acepta_decimal():
    assert leer_monto(Decimal("29.00")) == Decimal("29.00")


def test_leer_monto_rechaza_float():
    with pytest.raises(TypeError):
        leer_monto(29.0)


@pytest.mark.parametrize("valor", [29, None, b"29.00"])
def test_leer_monto_rechaza_otros_tipos(valor):
    with pytest.raises(TypeError):
        leer_monto(valor)


@pytest.mark.parametrize("texto", ["", "abc", "1,234.50", "$29.00", "NaN", "Infinity"])
def test_leer_monto_rechaza_texto_invalido(texto):
    with pytest.raises(ValueError):
        leer_monto(texto)


# --- Porcentajes ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("porcentaje", "esperado"),
    [
        ("75.63", "75.6 %"),
        ("24.96", "25.0 %"),
        ("24.95", "25.0 %"),
        ("24.94", "24.9 %"),
        ("143.1", "143.1 %"),
        ("25", "25.0 %"),
        ("-3.25", "-3.3 %"),
        ("-0.04", "0.0 %"),
        ("0", "0.0 %"),
    ],
)
def test_formatear_porcentaje_a_un_decimal(porcentaje, esperado):
    assert formatear_porcentaje(Decimal(porcentaje)) == esperado


def test_formatear_porcentaje_no_altera_el_valor_para_comparar():
    # 24.96% se muestra "25.0 %", pero sigue siendo menor que 25% al comparar (DEC-207).
    descuento = Decimal("24.96")
    assert formatear_porcentaje(descuento) == "25.0 %"
    assert descuento == Decimal("24.96")
    assert descuento < Decimal("25")


def test_formatear_porcentaje_rechaza_float():
    with pytest.raises(TypeError):
        formatear_porcentaje(24.96)


def test_formatear_porcentaje_rechaza_no_finitos():
    with pytest.raises(ValueError):
        formatear_porcentaje(Decimal("NaN"))
