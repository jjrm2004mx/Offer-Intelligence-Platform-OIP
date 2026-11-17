# RN-013 — Identificación del producto y datos de cada observación

```yaml
id: RN-013
titulo: Identificación del producto y datos de cada observación
grupo: común
estado: BORRADOR
version: 1
fecha: 2026-11-16
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-014]
origen: DEC-027, DEC-134, DEC-145; ejercicios CASO-001, CASO-002, CASO-003, CASO-006
```

> **Regla nueva.** Junta lo que ya estaba decidido sobre identificar el producto (DEC-027) y los datos que se capturan en cada observación (DEC-134). En los ejercicios, cuatro casos fallaron por lo mismo: edición, kit, generación o contenido distintos. Lo marcado como propuesta está **por aceptar**.

## 1. ¿Qué queremos lograr?
Comparar **solo el mismo producto**. Un descuento o una comparación no sirve si se compara un kit contra la herramienta sola, una edición especial contra la normal o una generación contra otra.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Cuándo dos publicaciones son el mismo producto.
- Qué datos se guardan en cada observación de precio.
- Qué pasa cuando no hay certeza.

**No incluye:**
- El valor de los productos usados (RN-014).
- El riesgo del vendedor (RN-015).

## 3. ¿Cómo funciona, en palabras?
Lo más seguro es el **código de barras** del producto (UPC/EAN/GTIN). Si no hay código, se usan el modelo y la marca; el nombre solo ayuda a encontrar candidatos. Si no hay certeza, la comparación queda **"no confirmada"** y Jesús la revisa.

## 4. La regla

**4.1 Mismo producto** = mismo **modelo, versión, generación, edición y contenido** (lo que trae la caja), y el mismo **estado** (RN-014). Orden de evidencia:

| Evidencia | Resultado |
|---|---|
| 1. Código de barras válido (con su dígito verificador) y mismo contenido | **Confirmada** |
| 2. Número de modelo del fabricante + marca, mismo contenido | **Confirmada**, si el modelo distingue kits y ediciones; si no, no confirmada |
| 3. Solo nombre, marca y características | **COINCIDENCIA NO CONFIRMADA** → revisión manual (RN-009) o "otras opciones" (RN-011) |

- Kit contra herramienta sola, paquete de 2 contra 1, color o capacidad distintos: **productos distintos**.
- Jesús puede corregir manualmente una identificación; queda registrado quién y cuándo.

**4.2 Datos de cada observación** (DEC-134):
1. Identificación: código, modelo, marca, contenido.
2. Precio, y precio tachado si lo hay.
3. **Vendedor:** el propio comercio o un vendedor externo.
4. Disponibilidad con sus estados (RN-007).
5. Envío: costo, plazo, envío o recoger en tienda.
6. MSRP con fuente y fecha, si se conoce.
7. Estado del producto (RN-014).
8. Fecha y hora.

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Evidencia mínima para comparar | Código o modelo + marca | Ver tabla | DEC-027, DEC-134 |
| Contenido idéntico | Obligatorio | Sí | **Propuesta (por aceptar)**, de 4 ejercicios |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Mismo código**
- Taladro en Home Depot y en Amazon con el mismo código de barras y "herramienta, batería y cargador" en ambos → **confirmada**.

**Ejemplo B — Kit contra herramienta sola (CASO-006)**
- DEWALT DCF840D1 (con batería, cargador y bolsa) contra DCF840 con otra batería → contenido distinto → **productos distintos**; no se comparan.

**Ejemplo C — Solo por nombre**
- "Consola Switch OLED blanca" sin código ni modelo → **COINCIDENCIA NO CONFIRMADA**.

## 6. ¿Qué información necesitamos?
- Lo que publica cada comercio en la ficha: código, modelo, marca, contenido, vendedor y estado.

## 7. ¿Qué obtenemos?
- Para cada par de publicaciones: confirmada / no confirmada / distintas, con la evidencia usada.

## 8. ¿Quién participa?
- El sistema identifica.
- Jesús confirma o corrige los casos no confirmados.

## 9. ¿De qué depende?
- De que los comercios publiquen código o modelo en la ficha.
- RN-014 (estado).

## 10. Limitaciones
- Algunos comercios no publican el código de barras; esos casos dependen del modelo o de la revisión manual.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| El código no pasa el dígito verificador | Se ignora el código; se usa el modelo |
| Mismo código pero contenido distinto | Se tratan como distintos y se avisa |
| No se conoce el estado | Se trata como no confirmada |

## 12. Preguntas para el experto
1. ¿Conoce otros casos frecuentes en que el mismo modelo se vende con contenido distinto?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-11 | Datos de cada observación (DEC-134) | Jesús |
| 2026-11-11 | Sin código, la comparación queda "no confirmada" (DEC-134) | Jesús |

## 14. Revisión de consistencia
- Última revisión: 2026-11-16 (v1) — RECHAZADO
- Detalle: [revisiones/RN-013.md](/revisiones/RN-013.md)
