# RN-004 — Demanda en Amazon ("lo que la gente mueve")

```yaml
id: RN-004
titulo: Demanda en Amazon
grupo: amazon
estado: EN_REVISION
version: 2
fecha: 2026-11-16
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-002, RN-013]
```

> **Qué cambió en la v2 (2026-11-16):** el umbral de ranking es un **porcentaje de la categoría** (0.5% superior), no un número fijo; decide la categoría principal; la tendencia usa **promedios de 7 días**; el ranking es señal de **popularidad, no de unidades vendidas** (DEC-128); los datos salen de lo que OIP observa en Amazon, sin Keepa (DEC-124). Si la demanda en Amazon no alcanza, **no se descarta la oferta**: se evalúa la venta local (RN-017, RN-018). Propuestas de Claude aceptadas por Jesús, [sesión 2](/sesiones/sesion-2-respuestas.md), bloque 4; por validar con el experto. La v1 queda en el historial: [RN-004 v1](https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/blob/1c1d4e04d5e5e2401dbb565782bf11061d8813f7/docs/negocio/reglas/RN-004-demanda.md).

## 1. ¿Qué queremos lograr?
Evitar comprar para Amazon productos baratos **que nadie compra**. Una oferta solo vale la pena en Amazon si el producto se vende con frecuencia y no hay demasiados vendedores peleando la misma venta.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Qué tan bien se vende el producto en Amazon (su ranking en la categoría principal).
- Cuántos vendedores lo ofrecen.
- Si su venta va a la baja.
- Cuántas unidades se venden al mes, cuando Amazon lo muestra.

**No incluye:**
- Cuántos días tardará en venderse (RN-005).
- La demanda en venta local (RN-017).

## 3. ¿Cómo funciona, en palabras?
Amazon da a cada producto un lugar en su categoría: entre más bajo el número, más se vende comparado con los demás. Como las categorías tienen tamaños muy distintos, no se usa un número fijo: el producto debe estar dentro del **medio por ciento superior** de su categoría. Además no debe tener demasiados vendedores, y se vigila si su lugar empeora.

## 4. La regla

La demanda en Amazon es **SUFICIENTE** si se cumplen las dos condiciones:
1. Ranking en la **categoría principal** ≤ **0.5% del total de artículos de la categoría**.
   - En **relojes y joyería**, que están dentro de una categoría enorme ("Ropa, zapatos y joyería"), además debe estar entre los **primeros 100 de su subcategoría**.
2. Vendedores de producto nuevo ≤ **20**.

Si no se cumple alguna → **DEMANDA INSUFICIENTE EN AMAZON** → el canal Amazon no es viable para esta oferta; se evalúa la venta local (RN-018).

Advertencia (no descarta): **DEMANDA A LA BAJA** si el **promedio de 7 días** del ranking de hoy empeoró más de **50%** frente al promedio de 7 días de hace 30 días. El ranking cambia cada hora; un solo día engaña.

Señales complementarias, **nunca suficientes solas**: variación del número de reseñas entre consultas y temporada del producto (DEC-153).

**Umbral por categoría** (el tamaño de cada categoría se actualiza cada mes con una tabla pública):

| Categoría principal en Amazon | Artículos (oct-2025) | Umbral (0.5%) |
|---|---|---|
| Herramientas y mejoras del hogar (incluye iluminación) | 33,688,021 | 168,440 |
| Ropa, zapatos y joyería (relojes y joyería) | 248,469,279 | 1,242,346 + primeros 100 de la subcategoría |
| Belleza (perfumes), hogar y cocina, juguetes, electrónica | Por cargar | 0.5% del total |

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Porcentaje de la categoría | Umbral de "se vende bien" | 0.5% | Aceptado por Jesús; validar con el experto |
| Subcategoría (relojes y joyería) | Lugar máximo | 100 | Aceptado por Jesús |
| Vendedores máximos | Producto nuevo | 20 | Aceptado por Jesús |
| Empeoramiento para advertencia | Promedio de 7 días contra el de hace 30 días | 50% | Aceptado por Jesús |

