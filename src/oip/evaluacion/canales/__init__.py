"""Pasos 6 a 8 de REQ §3.2: costo de compra, estado de cada canal y sus números base (CMP-13).

Reglas (RN-001 v2, RN-004 v2, RN-006 v2, RN-008 v2, RN-016 v1, RN-017 v1; REQ §3.2.1; S-06,
S-08, S-09, S-12, S-24, S-27, S-31; DEC-197, DEC-206, DEC-217, DEC-220, DEC-225). Todas las
cifras salen de la configuración versionada (PAR-04, PAR-05, PAR-06, PAR-07, PAR-09, PAR-11,
PAR-12, PAR-13); ninguna está en el código. Cada monto de la lista cerrada se redondea **una
vez**, al final de su fórmula, con ``oip.dinero.redondear``; los montos combinados usan los ya
redondeados (design.md §8).

- **Costo de compra** (RN-001 §4, REQ §3.2 paso 6) = precio + impuesto + envío hacia mí. El
  impuesto usa la tasa de ``taxLocation`` (PAR-07) o la de respaldo (DEC-220); la compra a un
  particular no lleva impuesto (S-14). La recogida con particulares la agrega T20.
- **Estado del canal** (REQ §3.2.1): con una causa de cerrado queda **cerrado**, aunque tenga
  también una de por revisar (S-31); con solo causas de por revisar, **por revisar**; si no,
  **disponible**.
- **Amazon** (RN-004, RN-006; DEC-206): ranking = promedio de la última ``rankMain`` de cada
  día de los ``rank_window_days`` días que terminan el día evaluado (con 1 a 6 días, el de los
  disponibles; con 0, demanda desconocida); el mismo valor sirve para el umbral, los días de
  venta y el tope. Demanda SUFICIENTE con ranking ≤ tamaño de la categoría ×
  ``category_rank_pct`` (y en relojes y joyería, además, ``rankSub`` ≤
  ``subcategory_max_rank``) y vendedores ≤ ``max_new_sellers``; sin ranking, sin vendedores o
  sin tamaño de categoría, DESCONOCIDA (por revisar, DEC-225). Comisión de la categoría
  (``flat``, ``total_threshold`` o ``tiers``, DEC-217) con su mínimo por unidad; envío y
  empaque por peso (S-06); restricción por categoría, marca, producto o temporada de juguetes
  (S-09, S-10); ``MATERIAL PELIGROSO`` solo marca (S-07).
- **Venta local** (RN-016, RN-017, RN-008): precio estimado = el de Jesús o
  ``market_today_pct`` del precio de mercado hoy; techo = el menor precio pedido de los
  comparables del mismo estado en la zona de venta local; precio de venta local = mínimo de los
  dos × (1 − ``negotiation_pct``), redondeado una vez (B33). Demanda local = la captura más
  reciente de la categoría o la inicial de PAR-04, un nivel menos con más de
  ``competition_threshold`` comparables activos; baja cierra el canal. Entrega por defecto
  (S-24) = km × costo por km + horas × valor de la hora + costos fijos.

En todo cálculo de Amazon se marcan ``MARGEN ESTIMADO`` y ``EMPAQUE POR CONFIRMAR`` (RN-001
§11; RNF-9). Las causas de canal cerrado se registran también como marcas (REQ §3.2.3).

Puro (design.md §14): sin reloj, sin I/O, sin red.

Lecturas que fija esta implementación (para G4; ninguna cambia un escenario):

- **Demanda en Amazon** (RN-004 §4 y §11): cada condición (ranking, subcategoría,
  vendedores) se cumple, no se cumple o no se sabe. Si alguna **no se cumple**, INSUFICIENTE;
  si no, si alguna **no se sabe**, DESCONOCIDA; si no, SUFICIENTE.
- **Techo local** (RN-016 §4): cuentan todos los comparables del mismo estado en la zona de
  venta local (PAR-09, ``in_local_sale_zone``), vendidos o no; la **competencia** de RN-017
  ("publicaciones comparables activas") cuenta solo los no vendidos.
- **Peso a cobrar** (RN-006 §4.2): el ``weightKg`` de la observación; el peso por tamaño de la
  caja necesita el divisor de la paquetería, que la configuración no trae.
- **Venta local de un usado**: solo con estimado de Jesús hasta que T20 agregue el valor de
  referencia (RN-014).

El paquete está dividido por tema sin cambiar la interfaz (design.md §1: un módulo de más
de ~400 líneas pasa a un subpaquete con el mismo nombre): ``_base`` (tipos, apoyo y estado
del canal), ``_compra``, ``_amazon`` y ``_local``.
"""

from oip.evaluacion.canales._amazon import (
    comision_amazon,
    competencia_mas_barata,
    demanda_en_amazon,
    envio_amazon,
    evaluar_amazon,
    ficha_vigente,
    material_peligroso,
    ranking_amazon,
    restringido_en_amazon,
    tasa_devolucion_amazon,
    ventas_al_mes_amazon,
)
from oip.evaluacion.canales._base import (
    CanalEvaluado,
    CostoCompra,
    DemandaEnAmazon,
    EnvioAmazon,
    PrecioLocal,
    Ranking,
    TasaDevolucion,
    estado_del_canal,
)
from oip.evaluacion.canales._compra import (
    costo_compra,
    costo_recogida,
    tasa_impuesto,
)
from oip.evaluacion.canales._local import (
    costo_entrega,
    demanda_local,
    dias_por_unidad_local,
    evaluar_local,
    precio_venta_local,
    ventas_al_mes_local,
)

__all__ = [
    "CanalEvaluado",
    "CostoCompra",
    "DemandaEnAmazon",
    "EnvioAmazon",
    "PrecioLocal",
    "Ranking",
    "TasaDevolucion",
    "comision_amazon",
    "competencia_mas_barata",
    "costo_compra",
    "costo_entrega",
    "costo_recogida",
    "demanda_en_amazon",
    "demanda_local",
    "dias_por_unidad_local",
    "envio_amazon",
    "estado_del_canal",
    "evaluar_amazon",
    "evaluar_local",
    "ficha_vigente",
    "material_peligroso",
    "precio_venta_local",
    "ranking_amazon",
    "restringido_en_amazon",
    "tasa_devolucion_amazon",
    "tasa_impuesto",
    "ventas_al_mes_amazon",
    "ventas_al_mes_local",
]
