# RN-014 — Condición del producto y valor de usados

```yaml
id: RN-014
titulo: Condición del producto y valor de usados
grupo: común
estado: BORRADOR
version: 1
fecha: 2026-11-11
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-002, RN-013, RN-016]
```

## 1. ¿Qué queremos lograr?
Que OIP **no compare un producto usado contra precios de nuevo**. Un taladro usado a $70 no está "61% más barato" que uno nuevo a $179: son productos distintos (CASO-006). Esta regla define la condición de cada publicación y cuánto vale un usado.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- La **condición** de cada publicación, como dato obligatorio (DEC-149).
- El **valor de referencia** de un producto que no es nuevo.
- El ajuste por **accesorios faltantes**.

**No incluye:**
- La inspección física y los riesgos de comprar a un particular (RN-015).
- El precio de venta local (RN-016), aunque comparten la competencia local como dato.

## 3. ¿Cómo funciona, en palabras?
Cada publicación lleva su condición. Solo se comparan publicaciones en la **misma condición**. Para un usado, la mejor referencia es lo que **realmente se pagó** por usados iguales. Si no hay ventas registradas, se usa lo que piden otros vendedores en la zona, que es un techo. Si tampoco hay eso, un porcentaje del precio de nuevo, marcado como estimado.

## 4. La regla

**Condiciones:**

| Condición | Qué significa |
|---|---|
| Nuevo | Sin abrir, con garantía del fabricante |
| Caja abierta | Abierto o devuelto, completo, sin uso visible |
| Reacondicionado | Revisado por el fabricante o un tercero, con o sin garantía |
| Usado, buen estado | Funciona, desgaste normal |
| Usado, con detalles | Funciona, con desgaste visible |
| Para piezas | No funciona o no se pudo probar |

La condición es **obligatoria**. Si una publicación no la dice: tienda o comercio → se toma como **nuevo** solo si la ficha lo indica; particular → **usado, con detalles** hasta que Jesús la verifique.

**Valor de referencia de un producto que no es nuevo**, el primero que exista:

```
1. Mediana de ventas concretadas comparables (misma condición, últimos 90 días; al menos 3)
2. Menor precio pedido comparable en la zona (techo, RN-016), marcado "estimado"
3. Precio de mercado hoy del producto nuevo (RN-002) × factor de la condición, marcado "estimado"

Accesorio faltante: se resta el precio de mercado hoy del accesorio (por ejemplo, una batería).
                   La condición describe el estado físico; los faltantes solo se restan (no bajan además la condición).
```

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Factor caja abierta | Sobre el precio de nuevo | 85% | Por confirmar |
| Factor reacondicionado | Sobre el precio de nuevo | 75% | Por confirmar |
| Factor usado, buen estado | Sobre el precio de nuevo | 60% | Por confirmar |
| Factor usado, con detalles | Sobre el precio de nuevo | 45% | Por confirmar |
| Factor para piezas | Sobre el precio de nuevo | 20% | Por confirmar |
| Ventas concretadas mínimas | Para usar la mediana | 3 en 90 días | Por confirmar |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Usado comparado contra usados (CASO-006)**
- DEWALT DCF840 de un particular: $70, con batería de 2 Ah y cargador. Jesús lo verifica: **usado, buen estado**, contenido igual al kit DCF840D1.
- Ventas concretadas de usados iguales: ninguna registrada. Precios pedidos en la zona: ninguno comparable.
- Precio de mercado hoy del DCF840D1 nuevo: **$169.99, supuesto** (el ejercicio dio $179 para el D1 en Lowe's y $169.99 para otro kit, el C2; con el dato real del D1 cambia el resultado).
- Valor de referencia = 169.99 × 60% = **$101.99**, marcado "estimado".
- La comparación es $70 contra $101.99, **no** contra $179 de nuevo.

**Ejemplo B — Mismo usado, con detalles**
- Si tiene desgaste visible: 169.99 × 45% = **$76.50**, estimado. A $70, el margen casi desaparece.

**Ejemplo C — Con ventas concretadas**
- Ventas de usados iguales en 90 días: $95, $110, $100 → mediana = **$100**. Se usa esta, sin marca de estimado.

**Ejemplo D — Accesorio faltante**
- El mismo usado, pero sin batería. Batería igual nueva hoy: $49 (supuesto). Valor = 101.99 − 49 = **$52.99**, estimado.

## 6. ¿Qué información necesitamos?
- Condición de cada publicación (ficha del comercio, o lo que capture Jesús).
- Ventas concretadas de usados comparables (cuando existan; al inicio, las que registre Jesús).
- Precios pedidos comparables en la zona (RN-016).
- Precio de mercado hoy del producto nuevo y de sus accesorios (RN-002).

## 7. ¿Qué obtenemos?
- La condición de cada publicación y el valor de referencia de los usados, con su fuente y la marca "estimado" cuando corresponda.

## 8. ¿Quién participa?
- El sistema calcula.
- Jesús verifica la condición de lo que compra a particulares y registra las ventas concretadas que conozca.

## 9. ¿De qué depende?
- RN-002 (precio de nuevo), RN-013 (mismo producto) y RN-016 (precios pedidos en la zona).

## 10. Limitaciones
- Al inicio casi no habrá ventas concretadas registradas: la mayoría de los valores serán estimados.
- Los factores por condición son un punto de partida; varían mucho por categoría.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| No se conoce la condición | Comercio: nuevo solo si la ficha lo dice. Particular: usado, con detalles |
| No hay precio de nuevo ni usados comparables | Sin valor de referencia; revisión manual |
| La condición declarada no coincide con la inspección | Se corrige con lo que registre Jesús |

## 12. Preguntas para el experto
1. ¿Los factores por condición le parecen razonables para herramientas y electrónica? ¿Cambian por categoría?
2. ¿Dónde se pueden ver ventas concretadas de usados en EE. UU. de forma confiable?
3. ¿Conviene comprar "para piezas" alguna vez, o se excluye?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-11 | Usados en el alcance, con condición obligatoria y valor de usados comparables (DEC-149) | Jesús |

## 14. Revisión de consistencia
- Última revisión: 2026-11-11 (v1) — **APROBADO CON OBSERVACIONES**.
- Detalle: [revisiones/RN-014.md](/revisiones/RN-014.md)
