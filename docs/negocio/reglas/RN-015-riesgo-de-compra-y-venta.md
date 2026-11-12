# RN-015 — Riesgo de compra y de venta

```yaml
id: RN-015
titulo: Riesgo de compra y de venta
grupo: común
estado: BORRADOR
version: 1
fecha: 2026-11-11
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-002, RN-013, RN-014]
```

## 1. ¿Qué queremos lograr?
Que OIP **no recomiende una compra solo porque el precio es bajo**. Un precio demasiado bueno de un vendedor desconocido, un producto que se falsifica con frecuencia o una compra a un particular sin poder probar el artículo son riesgos que pueden costar más que el margen.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- **Riesgo de compra:** quién vende, procedencia, autenticidad, funcionamiento y disponibilidad.
- **Riesgo de venta:** cancelaciones, fraude en el pago y devoluciones en la venta local.
- Un nivel de riesgo (**Bajo, Medio, Alto**) y lo que provoca.

**No incluye:**
- Las devoluciones de Amazon, que ya descuenta RN-005 con su tasa de devolución.
- Las restricciones de venta en Amazon (RN-006).

## 3. ¿Cómo funciona, en palabras?
Se revisan señales de riesgo en cada publicación. Cada señal suma un nivel. Con riesgo **Alto** no hay alerta automática y la oferta va a revisión manual. Con riesgo **Medio**, la oferta sigue, pero se marca y, si es de un particular, exige inspección física antes de comprar.

## 4. La regla

**Señales de riesgo de compra:**

| Señal | Nivel que aporta |
|---|---|
| Vende el comercio o el fabricante | Bajo |
| Vendedor externo con calificación ≥ 95% y ≥ 100 calificaciones | Medio |
| Vendedor externo sin calificación o con menos de eso | Alto |
| Vendedor **sin confirmar** (no se sabe quién vende) | Alto, hasta confirmarlo |
| Particular (OfferUp, Marketplace, contacto) | Medio, con **inspección física obligatoria** |
| Particular que no permite probar el producto | Alto |
| Producto **propenso a falsificación** (baterías de marca, perfumes, relojes, joyería) **y** vendedor que no es el comercio | Sube un nivel |
| Precio **50% o más** por debajo del precio de mercado hoy, de un vendedor que no es el comercio | Sube un nivel |
| Sin caja, sin recibo o con número de serie borrado | Alto |

El nivel final es **el más alto** de las señales, con los ajustes "sube un nivel" aplicados al final (Bajo → Medio → Alto).

**Señales de riesgo de venta (venta local):**

| Señal | Qué provoca |
|---|---|
| Pago que no es en efectivo ni por un medio verificado al entregar | Se marca; Jesús decide |
| Comprador que pide envío fuera de la plataforma | Se marca como posible fraude |

**Qué provoca cada nivel:**

| Nivel | Búsqueda de ofertas (A) y particulares | Búsqueda por artículo (B) |
|---|---|---|
| Bajo | Sigue normal | Puede recomendarse |
| Medio | Sigue; marcado. **Vendedor externo: revisión manual** (DEC-137). Particular: inspección obligatoria antes de comprar | Se muestra marcado; **no se recomienda por defecto** (DEC-135) |
| Alto | **Revisión manual, sin alerta automática** (DEC-137) | Se muestra marcado; no se recomienda |

**Inspección física** (antes de pagarle a un particular): funciona, batería y accesorios en buen estado, coincide con lo publicado (modelo y contenido, RN-013), sin señales de procedencia irregular.

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Calificación mínima del vendedor externo | % positivo / número | 95% / 100 | Por confirmar |
| Precio sospechoso | % por debajo del precio de mercado hoy | 50% | Por confirmar |
| Categorías propensas a falsificación | Lista | Baterías de marca, perfumes, relojes, joyería | Por confirmar |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Riesgo bajo (CASO-004)**
- Ninja BN701 vendida por Amazon.com → **Bajo**.

**Ejemplo B — Riesgo alto (CASO-005)**
- Baterías Milwaukee en Walmart a $120, vendedor sin confirmar → Alto.
- Además: producto propenso a falsificación y (1 − 120 ÷ 269) × 100 = 55.39% por debajo de la única referencia → sube un nivel, pero ya es Alto.
- Resultado: **Alto** → revisión manual, sin alerta.
- Si se confirma que vende Walmart: Bajo; el precio sospechoso solo aplica a vendedores que no son el comercio.

**Ejemplo C — Particular (CASO-006)**
- DEWALT DCF840 de un particular en San Diego, que permite probarlo → **Medio** → inspección obligatoria antes de comprar.
- Si no permite probarlo → **Alto**.

**Ejemplo D — Vendedor externo con buena calificación**
- Vendedor externo con 98% positivo y 1,200 calificaciones, producto no propenso → **Medio**. En la búsqueda de ofertas va a revisión manual por ser vendedor externo (DEC-137).

## 6. ¿Qué información necesitamos?
- Tipo de vendedor y su calificación (RN-013).
- Categoría del producto.
- Precio de mercado hoy (RN-002).
- Para particulares: lo que Jesús registre de la inspección.

## 7. ¿Qué obtenemos?
- Nivel de riesgo, las señales que lo causaron y si exige inspección.

## 8. ¿Quién participa?
- El sistema evalúa las señales.
- Jesús hace la inspección física y decide en los casos de revisión manual.

## 9. ¿De qué depende?
- RN-002, RN-013 y RN-014.
- La usan RN-009, RN-011 y RN-012.

## 10. Limitaciones
- OIP no puede comprobar autenticidad ni funcionamiento a distancia: solo detecta señales.
- La calificación de los vendedores externos no siempre aparece en la página.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| No se ve la calificación del vendedor externo | Se trata como "sin calificación" → Alto |
| La inspección falla | Jesús la registra; la oportunidad se descarta |
| El riesgo cambia después de alertar | Se avisa y la oportunidad baja a revisión manual |

## 12. Preguntas para el experto
1. ¿Qué categorías considera más propensas a falsificación o procedencia irregular en EE. UU.?
2. ¿95% y 100 calificaciones es un buen mínimo para confiar en un vendedor externo?
3. ¿Qué conviene revisar al comprarle herramientas o electrónica a un particular?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-11 | Vendedor externo en B: marcado y no recomendado por defecto (DEC-135) | Jesús |
| 2026-11-11 | Vendedor externo en A: revisión manual (DEC-137) | Jesús |
| 2026-11-11 | Particulares con captura manual (DEC-150) | Jesús |

## 14. Revisión de consistencia
- Última revisión: 2026-11-11 (v1) — **APROBADO CON OBSERVACIONES**.
- Detalle: [revisiones/RN-015.md](/revisiones/RN-015.md)
