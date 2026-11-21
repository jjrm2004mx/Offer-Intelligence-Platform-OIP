"""Catálogos cerrados de la parte B (CMP-03; design.md §9).

Cada enum guarda el **código exacto** del REQ-2026-0001 o del contrato de ingesta 3.1 de
la arquitectura v2.2 §8, con sus espacios y acentos. El orden de definición es el orden
de §9 donde importa (motivos, niveles, calidad del precio, motivos de rechazo).

Este módulo no decide resultados: solo fija códigos, su orden y su "lleva a".
El tipo de monto (lista cerrada de §8) vive en ``oip.dinero.TipoMonto``.
"""

from enum import StrEnum
from types import MappingProxyType

# --- Resultado (REQ §3.2.2) ------------------------------------------------------------


class Resultado(StrEnum):
    """Catálogo de resultados (REQ §3.2.2). La precedencia de §3.2.4 la aplica CMP-16."""

    RECHAZADA_VALIDACION = "RECHAZADA_VALIDACION"
    DESCARTADA = "DESCARTADA"
    SOLO_REFERENCIA = "SOLO_REFERENCIA"
    REVISION_MANUAL = "REVISION_MANUAL"
    SIN_NIVEL = "SIN_NIVEL"
    NIVEL_ASIGNADO = "NIVEL_ASIGNADO"


# --- Motivo de rechazo (REQ §3.2 paso 1, §3.2.6) -----------------------------------------


class MotivoRechazo(StrEnum):
    """Motivos de rechazo de un registro, en el orden de comprobación de design.md §6.

    ``CAMPO_OBLIGATORIO_FALTANTE`` es el código base; el motivo completo lleva el campo:
    use ``motivo_campo_faltante``.
    """

    TIPO_DE_REGISTRO_DESCONOCIDO = "TIPO DE REGISTRO DESCONOCIDO"
    CAMPO_OBLIGATORIO_FALTANTE = "CAMPO OBLIGATORIO FALTANTE"
    PRECIO_INVALIDO = "PRECIO INVÁLIDO"
    DOMINIO_NO_AUTORIZADO = "DOMINIO NO AUTORIZADO"
    CIUDAD_NO_CONFIGURADA = "CIUDAD NO CONFIGURADA"


def motivo_campo_faltante(campo: str) -> str:
    """``CAMPO OBLIGATORIO FALTANTE (<campo>)`` con el nombre del campo tal como va en el
    archivo (design.md §6; DEC-234), por ejemplo ``(exchangeRate)`` o ``(pickupLocation)``.
    """
    return _con_dato(MotivoRechazo.CAMPO_OBLIGATORIO_FALTANTE, campo, "campo")


# --- Motivo (REQ §3.2.3) -----------------------------------------------------------------


class Motivo(StrEnum):
    """Motivos en el orden de REQ §3.2.3: el primero que aplica es el principal.

    ``lleva_a`` da el resultado de cada motivo (columna "Lleva a" de §3.2.3).
    """

    EVITAR = "EVITAR"
    MERCADO_YA_BARATO = "MERCADO YA BARATO"
    SIN_CANAL_DISPONIBLE = "SIN CANAL DISPONIBLE"
    MARGEN_NEGATIVO = "MARGEN NEGATIVO"
    SOLO_REFERENCIA = "SOLO REFERENCIA"
    SIN_HISTORIAL_SUFICIENTE = "SIN HISTORIAL SUFICIENTE"
    SIN_REFERENCIA_DE_USADOS = "SIN REFERENCIA DE USADOS"
    COINCIDENCIA_NO_CONFIRMADA = "COINCIDENCIA NO CONFIRMADA"
    VENDEDOR_EXTERNO = "VENDEDOR EXTERNO"
    PARTICULAR = "PARTICULAR"
    RIESGO_DE_PROCEDENCIA = "RIESGO DE PROCEDENCIA"
    DEMANDA_DESCONOCIDA = "DEMANDA DESCONOCIDA"

    @property
    def lleva_a(self) -> Resultado:
        return _LLEVA_A[self]


