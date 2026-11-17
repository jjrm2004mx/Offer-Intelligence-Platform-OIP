# RN-016 — Precio de venta local

```yaml
id: RN-016
titulo: Precio de venta local
grupo: local
estado: BORRADOR
version: 1
fecha: 2026-11-16
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-002, RN-014]
origen: DEC-140, DEC-145, DEC-151; ejercicio CASO-005
```

> **Regla nueva.** La venta local (OfferUp, Facebook Marketplace y venta personal, DEC-151) no tiene una fuente automática de precios: Marketplace no tiene API, exige sesión y solo muestra precios pedidos (DEC-140). Por eso el precio local siempre es **estimado**. Lo marcado como propuesta está **por aceptar**.

## 1. ¿Qué queremos lograr?
Tener un precio de venta local **conservador** para calcular el margen en ese canal, sin contar con vender más caro que la competencia de la zona.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- De dónde sale el precio local estimado.
- El techo por la competencia local.
- El margen de negociación.

**No incluye:**
- La demanda local (RN-017).
- El costo de entrega (RN-008).

## 3. ¿Cómo funciona, en palabras?
Jesús captura a cuánto cree que puede venderlo; si no, se toma un porcentaje del precio de mercado. Ese precio nunca puede superar lo que piden otros por el mismo producto en la zona. Como en la venta local casi siempre se negocia, se descuenta un margen de negociación.

## 4. La regla

```
precio estimado        = el que captura Jesús;
                         si no lo hay: 85% del precio de mercado hoy (RN-002) — usados: 100% del valor de referencia (RN-014)
techo local            = el MENOR precio pedido de publicaciones comparables en la zona de venta local
precio pedido          = el MENOR entre precio estimado y techo local
precio de venta local  = precio pedido × (1 − 10%)        ← margen de negociación
```

- **Zona de venta local:** Tijuana y las Zonas 1 y 2 de San Diego (RN-008).
- Solo cuentan publicaciones del **mismo producto y estado** (RN-013, RN-014); las de otras ciudades no cuentan (CASO-005).
- Siempre se marca **"estimado"**.

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Porcentaje del precio de mercado | Sin estimado de Jesús | 85% | **Propuesta (por aceptar)** |
| Margen de negociación | Descuento sobre el precio pedido | 10% | **Propuesta (por aceptar)** |
| Zona de venta local | Dónde cuentan los comparables | Tijuana y Zonas 1 y 2 de San Diego | **Propuesta (por aceptar)** |

Todos los valores son iniciales y configurables.

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Taladro con estimado de Jesús**
- Jesús estima $129. Comparables locales: $135, $139, $150 → techo **$135**.
- Precio pedido = menor(129, 135) = $129 → precio de venta local = 129 × 0.90 = **$116.10** (lo usa RN-001, ejemplo C).

**Ejemplo B — Sin estimado**
- Precio de mercado hoy $149 → 85% = $126.65. Techo $135 → precio pedido $126.65 → × 0.90 = **$113.99**.

**Ejemplo C — Baterías Milwaukee (CASO-005)**
- Jesús estima $110. Comparable en la zona: $99 (Vista); los de Houston no cuentan → techo **$99**.
- Precio pedido $99 → precio de venta local = **$89.10**.

## 6. ¿Qué información necesitamos?
- Estimado de Jesús, si lo hay.
- Publicaciones comparables en la zona, que captura Jesús (DEC-150).
- Precio de mercado hoy (RN-002) o valor de usados (RN-014).

## 7. ¿Qué obtenemos?
- Precio de venta local estimado, con el techo y los comparables usados.

## 8. ¿Quién participa?
- Jesús captura el estimado y los comparables.
- El sistema calcula.

## 9. ¿De qué depende?
- RN-002, RN-013 y RN-014.

## 10. Limitaciones
- Los precios pedidos no son ventas concretadas; por eso se aplica el margen de negociación.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| No hay comparables en la zona | Sin techo; se usa el estimado y se marca "sin comparables locales" |
| No hay estimado ni precio de mercado hoy | No hay precio local → canal local no viable |

## 12. Preguntas para el experto
1. ¿85% del precio de mercado es una estimación razonable para vender en persona?
2. ¿Cuánto se suele ceder al negociar en venta local? (propuesta: 10%)

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-11 | Venta directa con precio estimado que captura Jesús o porcentaje del precio de mercado, marcado "estimado" (DEC-140) | Jesús |
| 2026-11-11 | Venta local = OfferUp, Marketplace y venta personal juntas (DEC-151) | Jesús |

## 14. Revisión de consistencia
- Última revisión: ver `revisiones/RN-016.md`
- Detalle: [revisiones/RN-016.md](/revisiones/RN-016.md)
