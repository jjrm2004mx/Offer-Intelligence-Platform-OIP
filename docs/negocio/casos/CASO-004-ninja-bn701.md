# CASO-004 — Licuadora Ninja Professional Plus BN701

```yaml
id: CASO-004
tipo: búsqueda de ofertas (A) y calidad del precio; primer caso positivo
fecha_del_ejercicio: 2026-11-11
moneda: USD
comercios: solo EE. UU.
reglas_que_prueba: [RN-002, RN-003, RN-004, RN-009, RN-011, RN-012 (propuesta)]
estado: EN ANÁLISIS (las decisiones se toman al terminar los ejercicios)
```

> Datos del ejercicio, tomados de sitios de seguimiento de precios (comparación entre comercios del 2026-11-07). **No se verificaron** en los comercios.

## 1. La situación

Se aplicó un filtro exigente: no basta la etiqueta de descuento; se busca evidencia de que el precio esté por debajo de lo que **normalmente cuesta** y de lo que **ofrecen otros comercios**.

## 2. Datos encontrados

| Dato | Valor |
|---|---|
| Producto | Ninja Professional Plus, modelo **BN701** (1,400 W, 72 oz) |
| Precio actual en Amazon | $79.99, **vendido por Amazon.com** |
| Precio tachado de referencia | $119.99 (anunciado 33.34%) |
| Promedio de 90 días (fuente externa) | $100.39 |
| Mínimo de 90 días | $79.99 (el actual) |
| Antecedente | $79.99 ya apareció en Black Friday de 2025 |
| Calificación / reseñas | 4.7 / 5, con unas 19,780 reseñas en Amazon |

| Comercio | Precio |
|---|---|
| Amazon | $79.99 |
| JCPenney | $79.99 |
| Walmart | $108.90 |
| Nordstrom, Macy's, Wayfair, Home Depot, Best Buy | $109.99 |

## 3. Resultado esperado

- **Descuento real** contra el promedio de 90 días: $20.40 (**20.32%**). El 33.34% contra el precio tachado no cuenta (DEC-129).
- **Competitividad:** **27.28%** por debajo de los comercios a $109.99 (26.55% contra Walmart). Dos comercios independientes tienen el mismo precio, lo que **confirma que el precio es real** y no un error.
- **Cercanía al mínimo:** igual al mínimo de 90 días, pero **igual, no menor**, al de Black Friday de 2025.
- **Calidad del precio (RN-012):** **"Buena oferta"**. No llega a "Oferta excepcional" porque repite un mínimo anterior.
- **Búsqueda por artículo (B):** empate en $79.99 entre Amazon y JCPenney; decide el **costo total** (envío, membresía, devolución).
- **Reventa (A):** **DESCARTADA**. El precio más bajo del mercado es el de Amazon, donde se vendería; no hay diferencia que aprovechar.

## 4. Huecos que descubrió (pendientes de decisión)

1. **Calibrar umbrales de RN-012:** este caso sirve de referencia para "Buena oferta" (cerca de 20% bajo el habitual y cerca de 27% bajo el mercado).
2. **Promedio contra mediana:** la fuente externa usa promedio de 90 días; OIP usa mediana (DEC-130, 60 días en historial propio; RN-002, 90 días para Amazon). Los números pueden diferir.
3. **Confirmación por segundo comercio:** dos comercios independientes al mismo precio aumentan la confianza en el dato.
4. **Sitios de seguimiento de precios como fuente de historial** mientras OIP no tenga el suyo: no están en las etapas de DEC-123.
5. **Desempate** cuando dos comercios tienen el mismo precio.
