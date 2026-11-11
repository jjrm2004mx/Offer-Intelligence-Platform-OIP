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
