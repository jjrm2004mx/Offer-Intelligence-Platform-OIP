# RN-005 — Rentabilidad ajustada por tiempo y riesgo, por canal

```yaml
id: RN-005
titulo: Rentabilidad ajustada por tiempo y riesgo, por canal
grupo: resultado
estado: EN_REVISION
version: 2
fecha: 2026-11-16
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-001, RN-002, RN-004, RN-007, RN-008, RN-009, RN-017]
```

> **Qué cambió en la v2 (2026-11-16):** el canal es un parámetro (DEC-143); tasas de devolución por categoría tomadas de los umbrales que publica Amazon; pérdida por devolución de 75% en perfumes y joyería; **30 días** de pago para vendedor nuevo (Amazon retiene el dinero hasta 7 días después de la entrega desde el 12-mar-2026); tope de **3 unidades** (5 en casos muy buenos) en la primera compra; el tiempo se cuenta **hasta vender la última unidad**. Propuestas de Claude aceptadas por Jesús, [sesión 2](/sesiones/sesion-2-respuestas.md), bloque 5; por validar con el experto. La v1 queda en el historial: [RN-005 v1](https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/blob/1c1d4e04d5e5e2401dbb565782bf11061d8813f7/docs/negocio/reglas/RN-005-rentabilidad-ajustada-por-tiempo.md).

## 1. ¿Qué queremos lograr?
Que la ganancia sea **real, no aparente**. Un margen alto que tarda meses en convertirse en dinero, o que se lo comen las devoluciones o una baja de precio, vale menos que un margen moderado que se cobra en semanas.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Ajustar el margen por devoluciones esperadas y por el riesgo de que baje el precio.
- Recomendar cuántas unidades comprar.
- Estimar en cuántos días se recupera el dinero y un rendimiento mensual para **ordenar** oportunidades.
- Todo, por canal: Amazon FBM y venta local.

**No incluye:**
- El costo del viaje a tienda (RN-008).
- Elegir el canal (RN-018).

## 3. ¿Cómo funciona, en palabras?
1. Al margen neto del canal (RN-001) se le restan dos riesgos: lo que se espera perder por devoluciones y la mitad de lo que podría bajar el precio.
2. Con ese margen ajustado se asigna el nivel (RN-009).
3. Se decide cuántas unidades comprar, con un tope prudente mientras se aprende.
4. Se estima cuánto tarda en venderse **la última unidad**, más lo que tarda el canal en pagar.
5. Con eso se calcula cuánto rinde el dinero por mes.

## 4. La regla

```
costo por devoluciones = precio de venta esperado × tasa de devolución × pérdida por devolución
castigo por baja       = (precio de venta esperado − mínimo de 60 días en Amazon) × 50%   (si sale negativo, 0)
margen ajustado ($)    = margen neto − costo por devoluciones − castigo por baja
margen ajustado (%)    = margen ajustado ($) ÷ costo de compra × 100

unidades recomendadas  = el MENOR entre:
                           · ventas al mes que le tocan a Jesús
                             (Amazon: ventas al mes ÷ (vendedores + 1); local: RN-017), redondeado hacia abajo
                           · unidades disponibles
                           · límite de unidades por cliente del comercio (RN-008), si lo hay
                           · tope de primera compra: 3 (5 si el ranking es menor de 10,000
                             y el nivel en ese canal es Comprar ya o Muy recomendable)

días de venta          = el MAYOR entre:
                           · días de la tabla (Amazon) o días por unidad de RN-017 × unidades (local)
                           · unidades ÷ (ventas al mes que le tocan a Jesús ÷ 30)
días para recuperar    = días de venta + días de pago del canal
rendimiento mensual    = margen ajustado (%) × 30 ÷ días para recuperar
```

**Valores por canal:**

| Valor | Amazon FBM | Venta local |
|---|---|---|
| Tasa de devolución | Herramientas 7%, hogar 8%, perfumes y belleza 6%, joyería 11%, relojes 12%, tecnología 11%, juguetes 5% | 0% (se revisa al entregar) |
| Pérdida por devolución | 50%; perfumes y joyería 75% | — |
| Castigo por baja | 50% de (venta − mínimo de 60 días en Amazon); sin mínimo, 10% del precio de venta | Igual |
| Días de pago | **30** con cuenta nueva; **21** con historial | 0 (pago al entregar) |
| Días de venta | Tabla por ranking (abajo) | RN-017 |

**Días de venta en Amazon según el ranking** (herramientas; otras categorías se calibran con resultados):

| Ranking | Días estimados de venta |
|---|---|
| menos de 10,000 | 7 |
| 10,000 a 50,000 | 21 |
| más de 50,000, hasta el umbral de RN-004 | 45 |

- El **tope de primera compra** se levanta para un producto cuando ya se vendió (registro de resultados).
- Las tasas de devolución de Amazon son los **umbrales por categoría que publica Amazon** (desde jun-2024), redondeados: por encima de ellos Amazon cobra una cuota extra, así que son conservadores.

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Tasas de devolución | Ver tabla | Ver tabla | Aceptado por Jesús; tecnología y juguetes: **propuesta nueva** con el mismo criterio |
| Pérdida por devolución | Ver tabla | 50% / 75% | Aceptado por Jesús |
| Peso del castigo por baja | Parte de la posible baja | 50% | Aceptado por Jesús |
| Días de pago Amazon | Cuenta nueva / con historial | 30 / 21 | Aceptado por Jesús |
| Tope de primera compra | Unidades | 3; 5 en casos muy buenos | Aceptado por Jesús |
| Hasta qué unidad se cuenta | Primera o última | Última | Aceptado por Jesús |
| Tasa de devolución local | % | 0% | **Propuesta nueva de Claude (por aceptar)** |

