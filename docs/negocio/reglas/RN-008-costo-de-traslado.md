# RN-008 — Costo de traslado: viajes de compra y entregas

```yaml
id: RN-008
titulo: Costo de traslado: viajes de compra y entregas
grupo: común
estado: EN_REVISION
version: 2
fecha: 2026-11-16
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-005, RN-007, RN-009]
```

> **Qué cambió en la v2 (2026-11-16):** criterio de Jesús: **entre más cerca de la frontera, mejor**. La zona se mide en **km desde la garita** en tres anillos, con ganancia mínima por viaje escalonada ($50 / $75 / $150); el tiempo cuenta como costo **incluida la espera en la garita**; oportunidades en espera 2 días (1 en liquidación); límite de unidades por cliente. Se agregan las **entregas de la venta local** y el **doble traslado** con particulares, con las mismas tarifas (DEC-142, DEC-148). Propuestas de Claude aceptadas por Jesús, [sesión 2](/sesiones/sesion-2-respuestas.md), bloque 8; por validar con el experto. La v1 queda en el historial: [RN-008 v1](https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/blob/1c1d4e04d5e5e2401dbb565782bf11061d8813f7/docs/negocio/reglas/RN-008-costo-de-traslado.md).

## 1. ¿Qué queremos lograr?
Decidir si **vale la pena el viaje** a una tienda física, tomando en cuenta gasolina, el cruce de la frontera y el tiempo de Jesús, y saber cuánto cuesta **entregar** un producto en la venta local. Entre más cerca de la frontera, mejor.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Zonas por distancia desde la garita.
- Costo del viaje de compra: kilómetros, manejo, espera en la garita y tiempo en tienda.
- Juntar varias oportunidades en un solo viaje (ruta).
- Costo de entrega en la venta local y traslados con particulares.
- Reglas prácticas de comprar en tiendas de EE. UU. para revender.

**No incluye:**
- Costos de importación o cruce para la venta, incluida la **franquicia aduanal** al pasar mercancía a México: fuera del modelo por decisión C-14. Conviene que Jesús lo tenga presente.
- Compras en línea (llegan al PO Box, RN-001).

## 3. ¿Cómo funciona, en palabras?
Cada tienda tiene una zona según qué tan lejos está de la garita. Se suma la ganancia ajustada (RN-005) de todas las oportunidades con nivel (RN-009) en las tiendas de una ruta y se le resta lo que cuesta el viaje. Si lo que queda supera la ganancia mínima de la zona, el sistema recomienda ir. Las entregas de venta local se cobran con las mismas tarifas de kilómetro y hora.

## 4. La regla

**4.1 Zonas** (km en línea de manejo desde la garita más cercana: San Ysidro u Otay Mesa)

| Zona | Distancia | Ejemplos | Ganancia mínima por viaje |
|---|---|---|---|
| **Zona 1** | hasta 20 km | San Ysidro, Otay, Chula Vista, National City | **$50** |
| **Zona 2** | más de 20 y hasta 40 km | Resto del área central de San Diego | **$75** |
| **Lejos** | más de 40 km | Los Ángeles | **$150**, y solo entonces se avisa |

- La lista de tiendas de cada zona **se arma sola** con esa distancia.
- En una ruta con tiendas de varias zonas, manda la **zona más lejana**.
- Con igual ganancia, se prefiere la tienda más cercana.

**4.2 Viaje de compra**

```
horas del viaje    = horas de manejo (ida y vuelta) + horas de espera en la garita + 0.5 h por cada tienda
costo del viaje    = km totales × costo por km + horas del viaje × valor de la hora + costos fijos
ganancia del viaje = Σ (margen ajustado por unidad × unidades recomendadas) de las oportunidades de la ruta
                     − costo del viaje
```

- Solo cuentan oportunidades con nivel (RN-009) y confianza Alta o Media (RN-007).
- **Vale la pena** si la ganancia del viaje alcanza la ganancia mínima de su zona.
- **En espera:** una oportunidad que sola no paga el viaje se conserva **2 días** (en liquidación, **1 día**) por si aparece otra en la misma zona. Antes de salir se vuelve a consultar (RN-007, RN-010).

**4.3 Entregas y traslados de la venta local**

```
costo de entrega = km (ida y vuelta) × costo por km + horas × valor de la hora + costos fijos
```

- Se suma al costo de venta del canal local (RN-001).
- **Compra a particulares** (RN-014): recoger el producto es un traslado más, que se suma al costo de compra. Con particulares hay **doble traslado**: recoger y entregar.

**4.4 Comprar en tiendas de EE. UU. para revender**
- **Límite de unidades por cliente:** frecuente en liquidaciones y temporada; se registra por comercio y topa las unidades recomendadas (RN-005).
- **Devoluciones:** muchas tiendas exigen el ticket; se guarda el comprobante de cada compra.
- **Impuesto de venta** de la ciudad de la tienda: ya está en RN-001.

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Costo por km | Gasolina y desgaste | $0.20 | DEC-142, DEC-148 |
| Valor de la hora | Tiempo de Jesús, **incluida la espera en la garita** | $15 | Jesús; aceptado (sesión 2) |
| Espera en la garita | Ida y vuelta, configurable por día y hora | 1.5 h | Por confirmar con datos reales |
| Tiempo por tienda | Dentro de cada tienda | 0.5 h | Por confirmar |
| Costos fijos | Estacionamiento, cuotas | $0 | Por confirmar |
| Límites de zona | km desde la garita | 20 / 40 | Aceptado por Jesús |
| Ganancia mínima por zona | Por viaje | $50 / $75 / $150 | Aceptado por Jesús |
| Días en espera | Normal / liquidación | 2 / 1 | Aceptado por Jesús |

