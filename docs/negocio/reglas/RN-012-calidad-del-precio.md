# RN-012 — Calidad del precio

```yaml
id: RN-012
titulo: Calidad del precio
grupo: común
estado: BORRADOR
version: 1
fecha: 2026-11-11
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-002, RN-003, RN-013, RN-014, RN-015]
```

## 1. ¿Qué queremos lograr?
Responder **"¿está barato?"** con una clasificación honesta, para que OIP nunca anuncie como gran oferta algo que solo tiene su precio normal. Es el **primer eje** de clasificación; el segundo, "¿conviene revenderlo?", es RN-009 (DEC-131).

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Cuatro clases: **Oferta excepcional**, **Buena oferta**, **Precio competitivo** y **Descuento cuestionable**, más "sin clasificación".
- Aplica a las tres búsquedas: ofertas (A), artículo específico (B) y particulares (F3).

**No incluye:**
- Si conviene revenderlo (RN-009) o dónde conviene comprarlo (RN-011).
- La demanda (RN-004 y RN-017): un producto puede tener excelente precio y poca demanda.

## 3. ¿Cómo funciona, en palabras?
Se miran dos cosas a la vez: si el precio está **por debajo de lo normal** (descuento real, RN-003) y si está **entre los más baratos de hoy** (ventaja contra el mercado, RN-003). Solo cuando las dos se cumplen hay una oferta. Si el precio repite o rompe su mínimo de un año, la oferta es excepcional. Sin historial, lo más que se puede decir es "precio competitivo". Y si hay señales de riesgo o un anuncio inflado sin ventaja, el descuento es cuestionable.

## 4. La regla

"**Entre los más baratos**" = precio de oferta ≤ precio de mercado hoy × 1.02 (no más de 2% arriba del más barato de los otros comercios).

Se asigna la **primera** clase que se cumpla, en este orden:

| Orden | Clase | Condición |
|---|---|---|
| 1 | **Descuento cuestionable** | Riesgo **Alto** (RN-015), **o** vendedor externo, **o** "precio antes inflado" (RN-003) sin estar entre los más baratos |
| 2 | **Oferta excepcional** | Descuento real ≥ **15%**, entre los más baratos **y** precio **menor** que el mínimo de 12 meses (RN-002) |
| 3 | **Buena oferta** | Descuento real ≥ **15%** y entre los más baratos |
| 4 | **Precio competitivo** | Entre los más baratos; **o**, sin precio de mercado hoy, descuento real ≥ 15% o precio ≤ MSRP |
| 5 | **Sin clasificación** | Ninguna de las anteriores |

Reglas adicionales:
- **Sin historial suficiente** (RN-002): el máximo es **Precio competitivo** (DEC-129).
- **Sin mínimo de 12 meses** (menos de un año de historial): no puede haber **Oferta excepcional**.
- La marca **"descuento anunciado no comprobado"** (RN-003) se muestra **junto** a la clase, sin cambiarla: un precio puede ser competitivo aunque su anuncio esté inflado.
- Solo se comparan productos iguales (RN-013) y en la misma condición (RN-014).

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Tolerancia "entre los más baratos" | % sobre el precio de mercado hoy | 2% | Por confirmar |
| Descuento real mínimo | Para Buena oferta y Oferta excepcional | 15% | Por confirmar (calibrado con CASO-004) |
| Referencia de excepcional | Mínimo contra el que se compara | 12 meses | Por confirmar |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Buena oferta (CASO-004, con historial propio supuesto)**
- Ninja BN701 en Amazon: $79.99, vendido por Amazon.com.
- Precio habitual (60 días): $104.99. Precio de mercado hoy (otros comercios): $79.99 (JCPenney). Mínimo de 12 meses: $79.99 (Black Friday 2025).
- Descuento real = (1 − 79.99 ÷ 104.99) × 100 = **23.81%** ≥ 15% ✓.
- Entre los más baratos: 79.99 ≤ 79.99 × 1.02 = 81.59 ✓.
- ¿Menor que el mínimo de 12 meses? 79.99 no es menor que 79.99 ✗.
- Resultado: **Buena oferta**.

