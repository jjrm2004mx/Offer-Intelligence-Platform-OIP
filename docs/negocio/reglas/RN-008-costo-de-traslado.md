# RN-008 — Costo de adquisición y traslados

```yaml
id: RN-008
titulo: Costo de adquisición y traslados
grupo: común
estado: BORRADOR
version: 2
fecha: 2026-11-11
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-005, RN-007, RN-009]
version_anterior: https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/blob/5a4744d15b2ac6439f2cd89d25cb377ab437ab36/docs/negocio/reglas/RN-008-costo-de-traslado.md
```

## 1. ¿Qué queremos lograr?
Saber **cuánto cuesta realmente adquirir** un producto y decidir si **vale la pena el viaje**: a una tienda física, a recoger con un particular o a entregarle a un comprador. Se toman en cuenta gasolina, el tiempo de cruce y el tiempo de Jesús. Una buena oferta de una sola unidad puede no pagar el viaje; varias oportunidades en la misma zona, sí.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- **Costo de adquisición por unidad:** precio, impuesto de venta y envío (nuevo en la v2).
- **Costo del viaje de compra:** kilómetros, horas de manejo, cruce fronterizo y tiempo en cada parada (igual que la v1).
- Paradas en **tiendas** y, nuevo en la v2, **puntos de encuentro con particulares**.
- **Costo de entrega** en venta local (nuevo en la v2, DEC-142 y DEC-148).
- Juntar varias oportunidades en un solo viaje (ruta), dentro y fuera de la zona de San Diego.

**No incluye:**
- Costos de importación o cruce para la venta (decisión tomada: fuera del modelo).
- El costo total que ve un cliente en la búsqueda por artículo (RN-011).

## 3. ¿Cómo funciona, en palabras?
Cada unidad cuesta su precio más el impuesto de venta de donde se compra, más el envío si es en línea. Los viajes se calculan **por ruta**, no por unidad: se suma la ganancia ajustada (RN-005) de todas las oportunidades que pasaron su nivel (RN-009) en las paradas de una ruta, y se le resta lo que cuesta el viaje. Si lo que queda supera una ganancia mínima por viaje, el sistema recomienda ir. Las entregas de venta local se calculan con las mismas tarifas.

## 4. La regla

```
costo de adquisición por unidad = precio + impuesto de venta + envío (si es en línea)
impuesto de venta               = precio × tasa del lugar de compra (particulares: 0)

horas del viaje    = horas de manejo (ida y vuelta) + horas de cruce (si se cruza) + 0.5 h por cada parada
costo del viaje    = km totales × costo por km + horas del viaje × valor de la hora + costos fijos
ganancia del viaje = Σ (margen ajustado por unidad × unidades recomendadas) de las oportunidades de la ruta
                     − costo del viaje

costo de entrega (venta local) = km × costo por km + horas × valor de la hora
                                 (+ horas de cruce si el comprador está del otro lado)
```

- Una **parada** es una tienda o un punto de encuentro con un particular.
- Solo cuentan oportunidades con nivel (RN-009) y confianza de tienda Alta o Media, o publicación vigente de particular (RN-007).
- **Vale la pena** si la ganancia del viaje es ≥ **$50** dentro de la zona de San Diego, o ≥ **$150** fuera de ella.
- Si una entrega se junta con un viaje de compra, se suma como parada de ese viaje y no se cobra aparte.

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Costo por km | Gasolina y desgaste | $0.20 | Por confirmar |
| Valor de la hora | Cuánto vale el tiempo de Jesús | $15 | Decisión de Jesús |
| Horas de cruce | Ida y vuelta, promedio | 1.5 h | Por confirmar con datos reales |
| Tiempo por parada | En cada tienda o encuentro | 0.5 h | Por confirmar |
| Costos fijos | Estacionamiento, cuotas | $0 | Por confirmar |
| Tasa de impuesto de venta | Zona de San Diego | 7.75% | **Por confirmar** (varía por ciudad; y si existe un permiso de reventa que lo exente) |
| Ganancia mínima en zona San Diego | Por viaje | $50 | Decisión de Jesús |
| Ganancia mínima fuera de zona | Por viaje | $150 | Decisión de Jesús |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Costo de un viaje típico a Home Depot Chula Vista** (de la v1; 50 km ida y vuelta, 1 h de manejo, 1 tienda):
- Horas = 1 + 1.5 + 0.5 = **3 h**.
- Costo = 50 × 0.20 + 3 × 15 + 0 = 10 + 45 = **$55**.

**Ejemplo A — Vale la pena (de la v1)**
- Sierra circular: margen ajustado $45.92 por unidad × 3 unidades = **$137.76**.
- Ganancia del viaje = 137.76 − 55 = **$82.76** (≥ $50) → **recomienda ir**.

