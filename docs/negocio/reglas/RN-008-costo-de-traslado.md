# RN-008 — Costo de traslado y viaje de compra

```yaml
id: RN-008
titulo: Costo de traslado y viaje de compra
estado: BORRADOR
version: 1
fecha: 2026-11-08
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-005, RN-007, RN-009]
```

## 1. ¿Qué queremos lograr?
Decidir si **vale la pena el viaje** a una tienda física, tomando en cuenta gasolina, el tiempo de cruce y el tiempo de Jesús. Una buena oferta de una sola unidad puede no pagar el viaje; varias oportunidades en la misma zona, sí.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Costo del viaje: kilómetros, horas de manejo, cruce fronterizo y tiempo en tienda.
- Juntar varias oportunidades en un solo viaje (ruta).
- Tiendas dentro y fuera de la zona de San Diego.

**No incluye:**
- Costos de importación o cruce para la venta (decisión tomada: fuera del modelo).
- Compras en línea.

## 3. ¿Cómo funciona, en palabras?
Se suma la ganancia ajustada (RN-005) de todas las oportunidades que pasaron su nivel (RN-009) en las tiendas de una ruta. A esa suma se le resta lo que cuesta el viaje. Si lo que queda supera una ganancia mínima por viaje, el sistema recomienda ir.

## 4. La regla

```
horas del viaje    = horas de manejo (ida y vuelta) + horas de cruce + 0.5 h por cada tienda
costo del viaje    = km totales × costo por km + horas del viaje × valor de la hora + costos fijos
ganancia del viaje = Σ (margen ajustado por unidad × unidades recomendadas) de las oportunidades de la ruta
                     − costo del viaje
```

- Solo cuentan oportunidades con nivel (RN-009) y confianza de tienda Alta o Media (RN-007).
- **Vale la pena** si la ganancia del viaje es ≥ **$50** dentro de la zona de San Diego, o ≥ **$150** fuera de ella.

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Costo por km | Gasolina y desgaste | $0.20 | Por confirmar |
| Valor de la hora | Cuánto vale el tiempo de Jesús | $15 | Decisión de Jesús |
| Horas de cruce | Ida y vuelta, promedio | 1.5 h | Por confirmar con datos reales |
| Tiempo por tienda | Dentro de cada tienda | 0.5 h | Por confirmar |
| Costos fijos | Estacionamiento, cuotas | $0 | Por confirmar |
| Ganancia mínima en zona San Diego | Por viaje | $50 | Decisión de Jesús |
| Ganancia mínima fuera de zona | Por viaje | $150 | Decisión de Jesús |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Costo de un viaje típico a Home Depot Chula Vista** (50 km ida y vuelta, 1 h de manejo, 1 tienda):
- Horas = 1 + 1.5 + 0.5 = **3 h**.
- Costo = 50 × 0.20 + 3 × 15 + 0 = 10 + 45 = **$55**.

**Ejemplo A — Vale la pena**
- Sierra circular: margen ajustado $45.92 por unidad × 3 unidades = **$137.76**.
- Ganancia del viaje = 137.76 − 55 = **$82.76** (≥ $50) → **recomienda ir**.

**Ejemplo B — No vale la pena**
- Una oportunidad con margen ajustado de $12 por unidad × 2 unidades = **$24**.
- Ganancia del viaje = 24 − 55 = **−$31** → **no recomienda ir** (queda en espera por si aparece otra oportunidad en la misma zona).

**Ejemplo C — Se juntan en ruta**
- La del ejemplo B ($24) más otra en una tienda cercana de $70 (2 tiendas, 60 km, 1.2 h de manejo).
- Horas = 1.2 + 1.5 + 0.5 × 2 = **3.7 h**. Costo = 60 × 0.20 + 3.7 × 15 = 12 + 55.50 = **$67.50**.
- Ganancia = 24 + 70 − 67.50 = **$26.50** (< $50) → todavía no conviene.

## 6. ¿Qué información necesitamos?
- Ubicación de cada tienda, distancia y tiempo de manejo desde Tijuana.
- Tiempo de cruce estimado.
- Resultados de RN-005, RN-007 y RN-009.

## 7. ¿Qué obtenemos?
- Costo del viaje, ganancia del viaje y recomendación: ir / no ir / esperar a juntar más.

## 8. ¿Quién participa?
- El sistema calcula y recomienda.
- Jesús fija el valor de su hora y las ganancias mínimas, y decide si va.

## 9. ¿De qué depende?
- RN-005 (margen ajustado y unidades), RN-007 (confianza) y RN-009 (nivel).

## 10. Limitaciones
- El tiempo de cruce varía mucho por día y hora. Al inicio es un promedio fijo; con el tiempo puede usar el historial real de cada viaje.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| No se conoce la distancia a una tienda nueva | Pide registrarla antes de recomendar |
| La confianza baja a "Baja" antes del viaje | Saca esa oportunidad de la ruta y recalcula |
| La ruta tiene más de 4 tiendas | Recomienda partirla en dos viajes |

## 12. Preguntas para el experto
1. ¿Le parece correcto considerar el tiempo como costo o solo los gastos directos?
2. ¿$50 de ganancia mínima por viaje es razonable para empezar?
3. ¿Hay algo de comprar en tiendas de EE. UU. para revender que debamos considerar (límites de compra por cliente, políticas de la tienda)?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-08 | Zona inicial de compra en tienda: San Diego; más lejos solo si la ganancia lo justifica | Jesús |

## 14. Revisión de consistencia
- Última revisión: 2026-11-08 — APROBADO CON OBSERVACIONES
- Detalle: [revisiones/RN-008.md](/revisiones/RN-008.md)
