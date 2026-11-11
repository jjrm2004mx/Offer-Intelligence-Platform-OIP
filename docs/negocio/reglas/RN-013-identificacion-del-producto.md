# RN-013 — Identificación del producto y de su origen

```yaml
id: RN-013
titulo: Identificación del producto y de su origen
grupo: común
estado: BORRADOR
version: 1
fecha: 2026-11-11
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: []
```

## 1. ¿Qué queremos lograr?
Que OIP **solo compare productos iguales**. En los ejercicios, cuatro casos de seis tenían el mismo problema: una edición especial, un kit con otro contenido, otra generación del mismo modelo y un kit con otra presentación. Comparar productos distintos produce descuentos y márgenes falsos.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Identificar el producto: marca, modelo, código (UPC/EAN/GTIN), versión o generación, edición y contenido.
- Decidir si dos publicaciones son **el mismo producto** y con qué certeza.
- Registrar el **origen** de cada publicación: tipo de fuente y tipo de vendedor (DEC-134).

**No incluye:**
- La condición del producto, nuevo o usado (RN-014).
- Buscar productos **equivalentes** pero distintos, como otro modelo que cumple la misma función: es la búsqueda por necesidad, funcionalidad futura (DEC-152).

## 3. ¿Cómo funciona, en palabras?
Cada publicación se identifica con el dato más confiable que tenga. El mejor es el código de barras del fabricante (GTIN), porque distingue ediciones y kits. Si no hay código, se usa el número de modelo más la marca, y se revisa que el contenido coincida. Si solo hay un título, la coincidencia es dudosa y esa publicación no se usa para comparar.

## 4. La regla

**Nivel de identificación**, del más al menos confiable (DEC-027):

| Nivel | Cómo se identifica | Certeza | ¿Cuenta para comparar? |
|---|---|---|---|
| 1 | **GTIN** (UPC/EAN) con dígito verificador válido | **Confirmada** | Sí |
| 2 | **Modelo exacto + marca**, con el **mismo contenido** (versión, edición, accesorios incluidos) | **Confirmada** | Sí |
| 3 | Modelo + marca, pero el contenido **no se pudo verificar** | **No confirmada** | No; se muestra aparte |
| 4 | Solo el título o la descripción | **COINCIDENCIA DUDOSA** | No; nunca genera alerta automática |
| — | Captura manual de Jesús (particulares, DEC-150) | La que Jesús registre, con foto de la etiqueta si existe | Según el nivel registrado |

**Dos publicaciones son el mismo producto** si coinciden en: marca, modelo, **versión o generación**, **edición** y **contenido** (número y tipo de piezas, capacidad de baterías, accesorios). El color cuenta solo cuando cambia el precio.

**Origen de cada publicación** (se registra siempre):
- **Tipo de fuente:** tienda en línea · tienda física · particular (OfferUp, Facebook Marketplace u otra plataforma) · contacto directo.
- **Tipo de vendedor:** el comercio · vendedor externo del marketplace del comercio · particular · fabricante.

**Comprobación del dígito verificador** (GTIN de 12 dígitos): se multiplican los primeros 11 dígitos, alternando ×3 y ×1 empezando por el primero; se suman; el verificador es lo que le falta a la suma para llegar a la siguiente decena.

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Niveles que cuentan para comparar | Certeza mínima | Niveles 1 y 2 | Por confirmar |
| ¿El color cuenta? | Variantes de color | Solo si cambia el precio | Por confirmar |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Dígito verificador**
- Código 03600029145**2**. Primeros 11 dígitos: 0 3 6 0 0 0 2 9 1 4 5.
- Suma = 0×3 + 3×1 + 6×3 + 0×1 + 0×3 + 0×1 + 2×3 + 9×1 + 1×3 + 4×1 + 5×3 = 0 + 3 + 18 + 0 + 0 + 0 + 6 + 9 + 3 + 4 + 15 = **58**.
- A 58 le faltan **2** para llegar a 60 → verificador 2 ✓ → **identificación confirmada (nivel 1)**.

**Ejemplo B — Edición especial (CASO-001)**
- "Nintendo Switch 2" y "Nintendo Switch 2 – Zelda 40th Anniversary Edition" tienen GTIN distinto → **no son el mismo producto**; no se comparan.

**Ejemplo C — Generación (CASO-003)**
- Bose QuietComfort de primera y de segunda generación: mismo nombre comercial, distinto modelo → **no son el mismo producto**. La segunda generación se puede mostrar como **sugerencia** (DEC-139), no como comparación.

**Ejemplo D — Contenido del kit (CASO-002 y CASO-006)**
- DEWALT DCF840D1 (con batería, cargador y bolsa) y DCF840C2 (otro kit): mismo modelo base, distinto contenido → **no son el mismo producto**.
- Una publicación "DCF840" de un particular sin detalle del contenido → **nivel 3, no confirmada**, hasta que Jesús verifique qué incluye.

**Ejemplo E — Solo título**
- "Taladro inalámbrico 20V profesional" sin marca ni modelo → **COINCIDENCIA DUDOSA**; no cuenta para precios ni genera alertas.

## 6. ¿Qué información necesitamos?
- GTIN, marca, modelo, versión, edición y contenido, de la ficha del comercio (datos estructurados de la página cuando existan).
- Tipo de fuente y de vendedor.
- Para particulares: lo que Jesús capture (modelo, contenido, foto de la etiqueta).

## 7. ¿Qué obtenemos?
- Para cada publicación: nivel de identificación, certeza y origen.
- Para cada par de publicaciones: si son el mismo producto.

## 8. ¿Quién participa?
- El sistema identifica y compara.
- Jesús confirma las identificaciones de nivel 3 y las capturas manuales.

## 9. ¿De qué depende?
- De que las fichas de los comercios muestren el código o el modelo.
- La alimentan RN-002, RN-003, RN-011 y RN-012: ninguna compara sin pasar por esta regla.

## 10. Limitaciones
- Algunos comercios venden **modelos exclusivos** con número propio; no hay con qué compararlos directamente (CASO-002). Quedan sin precio de mercado hoy.
- Los particulares rara vez publican el código; casi siempre serán nivel 2 o 3.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| El GTIN no pasa el dígito verificador | Se ignora el código y se baja al nivel 2 |
| Dos publicaciones tienen el mismo GTIN pero distinto contenido declarado | Se marcan para revisión manual |
| El modelo es exclusivo de un comercio | Se identifica, pero queda "comparación insuficiente" (RN-002) |
| Un particular no dice qué incluye | Nivel 3 hasta que Jesús lo verifique |

## 12. Preguntas para el experto
1. ¿Hay categorías donde el color, la talla o la capacidad cambien mucho el precio y deban contar siempre?
2. ¿Conoce casos frecuentes de modelos exclusivos por comercio en herramientas o electrónica?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-08 | Identificación: GTIN → modelo + marca → búsqueda → título solo auxiliar (DEC-027) | Jesús |
| 2026-11-11 | Datos a capturar en cada observación, con vendedor y origen (DEC-134) | Jesús |
| 2026-11-11 | Particulares con captura manual en el Inc. 1 (DEC-150) | Jesús |

## 14. Revisión de consistencia
- Última revisión: pendiente.
- Detalle: `revisiones/RN-013.md` (por crear)
