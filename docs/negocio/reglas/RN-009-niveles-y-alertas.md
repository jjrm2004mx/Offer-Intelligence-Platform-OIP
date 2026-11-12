# RN-009 — Niveles de oportunidad de reventa y alertas

```yaml
id: RN-009
titulo: Niveles de oportunidad de reventa y alertas
grupo: resultado
estado: BORRADOR
version: 2
fecha: 2026-11-11
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-001, RN-003, RN-004, RN-005, RN-006, RN-007, RN-013, RN-015, RN-017, RN-018]
version_anterior: https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/blob/5a4744d15b2ac6439f2cd89d25cb377ab437ab36/docs/negocio/reglas/RN-009-niveles-y-alertas.md
```

## 1. ¿Qué queremos lograr?
Clasificar cada oferta que sobrevivió a todos los filtros en un **nivel de oportunidad de reventa**, y avisar a Jesús en el momento adecuado: de inmediato las mejores y en resumen las demás, sin llenarlo de avisos repetidos. Es el **segundo eje** de clasificación ("¿conviene revenderlo?"); el primero, "¿está barato?", es RN-012 (DEC-131).

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Condiciones para que una oferta sea oportunidad, **en el canal que eligió RN-018**.
- Qué ofertas van a **revisión manual** en lugar de recibir nivel.
- Niveles y qué tipo de aviso genera cada uno.
- Cuándo no repetir un aviso.
- **Vigilancia de precio** de las ofertas que no alcanzaron por margen (nuevo en la v2).

**No incluye:**
- La decisión del viaje (RN-008), que se calcula aparte con las oportunidades que pasan aquí.
- La calidad del precio para un consumidor (RN-012) y la búsqueda por artículo (RN-011).

## 3. ¿Cómo funciona, en palabras?
Primero se revisa que la oferta no tenga ningún impedimento. Si tiene una señal de riesgo que pide criterio humano, va a revisión manual. Si pasa, se le asigna el **nivel más alto cuyas dos condiciones cumpla**: descuento real mínimo y margen ajustado mínimo, en el canal elegido, y además debe dejar al menos **$10 por unidad**. Si la oferta no alcanzó solo por margen, OIP calcula a qué precio sí alcanzaría y avisa si baja a ese precio.

## 4. La regla

**Resultado de cada oferta, en orden de precedencia:** **DESCARTADA** > **REVISIÓN MANUAL** > **nivel** (A, B, C, D) > **no es oportunidad**.

**Descartada** (si falta cualquiera de estos requisitos):
- Identificación **confirmada** (RN-013, niveles 1 y 2).
- Sin marca **MERCADO YA BARATO** (RN-003).
- Que no sea **voluminoso** (DEC-159) y que, si hay al menos un canal con datos, no estén descartados todos (RN-018: no vendible, demanda insuficiente o saturada). Si ningún canal tiene datos, va a revisión manual, no se descarta.
- Disponibilidad: tienda física con confianza Alta o Media; en línea, "disponible confirmada"; particular, publicación vigente (RN-007).

**Revisión manual** (sin nivel ni aviso automático; Jesús decide):
- Marca **SIN REFERENCIA** (RN-003).
- Riesgo **Alto** (RN-015).
- **Vendedor externo** (DEC-137).
- **Ningún canal tiene datos** (RN-018): sin precio de venta en Amazon ni en venta local.

**Niveles** — se asignan solo si RN-018 eligió un canal (margen ajustado **≥ $10 por unidad** y ≥ 25% en ese canal). Se asigna el más alto cuyas dos condiciones se cumplan:

| Nivel | Descuento real (RN-003) | Margen ajustado % (RN-005) | Aviso |
|---|---|---|---|
| **A** | ≥ 80% | ≥ 50% | Inmediato |
| **B** | ≥ 70% | ≥ 40% | Inmediato |
| **C** | ≥ 50% | ≥ 30% | Resumen 2 veces al día |
| **D** | ≥ 40% | ≥ 25% | Solo en el tablero |

- **Sin historial suficiente** (RN-002): en lugar del descuento real se usa la **ventaja contra el mercado** (RN-003), y la oportunidad se marca "sin historial".
- **Demanda local desconocida** (RN-017): nivel máximo **C**.
- Se muestran las marcas que apliquen: "requiere inspección" (particular, RN-015), "riesgo de inventario" (RN-005), "sin historial", "precio estimado" (RN-016).
- Si no alcanza ni el nivel D → **no es oportunidad** (queda registrada como evaluada).

