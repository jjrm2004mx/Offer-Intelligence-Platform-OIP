# RN-005 — Rentabilidad ajustada por tiempo y riesgo, por canal

```yaml
id: RN-005
titulo: Rentabilidad ajustada por tiempo y riesgo, por canal
grupo: resultado
estado: BORRADOR
version: 2
fecha: 2026-11-11
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-001, RN-002, RN-004, RN-016, RN-017]
version_anterior: https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/blob/5a4744d15b2ac6439f2cd89d25cb377ab437ab36/docs/negocio/reglas/RN-005-rentabilidad-ajustada-por-tiempo.md
```

## 1. ¿Qué queremos lograr?
Que la ganancia sea **real, no aparente**. Un margen alto que tarda meses en convertirse en dinero, o que se lo comen las devoluciones o una baja de precio, vale menos que un margen moderado que se cobra en semanas. Es lo que distingue una **oportunidad de inversión** de una simple oportunidad de reventa (ANL-001): $50 en tres meses no equivale a $30 en tres días. En la v2 se calcula **para cada canal** con la misma fórmula (DEC-143).

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Ajustar el margen por devoluciones esperadas y por el riesgo de que baje el precio.
- Estimar en cuántos días se recupera el dinero.
- Calcular un rendimiento mensual equivalente para **ordenar** oportunidades.
- Recomendar cuántas unidades comprar.
- Marcar el **riesgo de inventario** de una compra por oportunidad (DEC-141).

**No incluye:**
- El costo del viaje a tienda (RN-008).

## 3. ¿Cómo funciona, en palabras?
1. Al margen neto (RN-001) se le restan dos riesgos: lo que se espera perder por devoluciones y una parte de lo que podría bajar el precio mientras tenemos el producto.
2. Se estima cuánto tarda en venderse, según la demanda (RN-004), más lo que tarda Amazon en pagar.
3. Con eso se calcula cuánto rinde el dinero por mes, para comparar oportunidades que tardan distinto.

## 4. La regla

```
costo por devoluciones = precio de venta esperado × tasa de devolución × pérdida por devolución
castigo por baja       = (precio de venta esperado − mínimo de 90 días en Amazon) × 50%
margen ajustado ($)    = margen neto − costo por devoluciones − castigo por baja
margen ajustado (%)    = margen ajustado ($) ÷ costo de compra × 100

días para recuperar    = días estimados de venta + días de pago de Amazon
rendimiento mensual    = margen ajustado (%) × 30 ÷ días para recuperar

unidades recomendadas  = ventas al mes ÷ (vendedores + 1), redondeado hacia abajo,
                         sin pasar de las unidades disponibles
```

**Lo que cambia por canal** (la fórmula es la misma):

| Concepto | Amazon FBM | Venta local |
|---|---|---|
| Costo por devoluciones | Como arriba | **$0**: la venta en persona es "como está" (las devoluciones acordadas son un riesgo de RN-015) |
| Castigo por baja | (precio esperado − mínimo de 90 días en Amazon) × 50% | **5%** del precio de venta esperado (no hay historial local de precios) |
| Días estimados de venta | Por ranking (tabla de abajo, RN-004) | Por clase de demanda local (RN-017): 7, 14 o 30 |
| Días de pago | 14 (Amazon) | **0**: pago al entregar |
| Unidades recomendadas | Fórmula de arriba | Máximo **2** mientras la demanda local no sea "probada"; con "probada", máximo 3 |

**Riesgo de inventario (compra por oportunidad, DEC-141):** si los días para recuperar pasan de **60**, la oportunidad se marca **"riesgo de inventario"**. No se descarta: el rendimiento mensual ya la pone abajo en el orden.

Días estimados de venta según el ranking (RN-004):

| Ranking de ventas | Días estimados de venta |
|---|---|
| menos de 10,000 | 7 |
| 10,000 a 50,000 | 21 |
| 50,001 a 150,000 | 45 |

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Tasa de devolución | % de ventas que se devuelven, por categoría | Herramientas 5% | Por confirmar |
| Pérdida por devolución | Qué parte del precio se pierde en una devolución | 50% | Por confirmar |
| Peso del castigo por baja | Qué parte de la posible baja se descuenta | 50% | Por confirmar |
| Días de pago de Amazon | Lo que tarda Amazon en depositar | 14 | Por confirmar |
| Castigo por baja en venta local | % del precio esperado | 5% | Por confirmar |
| Unidades máximas en venta local | Sin / con demanda probada | 2 / 3 | Por confirmar |
| Límite de riesgo de inventario | Días para recuperar | 60 | Por confirmar |
| Tabla de días por ranking | Ver arriba | Ver arriba | Por confirmar |