**Ejemplo B — Oferta excepcional (mismo producto, precio supuesto)**
- La misma licuadora a $59.99: descuento real = (1 − 59.99 ÷ 104.99) × 100 = **42.86%** ✓; entre los más baratos ✓; 59.99 < 79.99 ✓.
- Resultado: **Oferta excepcional**.

**Ejemplo C — Precio competitivo con anuncio inflado (CASO-003, historial supuesto)**
- Bose QuietComfort en Best Buy: $169. Precio habitual $169 → descuento real 0%. Precio de mercado hoy $169 → entre los más baratos ✓.
- Resultado: **Precio competitivo**, con la marca **"descuento anunciado no comprobado"** (anunciado 52.92%).

**Ejemplo D — Sin historial (CASO-001)**
- Switch 2 Zelda en Amazon: $499.99. Sin historial, sin precio de mercado hoy (todo agotado o sin confirmar); MSRP $519.99.
- 499.99 ≤ 519.99 → **Precio competitivo** (el máximo posible sin historial).
- Walmart a $459.99 con **vendedor externo** → **Descuento cuestionable**.

**Ejemplo E — Sin clasificación (CASO-005)**
- Baterías Milwaukee en Walmart: $120. Un solo comercio de comparación (Home Depot $269), sin historial, sin MSRP y vendedor sin confirmar.
- No hay precio de mercado hoy, ni descuento real, ni MSRP → **Sin clasificación** hasta tener más datos.

## 6. ¿Qué información necesitamos?
- Descuento real, ventaja contra el mercado y marcas (RN-003).
- Precio de mercado hoy, mínimo de 12 meses y MSRP (RN-002).
- Nivel de riesgo y tipo de vendedor (RN-015).

## 7. ¿Qué obtenemos?
- La clase de calidad del precio, con las marcas que la acompañan y una explicación corta ("23.81% bajo su precio habitual; empata con el más barato").

## 8. ¿Quién participa?
- El sistema clasifica.
- El experto valida los umbrales.

## 9. ¿De qué depende?
- RN-002, RN-003, RN-013, RN-014 y RN-015.

## 10. Limitaciones
- Los primeros meses casi nada podrá ser "Oferta excepcional", porque no habrá 12 meses de historial (salvo Keepa, solo para Amazon).
- Los nombres de las clases se parecen a los niveles de reventa de RN-009 v1 ("Excepcional", "Buena"). RN-009 v2 los renombra para no confundirlos.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| No hay precio habitual ni precio de mercado hoy ni MSRP | Sin clasificación |
| El precio está más de 2% arriba del más barato | No es oferta, aunque tenga descuento real |
| El vendedor no está confirmado | Se clasifica cuando se confirme; mientras, "sin clasificación" |
| El producto es usado | Se compara contra usados comparables (RN-014) |

## 12. Preguntas para el experto
1. ¿Las cuatro clases y su orden le parecen claros para un cliente?
2. ¿15% de descuento real es un buen mínimo para "Buena oferta"?
3. ¿Romper el mínimo de 12 meses es el criterio correcto para "excepcional", o bastaría con igualarlo?
4. ¿2% es una tolerancia razonable para "entre los más baratos"?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-11 | Dos ejes de clasificación: calidad del precio (esta regla) y oportunidad de reventa (RN-009) (DEC-131) | Jesús |
| 2026-11-11 | Sin historial, el máximo es "Precio competitivo" (DEC-129) | Jesús |

## 14. Revisión de consistencia
- Última revisión: 2026-11-11 (v1) — **RECHAZADO**: corregir y reinspeccionar.
- Detalle: [revisiones/RN-012.md](/revisiones/RN-012.md)
