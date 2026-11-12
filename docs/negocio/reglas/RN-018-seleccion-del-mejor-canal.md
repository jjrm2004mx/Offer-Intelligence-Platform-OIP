# RN-018 — Selección del mejor canal de venta

```yaml
id: RN-018
titulo: Selección del mejor canal de venta
grupo: resultado
estado: BORRADOR
version: 1
fecha: 2026-11-11
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-001, RN-004, RN-005, RN-006, RN-016, RN-017]
```

## 1. ¿Qué queremos lograr?
Que OIP diga **dónde conviene vender** cada oportunidad, sin importar dónde se compró (DEC-146). El mismo producto puede ser poco atractivo en Amazon y bastante interesante en venta local. La mejor opción no es la del precio de venta más alto, sino la que deja **el mejor resultado ajustado por costos, tiempo y riesgo**.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Calcular el resultado en **cada canal activo** y elegir uno.
- Mostrar los demás canales, con su resultado, para que Jesús compare.

**No incluye:**
- El nivel de la oportunidad (RN-009), que se calcula después con el canal elegido.
- Canales que no son del Inc. 1: eBay o venta con envío por plataformas locales (DEC-151, DEC-161).

## 3. ¿Cómo funciona, en palabras?
Para cada canal donde el producto se puede vender, se calcula el margen (RN-001) y el rendimiento mensual (RN-005). Los canales que no cumplen lo mínimo se descartan. Entre los que quedan, gana el que rinde más por mes, porque así se compara una ganancia grande que tarda contra una más chica que llega rápido.

## 4. La regla

**Canales del Inc. 1** (DEC-151):

Cada canal pasa por tres preguntas, en orden:

| Pregunta | Amazon FBM | Venta local (OfferUp, Facebook Marketplace y venta personal) |
|---|---|---|
| 1. ¿**Tiene datos**? (canal activo) | Hay fuente de datos de Amazon: API oficial o Keepa (DEC-156) | Hay precio de venta local (RN-016) |
| 2. ¿Está **descartado**? | No vendible (RN-006) o demanda insuficiente (RN-004) | Demanda saturada (RN-017) |
| 3. ¿Es **elegible**? | Margen ajustado **≥ $10 por unidad** y **≥ 25%** (el mínimo del nivel D de RN-009) | Igual |

Los productos voluminosos quedan descartados en todos los canales (DEC-159).

**Resultado que recibe RN-009:**

| Situación | Resultado |
|---|---|
| Ningún canal tiene datos | **REVISIÓN MANUAL** (sin precio de venta) |
| Todos los canales con datos están descartados | **DESCARTADA** |
| Hay canales no descartados, pero ninguno es elegible | **No es oportunidad**; se informa el de mayor margen ajustado para la **vigilancia de precio** |
| Al menos un canal es elegible | Se elige uno (abajo) y RN-009 asigna el nivel |

**Elección entre canales elegibles:**
1. Gana el de **mayor rendimiento mensual** (RN-005).
2. Empate (diferencia menor a 1 punto): gana el de **mayor margen ajustado en $**.
3. Si sigue el empate: **venta local** (cobra al entregar y no tiene devoluciones de plataforma).

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Diferencia para empate | Puntos de rendimiento mensual | 1 | Por confirmar |
| Margen mínimo por canal | $ por unidad y % | $10 y 25% (iguales que RN-009) | Por confirmar |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Gana la venta local (el ejemplo de canales de ANL-001, con las tarifas de OIP)**
- Compra $69.00 + impuesto $5.35 → **costo de compra $74.35** (RN-008).
- **Amazon FBM:** venta esperada $119; comisión $17.85, envío $12, empaque $2 → margen neto = 119 − 74.35 − 31.85 = **$12.80**. Devoluciones 119 × 5% × 50% = $2.98; castigo (119 − 115) × 50% = $2.00 → margen ajustado **$7.82** → **menos de $10: no elegible**.
- **Venta local:** venta esperada $109; entrega $9.50 → margen neto = 109 − 74.35 − 9.50 = **$25.15**. Castigo 109 × 5% = $5.45 → margen ajustado **$19.70** (26.50%). Demanda probada → 7 días → rendimiento mensual = 26.50% × 30 ÷ 7 = **113.56%**.
- Resultado: **venta local**.

**Ejemplo B — Amazon sin datos (etapa 1)**
- Sin fuente de Amazon (DEC-156) → solo se evalúa la venta local. Si la venta local está saturada → **DESCARTADA**. Si no está saturada pero no es elegible → no es oportunidad, con vigilancia de precio.

**Ejemplo C — Ningún canal elegible (baterías DEWALT, RN-005 ejemplo C)**
- Amazon: no vendible (baterías de litio, RN-006). Venta local: margen ajustado **$2.85** → no elegible.
- Resultado: Amazon descartado; venta local no descartada pero no elegible → **no es oportunidad**; se informa venta local ($2.85) para la vigilancia de precio.

**Ejemplo D — Gana Amazon (sierra circular, RN-005 ejemplo B, con venta local supuesta)**
- Amazon FBM: margen ajustado $45.92 (146.9%), 21 días → rendimiento **209.9%**.
- Venta local supuesta: esperada $95, entrega $9.50 → neto = 95 − 31.25 − 9.50 = **$54.25**; castigo 95 × 5% = $4.75 → ajustado **$49.50** (158.40%); demanda desconocida → 30 días → rendimiento = 158.40% × 30 ÷ 30 = **158.40%**.
- Resultado: **Amazon FBM** (209.9% contra 158.40%), aunque el margen local en $ sea un poco mayor.

## 6. ¿Qué información necesitamos?
- Resultados de RN-001 y RN-005 por canal, RN-004, RN-006, RN-016 y RN-017.

## 7. ¿Qué obtenemos?
- El canal elegido y el resultado de cada canal (margen ajustado, rendimiento mensual, motivo si no es elegible).

## 8. ¿Quién participa?
- El sistema calcula y elige.
- Jesús puede vender por otro canal; si lo hace, se registra para aprender.

## 9. ¿De qué depende?
- RN-001, RN-004, RN-005, RN-006, RN-016 y RN-017.
- La usa RN-009.

## 10. Limitaciones
- En la etapa 1 casi siempre habrá un solo canal activo (venta local), porque Amazon espera su fuente de datos (DEC-156).
- El rendimiento mensual depende de los días estimados de venta, que al inicio son gruesos.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| Ningún canal tiene datos | Revisión manual (RN-009) |
| Jesús vende por un canal distinto al elegido | Se registra el canal real y el resultado |
| Un canal se activa después (llega Keepa) | Las oportunidades vigentes se vuelven a evaluar |

## 12. Preguntas para el experto
1. ¿Le parece correcto elegir por rendimiento mensual, o preferiría el mayor margen en $?
2. ¿Hay razones para preferir un canal aunque rinda menos (reputación, riesgo, volumen)?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-11 | Canales por oportunidad (DEC-140); Inc. 1 con 2 canales (DEC-151) | Jesús |
| 2026-11-11 | Origen de compra y canal de venta independientes (DEC-146) | Jesús |
| 2026-11-11 | Amazon FBM se activa con fuente de Amazon (DEC-156) | Jesús |

## 14. Revisión de consistencia
- Última revisión: 2026-11-11 (v1) — RECHAZADO.
- Detalle: [revisiones/RN-018.md](/revisiones/RN-018.md)