> Nota para el documento técnico (de la v1): esta regla usa **rendimiento mensual** en lugar del "ROI anualizado" del documento de arquitectura v1.2, porque se entiende mejor. También agrega la "pérdida por devolución" y el castigo por baja con peso de 50%. Hay que actualizar el documento técnico cuando se apruebe.

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Taladro**
- Margen neto (RN-001): $27.53. Costo de compra: $85.12. Venta esperada: $149. Mínimo 90 días: $139.
- Devoluciones: 149 × 5% × 50% = **$3.73**. Castigo por baja: (149 − 139) × 50% = **$5.00**.
- Margen ajustado = 27.53 − 3.73 − 5.00 = **$18.80** → 18.80 ÷ 85.12 = **22.1%**.
- Ranking 8,500 → 7 días de venta + 14 de pago = **21 días**.
- Rendimiento mensual = 22.1% × 30 ÷ 21 = **31.6%**.
- Ventas al mes 300, 9 vendedores → 300 ÷ 10 = 30 unidades; en tienda hay 4 → **comprar 4**.

**Ejemplo B — Sierra circular**
- Margen neto: 119 − 31.25 − 33.85 = **$53.90** (compra $29 + 7.75% = $31.25; comisión 15% $17.85, envío $14, empaque $2).
- Devoluciones: 119 × 5% × 50% = **$2.98**. Castigo: (119 − 109) × 50% = **$5.00**.
- Margen ajustado = 53.90 − 2.98 − 5.00 = **$45.92** → 45.92 ÷ 31.25 = **146.9%**.
- Ranking 6,000 → 7 + 14 = 21 días → rendimiento mensual = 146.9% × 30 ÷ 21 = **209.9%**.
- Ventas al mes 200, 5 vendedores → 200 ÷ 6 = 33; en tienda hay 3 → **comprar 3**.

**Comparación:** el taladro parecía bueno (32.3% de margen neto), pero ajustado queda en 22.1%. La sierra sigue siendo excelente.

**Ejemplo C — Baterías DEWALT en venta local (nuevo; RN-001, ejemplo C)**
- Margen neto local: $7.98. Costo de compra: $85.12. Precio esperado: $102.60.
- Devoluciones: $0. Castigo por baja: 102.60 × 5% = **$5.13**.
- Margen ajustado = 7.98 − 0 − 5.13 = **$2.85** → 2.85 ÷ 85.12 = **3.35%**.
- Demanda local probada (RN-017) → 7 días + 0 de pago = **7 días**. Rendimiento mensual = 3.35% × 30 ÷ 7 = **14.35%** (con el porcentaje sin redondear, 3.3482…%).
- Margen menor a $10 por unidad → no alcanza los requisitos de RN-009.

**Ejemplo D — Oportunidad de inversión (ANL-001)**
- Compra de $70 en los dos casos. Uno deja $50 en 90 días: 71.43% × 30 ÷ 90 = **23.81% al mes**, y se marca "riesgo de inventario" (más de 60 días). El otro deja $30 en 3 días: 42.86% × 30 ÷ 3 = **428.57% al mes**.
- Con menos ganancia, el segundo queda muy arriba en el orden.

## 6. ¿Qué información necesitamos?
- Resultados de RN-001, RN-002 y RN-004.
- Ventas al mes y número de vendedores (API oficial de Amazon o Keepa, cuando se contraten; DEC-156).
- Para venta local: precio esperado (RN-016) y clase de demanda (RN-017).
- Unidades disponibles en la tienda (RN-007).

## 7. ¿Qué obtenemos?
- Por canal: margen ajustado ($ y %), días para recuperar, rendimiento mensual, unidades recomendadas y marca de riesgo de inventario.

## 8. ¿Quién participa?
- El sistema calcula.
- El experto valida tasas, días y criterio de unidades.
- Jesús decide cuánto comprar en realidad.

## 9. ¿De qué depende?
- RN-001, RN-002, RN-004 y RN-007; para venta local, RN-016 y RN-017.

## 10. Limitaciones
- Los días de venta son una estimación gruesa hasta tener ventas reales. Con cada venta registrada se irá ajustando la tabla.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| No hay dato de ventas al mes | Recomienda máximo 2 unidades y lo marca como estimación |
| No hay mínimo de 90 días | Castigo por baja = 10% del precio de venta esperado |
| El margen ajustado sale negativo | No genera alerta |
| Ranking mayor a 150,000 | No aplica: RN-004 ya la descartó |

## 12. Preguntas para el experto
1. ¿Qué tasa de devolución esperar en herramientas, relojes, perfumes y joyería?
2. Cuando hay una devolución, ¿qué parte del precio se suele perder (envío de regreso, producto que ya no se puede vender como nuevo)?
3. ¿Le parece razonable descontar la mitad de la posible baja de precio, o es demasiado (o muy poco)?
4. ¿Cuánto tarda en realidad Amazon en pagar a un vendedor nuevo?
5. Para un vendedor que empieza, ¿cuántas unidades del mismo producto recomendaría como máximo en la primera compra?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-11 | Compra por oportunidad, con riesgo de inventario (DEC-141) | Jesús |
| 2026-11-11 | Una sola fórmula, con el canal como parámetro (DEC-143) | Jesús |

**Cambios de la v2 contra la v1:** se agrega la tabla de lo que cambia por canal, el riesgo de inventario y los ejemplos C y D. Fórmulas y ejemplos A y B de Amazon, iguales que la v1.

## 14. Revisión de consistencia
- Última revisión: 2026-11-08 (v1) — APROBADO CON OBSERVACIONES. **La v2 está pendiente de revisión.**
- Detalle: [revisiones/RN-005.md](/revisiones/RN-005.md)