Todos los valores son iniciales y configurables.

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Taladro en Amazon**
- Margen neto (RN-001): $27.53. Costo de compra: $85.12. Venta esperada: $149. Mínimo de 60 días: $139.
- Devoluciones: 149 × 7% × 50% = **$5.22**. Castigo por baja: (149 − 139) × 50% = **$5.00**.
- Margen ajustado = 27.53 − 5.22 − 5.00 = **$17.31** → 17.31 ÷ 85.12 = **20.3%** → no alcanza nivel (RN-009).
- Unidades: 300 al mes ÷ (9 + 1) = 30; en tienda hay 4; tope 3 → **3 unidades**.
- Días de venta = mayor(7, 3 ÷ (30 ÷ 30) = 3) = **7**. Días para recuperar = 7 + 30 = **37**.
- Rendimiento mensual = 20.3% × 30 ÷ 37 = **16.5%**.

**Ejemplo B — Sierra circular en Amazon**
- Margen neto: 119 − 31.25 − 33.85 = **$53.90**.
- Devoluciones: 119 × 7% × 50% = **$4.17**. Castigo: (119 − 109) × 50% = **$5.00**.
- Margen ajustado = 53.90 − 4.17 − 5.00 = **$44.73** → 44.73 ÷ 31.25 = **143.1%** → nivel Muy recomendable (RN-009).
- Unidades: 200 al mes ÷ (5 + 1) = 33; en tienda hay 3; tope 5 (ranking 6,000 y Muy recomendable) → **3 unidades**.
- Días de venta = mayor(7, 3 ÷ (33 ÷ 30) = 2.7) = **7**. Recuperar = 7 + 30 = **37**.
- Rendimiento mensual = 143.1% × 30 ÷ 37 = **116.0%**.

**Ejemplo C — Taladro en venta local**
- Margen neto local (RN-001, ejemplo C): **$21.48**. Devoluciones: 0. Castigo: venta local $116.10 es menor que el mínimo de $139 → **0**.
- Margen ajustado = **$21.48** → **25.2%**.
- Demanda local media (RN-017): 14 días por unidad → 30 ÷ 14 = 2 ventas al mes; disponibles 4; tope 3 → **2 unidades**.
- Días de venta = mayor(14 × 2 = 28, 2 ÷ (2 ÷ 30) = 30) = **30**. Días de pago: 0 → recuperar **30**.
- Rendimiento mensual = 25.2% × 30 ÷ 30 = **25.2%**.

**Comparación:** el taladro parecía bueno en Amazon (32.3% de margen neto), pero ajustado queda en 20.3% y tarda 37 días en volver el dinero. En venta local rinde más (RN-018).

## 6. ¿Qué información necesitamos?
- Resultados de RN-001, RN-002, RN-004 y RN-017.
- Ventas al mes y vendedores en Amazon (los que muestre la ficha, RN-004).
- Unidades disponibles (RN-007) y límite por cliente del comercio (RN-008).

## 7. ¿Qué obtenemos?
- Por canal: margen ajustado ($ y %), unidades recomendadas, días para recuperar y rendimiento mensual.

## 8. ¿Quién participa?
- El sistema calcula.
- El experto valida tasas, días y criterio de unidades.
- Jesús decide cuánto comprar en realidad.

## 9. ¿De qué depende?
- RN-001, RN-002, RN-004, RN-007, RN-008 (límite por cliente), RN-009 (nivel, para el tope) y RN-017.

## 10. Limitaciones
- Los días de venta son una estimación gruesa hasta tener ventas reales; se ajustan con cada venta registrada.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| No hay dato de ventas al mes en Amazon | Recomienda máximo **2** unidades y lo marca como estimación |
| No hay mínimo de 60 días | Castigo por baja = 10% del precio de venta esperado |
| El margen ajustado sale negativo | No genera aviso |
| La demanda en Amazon es insuficiente | El canal Amazon no se calcula (RN-004); se evalúa la venta local |

## 12. Preguntas para el experto
1. ¿Le parecen bien las tasas de devolución por categoría y la pérdida de 50% (75% en perfumes y joyería)? (propuesta aceptada por Jesús)
2. ¿30 días de pago con cuenta nueva y 21 con historial? (propuesta aceptada por Jesús)
3. ¿Tope de 3 unidades en la primera compra (5 en casos muy buenos)? (propuesta aceptada por Jesús)
4. ¿Le parece razonable 0% de devoluciones en venta local, porque el comprador revisa al recibir? (propuesta nueva)

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-11 | Compra por oportunidad: conservar hasta encontrar comprador; el riesgo se mide con días y rendimiento (DEC-141) | Jesús |
| 2026-11-16 | Tasas de devolución por categoría según los umbrales de Amazon | Jesús (propuesta de Claude) |
| 2026-11-16 | Pérdida por devolución 50%; 75% en perfumes y joyería | Jesús (propuesta de Claude) |
| 2026-11-16 | Castigo por baja 50% | Jesús (propuesta de Claude) |
| 2026-11-16 | Días de pago Amazon: 30 con cuenta nueva, 21 con historial; venta local 0 | Jesús (propuesta de Claude) |
| 2026-11-16 | Tope de primera compra 3 unidades (5 en casos muy buenos) | Jesús (propuesta de Claude) |
| 2026-11-16 | Se cuenta hasta vender la última unidad | Jesús (propuesta de Claude) |

## 14. Revisión de consistencia
- Última revisión: ver `revisiones/RN-005.md` (columna v2)
- Detalle: [revisiones/RN-005.md](/revisiones/RN-005.md)
