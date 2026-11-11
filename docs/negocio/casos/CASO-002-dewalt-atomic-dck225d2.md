# CASO-002 — Kit DEWALT ATOMIC 20V MAX (DCK225D2)

```yaml
id: CASO-002
tipo: búsqueda por artículo (B) y búsqueda de ofertas (A)
fecha_del_ejercicio: 2026-11-11
moneda: USD
comercios: solo EE. UU.
reglas_que_prueba: [RN-003, RN-004, RN-007, RN-011, RN-012 (propuesta)]
estado: EN ANÁLISIS (las decisiones se toman al terminar los ejercicios)
```

> Los datos vienen del ejercicio y **no se verificaron** en el comercio. El precio y la disponibilidad pueden variar según la ubicación.

## 1. La situación

Un cliente no pide un modelo exacto: **necesita una herramienta** (un taladro y un atornillador de impacto). El ejercicio propone este kit como respuesta y pregunta si **OIP lo encontraría por sí mismo**, sin que se le indique la tienda ni el precio.

## 2. Datos encontrados

| Dato | Valor |
|---|---|
| Producto | DEWALT ATOMIC 20V MAX, modelo **DCK225D2** |
| Contenido | Taladro, atornillador de impacto, 2 baterías de 2.0 Ah, cargador, bolsa |
| Comercio | The Home Depot (catálogo de promociones) |
| Precio tachado ("antes") | $249.00 |
| Precio de oferta | $169.00 |
| Ahorro anunciado | $80.00 (32.13%) |
| Calificación / reseñas | 4.7 / 5, con 5,188 reseñas; marcado como producto destacado |
| Otros comercios | Sin datos |
| Historial propio de OIP | Ninguno |
| Disponibilidad | Sin confirmar; varía por tienda |

## 3. Resultado con las reglas actuales y las decisiones DEC-123 a DEC-137

- **Calidad del precio:** el 32% se calcula contra el **precio tachado**, que no es referencia (DEC-129). Sin historial y sin precios de otros comercios, OIP no puede afirmar que haya descuento ni que el precio sea competitivo. **Resultado: sin clasificación**, hasta tener la comparación entre comercios.
- **Demanda:** las reseñas y la etiqueta "destacado" no están en ninguna regla. RN-004 solo usa el Sales Rank de Amazon.
- **Búsqueda por artículo (B):** RN-011 parte de un producto concreto (modelo o UPC). Una búsqueda **por necesidad** no está cubierta.
- **Búsqueda de ofertas (A):** Home Depot es un comercio del Inc. 1 y su catálogo de promociones es una entrada natural. OIP sí encontraría esta publicación, pero para evaluarla le faltan el precio de venta esperado y la demanda (RN-001, RN-002, RN-004).
- **Disponibilidad:** se consulta por tienda (RN-007), y para tienda física cuenta el costo del viaje (RN-008).

## 4. Huecos que descubrió (pendientes de decisión)

1. **Búsqueda por necesidad:** el cliente describe lo que necesita y OIP propone modelos.
2. **Reseñas como señal de demanda** fuera de Amazon.
3. **Equivalencia de kits:** el mismo nombre puede traer otro contenido (baterías de otra capacidad, sin bolsa). Solo se comparan publicaciones con el mismo modelo o el mismo contenido.
4. **Modelos exclusivos de un comercio:** si un modelo se vende solo en una tienda, no hay comparación horizontal posible; habría que comparar contra kits equivalentes.