Todos los valores son iniciales y configurables.

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Taladro (demanda suficiente)**
- Herramientas: ranking 8,500 ≤ 168,440 ✓. 9 vendedores ≤ 20 ✓.
- Promedio de 7 días hoy 8,500; hace 30 días 8,000: empeoró 6.25% → **SUFICIENTE**, sin advertencia.

**Ejemplo B — Lámpara (insuficiente)**
- Herramientas (iluminación): ranking 420,000 > 168,440 ✗ → **DEMANDA INSUFICIENTE EN AMAZON**.

**Ejemplo C — Producto saturado**
- Ranking 12,000 ✓, pero 35 vendedores > 20 ✗ → **DEMANDA INSUFICIENTE EN AMAZON**.

**Ejemplo D — Advertencia de baja**
- Promedio de 7 días hoy 30,000; hace 30 días 18,000. Empeoró (30,000 − 18,000) ÷ 18,000 = **66.7%** → **SUFICIENTE con advertencia DEMANDA A LA BAJA**.

**Ejemplo E — Reloj**
- Ranking en "Ropa, zapatos y joyería" 900,000 ≤ 1,242,346 ✓, pero lugar 240 en su subcategoría (más de 100) ✗ → **DEMANDA INSUFICIENTE EN AMAZON**.

## 6. ¿Qué información necesitamos?
- Ranking en la categoría principal y en la subcategoría, número de vendedores de nuevo, número de reseñas y, si Amazon lo muestra, cuántas unidades se compraron el mes pasado. Los registra OIP en cada consulta a la ficha de Amazon, como su propio historial.
- Tamaño de cada categoría principal (tabla pública, mensual).

## 7. ¿Qué obtenemos?
- SUFICIENTE / INSUFICIENTE en Amazon, advertencia de baja y los datos usados.

## 8. ¿Quién participa?
- El sistema consulta y evalúa.
- El experto ayuda a ajustar el porcentaje por categoría.

## 9. ¿De qué depende?
- De identificar el producto en Amazon (RN-013).

## 10. Limitaciones
- El ranking indica popularidad relativa, no unidades vendidas (DEC-128).
- Sin Keepa, la tendencia necesita que OIP acumule sus propias observaciones; los primeros 30 días no hay advertencia de baja.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| No hay ranking | Demanda "desconocida": se evalúa, pero va a revisión manual sin aviso (RN-009) |
| No se conoce el número de vendedores | Demanda "desconocida", igual que arriba |
| No hay datos de hace 30 días | No calcula la advertencia de baja |
| No se conoce el tamaño de la categoría | Demanda "desconocida" hasta cargarlo |

## 12. Preguntas para el experto
1. ¿Le parece bien el criterio de **0.5% superior de la categoría**, y para relojes y joyería, además, los **primeros 100 de la subcategoría**? (propuesta aceptada por Jesús)
2. ¿Bastan **20 vendedores** como máximo? (propuesta aceptada por Jesús)
3. ¿Le parece bien comparar **promedios de 7 días** para detectar la baja? (propuesta aceptada por Jesús)

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-11 | El ranking es señal de popularidad, no de unidades (DEC-128) | Jesús |
| 2026-11-16 | Umbral = 0.5% superior de la categoría principal; relojes y joyería, además, primeros 100 de la subcategoría | Jesús (propuesta de Claude) |
| 2026-11-16 | Decide la categoría principal; la subcategoría es contexto | Jesús (propuesta de Claude) |
| 2026-11-16 | Máximo 20 vendedores | Jesús (propuesta de Claude) |
| 2026-11-16 | Reseñas y temporada como señales complementarias | Jesús (propuesta de Claude) |
| 2026-11-16 | Tendencia con promedios de 7 días | Jesús (propuesta de Claude) |

## 14. Revisión de consistencia
- Última revisión: ver `revisiones/RN-004.md` (columna v2)
- Detalle: [revisiones/RN-004.md](/revisiones/RN-004.md)
