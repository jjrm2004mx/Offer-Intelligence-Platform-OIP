# CASO-003 — Audífonos Bose QuietComfort (primera generación)

```yaml
id: CASO-003
tipo: búsqueda de ofertas (A), "búsqueda abierta"
fecha_del_ejercicio: 2026-11-11
moneda: USD
comercios: solo EE. UU.
reglas_que_prueba: [RN-001, RN-002, RN-003, RN-004, RN-009, RN-012 (propuesta)]
estado: EN ANÁLISIS (las decisiones se toman al terminar los ejercicios)
```

> Los datos vienen del ejercicio y **no se verificaron** en el comercio.

## 1. La situación

Nadie pidió el producto: el ejercicio parte de **descubrir** algo que vale la pena comprar. El objetivo es que OIP **descubra oportunidades**, no que solo encuentre productos rebajados.

## 2. Datos encontrados

| Dato | Valor |
|---|---|
| Producto | Bose QuietComfort Wireless, **primera generación** |
| Comercio | Best Buy (en línea) |
| Precio de referencia anunciado | $359.00 |
| Precio de oferta | $169.00 |
| Ahorro anunciado | $190.00 (52.92%) |
| Calificación / reseñas | 4.7 / 5, con 590 reseñas en Best Buy |
| Disponibilidad | En línea; se puede agregar al carrito |
| Sustituto cercano | Segunda generación a $199.00 en Best Buy ($30.00 más) |
| Otras fuentes | Varios sitios de seguimiento reportan la misma baja |
| Historial | El precio de $169 ya se había observado antes; no se sabe si es el mínimo histórico |

## 3. Resultado con las reglas actuales y las decisiones DEC-123 a DEC-137

- **Calidad del precio:** el 52.92% es contra el precio anunciado de $359, que no es referencia (DEC-129). Que $169 ya se haya visto antes indica que es un **precio de oferta recurrente**. Con historial, lo más probable es "Buena oferta", no "Oferta excepcional". Sin historial ni comparación entre comercios: sin clasificación.
- **Oportunidad de reventa (A, RN-001 a RN-009):** si la baja aparece en varias fuentes, es probable que **todo el mercado** tenga el mismo precio, incluido Amazon. Entonces el precio de venta esperado se acerca a $169 y, después de comisiones, **el margen es negativo**. Resultado esperado: **DESCARTADA por margen**, aunque el descuento sea grande.
- **Demanda:** 590 reseñas. Mismo hueco que en CASO-002.
- **Disponibilidad:** "se puede agregar al carrito" es una señal fuerte de disponibilidad en línea.

## 4. Huecos que descubrió (pendientes de decisión)

1. **¿Para quién es la oportunidad?** Reventa (DEC-110) o compra para el consumidor final. Son evaluaciones distintas.
2. **Descuento general contra descuento aislado:** una baja que tiene todo el mercado no deja margen de reventa; la oportunidad de reventa es cuando un comercio está muy por debajo de los demás.
3. **Generación o versión del modelo:** el mismo nombre comercial ("QuietComfort") cubre dos generaciones. Es el tercer caso con este patrón (edición especial, kit, generación).
4. **Sustituto cercano:** la versión nueva cuesta $30 más; un modelo anterior puede perder valor de reventa cuando sale el nuevo.
5. **Criterio de "disponible confirmada" en línea:** propuesta, la ficha dice "en existencia" y permite agregar al carrito.

---

## 5. Revisión 2: comparación entre comercios (datos al 2026-11-09)

| Comercio | Precio | Disponibilidad | Nota |
|---|---|---|---|
| Best Buy | $169.00 | Disponible según la publicación | Algunas publicaciones son de **vendedores externos**: confirmar quién vende y envía |
| Amazon | $169.00 | Por confirmar | — |
| Target | $169.99 | En existencia | — |
| Lowe's | $249.00 | En existencia | — |
| Dell | $359.00 | En existencia | Igual al precio anunciado de referencia |
| Walmart | $363.00 | En existencia | **Por encima** del precio de referencia: probablemente vendedor externo |

