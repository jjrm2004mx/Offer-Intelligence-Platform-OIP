# RN-004 — Demanda suficiente ("lo que la gente mueve")

```yaml
id: RN-004
titulo: Demanda suficiente
estado: BORRADOR
version: 1
fecha: 2026-11-08
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-002]
```

> **Por actualizar (v2, 2026-11-11).** Esta regla cambiará al terminar los ejercicios de comprobación: el Sales Rank es un indicador de **popularidad, no de unidades vendidas**; definir la demanda sin Keepa mientras esté diferido. DEC-124, DEC-128. El texto de abajo sigue siendo la v1.

## 1. ¿Qué queremos lograr?
Evitar comprar productos baratos **que nadie compra**. Una oferta solo vale la pena si el producto se vende con frecuencia y no hay demasiados vendedores peleando la misma venta.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Qué tan bien se vende el producto en Amazon (su ranking de ventas).
- Cuántos vendedores lo ofrecen.
- Si su venta va a la baja.
- Cuántas unidades se venden al mes (cuando el dato exista).

**No incluye:**
- Cuántos días tardará en venderse (RN-005 lo estima a partir de esta regla).
- Demanda en Facebook Marketplace (fase posterior).

## 3. ¿Cómo funciona, en palabras?
Amazon ordena los productos de cada categoría del más vendido al menos vendido; ese lugar se llama **ranking de ventas** (en inglés BSR). Entre más chico el número, más se vende: el lugar 1 es el más vendido. Si el ranking es muy alto (se vende poco) o hay demasiados vendedores, la demanda no alcanza.

## 4. La regla

La demanda es **SUFICIENTE** si se cumplen las dos condiciones:
1. Ranking de ventas en su categoría ≤ **150,000**.
2. Número de vendedores de producto nuevo ≤ **20**.

Si no se cumple alguna → **DEMANDA INSUFICIENTE** → la oferta se descarta.

Advertencia (no descarta): **DEMANDA A LA BAJA** si el ranking empeoró más de **50%** en los últimos 30 días (por ejemplo, pasó de 10,000 a más de 15,000).

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Ranking máximo | Por categoría | 150,000 (igual para todas al inicio) | Por confirmar por categoría |
| Vendedores máximos | Competidores con producto nuevo | 20 | Por confirmar |
| Empeoramiento para advertencia | En 30 días | 50% | Por confirmar |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Taladro (demanda suficiente)**
- Ranking 8,500 (≤ 150,000 ✓). 9 vendedores (≤ 20 ✓). Hace 30 días ranking 8,000: empeoró 6.25% (menos de 50%) → **SUFICIENTE**, sin advertencia.

**Ejemplo B — Lámpara (demanda insuficiente)**
- Ranking 420,000 (> 150,000 ✗) → **DEMANDA INSUFICIENTE** → descartada.

**Ejemplo C — Producto saturado**
- Ranking 12,000 ✓ pero 35 vendedores (> 20 ✗) → **DEMANDA INSUFICIENTE**.

**Ejemplo D — Advertencia de baja**
- Ranking hoy 30,000; hace 30 días 18,000. Empeoró (30,000 − 18,000) ÷ 18,000 = **66.7%** → **SUFICIENTE con advertencia DEMANDA A LA BAJA**.

## 6. ¿Qué información necesitamos?
- Ranking de ventas actual y de hace 30 días, número de vendedores y, si existe, unidades vendidas el último mes. Todo de Keepa.

## 7. ¿Qué obtenemos?
- Resultado: SUFICIENTE / INSUFICIENTE, advertencia de baja y los datos usados.

## 8. ¿Quién participa?
- El sistema consulta y evalúa.
- El experto ayuda a fijar umbrales por categoría.

## 9. ¿De qué depende?
- De haber identificado el producto en Amazon (RN-002).

## 10. Limitaciones
- El ranking no es comparable entre categorías: 50,000 en herramientas no significa lo mismo que 50,000 en joyería. Por eso el umbral debería ajustarse por categoría.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| No hay ranking (producto nuevo en Amazon) | Demanda "desconocida": se evalúa, pero no genera alerta automática |
| No se conoce el número de vendedores | Evalúa solo el ranking y lo marca como incompleto |
| No hay ranking de hace 30 días | No calcula la advertencia de baja |

## 12. Preguntas para el experto
1. ¿Qué ranking máximo consideraría "se vende bien" en herramientas? ¿Y en relojes, perfumes y joyería?
2. ¿20 vendedores es mucho o poco para entrar a competir siendo nuevo?
3. ¿Hay otra señal de demanda que usted mire (reseñas recientes, búsquedas, temporada)?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| | | |

## 14. Revisión de consistencia
- Última revisión: 2026-11-08 — APROBADO CON OBSERVACIONES
- Detalle: [revisiones/RN-004.md](/revisiones/RN-004.md)