**Orden:** dentro de cada nivel, por **rendimiento mensual** (RN-005), de mayor a menor.

**No repetir avisos:** la misma oferta no se vuelve a avisar en **24 horas**, salvo que suba de nivel o su precio baje **5% o más**.

**Vigilancia de precio** (nuevo): si RN-018 dice "no es oportunidad" porque ningún canal fue elegible solo por **margen** (el $10 por unidad o el % del nivel D), se calcula el **precio máximo de compra** con el que alcanzaría el nivel D en su canal. Mientras siga publicada, si su precio baja a ese valor o menos, se vuelve a evaluar completa y se avisa si alcanza nivel.

```
margen ajustado sin la compra = precio esperado − costo de venta − devoluciones − castigo por baja
costo de compra máximo        = el MENOR entre:
                                  · margen ajustado sin la compra − 10
                                  · margen ajustado sin la compra ÷ 1.25      (para llegar a 25%)
precio máximo de compra       = costo de compra máximo ÷ (1 + tasa de impuesto), redondeado hacia abajo
```

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Margen mínimo por unidad | $ | $10 | Por confirmar |
| Umbrales por nivel | Ver tabla | Ver tabla | Por confirmar |
| Nivel máximo con demanda local desconocida | — | C | Por confirmar |
| Horarios del resumen | 2 veces al día | 8:00 y 18:00 (Tijuana) | Decisión de Jesús |
| Ventana sin repetir | Horas | 24 h | Decisión de Jesús |
| Baja de precio para repetir | % | 5% | Decisión de Jesús |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Sierra circular → Nivel B, aviso inmediato (de la v1)**
- Canal Amazon FBM. Descuento real **75.63%** (RN-003, ejemplo E), margen ajustado 146.9% ($45.92 por unidad), demanda suficiente, vendible, confianza Alta.
- Nivel A exige ≥ 80% de descuento real ✗. Nivel B: 75.63% ≥ 70% ✓ y 146.9% ≥ 40% ✓ → **Nivel B** → aviso inmediato.

**Ejemplo B — Taladro → no es oportunidad (de la v1)**
- Canal Amazon FBM. Precio habitual $149 → descuento real = (1 − 79 ÷ 149) × 100 = **46.98%**; margen ajustado 22.1% ($18.80 por unidad).
- Nivel D exige ≥ 40% ✓ y ≥ 25% ✗ → **no alcanza ningún nivel**, aunque la tienda anunciara 60%.

**Ejemplo C — Lámpara → descartada (de la v1)**
- Marca MERCADO YA BARATO (RN-003, ejemplo A) → **DESCARTADA**.

**Ejemplo D — Descuento alto, margen moderado (de la v1)**
- Descuento real 82%, margen ajustado 35%, $22 por unidad.
- A: 82% ✓ pero 35% < 50% ✗. B: ✓ pero 35% < 40% ✗. C: 82% ≥ 50% ✓ y 35% ≥ 30% ✓ → **Nivel C** → va al resumen.

**Ejemplo E — No repetir (de la v1)**
- La sierra se avisó a las 10:00. A las 14:00 el precio sigue igual → no se avisa otra vez. A las 16:00 baja de $29 a $27 (6.9%) → **sí se vuelve a avisar**.

**Ejemplo F — Revisión manual (CASO-005)**
- Baterías Milwaukee en Walmart con vendedor sin confirmar → riesgo Alto (RN-015) → **REVISIÓN MANUAL**, sin aviso, aunque no tuviera otro problema.