_LLEVA_A: MappingProxyType[Motivo, Resultado] = MappingProxyType(
    {
        Motivo.EVITAR: Resultado.DESCARTADA,
        Motivo.MERCADO_YA_BARATO: Resultado.DESCARTADA,
        Motivo.SIN_CANAL_DISPONIBLE: Resultado.DESCARTADA,
        Motivo.MARGEN_NEGATIVO: Resultado.DESCARTADA,
        Motivo.SOLO_REFERENCIA: Resultado.SOLO_REFERENCIA,
        Motivo.SIN_HISTORIAL_SUFICIENTE: Resultado.REVISION_MANUAL,
        Motivo.SIN_REFERENCIA_DE_USADOS: Resultado.REVISION_MANUAL,
        Motivo.COINCIDENCIA_NO_CONFIRMADA: Resultado.REVISION_MANUAL,
        Motivo.VENDEDOR_EXTERNO: Resultado.REVISION_MANUAL,
        Motivo.PARTICULAR: Resultado.REVISION_MANUAL,
        Motivo.RIESGO_DE_PROCEDENCIA: Resultado.REVISION_MANUAL,
        Motivo.DEMANDA_DESCONOCIDA: Resultado.REVISION_MANUAL,
    }
)


# --- Marcas informativas (REQ §3.2.3) ----------------------------------------------------


class Marca(StrEnum):
    """Marcas informativas: no cambian el resultado (REQ §3.2.3).

    ``ESTIMADO`` es el código base; la marca completa lleva el dato: use ``marca_estimado``.
    Las causas de canal cerrado también se registran como marcas (``CausaCanalCerrado``).
    """

    PRECIO_ANTES_INFLADO = "PRECIO ANTES INFLADO"
    DESCUENTO_ANUNCIADO_NO_COMPROBADO = "DESCUENTO ANUNCIADO NO COMPROBADO"
    DEMANDA_A_LA_BAJA = "DEMANDA A LA BAJA"
    COMPETENCIA_MAS_BARATA = "COMPETENCIA MÁS BARATA"
    SIN_OFERTA_HOY = "SIN OFERTA HOY"
    MATERIAL_PELIGROSO = "MATERIAL PELIGROSO"
    REVISAR_RETIROS = "REVISAR RETIROS"
    SIN_COMPARABLES_LOCALES = "SIN COMPARABLES LOCALES"
    CONFIANZA_BAJA = "CONFIANZA BAJA"
    ESTIMADO = "ESTIMADO"
    MARGEN_ESTIMADO = "MARGEN ESTIMADO"
    EMPAQUE_POR_CONFIRMAR = "EMPAQUE POR CONFIRMAR"


class DatoEstimado(StrEnum):
    """El ``<dato>`` de ``ESTIMADO (<dato>)`` (design.md §9; DEC-266)."""

    PESO = "peso"
    DEVOLUCION = "devolución"
    UNIDADES = "unidades"


def marca_estimado(dato: str) -> str:
    """``ESTIMADO (<dato>)``, por ejemplo ``ESTIMADO (peso)`` o ``ESTIMADO (devolución)``."""
    return _con_dato(Marca.ESTIMADO, dato, "dato")


def es_marca(texto: str) -> bool:
    """``True`` si ``texto`` es una marca del registro (design.md §9; DEC-266): una ``Marca``
    salvo ``ESTIMADO`` solo, una ``CausaCanalCerrado`` o ``ESTIMADO (<dato>)`` con el dato de
    ``DatoEstimado``. Una causa de canal por revisar no es marca."""
    raise NotImplementedError


def _con_dato(base: StrEnum, dato: str, nombre: str) -> str:
    if not isinstance(dato, str) or not dato.strip():
        raise ValueError(f"falta el {nombre} de {base.value}")
    return f"{base.value} ({dato.strip()})"


# --- Canales (REQ §3.2.1) ----------------------------------------------------------------


class Canal(StrEnum):
    AMAZON = "amazon"
    LOCAL = "local"


class EstadoCanal(StrEnum):
    """Estado de cada canal (REQ §3.2.1). Con causas de cerrado y de por revisar a la vez,
    queda cerrado (S-31); lo decide CMP-13."""

    CERRADO = "CERRADO"
    POR_REVISAR = "POR_REVISAR"
    DISPONIBLE = "DISPONIBLE"


