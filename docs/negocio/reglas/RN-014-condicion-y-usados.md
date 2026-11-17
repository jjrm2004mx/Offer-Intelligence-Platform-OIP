# RN-014 — Condición del producto y valor de usados

```yaml
id: RN-014
titulo: Condición del producto y valor de usados
grupo: común
estado: BORRADOR
version: 1
fecha: 2026-11-16
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-008, RN-013, RN-015, RN-016]
origen: DEC-149, DEC-150, DEC-151; ejercicio CASO-006
```

> **Regla nueva.** Los productos usados entran al alcance con **estado obligatorio** (DEC-149), y en el Inc. 1 las publicaciones de particulares las **captura Jesús** a mano (DEC-150). Lo marcado como propuesta está **por aceptar**.

## 1. ¿Qué queremos lograr?
Poder evaluar productos que no son nuevos, sobre todo los que venden particulares (OfferUp, Marketplace), **sin compararlos contra el precio de uno nuevo**. Un usado vale lo que valen otros usados iguales, no lo que cuesta nuevo en la tienda.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Los estados del producto.
- El valor de referencia de un usado.
- Requisitos para comprar a un particular.

**No incluye:**
- La búsqueda automática en sitios de particulares: después de revisar condiciones de uso, datos personales y protección de la IP (DEC-150).
- El riesgo de procedencia (RN-015).

## 3. ¿Cómo funciona, en palabras?
Cada producto lleva su estado. Si no es nuevo, su "precio habitual" es el de **usados comparables** en el mismo estado, de preferencia ventas que sí se concretaron. Comprar a un particular exige revisar el producto en persona antes de pagar, y cuesta dos traslados: recogerlo y entregarlo.

## 4. La regla

**Estados** (obligatorio): **nuevo · caja abierta · reacondicionado · usado · para piezas**.

```
valor de referencia (no nuevo) = mediana de usados comparables, mismo producto (RN-013) y mismo estado,
                                 de preferencia ventas concretadas
                                 (si solo hay precios pedidos: mediana de precios pedidos × 85%)
```

- Se necesitan **al menos 3** comparables; con menos, "sin referencia de usados" → revisión manual.
- Los comparables cuentan solo **en la zona de venta local**: Tijuana y todo el condado de San Diego (RN-016, DEC-171).
- Este valor reemplaza al precio habitual en el **descuento real** (RN-003) y sirve de base para el precio de venta local (RN-016).
- **Amazon y usados:** joyería, relojes y belleza usados no se venden en Amazon (RN-006); en las demás categorías, por confirmar con la cuenta de vendedor.
- **Compra a particulares:**
  - **Inspección física obligatoria** antes de pagar: funcionamiento, salud de la batería, autenticidad, procedencia y contenido exacto.
  - **Doble traslado** (RN-008): recoger entra en el costo de compra, entregar en el de venta.
  - Riesgo de procedencia (RN-015).

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Comparables mínimos | Cantidad | 3 | **Propuesta (por aceptar)** |
| Factor sobre precios pedidos | Cuando no hay ventas concretadas | 85% | **Propuesta (por aceptar)** |

Todos los valores son iniciales y configurables.

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Atornillador DEWALT DCF840 usado (CASO-006)**
- Un particular en San Diego pide $70. Precio de nuevo en Lowe's: $179, **no cuenta**.
- Usados comparables en la zona (precios pedidos): $120, $130, $140 → mediana $130 × 85% = **$110.50** de valor de referencia.
- Descuento real = (1 − 70 ÷ 110.50) × 100 = **36.7%** → sigue en evaluación (RN-003).
- Traslados: recoger $9.50 + entregar $9.50 (RN-008). Resultado: **"por investigar, requiere inspección física"**.

**Ejemplo B — Sin comparables**
- Solo hay 2 usados comparables → **sin referencia de usados** → revisión manual.

## 6. ¿Qué información necesitamos?
- Estado del producto (de la publicación o de la inspección).
- Usados comparables en la zona, con precio y si la venta se concretó.

## 7. ¿Qué obtenemos?
- Estado, valor de referencia y requisitos pendientes (inspección).

## 8. ¿Quién participa?
- Jesús captura las publicaciones de particulares y hace la inspección.
- El sistema calcula.

## 9. ¿De qué depende?
- RN-013 (mismo producto), RN-008 (traslados), RN-015 (riesgo) y RN-016 (zona de venta local).

## 10. Limitaciones
- Las ventas concretadas casi nunca se publican; al inicio la referencia sale de precios pedidos, con el factor de 85%.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| La publicación no dice el estado | Se trata como "usado" hasta la inspección |
| La inspección encuentra fallas | Se cambia el estado (por ejemplo, "para piezas") y se recalcula |
| El particular no permite revisar | No se recomienda comprar |

## 12. Preguntas para el experto
1. ¿85% de los precios pedidos es una buena estimación de lo que realmente se paga entre particulares?
2. ¿Bastan 3 comparables?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-11 | Productos usados en el alcance, con estado obligatorio y usados comparables (DEC-149) | Jesús |
| 2026-11-11 | Particulares con captura manual en el Inc. 1 (DEC-150) | Jesús |

## 14. Revisión de consistencia
- Última revisión: 2026-11-16 (v1) — APROBADO CON OBSERVACIONES
- Detalle: [revisiones/RN-014.md](/revisiones/RN-014.md)
