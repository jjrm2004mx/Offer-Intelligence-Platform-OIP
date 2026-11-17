# RN-012 — Calidad del precio (eje 1)

```yaml
id: RN-012
titulo: Calidad del precio
grupo: común
estado: BORRADOR
version: 1
fecha: 2026-11-16
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-002, RN-003, RN-013, RN-015]
origen: DEC-128, DEC-129, DEC-131, DEC-145; ejercicios CASO-001 a CASO-005
```

> **Regla nueva.** Es el **eje 1** de la clasificación (DEC-131): dice qué tan bueno es un precio **para cualquier comprador**. El eje 2, si conviene para revender, es RN-009. Aplica a las dos funcionalidades: la búsqueda de ofertas la muestra junto al nivel y la búsqueda por artículo solo usa este eje. Los umbrales son **propuestas de Claude** tomadas de los ejercicios ([pendientes de consolidación](/analisis/pendientes-de-consolidacion.md), §2) y están **por aceptar**.

## 1. ¿Qué queremos lograr?
Evitar anunciar como gran oferta algo que solo tiene precio normal. Un precio es bueno si está **por debajo de lo que el producto cuesta normalmente** y **entre los más baratos del mercado hoy**.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Cinco clases de precio y cómo se asigna cada una.
- Cuántos comercios hacen falta para calificar.

**No incluye:**
- Si conviene revender (RN-009).
- Cómo se obtienen el precio habitual y el de mercado hoy (RN-002).

## 3. ¿Cómo funciona, en palabras?
Se miden tres cosas que no se mezclan (DEC-128): el **descuento** contra el precio habitual, la **competitividad** contra los otros comercios hoy y, para las mejores, si el precio es **el más bajo que se ha visto**. Si hay señales de engaño, el precio queda como "cuestionable", sin importar los números.

## 4. La regla

```
descuento contra el habitual (%) = (1 − precio ÷ precio habitual) × 100               (RN-002, RN-003)
entre los más baratos            = precio ≤ precio de mercado hoy × (1 + 2%)
```

Se asigna **la primera** clase que se cumpla, de arriba hacia abajo:

| Clase | Condición |
|---|---|
| **Descuento cuestionable** | PRECIO ANTES INFLADO (RN-003); o vendedor externo sin confirmar (RN-015); o un **descuento anunciado** que solo se puede comparar contra **un comercio** (CASO-005). Distinto de la marca DESCUENTO ANUNCIADO NO COMPROBADO de RN-003, que no cambia la clase |
| **Oferta excepcional** | Descuento ≥ **15%**, entre los más baratos y **menor** que el mínimo registrado (con al menos 90 días de historial). Igualar un mínimo anterior no basta |
| **Buena oferta** | Descuento ≥ **15%** y entre los más baratos |
| **Precio competitivo** | Entre los más baratos, pero con descuento menor de 15%; o **sin historial suficiente** (solo MSRP o comparación entre comercios), que nunca pasa de esta clase |
| **Precio normal** | Todo lo demás |

- **Mínimo de comercios:** para pasar de "Precio competitivo" se necesitan datos de **al menos 2 comercios** además del evaluado. Que dos comercios independientes tengan el mismo precio bajo lo hace más creíble (CASO-004).
- La marca **DESCUENTO ANUNCIADO NO COMPROBADO** (RN-003) se muestra aparte y no cambia la clase.
- OIP usa **mediana**; los sitios externos suelen usar promedio, así que sus números pueden diferir (CASO-004).

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Descuento para Buena oferta | % bajo el habitual | 15% | **Propuesta (por aceptar)** |
| Tolerancia "entre los más baratos" | % sobre el más barato | 2% | **Propuesta (por aceptar)** |
| Historial para Oferta excepcional | Días mínimos | 90 | **Propuesta (por aceptar)** |
| Comercios mínimos | Además del evaluado | 2 | **Propuesta (por aceptar)** |

Todos los valores son iniciales y configurables.

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Licuadora Ninja BN701 (CASO-004) → Buena oferta**
- Precio $79.99; habitual de referencia $100.39 → descuento (1 − 79.99 ÷ 100.39) × 100 = **20.3%** ≥ 15% ✓.
- Mercado hoy: JCPenney $79.99, Walmart $108.90 y otros a $109.99 → 79.99 ≤ 79.99 × 1.02 ✓; más de 2 comercios ✓.
- Mínimo registrado: $79.99 (Black Friday 2025) → **igual, no menor** → no es excepcional → **Buena oferta**.

**Ejemplo B — Sierra circular → Buena oferta**
- Situación base (RN-002, ejemplo B): $29 contra habitual $119 → **75.6%** ✓. Mercado hoy $119 (Amazon $119, Walmart $124: 2 comercios ✓) → 29 ≤ 121.38 ✓.
- Solo 60 días de historial (menos de 90) → no puede ser excepcional → **Buena oferta**.

**Ejemplo C — Baterías Milwaukee (CASO-005) → Descuento cuestionable**
- Walmart a $120, vendedor sin confirmar, y solo se compara contra Home Depot → **Descuento cuestionable**.

**Ejemplo D — Sin historial**
- Producto recién visto, MSRP $199, hoy $169 y es el más barato de 3 comercios → **Precio competitivo** (sin historial no pasa de aquí).

**Ejemplo E — Precio normal**
- $105 con habitual $110 (4.5%) y el más barato hoy a $95 → no está entre los más baratos (105 > 96.90) → **Precio normal**.

## 6. ¿Qué información necesitamos?
- Precio habitual, precio de mercado hoy, mínimo registrado y días de historial (RN-002).
- Marcas de RN-003 y vendedor (RN-013, RN-015).

## 7. ¿Qué obtenemos?
- La clase de precio, con los datos que la justifican.

## 8. ¿Quién participa?
- El sistema clasifica.
- El experto valida los umbrales.

## 9. ¿De qué depende?
- RN-002, RN-003, RN-013 y RN-015.

## 10. Limitaciones
- Al inicio no hay 90 días de historial: ninguna oferta podrá ser "Oferta excepcional" durante los primeros meses.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| No hay precio de mercado hoy | No puede saber si está entre los más baratos → máximo "Precio competitivo" |
| Menos de 2 comercios de comparación | Máximo "Precio competitivo"; si además el descuento anunciado solo se compara contra un comercio, Descuento cuestionable |
| El precio está por encima del habitual | Precio normal |

## 12. Preguntas para el experto
1. ¿15% bajo el precio habitual es buen umbral para "Buena oferta"?
2. ¿Le parece bien exigir que el precio sea **menor** que el mínimo registrado para llamarlo "Oferta excepcional"?
3. ¿Bastan 2 comercios de comparación?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-11 | Tres indicadores que no se mezclan: descuento, competitividad y demanda (DEC-128) | Jesús |
| 2026-11-11 | Cuatro referencias de precio; descuento solo contra el habitual (DEC-129) | Jesús |
| 2026-11-11 | Dos ejes: calidad del precio (esta regla) y oportunidad de reventa (RN-009) (DEC-131) | Jesús |

## 14. Revisión de consistencia
- Última revisión: 2026-11-16 (v2.1) — APROBADO CON OBSERVACIONES
- Detalle: [revisiones/RN-012.md](/revisiones/RN-012.md)