Todos los valores son iniciales y configurables.

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Costo de un viaje típico a Home Depot Chula Vista** (Zona 1; 50 km ida y vuelta desde Tijuana, 1 h de manejo, 1 tienda):
- Horas = 1 + 1.5 + 0.5 = **3 h**.
- Costo = 50 × 0.20 + 3 × 15 + 0 = 10 + 45 = **$55**.

**Ejemplo A — Vale la pena**
- Sierra circular: margen ajustado $44.73 por unidad × 3 unidades = **$134.19**.
- Ganancia del viaje = 134.19 − 55 = **$79.19** ≥ $50 (Zona 1) → **recomienda ir**.

**Ejemplo B — No vale la pena (en espera)**
- Una oportunidad con margen ajustado de $12 por unidad × 2 unidades = **$24**.
- Ganancia del viaje = 24 − 55 = **−$31** → no recomienda ir; queda **en espera 2 días**.

**Ejemplo C — Ruta con una tienda de Zona 2**
- La del ejemplo B ($24) más otra en Zona 2 de $70 (2 tiendas, 60 km, 1.2 h de manejo).
- Horas = 1.2 + 1.5 + 0.5 × 2 = **3.7 h**. Costo = 60 × 0.20 + 3.7 × 15 = 12 + 55.50 = **$67.50**.
- Ganancia = 24 + 70 − 67.50 = **$26.50** < $75 (manda la Zona 2) → todavía no conviene.

**Ejemplo D — Lejos**
- Tienda en Los Ángeles: 400 km ida y vuelta, 6 h de manejo, 1 tienda. Horas = 6 + 1.5 + 0.5 = 8 h. Costo = 400 × 0.20 + 8 × 15 = 80 + 120 = **$200**.
- Oportunidades por $380 → ganancia = 380 − 200 = **$180** ≥ $150 → **se avisa**. Con $300 → $100 → solo tablero.

**Ejemplo E — Entrega local**
- 10 km ida y vuelta y 30 minutos: 10 × 0.20 + 0.5 × 15 = 2.00 + 7.50 = **$9.50** (DEC-142).

**Ejemplo F — Doble traslado con un particular**
- Recoger: $9.50. Entregar: $9.50 → **$19.00** de traslados (CASO-006).

## 6. ¿Qué información necesitamos?
- Ubicación de cada tienda, distancia a la garita y tiempo de manejo desde Tijuana.
- Espera estimada en la garita.
- Límites de unidades por cliente que se vayan detectando.
- Resultados de RN-005, RN-007 y RN-009.

## 7. ¿Qué obtenemos?
- Zona de cada tienda, costo y ganancia del viaje, recomendación (ir / no ir / en espera) y costo de cada entrega local.

## 8. ¿Quién participa?
- El sistema calcula y recomienda.
- Jesús fija tarifas y mínimos y decide si va.

## 9. ¿De qué depende?
- RN-005 (margen ajustado y unidades), RN-007 (confianza) y RN-009 (nivel).

## 10. Limitaciones
- La espera en la garita varía mucho por día y hora. Al inicio es un promedio; con el tiempo usa el historial real de cada viaje.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| No se conoce la distancia a una tienda nueva | Pide registrarla antes de recomendar |
| La confianza baja a "Baja" antes del viaje | Saca esa oportunidad de la ruta y recalcula |
| La ruta tiene más de 4 tiendas | Recomienda partirla en dos viajes |
| Pasa el tiempo de espera sin juntar ganancia | La oportunidad sale de la ruta |

## 12. Preguntas para el experto
1. ¿Le parecen bien las tres zonas por distancia a la garita y sus mínimos de $50, $75 y $150? (propuesta aceptada por Jesús)
2. ¿2 días de espera (1 en liquidación)? (propuesta aceptada por Jesús)

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-08 | Zona inicial de compra en tienda: San Diego; más lejos solo si la ganancia lo justifica | Jesús |
| 2026-11-11 | Entregas de venta local con las mismas tarifas (DEC-142, DEC-148) | Jesús |
| 2026-11-16 | Entre más cerca de la frontera, mejor | Jesús |
| 2026-11-16 | El tiempo cuenta como costo, incluida la espera en la garita | Jesús (propuesta de Claude) |
| 2026-11-16 | Zonas por km desde la garita: 20 / 40; mínimos $50 / $75 / $150 | Jesús (propuesta de Claude) |
| 2026-11-16 | Lejos: aviso solo con $150 o más | Jesús (propuesta de Claude) |
| 2026-11-16 | En espera 2 días; 1 en liquidación | Jesús (propuesta de Claude) |
| 2026-11-16 | Límite por cliente, devoluciones con ticket; franquicia aduanal fuera del modelo | Jesús (propuesta de Claude) |

## 14. Revisión de consistencia
- Última revisión: ver `revisiones/RN-008.md` (columna v2)
- Detalle: [revisiones/RN-008.md](/revisiones/RN-008.md)