class CausaCanalCerrado(StrEnum):
    """Causas de canal cerrado (REQ §3.2.1). ``PRODUCTO NO NUEVO``, ``DEMANDA LOCAL BAJA`` y
    ``SIN PRECIO LOCAL`` no tienen literal en el REQ: los fija DEC-234 (1)."""

    SIN_PRECIO_DE_VENTA_EN_AMAZON = "SIN PRECIO DE VENTA EN AMAZON"
    DEMANDA_INSUFICIENTE_EN_AMAZON = "DEMANDA INSUFICIENTE EN AMAZON"
    NO_VENDIBLE_EN_AMAZON = "NO VENDIBLE EN AMAZON (POR AHORA)"
    COMISION_DESCONOCIDA = "COMISIÓN DESCONOCIDA"
    TASA_DE_DEVOLUCION_DESCONOCIDA = "TASA DE DEVOLUCIÓN DESCONOCIDA"
    ENVIO_POR_COTIZAR = "ENVÍO POR COTIZAR"
    PRODUCTO_NO_NUEVO = "PRODUCTO NO NUEVO"
    SIN_ROTACION = "SIN ROTACIÓN"
    DEMANDA_LOCAL_BAJA = "DEMANDA LOCAL BAJA"
    SIN_PRECIO_LOCAL = "SIN PRECIO LOCAL"


class CausaCanalPorRevisar(StrEnum):
    """Causas de canal por revisar (REQ §3.2.1)."""

    DEMANDA_DESCONOCIDA = "DEMANDA DESCONOCIDA"
    SIN_REFERENCIA_DE_USADOS = "SIN REFERENCIA DE USADOS"


CAUSAS_CERRADO_POR_CANAL: MappingProxyType[Canal, tuple[CausaCanalCerrado, ...]] = MappingProxyType(
    {
        Canal.AMAZON: (
            CausaCanalCerrado.SIN_PRECIO_DE_VENTA_EN_AMAZON,
            CausaCanalCerrado.DEMANDA_INSUFICIENTE_EN_AMAZON,
            CausaCanalCerrado.NO_VENDIBLE_EN_AMAZON,
            CausaCanalCerrado.COMISION_DESCONOCIDA,
            CausaCanalCerrado.TASA_DE_DEVOLUCION_DESCONOCIDA,
            CausaCanalCerrado.ENVIO_POR_COTIZAR,
            CausaCanalCerrado.PRODUCTO_NO_NUEVO,
            CausaCanalCerrado.SIN_ROTACION,
        ),
        Canal.LOCAL: (
            CausaCanalCerrado.DEMANDA_LOCAL_BAJA,
            CausaCanalCerrado.SIN_PRECIO_LOCAL,
            CausaCanalCerrado.SIN_ROTACION,
        ),
    }
)

CAUSAS_POR_REVISAR_POR_CANAL: MappingProxyType[Canal, tuple[CausaCanalPorRevisar, ...]] = (
    MappingProxyType(
        {
            Canal.AMAZON: (CausaCanalPorRevisar.DEMANDA_DESCONOCIDA,),
            Canal.LOCAL: (CausaCanalPorRevisar.SIN_REFERENCIA_DE_USADOS,),
        }
    )
)


# --- Nivel (RN-009) ----------------------------------------------------------------------


class Nivel(StrEnum):
    """Niveles de RN-009, de mayor a menor."""

    COMPRAR_YA = "COMPRAR_YA"
    MUY_RECOMENDABLE = "MUY_RECOMENDABLE"
    RECOMENDABLE = "RECOMENDABLE"
    VIGILAR = "VIGILAR"


def nivel_inferior(nivel: Nivel) -> Nivel | None:
    """El nivel siguiente hacia abajo ("baja un nivel"); Vigilar baja a sin nivel (``None``)."""
    orden = list(Nivel)
    posicion = orden.index(Nivel(nivel))
    return orden[posicion + 1] if posicion + 1 < len(orden) else None


# --- Calidad del precio (RN-012) ---------------------------------------------------------