**Ejemplo G — Vigilancia de precio (producto supuesto, con historial y comparación suficiente)**
- Canal venta local. Precio esperado $84.65 (RN-016, ejemplo B); entrega $9.50; devoluciones $0; castigo 84.65 × 5% = $4.23.
- Margen ajustado sin la compra = 84.65 − 9.50 − 0 − 4.23 = **$70.92**.
- Costo de compra máximo = menor(70.92 − 10 = 60.92 ; 70.92 ÷ 1.25 = 56.736 → $56.74) → **$56.74**.
- Precio máximo de compra = 56.74 ÷ 1.0775 = 52.658… → **$52.65** (hacia abajo). Comprobación: con $52.65 + impuesto $4.08 = $56.73, el margen ajustado es 70.92 − 56.73 = $14.19 = 25.01% ✓. Si el precio baja a $52.65 o menos, se vuelve a evaluar y se avisa si alcanza nivel.
- Las baterías Milwaukee reales (CASO-005) **no** llegan a vigilancia: sin historial y con un solo comercio de comparación quedan en SIN REFERENCIA → revisión manual.

**Ejemplo H — Sin historial**
- Oferta nueva sin precio habitual, ventaja contra el mercado 55% y margen ajustado 32% ($14) en venta local con demanda probada → se usa la ventaja: C exige 50% ✓ y 30% ✓ → **Nivel C**, marcado "sin historial".

## 6. ¿Qué información necesitamos?
- Resultados de RN-001 a RN-007, RN-013, RN-015, RN-017 y el canal elegido por RN-018.

## 7. ¿Qué obtenemos?
- Resultado de cada oferta (descartada, revisión manual, nivel o no es oportunidad), con sus marcas, el aviso correspondiente (mensaje al celular de Jesús), su lugar en el tablero y, si aplica, su precio de vigilancia.

## 8. ¿Quién participa?
- El sistema clasifica y avisa.
- Jesús recibe los avisos, resuelve las revisiones manuales y decide.
- El experto valida los umbrales.

## 9. ¿De qué depende?
- De todas las RN anteriores y de RN-018 (canal elegido).

## 10. Limitaciones
- Los umbrales son iniciales. Se ajustarán con los resultados reales de compra y venta.
- Los primeros meses casi todo será "sin historial" y con demanda local "desconocida": habrá pocos avisos inmediatos, y es esperado.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| Falla el envío del aviso | Reintenta; si sigue fallando, queda visible en el tablero |
| La oportunidad desaparece (se agotó o subió el precio) | Se marca "ya no disponible" en el tablero; no se avisa; se deja de vigilar |
| Muchas oportunidades al mismo tiempo (más de 10 inmediatas en una hora) | Se agrupan en un solo aviso |
| No hay precio habitual ni ventaja contra el mercado | SIN REFERENCIA → revisión manual |

## 12. Preguntas para el experto
1. *(De la v1)* ¿Le parecen bien los umbrales de cada nivel? ¿Pondría más exigencia en descuento o en margen?
2. *(De la v1)* ¿$10 por unidad es un mínimo razonable, o depende del precio del producto?
3. *(De la v1)* ¿Algún tipo de producto que, aunque cumpla los números, usted evitaría siempre?
4. ¿Los umbrales deberían ser distintos para venta local y para Amazon?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-08 | Los avisos llegan por mensaje al celular (Telegram) y además se ven en un tablero | Jesús |
| 2026-11-11 | Dos ejes de clasificación; esta regla es el de reventa (DEC-131) | Jesús |
| 2026-11-11 | Vendedor externo en la búsqueda de ofertas: revisión manual (DEC-137) | Jesús |
| 2026-11-11 | Una sola fórmula con el canal como parámetro (DEC-143) | Jesús |

**Cambios de la v2 contra la v1:** los niveles se renombran **A, B, C y D** (antes Excepcional, Muy buena, Buena e Interesante), para no confundirlos con las clases de RN-012; los requisitos se evalúan en el canal elegido por RN-018; se agregan la revisión manual y la precedencia, el uso de la ventaja contra el mercado sin historial, el tope por demanda local desconocida y la vigilancia de precio, con los ejemplos F, G y H. "Coincidencia dudosa" pasa a RN-013. Los ejemplos A a E de la v1 se conservan; A y B usan los porcentajes recalculados (75.63% y 46.98%).

## 14. Revisión de consistencia
- Última revisión: 2026-11-11 (v2.1) — **APROBADO CON OBSERVACIONES**: continuar a requerimiento; las preguntas abiertas se responden antes de cerrar el desarrollo. Revisiones anteriores: 2026-11-11 (v2) — RECHAZADO; 2026-11-08 (v1) — APROBADO CON OBSERVACIONES.
- Detalle: [revisiones/RN-009.md](/revisiones/RN-009.md)