**Ejemplo B — No vale la pena (de la v1)**
- Una oportunidad con margen ajustado de $12 por unidad × 2 unidades = **$24**.
- Ganancia del viaje = 24 − 55 = **−$31** → **no recomienda ir** (queda en espera por si aparece otra oportunidad en la misma zona).

**Ejemplo C — Se juntan en ruta (de la v1)**
- La del ejemplo B ($24) más otra en una tienda cercana de $70 (2 tiendas, 60 km, 1.2 h de manejo).
- Horas = 1.2 + 1.5 + 0.5 × 2 = **3.7 h**. Costo = 60 × 0.20 + 3.7 × 15 = 12 + 55.50 = **$67.50**.
- Ganancia = 24 + 70 − 67.50 = **$26.50** (< $50) → todavía no conviene.

**Ejemplo D — Costo de adquisición con impuesto (nuevo)**
- Baterías DEWALT en Home Depot San Diego: $79. Impuesto = 79 × 7.75% = **$6.12**. Costo de adquisición = **$85.12** por unidad.

**Ejemplo E — Recoger con un particular cuesta como un viaje (nuevo, CASO-006)**
- DCF840 en San Diego: 40 km ida y vuelta, 0.8 h de manejo, 1 encuentro.
- Horas = 0.8 + 1.5 + 0.5 = **2.8 h**. Costo = 40 × 0.20 + 2.8 × 15 = 8 + 42 = **$50.00**.
- Si es el único motivo del viaje, se come casi todo el margen: hay que juntarlo en ruta con otras compras.

**Ejemplo F — Entrega en venta local (nuevo, DEC-142)**
- Comprador en Tijuana, 10 km y 0.5 h → 10 × 0.20 + 0.5 × 15 = **$9.50**, sin cruce.

## 6. ¿Qué información necesitamos?
- Ubicación de cada tienda o punto de encuentro, distancia y tiempo de manejo desde Tijuana.
- Tiempo de cruce estimado.
- Tasa de impuesto de venta por lugar de compra.
- Costo de envío de las compras en línea.
- Resultados de RN-005, RN-007 y RN-009.

## 7. ¿Qué obtenemos?
- Costo de adquisición por unidad.
- Costo del viaje, ganancia del viaje y recomendación: ir / no ir / esperar a juntar más.
- Costo de entrega de cada venta local.

## 8. ¿Quién participa?
- El sistema calcula y recomienda.
- Jesús fija el valor de su hora y las ganancias mínimas, y decide si va.

## 9. ¿De qué depende?
- RN-005 (margen ajustado y unidades), RN-007 (confianza y vigencia) y RN-009 (nivel).

## 10. Limitaciones
- El tiempo de cruce varía mucho por día y hora. Al inicio es un promedio fijo; con el tiempo puede usar el historial real de cada viaje.
- Desde Tijuana, **cualquier parada en San Diego** paga el cruce: las compras a particulares solo convienen juntas con otras paradas o con márgenes altos.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| No se conoce la distancia a una tienda o punto nuevo | Pide registrarla antes de recomendar |
| La confianza baja a "Baja" antes del viaje, o la publicación deja de estar vigente | Saca esa oportunidad de la ruta y recalcula |
| La ruta tiene más de 4 paradas | Recomienda partirla en dos viajes |
| No se conoce la tasa de impuesto del lugar | Usa la de la zona de San Diego y lo marca |

## 12. Preguntas para el experto
1. *(De la v1)* ¿Le parece correcto considerar el tiempo como costo o solo los gastos directos?
2. *(De la v1)* ¿$50 de ganancia mínima por viaje es razonable para empezar?
3. *(De la v1)* ¿Hay algo de comprar en tiendas de EE. UU. para revender que debamos considerar (límites de compra por cliente, políticas de la tienda)?
4. ¿Conviene tramitar un permiso de reventa (*resale certificate*) para no pagar impuesto de venta al comprar? ¿Aplica a alguien que vive en México?
5. ¿Hay puntos de encuentro habituales para compraventa entre particulares que reduzcan el tiempo?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-08 | Zona inicial de compra en tienda: San Diego; más lejos solo si la ganancia lo justifica | Jesús |
| 2026-11-11 | El costo de entrega en venta local usa estas mismas tarifas (DEC-142, DEC-148) | Jesús |

**Cambios de la v2 contra la v1:** se agregan el costo de adquisición por unidad (con impuesto de venta y envío), las paradas con particulares y el costo de entrega de venta local, con los ejemplos D, E y F. La regla del viaje y los ejemplos de la v1 quedan iguales. La v1 excluía compras en línea; ahora su costo de adquisición incluye el envío.

## 14. Revisión de consistencia
- Última revisión: 2026-11-11 (v2) — **APROBADO CON OBSERVACIONES**. Revisión anterior: 2026-11-08 (v1) — APROBADO CON OBSERVACIONES.
- Detalle: [revisiones/RN-008.md](/revisiones/RN-008.md)