**Fuente externa adicional:** una publicación editorial (NBC Select, 3 de noviembre) reporta $169 como el **precio más bajo del año**.

### 5.1 Resultado con estos datos

- **Competitividad:** $169 empata con el precio más bajo del mercado hoy (Best Buy, Amazon y Target dentro de $0.99).
- **Calidad del precio:** candidato a **"Buena oferta"** u **"Oferta excepcional"**, según los umbrales que se definan en RN-012. La señal de "mínimo del año" viene de una fuente externa, no del historial propio.
- **Oportunidad de reventa:** **DESCARTADA**. Amazon está en $169, así que el precio de venta esperado es igual al de compra y cualquier comisión vuelve negativo el margen (RN-001). Se confirma lo esperado en la sección 3.
- Se confirman los **dos ejes** (DEC-131): el mismo producto es de alta calidad de precio y nula oportunidad de reventa.

### 5.2 Huecos adicionales

6. **Precio publicado no es precio de venta:** Walmart a $363 no significa que alguien lo compre a ese precio. Para la comparación solo cuentan publicaciones del mismo producto exacto, vendidas por el comercio y disponibles; las demás se muestran aparte.
7. **Fuentes editoriales** (artículos de ofertas) como señal externa, igual que los comparadores (DEC-133): orientan, pero no sustituyen el historial ni la confirmación en la ficha.
8. **Categoría:** audio cabe en **tecnología**, que ya es una categoría acordada (DEC-006). Lo que falta es priorizar las categorías por temporada (DEC-138) para decidir qué páginas de ofertas recorrer primero.
9. **Umbrales de RN-012:** el "mínimo de 180 días o del año" es un buen criterio para "Oferta excepcional", pero exige un historial largo que OIP no tendrá al principio.
10. **Filtro previo al descubrimiento:** con el límite de consultas (RN-010), OIP no puede comparar cada producto rebajado en todos los comercios. El descuento anunciado sirve para **decidir qué investigar**, no para calificar la oferta.

---

## 6. Revisión 3: ¿está barato o conviene comprarlo? (2026-11-11)

**Historial supuesto del ejercicio** (hipotético, no verificado; contradice la señal editorial de "mínimo del año", y con datos reales solo una de las dos versiones será cierta):

| Periodo | Precio |
|---|---|
| Hace 180 días | $179 |
| Hace 90 días | $169 |
| Hace 30 días | $169 |
| Hoy | $169 |

### 6.1 Resultado con el historial supuesto

- **Descuento anunciado:** 52.92% contra $359. **Descuento real** contra el precio habitual ($169): **0%**.
- **Competitividad:** empata con Amazon y Target. Sin ventaja.
- **Calidad del precio (RN-012):** **"Precio competitivo"**, con la marca **"descuento anunciado no comprobado"**. Esto equivale a la conclusión del ejercicio: *producto con descuento comercial, sin ventaja competitiva demostrada*.
- **Búsqueda por artículo (B):** la mejor opción es la de **menor costo total** (precio + envío + condiciones), no la del mayor descuento anunciado.
- **Reventa (A):** DESCARTADA (sin cambio).

Conclusión: **el resultado depende del historial**. Con el historial supuesto no es una súper oferta; con la señal de "mínimo del año" podría serlo. Por eso OIP necesita su historial propio antes de calificar.

### 6.2 Huecos adicionales

11. **Tres preguntas, tres reglas:** ¿está barato? (RN-012), ¿dónde conviene comprarlo? (RN-011) y ¿conviene revenderlo? (RN-009).
12. **Cercanía al mínimo histórico** como criterio aparte del descuento contra la mediana.
13. **Costo total de compra:** precio, envío, impuestos, cupones, membresías necesarias, devolución y garantía.
14. **La marca de "descuento anunciado no comprobado"** debe ir separada de la clasificación del precio: un precio puede ser competitivo aunque su anuncio esté inflado.