class CalidadPrecio(StrEnum):
    """Calidad del precio en el orden de asignación de RN-012 §4: se asigna la primera que se
    cumple, y Descuento cuestionable se evalúa primero. ``NO_APLICA`` (usados, DEC-215) queda
    fuera de ese orden y va al final."""

    DESCUENTO_CUESTIONABLE = "DESCUENTO_CUESTIONABLE"
    OFERTA_EXCEPCIONAL = "OFERTA_EXCEPCIONAL"
    BUENA_OFERTA = "BUENA_OFERTA"
    PRECIO_COMPETITIVO = "PRECIO_COMPETITIVO"
    PRECIO_NORMAL = "PRECIO_NORMAL"
    NO_APLICA = "NO_APLICA"


# --- Identificación (RN-013) -------------------------------------------------------------


class Identificacion(StrEnum):
    """Coincidencia del producto (RN-013): columna ``identification`` de TAB-05 y TAB-10."""

    CONFIRMED = "confirmed"
    UNCONFIRMED = "unconfirmed"


# --- Confianza y demanda -----------------------------------------------------------------


class Confianza(StrEnum):
    """Confianza de la disponibilidad (RN-007)."""

    ALTA = "ALTA"
    MEDIA = "MEDIA"
    BAJA = "BAJA"


class DemandaAmazon(StrEnum):
    """Demanda en Amazon (RN-004)."""

    SUFICIENTE = "SUFICIENTE"
    INSUFICIENTE = "INSUFICIENTE"
    DESCONOCIDA = "DESCONOCIDA"


class DemandaLocal(StrEnum):
    """Demanda local (RN-017), con los códigos de la captura ``local_demand``."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Tipos de registro de un archivo (REQ §3.2.6, §6; DEC-227) ---------------------------


class TipoRegistro(StrEnum):
    """Valores de ``recordType``."""

    OBSERVATION = "observation"
    LOCAL_COMPARABLE = "local_comparable"
    LOCAL_ESTIMATE = "local_estimate"
    MSRP = "msrp"
    LOCAL_DEMAND = "local_demand"
    STORE_VISIT = "store_visit"
    ACTUAL_RESULT = "actual_result"
    CLIENT_REQUEST = "client_request"


# --- Códigos cerrados del contrato de ingesta 3.1 (arquitectura v2.2 §8; DEC-199) --------
# Agregar un código es un cambio de contrato.


class EstadoDisponibilidad(StrEnum):
    """``availability.state``."""

    IN_STOCK_CONFIRMED = "in_stock_confirmed"
    IN_STOCK = "in_stock"
    LIMITED_STOCK = "limited_stock"
    UNCONFIRMED = "unconfirmed"
    OUT_OF_STOCK = "out_of_stock"
    LISTED = "listed"


class Categoria(StrEnum):
    """``category``."""

    TOOLS = "tools"
    HOME_LIGHTING = "home_lighting"
    HOME_KITCHEN = "home_kitchen"
    ELECTRONICS = "electronics"
    VIDEO_GAME_CONSOLES = "video_game_consoles"
    VIDEO_GAMES = "video_games"
    TOYS = "toys"
    WATCHES = "watches"
    JEWELRY = "jewelry"
    BEAUTY = "beauty"


class Condicion(StrEnum):
    """``condition`` (RN-014)."""

    NEW = "new"
    OPEN_BOX = "open_box"
    REFURBISHED = "refurbished"
    USED = "used"
    FOR_PARTS = "for_parts"


class Vendedor(StrEnum):
    """``seller``."""

    COMERCIO = "comercio"
    EXTERNO = "externo"
    PARTICULAR = "particular"
    DESCONOCIDO = "desconocido"


class ModoCompra(StrEnum):
    """``purchaseMode``."""

    ENVIO = "envio"
    RECOLECCION = "recoleccion"
    TIENDA = "tienda"
    PARTICULAR = "particular"


# --- Referencias de precio (REQ §3.2.5) --------------------------------------------------


class ReferenciaPrecio(StrEnum):
    """Las cuatro referencias de precio cuyo cambio dispara una reevaluación (§3.2.5)."""

    PRECIO_HABITUAL = "precio_habitual"
    PRECIO_MERCADO_HOY = "precio_mercado_hoy"
    MINIMO_60_DIAS_AMAZON = "minimo_60_dias_amazon"
    PRECIO_VENTA_AMAZON = "precio_venta_amazon"
