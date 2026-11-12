# RN-016 — Precio de venta local

```yaml
id: RN-016
titulo: Precio de venta local
grupo: local
estado: BORRADOR
version: 1
fecha: 2026-11-11
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-002, RN-013, RN-014]
```

## 1. ¿Qué queremos lograr?
Estimar **a cuánto se puede vender** un producto en **venta local** (OfferUp, Facebook Marketplace o venta directa) **sin sobreestimarlo**. Lo que piden otros vendedores no es lo que se paga, y un comprador local también puede comprar en línea: si la tienda lo tiene a $169, nadie paga $200 en Marketplace.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- El precio al que conviene **publicar** y el precio de venta **esperado** después de negociar.
- Productos nuevos y usados (RN-014).
- Las tres plataformas de venta local juntas, como un solo canal en el Inc. 1 (DEC-151).

**No incluye:**
- El precio de venta en Amazon (RN-002).
- La demanda local (RN-017).
- Costos de entrega (RN-008) y margen (RN-001).
- Venta con envío por la plataforma: en el Inc. 1 la venta local es **en persona**.

## 3. ¿Cómo funciona, en palabras?
Se toman las referencias que existan y se usa **la más baja**, para no inflar la ganancia: lo que piden otros vendedores en la zona (un poco abajo, para competir), lo que cuesta nuevo en las tiendas (un poco abajo, porque si no el comprador va a la tienda) y lo que Jesús estime. A ese precio de publicación se le resta lo que suele bajar en la negociación. Si hay ventas concretadas registradas, el precio esperado tampoco puede pasar de ellas.

## 4. La regla

```
precio de publicación = el MÁS BAJO de las referencias que existan:
  · techo local:        menor precio pedido comparable en la zona × (1 − 5%)
  · tope de tienda:     precio de mercado hoy del producto nuevo (RN-002) × (1 − 10%)   [solo si se vende nuevo]
  · valor de usado:     valor de referencia de RN-014                                    [solo si se vende usado]
  · estimado de Jesús:  precio que Jesús capture (DEC-140)

precio de venta esperado = el MÁS BAJO entre:
  · precio de publicación × (1 − margen de negociación)
  · mediana de ventas concretadas comparables (90 días, al menos 3; DEC-161)   [si existe]
```

- **Comparable:** mismo producto exacto (RN-013) y misma condición (RN-014).
- **Zona:** solo cuentan publicaciones de la zona de venta; las de otras ciudades no (CASO-005).
- **Fuente de los datos:** las publicaciones de particulares y las ventas concretadas de eBay las **captura Jesús** (DEC-150, DEC-161).
- Si el precio esperado sale solo del estimado de Jesús, se marca **"estimado"**.
- **Voluminosos o pesados:** excluidos en el Inc. 1 (DEC-159).

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Descuento para competir | Bajo el menor precio pedido | 5% | Por confirmar |
| Tope contra tienda | Bajo el precio de mercado hoy del nuevo | 10% | Por confirmar |
| Margen de negociación | Lo que suele bajar el comprador | 10% | Por confirmar |
| Ventas concretadas mínimas | Para usar su mediana | 3 en 90 días | Por confirmar |
| Zona de venta local | Dónde se vende en persona | San Diego y Tijuana | **Por confirmar** (pregunta 3) |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Baterías DEWALT nuevas (CASO-007, datos supuestos)**
- Menor precio pedido en la zona: $120 → techo local = 120 × 0.95 = **$114.00**.
- Precio de mercado hoy del nuevo en otros comercios: $169 → tope de tienda = 169 × 0.90 = **$152.10**.
- Precio de publicación = mínimo(114.00, 152.10) = **$114.00**.
- Después de negociar: 114.00 × 0.90 = **$102.60**. Ventas concretadas en eBay: $105, $110, $115 → mediana **$110**.
- Precio de venta esperado = mínimo(102.60, 110) = **$102.60**.

**Ejemplo B — Baterías Milwaukee (CASO-005)**
- Menor precio pedido en la zona: $99 (Vista, CA; Houston no cuenta) → techo = 99 × 0.95 = **$94.05**. Tope de tienda: 269 × 0.90 = $242.10.
- Precio de publicación = **$94.05** → esperado = 94.05 × 0.90 = **$84.65**.
- Con compra a $120 más impuesto ($129.30, RN-008), no hay margen.

**Ejemplo C — Solo el estimado de Jesús**
- Sin publicaciones ni ventas registradas. Jesús estima $110 → publicación $110 → esperado = 110 × 0.90 = **$99.00**, marcado "estimado".

**Ejemplo D — Sin referencias**
- Nada registrado y Jesús no estima → **sin precio de venta local** → la oportunidad queda en revisión manual.

## 6. ¿Qué información necesitamos?
- Publicaciones comparables en la zona: precio pedido, condición, fecha (captura de Jesús).
- Ventas concretadas comparables (eBay u otras, captura de Jesús).
- Precio de mercado hoy del producto nuevo (RN-002) o valor de usado (RN-014).
- El estimado de Jesús, cuando lo dé.

## 7. ¿Qué obtenemos?
- Precio de publicación sugerido y precio de venta esperado, con la referencia que lo fijó y la marca "estimado" si aplica.

## 8. ¿Quién participa?
- El sistema calcula.
- Jesús captura publicaciones, ventas concretadas y su estimado.

## 9. ¿De qué depende?
- RN-002, RN-013 y RN-014.
- La usan RN-001, RN-005 y RN-018.

## 10. Limitaciones
- Al inicio casi todo dependerá de lo que capture Jesús: OIP no consulta plataformas de particulares (DEC-150).
- La negociación real varía mucho por producto y comprador; 10% es un punto de partida.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| Solo hay publicaciones de otras ciudades | No hay techo local; se usan las demás referencias |
| El precio pedido más bajo parece un error (mucho más bajo que el resto) | Se usa igual y se marca para que Jesús lo revise |
| Las ventas concretadas son más altas que el precio de publicación | Gana el precio de publicación negociado (el más bajo) |
| El producto es voluminoso | No se evalúa (DEC-159) |

## 12. Preguntas para el experto
1. ¿Cuánto suele bajar un comprador en OfferUp o Marketplace? ¿10% es razonable?
2. ¿Cuánto por debajo de la tienda hay que publicar un producto nuevo para que se venda en persona?
3. *(Para Jesús)* ¿La venta local es en San Diego, en Tijuana o en ambas? Si es en Tijuana, ¿se vende en dólares o en pesos?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-11 | Canales por oportunidad; venta directa con precio estimado (DEC-140) | Jesús |
| 2026-11-11 | Venta local agrupa OfferUp, Marketplace y venta personal en el Inc. 1 (DEC-151) | Jesús |
| 2026-11-11 | Ventas concretadas de eBay como dato, con captura manual (DEC-161) | Jesús |

## 14. Revisión de consistencia
- Última revisión: 2026-11-11 (v1) — APROBADO CON OBSERVACIONES.
- Detalle: [revisiones/RN-016.md](/revisiones/RN-016.md)
